"""목표 검토 상기 훅(.claude/hooks/remind_goal_review.py, HISTORY [212])."""

import importlib.util
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "remind_goal_review.py"
spec = importlib.util.spec_from_file_location("remind_goal_review", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

READY = "### [E2] 앞 시험\n- [x] 결과: 끝\n\n### [E2] 이번 시험\n- [x] 목적: 말\n- [x] 목표 검토: 통과면 목록이 줄고 실패면 그대로\n"
RUN = "python data/eval/state_generic/flow_run.py"


@pytest.mark.parametrize("command", [
    RUN,
    r".venv\Scripts\python data\eval\state_generic\flow_run.py",
    r'& ".venv\Scripts\python.exe" "data\eval\state_generic\flow_run.py"',
    "$env:STATE_WINDOW_X='-1920'; python -u data/eval/state_generic/case_run.py 1",
    "/c/WORK/rag_blender_tutor/.venv/Scripts/python.exe /c/WORK/rag_blender_tutor/data/eval/state_generic/drag_run.py",
    r'& $blender -b --python "data\eval\state_generic\dup_share_check.py"',
    "pytest; python data/eval/state_generic/sim_pref_run.py",
])
def test_시험을_띄우는_명령을_알아본다(command):
    assert hook.starts_experiment(command, "C:/WORK/rag_blender_tutor")


@pytest.mark.parametrize("command", [
    "git status",
    ".venv\\Scripts\\python -m pytest",
    "grep -n rmtree data/eval/state_generic/flow_run.py",
    "cat data/eval/state_generic/flow_run.py",
    "python data/eval/state_generic/value_master.py",
    "python scripts/other_run.py",
])
def test_시험이_아닌_명령은_보지_않는다(command):
    assert hook.decide(command, "C:/WORK/rag_blender_tutor", "### [E2] 칸 없음\n") is None


def test_폴더_안에서_이름만_적어도_알아본다():
    assert hook.starts_experiment("python flow_run.py", "C:/WORK/rag_blender_tutor/data/eval/state_generic")
    assert not hook.starts_experiment("python flow_run.py", "C:/WORK/rag_blender_tutor")


def test_기록이_있으면_통과한다():
    assert hook.decide(RUN, ".", READY) is None


@pytest.mark.parametrize("record, word", [
    ("### [E2] 칸 없음\n- [x] 목적: 말\n", "목표 검토"),
    ("### [E2] 빈칸\n- [ ] 목표 검토: \n", "목표 검토"),
    ("### [E2] 앞 시험\n- [x] 목표 검토: 답\n\n### [E2] 새 시험\n- [x] 목적: 말\n", "목표 검토"),
    ("### [E2] 끝난 시험\n- [x] 목표 검토: 답\n- [x] 결과: 끝\n", "새 절"),
    ("기록 없음\n", "실험 절"),
])
def test_기록이_없으면_묻지_않고_막으며_까닭을_알린다(record, word):
    answer = hook.decide(RUN, ".", record)
    assert answer["permissionDecision"] == "deny"
    assert word in answer["permissionDecisionReason"]
    assert "최종 답" in answer["permissionDecisionReason"]
