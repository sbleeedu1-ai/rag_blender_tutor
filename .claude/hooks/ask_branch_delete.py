"""브랜치를 지우는 명령이 들어 있으면 실행 전에 사용자에게 따로 묻게 하는 훅(PreToolUse, Bash·PowerShell).

권한 규칙(permissions.ask)은 명령 앞부분으로 맞추므로, 여러 명령을 한 줄에 이으면 중간의 삭제가 눈에 띄지 않을 수 있다.
이 훅은 명령 글 전체에서 브랜치 삭제를 찾아, 찾으면 무엇을 지우는지 적어 "ask"로 돌려준다(2026-11-02, HISTORY [137]).
"""

import json
import re
import sys

# 명령 글에서 브랜치를 지우는 꼴(대소문자 그대로)
PATTERNS = [
    (r"\bgit\s+branch\b[^\n;&|]*\s(-[a-zA-Z]*[dD][a-zA-Z]*|--delete)\b", "로컬 브랜치 삭제(git branch -d/-D)"),
    (r"\bgit\s+push\b[^\n;&|]*\s(--delete|-d)\b", "원격 브랜치 삭제(git push --delete)"),
    (r"\bgit\s+push\s+\S+\s+:\S+", "원격 브랜치 삭제(git push <원격> :<브랜치>)"),
    (r"\bgh\s+pr\s+merge\b[^\n;&|]*\s(--delete-branch|-d)\b", "병합하며 브랜치 삭제(gh pr merge --delete-branch)"),
    (r"\bgh\s+api\b[^\n;&|]*(-X|--method)\s+DELETE[^\n;&|]*git/refs", "GitHub API로 브랜치 삭제"),
]


def found(command: str) -> list[str]:
    return [label for pattern, label in PATTERNS if re.search(pattern, command)]


def main() -> None:
    # Windows 기본 글자판(cp949)이 아니라 UTF-8로 주고받는다(한글 명령·이유가 깨지지 않게)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    labels = found(command)
    if labels:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "브랜치를 지우는 명령이 들어 있습니다: " + ", ".join(labels)
            + ". 병합이 실제로 끝났는지(MERGED) 확인한 뒤 허락하세요.",
        }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
