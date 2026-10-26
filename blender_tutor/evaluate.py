"""평가 프로그램(명세 "평가", User Stories 67·69-72, 티켓 29).

- run: 문항 파일을 Blender 없이 답 엔진에 바로 넣어 답·검색 결과를 모으고, 정답 위치가 검색 결과에 들었는지(검색 적중) 센다.
- times: 도우미 창의 시간 기록(timing.py)에서 문항 질문과 맞는 줄을 찾아 중앙값·최대값을 낸다.
결과는 results/<날짜>_<이름>/에 새로 쓰고, 그 폴더가 이미 있으면 덮어쓰지 않고 멈춘다.

문항 파일은 목록 하나(JSON)이고, 한 항목이 대화 하나다. 보통 문항은 차례가 하나인 대화이고, 시나리오형은 '차례' 목록을
가진다. 시나리오형은 이전 프로젝트(rag_korea_history)처럼 한 대화를 앞에서부터 실제로 이어 물으며, 핵심이 있는 차례마다
문항 하나로 센다(2026-10-26 사용자 결정). 지어낸 예:

    [{"번호": "D01", "분류": "연습 과정 단계", "질문": "칼끝은 어떻게 모아요?", "작업 상태": "states/D01.json",
      "스크린샷": "states/D01.png", "연습 과정": "sword", "단계": "blade-tip",
      "핵심": ["점 두 개를 골라 합친다"], "정답 위치": ["modeling/meshes/editing/vertex/merge_vertices.html#..."]},
     {"번호": "S1", "분류": "시나리오형", "연습 과정": "sword",
      "차례": [{"번호": "S1-1", "질문": "...", "작업 상태": "...", "단계": "blade-stretch", "핵심": [...], "정답 위치": [...]}]}]
"""

import argparse
import dataclasses
import json
import platform
import statistics
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from blender_tutor import stand_in
from blender_tutor.answer_engine import AnswerEngine, Done, Failure, Piece, Reasoning, Settings, Source
from blender_tutor.conversation import RECENT_PAIRS, Conversation
from blender_tutor.manual_chunks import BASE_URL, Chunk
from blender_tutor.paths import COURSES, PROJECT, default_progress_records
from blender_tutor.progress import Course, Step, load_courses
from blender_tutor.work_state import WorkState

# 지금 고를 수 있는 임베딩 종류·리랭커. 리랭커와 bge-m3 같은 다른 임베딩은 아직 없어서, 켠 척하지 않게 고를 수 없게 막는다.
# 생기는 티켓(임베딩은 31, 리랭커는 개발 평가에서 켜 보기로 할 때)에서 값을 더하고 엔진에 실제로 넘긴다
EMBEDDINGS = (stand_in.NAME,)
RERANKERS = ("끔",)

# 칸 이름 → 꼭 있어야 하나. 연습 과정 밖 질문이면 연습 과정·단계를 빼거나 null로 둔다
_TURN = {"번호": True, "질문": True, "작업 상태": True, "스크린샷": False, "단계": False, "핵심": True, "정답 위치": True}
_SINGLE = {**_TURN, "분류": True, "연습 과정": False}
_SCENARIO = {"번호": True, "분류": True, "연습 과정": False, "차례": True}


@dataclass(frozen=True)
class Turn:
    """대화의 차례 하나: 묻는 질문과 그때의 작업 상태·단계, 채점에 쓸 핵심과 정답 위치."""

    number: str
    question: str
    state: WorkState
    step: Step | None  # 연습 과정 밖이면 None
    keys: tuple[str, ...]  # 맞는 답의 핵심(비면 묻기만 하고 세지 않는 차례)
    locations: tuple[str, ...]  # 정답 위치(경로.html#앵커 또는 쪽 전체 경로.html). 문서에 없는 질문이면 빈 묶음

    @property
    def scored(self) -> bool:
        """채점하는 차례인가(핵심이 있으면 문항 하나로 센다)."""
        return bool(self.keys)


@dataclass(frozen=True)
class Dialogue:
    """대화 하나. 평가 프로그램은 대화마다 새로 시작한다(GPT 쪽 조건 '문항마다 새 대화'와 같음)."""

    number: str
    kind: str  # 작은 분류(오답 분석용)
    turns: tuple[Turn, ...]


@dataclass(frozen=True)
class TurnResult:
    """차례 하나를 물은 결과."""

    dialogue: Dialogue
    turn: Turn
    answer: str  # 나온 답 글(실패했으면 실패 전까지 나온 것)
    failure: str | None  # 오류·시간 초과 표시 문구. 끝까지 나왔으면 None
    sources: tuple[Source, ...]  # 근거 목록(실패하면 없음)
    results: tuple[Chunk, ...]  # 검색 결과(순위대로, 먼저 볼 소제목 뺌)
    hit: int | None  # 정답 위치가 검색 결과 몇 위에 처음 들었나(1부터). 못 찾았거나 정답 위치가 없으면 None


def run(dialogues: Sequence[Dialogue], engine: AnswerEngine, recent_pairs: int = RECENT_PAIRS) -> list[TurnResult]:
    """대화마다 새 대화로 시작해 차례를 앞에서부터 엔진에 묻는다. 앞 차례의 답은 엔진이 실제로 낸 것을 최근 대화로 넘기고,
    도우미 창처럼 끝까지 나온 답만 넣는다(conversation.Conversation을 그대로 씀). recent_pairs는 최근 대화 쌍 수(User Story 72)."""
    found = []
    for dialogue in dialogues:
        conversation = Conversation(keep=recent_pairs)
        conversation.engine = engine
        for turn in dialogue.turns:
            pieces, failure, sources, results = [], None, (), ()
            for event in conversation.ask(turn.question, turn.state, turn.step):
                if isinstance(event, Piece):
                    pieces.append(event.text)
                elif isinstance(event, Done):
                    sources, results = event.sources, event.results
                elif isinstance(event, Failure):
                    failure, results = event.message, event.results
            found.append(TurnResult(dialogue, turn, "".join(pieces), failure, sources, results, hit(turn.locations, results)))
    return found


def hit(locations: Sequence[str], results: Sequence[Chunk]) -> int | None:
    """정답 위치 중 하나가 검색 결과 몇 위에 처음 들었나(1부터). 경로.html#앵커는 그 소제목(나눈 조각 모두),
    앵커 없는 경로.html은 그 쪽의 어느 소제목이든 맞은 것으로 본다."""
    for rank, chunk in enumerate(results, start=1):
        if any(location in (chunk.address, f"{chunk.page_path}.html") for location in locations):
            return rank
    return None


# 시간 기록 한 줄에서 재는 것: 이름 → (시작 칸, 끝 칸). 목표는 질문 준비 0.5초, 첫 글자 2초, 답 끝 6초(명세 "속도 목표").
# F10 → 답 끝은 "이겼다" 기준(질문 준비 포함 답 끝까지가 GPT의 절반 이하)에 쓴다
MEASURES = {
    "질문 준비(F10 → 입력 가능)": ("f10_pressed", "ready"),
    "첫 글자(보냄 → 첫 글자)": ("sent", "first_piece"),
    "답 끝(보냄 → 답 끝)": ("sent", "done"),
    "F10 → 답 끝": ("f10_pressed", "done"),
}


@dataclass(frozen=True)
class Spread:
    """초 단위 중앙값·최대값과 분모(센 줄 수). 센 줄이 없으면 둘 다 None."""

    count: int
    median: float | None
    max: float | None


@dataclass(frozen=True)
class TimingGroup:
    """엔진 이름과 설정이 같은 줄 묶음 하나의 통계."""

    engine: str
    settings: dict
    numbers: tuple[str, ...]  # 센 문항(차례) 번호, 문항 파일 차례
    failures: tuple[str, ...]  # 마지막 줄이 실패로 끝나 통계에서 뺀 번호
    spreads: dict[str, Spread]  # MEASURES 이름 → 통계


@dataclass(frozen=True)
class TimingSummary:
    groups: tuple[TimingGroup, ...]  # 처음 나온 차례
    unmatched: int  # 어느 문항과도 맞지 않은 줄 수(평가 밖에서 물은 질문)
    not_ready: int  # 문항과 맞지만 엔진 준비 전에 물어 엔진·설정이 없는 줄 수


def timing_summary(lines: Iterable[dict], dialogues: Sequence[Dialogue]) -> TimingSummary:
    """시간 기록 줄(timing.py가 쓴 것)을 문항과 맞춰 엔진·설정 묶음마다 통계를 낸다(티켓 28에서 넘긴 규칙, 2026-10-26 사용자 결정).

    - 질문 글은 앞뒤 공백을 지우고 안쪽 공백·줄바꿈을 한 칸으로 줄여 견준다(붙여 넣을 때 붙은 공백).
    - 같은 문항을 여러 번 물었으면 그 묶음의 마지막 줄을 쓴다. 그 줄이 실패로 끝났으면 통계에서 빼고 failures에 적는다.
    - F10 칸이 비어 있는 줄(창이 떠 있는 채 이어 물음 등)은 F10이 드는 통계에서만 빠진다. 그래서 통계마다 분모가 다를 수 있다.
    질문 글이 같은 문항이 둘 있으면 어느 문항의 줄인지 가를 수 없어 ValueError.
    """
    numbers: dict[str, str] = {}  # 견줄 질문 글 → 차례 번호
    for dialogue in dialogues:
        for turn in dialogue.turns:
            key = _plain(turn.question)
            if key in numbers:
                raise ValueError(f"{numbers[key]}, {turn.number}: 질문 글이 같아 시간 기록 줄을 가를 수 없음")
            numbers[key] = turn.number
    last: dict[str, dict[str, dict]] = {}  # 묶음 열쇠 → 차례 번호 → 마지막 줄
    unmatched = not_ready = 0
    for record in lines:
        number = numbers.get(_plain(record["question"]))
        if number is None:
            unmatched += 1
        elif record["engine"] is None:
            not_ready += 1
        else:
            key = json.dumps([record["engine"], record["settings"]], sort_keys=True, ensure_ascii=False)
            last.setdefault(key, {})[number] = record
    order = list(numbers.values())
    groups = []
    for found in last.values():
        counted = sorted(found, key=order.index)
        kept = [number for number in counted if found[number]["outcome"] != "failure"]
        spreads = {
            name: _spread([found[number][end] - found[number][start] for number in kept
                           if found[number][start] is not None and found[number][end] is not None])
            for name, (start, end) in MEASURES.items()
        }
        sample = found[counted[0]]
        failures = tuple(number for number in counted if number not in kept)
        groups.append(TimingGroup(sample["engine"], sample["settings"], tuple(kept), failures, spreads))
    return TimingSummary(tuple(groups), unmatched, not_ready)


def _plain(text: str) -> str:
    return " ".join(text.split())


def _spread(seconds: list[float]) -> Spread:
    if not seconds:
        return Spread(0, None, None)
    return Spread(len(seconds), statistics.median(seconds), max(seconds))


def load_questions(path: Path, courses: Sequence[Course]) -> list[Dialogue]:
    """문항 파일을 읽는다. 작업 상태 경로는 문항 파일이 있는 폴더 기준이다.

    칸 이름이 틀렸거나, 없는 연습 과정·단계를 가리키거나, 번호가 겹치면 그 번호와 함께 ValueError.
    """
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError(f"{path}: 문항 파일은 목록이어야 함")
    steps = {(course.label, step.label): step for course in courses for step in course.steps}
    dialogues, seen = [], set()
    for item in items:
        scenario = isinstance(item, dict) and "차례" in item
        _check_fields(item, _SCENARIO if scenario else _SINGLE)
        if scenario:
            if not isinstance(item["차례"], list) or not item["차례"]:
                raise ValueError(f"{item['번호']}: 차례는 비지 않은 목록이어야 함")
            for turn in item["차례"]:
                _check_fields(turn, _TURN)
        course = item.get("연습 과정")
        turns = tuple(_turn(turn, course, steps, path.parent) for turn in (item["차례"] if scenario else [item]))
        for number in dict.fromkeys((item["번호"], *(turn.number for turn in turns))):
            if number in seen:
                raise ValueError(f"{number}: 번호가 겹침")
            seen.add(number)
        dialogues.append(Dialogue(item["번호"], item["분류"], turns))
    return dialogues


def _turn(data: dict, course: str | None, steps: dict[tuple[str, str], Step], folder: Path) -> Turn:
    """칸 이름 검사를 마친 차례 하나를 읽는다. course는 대화의 연습 과정 이름표(밖이면 None)."""
    number, label = data["번호"], data.get("단계")
    if (course is None) != (label is None):
        raise ValueError(f"{number}: 연습 과정과 단계는 함께 적거나 함께 비움")
    if course is not None and (course, label) not in steps:
        raise ValueError(f"{number}: 연습 과정 {course}에 단계 {label}가 없음")
    for key in ("핵심", "정답 위치"):
        if not isinstance(data[key], list) or not all(isinstance(text, str) for text in data[key]):
            raise ValueError(f"{number}: {key}는 글 목록이어야 함")
    locations = tuple(location.removeprefix(BASE_URL) for location in data["정답 위치"])
    for location in locations:
        if not location.split("#")[0].endswith(".html"):
            raise ValueError(f"{number}: 정답 위치 {location}는 경로.html 또는 경로.html#앵커 꼴이어야 함")
    state_path = folder / data["작업 상태"]
    try:
        state = WorkState.from_json(json.loads(state_path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise ValueError(f"{number}: 작업 상태 {data['작업 상태']}를 읽지 못함({error})") from error
    step = steps[(course, label)] if course is not None else None
    return Turn(number, data["질문"], state, step, tuple(data["핵심"]), locations)


def _check_fields(data: object, fields: dict[str, bool]) -> None:
    """칸 이름이 정해 둔 것뿐이고 꼭 있어야 할 칸이 다 있나."""
    number = data.get("번호", "?") if isinstance(data, dict) else "?"
    if not isinstance(data, dict):
        raise ValueError(f"{number}: 문항은 사전이어야 함")
    if unknown := [key for key in data if key not in fields]:
        raise ValueError(f"{number}: 모르는 칸 {unknown}")
    if missing := [key for key, required in fields.items() if required and key not in data]:
        raise ValueError(f"{number}: 빠진 칸 {missing}")


def main(argv: Sequence[str] | None = None, today: date | None = None) -> int:
    """명령 줄 입구. 돌려주는 값은 종료 코드(0 성공, 1 결과 폴더가 이미 있음)."""
    parser = argparse.ArgumentParser(description="평가 문항을 답 엔진에 넣어 답·검색 적중을 모으거나(run), 시간 기록 통계를 냅니다(times).")
    commands = parser.add_subparsers(dest="command", required=True)
    run_command = commands.add_parser("run", help="문항을 답 엔진에 넣어 답·검색 결과·검색 적중을 모은다")
    times_command = commands.add_parser("times", help="도우미 창의 시간 기록에서 중앙값·최대값을 낸다")
    for command in (run_command, times_command):
        command.add_argument("questions", type=Path, help="문항 파일(JSON 목록)")
        command.add_argument("--name", required=True, help="결과 폴더 이름(results/<날짜>_<이름>)")
        command.add_argument("--results", type=Path, default=PROJECT / "results", help="결과를 쓸 폴더")
        command.add_argument("--courses", type=Path, default=COURSES, help="연습 과정 폴더")
    defaults = Settings()
    run_command.add_argument("--data", type=Path, default=PROJECT / "data", help="청크·메뉴 이름 사전이 있는 폴더")
    run_command.add_argument("--reasoning", choices=[level.value for level in Reasoning], default=defaults.reasoning.value, help="생각 수준")
    run_command.add_argument("--recent", type=int, default=RECENT_PAIRS, help="최근 대화 쌍 수")
    run_command.add_argument("--top-k", type=int, default=defaults.top_k, help="답변 모델에 넘길 검색 결과 수")
    run_command.add_argument("--no-bm25", action="store_true", help="낱말 검색(BM25)을 끄고 뜻 검색만")
    run_command.add_argument("--embedding", choices=EMBEDDINGS, default=EMBEDDINGS[0], help="임베딩 종류")
    run_command.add_argument("--reranker", choices=RERANKERS, default=RERANKERS[0], help="리랭커")
    times_command.add_argument("--timings", type=Path, help="도우미 창의 시간 기록 파일(기본: 설정 폴더의 timings.jsonl)")
    args = parser.parse_args(argv)

    courses = load_courses(args.courses)
    dialogues = load_questions(args.questions, courses)
    folder = args.results / f"{today or date.today():%Y%m%d}_{args.name}"
    try:
        folder.mkdir(parents=True)
    except FileExistsError:
        print(f"{folder}가 이미 있어 멈춥니다(결과는 덮어쓰지 않음). 다른 --name을 주세요.", file=sys.stderr)
        return 1
    if args.command == "run":
        settings = Settings(top_k=args.top_k, use_bm25=not args.no_bm25, reasoning=args.reasoning)
        # 평가에서는 가짜 답의 쉼(창 동작 확인용)이 필요 없어 0으로 둔다
        engine = stand_in.build_engine(args.data, stand_in.StandInModel(0, 0), courses=courses, settings=settings)
        _write_run(folder, args, settings, run(dialogues, engine, args.recent))
    else:
        timings = args.timings or default_progress_records().parent / "timings.jsonl"
        lines = [json.loads(text) for text in timings.read_text(encoding="utf-8").splitlines() if text.strip()]
        _write_times(folder, args.name, timings, args.questions, timing_summary(lines, dialogues))
    print(f"결과: {folder}")
    return 0


def _write_run(folder: Path, args: argparse.Namespace, settings: Settings, found: list[TurnResult]) -> None:
    """설정.json(무엇으로 돌렸나), 답.jsonl(차례마다 한 줄), 요약.md(검색 적중)를 쓴다.

    설정.json의 settings 칸은 시간 기록 줄의 settings와 같은 모양이라 두 결과를 맞대 볼 수 있다.
    """
    about = {
        "문항 파일": str(args.questions), "engine": stand_in.NAME, "임베딩": args.embedding, "리랭커": args.reranker,
        "settings": {**dataclasses.asdict(settings), "recent_pairs": args.recent},
        "pc": platform.node(), "시각": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "답.jsonl").open("w", encoding="utf-8") as file:
        for result in found:
            row = {
                "대화": result.dialogue.number, "번호": result.turn.number, "분류": result.dialogue.kind,
                "채점": result.turn.scored, "질문": result.turn.question, "답": result.answer, "실패": result.failure,
                "근거": [source.url for source in result.sources],
                "검색 결과": [
                    {"순위": rank, "주소": chunk.address, "경로": chunk.path} for rank, chunk in enumerate(result.results, start=1)
                ],
                "정답 위치": list(result.turn.locations), "적중 순위": result.hit, "핵심": list(result.turn.keys),
            }
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    scored = [result for result in found if result.turn.scored]
    counted = [result for result in scored if result.turn.locations]
    lines = [
        f"# 평가 결과: {args.name}", "",
        f"- 설정: `{json.dumps(about['settings'], ensure_ascii=False)}`, 엔진 {about['engine']}, 임베딩 {args.embedding}, 리랭커 {args.reranker}",
        f"- 검색 적중: {sum(result.hit is not None for result in counted)} / {len(counted)}"
        " (분모: 핵심과 정답 위치가 있는 차례, 채점자: 프로그램)",
        f"- 채점하는 차례 {len(scored)}개 중 답이 실패로 끝난 차례 {sum(result.failure is not None for result in scored)}개",
        "", "| 번호 | 분류 | 적중 순위 | 실패 |", "|---|---|---|---|",
    ]
    for result in scored:
        rank = "-" if not result.turn.locations else (result.hit or "못 찾음")
        lines.append(f"| {result.turn.number} | {result.dialogue.kind} | {rank} | {result.failure or ''} |")
    (folder / "요약.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_times(folder: Path, name: str, timings: Path, questions: Path, summary: TimingSummary) -> None:
    """시간.md: 엔진·설정 묶음마다 통계 표(초)."""
    lines = [
        f"# 시간 통계: {name}", "",
        f"- 시간 기록 파일: `{timings}`, 문항 파일: `{questions}`",
        f"- 세지 않은 줄: 문항에 없는 질문 {summary.unmatched}개, 엔진 준비 전에 물은 것 {summary.not_ready}개",
        "- 같은 문항을 여러 번 물었으면 마지막 줄을 쓰고, 실패로 끝난 줄은 뺀다. 목표(중앙값): 질문 준비 0.5초, 첫 글자 2초, 답 끝 6초",
    ]
    for group in summary.groups:
        lines += [
            "", f"## {group.engine} · `{json.dumps(group.settings, ensure_ascii=False)}`", "",
            f"- 센 문항: {', '.join(group.numbers) or '없음'}",
            f"- 실패로 뺀 문항: {', '.join(group.failures) or '없음'}",
            "", "| 잰 것 | 분모 | 중앙값(초) | 최대값(초) |", "|---|---|---|---|",
        ]
        for measure, spread in group.spreads.items():
            median = "-" if spread.median is None else f"{spread.median:.2f}"
            longest = "-" if spread.max is None else f"{spread.max:.2f}"
            lines.append(f"| {measure} | {spread.count} | {median} | {longest} |")
    (folder / "시간.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
