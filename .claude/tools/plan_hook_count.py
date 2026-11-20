"""계획 진행 규칙 훅(check_plan_steps.py)의 Stop 규칙을 한 세션 기록의 차례마다 돌려 몇 번 걸리는지 센다(HISTORY [550]).

돌리기: .venv/bin/python .claude/tools/plan_hook_count.py <세션 기록.jsonl> [시작 시각(UTC, 예 2026-11-20T01:15)]
네 칸 이름(배경·계획·기대하는 결과·나온 결론)이 wrap_up을 부른 차례의 글에 있는지도 함께 센다(넣을지 정하려고 잼, 훅은 안 봄).
진행 기록 규칙(①')은 지금 계획 문서 상태로 보므로 지난 차례에는 맞지 않아 세지 않는다.
"""

import importlib.util
import json
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "check_plan_steps.py"
FOUR = ("배경", "계획", "기대하는 결과", "나온 결론")


def main() -> None:
    spec = importlib.util.spec_from_file_location("hook", HOOK)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    since = sys.argv[2] if len(sys.argv) > 2 else ""
    entries = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").split("\n") if line.strip()]
    turns, current = [], None
    for e in entries:
        if hook._is_human(e):
            current = {"time": e.get("timestamp", ""), "blocks": []}
            turns.append(current)
        elif current is not None and e.get("type") == "assistant":
            content = (e.get("message") or {}).get("content")
            if isinstance(content, list):
                current["blocks"] += [c for c in content if isinstance(c, dict)]
    turns = [t for t in turns if t["time"] >= since]
    hit = wrapped = no_four = 0
    for t in turns:
        found = hook.stop_problems(t["blocks"])  # 계획 글을 안 넘겨 되짚기 규칙은 빠진다
        text = "\n".join(b.get("text", "") for b in t["blocks"] if b.get("type") == "text")
        if found:
            hit += 1
            print(t["time"][:19], "|", " / ".join(f[:40] for f in found))
        if any(b.get("type") == "tool_use" and b.get("name", "").endswith("wrap_up") for b in t["blocks"]):
            wrapped += 1
            no_four += not all(name in text for name in FOUR)
    print(f"Stop 규칙에 걸린 차례 {hit} / {len(turns)}")
    print(f"wrap_up을 부른 차례 {wrapped} 가운데 네 칸 이름이 다 없는 차례 {no_four}")


if __name__ == "__main__":
    main()
