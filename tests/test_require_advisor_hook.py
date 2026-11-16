"""advisor 상의 확인 훅(.claude/hooks/require_advisor.py, HISTORY [362]·[363]): 임시 git 저장소와 가짜 세션 기록으로 본다."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))  # 훅이 옆 파일(ask_branch_delete·deny_cut_output)을 가져온다
spec = importlib.util.spec_from_file_location("require_advisor", HOOKS / "require_advisor.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

HUMAN = {"type": "user", "origin": {"kind": "human"}, "message": {"role": "user", "content": "고쳐 줘"}}
CALL = {"type": "assistant", "message": {"content": [{"type": "server_tool_use", "id": "s1", "name": "advisor", "input": {}}]}}
OK = {"type": "assistant", "message": {"content": [{"type": "advisor_tool_result", "tool_use_id": "s1",
                                                     "content": {"type": "advisor_redacted_result"}}]}}
ERROR = {"type": "assistant", "message": {"content": [{"type": "advisor_tool_result", "tool_use_id": "s1",
                                                        "content": {"type": "advisor_tool_result_error", "error_code": "overloaded"}}]}}
TOOL_RESULT = {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """blender_tutor/a.py와 docs/b.md가 커밋된 저장소."""
    mine = tmp_path / "mine"
    subprocess.run(["git", "init", "-q", "-b", "main", str(mine)], check=True)
    git(mine, "config", "user.email", "t@example.com")
    git(mine, "config", "user.name", "t")
    (mine / "blender_tutor").mkdir()
    (mine / "docs").mkdir()
    (mine / "blender_tutor" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (mine / "docs" / "b.md").write_text("글\n", encoding="utf-8")
    git(mine, "add", ".")
    git(mine, "commit", "-q", "-m", "처음")
    return mine


def transcript(tmp_path, *entries) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    return path


def change(repo, rel, stage=True):
    (repo / rel).write_text("바뀜\n", encoding="utf-8")
    if stage:
        git(repo, "add", rel)


def denied(answer) -> bool:
    return bool(answer) and answer["permissionDecision"] == "deny"


def test_scope_commit_without_advisor_is_denied(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    answer = hook.decide("git commit -m 고침", str(repo), transcript(tmp_path, HUMAN, TOOL_RESULT))
    assert denied(answer)
    assert "blender_tutor/a.py" in answer["permissionDecisionReason"]


@pytest.mark.parametrize("result", [OK, ERROR])
def test_advisor_result_success_or_error_passes(repo, tmp_path, result):
    change(repo, "blender_tutor/a.py")
    assert hook.decide("git commit -m 고침", str(repo), transcript(tmp_path, HUMAN, CALL, result)) is None


def test_call_without_result_is_denied(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    assert denied(hook.decide("git commit -m 고침", str(repo), transcript(tmp_path, HUMAN, CALL, TOOL_RESULT)))


def test_new_user_message_resets(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    assert denied(hook.decide("git commit -m 고침", str(repo), transcript(tmp_path, HUMAN, CALL, OK, HUMAN)))


def test_add_and_commit_in_one_command_is_denied(repo, tmp_path):
    change(repo, "blender_tutor/a.py", stage=False)
    command = "git add blender_tutor/a.py && git commit -q -m 고침"
    assert denied(hook.decide(command, str(repo), transcript(tmp_path, HUMAN)))


def test_commit_all_flag_sees_unstaged(repo, tmp_path):
    change(repo, "blender_tutor/a.py", stage=False)
    assert denied(hook.decide("git commit -am 고침", str(repo), transcript(tmp_path, HUMAN)))


def test_docs_only_commit_passes_even_with_dirty_scope_file(repo, tmp_path):
    change(repo, "blender_tutor/a.py", stage=False)
    change(repo, "docs/b.md")
    assert hook.decide("git commit -m 문서", str(repo), transcript(tmp_path, HUMAN)) is None


def test_git_commit_words_inside_message_or_heredoc_pass(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    t = transcript(tmp_path, HUMAN)
    assert hook.decide("echo 'git commit 하기 전에'", str(repo), t) is None
    assert hook.decide("cat > n.md <<'EOF'\ngit commit -m x\nEOF", str(repo), t) is None


def test_cd_or_dash_c_picks_repo(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    t = transcript(tmp_path, HUMAN)
    assert denied(hook.decide(f"cd {repo} && git commit -m 고침", str(tmp_path), t))
    assert denied(hook.decide(f"git -C {repo} commit -m 고침", str(tmp_path), t))


def test_hooks_folder_is_in_scope(repo, tmp_path):
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".claude" / "hooks" / "h.py").write_text("y = 2\n", encoding="utf-8")
    git(repo, "add", ".claude/hooks/h.py")
    assert denied(hook.decide("git commit -m 훅", str(repo), transcript(tmp_path, HUMAN)))


def test_commit_with_path_args_sees_unstaged(repo, tmp_path):
    change(repo, "blender_tutor/a.py", stage=False)
    t = transcript(tmp_path, HUMAN)
    assert denied(hook.decide("git commit -qm 고침 blender_tutor/a.py", str(repo), t))
    assert denied(hook.decide("git commit -m 고침 -- blender_tutor/a.py", str(repo), t))


def test_unresolvable_cd_falls_back_to_cwd(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    assert denied(hook.decide('cd "$D" && git commit -m 고침', str(repo), transcript(tmp_path, HUMAN)))


def test_only_assistant_lines_count_as_result(repo, tmp_path):
    change(repo, "blender_tutor/a.py")
    blob = dict(OK, type="api-request-blob")
    assert denied(hook.decide("git commit -m 고침", str(repo), transcript(tmp_path, HUMAN, CALL, blob)))


def test_non_commit_command_needs_no_transcript_path():
    """하위 에이전트 입력에 transcript_path가 없어도 커밋이 아닌 Bash는 막지 않는다(onFailure block)."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "."})
    done = subprocess.run([sys.executable, str(HOOKS / "require_advisor.py")], input=payload, capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout == ""
