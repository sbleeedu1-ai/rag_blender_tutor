"""계획 진행 규칙 훅(.claude/hooks/check_plan_steps.py, HISTORY [550]). 진행 기록은 지어낸 글이고, 답 글은 2026-11-20 실제 실수 원문이다."""

import importlib.util
import json
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
spec = importlib.util.spec_from_file_location("check_plan_steps", HOOKS / "check_plan_steps.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

RULES = "> **이 계획을 따라 일할 때 반드시 먼저 읽는다**\n> 1. 시작할 때 체크리스트\n"


def plan(review="", now="### 지금: 차례 2번 바이트 점검(묶음 1)\n\n- [ ] (사용자) 승인\n- [ ] 실행\n- [ ] 되짚기: 통과 규칙에 대어 판정\n- 끝 조건: 15답\n- 결과가 들어갈 곳: 차례 3번\n"):
    return f"{RULES}\n(11-20 Astra 검토 뒤 주 세션 고침, [544])\n## 0. 진행 기록\n\n{review}\n{now}\n# 7. 전체 계획\n\n## 1. 결론\n- [ ] 계획 본문의 체크 줄은 진행 기록이 아니다\n"


OPEN_REVIEW = "### 되짚기: 11-20\n\n- [ ] **검색 관문 ④:** 문턱 뜻을 판정하지 않았다\n- [x] 고친 것\n- [ ] (사용자) 물음 2번\n"
ASK = {"recap": "…", "ask": "차례 2번 바이트 점검(약 $0.04)을 돌릴까요?"}  # 2026-11-20 실제 wrap_up 물음


def test_되짚기에_안_된_줄이_남았는데_사용자에게_물으면_거부하고_그_줄을_돌려준다():
    reason = hook.pre_decision("mcp__ccd_turn__wrap_up", ASK, plan(OPEN_REVIEW))
    assert reason and "검색 관문 ④" in reason and "(사용자) 물음 2번" not in reason
    assert hook.pre_decision("AskUserQuestion", {}, plan(OPEN_REVIEW))


def test_사용자_답을_기다리는_줄만_남았거나_묻지_않으면_통과():
    only_user = "### 되짚기: 11-20\n\n- [x] 고친 것\n- [ ] (사용자) 물음 2번\n"
    assert hook.pre_decision("mcp__ccd_turn__wrap_up", ASK, plan(only_user)) is None
    assert hook.pre_decision("mcp__ccd_turn__wrap_up", {"recap": "…"}, plan(OPEN_REVIEW)) is None


def test_지금_절에_체크리스트가_없으면_에이전트와_유료_실행을_거부한다():
    bare = plan(now="### 지금: 차례 2번\n\n바이트 점검을 한다.\n")
    reason = hook.pre_decision("Agent", {"prompt": "…"}, bare)
    assert reason and "체크 줄" in reason and "끝 조건" in reason and "결과가 들어갈 곳" in reason
    assert hook.pre_decision("Bash", {"command": ".venv/bin/python run.py --yes"}, bare)
    assert hook.pre_decision("Agent", {"prompt": "…"}, plan(now="")) is not None
    assert hook.pre_decision("Agent", {"prompt": "…"}, plan()) is None
    assert hook.pre_decision("Bash", {"command": "git status"}, bare) is None


def test_계획_이름표만_쓴_지난_실수는_막힌다():
    # 2026-11-20 실제 답 원문("1-2"를 차례 없이 씀, 사용자 "분류를 똑바로 쳐 말해야지")
    assert hook.bare_labels("**여쭤볼 것 하나:** 1-2 바이트 점검을 돌려도 될까요?") == ["1-2"]
    assert hook.bare_labels("**6번(1-6):** 앞으로 할 일의 순서가") == ["1-6"]


def test_차례_번호와_함께_쓰거나_인용_날짜_범위_절_번호는_통과():
    for ok in ["차례 2번: 바이트 점검(묶음 1, 이름표 1-2)", "달력에는 \"1-1 → 1-2·1-3\"이라 적혀 있습니다",
               "11-20에 물을 것", "물음 1-3번", "Q04-1", "4-2절 달력", "`1-6` 표", "문항 1-23번",
               "1-3번을 먼저 합니다", "약 1-2분", "5회 중 3-4회", "위 5-6개", "2-3줄", "하루 1-2칸"]:
        assert hook.bare_labels(ok) == [], ok


def test_계획을_안_읽고_권하면_막고_읽었으면_통과():
    said = {"type": "text", "text": "그래서 이렇게 하자고 권합니다. 그 25개만 벡터로 바꿔 합친 순위를 셉니다(약 $0.003)."}  # 2026-11-20 실제 원문
    assert any("계획 문서" in p for p in hook.stop_problems([said]))
    read = {"type": "tool_use", "name": "Bash", "input": {"command": "sed -n 180,192p results/x/7_전체계획.md"}}
    assert not any("계획 문서" in p for p in hook.stop_problems([read, said]))


def test_계획_문서가_없으면_아무것도_안_한다(tmp_path):
    missing = tmp_path / "없음.md"
    assert hook.run("pre", {"session_id": hook.PLAN_SESSION, "tool_name": "AskUserQuestion", "tool_input": {}}, missing) is None
    assert hook.run("prompt", {"session_id": hook.PLAN_SESSION}, missing) is None


def test_사용자_메시지마다_규칙_상자와_안_된_줄을_넣는다(tmp_path):
    path = tmp_path / "7_전체계획.md"
    path.write_text(plan(OPEN_REVIEW), encoding="utf-8")
    context = hook.run("prompt", {"session_id": hook.PLAN_SESSION}, path)["hookSpecificOutput"]["additionalContext"]
    assert "반드시 먼저 읽는다" in context and "검색 관문 ④" in context and "(사용자) 승인" in context
    assert "계획 본문의 체크 줄" not in context


def test_답_검사는_기록의_특수_줄바꿈에_깨지지_않는다(tmp_path):
    entries = [{"type": "user", "origin": {"kind": "human"}, "message": {"content": "해"}},
               {"type": "user", "message": {"content": [{"type": "tool_result", "content": "웹 글"}]}},
               {"type": "assistant", "message": {"content": [{"type": "text", "text": "1-2 바이트 점검을 돌려도 될까요?"}]}}]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")
    assert any("1-2" in p for p in hook.stop_problems(hook.turn_blocks(path)))


def test_답_글로_묻는_것도_되짚기가_남았으면_막는다():
    said = [{"type": "text", "text": "**차례 2번 바이트 점검을 돌려도 될까요?** 비용은 약 $0.04입니다."}]  # 2026-11-20 실제 원문
    assert any("되짚기" in p for p in hook.stop_problems(said, plan(OPEN_REVIEW)))
    assert not any("되짚기" in p for p in hook.stop_problems(said, plan()))


def test_Astra_검토를_반영한_최종_계획이_아니면_걸지_않는다(tmp_path):
    # 사용자 "지금 만드는 훅은 우리 아스트라 검토 이후 최종 완성된 계획에만 쓰여야 한다"(11-20)
    path = tmp_path / "7_전체계획.md"
    path.write_text(plan(OPEN_REVIEW).replace("(11-20 Astra 검토 뒤 주 세션 고침, [544])", ""), encoding="utf-8")
    assert hook.run("pre", {"session_id": hook.PLAN_SESSION, "tool_name": "AskUserQuestion", "tool_input": {}}, path) is None
    path.write_text(plan(OPEN_REVIEW), encoding="utf-8")
    assert hook.run("pre", {"session_id": hook.PLAN_SESSION, "tool_name": "AskUserQuestion", "tool_input": {}}, path) is not None


def test_지금_절에_되짚기_줄이_없으면_시작을_막는다():
    no_review = plan(now="### 지금: 차례 2번\n\n- [ ] 실행\n- 끝 조건: 15답\n- 결과가 들어갈 곳: 차례 3번\n")
    assert "되짚기" in (hook.pre_decision("Agent", {"prompt": "…"}, no_review) or "")


def test_wrap_up_물음을_낸_차례도_Stop에서_본다():
    blocks = [{"type": "tool_use", "name": "mcp__ccd_turn__wrap_up", "input": ASK}]
    assert any("되짚기" in p for p in hook.stop_problems(blocks, plan(OPEN_REVIEW)))


def test_계획_전용_세션이_아니면_걸지_않는다(tmp_path):
    # 사용자 "그냥 계획 전용 세션을 따로 만들어서 그거 전용으로 걸어놓는게 안전하겠다"(11-20): 다른 세션의 질문·권유까지 막았다
    path = tmp_path / "7_전체계획.md"
    path.write_text(plan(OPEN_REVIEW), encoding="utf-8")
    ask = {"tool_name": "AskUserQuestion", "tool_input": {}}
    assert hook.run("pre", {**ask, "session_id": "다른-세션"}, path) is None
    assert hook.run("pre", ask, path) is None
    assert hook.run("pre", {**ask, "session_id": hook.PLAN_SESSION}, path) is not None
