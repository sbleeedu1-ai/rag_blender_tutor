"""사용자에게 보내는 답이 이미 정한 것을 어기면 답을 막는 훅(Stop). HISTORY [378].

지금은 settings.json에 걸지 않았다. 답 검사 Stop 훅은 [214]·[223]에서 사용자가 거절해, 켤지는 다시 묻는다.

왜: 글로 된 규칙(answer-forms.md "거부한 꼴", 전역 지침 "번호·이름표는 뜻을 함께")이 있는데도 2026-11-16 밤 8시 요약에서
거부된 '곧' 꼴을 다시 권하고 ㉠ 같은 기호를 풀지 않고 썼다. pstack `correct` 스킬(cursor/plugins, MIT)의 "글 규칙은 아무것도
실패시키지 않는다 → 검사로 막고, 그 검사가 실제 지난 실수를 잡는지 증명한다"를 따랐다.

- 본다: 마지막 사람 메시지 뒤 Claude가 쓴 답 글 전부(진행 중 짧은 말 포함).
- 규칙 1: 동그라미 기호(㉠-㉻)만 쓴 줄은 사용자가 뜻을 모른다. 같은 줄에 실제 꼴(따옴표 속 문장)을 함께 쓴다.
- 규칙 2: 답이 무엇을 권하면(권함·권하는·권합니다·추천·제안), 거부한 꼴(answer-forms.md 표의 "검사" 칸 정규식)이 든 줄을 찾는다.
  같은 줄에 거부·지금 제품·지금 꼴 같은 말이 있으면 설명으로 보고 넘긴다.
- 막으면 까닭을 Claude에게 돌려주고 Claude가 답을 고쳐 다시 낸다. stop_hook_active면(이미 한 번 막혀 고치는 중) 보지 않는다.
- 못 보는 것: 거부한 꼴을 다른 모양으로 바꿔 쓴 것, 정해 둔 차례를 어긴 권유, 말이 길고 어려운 것.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORMS = ROOT / "docs" / "agents" / "answer-forms.md"
SYMBOLS = re.compile(r"[㉠-㉻]")
QUOTED = re.compile(r"[\"“][^\"”]{4,}[\"”]")  # 기호 옆에 실제 꼴이 따옴표로 있으면 풀어 쓴 것으로 본다
RECOMMENDS = re.compile(r"권함|권하는|권합니다|권해|추천|제안")
EXPLAINS = re.compile(r"거부|지금 제품|지금 꼴|지금:|전:|예전|않|말고")


def rejected_patterns() -> list[tuple[str, re.Pattern]]:
    """answer-forms.md "사용자가 거부한 꼴" 표의 (꼴 이름, 검사 정규식). 검사 칸이 '-'인 줄은 뺀다."""
    text = FORMS.read_text(encoding="utf-8")
    section = text.split("## 사용자가 거부한 꼴", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[-1].startswith("`") and cells[-1].endswith("`"):
            out.append((cells[0].split(":")[0], re.compile(cells[-1].strip("`"))))
    return out


def problems(text: str) -> list[str]:
    bare = {m for line in text.splitlines() if not QUOTED.search(line) for m in SYMBOLS.findall(line)}
    found = [f"풀지 않은 기호 {m}: 같은 줄에 실제 꼴(따옴표 속 문장)을 함께 쓴다" for m in sorted(bare)]
    if RECOMMENDS.search(text):
        for name, pattern in rejected_patterns():
            for line in text.splitlines():
                m = pattern.search(line)
                if m and not EXPLAINS.search(line):
                    found.append(f"거부한 꼴({name}) \"{m.group()}\"을 권하는 답에 씀: docs/agents/answer-forms.md 표를 보고 다른 꼴을 낸다")
    return found


def _is_human(entry: dict) -> bool:
    return (entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human"
            and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain")))


def turn_text(transcript: Path) -> str:
    """마지막 사람 메시지 뒤 Claude가 쓴 글."""
    entries = [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = max((i for i, e in enumerate(entries) if _is_human(e)), default=-1) + 1
    texts = []
    for e in entries[start:]:
        content = (e.get("message") or {}).get("content") if e.get("type") == "assistant" else None
        if isinstance(content, list):
            texts += [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(texts)


def main() -> int:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active") or not data.get("transcript_path"):
        return 0
    found = problems(turn_text(Path(data["transcript_path"])))
    if found:
        print(json.dumps({"decision": "block", "reason": "답을 고쳐 다시 낸다(HISTORY [378]): " + " / ".join(found)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
