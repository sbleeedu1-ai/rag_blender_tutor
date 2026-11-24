"""훅이 막거나 물을 때 사용자 화면에도 "어느 훅이, 어디서, 왜"를 띄운다.

사용자 원문(2026-11-24): "어떤 자리에서 뭐때문에 걸렸는지좀 미리 출력하고 이어서 하라고 … 맨날 왜이리 오래걸리나 보면
다 훅걸린건데 뭔지 몰라서 답답함". 막는 까닭(reason)은 Claude에게만 가므로, 공식 문서의 공통 칸
`systemMessage`("Warning message shown to the user", code.claude.com/docs/en/hooks JSON output 절)에 같은 까닭을 줄여 넣는다.
"""

SHOW = 300  # 화면에 띄우는 까닭 글자 수(길면 화면을 덮으므로 앞부분만)


def where(payload: dict) -> str:
    """막힌 자리: 도구 이름과 명령·파일 앞부분, Stop이면 답을 끝내려던 자리."""
    if payload.get("hook_event_name") == "Stop":
        return "답을 끝내려던 자리"
    tool = payload.get("tool_name") or "?"
    args = payload.get("tool_input") or {}
    target = args.get("command") or args.get("file_path") or args.get("description") or ""
    target = " ".join(str(target).split())
    return f"{tool} `{target[:60]}{'…' if len(target) > 60 else ''}`" if target else tool


def with_notice(hook: str, payload: dict, out: dict) -> dict:
    """훅의 출력 JSON에 systemMessage를 더해 돌려준다. 막지도 묻지도 않는 출력은 그대로."""
    spec = out.get("hookSpecificOutput") or {}
    decision = spec.get("permissionDecision") or out.get("decision")
    reason = spec.get("permissionDecisionReason") or out.get("reason") or ""
    if decision not in ("deny", "ask", "block"):
        return out
    verb = "물음" if decision == "ask" else "막음"
    short = " ".join(reason.split())
    short = short[:SHOW] + ("…" if len(short) > SHOW else "")
    return {**out, "systemMessage": f"[훅 {hook} {verb}] {where(payload)} — {short}"}
