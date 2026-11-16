"""제품 코드·훅을 advisor와 상의하지 않고 커밋하지 않게 막는 훅(PreToolUse, Bash·PowerShell). HISTORY [361] 회고 A, [362]·[363].

- 왜 커밋 때인가: 지난 기록(2026-11-12-16)에서 범위 파일 쓰기 89개 중 약 80개가 Edit·Write가 아니라 Bash(sed·파이썬 heredoc)였다.
  고치는 길은 여러 갈래라 다 못 지키므로, 어느 길로 고쳤든 지나가는 커밋에서 본다. 커밋 전이면 잘못 고친 것은 git으로 되돌린다.
  사용자 "어차피 git 으로 관리되는 이상 고친 후라도 막고 상의해서 잘못 고친거면 되돌리면 그만이니?" → "ㅇㅇ".
- 대상: 커밋에 들어갈 `blender_tutor/`·`addon/`·`.claude/hooks/` 파일. 명령에 `git add`나 `commit -a`가 함께 있으면
  아직 스테이징 전이라 스테이징 안 된 것·새 파일도 보고(경로를 붙인 `git commit -m x 파일`도 같음), 없으면 스테이징된 것만 본다
  (범위 파일이 더러운 채 문서만 커밋할 때 막지 않게). `cd "$D"`처럼 풀지 못하는 폴더는 입력의 cwd로 본다.
- 규칙: 세션 기록(transcript_path)에서 마지막 사람 메시지(`origin.kind == "human"`, restore_after_compact.py와 같은 판별) 뒤에
  advisor 결과(`advisor_tool_result`, 성공·오류 모두)가 있으면 통과. 호출 줄만 있고 결과가 없으면(편집과 같은 메시지에 보냈거나 끊김) 막는다.
- 명령 나누기는 deny_cut_output.py의 linked_pieces·git_subcommand를 쓴다(커밋 메시지·heredoc·echo 속 "git commit" 글자는 안 본다).
  커밋 명령이 아니면 기록·git을 읽지 않고 바로 끝낸다.
- 못 보는 것: 커밋 전에 이미 효과가 난 것(고친 훅은 바로 돈다, 고친 코드로 돌린 유료 시험, Git 밖 `results/`·`data/`),
  `--amend`·병합·체리픽, 말로 한 제안. advisor 도구가 없는 세션에서는 범위 커밋이 계속 막힌다.
  하위 에이전트(입력에 agent_id)는 advisor가 없어 보지 않는다. 그 키가 실제로 오는지는 확인하지 않았다.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from deny_cut_output import git_subcommand, linked_pieces

SCOPES = ("blender_tutor", "addon", ".claude/hooks")
PATHSPECS = [f":(top){s}" for s in SCOPES]
CHUNK = 1 << 20  # 기록 파일을 끝에서 1MB씩 거슬러 읽는다
REASON = ("advisor와 상의하지 않은 제품 코드·훅 커밋이다(마지막 사용자 메시지 뒤 advisor 결과 없음): {files}. "
          "advisor를 불러 이 변경을 검토받은 뒤 같은 커밋을 다시 한다. 잘못 고친 것이면 되돌린다. "
          "advisor를 부를 수 없으면(도구 없음 등) 사용자에게 알린다.")


def _is_human(entry: dict) -> bool:
    return (
        entry.get("type") == "user"
        and (entry.get("origin") or {}).get("kind") == "human"
        and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain"))
    )


def _has_block(entry: dict, block_type: str) -> bool:
    content = (entry.get("message") or {}).get("content")
    return isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == block_type for b in content)


def lines_from_end(path: Path):
    """기록 파일을 끝에서부터 한 줄씩(덜 적힌 마지막 줄 포함, 읽지 못하는 줄은 consulted가 건너뜀)."""
    with path.open("rb") as f:
        f.seek(0, 2)
        pos, rest = f.tell(), b""
        while pos > 0:
            step = min(CHUNK, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + rest).split(b"\n")
            rest = parts.pop(0)
            yield from reversed(parts)
        yield rest


def consulted(transcript: Path) -> bool:
    """마지막 사람 메시지 뒤에 advisor 결과(성공·오류)가 있는지."""
    for raw in lines_from_end(transcript):
        if b"advisor_tool_result" not in raw and b'"human"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "assistant" and _has_block(entry, "advisor_tool_result"):
            return True  # api-request-blob 줄도 같은 블록을 담지만 적히는 때를 확인하지 않아 assistant 줄만 센다
        if _is_human(entry):
            return False
    return False


def _git_dir(words: list[str], here: str) -> str:
    """git 조각의 -C 값(여럿이면 차례로 이어 붙임)."""
    for index, word in enumerate(words[:-1]):
        if word == "-C":
            here = os.path.join(here, words[index + 1])
    return here


# commit 옵션 가운데 값을 하나 받는 것(그 값은 경로 인자가 아니다)
_COMMIT_VALUE_OPTIONS = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date", "--template",
                         "--reuse-message", "--reedit-message", "--fixup", "--squash", "--cleanup", "--trailer"}


def _commits_worktree(words: list[str]) -> bool:
    """commit이 스테이징 안 된 내용도 커밋하는지: -a·--all(-am처럼 붙은 꼴 포함)이나 경로 인자(`git commit -m x 파일`)."""
    after = iter(words[words.index("commit") + 1:] if "commit" in words else [])
    for word in after:
        if word == "--":
            return True
        if word == "--all" or (word.startswith("-") and not word.startswith("--") and "a" in word[1:]):
            return True
        if word in _COMMIT_VALUE_OPTIONS or (word.startswith("-") and not word.startswith("--") and word[-1] in "mFCct"):
            next(after, None)
        elif not word.startswith("-"):
            return True
    return False


def commit_targets(command: str, cwd: str) -> tuple[str, bool] | None:
    """커밋 조각이 있으면 (저장소 폴더, 스테이징 안 된 것도 볼지), 없으면 None."""
    here, added = cwd, False
    for _, words in linked_pieces(command.replace("\\", "/")):
        if words and words[0] == "cd" and len(words) > 1:
            moved = os.path.join(here, os.path.expanduser(words[1]))
            here = moved if os.path.isdir(moved) else cwd  # "$D"처럼 풀지 못하면 입력의 cwd로 본다
            continue
        sub = git_subcommand(words)
        if sub == "add":
            added = True
        elif sub == "commit":
            return _git_dir(words, here), added or _commits_worktree(words)
    return None


def scope_files(repo: str, with_unstaged: bool) -> list[str]:
    """커밋에 들어갈 범위 파일. git 저장소가 아니면 빈 목록(이 훅이 볼 커밋이 아님)."""
    if with_unstaged:
        args = ["status", "--porcelain=v1", "--untracked-files=all", "--", *PATHSPECS]
    else:
        args = ["diff", "--cached", "--name-only", "--", *PATHSPECS]
    done = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        return []
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    if with_unstaged:
        lines = [line[3:].split(" -> ")[-1] for line in lines]
    return lines


def decide(command: str, cwd: str, transcript: Path) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    target = commit_targets(command, cwd)
    if target is None:
        return None
    files = scope_files(*target)
    if not files or consulted(transcript):
        return None
    return {"hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": REASON.format(files=", ".join(files[:5]) + (" 등" if len(files) > 5 else ""))}


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    if payload.get("agent_id"):
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if commit_targets(command, payload.get("cwd") or os.getcwd()) is None:
        return  # 커밋이 아니면 기록을 읽지 않는다(transcript_path가 없는 입력에서도 막지 않게)
    answer = decide(command, payload.get("cwd") or os.getcwd(), Path(payload["transcript_path"]))
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
