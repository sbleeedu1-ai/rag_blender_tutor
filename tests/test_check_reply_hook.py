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


# 11-16 밤 실제 실수 둘([392]). 글은 실제 답 줄을 옮겼고, 도구 호출은 그 차례의 실제 호출 가운데 이 규칙이 보는 것만 옮겼다.
NO_SEARCH_1 = "1. **목록이 못 잡는 72자리의 꼴.** 권하는 안은 D입니다."  # 20:23 차례(실제 호출: 목록 파일을 읽은 python -c, 기록 읽기 없음)
NO_SEARCH_1_TOOLS = [("Bash", {"command": ".venv/bin/python -c \"import json;d=json.load(open('data/menu_names/common_ko.json'))\""})]
NO_SEARCH_2 = "**권하는 길**\n- 흔들림 자체를 줄이는 방법도 확인해 볼 만합니다. 예를 들어 모델의 무작위성 설정(temperature)을 낮추는 것입니다."  # 23:5x 차례
NO_SEARCH_2_WRITES = [("Bash", {"command": "cat >> HISTORY.md <<'EOF'\n...\nEOF\ngit add HISTORY.md .scratch/mvp-roundtrip/spec.md && git commit -q -m x && git log --oneline -1"})]


def _turn(tmp_path, reply, tools=()):
    human = {"type": "user", "origin": {"kind": "human"}, "message": {"content": "질문"}}
    calls = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": n, "input": i}]}} for n, i in tools]
    text = {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}}
    return _transcript(tmp_path, [human, *calls, text])


def test_기록을_안_찾고_제안하면_막힌다(tmp_path):
    for reply, tools in ((NO_SEARCH_1, NO_SEARCH_1_TOOLS), (NO_SEARCH_2, NO_SEARCH_2_WRITES)):
        hits = check_reply.turn_problems(_turn(tmp_path, reply, tools))
        assert any("기록을 찾지 않았다" in h for h in hits), reply


def test_한계_다른_주제로_기록을_읽었으면_통과한다(tmp_path):
    other = [("Bash", {"command": "sed -n '/^### \\[342\\]/,/^### \\[343\\]/p' HISTORY.md"})]  # temperature 차례에 실제로 있던 읽기
    assert not any("기록을 찾지 않았다" in h for h in check_reply.turn_problems(_turn(tmp_path, NO_SEARCH_2, NO_SEARCH_2_WRITES + other)))


def test_지난_실수를_말하는_제안은_권유가_아니다(tmp_path):
    assert check_reply.turn_problems(_turn(tmp_path, "오늘만 해도 기록을 안 찾고 제안한 게 두 번입니다.")) == []


def test_그_차례에_기록을_찾았으면_통과(tmp_path):
    for tools in ([("Bash", {"command": "grep -n temperature HISTORY.md"})],
                  [("Grep", {"pattern": "temp", "path": "docs/experiment.md"})],
                  [("Read", {"file_path": "/x/HISTORY.md"})]):
        assert not any("기록을 찾지 않았다" in h for h in check_reply.turn_problems(_turn(tmp_path, NO_SEARCH_2, tools)))


def test_제안이_없으면_기록_검사를_안_한다(tmp_path):
    assert check_reply.turn_problems(_turn(tmp_path, "시험이 끝났습니다. 결과는 13.0입니다.")) == []


# 2026-11-19 실제 실수 둘([482]). advisor를 부르지 않은 차례의 답 줄을 그대로 옮겼다.
NO_ADVISOR_1 = "**결론: 03 결과만으로는 C를 새 판에 넣을지 정하지 못했습니다. 그래서 이것부터 정하고, 04는 그다음에 돌립니다.**"  # 01:06 차례
NO_ADVISOR_2 = "그래서 순서는 이렇게 되어야 합니다."  # 01:05 차례
ADVISOR_RESULT = {"type": "assistant", "message": {"content": [{"type": "advisor_tool_result", "content": "..."}]}}


def test_advisor_없이_결론을_내면_막힌다(tmp_path):
    for reply in (NO_ADVISOR_1, NO_ADVISOR_2):
        hits = check_reply.turn_problems(_turn(tmp_path, reply))
        assert any("advisor" in h and "[482]" in h for h in hits), reply


def test_그_차례에_advisor를_불렀으면_결론도_통과(tmp_path):
    human = {"type": "user", "origin": {"kind": "human"}, "message": {"content": "질문"}}
    text = {"type": "assistant", "message": {"content": [{"type": "text", "text": NO_ADVISOR_1}]}}
    assert not any("advisor" in h for h in check_reply.turn_problems(_transcript(tmp_path, [human, ADVISOR_RESULT, text])))


def test_advisor_결과가_앞_차례에만_있으면_막힌다(tmp_path):
    human = {"type": "user", "origin": {"kind": "human"}, "message": {"content": "질문"}}
    text = {"type": "assistant", "message": {"content": [{"type": "text", "text": NO_ADVISOR_1}]}}
    assert any("advisor" in h for h in check_reply.turn_problems(_transcript(tmp_path, [ADVISOR_RESULT, human, text])))


def test_결론_없는_진행_말은_advisor를_안_본다(tmp_path):
    assert check_reply.turn_problems(_turn(tmp_path, "지금은 근거 자료를 모으는 중입니다.")) == []


def test_따옴표_속_세로막대가_있는_grep도_기록_찾기로_본다():
    # 2026-11-17 오후 6시 차례에서 그대로 옮긴 명령. 따옴표 속 |에서 쪼개져 grep과 HANDOFF.md가 갈려 헛막음이 났다([434])
    command = 'cd /Volumes/mac_ssd/proj/rag_blender_tutor && grep -n -E "③ Q38|④ 보고서|빠졌던 것" HANDOFF.md | head -3 | cut -c1-200'
    assert check_reply._reads_records("Bash", {"command": command})
    assert not check_reply._reads_records("Bash", {"command": 'echo "grep|x" >> HANDOFF.md'})
