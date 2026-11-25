"""훅이 막거나 물을 때 화면 알림(systemMessage)이 붙는지 본다(2026-11-24 사용자 "어떤 자리에서 뭐때문에 걸렸는지좀 미리 출력")."""

import json
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

from hook_notice import with_notice  # noqa: E402


def test_막은_도구_자리와_까닭을_띄운다():
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit -m 기록"}}
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "advisor 먼저"}}
    msg = with_notice("require_advisor", payload, out)["systemMessage"]
    assert msg == "[훅 require_advisor 막음] Bash `git commit -m 기록` — advisor 먼저"


def test_Stop_막음과_물음():
    stop = with_notice("check_reply", {"hook_event_name": "Stop"}, {"decision": "block", "reason": "규칙 4"})
    assert stop["systemMessage"] == "[훅 check_reply 막음] 답을 끝내려던 자리 — 규칙 4"
    ask = with_notice("ask_file_delete", {"tool_name": "Bash", "tool_input": {"command": "rm a"}},
                      {"hookSpecificOutput": {"permissionDecision": "ask", "permissionDecisionReason": "지움"}})
    assert ask["systemMessage"].startswith("[훅 ask_file_delete 물음]")


def test_막지_않는_출력은_그대로():
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "x"}}
    assert with_notice("check_plan_steps", {}, out) == out


def test_실제_훅이_화면_알림을_낸다():
    """deny_cut_output을 실제로 돌려 출력 JSON에 systemMessage가 있는지 본다."""
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git push origin x | tail -3"}}
    done = subprocess.run([sys.executable, str(HOOKS / "deny_cut_output.py")], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", check=True)
    out = json.loads(done.stdout)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["systemMessage"].startswith("[훅 deny_cut_output 막음] Bash `git push origin x | tail -3` — ")
