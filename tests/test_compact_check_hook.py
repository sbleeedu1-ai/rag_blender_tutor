"""기록 누락 확인 훅(.claude/hooks/check_records_before_compact.py, HISTORY [193]): 임시 저장소로 본다."""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
spec = importlib.util.spec_from_file_location("check_records_before_compact", HOOKS / "check_records_before_compact.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

NOW = datetime(2026, 11, 6, 10, 0, 0)


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@e", "-c", "user.name=t", *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """기록을 다 남기고 커밋한 저장소. results/는 git에서 뺀다."""
    mine = tmp_path / "mine"
    (mine / "docs").mkdir(parents=True)
    (mine / "results" / "20261106" / "092251_flow_walk").mkdir(parents=True)
    (mine / ".gitignore").write_text("results/\n", encoding="utf-8")
    (mine / "docs" / "experiment.md").write_text("결과는 `results/20261106/092251_flow_walk/`\n", encoding="utf-8")
    (mine / "HANDOFF.md").write_text("# 인수인계\n\n마지막 갱신: 2026-11-06 오전 · Claude\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(mine)], check=True)
    git(mine, "add", ".")
    git(mine, "commit", "-q", "-m", "처음")
    return mine


def test_기록을_다_남겼으면_막지_않는다(repo):
    assert hook.missing_records(repo, NOW) == []
    assert hook.decide(repo, NOW) is None


def test_오늘_결과_폴더가_실험_기록에_없으면_알린다(repo):
    (repo / "results" / "20261106" / "101010_new_run").mkdir()
    assert any("101010_new_run" in item for item in hook.missing_records(repo, NOW))


def test_어제_결과_폴더는_보지_않는다(repo):
    (repo / "results" / "20261105" / "225533_old_run").mkdir(parents=True)
    assert hook.missing_records(repo, NOW) == []


def test_커밋하지_않은_파일이_있으면_알린다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    assert any("새파일.md" in item for item in hook.missing_records(repo, NOW))


def test_HANDOFF_날짜가_오늘이_아니면_알린다(repo):
    (repo / "HANDOFF.md").write_text("마지막 갱신: 2026-11-05 밤\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "옛 날짜")
    assert any("HANDOFF" in item for item in hook.missing_records(repo, NOW))


def test_한_번_막고_10분_안에_다시_하면_통과한다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    message = hook.decide(repo, NOW)
    assert "새파일.md" in message and "10분 안에" in message
    assert hook.decide(repo, NOW + timedelta(minutes=9)) is None


def test_통과한_뒤에는_다시_막는다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    assert hook.decide(repo, NOW) is not None
    assert hook.decide(repo, NOW + timedelta(minutes=1)) is None
    assert hook.decide(repo, NOW + timedelta(minutes=2)) is not None


def test_10분이_지나면_다시_막는다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    assert hook.decide(repo, NOW) is not None
    assert hook.decide(repo, NOW + timedelta(minutes=11)) is not None


def test_하위_폴더에서_불러도_저장소_맨_위를_본다(repo):
    below = repo / "docs"
    assert hook.decide(below, NOW) is None  # HANDOFF가 있는데 없다고 막으면 안 된다
    (repo / "results" / "20261106" / "101010_new_run").mkdir()
    assert "101010_new_run" in hook.decide(below, NOW)  # 오늘 결과 점검도 빠지면 안 된다


def run_hook(repo, trigger):
    payload = json.dumps({"hook_event_name": "PreCompact", "trigger": trigger, "cwd": str(repo)})
    return subprocess.run([sys.executable, str(HOOKS / "check_records_before_compact.py")], input=payload,
                          capture_output=True, text=True, encoding="utf-8")


def test_직접_입력한_컴팩트를_종료_코드_2로_막고_이유를_보인다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    done = run_hook(repo, "manual")
    assert done.returncode == 2
    assert "새파일.md" in done.stderr


def test_자동_압축은_막지_않는다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    assert run_hook(repo, "auto").returncode == 0


def test_설정이_직접_입력과_자동_압축_모두에_훅을_건다():
    settings = json.loads((HOOKS.parent / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreCompact"]
    assert [entry["matcher"] for entry in entries] == ["manual|auto"]
    assert "check_records_before_compact.py" in entries[0]["hooks"][0]["command"]
    assert "Stop" not in settings["hooks"]


def test_자동_압축은_빠진_기록을_요약_지시문으로_넘긴다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    done = run_hook(repo, "auto")
    assert done.returncode == 0
    assert "새파일.md" in done.stdout
    assert "요약" in done.stdout


def test_자동_압축은_기록이_다_있으면_아무것도_안_넘긴다(repo):
    (repo / "HANDOFF.md").write_text(f"마지막 갱신: {datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "오늘 날짜")
    (repo / "docs" / "experiment.md").write_text(f"results/{datetime.now():%Y%m%d}/\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "기록")
    done = run_hook(repo, "auto")
    assert done.returncode == 0
    assert done.stdout.strip() == ""


def run_notice(repo, **payload):
    return subprocess.run([sys.executable, str(HOOKS / "notice_after_clear.py")], input=json.dumps({"cwd": str(repo), **payload}),
                          capture_output=True, text=True, encoding="utf-8")


def end(repo, reason="clear"):
    return run_notice(repo, hook_event_name="SessionEnd", reason=reason, transcript_path="C:/기록/세션.jsonl")


def start(repo, source="clear"):
    return run_notice(repo, hook_event_name="SessionStart", source=source)


def test_기록이_빠진_채_클리어하면_새_세션에_알린다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    assert end(repo).returncode == 0
    done = start(repo)
    assert done.returncode == 0
    assert "새파일.md" in done.stdout
    assert "C:/기록/세션.jsonl" in done.stdout


def test_알림은_한_번만_한다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    end(repo)
    assert "새파일.md" in start(repo).stdout
    assert start(repo).stdout.strip() == ""


def test_세션을_끝낸_뒤_새로_열어도_알린다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    end(repo, "prompt_input_exit")
    assert "새파일.md" in start(repo, "startup").stdout


def test_빠진_기록이_없으면_알리지_않는다(repo):
    (repo / "HANDOFF.md").write_text(f"마지막 갱신: {datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "오늘 날짜")
    end(repo)
    assert start(repo).stdout.strip() == ""


def test_다음_종료에_기록이_채워졌으면_옛_알림을_지운다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    end(repo)
    (repo / "HANDOFF.md").write_text(f"마지막 갱신: {datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "채움")
    end(repo)
    assert start(repo).stdout.strip() == ""


def test_종료_알림은_git_상태에_안_나타난다(repo):
    (repo / "새파일.md").write_text("x", encoding="utf-8")
    end(repo)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8").stdout
    assert status.strip() == "?? 새파일.md"


def test_설정이_세션_끝과_시작에_알림_훅을_건다():
    settings = json.loads((HOOKS.parent / "settings.json").read_text(encoding="utf-8"))
    assert "notice_after_clear.py" in settings["hooks"]["SessionEnd"][0]["hooks"][0]["command"]
    begin = settings["hooks"]["SessionStart"][0]
    assert begin["matcher"] == "startup|clear"
    assert "notice_after_clear.py" in begin["hooks"][0]["command"]
