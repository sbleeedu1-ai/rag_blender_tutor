"""남은 기간 전체 계획(7_전체계획.md)을 따라 일할 때, 맨 위 진행 규칙을 지키게 하는 훅. 이번 계획 전용(HISTORY [550]).

왜: 2026-11-20 사용자가 "시작할떄 해야할일 체크리스트 만들고 체크 해나가면서 하라고 그리고 체크가 다 됐으면 다시 되짚어봐서
빠진거 없는지 보고나서 … 배경 / 계획 / 기대하는 결과 / 나온 결론"을 계획 문서 맨 위에 적게 했다([548]).
적은 바로 뒤 Claude가 되짚기에서 찾은 빠진 것을 메우지 않고 다음 물음으로 넘어가 "이거봐이거봐 적어놔도 안지키네 너?",
"이거 훅으로 만들어 이번 계획 전용으로"([550]).

Astra 검토를 반영한 최종 계획에만 건다: 그 파일이 없거나(다른 PC·GitHub 검사) Astra 검토 표시(FINAL_MARK, [544])가 없으면 아무것도 하지 않는다. 11-30 발표 뒤에는 settings.json에서 이 훅 줄을 뺀다.
진행 기록의 꼴(기계가 읽음): "## 0. 진행 기록" 절 안의 "### 되짚기…" 절과 "### 지금: …" 절. 체크 줄은 "- [ ] "·"- [x] ",
사용자 답을 기다리는 줄은 "- [ ] (사용자) "로 쓴다. "지금:" 절에는 "- 끝 조건:"과 "- 결과가 들어갈 곳:" 줄을 둔다.

- prompt(UserPromptSubmit): 사용자 메시지마다 맨 위 규칙 상자와 아직 안 된 체크 줄을 Claude 문맥에 넣는다.
- pre(PreToolUse): ① 사용자에게 묻는 호출(wrap_up의 ask, AskUserQuestion) 전에 되짚기 절에 안 된 줄(사용자 답 기다림 빼고)이
  남았으면 거부한다. ② 단계 일의 신호(Agent 띄우기, `--yes`가 든 유료 실행) 전에 "지금:" 절에 체크 줄·끝 조건·결과가 들어갈 곳이
  없으면 거부한다. 거부는 까닭을 Claude에게 돌려주는 꼴만 쓴다(사용자 확인 창은 띄우지 않는다, AGENTS.md).
- stop(Stop): 그 차례 답 글에서 ①' 되짚기에 안 된 줄이 남았는데 "~까요?"로 묻는 것, ③ 계획의 이름표("1-2" 꼴)를 "차례" 없이 쓴 줄, ④ 무엇을 권하는데 그 차례에 계획 문서를 읽은
  호출이 없는 것을 막는다.
- 이 훅이 죽어도(오류) Stop은 조용히 지나간다(11-20 U+2028로 답 검사 훅이 그렇게 꺼져 있었다).
- 못 보는 것: 체크가 사실인지(체크만 하고 안 한 것), 네 칸 보고(배경/계획/기대하는 결과/나온 결론)를 썼는지조차(규칙 4는 글 규칙으로만 둠),
  되짚기 절을 아예 안 쓰고 넘어가는 것("지금:" 절에 되짚기 체크 줄을 두게 해 시작 때만 막음), 계획 규칙을 읽고도 어긴 권유,
  "--yes" 밖의 유료 실행. 진행 기록 꼴이 깨지면 ①은 통과하고 ②는 어느 줄이 없는지 알려 거부한다.
"""

import json
import re
import sys
from pathlib import Path

from hook_notice import with_notice

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "results" / "20261119" / "222431_실패분석" / "7_전체계획.md"
PLAN_NAME = "7_전체계획.md"
# 사용자 "지금 만드는 훅은 우리 아스트라 검토 이후 최종 완성된 계획에만 쓰여야 한다"(11-20): Astra 검토를 반영한 판에만 붙는 표시가 있어야 건다
FINAL_MARK = "Astra 검토 뒤 주 세션 고침, [544]"
# 계획 전용 세션에서만 건다. 같은 프로젝트의 다른 세션(스킬 분류 등)까지 막아서, 사용자 "그냥 계획 전용 세션을 따로 만들어서
# 그거 전용으로 걸어놓는게 안전하겠다. 계속 컴팩트 하면서 써야지 뭐"(11-20, [553]). 컴팩트해도 번호는 그대로이고,
# 새 대화를 열어 계획을 이어 가면 그 세션 번호(훅 입력의 session_id, 세션 기록 파일 이름)로 여기만 바꾼다.
# 사용자 메시지마다 규칙 상자가 문맥에 안 뜨면 이 번호가 어긋나 훅이 꺼진 것이다.
PLAN_SESSION = "e71573a4-b091-42bd-86c4-e6744df5da5d"
WHY = ("까닭(사용자 원문): \"체크가 다 됐으면 다시 되짚어봐서 빠진거 없는지 보고나서\", \"이거봐이거봐 적어놔도 안지키네 너?\" [548]·[550]")
RECOMMENDS = re.compile(r"권함|권하는|권합니다|권해|추천|제안")
PAST = re.compile(r"실수|잘못|했습니다|였습니다|했던|한 것|한 게|어긴|거두|거뒀")
LABEL = re.compile(r"(?<![\w.\-/\[])([1-8]-\d)(?![\d\-])(?!\s*(절|번|개|줄|회|분|초|칸|문항|차례|일|곳|명|%|만|배))")
# 뒤에 절 번호("4-2절")나 세는 말("1-3번", "약 1-2분")이 오면 범위로 보고 뺀다(전역 지침이 범위를 "1-3번" 꼴로 쓰게 함)
ASKS = re.compile(r"(까요|될까요|할까요|드릴까요)\?")  # 사용자에게 다음 일을 묻는 말
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|`[^`]*`")
NOT_LABEL_BEFORE = re.compile(r"(물음|Q|회|줄|칸|번호|\[)\s*$")


def _section(text: str, head: str, level: str) -> str:
    """머리글 head로 시작하는 절의 본문(같은 깊이 이상의 다음 머리글 전까지)."""
    start = text.find(head)
    if start < 0:
        return ""
    body = text[start + len(head):]
    stop = re.search(rf"\n{level} |\n# |\n## ", body)
    return body[: stop.start()] if stop else body


def progress(text: str) -> str:
    return _section(text, "## 0. 진행 기록", "##")


def open_review_items(text: str) -> list[str]:
    """되짚기 절들의 안 된 체크 줄(사용자 답을 기다리는 줄은 뺌)."""
    record = progress(text)
    items = []
    for part in record.split("\n### ")[1:]:
        if part.startswith("되짚기"):
            items += [line.strip() for line in part.splitlines()
                      if line.strip().startswith("- [ ]") and not line.strip().startswith("- [ ] (사용자)")]
    return items


def missing_now(text: str) -> list[str]:
    """"지금:" 절에 없는 것."""
    record = progress(text)
    now = next((part for part in record.split("\n### ")[1:] if part.startswith("지금:")), None)
    if now is None:
        return ["\"### 지금: …\" 절"]
    lacks = []
    if not re.search(r"^- \[[ x]\] ", now, re.M):
        lacks.append("체크 줄(- [ ] …)")
    if not re.search(r"^- \[[ x]\] .*되짚기", now, re.M):
        lacks.append("되짚기 체크 줄(- [ ] 되짚기: …)")
    for name in ("끝 조건:", "결과가 들어갈 곳:"):
        if f"- {name}" not in now:
            lacks.append(f"\"- {name}\" 줄")
    return lacks


def rule_box(text: str) -> str:
    return "\n".join(line for line in text.splitlines()[:20] if line.startswith(">"))


def asks_user(tool: str, args: dict) -> bool:
    return tool == "AskUserQuestion" or (tool.endswith("wrap_up") and bool((args.get("ask") or "").strip()))


def starts_step(tool: str, args: dict) -> bool:
    return tool in ("Agent", "Workflow") or (tool == "Bash" and " --yes" in (args.get("command") or ""))


def pre_decision(tool: str, args: dict, text: str) -> str | None:
    if asks_user(tool, args) and (items := open_review_items(text)):
        return ("사용자에게 묻기 전에 계획 문서 \"0. 진행 기록\"의 되짚기에서 안 된 줄을 먼저 메운다(혼자 할 수 없는 줄이면 \"- [ ] (사용자)\"로 고친다): "
                + " / ".join(items[:6]) + (" 등" if len(items) > 6 else "") + ". " + WHY)
    if starts_step(tool, args) and (lacks := missing_now(text)):
        return ("단계 일을 시작하기 전에 계획 문서 \"0. 진행 기록\"의 \"지금:\" 절에 체크리스트를 먼저 적는다. 없는 것: "
                + ", ".join(lacks) + ". " + WHY)
    return None


def bare_labels(reply: str) -> list[str]:
    found = []
    for line in reply.splitlines():
        line = QUOTED.sub("", line)  # 계획 글을 인용한 것(따옴표·백틱 안)은 보지 않는다
        if "차례" in line:
            continue
        for m in LABEL.finditer(line):
            if not NOT_LABEL_BEFORE.search(line[: m.start()]):
                found.append(m.group(1))
    return sorted(set(found))


def _is_human(entry: dict) -> bool:
    return (entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human"
            and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain")))


def turn_blocks(transcript: Path) -> list[dict]:
    """마지막 사람 메시지 뒤 Claude 메시지의 조각. split("\\n")로 나눈다(splitlines는 글 속 U+2028에서도 잘라 깨진다, [550])."""
    entries = [json.loads(line) for line in transcript.read_text(encoding="utf-8").split("\n") if line.strip()]
    start = max((i for i, e in enumerate(entries) if _is_human(e)), default=-1) + 1
    blocks = []
    for e in entries[start:]:
        content = (e.get("message") or {}).get("content") if e.get("type") == "assistant" else None
        if isinstance(content, list):
            blocks += [c for c in content if isinstance(c, dict)]
    return blocks


def stop_problems(blocks: list[dict], plan_text: str = "") -> list[str]:
    reply = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    found = []
    asked = ASKS.search(reply) or any(b.get("type") == "tool_use" and asks_user(b.get("name", ""), b.get("input") or {}) for b in blocks)
    if asked and (items := open_review_items(plan_text)):
        found.append("되짚기에서 안 된 줄이 남았는데 사용자에게 물었다. 그 줄을 먼저 메우고(혼자 할 수 없는 줄은 \"- [ ] (사용자)\"로 고침) 묻는다: "
                     + " / ".join(items[:6]) + ". " + WHY)
    if labels := bare_labels(reply):
        found.append(f"계획 이름표 {', '.join(labels)}를 \"차례\" 없이 썼다. \"차례 2번: 바이트 점검(묶음 1)\"처럼 차례 번호와 이름으로 쓴다. "
                     "까닭(사용자 원문): \"분류를 똑바로 쳐 말해야지 장난하니?\" [548]")
    recommends = any(RECOMMENDS.search(line) and not PAST.search(line) for line in reply.splitlines())
    read_plan = any(b.get("type") == "tool_use" and PLAN_NAME in json.dumps(b.get("input") or {}, ensure_ascii=False) for b in blocks)
    if recommends and not read_plan:
        found.append("무엇을 권하는데 이 차례에 계획 문서(7_전체계획.md)를 읽지 않았다. 계획에 이미 그 일의 규칙(통과·접기·차례)이 있는지 먼저 보고, "
                     "있으면 새 일을 권하지 않고 그 규칙대로 말한다. 까닭(사용자 원문): \"너 또 계획안에서 뭔가 하고 나서 순서 체크리스트 안정할래?\" [548]")
    return found


def run(mode: str, payload: dict, plan: Path = PLAN) -> dict | None:
    """훅 하나의 답(출력할 JSON). 계획 문서가 없거나 하위 에이전트면 None."""
    if payload.get("session_id") != PLAN_SESSION or not plan.exists() or payload.get("agent_id"):
        return None
    text = plan.read_text(encoding="utf-8")
    if FINAL_MARK not in text:  # Astra 검토 전 판·다른 계획에는 걸지 않는다
        return None
    if mode == "prompt":
        items = [line.strip() for line in progress(text).splitlines() if line.strip().startswith("- [ ]")]
        context = (f"[계획 진행 규칙, {PLAN_NAME} 맨 위]\n{rule_box(text)}\n\n[진행 기록에서 아직 안 된 줄]\n" + "\n".join(items or ["(없음)"]))
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}
    if mode == "pre":
        reason = pre_decision(payload.get("tool_name") or "", payload.get("tool_input") or {}, text)
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": reason}} if reason else None
    if mode == "stop" and not payload.get("stop_hook_active") and payload.get("transcript_path"):
        found = stop_problems(turn_blocks(Path(payload["transcript_path"])), text)
        return {"decision": "block", "reason": "답을 고쳐 다시 낸다(계획 진행 규칙): " + " / ".join(found)} if found else None
    return None


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    answer = run(sys.argv[1] if len(sys.argv) > 1 else "", payload)
    if answer:
        print(json.dumps(with_notice("check_plan_steps", payload, answer), ensure_ascii=False))


if __name__ == "__main__":
    main()
