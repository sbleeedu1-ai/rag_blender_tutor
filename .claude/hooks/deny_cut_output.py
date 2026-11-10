"""공식 문서·푸시 결과를 잘라 읽거나, 허락 없이 저장소를 내려받는 명령을 막는 훅(PreToolUse, Bash·PowerShell).

- `api_doc.py`를 실행하는 조각이나 `git push` 조각의 출력이 파이프(|)로 곧바로 head·tail·grep 같은 자르는 명령에 넘어가면 거부한다.
  공식 문서는 끝까지 읽고(AGENTS.md), 실패를 봐야 하는 명령 뒤에 `| tail`을 붙이지 않는다(CLAUDE.md).
- `git clone` 조각은 거부한다. 내려받기는 채팅에서 파일 이름·출처·크기를 보이고 허락받은 뒤에만 한다.
- 그 밖의 grep·tail은 건드리지 않는다(출력 없음 = 평소 권한 규칙대로).
- 명령 나누기는 ask_branch_delete.py의 pieces()와 같은 방법이다. 다만 조각 사이 기호가 파이프인지 알아야 해서 기호를 함께 남긴다.
"""

import json
import re
import shlex
import sys

from ask_branch_delete import _SEPARATORS, _without_heredocs

# 출력을 잘라 보여 주는 명령. select·sls는 PowerShell에서 Select-Object·Select-String의 줄임 이름이다.
CUTTERS = {"head", "tail", "grep", "cut", "sed", "awk", "select-object", "select-string", "findstr", "more", "select", "sls"}
# git 뒤에 값을 하나 받는 옵션(그 값은 하위 명령이 아니다): git -C 경로 push
_GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
CUT_REASON = ("공식 문서·푸시 결과는 잘라 읽지 않는다(AGENTS.md, CLAUDE.md). "
              "그대로 실행하거나 파일로 저장 뒤 Read로 끝까지 읽는다.")
CLONE_REASON = ("내려받기는 채팅에서 파일 이름·출처·크기를 보이고 허락받은 뒤에만. "
                "허락받았으면 사용자에게 알리고 스크립트로 진행.")


def linked_pieces(command: str) -> list[tuple[str, list[str]]]:
    """(앞 조각과 이은 기호들, 조각의 낱말 목록) 목록. 첫 조각의 기호는 빈 글자.
    pieces()와 같게 따옴표 안의 글과 heredoc 본문은 가르지 않고, 따옴표가 안 닫히면 기호마다 보수적으로 가른다."""
    command = _without_heredocs(command)
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = [t for t in re.split(r"\s+|(&&|\|\||;|\||\n)", command) if t]
    found, current, links = [], [], ""
    for token in tokens:
        if token in _SEPARATORS:
            if current:
                found.append((links, current))
                current, links = [], ""
            links += token if token != "\n" else " "
        else:
            current.append(token)
    if current:
        found.append((links, current))
    return found


def _name(word: str) -> str:
    """경로·.exe를 뺀 명령 이름(소문자): /usr/bin/tail.exe → tail."""
    return re.sub(r"\.exe$", "", word.replace("\\", "/").rsplit("/", 1)[-1].lower())


def git_subcommand(words: list[str]) -> str | None:
    """git 조각이면 하위 명령(push·clone 등), 아니면 None."""
    if not words or _name(words[0]) != "git":
        return None
    rest = iter(words[1:])
    for word in rest:
        if word in _GIT_VALUE_OPTIONS:
            next(rest, None)
        elif not word.startswith("-"):
            return word
    return None


def runs_api_doc(words: list[str]) -> bool:
    """파이썬으로 api_doc.py를 실행하는 조각인지. 이 파일을 grep·cat으로 읽는 조각은 해당하지 않는다."""
    return bool(words) and _name(words[0]) in {"python", "python3", "py"} and any(w.endswith("api_doc.py") for w in words[1:])


def decide(command: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    # pieces()처럼 \ 를 / 로 바꿔 읽는다. 바꾸지 않으면 .claude\tools 가 이스케이프로 읽혀 .claudetools 가 된다.
    parts = linked_pieces(command.replace("\\", "/"))
    for index, (links, words) in enumerate(parts):
        if git_subcommand(words) == "clone":
            return _deny(CLONE_REASON)
        if index == 0 or "|" not in links.replace("||", "") or _name(words[0]) not in CUTTERS:
            continue
        before = parts[index - 1][1]
        if runs_api_doc(before) or git_subcommand(before) == "push":
            return _deny(CUT_REASON)
    return None


def _deny(reason: str) -> dict:
    return {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    answer = decide((payload.get("tool_input") or {}).get("command") or "")
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
