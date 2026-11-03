"""파일 지우기 명령(rm·rmdir·Remove-Item)을 실행하기 전에, 무엇이 지워지고 되살릴 수 있는지 쉬운 말로 묻는 훅
(PreToolUse, Bash·PowerShell). HISTORY [144].

설정의 "ask" 규칙만으로는 확인 창에 명령 줄만 보여서, 지울 대상마다 파일·폴더인지, git으로 되살릴 수 있는지를 붙인다.
귀찮으면 .claude/settings.json에서 이 훅 줄만 빼면 된다("ask" 규칙은 그대로 남아 확인 창은 계속 뜬다).
지우기 명령이 없으면 아무것도 하지 않는다(출력 없음 = 평소 권한 규칙대로).
"""

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ask_branch_delete import pieces

DELETE_COMMANDS = {"rm", "rmdir", "remove-item"}
# Remove-Item에서 값을 받는 옵션(그 값은 지울 대상이 아니다). -Path·-LiteralPath 뒤 값은 대상이다.
_VALUE_OPTIONS = {"-filter", "-include", "-exclude", "-credential", "-stream"}
SHOWN_AT_MOST = 10


def targets(words: list[str]) -> list[str] | None:
    """조각 하나가 파일 지우기면 지울 대상 목록, 아니면 None."""
    if not words or words[0].lower() not in DELETE_COMMANDS:
        return None
    found, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif word.startswith("-"):
            skip = word.lower() in _VALUE_OPTIONS
        else:
            found.extend(part for part in word.split(",") if part)  # PowerShell은 a,b로 여러 개를 준다
    return found


def _local_path(text: str, cwd: str) -> Path:
    """Git Bash 모양(/c/WORK/…)·~ 를 이 PC 경로로."""
    text = re.sub(r"^/([a-zA-Z])/", r"\1:/", text)
    path = Path(os.path.expanduser(text))
    return path if path.is_absolute() else Path(cwd) / path


def _git_lines(cwd: Path, *args: str) -> list[str] | None:
    """git 명령의 출력 줄들. git 저장소 밖이면 None."""
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=10)
    return done.stdout.splitlines() if done.returncode == 0 else None


def describe(path: Path) -> str:
    """대상 하나: 무엇이고, 지우면 되살릴 수 있나."""
    if not path.exists():
        return "지금 없는 것이라 지워지는 것이 없습니다."
    where = path if path.is_dir() else path.parent
    tracked = _git_lines(where, "ls-files", "--", path.name if path.is_file() else ".")
    if path.is_file():
        kind, total = "파일", 1
    else:
        total = sum(len(files) for _, _, files in os.walk(path))
        kind = f"폴더, 안에 파일 {total}개"
    if tracked is None:
        return f"({kind}) git 저장소 밖이라 지우면 되살릴 수 없습니다."
    changed = _git_lines(where, "status", "--porcelain", "--", path.name if path.is_file() else ".") or []
    changed = [line for line in changed if not line.startswith("??")]
    saved = len(tracked)
    if saved == 0:
        return f"({kind}) git에 저장되지 않은 것이라 지우면 되살릴 수 없습니다."
    note = f" 그중 {len(changed)}개는 마지막 저장 뒤 고친 내용이 있어, 그 고친 부분은 사라집니다." if changed else ""
    if saved >= total:
        return f"({kind}) 모두 git에 저장돼 있어 git으로 되살릴 수 있습니다.{note}"
    return f"({kind}) {saved}개는 git으로 되살릴 수 있고, 나머지 {total - saved}개는 git에 없어 되살릴 수 없습니다.{note}"


def explain(target: str, cwd: str) -> str:
    if re.search(r"[$`]", target):
        return f"{target}: 명령 안의 변수라 정확히 무엇이 지워지는지 미리 알 수 없습니다."
    if any(c in target for c in "*?["):
        matches = glob.glob(str(_local_path(target, cwd)))
        if not matches:
            return f"{target}: 맞는 것이 지금 없습니다."
        listed = ", ".join(Path(m).name for m in matches[:SHOWN_AT_MOST])
        more = f" 외 {len(matches) - SHOWN_AT_MOST}개" if len(matches) > SHOWN_AT_MOST else ""
        return f"{target}: {len(matches)}개({listed}{more})"
    return f"{target}: {describe(_local_path(target, cwd))}"


def decide(command: str, cwd: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    # 나누는 함수는 \ 를 이스케이프로 읽어 C:\WORK 가 C:WORK 가 된다. Windows 경로는 / 로 써도 같은 곳이다.
    parts = pieces(command.replace("\\", "/"))
    found = [t for p in parts if (t := targets(p)) is not None]
    if not found:
        return None
    names = [name for group in found for name in group]
    lines = [f"- {explain(name, cwd)}" for name in names[:SHOWN_AT_MOST]]
    if len(names) > SHOWN_AT_MOST:
        lines.append(f"- 그 밖에 {len(names) - SHOWN_AT_MOST}개")
    if not names:
        lines.append("- 지울 대상을 명령에서 찾지 못했습니다.")
    others = len(parts) - len(found)
    if others:
        lines.append(f"(이 줄에는 지우기 말고 다른 명령 {others}개도 함께 있습니다.)")
    reason = "[파일 지우기 확인] 휴지통으로 가지 않고 바로 지웁니다.\n" + "\n".join(lines)
    return {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": reason}


def main() -> None:
    # Windows 기본 글자판(cp949)이 아니라 UTF-8로 주고받는다(한글 경로·이유가 깨지지 않게)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    answer = decide(command, payload.get("cwd") or ".")
    with open(os.path.join(os.environ["TEMP"], "ask_file_delete_debug.log"), "a", encoding="utf-8") as log:  # 임시 확인용
        log.write(f"{command!r} -> {answer is not None}\n")
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
