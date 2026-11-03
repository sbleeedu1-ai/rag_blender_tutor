"""파일 지우기 확인 훅(.claude/hooks/ask_file_delete.py, HISTORY [144]): 임시 git 저장소로 본다."""

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
    assert "휴지통으로 가지 않고" in text
    assert "saved.txt: (파일) 모두 git에 저장돼 있어 git으로 되살릴 수 있습니다." in text
    assert "edited.txt: (파일) 모두 git에 저장돼 있어 git으로 되살릴 수 있습니다. 그중 1개는" in text
    assert "new.txt: (파일) git에 저장되지 않은 것이라 지우면 되살릴 수 없습니다." in text
    assert "없는것.txt: 지금 없는 것이라" in text


def test_폴더는_안의_파일을_세어_나눈다(repo):
    assert "box: (폴더, 안에 파일 2개) 1개는 git으로 되살릴 수 있고, 나머지 1개는 git에 없어" in reason("rm -rf box", repo)


def test_PowerShell_명령과_Windows_경로도_읽는다(repo):
    absolute = str(Path(repo) / "new.txt")  # C:\...\new.txt 처럼 \ 가 든 경로
    text = reason(f"Remove-Item -LiteralPath {absolute} -Force -Confirm:$false", repo)
    assert "되살릴 수 없습니다" in text and "지금 없는 것" not in text
    assert "saved.txt: (파일) 모두 git에" in reason('Remove-Item -Path "saved.txt"', repo)


def test_와일드카드_변수_섞인_명령(repo):
    assert "*.txt: 3개(" in reason("rm *.txt", repo)
    assert "변수라 정확히" in reason("rm $TARGET", repo)
    assert "다른 명령 1개도 함께" in reason("rm new.txt && git status", repo)


def test_지우지_않는_명령에는_관여하지_않는다(repo):
    for command in ("git rm --cached x", "ls -rm", 'echo "rm new.txt"', "git status", "python -m pytest"):
        assert hook.decide(command, repo) is None, command
