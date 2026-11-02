"""첫 글자 시간 실측(티켓 44): 도우미와 같은 엔진(질문 바꾸기 5개 흘려 받기 + 답변 모델 2개 동시)으로 문항을 돌리며
호출마다 보냄·첫 조각·검색어 닫힘·끝 시각과 토큰을 남기고, 새 호출 없이 방법 1-3 각각의 단축을 가른다.

- 방법 1(흘려 받기): 5개 중 먼저 끝난 시각 − 먼저 검색어가 닫힌 시각
- 방법 2(3 → 5개): 앞 3개 중 먼저 닫힌 시각 − 5개 중 먼저 닫힌 시각
- 방법 3(답변 2개): 첫째 답변의 첫 조각까지 − 둘 중 빠른 쪽의 첫 조각까지(각자 보낸 시각부터)
- 옛 방식 어림 첫 글자: 잰 첫 글자 + (앞 3개 중 먼저 끝난 시각 − 쓴 검색어가 닫힌 시각) + 방법 3의 단축
적중은 search_compare와 같은 기준(질문마다 필요한 근거 중 상위 top_k에서 찾은 비율의 평균, HISTORY [127]의 85.3%와 견줌)이다.
쓰지 않은 검색어도 채점하려고, 다 돈 뒤 모든 검색어를 임베딩해 같은 검색으로 순위를 낸다(아주 적은 비용).
돈이 든다. 어림 비용을 보이고 --yes가 있어야 돈다. 결과는 results/<날짜>/<시각>_<이름>/에 새로 쓴다.
"""

import argparse
import json
import platform
import statistics
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blender_tutor import engine_setup, manual_vectors
from blender_tutor.answer_engine import CLOSED_QUERY, AnswerEngine, Done, Failure, Piece, Settings, closed_query
from blender_tutor.answer_model import COPIES, MODEL, PRICE, FirstOf, OpenAIAnswerModel
from blender_tutor.beginner_scope import OpenAIModel, openai_key
from blender_tutor.manual_chunks import load_chunks
from blender_tutor.paths import PROJECT
from blender_tutor.search_compare import hit
from blender_tutor.translate import pieces
from blender_tutor.work_state import WorkState

QUESTIONS = (PROJECT / "data" / "search_compare" / "questions" / "web_questions.jsonl",
             PROJECT / "data" / "search_compare" / "questions" / "ai_questions.jsonl")
STATE = PROJECT / "data" / "eval" / "speed" / "state_cube.json"  # [131] 엔진 실측과 같은 기본 큐브
BEFORE_HIT = 0.853  # [127] 긴 지시 + 3번 동시 + 먼저 온 1개, 상위 8개 찾은 비율
# 어림(달러, [127]·[131] 실측): 질문 바꾸기 호출 하나 약 $0.00008, 답변 호출 하나 약 $0.0003(none)
GUESS_REWRITE, GUESS_ANSWER = 0.00008, 0.0003
IDLE_WAIT = 60.0  # 다음 질문 전에 뒤에서 도는 호출이 모두 끝나기를 기다리는 한도(초)


@dataclass(frozen=True)
class Question:
    id: str
    text: str
    groups: tuple[tuple[str, ...], ...]  # 필요한 근거마다 대신할 수 있는 청크 열쇠들


def load_questions(paths: Sequence[Path]) -> list[Question]:
    """search_compare 질문 파일들에서 빼기로 하지 않은 질문(정답 열쇠 포함)."""
    rows = [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [Question(row["id"], row["question"], tuple(tuple(g["any_of"]) for g in row["answer_groups"]))
            for row in rows if not row.get("dropped")]


class Calls:
    """질문 하나 동안의 호출 기록. 시각은 start()부터 잰 초. 뒤에서 도는 호출이 모두 끝나기를 기다릴 수 있다."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter):
        self.clock = clock
        self.records: list[dict] = []
        self._open = 0
        self._idle = threading.Condition()
        self._start = clock()

    def start(self) -> None:
        self.records, self._start = [], self.clock()

    def now(self) -> float:
        return round(self.clock() - self._start, 4)

    def begin(self, kind: str, slot: int) -> dict:
        record = {"종류": kind, "몇째": slot, "보냄": self.now()}
        with self._idle:
            self._open += 1
            self.records.append(record)
        return record

    def end(self, record: dict) -> None:
        record["끝"] = self.now()
        with self._idle:
            self._open -= 1
            self._idle.notify_all()

    def wait_idle(self, timeout: float = IDLE_WAIT) -> None:
        with self._idle:
            if not self._idle.wait_for(lambda: self._open == 0, timeout):
                raise RuntimeError(f"{timeout}초가 지나도 끝나지 않은 호출이 있음(다음 질문의 토큰 셈이 섞이지 않게 멈춤)")


def _tokens(model: OpenAIModel | OpenAIAnswerModel) -> tuple[int, int, int]:
    return model.input_tokens, model.output_tokens, model.reasoning_tokens


def _close(calls: Calls, record: dict, inner, before: tuple[int, int, int], text: str) -> None:
    record["입력"], record["출력"], record["생각"] = (after - was for after, was in zip(_tokens(inner), before))
    record["글"] = text
    calls.end(record)


class TimedRewriter:
    """질문 바꾸기 모델을 감싸 호출마다 보냄·첫 조각·검색어 닫힘·끝 시각, 토큰, 받은 글을 남긴다."""

    def __init__(self, inner: OpenAIModel, calls: Calls, slot: int):
        self.inner, self.calls, self.slot = inner, calls, slot

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        record, before, text = self.calls.begin("질문 바꾸기", self.slot), _tokens(self.inner), ""
        try:
            for piece in self.inner.stream(messages):
                record.setdefault("첫 조각", self.calls.now())
                text += piece
                if "검색어 닫힘" not in record and "빈 검색어" not in record and (match := CLOSED_QUERY.search(text)):
                    # 엔진(closed_query)처럼 빈 검색어는 쓸 수 없는 답으로 둔다
                    record["검색어 닫힘" if json.loads(match.group(1)).strip() else "빈 검색어"] = self.calls.now()
                yield piece
        except Exception as error:
            record["오류"] = repr(error)
            raise
        finally:
            _close(self.calls, record, self.inner, before, text)


class TimedAnswer:
    """답변 모델을 감싸 호출마다 보냄·첫 조각·끝 시각, 토큰, 답 글자 수를 남긴다(FirstOf에 끼운다)."""

    def __init__(self, inner: OpenAIAnswerModel, calls: Calls, slot: int):
        self.inner, self.calls, self.slot, self.model = inner, calls, slot, inner.model

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterator[str]:
        record, before, text = self.calls.begin("답변", self.slot), _tokens(self.inner), ""
        try:
            for piece in self.inner.stream(messages, timeout):
                record.setdefault("첫 조각", self.calls.now())
                text += piece
                yield piece
        except Exception as error:
            record["오류"] = repr(error)
            raise
        finally:
            _close(self.calls, record, self.inner, before, text)

    def dollars(self) -> float:
        return self.inner.dollars()


def run(engine: AnswerEngine, questions: Sequence[Question], state: WorkState, calls: Calls, keys: dict, rounds: int,
        keep: Callable[[dict], None] = lambda row: None) -> list[dict]:
    """질문마다 엔진을 한 번 돌리고, 뒤에서 도는 호출이 모두 끝난 뒤 기록을 한 줄로 묶는다.
    keep은 줄이 생길 때마다 불린다(도중에 멈춰도 돈을 쓴 호출의 기록이 남게 바로 파일에 쓴다)."""
    rows = []
    for round_number in range(1, rounds + 1):
        for question in questions:
            calls.start()
            first = done = None
            results, failure = [], None
            for event in engine.answer(question.text, state, []):
                if isinstance(event, Piece) and first is None:
                    first = calls.now()
                elif isinstance(event, Done):
                    done, results = calls.now(), [keys[chunk] for chunk in event.results]
                elif isinstance(event, Failure):
                    failure = event.message
            calls.wait_idle()
            rows.append({
                "회차": round_number, "질문": question.id, "첫 글자": first, "답 끝": done, "실패": failure,
                "결과": results, "적중": hit(question.groups, results, engine.settings.top_k).ratio if results else None,
                "호출": calls.records,
            })
            keep(rows[-1])
            print(f"{round_number}회차 {question.id}: 첫 글자 {first}초", file=sys.stderr)
    return rows


def score_queries(rows: list[dict], questions: Sequence[Question], engine: AnswerEngine, embed: Callable, keys: dict) -> None:
    """모든 질문 바꾸기 호출의 검색어를 같은 검색으로 채점해 호출 기록에 "검색어"·"적중"을 붙인다(쓰지 않은 것도)."""
    groups = {question.id: question.groups for question in questions}
    found = [(row, record, closed_query(record["글"])) for row in rows for record in row["호출"]
             if record["종류"] == "질문 바꾸기" and "검색어 닫힘" in record]
    texts = list(dict.fromkeys(query for _, _, query in found))
    vectors = dict(zip(texts, embed(texts)))
    for row, record, query in found:
        ranked = [keys[chunk] for chunk in engine.search(query, vectors[query])]
        record["검색어"], record["적중"] = query, hit(groups[row["질문"]], ranked, engine.settings.top_k).ratio


def summarize(rows: Sequence[dict]) -> dict:
    """기록에서 방법별 단축(질문마다 계산한 값의 중앙값)·단계별 시간·적중·칸 순서를 계산한다. 실패한 줄은 뺀다."""
    gains = {"방법 1 흘려 받기": [], "방법 2 3→5개": [], "방법 3 답변 2개": []}
    stages = {"검색어 닫힘(5개 중 먼저)": [], "임베딩+검색": [], "답변 첫 조각(빠른 쪽)": [], "첫 글자(잰 것)": [],
              "첫 글자(옛 방식 어림)": [], "답 끝": []}
    hits = {"쓴 검색어(5개 중 먼저 닫힘)": [], "앞 3개 중 먼저 닫힘": [], "옛 방식(앞 3개 중 먼저 끝남)": []}
    query_first, reasoning = [], 0
    fixed = {"질문 바꾸기": [], "답변": []}  # 호출 하나의 보냄 → 첫 조각(조사 문서의 "고정 몫 약 0.8초")
    for row in rows:
        if row["실패"] or row["첫 글자"] is None:
            continue
        rewrites = sorted((r for r in row["호출"] if r["종류"] == "질문 바꾸기"), key=lambda r: r["몇째"])
        answers = sorted((r for r in row["호출"] if r["종류"] == "답변"), key=lambda r: r["몇째"])
        usable = [r for r in rewrites if "검색어 닫힘" in r]
        used = min(usable, key=lambda r: r["검색어 닫힘"])
        front = [r for r in usable if r["몇째"] < 3]
        front_closed = min(front, key=lambda r: r["검색어 닫힘"]) if front else None
        front_ended = min(front, key=lambda r: r["끝"]) if front else None
        waits = [r["첫 조각"] - r["보냄"] for r in answers if "첫 조각" in r]
        sent = min(r["보냄"] for r in answers)
        gains["방법 1 흘려 받기"].append(min(r["끝"] for r in usable) - used["검색어 닫힘"])
        if front_closed:
            gains["방법 2 3→5개"].append(front_closed["검색어 닫힘"] - used["검색어 닫힘"])
        hedge = answers[0]["첫 조각"] - answers[0]["보냄"] - min(waits) if "첫 조각" in answers[0] else None
        if hedge is not None:
            gains["방법 3 답변 2개"].append(hedge)
        stages["검색어 닫힘(5개 중 먼저)"].append(used["검색어 닫힘"])
        stages["임베딩+검색"].append(sent - used["검색어 닫힘"])
        stages["답변 첫 조각(빠른 쪽)"].append(row["첫 글자"] - sent)
        stages["첫 글자(잰 것)"].append(row["첫 글자"])
        if front_ended and hedge is not None:  # 첫째 답변이 실패했으면 1개만 쓸 때를 알 수 없어 뺀다
            stages["첫 글자(옛 방식 어림)"].append(row["첫 글자"] + front_ended["끝"] - used["검색어 닫힘"] + hedge)
        stages["답 끝"].append(row["답 끝"])
        for name, record in (("쓴 검색어(5개 중 먼저 닫힘)", used), ("앞 3개 중 먼저 닫힘", front_closed),
                             ("옛 방식(앞 3개 중 먼저 끝남)", front_ended)):
            if record and "적중" in record:
                hits[name].append(record["적중"])
        for record in rewrites:
            if record["글"].lstrip().startswith("{"):
                query_first.append(record["글"].lstrip().lstrip("{").lstrip().startswith('"query"'))
        reasoning += sum(record.get("생각", 0) for record in row["호출"])
        for record in row["호출"]:
            if "첫 조각" in record:
                fixed[record["종류"]].append(record["첫 조각"] - record["보냄"])
    return {
        "단축(초, 중앙값)": {name: _median(values) for name, values in gains.items()},
        "단축(초, 평균)": {name: round(statistics.mean(values), 4) if values else None for name, values in gains.items()},
        "단계(초, 중앙값·최대값)": {name: (_median(values), max(values) if values else None) for name, values in stages.items()},
        "적중(찾은 비율 평균)": {name: round(statistics.mean(values), 4) if values else None for name, values in hits.items()},
        "적중 견줄 값([127])": BEFORE_HIT,
        "호출 하나 보냄→첫 조각(초, 중앙값·최소값)": {kind: (_median(v), min(v) if v else None) for kind, v in fixed.items()},
        "query가 첫 칸인 비율": round(sum(query_first) / len(query_first), 4) if query_first else None,
        "생각 토큰 합": reasoning,
        "질문 수(실패 뺌)": len(stages["첫 글자(잰 것)"]),
    }


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def estimate(questions: int, rounds: int) -> str:
    turns = questions * rounds
    dollars = turns * (engine_setup.REWRITE_COUNT * GUESS_REWRITE + COPIES * GUESS_ANSWER)
    return (f"질문 {questions}개 × {rounds}회차 = {turns}번, 질문 바꾸기 {engine_setup.REWRITE_COUNT}개 + 답변 {COPIES}개씩 "
            f"→ 약 ${dollars:.3f}(어림, 임베딩은 아주 적음)")


def _markdown(name: str, about: dict, summary: dict) -> str:
    lines = [f"# {name}", "", f"- 엔진 {about['엔진']}, {about['pc']}, 시작 {about['시작 시각']}, 실제 비용 ${about['실제 비용(달러)']['합']}",
             f"- 질문 {about['질문 수']}개 × {about['회차']}회차, 실패 뺀 {summary['질문 수(실패 뺌)']}번", "",
             "## 방법별 단축(초)", "", "| 방법 | 중앙값 | 평균 |", "|---|---|---|"]
    lines += [f"| {k} | {v} | {summary['단축(초, 평균)'][k]} |" for k, v in summary["단축(초, 중앙값)"].items()]
    lines += ["", "## 단계(초)", "", "| 단계 | 중앙값 | 최대값 |", "|---|---|---|"]
    lines += [f"| {k} | {m} | {x} |" for k, (m, x) in summary["단계(초, 중앙값·최대값)"].items()]
    lines += ["", "## 적중(상위 8개, 찾은 비율 평균)", "", f"견줄 값 [127]: {BEFORE_HIT}", ""]
    lines += [f"- {k}: {v}" for k, v in summary["적중(찾은 비율 평균)"].items()]
    lines += [f"- 호출 하나 보냄→첫 조각(중앙값·최소값) {k}: {v}" for k, v in summary["호출 하나 보냄→첫 조각(초, 중앙값·최소값)"].items()]
    lines += ["", f"- query가 첫 칸인 비율: {summary['query가 첫 칸인 비율']}", f"- 생각 토큰 합: {summary['생각 토큰 합']}"]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="결과 폴더 이름(results/<날짜>/<시각>_<이름>)")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--yes", action="store_true", help="어림 비용을 확인했으니 실제로 돈다")
    parser.add_argument("--data", type=Path, default=PROJECT / "data")
    parser.add_argument("--results", type=Path, default=PROJECT / "results")
    args = parser.parse_args(argv)
    questions = load_questions(QUESTIONS)
    guess = estimate(len(questions), args.rounds)
    if not args.yes:
        print(f"{guess}. 확인받은 뒤 --yes를 붙여 다시 돌리세요.", file=sys.stderr)
        return 2
    now = datetime.now()
    folder = args.results / now.strftime("%Y%m%d") / f"{now.strftime('%H%M%S')}_{args.name}"
    if folder.exists():
        raise SystemExit(f"{folder}가 이미 있습니다(덮어쓰지 않음).")
    settings, key, calls = Settings(), openai_key(), Calls()
    inner_rewriters = engine_setup.rewriters_for(settings, key)
    inner_answers = [OpenAIAnswerModel(MODEL, key, settings.reasoning.value) for _ in range(COPIES)]
    engine = engine_setup.build_engine(
        args.data, model=FirstOf([TimedAnswer(model, calls, slot) for slot, model in enumerate(inner_answers)]),
        settings=settings, rewriters=[TimedRewriter(model, calls, slot) for slot, model in enumerate(inner_rewriters)],
    )
    keys = {piece.chunk: piece.key for piece in pieces(load_chunks(args.data / "chunks" / "manual_chunks.jsonl"))}
    state = WorkState.from_json(json.loads(STATE.read_text(encoding="utf-8")))
    folder.mkdir(parents=True)
    with (folder / "실행.jsonl").open("w", encoding="utf-8") as file:
        def keep(row: dict) -> None:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
            file.flush()

        rows = run(engine, questions, state, calls, keys, args.rounds, keep)
    scorer = manual_vectors.OpenAIEmbedder(manual_vectors.MODEL, key)
    score_queries(rows, questions, engine, lambda texts: scorer.embed(texts, 30.0), keys)
    rewrite_in = sum(model.input_tokens for model in inner_rewriters)
    rewrite_out = sum(model.output_tokens for model in inner_rewriters)
    price_in, price_out = PRICE[MODEL]
    paid = {
        "질문 바꾸기": round((rewrite_in * price_in + rewrite_out * price_out) / 1_000_000, 6),
        "답변": round(sum(model.dollars() for model in inner_answers), 6),
        # 엔진 안 임베딩기의 토큰 수는 실측에서만 들여다본다(엔진이 바깥에 내놓지 않음)
        "임베딩(엔진)": round(engine._embedder.tokens * manual_vectors.PRICE_PER_MILLION[manual_vectors.MODEL] / 1_000_000, 6),
        "임베딩(채점)": round(scorer.tokens * manual_vectors.PRICE_PER_MILLION[manual_vectors.MODEL] / 1_000_000, 6),
    }
    paid["합"] = round(sum(paid.values()), 6)
    paid["질문당(채점 뺌)"] = round((paid["합"] - paid["임베딩(채점)"]) / len(rows), 6)
    summary = summarize(rows)
    about = {"엔진": engine.name, "질문 수": len(questions), "회차": args.rounds, "어림": guess, "실제 비용(달러)": paid,
             "pc": platform.node(), "시작 시각": now.isoformat(timespec="seconds"), "요약": summary}
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "채점.jsonl").open("w", encoding="utf-8") as file:  # 실행.jsonl 줄 + 검색어마다 채점
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    (folder / "요약.md").write_text(_markdown(args.name, about, summary), encoding="utf-8")
    print(f"결과: {folder}\n실제 비용: {paid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
