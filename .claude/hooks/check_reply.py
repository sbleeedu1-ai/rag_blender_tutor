"""사용자에게 보내는 답이 이미 정한 것을 어기면 답을 막는 훅(Stop). HISTORY [378].

[214]·[223]에서 답 검사 Stop 훅을 거절했으나, 11-16 밤 사용자가 "답 검산 좋아"로 켰다([379]). 길이 제한은 넣지 않았다.

왜: 글로 된 규칙(answer-forms.md "거부한 꼴", 전역 지침 "번호·이름표는 뜻을 함께")이 있는데도 2026-11-16 밤 8시 요약에서
거부된 '곧' 꼴을 다시 권하고 ㉠ 같은 기호를 풀지 않고 썼다. pstack `correct` 스킬(cursor/plugins, MIT)의 "글 규칙은 아무것도
실패시키지 않는다 → 검사로 막고, 그 검사가 실제 지난 실수를 잡는지 증명한다"를 따랐다.

- 본다: 마지막 사람 메시지 뒤 Claude가 쓴 답 글 전부(진행 중 짧은 말 포함).
- 규칙 1: 동그라미 기호(㉠-㉻)만 쓴 줄은 사용자가 뜻을 모른다. 같은 줄에 실제 꼴(따옴표 속 문장)을 함께 쓴다.
- 규칙 2: 답이 무엇을 권하면(권함·권하는·권합니다·추천·제안), 거부한 꼴(answer-forms.md 표의 "검사" 칸 정규식)이 든 줄을 찾는다.
  같은 줄에 거부·지금 제품·지금 꼴 같은 말이 있으면 설명으로 보고 넘긴다.
- 막으면 거부한 까닭(표의 사용자 원문·HISTORY)을 Claude에게 돌려주고 Claude가 답을 고쳐 다시 낸다. stop_hook_active면(이미 한 번 막혀 고치는 중) 보지 않는다.
- 규칙 3([392]): 답이 무엇을 권하는데 그 차례(마지막 사람 메시지 뒤)에 기록(HISTORY·실험 기록·인계·답 꼴·티켓)을 찾은 도구 호출이 없으면 막는다.
  전역 지침 "제안하기 전에는 HISTORY.md와 git 이력에서 그 주제를 찾아" 를 11-16에 두 번 어김("왜 확인안하지?", temperature 제안).
  읽기(grep·sed -n·Read 등)만 찾기로 치고 쓰기(>>·git add)는 안 친다. 지난 일을 말하는 줄(실수·했습니다 등)의 '제안'은 권유로 안 본다.
  한계: 그 차례에 기록을 다른 주제로 읽었으면 통과한다(temperature 제안 차례는 [342]를 읽어서 이 규칙으로도 못 막는다).
- 규칙 4([482]): 답이 결론·순서·다음 할 일을 말하거나 무엇을 권하는데 그 차례에 advisor 결과(advisor_tool_result)가 없으면 막는다.
  사용자 "앞으로 결론 내기전에 무조건 어드바이저 지금 페이블이잖아 상의하고 결로내"(11-19). 11-19 세션(압축 앞뒤 합침) 답이 있는 89차례에 돌리면 31번 걸림.
  한계: 결론 낱말 없이 결론을 말한 답(예: "04에서 어차피 나오는 답 일부를 … 세자는 뜻입니다")은 못 본다.
  막는 때는 차례 끝이라 상의 없이 쓴 결론이 이미 화면에 나간 뒤다. 그 차례의 advisor 결과가 하나라도 있으면 통과한다
  (새 근거가 오기 전에 부른 advisor여도 통과, 11-19 Fable 판단이 온 차례가 그랬다).
- 못 보는 것: 거부한 꼴을 다른 모양으로 바꿔 쓴 것, 정해 둔 차례를 어긴 권유, 말이 길고 어려운 것, 찾긴 했으나 다른 낱말로 찾아 놓친 것.
  화면을 안 보고 화면 글자를 단정한 것(11-17 잰 결과 헛막음이 많아 안 넣음, rules-enforced.md·[434]).
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
RECORDS = re.compile(r"HISTORY\.md|experiment\.md|HANDOFF\.md|answer-forms\.md|rules-enforced\.md|\.scratch|session-search|git log -S|git log --grep")
READS = re.compile(r"\bgrep\b|\brg\b|sed -n|\bawk\b|\bhead\b|\btail\b|\bcat\b(?!\s*>)|git log -S|git log --grep|session-search")
WRITES = re.compile(r">>|>\s*\S|git add|git commit|write_text")
PAST = re.compile(r"실수|잘못|했습니다|였습니다|했던|한 것|한 게|어긴|거부된")
CONCLUDES = re.compile(r"결론|다음은|다음 할 일|순서는")
EXPLAINS = re.compile(r"거부|지금 제품|지금 꼴|지금:|전:|예전|않|말고")


def rejected_patterns() -> list[tuple[str, str, str, re.Pattern]]:
    """answer-forms.md "사용자가 거부한 꼴" 표의 (꼴 이름, 사용자 원문, HISTORY, 검사 정규식). 검사 칸이 '-'인 줄은 뺀다."""
    text = FORMS.read_text(encoding="utf-8")
    section = text.split("## 사용자가 거부한 꼴", 1)[1].split("\n## ", 1)[0]
    out = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[-1].startswith("`") and cells[-1].endswith("`"):
            out.append((cells[0].split(":")[0], cells[1], cells[2], re.compile(cells[-1].strip("`"))))
    return out


def problems(text: str) -> list[str]:
    bare = {m for line in text.splitlines() if not QUOTED.search(line) for m in SYMBOLS.findall(line)}
    found = [f"풀지 않은 기호 {m}: 같은 줄에 실제 꼴(따옴표 속 문장)을 함께 쓴다" for m in sorted(bare)]
    if RECOMMENDS.search(text):
        for name, quote, history, pattern in rejected_patterns():
            for line in text.splitlines():
                m = pattern.search(line)
                if m and not EXPLAINS.search(line):
                    found.append(f"\"{m.group()}\"은 사용자가 거부한 꼴({name})이다. 거부한 까닭(사용자 원문): {quote} {history}. "
                                 "권하지 말고 다른 꼴을 낸다. 꼭 써야 하면 같은 줄에 '거부된 꼴'이라고 밝히고 위 까닭을 함께 설명한다")
    return found


def _is_human(entry: dict) -> bool:
    return (entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human"
            and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain")))


def _turn_blocks(transcript: Path) -> list[dict]:
    """마지막 사람 메시지 뒤 Claude 메시지의 내용 조각(글·도구 호출)."""
    entries = [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = max((i for i, e in enumerate(entries) if _is_human(e)), default=-1) + 1
    blocks = []
    for e in entries[start:]:
        content = (e.get("message") or {}).get("content") if e.get("type") == "assistant" else None
        if isinstance(content, list):
            blocks += [c for c in content if isinstance(c, dict)]
    return blocks


def _reads_records(name: str, args: dict) -> bool:
    """기록을 읽은 호출인가. 쓰기(>>·git add·git commit)와 커밋 뒤 git log --oneline -1은 찾기로 치지 않는다."""
    if name in ("Grep", "Read"):
        return bool(RECORDS.search(json.dumps(args, ensure_ascii=False)))
    if name != "Bash":
        return False
    # 따옴표 속 글(정규식의 | 등)은 지우고 쪼갠다. 안 지우면 grep -E "a|b" HANDOFF.md가 grep과 파일 이름으로 갈려 헛막음([434])
    command = re.sub(r"\"[^\"]*\"|'[^']*'", '""', args.get("command", ""))
    for part in re.split(r"[;&|\n]+", command):
        if RECORDS.search(part) and READS.search(part) and not WRITES.search(part):
            return True
    return False


def turn_text(transcript: Path) -> str:
    """마지막 사람 메시지 뒤 Claude가 쓴 글."""
    return "\n".join(b.get("text", "") for b in _turn_blocks(transcript) if b.get("type") == "text")


def turn_problems(transcript: Path) -> list[str]:
    """규칙 1·2(답 글)와 규칙 3(권하는데 그 차례에 기록을 안 찾음)."""
    blocks = _turn_blocks(transcript)
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    found = problems(text)
    searched = any(b.get("type") == "tool_use" and _reads_records(b.get("name", ""), b.get("input") or {}) for b in blocks)
    recommends = any(RECOMMENDS.search(line) and not PAST.search(line) for line in text.splitlines())
    if recommends and not searched:
        found.append("권하기 전에 기록을 찾지 않았다(이 차례에 HISTORY.md·docs/experiment.md·HANDOFF.md·answer-forms.md·티켓을 찾은 호출이 없음). "
                     "그 주제를 기록에서 찾아 관련 결정 원문을 함께 들고, 못 찾으면 어디서 어떤 낱말로 찾았는지 쓴다. "
                     "까닭(사용자 원문): \"그러니까 왜 확인안하지?\", \"이런거 좀 찾아보라니까\" [392]")
    concludes = recommends or any(CONCLUDES.search(line) for line in text.splitlines())
    if concludes and not any(b.get("type") == "advisor_tool_result" for b in blocks):
        found.append("결론·순서·권유를 말하기 전에 advisor와 상의하지 않았다(이 차례에 advisor 결과 없음). advisor를 부르고 그 상의로 답을 고친다. advisor를 부를 수 없으면(도구 없음 등) 결론을 빼고 그 사실을 사용자에게 알린다. "
                     "까닭(사용자 원문): \"앞으로 결론 내기전에 무조건 어드바이저 지금 페이블이잖아 상의하고 결로내\" [482]")
    return found


def main() -> int:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active") or not data.get("transcript_path"):
        return 0
    found = turn_problems(Path(data["transcript_path"]))
    if found:
        print(json.dumps({"decision": "block", "reason": "답을 고쳐 다시 낸다(HISTORY [378]): " + " / ".join(found)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
