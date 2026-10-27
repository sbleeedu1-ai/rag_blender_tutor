"""설명서 번역(명세 "자료 준비"의 번역, User Stories 63·65, 티켓 31 2단계).

초보자 범위 청크를 한국어로 옮긴다. 블렌더 표기는 메뉴 이름 사전(menu_names)이 정한 화면 글자를 따라
"한국어(영어)"로 쓰고, 화면에서도 영어로 보이는 이름은 영어 그대로 둔다(번역이 여러 개인데 짝을 고르지 않은 이름 포함).
모델에게는 청크마다 이 이름표를 함께 준다.
"""

import argparse
import json
import random
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from blender_tutor.beginner_scope import CHARS_PER_TOKEN, DATA, Estimate, Model, OpenAIModel, openai_key
from blender_tutor.manual_chunks import Chunk, load_chunks
from blender_tutor.menu_names import MenuNames
from blender_tutor.paths import PROJECT

_PATH_SEP = "‣"  # 설명서 메뉴 경로의 구분 글자(Add ‣ Mesh)
BATCH = 5  # 한 번에 묻는 청크 수(지시문을 덜 되풀이하려고 묶는다)


@dataclass(frozen=True)
class Piece:
    """번역할 청크 하나와 그 열쇠."""

    key: str  # 주소/같은 주소 안의 차례(1부터). 긴 소제목을 나눈 조각은 주소가 같아서 차례로 가른다
    chunk: Chunk


def pieces(chunks: Iterable[Chunk]) -> list[Piece]:
    """청크마다 열쇠를 붙인다. 차례가 열쇠에 들어가므로 일부만 고르기 전에 청크 파일 전체로 부른다."""
    seen: dict[str, int] = {}
    found = []
    for chunk in chunks:
        seen[chunk.address] = seen.get(chunk.address, 0) + 1
        found.append(Piece(f"{chunk.address}/{seen[chunk.address]}", chunk))
    return found


_NOT_NAMES = {"Shortcut"}  # "모드·메뉴·단축키" 상자에서 블렌더 표기가 아닌 칸(단축키 글자)


def _shown(english: str, names: MenuNames, parent: str = "") -> str:
    korean = names.korean(english, parent)
    return f"{korean}({english})" if korean and korean != english else english  # UV처럼 화면도 같은 글자면 한 번만


def _items(chunk: Chunk) -> list[str]:
    """청크에 든 블렌더 표기: 메뉴 경로·버튼 이름, 옵션 이름, 상자 칸 값(쉼표로 나열한 것은 하나씩)."""
    boxed = [value.strip() for label, values in chunk.reference if label not in _NOT_NAMES for value in values.split(",")]
    return [*chunk.ui_names, *chunk.options, *(value for value in boxed if value)]


def glossary(chunks: Iterable[Chunk], names: MenuNames) -> list[tuple[str, str]]:
    """청크들에 나오는 블렌더 표기(메뉴 경로·버튼 이름·옵션 이름·상자 칸 값)와 번역에 쓸 모양. 처음 나온 차례로 한 번씩.

    메뉴 경로는 단마다 바꾸고, 바로 앞 단에 따른 짝을 쓴다(Add ‣ Empty → 추가(Add) ‣ 비어 있음(Empty)).
    한 단이라도 사전에 없으면 넣지 않는다(상자 칸의 All Modes 같은 글 조각은 보통 글로 번역한다).
    """
    found: dict[str, str] = {}
    for chunk in chunks:
        for item in _items(chunk):
            parts = [part.strip() for part in item.split(_PATH_SEP)]
            if item in found or any(names.get(part) is None for part in parts):
                continue
            shown = [_shown(part, names, parts[i - 1] if i else "") for i, part in enumerate(parts)]
            found[item] = f" {_PATH_SEP} ".join(shown)
    return list(found.items())


INSTRUCTIONS = """너는 Blender 5.2 공식 설명서(영어)를 한국어로 번역한다. 읽는 사람은 Blender를 처음 쓰는 한국어 사용자다.

- chunks의 text마다 한국어 번역 하나. 첫 줄은 '쪽 제목 > 소제목' 경로이고 이것도 번역한다. 줄 나눔은 원문대로 둔다.
- 블렌더 표기(메뉴·버튼·옵션 이름)는 glossary의 오른쪽 모양을 글자 그대로 쓴다. 오른쪽이 영어뿐이면 영어 그대로 둔다
  (한국어 화면에서도 영어로 보이는 이름이다). glossary에 없는 이름을 새로 번역해 괄호를 붙이지 않는다.
- 단축키(Ctrl-A 등), 숫자, 주소는 바꾸지 않는다. 설명을 더하거나 빼지 않는다.
JSON 하나로만 답한다: {"chunks": [{"key": "...", "korean": "..."}]}. 받은 청크를 하나도 빼지 말고 받은 차례대로 답한다."""


def _question(asked: Sequence[Piece], names: MenuNames) -> list[dict[str, str]]:
    shown = {
        "glossary": dict(glossary((piece.chunk for piece in asked), names)),
        "chunks": [{"key": piece.key, "text": piece.chunk.text} for piece in asked],
    }
    return [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": json.dumps(shown, ensure_ascii=False)}]


def _answers(text: str, asked: Sequence[Piece]) -> dict[str, str]:
    """모델 답에서 물은 청크의 빈 데 없는 번역만 골라낸다. 깨진 답이면 빈 사전."""
    try:
        rows = json.loads(text)["chunks"]
    except (ValueError, KeyError, TypeError):
        return {}
    wanted = {piece.key for piece in asked}
    got: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("key") in wanted and isinstance(row.get("korean"), str) and row["korean"].strip():
            got[row["key"]] = row["korean"].strip()
    return got


class TranslateError(Exception):
    """다시 물어도 번역을 받지 못한 청크가 있어 멈춤. 그때까지 받은 번역은 파일에 남아 있다."""

    def __init__(self, keys: list[str]):
        super().__init__(f"번역을 받지 못한 청크 {len(keys)}개: {', '.join(keys)}")
        self.keys = keys


def load_translations(path: Path) -> dict[str, str]:
    """translate가 쓴 파일(한 줄에 청크 하나)을 열쇠 → 번역으로 읽는다."""
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return {row["key"]: row["korean"] for row in rows}


def translate(todo: Sequence[Piece], names: MenuNames, model: Model, out: Path, batch: int = BATCH) -> dict[str, str]:
    """청크를 batch개씩 모델에게 묻고, 묶음 하나를 받을 때마다 out(한 줄에 청크 하나, JSON)에 덧붙인다.

    out에 이미 있는 청크는 다시 묻지 않는다(중간에 끊겨 다시 돌려도 돈을 두 번 내지 않게).
    돌려주는 것은 todo 차례의 열쇠 → 번역이다.
    """
    done = load_translations(out) if out.is_file() else {}
    out.parent.mkdir(parents=True, exist_ok=True)
    left = [piece for piece in todo if piece.key not in done]
    for start in range(0, len(left), batch):
        asked = left[start : start + batch]
        got = _answers(model.ask(_question(asked, names)), asked)
        missing = [piece for piece in asked if piece.key not in got]
        if missing:  # 빠진 청크·빈 번역·깨진 답은 그 청크만 한 번 다시 묻는다
            got.update(_answers(model.ask(_question(missing, names)), missing))
        with out.open("a", encoding="utf-8") as file:
            for piece in asked:
                if piece.key in got:
                    file.write(json.dumps({"key": piece.key, "korean": got[piece.key]}, ensure_ascii=False) + "\n")
        done.update(got)
        failed = [piece.key for piece in asked if piece.key not in got]
        if failed:  # 모델이 계속 이상하게 답하면 돈을 더 쓰지 않게 바로 멈춘다
            raise TranslateError(failed)
    return {piece.key: done[piece.key] for piece in todo}


KOREAN_PER_ENGLISH = 2  # 번역 출력 토큰 ÷ 원문 토큰 어림(근거 못 찾은 가정, 조사 문서 31의 위쪽 값). 생각 토큰은 빼고 센다
OUTPUT_TOKENS_PER_PIECE = 20  # 답 JSON에서 청크 하나에 붙는 열쇠·따옴표의 어림 토큰 수


def _tokens(text: str) -> int:
    """어림 토큰 수: 영어 등 ASCII는 CHARS_PER_TOKEN글자에 하나, 한글 등 나머지는 한 글자에 하나(이름표의 한국어)."""
    ascii_chars = sum(letter.isascii() for letter in text)
    return -(-ascii_chars // CHARS_PER_TOKEN) + len(text) - ascii_chars


def estimate(todo: Sequence[Piece], names: MenuNames, batch: int = BATCH) -> Estimate:
    """translate가 todo를 처음부터 물을 때 보낼 글을 그대로 지어 센다(다시 묻기·생각 토큰은 뺌)."""
    input_tokens = requests = 0
    for start in range(0, len(todo), batch):
        input_tokens += sum(_tokens(message["content"]) for message in _question(todo[start : start + batch], names))
        requests += 1
    output_tokens = sum(_tokens(piece.chunk.text) * KOREAN_PER_ENGLISH + OUTPUT_TOKENS_PER_PIECE for piece in todo)
    return Estimate(requests, input_tokens, output_tokens)


def sample(todo: Sequence[Piece], n: int, seed: int, must: Iterable[str] = ()) -> list[Piece]:
    """시험용으로 n개를 고른다. must의 이름마다 그 이름이 든 첫 청크를 먼저 넣고 나머지는 씨앗 값으로 무작위. 원래 차례로."""
    def has(piece: Piece, english: str) -> bool:
        return any(english == part.strip() for item in _items(piece.chunk) for part in item.split(_PATH_SEP))

    chosen: dict[str, None] = {}
    for english in must:
        hit = next((piece for piece in todo if has(piece, english)), None)
        if hit is not None:
            chosen[hit.key] = None
    rest = [piece.key for piece in todo if piece.key not in chosen]
    chosen.update(dict.fromkeys(random.Random(seed).sample(rest, max(0, min(n - len(chosen), len(rest))))))
    return [piece for piece in todo if piece.key in chosen]


SEED = 31  # 시험용 청크를 고르는 씨앗 값. none·medium을 같은 청크로 견주려고 고정한다
MUST = ("Smart UV Project",)  # 시험용 청크에 꼭 넣을 이름: 번역이 여러 개인데 짝을 고르지 않아 영어로 남아야 하는 것(HISTORY [67] P1)


def _in_scope(chunks_file: Path, scope_file: Path) -> list[Piece]:
    """청크 파일 전체로 열쇠를 붙인 뒤, 초보자 범위(scope.jsonl에서 include가 참인 쪽)의 청크만 남긴다."""
    rows = (json.loads(line) for line in scope_file.read_text(encoding="utf-8").splitlines() if line)
    scope = {row["path"] for row in rows if row["include"]}
    return [piece for piece in pieces(load_chunks(chunks_file)) if piece.chunk.page_path in scope]


def main(argv: Sequence[str] | None = None) -> int:
    """명령 줄 입구. 돈이 드는 것은 run뿐이다."""
    parser = argparse.ArgumentParser(description="초보자 범위 청크를 한국어로 번역합니다.")
    parser.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl", help="설명서 청크 파일")
    parser.add_argument("--scope", type=Path, default=DATA / "beginner_scope" / "scope.jsonl", help="초보자 범위 파일")
    parser.add_argument("--names", type=Path, default=DATA / "menu_names" / "menu_names.json", help="메뉴 이름 사전")
    parser.add_argument("--sample", type=int, help=f"시험용으로 이만큼만(씨앗 {SEED}, {', '.join(MUST)}가 든 청크 포함). 없으면 전부")
    commands = parser.add_subparsers(dest="command", required=True)
    estimate_command = commands.add_parser("estimate", help="모델에게 물을 횟수와 토큰 수를 어림한다(무료)")
    estimate_command.add_argument("--price", type=float, nargs=2, metavar=("입력", "출력"), help="백만 토큰당 달러")
    run_command = commands.add_parser("run", help="모델에게 물어 번역한다(돈이 든다)")
    run_command.add_argument("--out", type=Path, required=True, help="번역을 덧붙일 파일(이미 있는 청크는 다시 묻지 않음)")
    run_command.add_argument("--model", required=True, help="OpenAI 모델 이름")
    run_command.add_argument("--effort", help="생각 수준(none·medium 등). 없으면 모델 기본값")
    args = parser.parse_args(argv)

    names = MenuNames.load(
        args.names, MenuNames.load_choices(PROJECT / "menu_choices.json"), MenuNames.load_titles(PROJECT / "menu_titles.json")
    )
    todo = _in_scope(args.chunks, args.scope)
    if args.sample:
        todo = sample(todo, args.sample, SEED, MUST)
    if args.command == "estimate":
        guess = estimate(todo, names)
        print(f"청크 {len(todo)}개, 물음 {guess.requests}번, 입력 약 {guess.input_tokens:,} 토큰, 출력 약 {guess.output_tokens:,} 토큰(생각 토큰 뺌)")
        if args.price:
            print(f"약 ${guess.dollars(*args.price):.4f}")
        return 0
    model = OpenAIModel(args.model, openai_key(), args.effort)
    try:
        got = translate(todo, names, model, args.out)
    finally:
        print(f"물음 {model.requests}번, 입력 {model.input_tokens:,} 토큰, 출력 {model.output_tokens:,} 토큰(그중 생각 {model.reasoning_tokens:,})")
    print(f"번역 {len(got)}개 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
