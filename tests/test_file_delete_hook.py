"""파일 지우기 확인 훅(.claude/hooks/ask_file_delete.py, HISTORY [144]·[145]): 임시 git 저장소로 본다."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))  # 훅은 옆 파일(ask_branch_delete)에서 명령 나누기를 가져온다
spec = importlib.util.spec_from_file_location("ask_file_delete", HOOKS / "ask_file_delete.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


@pytest.fixture
def repo(tmp_path):
    """저장된 파일 saved.txt(고친 내용 없음), 저장 뒤 고친 edited.txt, git에 없는 new.txt, 반쯤 저장된 폴더 box/."""
    mine = tmp_path / "mine"
    subprocess.run(["git", "init", "-q", str(mine)], check=True)
    for name, text in (("saved.txt", "a"), ("edited.txt", "a"), ("box/kept.txt", "a")):
        (mine / name).parent.mkdir(exist_ok=True)
        (mine / name).write_text(text)
    subprocess.run(["git", "-C", str(mine), "add", "."], check=True)
    subprocess.run(["git", "-C", str(mine), "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "처음"],
                   check=True)
    (mine / "edited.txt").write_text("고침")
    (mine / "new.txt").write_text("새것")
    (mine / "box" / "loose.txt").write_text("새것")
    return str(mine)


def reason(command, cwd):
    answer = hook.decide(command, cwd)
    assert answer["permissionDecision"] == "ask", command
    return answer["permissionDecisionReason"]


def test_대상마다_되살릴_수_있는지_알려_준다(repo):
    text = reason("rm saved.txt edited.txt new.txt 없는것.txt", repo)
    assert text.startswith("[영구 삭제] 지우면 휴지통에 남지 않습니다.")
    assert "- saved.txt (파일): 되살릴 수 있음 (git에 저장됨)\n위치: " in text
    assert "- edited.txt (파일): 되살릴 수 있음, 단 마지막 커밋 뒤 고친 내용은 사라짐" in text
    assert "- new.txt (파일): 되살릴 수 없음 (git 기록 없음)" in text
    assert "- 없는것.txt: 지금 없음 (지워질 것 없음)" in text
    assert f"위치: {Path(repo).resolve().as_posix()}" in text


def test_폴더는_안의_파일을_세어_나눈다(repo):
    text = reason("rm -rf box", repo)
    assert "- box (폴더, 파일 2개): 1개만 되살릴 수 있음, 1개는 git 기록 없음" in text


def test_PowerShell_명령과_Windows_경로도_읽는다(repo):
    absolute = str(Path(repo) / "new.txt")  # C:\...\new.txt 처럼 \ 가 든 경로
    text = reason(f"Remove-Item -LiteralPath {absolute} -Force -Confirm:$false", repo)
    assert "- new.txt (파일): 되살릴 수 없음" in text
    assert "- saved.txt (파일): 되살릴 수 있음" in reason('Remove-Item -Path "saved.txt"', repo)


def test_와일드카드_변수_섞인_명령(repo):
    text = reason("rm *.txt", repo)
    assert all(f"- {n} (파일)" in text for n in ("saved.txt", "edited.txt", "new.txt"))
    assert "- $TARGET: 미리 알 수 없음 (경로에 변수가 있음)" in reason("rm $TARGET", repo)
    assert "다른 명령 1개도 함께" in reason("rm new.txt && git status", repo)


def test_git_reset_hard는_버려지는_파일을_보인다(repo):
    text = reason("git reset --hard", repo)
    assert text.startswith("[고친 내용 버리기]")
    assert "- 버려지는 파일 1개: edited.txt" in text
    assert "커밋으로 옮깁니다" not in text
    assert "- 지금 브랜치를 HEAD~1 커밋으로 옮깁니다." in reason("git reset --hard HEAD~1", repo)


def test_git_clean은_지워질_것을_미리_본다(repo):
    text = reason("git clean -fd", repo)
    assert text.startswith("[git 밖 파일 지우기]")
    assert "- 지워지는 것 2개: box/loose.txt, new.txt" in text
    assert "- 지워지는 것 1개: new.txt" in reason("git clean -f new.txt", repo)


def test_지우지_않는_명령에는_관여하지_않는다(repo):
    for command in ("git rm --cached x", "ls -rm", 'echo "rm new.txt"', "git status", "python -m pytest",
                    "git reset HEAD x", "git clean -n", "git clean --dry-run -d"):
        assert hook.decide(command, repo) is None, command
