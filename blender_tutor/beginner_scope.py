"""초보자 범위 분류(명세 "자료 준비"의 초보자 범위, User Stories 62·65, 티켓 30).

단위는 쪽이다. 연습 과정 단계가 가리키는 쪽과 시작하기(getting_started) 쪽은 바로 넣고, 나머지는 모델이
"처음 쓰는 사람이 간단한 아이템 하나를 만들고 내보내며 마주칠 가능성"으로 판단해 쪽마다 이유 한 줄을 남긴다.
모델에게는 쪽 전문이 아니라 주소·쪽 제목·첫 소제목 이름·첫머리 40단어만 보인다(2026-10-26 사용자 결정, 비용 때문).
"""

import argparse
import json
import os
import sys
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from blender_tutor.manual_chunks import Chunk, load_chunks
from blender_tutor.paths import COURSES, PROJECT
from blender_tutor.progress import Course, load_courses

DATA = PROJECT / "data"
OUT = DATA / "beginner_scope"  # 결과 폴더(커밋 안 함)

BATCH = 25  # 한 번에 묻는 쪽 수
INTRO_WORDS = 40  # 모델에게 보일 쪽 첫머리 낱말 수
GETTING_STARTED = "getting_started/"  # 시작하기 분야. 5.2 설명서에서 15쪽(티켓에는 16쪽으로 적었으나 실제 15쪽, 2026-10-26 사용자 확인)


@dataclass(frozen=True)
class Page:
    """분류할 쪽 하나에서 모델에게 보일 것."""

    path: str  # 쪽 경로(.html 뺀 것, 예: modeling/modifiers/generate/bevel)
    field: str  # 분야(경로 첫 폴더)
    title: str  # 쪽 제목
    headings: tuple[str, ...]  # 첫 겹 소제목 이름, 나온 차례로 한 번씩
    intro: str  # 쪽 글 첫머리 INTRO_WORDS 낱말


def pages_of(chunks: Iterable[Chunk]) -> list[Page]:
    """청크를 쪽마다 묶어 처음 나온 차례로 돌려준다."""
    found: dict[str, tuple[Chunk, list[str], list[str]]] = {}
    for chunk in chunks:
        first, headings, words = found.setdefault(chunk.page_path, (chunk, [], []))
        if chunk.headings and chunk.headings[0] not in headings:
            headings.append(chunk.headings[0])
        if len(words) < INTRO_WORDS:
            words.extend(chunk.body.split()[: INTRO_WORDS - len(words)])
    return [
        Page(path, first.field, first.page_title, tuple(headings), " ".join(words))
        for path, (first, headings, words) in found.items()
    ]


@dataclass(frozen=True)
class Label:
    """쪽 하나의 분류: 초보자 범위에 넣는지와 이유 한 줄."""

    path: str
    include: bool
    reason: str


def fixed_labels(pages: Iterable[Page], courses: Iterable[Course]) -> list[Label]:
    """모델에게 묻지 않고 바로 넣는 쪽: 시작하기 쪽과 연습 과정 단계의 '먼저 볼 소제목'이 가리키는 쪽. 쪽 목록 차례로."""
    pointed: dict[str, str] = {}
    for course in courses:
        for step in course.steps:
            for address in step.manual:
                pointed.setdefault(address.split(".html#")[0], f"연습 과정 '{course.name}'의 단계 '{step.name}'가 가리킴")
    labels = []
    for page in pages:
        if page.path.startswith(GETTING_STARTED):
            labels.append(Label(page.path, True, "시작하기 쪽"))
        elif page.path in pointed:
            labels.append(Label(page.path, True, pointed[page.path]))
    return labels


class Model(Protocol):
    """대화 글(역할 system·user)을 받아 답 글 하나를 돌려준다."""

    def ask(self, messages: list[dict[str, str]]) -> str: ...


INSTRUCTIONS = """너는 Blender 5.2 공식 설명서의 쪽을 '초보자 범위'에 넣을지 판단한다.

초보자 범위: Blender를 처음 쓰는 사람이 간단한 3D 아이템 하나(예: 검, 방패, 컵)를 만들고 glTF로 내보내기까지
마주칠 가능성이 있는 쪽. 기본 화면·조작, 물체 모드와 편집 모드의 기본 편집, 자주 쓰는 모디파이어, 재질 색 정도,
저장·내보내기, 그리고 초보자가 실수로 겪는 문제(화면이 사라짐, 단축키가 안 먹음 등)가 들어간다.
애니메이션·리깅·시뮬레이션·노드 깊은 내용·고급 렌더 설정·영상 편집·파이썬처럼 그 길에서 마주칠 일이 드문 쪽은 뺀다.
꼭 필요한지가 아니라 마주칠 가능성으로 판단한다. 실수로 켜서 겪는 기능, 기본 화면에 늘 보이는 설정도 넣는다.

쪽마다 주소(path), 쪽 제목(title), 첫 겹 소제목(headings), 첫머리 글(intro)을 준다.
JSON 하나로만 답한다: {"pages": [{"path": "...", "include": true 또는 false, "reason": "한국어 이유 한 줄"}]}
받은 쪽을 하나도 빼지 말고 받은 차례대로 답한다."""


def _question(pages: Sequence[Page]) -> list[dict[str, str]]:
    shown = [{"path": p.path, "title": p.title, "headings": list(p.headings), "intro": p.intro} for p in pages]
    return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": json.dumps(shown, ensure_ascii=False)}]


def _answers(text: str, asked: Sequence[Page]) -> list[Label]:
    """모델 답에서 물은 쪽의 올바른 분류만 골라낸다. 깨진 답이면 빈 목록."""
    try:
        rows = json.loads(text)["pages"]
    except (ValueError, KeyError, TypeError):
        return []
    wanted = {page.path for page in asked}
    labels = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        path, include, reason = row.get("path"), row.get("include"), row.get("reason")
        if path in wanted and isinstance(include, bool) and isinstance(reason, str) and reason.strip():
            labels.append(Label(path, include, reason.strip()))
    twice = {label.path for label in labels if sum(other.path == label.path for other in labels) > 1}
    return [label for label in labels if label.path not in twice]  # 한 답에 두 번 나온 쪽은 어느 쪽도 믿지 않는다


CHARS_PER_TOKEN = 4  # 영어 글은 대략 4글자가 토큰 하나(어림값, 실제 요금은 모델이 센 토큰으로 매긴다)
OUTPUT_TOKENS_PER_PAGE = 60  # 답에서 쪽 하나(경로 + 넣음 + 한국어 이유 한 줄)의 어림 토큰 수


@dataclass(frozen=True)
class Estimate:
    """돌리기 전 비용 추정."""

    requests: int  # 모델에게 묻는 횟수(다시 묻기는 빼고)
    input_tokens: int
    output_tokens: int

    def dollars(self, input_price: float, output_price: float) -> float:
        """가격은 백만 토큰당 달러."""
        return (self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000


def estimate(pages: Sequence[Page], batch: int = BATCH) -> Estimate:
    """classify가 pages를 처음부터 물을 때 보낼 글을 그대로 지어 센다."""
    chars = requests = 0
    for start in range(0, len(pages), batch):
        chars += sum(len(message["content"]) for message in _question(pages[start : start + batch]))
        requests += 1
    return Estimate(requests, -(-chars // CHARS_PER_TOKEN), len(pages) * OUTPUT_TOKENS_PER_PAGE)


class ClassifyError(Exception):
    """다시 물어도 바른 분류를 받지 못한 쪽이 있어 멈춤. 그때까지 받은 분류는 파일에 남아 있다."""

    def __init__(self, paths: list[str]):
        super().__init__(f"분류를 받지 못한 쪽 {len(paths)}개: {', '.join(paths)}")
        self.paths = paths


def load_labels(path: Path) -> list[Label]:
    """classify가 쓴 파일(한 줄에 쪽 하나)을 읽는다."""
    return [Label(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line]


@dataclass(frozen=True)
class ScopedLabel:
    """최종 범위의 쪽 하나: 분류와, 그 분류를 어느 묶음에서 가져왔는지."""

    path: str
    include: bool
    reason: str
    source: str  # 묶음 이름(fixed·decided·luna)


def merge(sources: Sequence[tuple[str, Iterable[Label]]], pages: Sequence[Page]) -> list[ScopedLabel]:
    """(이름, 분류) 묶음들을 합쳐 쪽 차례로 돌려준다. 같은 쪽이 여러 묶음에 있으면 앞 묶음이 이긴다.

    설명서 쪽 가운데 어느 묶음에도 없는 쪽이나, 설명서에 없는 쪽이 있으면 멈춘다(빠뜨리거나 옛 경로를 쓴 것).
    """
    chosen: dict[str, ScopedLabel] = {}
    for name, labels in sources:
        for label in labels:
            chosen.setdefault(label.path, ScopedLabel(label.path, label.include, label.reason, name))
    known = {page.path for page in pages}
    missing = [page.path for page in pages if page.path not in chosen]
    unknown = [path for path in chosen if path not in known]
    if missing or unknown:
        raise ValueError(f"분류가 없는 쪽: {', '.join(missing) or '없음'} / 설명서에 없는 쪽: {', '.join(unknown) or '없음'}")
    return [chosen[page.path] for page in pages]


def classify(pages: Sequence[Page], model: Model, out: Path, batch: int = BATCH) -> list[Label]:
    """쪽을 batch개씩 모델에게 묻고, 묶음 하나를 받을 때마다 out(한 줄에 쪽 하나, JSON)에 덧붙인다.

    out에 이미 있는 쪽은 다시 묻지 않는다(중간에 끊겨 다시 돌려도 돈을 두 번 내지 않게).
    돌려주는 것은 pages 차례의 분류다.
    """
    done = {label.path: label for label in load_labels(out)} if out.is_file() else {}
    out.parent.mkdir(parents=True, exist_ok=True)
    todo = [page for page in pages if page.path not in done]
    for start in range(0, len(todo), batch):
        asked = todo[start : start + batch]
        labels = _answers(model.ask(_question(asked)), asked)
        missing = [page for page in asked if page.path not in {label.path for label in labels}]
        if missing:  # 빠진 쪽·이유가 빈 쪽·깨진 답은 그 쪽만 한 번 다시 묻는다
            labels += _answers(model.ask(_question(missing)), missing)
        got = {label.path: label for label in labels}
        with out.open("a", encoding="utf-8") as file:
            for page in asked:
                if page.path in got:
                    file.write(json.dumps(asdict(got[page.path]), ensure_ascii=False) + "\n")
        done.update(got)
        failed = [page.path for page in asked if page.path not in got]
        if failed:  # 모델이 계속 이상하게 답하면 돈을 더 쓰지 않게 바로 멈춘다
            raise ClassifyError(failed)
    return [done[page.path] for page in pages]


class OpenAIModel:
    """OpenAI Chat Completions에 묻는다(돈이 든다, 시험하지 않음). 받은 토큰 수를 쌓아 둔다.

    실제 연결의 틀(바꿔 끼우기·시간 한도)은 티켓 31·33에서 정한다. 여기서는 분류 한 번에 필요한 만큼만 둔다.
    """

    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str, key: str, effort: str | None = None, timeout: float = 120):
        self.model, self.key, self.effort, self.timeout = model, key, effort, timeout
        self.input_tokens = self.output_tokens = self.reasoning_tokens = self.requests = 0

    def ask(self, messages: list[dict[str, str]]) -> str:
        body = {"model": self.model, "messages": messages, "response_format": {"type": "json_object"}}
        if self.effort:  # 생각 수준. 주지 않으면 모델 기본값(티켓 30에서 처음 두 번은 주지 않고 돌렸다)
            body["reasoning_effort"] = self.effort
        request = urllib.request.Request(
            self.URL, json.dumps(body).encode("utf-8"),
            {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            answer = json.loads(response.read())
        self.requests += 1
        self.input_tokens += answer["usage"]["prompt_tokens"]
        self.output_tokens += answer["usage"]["completion_tokens"]  # 생각 토큰을 포함한 출력(이것으로 요금을 매긴다)
        self.reasoning_tokens += answer["usage"].get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        return answer["choices"][0]["message"]["content"]


def openai_key(env_file: Path = DATA / ".env") -> str:
    """환경 변수 OPENAI_API_KEY, 없으면 data/.env의 같은 이름 줄에서 읽는다. 키는 화면에 내지 않는다."""
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "OPENAI_API_KEY" and value.strip():
                return value.strip().strip("\"'")
    raise SystemExit(f"OpenAI 키가 없습니다. 환경 변수 OPENAI_API_KEY나 {env_file}에 넣어 주세요.")


def _chosen(pages: list[Page], only: Path | None) -> list[Page]:
    """--only 파일(한 줄에 쪽 경로 하나, #부터는 메모)에 적힌 쪽만, 그 파일 차례로. 없으면 바로 넣는 쪽을 뺀 전부."""
    if only is None:
        fixed = {label.path for label in fixed_labels(pages, load_courses(COURSES))}
        return [page for page in pages if page.path not in fixed]
    by_path = {page.path: page for page in pages}
    paths = [line.split("#")[0].strip() for line in only.read_text(encoding="utf-8").splitlines()]
    unknown = [path for path in paths if path and path not in by_path]
    if unknown:
        raise SystemExit(f"설명서에 없는 쪽: {', '.join(unknown)}")
    return [by_path[path] for path in paths if path]


def main(argv: Sequence[str] | None = None) -> int:
    """명령 줄 입구. 돈이 드는 것은 classify뿐이다."""
    parser = argparse.ArgumentParser(description="설명서 쪽을 초보자 범위로 분류합니다.")
    parser.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl", help="설명서 청크 파일")
    commands = parser.add_subparsers(dest="command", required=True)
    fixed_command = commands.add_parser("fixed", help="바로 넣는 쪽(시작하기·연습 과정)을 파일로 쓴다")
    fixed_command.add_argument("--out", type=Path, default=OUT / "fixed.jsonl")
    estimate_command = commands.add_parser("estimate", help="모델에게 물을 횟수와 토큰 수를 어림한다(무료)")
    classify_command = commands.add_parser("classify", help="모델에게 물어 분류한다(돈이 든다)")
    for command in (estimate_command, classify_command):
        command.add_argument("--only", type=Path, help="이 파일에 적힌 쪽만(한 줄에 쪽 경로 하나). 없으면 바로 넣는 쪽을 뺀 전부")
    estimate_command.add_argument("--price", type=float, nargs=2, metavar=("입력", "출력"), help="백만 토큰당 달러")
    classify_command.add_argument("--out", type=Path, required=True, help="분류를 덧붙일 파일(이미 있는 쪽은 다시 묻지 않음)")
    classify_command.add_argument("--model", required=True, help="OpenAI 모델 이름")
    classify_command.add_argument("--effort", help="생각 수준(none·low 등). 없으면 모델 기본값")
    merge_command = commands.add_parser("merge", help="분류 파일들을 합쳐 최종 범위 파일을 쓴다(무료)")
    merge_command.add_argument("labels", type=Path, nargs="+", help="분류 파일들. 같은 쪽은 앞 파일이 이긴다")
    merge_command.add_argument("--out", type=Path, default=OUT / "scope.jsonl")
    args = parser.parse_args(argv)

    pages = pages_of(load_chunks(args.chunks))
    if args.command == "merge":
        if args.out.exists():
            raise SystemExit(f"{args.out}가 이미 있습니다. 덮어쓰지 않습니다.")
        scope = merge([(path.stem, load_labels(path)) for path in args.labels], pages)
        args.out.write_text("".join(json.dumps(asdict(label), ensure_ascii=False) + "\n" for label in scope), encoding="utf-8")
        for path in args.labels:
            used = [label for label in scope if label.source == path.stem]
            print(f"{path.stem}: {len(used)}쪽 가져옴, 그중 넣음 {sum(label.include for label in used)}")
        print(f"넣음 {sum(label.include for label in scope)}쪽 / 전체 {len(scope)}쪽 → {args.out}")
        return 0
    if args.command == "fixed":
        if args.out.exists():
            raise SystemExit(f"{args.out}가 이미 있습니다. 덮어쓰지 않습니다.")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        labels = fixed_labels(pages, load_courses(COURSES))
        args.out.write_text("".join(json.dumps(asdict(label), ensure_ascii=False) + "\n" for label in labels), encoding="utf-8")
        print(f"바로 넣는 쪽 {len(labels)}개 → {args.out}")
        return 0
    chosen = _chosen(pages, args.only)
    if args.command == "estimate":
        guess = estimate(chosen)
        print(f"쪽 {len(chosen)}개, 물음 {guess.requests}번, 입력 약 {guess.input_tokens:,} 토큰, 출력 약 {guess.output_tokens:,} 토큰")
        if args.price:
            print(f"약 ${guess.dollars(*args.price):.4f}")
        return 0
    model = OpenAIModel(args.model, openai_key(), args.effort)
    try:
        labels = classify(chosen, model, args.out)
    finally:
        print(f"물음 {model.requests}번, 입력 {model.input_tokens:,} 토큰, 출력 {model.output_tokens:,} 토큰(그중 생각 {model.reasoning_tokens:,})")
    print(f"넣음 {sum(label.include for label in labels)}개 / 뺌 {sum(not label.include for label in labels)}개 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
