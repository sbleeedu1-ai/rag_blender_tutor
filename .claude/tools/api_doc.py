"""내려받은 Blender 공식 파이썬 문서에서 항목 하나를 끝까지 줄 번호와 함께 보여 준다. HISTORY [214].

첫 줄만 읽고 "설명 없음"으로 적는 일을 줄이려고 만들었다. 시험 전 훅이 이 명령을 돌린 기록을 확인한다.

    .venv\\Scripts\\python .claude\\tools\\api_doc.py bpy.ops.sculpt.brush_stroke
    .venv\\Scripts\\python .claude\\tools\\api_doc.py bpy.types.View3DShading.selected_studio_light
    .venv\\Scripts\\python .claude\\tools\\api_doc.py bpy.types.Window      (타입 전체)
"""

import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "data" / "blender_api_5.2" / "txt"
_ENTRY_MARK = "¶"


def _doc_file(name: str, docs: Path) -> tuple[Path, str] | None:
    """이름의 가장 긴 앞부분과 같은 문서 파일과, 그 뒤에 남은 항목 이름."""
    parts = name.split(".")
    for count in range(len(parts), 0, -1):
        path = docs / (".".join(parts[:count]) + ".txt")
        if path.is_file():
            return path, ".".join(parts[count:])
    return None


def _entry_range(lines: list[str], member: str) -> tuple[int, int] | None:
    """항목의 시작과 끝(끝은 다음 항목 줄). 항목 줄은 문서에서 ¶로 끝난다."""
    head = re.compile(rf"(?:[\w.]+\.)?{re.escape(member)}\b")
    starts = [index for index, line in enumerate(lines) if line.endswith(_ENTRY_MARK) and head.match(line)]
    if not starts:
        return None
    start = starts[0]
    following = (index for index in range(start + 1, len(lines)) if lines[index].endswith(_ENTRY_MARK))
    return start, next(following, len(lines))


def lookup(name: str, docs: Path = DOCS) -> str | None:
    """보여 줄 글. 찾지 못하면 None."""
    found = _doc_file(name, docs)
    if found is None:
        return None
    path, member = found
    lines = path.read_text(encoding="utf-8").splitlines()
    span = _entry_range(lines, member) if member else (0, len(lines))
    if span is None:
        return None
    start, end = span
    body = "\n".join(f"{number + 1}: {lines[number]}" for number in range(start, end))
    return f"{path.name} {start + 1}-{end}줄 (파일 {len(lines)}줄)\n{body}"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("쓰는 법: api_doc.py bpy.ops.sculpt.brush_stroke", file=sys.stderr)
        return 2
    text = lookup(sys.argv[1])
    if text is None:
        # 항목 줄만 본 결과라 "문서에 없다"는 뜻은 아니다
        print(f"{DOCS}의 파일 이름과 항목 줄에서 {sys.argv[1]}을 찾지 못했습니다. 본문 검색은 하지 않았습니다.", file=sys.stderr)
        return 1
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
