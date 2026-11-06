"""실험 절차 상기 훅(.claude/hooks/remind_goal_review.py, HISTORY [212]·[213])."""

import importlib.util
import json
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "remind_goal_review.py"
spec = importlib.util.spec_from_file_location("remind_goal_review", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

RUN = "python data/eval/state_generic/flow_run.py"
TITLE = "[E2] 이번 시험"
OLD = "### [E2] 옛 시험\n- [x] 결과: 끝\n\n"
AFTER = "- [x] 결과: 끝\n- [x] 목적 다시 보기: 답\n- [x] 실험 점검: 함\n- [x] 결과를 본 뒤 바꾼 것: 없음\n- [x] 넘어간 것: 표\n- [x] 실행 뒤 독립 검토: 함\n"
OPEN = f"### {TITLE}\n- [x] 목적: 말\n- [x] 목표 검토: 통과면 목록이 줄고 실패면 그대로\n"
ASKED = [f"{TITLE} 목표 검토를 해 주세요"]


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
def test_시험이_아닌_명령은_기록을_읽지_않는다(command, tmp_path):
    assert hook.decide(command, "C:/WORK/rag_blender_tutor", tmp_path / "없음.md", str(tmp_path / "없음.jsonl")) is None


def test_폴더_안에서_이름만_적어도_알아본다():
    assert hook.starts_experiment("python flow_run.py", "C:/WORK/rag_blender_tutor/data/eval/state_generic")
    assert not hook.starts_experiment("python flow_run.py", "C:/WORK/rag_blender_tutor")


@pytest.mark.parametrize("record, prompts", [
    (OLD + OPEN, ASKED),  # 옛 절은 목표 검토 칸이 없어 보지 않는다
    (f"### [E2] 작은 확인\n- [x] 목표 검토: {hook._NOT_FOR_VERDICT}\n", []),
    (f"### {TITLE} 앞\n- [x] 목표 검토: {hook._NOT_FOR_VERDICT}\n\n" + OPEN, ASKED),
    (f"### [E2] 앞 시험\n- [x] 목표 검토: 답\n{AFTER}\n" + OPEN, ASKED + ["[E2] 앞 시험의 실행 뒤 독립 검토"]),
])
def test_절차를_밟았으면_통과한다(record, prompts):
    assert hook.missing_step(record, prompts) is None


@pytest.mark.parametrize("record, prompts, word", [
    ("기록 없음\n", ASKED, "실험 절이 없"),
    ("### [E2] 칸 없음\n- [x] 목적: 말\n", ASKED, "칸이 없"),
    ("### [E2] 빈칸\n- [ ] 목표 검토: \n", ASKED, "칸이 없"),
    (OLD + "### [E2] 칸 없는 새 시험\n- [x] 목적: 말\n", ASKED, "칸이 없"),
    (OPEN, [], "호출이 없"),
    (OPEN, [f"{TITLE} 설계를 봐 주세요"], "호출이 없"),  # 칸 이름이 프롬프트에 없음
    (OPEN, ["[E2] 다른 시험 목표 검토"], "호출이 없"),  # 절 제목이 다름
    (f"### [E2] 끝난 시험\n- [x] 목표 검토: 답\n{AFTER}", ["[E2] 끝난 시험 실행 뒤 독립 검토"], "새 절"),
    ("### [E2] 앞 시험\n- [x] 목표 검토: 답\n- [x] 결과: 끝\n\n" + OPEN, ASKED, "목적 다시 보기"),
    (f"### [E2] 앞 시험\n- [x] 목표 검토: 답\n{AFTER}\n" + OPEN, ASKED, "실행 뒤 독립 검토"),
])
def test_빠진_절차를_알려_준다(record, prompts, word):
    assert word in hook.missing_step(record, prompts)


def _log(path, *rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _call(name, prompt):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": {"prompt": prompt}}]}}


def test_세션_기록에서_하위_에이전트_프롬프트만_모은다(tmp_path):
    _log(tmp_path / "지난.jsonl", _call("Agent", "지난 세션 호출"))
    _log(tmp_path / "이번.jsonl", _call("Agent", "이번 세션 호출"), _call("Read", "Agent 아님"), {"type": "user", "message": {"content": "\"Agent\"라는 글자"}})
    with (tmp_path / "이번.jsonl").open("a", encoding="utf-8") as log:
        log.write('{"type": "assistant", "덜 적힌 "Agent" 줄')
    assert sorted(hook.agent_prompts(str(tmp_path / "이번.jsonl"))) == ["이번 세션 호출", "지난 세션 호출"]


def test_막을_때는_묻지_않고_까닭을_알린다(tmp_path):
    record = tmp_path / "experiment.md"
    record.write_text(OPEN, encoding="utf-8")
    _log(tmp_path / "세션.jsonl", _call("Read", "없음"))
    answer = hook.decide(RUN, ".", record, str(tmp_path / "세션.jsonl"))
    assert answer["permissionDecision"] == "deny"
    assert "최종 답" in answer["permissionDecisionReason"]

    _log(tmp_path / "세션.jsonl", _call("Agent", ASKED[0]))
    assert hook.decide(RUN, ".", record, str(tmp_path / "세션.jsonl")) is None
