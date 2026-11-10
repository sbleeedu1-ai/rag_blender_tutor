"""대화를 압축한 직후, 사용자가 직접 친 최근 메시지 원문을 Claude에게 다시 보여 주는 훅(SessionStart, matcher compact).

- 압축 요약은 사용자 말을 줄이거나 바꿔 적을 수 있다. 그래서 세션 기록(transcript_path, JSONL)에서 원문을 꺼내 함께 넘긴다.
- 사람이 친 메시지만 고른다: 기록 줄의 `origin.kind`가 "human"인 user 줄. 도구 결과·작업 알림(<task-notification>)·
  하위 에이전트 보고(origin "peer")·스킬 본문(isMeta)·압축 요약(isCompactSummary)은 이 표시가 없다(세션 기록으로 확인).
- 마지막 30개, 합계 8,000자 이하(넘으면 오래된 것부터 뺀다). holdout·홀드아웃·봉인이 든 메시지는 뺀다(AGENTS.md).
- 일반 출력이 아니라 additionalContext로 낸다. 한 값이 10,000자를 넘으면 잘려 파일로 빠지므로 8,000자로 묶는다(공식 문서).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

MAX_MESSAGES = 30
MAX_CHARS = 8000
EXCLUDED_WORDS = ("holdout", "홀드아웃", "봉인")
HEADER = "압축 직후 사용자 원문(시각 포함). 기록·계획·요약보다 이 원문이 먼저다. 범위를 줄이거나 바꾸려면 먼저 묻는다."


def _text(content) -> str:
    """user 줄의 content(글자 또는 조각 목록)를 글로. 그림 조각은 [그림]으로 표시한다."""
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if part.get("type") == "text":
            parts.append(part.get("text", ""))
        elif part.get("type") == "image":
            parts.append("[그림]")
    return "\n".join(parts)


def _slash_command(text: str) -> str:
    """사용자가 친 /명령(예: /handoff 인수)은 기록에 <command-name> 꼴로 남는다. 친 모양 그대로 되돌린다."""
    if not text.startswith("<command-message>"):
        return text
    name = text.partition("<command-name>")[2].partition("</command-name>")[0]
    args = text.partition("<command-args>")[2].partition("</command-args>")[0]
    return f"{name} {args}".strip()


def human_messages(transcript: Path) -> list[tuple[str, str]]:
    """세션 기록에서 사람이 친 메시지를 (시각, 원문) 차례대로."""
    # 지금 쓰이는 기록은 마지막 줄이 덜 적혀 있을 수 있어 완성된 줄만 읽는다(remind_goal_review.py와 같은 방식)
    complete = transcript.read_text(encoding="utf-8", errors="replace").rpartition("\n")[0]
    found = []
    for line in complete.splitlines():
        if '"human"' not in line:
            continue
        entry = json.loads(line)
        if entry.get("type") != "user" or (entry.get("origin") or {}).get("kind") != "human":
            continue
        if entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain"):
            continue
        text = _slash_command(_text((entry.get("message") or {}).get("content")))
        if text.strip():
            found.append((entry.get("timestamp", ""), text))
    return found


def _local_time(stamp: str) -> str:
    """기록의 UTC 시각(2026-11-07T13:05:00.000Z)을 이 PC 시각으로."""
    if not stamp:
        return "시각 없음"
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")


def pick(messages: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """제외 낱말이 든 것을 빼고 마지막 30개, 합계 8,000자 이하가 되게 오래된 것부터 뺀다."""
    kept = [m for m in messages if not any(word in m[1].lower() for word in EXCLUDED_WORDS)][-MAX_MESSAGES:]
    while kept and sum(len(text) for _, text in kept) > MAX_CHARS:
        kept.pop(0)
    return kept


def context(transcript: Path) -> str:
    picked = pick(human_messages(transcript))
    if not picked:
        return f"{HEADER}\n(세션 기록에서 사용자 원문을 찾지 못했다: {transcript})"
    body = "\n\n".join(f"[{_local_time(stamp)}]\n{text}" for stamp, text in picked)
    return f"{HEADER}\n최근 {len(picked)}개, 오래된 것부터.\n\n{body}"


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    text = context(Path(payload["transcript_path"]))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
