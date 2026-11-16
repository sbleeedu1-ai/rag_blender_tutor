"""대화를 압축한 직후, Claude가 사용자에게 한 약속 줄("…하겠습니다", "…보여 드립니다")을 다시 보여 주는 훅(SessionStart, matcher compact).

- 왜: 압축 요약이 약속을 빼먹어, 압축 뒤 약속한 견주기 표("3. 세 방법과 섞은 방법의 잡은 수와 잘못 바꾼 수를 한 표로 보여 드립니다.",
  2026-11-16 11:57)를 빠뜨렸다(HISTORY [361] 회고, [365]).
- 사용자 원문 훅(restore_after_compact.py)과 따로 둔다. additionalContext는 훅마다 따로 10,000자로 재므로(공식 문서 hooks
  "Claude Code measures each string on its own, even when several hooks run for the same event") 사용자 원문 8,000자 몫을 줄이지 않는다.
- 범위: 끝에서 두 번째 압축 요약(isCompactSummary) 뒤부터 끝까지. SessionStart 때 새 요약 줄이 이미 적혔든 아니든 직전 구간을 덮는다.
  압축은 최근 대화를 남기므로 빠지기 쉬운 것은 구간의 오래된 쪽이다.
- 고르는 줄: 본 세션(isSidechain 아님) assistant의 text 조각에서 PROMISE가 든 줄. 생각 블록·도구 결과는 보지 않는다.
  holdout·홀드아웃·봉인이 든 줄은 뺀다(AGENTS.md). 2026-11-16 기록으로 잼: 압축 구간마다 최대 45줄 4,859자, 걸린 줄은 거의 모두 약속·계획 줄.
- 넘치면 오래된 줄부터 빼고 "N줄 중 K줄"을 적는다(조용히 버리지 않는다). 한 줄은 300자에서 자른다.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

LIMIT = 9500  # additionalContext 10,000자 한도 안, 머리말 포함 전체 길이
LINE_CHARS = 300
PROMISE = re.compile(r"겠습니다|드립니다|드릴게요|할게요")
EXCLUDED_WORDS = ("holdout", "홀드아웃", "봉인")
HEADER = ("압축 전 Claude가 사용자에게 한 약속·계획 줄(시각 포함, 직전 압축 구간). 다음 일의 기준·체크리스트를 쓰기 전에 하나씩 대조해, "
          "지킬 것은 옮기고 버릴 것은 까닭과 함께 사용자에게 알린다.")


def _local_time(stamp: str) -> str:
    if not stamp:
        return "시각 없음"
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")


def promise_lines(transcript: Path) -> list[tuple[str, str]]:
    """끝에서 두 번째 압축 요약 뒤의 약속 줄을 (시각, 줄) 차례대로."""
    complete = transcript.read_text(encoding="utf-8", errors="replace").rpartition("\n")[0] + "\n"
    segments: list[list[tuple[str, str]]] = [[]]
    for line in complete.splitlines():
        if '"isCompactSummary"' not in line and '"assistant"' not in line:
            continue
        entry = json.loads(line)
        if entry.get("isCompactSummary"):
            segments.append([])
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        parts = [content] if isinstance(content, str) else [
            p.get("text", "") for p in content or [] if isinstance(p, dict) and p.get("type") == "text"]
        for row in "\n".join(parts).splitlines():
            row = row.strip()
            if PROMISE.search(row) and not any(word in row.lower() for word in EXCLUDED_WORDS):
                segments[-1].append((entry.get("timestamp", ""), row[:LINE_CHARS]))
    return [row for segment in segments[-2:] for row in segment]


def context(transcript: Path) -> str:
    found = [f"[{_local_time(stamp)}] {text}" for stamp, text in promise_lines(transcript)]
    if not found:
        return ""
    kept = list(found)

    def render() -> str:
        count = f"{len(found)}줄 중 최근 {len(kept)}줄(넘쳐서 오래된 것을 뺌)" if len(kept) < len(found) else f"{len(found)}줄"
        return f"{HEADER}\n{count}, 오래된 것부터.\n" + "\n".join(kept)

    while kept and len(render()) > LIMIT:
        kept.pop(0)
    return render()


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    text = context(Path(payload["transcript_path"]))
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
