"""브랜치 삭제·병합 확인 훅(.claude/hooks/ask_branch_delete.py, HISTORY [137]): 내 PC에 만든 임시 git 저장소로 본다(인터넷 없음)."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "ask_branch_delete.py"
spec = importlib.util.spec_from_file_location("ask_branch_delete", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """origin(빈 저장소) + 내 저장소. main에 병합된 "done"과 병합 안 된 "wip" 브랜치를 GitHub(origin)에도 올려 둔다."""
    origin, mine = tmp_path / "origin.git", tmp_path / "mine"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(mine)], check=True)
    git(mine, "config", "user.email", "t@example.com")
    git(mine, "config", "user.name", "t")
    git(mine, "commit", "-q", "--allow-empty", "-m", "처음")
    git(mine, "remote", "add", "origin", str(origin))
    for name in ("done", "wip"):
        git(mine, "checkout", "-q", "-b", name, "main")
        git(mine, "commit", "-q", "--allow-empty", "-m", name)
    git(mine, "checkout", "-q", "main")
    git(mine, "merge", "-q", "--no-ff", "-m", "done 병합", "done")
    git(mine, "push", "-q", "origin", "main", "done", "wip")
    return str(mine)


def test_오늘_실제로_실행된_섞인_명령은_거부한다(repo):
    today = ("gh pr merge 32 --merge 2>&1 | tail -2 && git checkout -q main && git pull -q && "
             "git branch -d feat/44-first-token-tweaks && (git push origin --delete feat/44-first-token-tweaks 2>&1 | tail -1)")
    answer = hook.decide(today, repo)
    assert answer["permissionDecision"] == "deny" and "따로 한 명령" in answer["permissionDecisionReason"]


def test_병합된_브랜치를_따로_지우면_쉬운_말로_묻는다(repo):
    for command, where in (("git branch -d done", "내 컴퓨터"), ("git push origin --delete done", "GitHub"), ("git push origin :done", "GitHub")):
        answer = hook.decide(command, repo)
        assert answer["permissionDecision"] == "ask", command
        assert f'"done" - {where}' in answer["permissionDecisionReason"] and "main에 모두 들어가" in answer["permissionDecisionReason"]


def test_병합_안_된_브랜치는_묻지_않고_거부한다(repo):
    for command in ("git branch -D wip", "git push origin --delete wip", "git push --delete origin wip"):
        answer = hook.decide(command, repo)
        assert answer["permissionDecision"] == "deny", command
        assert "아직 main에 들어가지 않았습니다" in answer["permissionDecisionReason"]


def test_없는_브랜치나_최신_상태를_받지_못하면_거부한다(repo):
    assert "찾지 못했습니다" in hook.decide("git branch -d 없는것", repo)["permissionDecisionReason"]
    git(repo, "remote", "set-url", "origin", str(Path(repo).parent / "사라진.git"))
    answer = hook.decide("git branch -d done", repo)
    assert answer["permissionDecision"] == "deny" and "최신 상태를 받지 못했습니다" in answer["permissionDecisionReason"]


def test_병합하며_같이_지우는_명령과_API_삭제는_거부한다(repo):
    assert hook.decide("gh pr merge 5 --merge --delete-branch", repo)["permissionDecision"] == "deny"
    assert hook.decide("gh api -X DELETE repos/o/r/git/refs/heads/x", repo)["permissionDecision"] == "deny"


def test_병합_명령은_PR_설명을_붙여_묻고_섞이면_거부한다(repo, monkeypatch):
    monkeypatch.setattr(hook, "pr_summary", lambda cwd, number: f"PR #{number} 설명")
    assert hook.decide("gh pr merge 32 --merge", repo) == {
        "hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "[PR 병합 확인] PR #32 설명"}
    assert hook.decide("gh pr merge 32 --merge && git log", repo)["permissionDecision"] == "deny"


def test_따옴표_안_글과_heredoc_본문은_명령으로_보지_않는다(repo):
    heredoc = "python - <<'EOF'\nnote = '오늘 git status && git push origin --delete done 를 한 줄로 실행'\nEOF\ngit status"
    assert hook.decide(heredoc, repo) is None
    assert hook.decide('git commit -m "git branch -d done 을 막는다" && git log', repo) is None
    assert hook.decide("echo 기록 && git branch -d done", repo)["permissionDecision"] == "deny"  # 따옴표 밖은 그대로 잡는다


def test_지우지_않는_명령에는_관여하지_않는다(repo):
    for command in ("git branch -a", "git branch feat/x HEAD", "git push -u origin feat/x", "git status --short",
                    'echo "git branch -d done"', "git branch --merged"):
        assert hook.decide(command, repo) is None, command
