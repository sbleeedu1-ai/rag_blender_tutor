"""HANDOFF.md·HISTORY.md에 없는 HISTORY 번호를 적지 않게 막는 훅(PreToolUse, Write·Edit).

- 대상: 저장소 맨 위의 HANDOFF.md·HISTORY.md. 다른 파일은 보지 않는다.
- 새로 쓰는 글(Write의 content, Edit의 new_string)의 `[숫자]`가 HISTORY.md의 `### [숫자]` 제목에 없으면 거부하고 없는 번호를 알린다.
  HISTORY.md에 쓰는 글이면 그 글 안의 `### [숫자]` 제목도 있는 것으로 친다(새 항목을 쓰는 중이므로).
- 거짓 경보를 줄이려고 빼는 것(지금 HANDOFF·HISTORY 전체로 시험해 정함):
  - 코드 조각(`...`, ```...```) 안: `split(".html")[0]` 같은 코드의 [0].
  - 마크다운 링크 꼴 `[46](.scratch/....md)`: 괄호 안에 빈칸 없는 주소가 붙은 것. `[220](2,000줄까지 …)`처럼 빈칸 있는 덧말은 번호로 본다.
  - 각주·참조 링크 꼴(`][1]`, `[1]:`)과 글자 바로 뒤 `x[1]`.
  - 이미 있던 번호: Edit의 old_string, Write면 지금 파일에 이미 있던 번호. 지난 기록의 잘못(예: 다른 PR에 있는 [161])은
    지난 항목을 고치지 않는 규칙상 그대로 두므로, 그 줄을 다시 쓸 때마다 막히지 않게 한다.
"""

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("HANDOFF.md", "HISTORY.md")
HEADING = re.compile(r"^### \[(\d+)\]", re.MULTILINE)
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
REF = re.compile(r"(?<![\]A-Za-z0-9_])\[(\d+)\](?!\([^\s)]*\)|:)")


def refs(text: str) -> set[str]:
    """글 안의 HISTORY 번호 참조([숫자])들. 코드 조각과 링크·각주 꼴은 뺀다."""
    return set(REF.findall(CODE.sub(" ", text)))


def _same(a: Path, b: Path) -> bool:
    return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def target_name(file_path: str) -> str | None:
    """대상 파일이면 이름(HANDOFF.md·HISTORY.md), 아니면 None."""
    return next((name for name in TARGETS if file_path and _same(Path(file_path), ROOT / name)), None)


def unknown_refs(name: str, new_text: str, old_text: str, history: str) -> list[str]:
    """새로 쓰는 글에 처음 나오는, HISTORY 제목에 없는 번호들(작은 것부터)."""
    known = set(HEADING.findall(history))
    if name == "HISTORY.md":
        known |= set(HEADING.findall(new_text))
    return sorted(refs(new_text) - refs(old_text) - known, key=int)


def decide(tool_name: str, tool_input: dict) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    file_path = tool_input.get("file_path") or ""
    name = target_name(file_path)
    if name is None:
        return None
    if tool_name == "Write":
        new_text = tool_input.get("content") or ""
        old_text = Path(file_path).read_text(encoding="utf-8") if Path(file_path).exists() else ""
    else:
        new_text, old_text = tool_input.get("new_string") or "", tool_input.get("old_string") or ""
    missing = unknown_refs(name, new_text, old_text, (ROOT / "HISTORY.md").read_text(encoding="utf-8"))
    if not missing:
        return None
    numbers = ", ".join(f"[{n}]" for n in missing)
    reason = (f"[HISTORY 번호 확인] {name}에 새로 쓰는 글의 {numbers}이(가) HISTORY.md의 `### [번호]` 제목에 없습니다. "
              "HISTORY.md에서 맞는 번호를 찾아 고치거나, 아직 없는 항목이면 HISTORY.md에 먼저 쓰세요.")
    return {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    answer = decide(payload.get("tool_name") or "", payload.get("tool_input") or {})
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
