"""번역 검사(명세 "자료 준비"의 번역 확인, 티켓 31 3단계).

번역 속 블렌더 표기가 이름표(translate.glossary)의 화면 글자와 맞는지, 단축키가 그대로인지, 덜 옮겨지지 않았는지
코드로 본다. 뜻이 맞는지는 보지 않는다(걸린 곳과 사용자 검수에서 사람이 읽는다).
"""

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from blender_tutor.beginner_scope import DATA
from blender_tutor.menu_names import MenuNames
from blender_tutor.paths import PROJECT
from blender_tutor.translate import BodyNames, Piece, _in_scope, glossary, load_translations, screen_words

_PATH_SEP = "‣"
# 원문 그대로 남아야 하는 키: 조합 키(Ctrl-F), 숫자판·마우스 버튼 번호, 기능 키. LMB·Tab·Delete처럼 하나짜리는
# 풀어 써도 되고(사용자 결정, HISTORY [71]) 보통 낱말과 헷갈려 보지 않는다
_KEYS = re.compile(r"(?<![A-Za-z0-9-])(?:(?:Ctrl|Shift|Alt|Cmd|OSKey)-[A-Za-z0-9]+|Numpad[A-Za-z0-9]+|Mouse\d|F\d{1,2})(?![A-Za-z0-9])")
SHORTEST = 0.3  # 번역 글자 수 ÷ 원문 글자 수가 이보다 작으면 덜 옮긴 것으로 본다(50청크 평균 0.58)


@dataclass(frozen=True)
class Problem:
    """검사에 걸린 곳 하나."""

    key: str  # 청크 열쇠
    kind: str  # 글자 없음 · 영어로 둘 이름을 옮김 · 키 사라짐 · 잘림 · 번역 안 됨
    detail: str  # 기대한 모양이나 사라진 것


def _bounded(english: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9-])" + re.escape(english) + r"(?![A-Za-z0-9-])")


def _korean_only(english: str, shown: str) -> str:
    """'추가(Add) ‣ 메시(Mesh)'에서 괄호 영어를 뺀 '추가 ‣ 메시'."""
    for part in english.split(_PATH_SEP):
        shown = shown.replace(f"({part.strip()})", "", 1)
    return shown


def _entries(piece: Piece, names: MenuNames, body: BodyNames | None) -> list[tuple[str, str]]:
    """이름표 가운데 볼 것. 원문에서 더 긴 이름 안에만 나오는 짧은 이름(3D Cursor 안의 Cursor)은 뺀다."""
    entries = glossary([piece.chunk], names, body)
    text = piece.chunk.text
    kept = []
    for english, shown in entries:
        pattern = _bounded(english)
        if pattern.search(text):
            stripped = text
            for longer, _ in entries:
                if longer != english and english in longer:
                    stripped = _bounded(longer).sub(" ", stripped)
            if not pattern.search(stripped):
                continue
        kept.append((english, shown))
    return kept


def check(piece: Piece, korean: str, names: MenuNames, body: BodyNames | None = None) -> list[Problem]:
    """청크 하나의 번역에서 걸린 곳들. 화면 글자가 있으면 괄호 영어를 뺀 것은 문제로 보지 않는다(english_dropped로 센다)."""
    problems = []
    for english, shown in _entries(piece, names, body):
        if shown == english:  # 화면도 영어: 영어가 그대로 있어야 하고 한국어(영어)로 감싸지 않아야 한다
            if english not in korean or re.search(r"[가-힣][^\s(]*\(" + re.escape(english) + r"\)", korean):
                problems.append(Problem(piece.key, "영어로 둘 이름을 옮김", english))
        elif shown not in korean and _korean_only(english, shown) not in korean:
            problems.append(Problem(piece.key, "글자 없음", shown))
    lost = [key for key in dict.fromkeys(_KEYS.findall(piece.chunk.text)) if key not in korean]
    if lost:
        problems.append(Problem(piece.key, "키 사라짐", ", ".join(lost)))
    if not re.search(r"[가-힣]", korean):
        problems.append(Problem(piece.key, "번역 안 됨", "한글 없음"))
    elif (ratio := len(korean) / max(1, len(piece.chunk.text))) < SHORTEST:
        problems.append(Problem(piece.key, "잘림", f"원문의 {ratio:.2f}배"))
    return problems


def english_dropped(piece: Piece, korean: str, names: MenuNames, body: BodyNames | None = None) -> int:
    """화면 글자는 맞는데 괄호 영어를 뺀 이름 수(문제는 아니고 참고로 센다)."""
    return sum(
        1 for english, shown in _entries(piece, names, body)
        if shown != english and shown not in korean and _korean_only(english, shown) in korean
    )


def fixes_path(original: Path) -> Path:
    """검수에서 고친 줄만 담는 파일(ko_none.jsonl → ko_none_fixes.jsonl). 모델 번역 원본은 덮어쓰지 않는다."""
    return original.with_name(f"{original.stem}_fixes.jsonl")


def reviewed(original: Path) -> dict[str, str]:
    """모델 번역 위에 고친 줄(열쇠·번역·고친 까닭)을 덮어 읽는다. 원본에 없는 청크를 고친 줄이 있으면 멈춘다."""
    translations = load_translations(original)
    fixes = fixes_path(original)
    if fixes.is_file():
        rows = [json.loads(line) for line in fixes.read_text(encoding="utf-8").splitlines() if line]
        unknown = [row["key"] for row in rows if row["key"] not in translations]
        if unknown:
            raise ValueError(f"{fixes}: 원본에 없는 청크 {', '.join(unknown)}")
        translations.update({row["key"]: row["korean"] for row in rows})
    return translations


def main(argv: Sequence[str] | None = None) -> int:
    """사용법: python -m blender_tutor.translation_check data/translations/ko_none.jsonl (무료)

    고친 줄 파일이 있으면 덮어 읽은 뒤 검사하고, 걸린 곳을 같은 폴더 check_<이름>.md에 쓴다.
    """
    parser = argparse.ArgumentParser(description="번역 속 화면 글자·단축키·잘림을 검사합니다.")
    parser.add_argument("translations", type=Path, help="translate run이 쓴 번역 파일")
    parser.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl")
    parser.add_argument("--scope", type=Path, default=DATA / "beginner_scope" / "scope.jsonl")
    parser.add_argument("--names", type=Path, default=DATA / "menu_names" / "menu_names.json")
    parser.add_argument("--po", type=Path, default=DATA / "ui_ko_5.2" / "ko.po")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    titles = MenuNames.load_titles(PROJECT / "menu_titles.json")
    names = MenuNames.load(args.names, MenuNames.load_choices(PROJECT / "menu_choices.json"), titles)
    body = BodyNames(screen_words(names, titles, args.po.read_text(encoding="utf-8")))
    translations = reviewed(args.translations)
    todo = _in_scope(args.chunks, args.scope)
    missing = [piece.key for piece in todo if piece.key not in translations]
    problems = [problem for piece in todo if piece.key in translations for problem in check(piece, translations[piece.key], names, body)]
    dropped = sum(english_dropped(piece, translations[piece.key], names, body) for piece in todo if piece.key in translations)
    kinds = Counter(problem.kind for problem in problems)

    out = args.translations.with_name(f"check_{args.translations.stem}.md")
    lines = [f"# 번역 검사: {args.translations.name}", "", f"청크 {len(todo)}개, 번역 없음 {len(missing)}개, 걸린 곳 {len(problems)}개"
             f"({', '.join(f'{kind} {n}' for kind, n in kinds.most_common()) or '없음'}), 참고: 괄호 영어를 뺀 이름 {dropped}개", ""]
    lines += [f"- 번역 없음 `{key}`" for key in missing]
    lines += [f"- {problem.kind} `{problem.key}`: {problem.detail}" for problem in problems]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(lines[2])
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
