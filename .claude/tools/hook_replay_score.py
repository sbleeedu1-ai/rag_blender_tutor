"""agent 훅 재판정을 정답과 맞대 센다(HISTORY [669]). 실행: .venv/bin/python -I .claude/tools/hook_replay_score.py <결과 폴더> [판정.tsv]"""
import csv
import json
import statistics
import sys
from pathlib import Path

D = Path(sys.argv[1])
want = json.loads((D / "정답.json").read_text(encoding="utf-8"))
label = {ts: "막음" for ts in want["막음"]} | {ts: "통과" for ts in want["통과"]}
rows = list(csv.DictReader((D / (sys.argv[2] if len(sys.argv) > 2 else "agent_판정.tsv")).open(encoding="utf-8"), delimiter="\t"))
got = {r["시각"]: r for r in rows}
print(f"판정 {len(got)}/{len(label)}, 빠짐 {sorted(set(label) - set(got))}")
miss = [ts for ts, v in label.items() if v == "막음" and got.get(ts, {}).get("판정") == "통과"]
false = [ts for ts, v in label.items() if v == "통과" and got.get(ts, {}).get("판정") == "막음"]
print(f"막아야 할 {sum(v == '막음' for v in label.values())} 중 놓침 {len(miss)}: {miss}")
print(f"통과여야 할 {sum(v == '통과' for v in label.values())} 중 헛막음 {len(false)}: {false}")
if rows and rows[0].get("걸린_ms"):
    for name, pick in (("판정 말 없는 보통 답 5", lambda ts: want["통과"].get(ts, "").startswith("보통 답")), ("나머지 17", lambda ts: not want["통과"].get(ts, "").startswith("보통 답"))):
        ms = [int(got[ts]["걸린_ms"]) for ts in label if ts in got and pick(ts)]
        print(f"{name}: 걸린 초 중앙값 {statistics.median(ms)/1000:.1f}, 최소 {min(ms)/1000:.1f}, 최대 {max(ms)/1000:.1f}")
