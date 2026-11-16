"""답 검사 훅(.claude/hooks/check_reply.py, HISTORY [378]). 실제 지난 실수로 막히는지 본다."""

import importlib.util
import json
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))
spec = importlib.util.spec_from_file_location("check_reply", HOOKS / "check_reply.py")
check_reply = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_reply)

# 2026-11-16 밤 8시 요약에서 그대로 옮긴 줄(거부된 '곧' 꼴을 다시 권함)
PAST_MISTAKE = """**결정하실 것 2가지**
1. **목록이 못 잡는 72자리의 꼴.** 권하는 안은 D입니다.
   - 괄호 뒤에 조사나 따옴표가 오는 45자리는 "배경, 곧 월드(World)가"처럼 씁니다.
"""
# 같은 날 밤 답에서 그대로 옮긴 줄(㉮가 무엇인지 같은 줄에 없음)
BARE_SYMBOL = "- ① 괄호 뒤에 조사가 올 때만 ㉮ 꼴을 쓴다."


def test_지난_실수는_막힌다():
    hits = check_reply.problems(PAST_MISTAKE)
    assert any("곧" in h for h in hits)
    assert any("더 나은 방향은 없는거야?" in h and "[377]" in h for h in hits)  # 거부한 까닭(사용자 원문)을 함께 보인다
    assert any("㉮" in h for h in check_reply.problems(BARE_SYMBOL))


def test_기호_옆에_실제_꼴이_있으면_통과():
    assert check_reply.problems('꼬리 낱말은 ㉠ 꼴로 갑니다: "면 선택 모드(Face)" → "페이스(Face) 선택 모드"') == []


def test_거부한_꼴을_지금_제품_설명으로_말하면_통과():
    text = "권하는 답은 아래입니다.\n지금 제품은 \"면(페이스, Face)\"를 냅니다. 이 꼴은 거부된 꼴입니다."
    assert check_reply.problems(text) == []


def test_권하지_않는_답에서_인용은_통과():
    assert check_reply.problems("오늘 17:40에 \"옆면 개수, 곧 버텍스(Vertices)\"를 보여 드렸습니다.") == []


def test_권하는_답에_거부한_꼴이면_막힌다():
    text = "권하는 꼴은 이것입니다.\n\"옆면 개수(버텍스, Vertices)를\""
    assert check_reply.problems(text)


def test_거부한_꼴은_answer_forms_표에서_읽는다():
    patterns = check_reply.rejected_patterns()
    assert len(patterns) >= 3
    assert all(quote and history.startswith("[") for _, quote, history, _ in patterns)


def _transcript(tmp_path, entries):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries), encoding="utf-8")
    return path


def test_마지막_사람_메시지_뒤의_답_글만_본다(tmp_path):
    human = {"type": "user", "origin": {"kind": "human"}, "message": {"content": "질문"}}
    old = {"type": "assistant", "message": {"content": [{"type": "text", "text": "권함: 배경, 곧 월드(World)가"}]}}
    new = {"type": "assistant", "message": {"content": [{"type": "text", "text": "새 답"}]}}
    assert check_reply.turn_text(_transcript(tmp_path, [old, human, new])) == "새 답"
