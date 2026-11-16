"""압축 뒤 약속 줄 복원 훅(.claude/hooks/restore_promises_after_compact.py, HISTORY [365]): 가짜 세션 기록으로 본다."""

import importlib.util
import json
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "restore_promises_after_compact.py"
spec = importlib.util.spec_from_file_location("restore_promises_after_compact", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def said(text, stamp="2026-11-16T02:57:00.000Z", sidechain=False, kind="text"):
    part = {"type": kind, kind: text} if kind != "thinking" else {"type": "thinking", "thinking": text}
    return {"type": "assistant", "timestamp": stamp, "isSidechain": sidechain, "message": {"content": [part]}}


SUMMARY = {"type": "user", "isCompactSummary": True, "timestamp": "2026-11-16T03:00:00.000Z", "message": {"content": "요약"}}


def transcript(tmp_path, *entries) -> Path:
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    return path


def test_promise_lines_are_picked(tmp_path):
    t = transcript(tmp_path, said("설명입니다.\n3. 세 방법과 섞은 방법을 한 표로 보여 드립니다.\n돌리기 전에 여쭙겠습니다."))
    out = hook.context(t)
    assert "섞은 방법을 한 표로 보여 드립니다" in out and "여쭙겠습니다" in out
    assert "설명입니다" not in out


def test_sidechain_thinking_and_excluded_words_are_dropped(tmp_path):
    t = transcript(tmp_path,
                   said("하위 에이전트가 하겠습니다", sidechain=True),
                   said("생각 속 하겠습니다", kind="thinking"),
                   said("홀드아웃을 열어 보겠습니다"),
                   said("표로 보여 드리겠습니다"))
    out = hook.context(t)
    assert "표로 보여 드리겠습니다" in out
    assert "하위 에이전트" not in out and "생각 속" not in out and "홀드아웃" not in out


def test_keeps_lines_since_the_compaction_before_last(tmp_path):
    """SessionStart 때 새 요약 줄이 이미 적혔든 아니든, 직전 압축 구간의 약속이 남는다."""
    old = said("아주 옛날에 하겠습니다", stamp="2026-11-16T01:00:00.000Z")
    mid = said("구간 안에서 하겠습니다", stamp="2026-11-16T02:00:00.000Z")
    before = dict(SUMMARY, timestamp="2026-11-16T01:30:00.000Z")
    with_new = hook.context(transcript(tmp_path, old, before, mid, SUMMARY))
    without_new = hook.context(transcript(tmp_path, old, before, mid))
    for out in (with_new, without_new):
        assert "구간 안에서 하겠습니다" in out
    assert "아주 옛날" not in with_new


def test_output_stays_under_limit_and_says_what_was_dropped(tmp_path):
    many = [said(f"{i}번 일을 " + "가" * 280 + " 하겠습니다", stamp=f"2026-11-16T02:{i % 60:02d}:00.000Z") for i in range(80)]
    out = hook.context(transcript(tmp_path, *many))
    assert len(out) <= hook.LIMIT
    assert "] 79번 일" in out and "] 0번 일을" not in out
    assert "80줄 중" in out


def test_no_promise_gives_empty(tmp_path):
    assert hook.context(transcript(tmp_path, said("설명만 있습니다."))) == ""
