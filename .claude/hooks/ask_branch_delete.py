"""브랜치 삭제·PR 병합 명령을 실행 전에 확인하는 훅(PreToolUse, Bash·PowerShell). HISTORY [137].

- 브랜치 삭제나 병합이 다른 명령과 한 줄에 섞여 있으면 거부한다(따로 한 명령씩 보내게).
- 브랜치 삭제는 GitHub에서 최신 상태를 받아, 그 브랜치 내용이 main에 모두 들어갔을 때만 쉬운 말로 묻는다.
  아직 안 들어갔거나 확인하지 못하면(인터넷 끊김 등) 거부한다.
- PR 병합은 PR 제목과 CI 시험 상태를 붙여 묻는다.
그 밖의 명령에는 아무것도 하지 않는다(출력 없음 = 평소 권한 규칙대로).
"""

import json
import re
import shlex
import subprocess
import sys

MAIN = "origin/main"
FETCH_SECONDS = 20

# 명령을 조각으로 가르는 기호(따옴표 밖에서만): && || ; | & 줄바꿈 괄호
_SEPARATORS = {"&&", "||", ";", "|", "&", "\n", "(", ")", ";;"}
# heredoc 시작(<<EOF, <<'EOF', <<-"EOF"): 그 뒤 끝 표시 줄까지는 명령이 아니라 넘기는 글이다
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _without_heredocs(command: str) -> str:
    """heredoc 본문(넘기는 글)을 뺀 명령. 본문에 적힌 'git branch -d' 같은 글을 명령으로 오인하지 않게."""
    kept, end = [], None
    for line in command.split("\n"):
        if end is not None:
            if line.strip() == end:
                end = None
            continue
        kept.append(line)
        if match := _HEREDOC.search(line):
            end = match.group(2)
    return "\n".join(kept)


def pieces(command: str) -> list[list[str]]:
    """명령 줄을 이어 붙인 조각들(조각마다 낱말 목록, 빈 조각 뺌). 따옴표 안의 글과 heredoc 본문은 가르지 않는다.
    따옴표가 안 닫힌 명령이면 기호마다 보수적으로 가른다."""
    command = _without_heredocs(command)
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = re.split(r"\s+|(&&|\|\||;|\||\n)", command)
        tokens = [t for t in tokens if t]
    found, current = [], []
    for token in tokens:
        if token in _SEPARATORS:
            if current:
                found.append(current)
            current = []
        else:
            current.append(token)
    if current:
        found.append(current)
    return found


def deletion(words: list[str]) -> dict | None:
    """조각 하나가 브랜치 삭제면 {"곳": "내 컴퓨터"·"GitHub", "브랜치": [...]}, 판정할 수 없는 삭제면 {"곳": "모름"}, 아니면 None."""
    piece = " ".join(words)
    if len(words) >= 2 and words[0] == "git" and words[1] == "branch":
        flags = [w for w in words[2:] if w.startswith("-")]
        if any(f == "--delete" or (not f.startswith("--") and re.search("[dD]", f)) for f in flags):
            return {"곳": "내 컴퓨터", "브랜치": [w for w in words[2:] if not w.startswith("-")]}
    if len(words) >= 2 and words[0] == "git" and words[1] == "push":
        rest = [w for w in words[2:] if not w.startswith("-") or w in ("--delete", "-d")]
        if "--delete" in rest or "-d" in rest:
            names = [w for w in rest if w not in ("--delete", "-d")]
            return {"곳": "GitHub", "브랜치": names[1:]}  # 첫 낱말은 원격 이름(origin)
        colon = [w[1:] for w in rest[1:] if w.startswith(":") and len(w) > 1]
        if colon:
            return {"곳": "GitHub", "브랜치": colon}
    if words[:2] == ["gh", "api"] and re.search(r"(-X|--method)\s+DELETE", piece) and "git/refs" in piece:
        return {"곳": "모름"}
    return None


def merging(words: list[str]) -> dict | None:
    """조각 하나가 PR 병합이면 {"PR": 번호 또는 None, "같이 삭제": bool}, 아니면 None."""
    if words[:3] != ["gh", "pr", "merge"]:
        return None
    number = next((w for w in words[3:] if w.isdigit()), None)
    return {"PR": number, "같이 삭제": any(w in ("--delete-branch", "-d") for w in words[3:])}


def _git(cwd: str, *args: str, timeout: float = 10) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def merged(cwd: str, found: dict) -> tuple[bool, str]:
    """지우려는 브랜치가 모두 main에 들어갔나와 그 설명. 최신 상태를 받지 못하거나 브랜치를 찾지 못하면 (False, 까닭)."""
    try:
        fetched = _git(cwd, "fetch", "-q", "origin", timeout=FETCH_SECONDS)
    except subprocess.TimeoutExpired:
        return False, "GitHub에서 최신 상태를 받지 못했습니다(시간 초과). 인터넷을 확인한 뒤 다시 시도하세요."
    if fetched.returncode != 0:
        return False, f"GitHub에서 최신 상태를 받지 못했습니다: {fetched.stderr.strip()[:200]}"
    if not found["브랜치"]:
        return False, "어느 브랜치를 지우는지 명령에서 찾지 못했습니다."
    for name in found["브랜치"]:
        ref = f"refs/heads/{name}" if found["곳"] == "내 컴퓨터" else f"refs/remotes/origin/{name}"
        if _git(cwd, "rev-parse", "--verify", "-q", ref).returncode != 0:
            return False, f"\"{name}\" 브랜치를 {found['곳']}에서 찾지 못했습니다(이미 지워졌거나 이름이 다름)."
        if _git(cwd, "merge-base", "--is-ancestor", ref, MAIN).returncode != 0:
            return False, (f"\"{name}\"의 내용이 아직 main에 들어가지 않았습니다. "
                           "지금 지우면 작업이 사라질 수 있어서 막았습니다. 병합이 끝난 뒤 다시 시도하세요.")
    return True, "이 브랜치의 내용은 이미 main에 모두 들어가 있습니다."


def pr_summary(cwd: str, number: str | None) -> str:
    """PR 제목·상태·CI 시험 결과를 쉬운 말로. 확인하지 못하면 그렇다고 적는다."""
    args = ["gh", "pr", "view", *([number] if number else []), "--json", "number,title,state,statusCheckRollup"]
    try:
        shown = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=FETCH_SECONDS)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "PR 정보를 확인하지 못했습니다."
    if shown.returncode != 0:
        return "PR 정보를 확인하지 못했습니다."
    data = json.loads(shown.stdout)
    checks = data.get("statusCheckRollup") or []
    if not checks:
        ci = "CI 시험 결과가 없습니다"
    elif all((c.get("conclusion") or "").upper() == "SUCCESS" for c in checks):
        ci = "CI 시험: 통과"
    elif any((c.get("status") or "").upper() != "COMPLETED" for c in checks):
        ci = "CI 시험: 아직 진행 중(끝나기 전에는 병합이 막힙니다)"
    else:
        ci = "CI 시험: 실패한 것이 있습니다"
    return f"PR #{data['number']} \"{data['title']}\"을(를) main에 합칩니다. {ci}."


def decide(command: str, cwd: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    parts = pieces(command)
    deletions = [(p, d) for p in parts if (d := deletion(p))]
    merges = [(p, m) for p in parts if (m := merging(p))]
    if not deletions and not merges:
        return None
    if len(parts) > 1:
        what = "브랜치 지우기" if deletions else "PR 병합"
        return _answer("deny", f"[{what} 거부] {what}가 다른 명령과 한 줄에 섞여 있습니다. "
                               f"결과를 확인하며 진행하도록, {what}는 다른 명령 없이 따로 한 명령으로 보내세요.")
    if merges:
        info = merges[0][1]
        if info["같이 삭제"]:
            return _answer("deny", "[PR 병합 거부] 병합하면서 브랜치를 같이 지우는 명령입니다. "
                                   "병합이 끝난 것(MERGED)을 확인한 뒤 브랜치는 따로 지우세요.")
        return _answer("ask", f"[PR 병합 확인] {pr_summary(cwd, info['PR'])}")
    found = deletions[0][1]
    if found["곳"] == "모름":
        return _answer("deny", "[브랜치 지우기 거부] GitHub API로 직접 지우는 명령은 확인할 수 없어 막았습니다. git 명령으로 지우세요.")
    ok, why = merged(cwd, found)
    names = ", ".join(f'"{n}"' for n in found["브랜치"]) or "(이름 없음)"
    if not ok:
        return _answer("deny", f"[브랜치 지우기 거부] {why}")
    return _answer("ask", f"[브랜치 지우기 확인] 지우려는 것: 작업 브랜치 {names} - {found['곳']}에 있는 것. "
                          f"확인한 것: {why} 허락하면: 브랜치 이름만 사라지고, 작업 내용은 main에 남습니다.")


def _answer(decision: str, reason: str) -> dict:
    return {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}


def main() -> None:
    # Windows 기본 글자판(cp949)이 아니라 UTF-8로 주고받는다(한글 명령·이유가 깨지지 않게)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    answer = decide(command, payload.get("cwd") or ".")
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
