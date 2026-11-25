"""세션 기록을 읽는 훅 넷이 글 속 특수 줄바꿈(U+2028)에 깨지지 않는지 본다(HISTORY [550]).

2026-11-20 세션 기록에 웹에서 읽은 글을 담은 줄이 들어오며 U+2028이 섞였다. JSON 줄 안의 그 글자는 줄 끝이 아닌데
str.splitlines()가 거기서 줄을 잘라 json.loads가 깨졌고, 답 검사 훅(Stop)은 그 뒤 차례마다 조용히 실패해 아무것도 막지 못했다.
"""

import importlib.util
import json
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path, entries, name="t.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    assert " " in path.read_text(encoding="utf-8")  # ensure_ascii=False라 글자가 그대로 들어간다(실제 기록과 같음)
    return path


HUMAN = {"type": "user", "origin": {"kind": "human"}, "timestamp": "2026-11-20T01:00:00Z", "message": {"role": "user", "content": "버그 고쳐"}}
WEB = {"type": "user", "timestamp": "2026-11-20T01:00:01Z", "message": {"role": "user", "content": [{"type": "tool_result", "content": "웹 글 다음 줄"}]}}


def _said(text):
    return {"type": "assistant", "timestamp": "2026-11-20T01:00:02Z", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def test_답_검사_훅은_특수_줄바꿈이_든_기록에서도_규칙을_건다(tmp_path):
    path = _write(tmp_path, [HUMAN, WEB, _said("이 판은 8/18로 채택입니다.")])
    hits = _load("check_reply").turn_problems(path)
    assert any("advisor" in h for h in hits)


def test_컴팩트_뒤_사용자_원문_복원은_특수_줄바꿈에_깨지지_않는다(tmp_path):
    path = _write(tmp_path, [HUMAN, WEB, {**HUMAN, "message": {"role": "user", "content": "줄 바꿈 든 말"}}])
    said = [text for _, text in _load("restore_after_compact").human_messages(path)]
    assert said == ["버그 고쳐", "줄 바꿈 든 말"]


def test_컴팩트_뒤_약속_줄_복원은_특수_줄바꿈에_깨지지_않는다(tmp_path):
    path = _write(tmp_path, [HUMAN, WEB, _said("고친 뒤 보고하겠습니다.")])
    _load("restore_promises_after_compact").promise_lines(path)


def test_실험_전_확인_훅의_기록_모으기는_특수_줄바꿈에_깨지지_않는다(tmp_path):
    agent = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Agent", "input": {"prompt": "목표 검토"}}]}}
    path = _write(tmp_path, [HUMAN, WEB, agent])
    prompts, _ = _load("remind_goal_review").session_calls(str(path))
    assert any("검토" in p for p in prompts)
