"""사용자에게 보내는 답이 이미 정한 것을 어기면 답을 막는 훅(Stop). HISTORY [378].

[214]·[223]에서 답 검사 Stop 훅을 거절했으나, 11-16 밤 사용자가 "답 검산 좋아"로 켰다([379]). 길이 제한은 넣지 않았다.

왜: 글로 된 규칙(answer-forms.md "거부한 꼴", 전역 지침 "번호·이름표는 뜻을 함께")이 있는데도 2026-11-16 밤 8시 요약에서
거부된 '곧' 꼴을 다시 권하고 ㉠ 같은 기호를 풀지 않고 썼다. pstack `correct` 스킬(cursor/plugins, MIT)의 "글 규칙은 아무것도
실패시키지 않는다 → 검사로 막고, 그 검사가 실제 지난 실수를 잡는지 증명한다"를 따랐다.

- 본다: 마지막 사람 메시지 뒤 Claude가 쓴 답 글(진행 중 짧은 말 포함). 이 훅이 그 차례에 막았으면 막은 뒤의 글만(아래 "글을 보는 범위").
- 규칙 1: 동그라미 기호(㉠-㉻)만 쓴 줄은 사용자가 뜻을 모른다. 같은 줄에 실제 꼴(따옴표 속 문장)을 함께 쓴다.
- 규칙 2: 답이 무엇을 권하면(권함·권하는·권합니다·추천·제안), 거부한 꼴(answer-forms.md 표의 "검사" 칸 정규식)이 든 줄을 찾는다.
  같은 줄에 거부·지금 제품·지금 꼴 같은 말이 있으면 설명으로 보고 넘긴다.
- 막으면 거부한 까닭(표의 사용자 원문·HISTORY)을 Claude에게 돌려주고 Claude가 답을 고쳐 다시 낸다. stop_hook_active면(이미 한 번 막혀 고치는 중) 보지 않는다.
- 규칙 3([392]): 답이 무엇을 권하는데 그 차례(마지막 사람 메시지 뒤)에 기록(HISTORY·실험 기록·인계·답 꼴·티켓)을 찾은 도구 호출이 없으면 막는다.
  전역 지침 "제안하기 전에는 HISTORY.md와 git 이력에서 그 주제를 찾아" 를 11-16에 두 번 어김("왜 확인안하지?", temperature 제안).
  읽기(grep·sed -n·Read 등)만 찾기로 치고 쓰기(>>·git add)는 안 친다. 지난 일을 말하는 줄(실수·했습니다 등)의 '제안'은 권유로 안 본다.
  한계: 그 차례에 기록을 다른 주제로 읽었으면 통과한다(temperature 제안 차례는 [342]를 읽어서 이 규칙으로도 못 막는다).
- 규칙 4([482], [485]에서 좁힘): 답이 실험 결과를 말하는데(결과 수 "8/18"·"29 / 30", 판정 낱말 채택·기각·'사이'·가를 수 없음·판단 안 함)
  그 차례에 advisor 결과(advisor_tool_result)가 없으면 막는다.
  처음엔 결론·순서·권유 낱말 모두에 걸어 11-19 세션 89차례 중 31번 걸렸고, 사용자 "나한테 말하기전에만 하라는 소리였는데 왜 31번이나 함?",
  "어떤 식으로든 실험 결과를 이야기할때만 상의하도록"으로 좁힘. 좁힌 뒤 같은 세션 93차례 중 23번 걸림(모두 결과 수·판정 낱말을 말한 답).
  한계: "8/18" 꼴과 판정 낱말 밖으로 말한 결과("47 대 47", "5회 중 3회", "1.7초")는 못 본다(04 결과가 이 꼴). 막는 때가 차례 끝이라 상의 없는 말은 이미 화면에 나간 뒤다.
  그 차례의 advisor 결과가 하나라도 있으면 통과한다(새 근거가 오기 전에 부른 advisor여도 통과).
- 규칙 5([575]): 용어 정리(PR #48)에서 바꾼 옛 말 가운데 뜻이 하나뿐인 것(OLD_TERMS)을 따옴표·백틱 밖에서 쓰면 막는다.
  한계: 여러 줄에 걸친 인용은 못 뺀다, 짝이 안 맞는 따옴표가 있으면 짝이 밀려 인용을 잘못 뺄 수 있다, 여러 뜻인 말은 안 본다.
- 규칙 6([602], [605]에서 좁힘): 마지막 답(Stop 입력 `last_assistant_message`, 없으면 기록의 마지막 글 조각)이 영어로 쓰였으면 막는다.
  진행 중 짧은 말은 안 본다(사용자 11-23 "최종 결론 답변 … 저럴때만 영어 체크하면 될거같은데", "어차피 어지간해선 중간거 안읽고 짧고 쉬운 영어면 내가 대충 이해는 가는"). 코드 블록·백틱·따옴표 인용·주소·경로를 뺀 뒤
  로마자가 20자 이상이고 한글의 2배보다 많고 영어 문장 낱말(the·is·I'll 등, 대소문자 안 가림)이 둘 이상이면, 또는 한글이 하나도 없으면 영어 답으로 본다.
  작은따옴표 짝은 빼지 않는다(I've … I'll 사이를 통째로 지움).
  Blender 화면 이름을 늘어놓은 한국어 답("Color Management에서 Working Space(Linear Rec.709)…를 봤습니다")을 살리려고 둘째·셋째 조건을 뒀다. 11-23 차례 7번 준비 중 진행 말 30여 개와 마지막 답을 영어로 써도 안 막혔다
  (사용자 "훅이 재 프롬프트 했지만 영어로 말하는건 안잡았네?").
  한계: 한국어 답 안의 영어 문장 하나는 못 본다(답 전체를 셈), 로마자 20자 밑의 아주 짧은 영어 답도 못 본다.
- 글을 보는 범위([604]): 글 규칙(1·2·5와 3·4의 글 쪽)은 그 차례에서 이 훅이 마지막으로 막은 뒤의 글만 본다(규칙 6은 마지막 답만).
  이미 고쳐 낸 글에 백그라운드 알림 차례마다 다시 막혔다(11-23 같은 영어 줄에 세 번: 처음 1번은 맞게, 되풀이 2번). advisor 결과·기록 찾기 호출은 차례 전체에서 본다.
  마지막 답은 Stop 입력 `last_assistant_message`에서 더한다. 공식 문서(code.claude.com/docs/en/hooks.md Stop input)
  "the transcript file isn't guaranteed to include the final message at Stop time"대로 11-23에 마지막 답의 '문턱'을 못 봤다.
- 못 보는 것: 거부한 꼴을 다른 모양으로 바꿔 쓴 것, 정해 둔 차례를 어긴 권유, 말이 길고 어려운 것, 찾긴 했으나 다른 낱말로 찾아 놓친 것.
  화면을 안 보고 화면 글자를 단정한 것(11-17 잰 결과 헛막음이 많아 안 넣음, rules-enforced.md·[434]).
"""

import json
import re
import sys
from pathlib import Path

from hook_notice import with_notice

ROOT = Path(__file__).resolve().parents[2]
FORMS = ROOT / "docs" / "agents" / "answer-forms.md"
SYMBOLS = re.compile(r"[㉠-㉻]")
QUOTED = re.compile(r"[\"“][^\"”]{4,}[\"”]")  # 기호 옆에 실제 꼴이 따옴표로 있으면 풀어 쓴 것으로 본다
RECOMMENDS = re.compile(r"권함|권하는|권합니다|권해|추천|제안")
RECORDS = re.compile(r"HISTORY\.md|experiment\.md|HANDOFF\.md|answer-forms\.md|rules-enforced\.md|\.scratch|session-search|git log -S|git log --grep")
READS = re.compile(r"\bgrep\b|\brg\b|sed -n|\bawk\b|\bhead\b|\btail\b|\bcat\b(?!\s*>)|git log -S|git log --grep|session-search")
WRITES = re.compile(r">>|>\s*\S|git add|git commit|write_text")
PAST = re.compile(r"실수|잘못|했습니다|였습니다|했던|한 것|한 게|어긴|거부된")
RESULTS = re.compile(r"(?<![\dA-Za-z_/.])\d{1,3}\s*/\s*\d{1,3}(?![\dA-Za-z_/.])|채택|기각|'사이'|사이로|가를 수 없음|판단 안 함")  # 결과 수(경로·날짜 속 숫자는 뺌, 뒤에 붙는 한글 조사는 둠)와 판정 낱말
EXPLAINS = re.compile(r"거부|지금 제품|지금 꼴|지금:|전:|예전|않|말고")
# 규칙 5(11-20): 용어 정리(PR #48, 대응표 `results/20261120/155834_용어정리/대응표.md`)에서 바꾼 옛 말 가운데 뜻이 하나뿐인 것만 둔다.
# 여러 뜻인 말(조각=조각 모드, 생각, 한도, 칸, 판, 팔, 뼈대=아마추어, 접음=패널 접기)은 헛막음이 많아 뺐다.
# 지시문(채점자 지시·번역 검수 지시도 뜻함)·관문(일반 낱말)·못 가름(자동으로 못 가름 등)은 정리된 문서에도 다른 뜻으로 남아 있어 뺐다([575]).
OLD_TERMS = (
    (r"질문 ?바꾸기", "쿼리 재작성"), (r"분야 ?고르기", "분야 선택"),
    (r"다시 줄 ?세우기", "리랭킹"), (r"정오표", "설명서 바로잡기 목록"), (r"예비 답변", "fallback 답변"),
    (r"헛고침|헛잡음", "잘못 고침·오탐"), (r"정답 조각|필요 조각", "정답 청크"),
    (r"(?<![_A-Za-z])조각만", "정답 청크 직접 넣음"), (r"옛 ?지금", "기준 조건(지금 제품 그대로)"), (r"숨긴 중복", "중복 확인 답"),
    (r"빈손", "GPT 단독"), (r"선 아래", "우선순위 밖"), (r"윗 상자", "메뉴·단축키 안내 상자"),
    (r"부호 검정", "우연인지 확인하는 계산(p값)"), (r"실행기", "실행 스크립트"), (r"모델 원문", "모델 raw 출력"),
    (r"보낸 글|넘긴 글", "모델에 보낸 내용 전체"), (r"천장", "상한"), (r"얼리기|얼린 ", "코드 동결"),
    (r"문턱|통과선", "기준값"), (r"(?:지금|새) 뼈대", "분야 선택 있음·없음"), (r"첫 글자(?:까지| 시간|가 나오)", "첫 토큰"),
)
CODE = re.compile(r"```.*?```|https?://\S+|[\w./-]*/[\w./-]+|\b[\w-]+\.(?:py|md|json|jsonl|txt|log|png)\b", re.S)  # 규칙 6에서 셈에 넣지 않는 것
FUNCTION_WORDS = re.compile(r"\b(?:the|a|an|is|are|was|to|of|and|so|it|this|that|I|I'll|I'm|I've|now|then|with|for)\b", re.I)  # 영어 문장에만 나오는 낱말(문장 첫 The·Now도 셈)
QUOTES_EN = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`")  # 규칙 6은 작은따옴표 짝을 빼지 않는다(I've … I'll 사이를 통째로 지움)
QUOTES = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`|'[^'\n]*'")  # 인용·파일 이름·코드 안은 옛 말이어도 그대로 둔다(대응표 "그대로 둘 것")


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
    found += old_term_problems(text)
    return found


def old_term_problems(text: str) -> list[str]:
    """규칙 5: 용어 정리로 바꾼 옛 말을 답에 다시 쓰면 막는다(따옴표·백틱 안은 뺀다).
    같은 줄에 새 말도 있으면 옛 말과 새 말을 견주어 설명하는 줄(대응표 보이기 등)로 보고 넘긴다."""
    hits = {}
    for line in QUOTES.sub("", text).splitlines():
        for pattern, new in OLD_TERMS:
            m = re.search(pattern, line)
            if m and new.split("(")[0].split("·")[0] not in line:
                hits.setdefault(pattern, f"'{m.group().strip()}' → '{new}'")
    hits = list(hits.values())
    if not hits:
        return []
    return ["용어 정리(11-20, PR #48)에서 바꾼 옛 말을 썼다: " + ", ".join(hits) + ". 새 말로 고친다(인용은 따옴표 안에 둔다). "
            "까닭(사용자 원문): \"니만 아는 한국어\", \"우리 합의본 단어들? 말고는 전부 고쳐\" [575]"]


def english_problems(blocks: list[str]) -> list[str]:
    """규칙 6: 영어로 쓴 답을 막는다(turn_problems가 마지막 답만 넘김, 코드·인용·주소·경로는 빼고 로마자와 한글 수를 견줌)."""
    for text in blocks:
        bare = QUOTES_EN.sub("", CODE.sub("", text))
        latin, hangul = len(re.findall(r"[A-Za-z]", bare)), len(re.findall(r"[가-힣]", bare))
        if latin >= 20 and (hangul == 0 or (latin > 2 * hangul and len(FUNCTION_WORDS.findall(bare)) >= 2)):  # 한글이 하나도 없으면 짧은 말도 막음  # 한글 한 글자가 로마자 2-3자 몫이라 2배로 견줌(Blender 화면 용어가 많은 한국어 답을 살림)
            return [f"답을 영어로 썼다(로마자 {latin}자·한글 {hangul}자: \"{text.strip()[:60]}\"). 마지막 답을 쉬운 한국어로 다시 쓴다(영어 용어·코드·인용은 그대로 둬도 됨, 진행 중 짧은 말은 영어여도 됨). "
                    "까닭(사용자 원문): \"훅이 재 프롬프트 했지만 영어로 말하는건 안잡았네?\" [602], \"최종 결론 답변 … 저럴때만 영어 체크하면 될거같은데\" [605], 전역 지침 \"설명은 쉬운 한국어로 하고\""]
    return []


def _is_human(entry: dict) -> bool:
    return (entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human"
            and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain")))


def _is_feedback(entry: dict) -> bool:
    """이 훅(Stop)이 막으며 돌려준 글이 기록에 들어간 항목."""
    content = (entry.get("message") or {}).get("content")
    text = content if isinstance(content, str) else " ".join(c.get("text", "") for c in content or [] if isinstance(c, dict))
    return entry.get("type") == "user" and text.startswith("Stop hook feedback")


def _turn_blocks(transcript: Path) -> list[dict]:
    """마지막 사람 메시지 뒤 Claude 메시지의 내용 조각(글·도구 호출). 훅이 막은 자리는 {"type": "feedback"}로 남긴다."""
    entries = [json.loads(line) for line in transcript.read_text(encoding="utf-8").split("\n") if line.strip()]  # splitlines()는 글 속 U+2028에서도 잘라 JSON 줄이 깨진다([550])
    start = max((i for i, e in enumerate(entries) if _is_human(e)), default=-1) + 1
    blocks = []
    for e in entries[start:]:
        if _is_feedback(e):
            blocks.append({"type": "feedback"})
            continue
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


def turn_problems(transcript: Path, last_message: str = "") -> list[str]:
    """규칙 1·2·5(답 글), 3(권하는데 기록을 안 찾음), 4(advisor 없이 결과), 6(영어 답).
    글은 마지막으로 막은 뒤의 것 + 기록에 아직 없을 수 있는 마지막 답(last_message), 도구 호출은 차례 전체."""
    blocks = _turn_blocks(transcript)
    cut = max((i for i, b in enumerate(blocks) if b.get("type") == "feedback"), default=-1) + 1
    texts = [b.get("text", "") for b in blocks[cut:] if b.get("type") == "text"]
    if last_message.strip() and last_message.strip() not in "\n".join(texts):
        texts.append(last_message)
    text = "\n".join(texts)
    found = problems(text)
    found += english_problems([last_message if last_message.strip() else (texts[-1] if texts else "")])  # 마지막 답만([605])
    searched = any(b.get("type") == "tool_use" and _reads_records(b.get("name", ""), b.get("input") or {}) for b in blocks)
    recommends = any(RECOMMENDS.search(line) and not PAST.search(line) for line in text.splitlines())
    if recommends and not searched:
        found.append("권하기 전에 기록을 찾지 않았다(이 차례에 HISTORY.md·docs/experiment.md·HANDOFF.md·answer-forms.md·티켓을 찾은 호출이 없음). "
                     "그 주제를 기록에서 찾아 관련 결정 원문을 함께 들고, 못 찾으면 어디서 어떤 낱말로 찾았는지 쓴다. "
                     "까닭(사용자 원문): \"그러니까 왜 확인안하지?\", \"이런거 좀 찾아보라니까\" [392]")
    if RESULTS.search(text) and not any(b.get("type") == "advisor_tool_result" for b in blocks):
        found.append("실험 결과를 말하기 전에 advisor와 상의하지 않았다(이 차례에 advisor 결과 없음). advisor를 부르고 그 상의로 답을 고친다. advisor를 부를 수 없으면(도구 없음 등) 결론을 빼고 그 사실을 사용자에게 알린다. "
                     "까닭(사용자 원문): \"앞으로 결론 내기전에 무조건 어드바이저 지금 페이블이잖아 상의하고 결로내\" [482], \"어떤 식으로든 실험 결과를 이야기할때만 상의하도록\" [485]")
    return found


def main() -> int:
    data = json.load(sys.stdin)
    if data.get("stop_hook_active") or not data.get("transcript_path"):
        return 0
    found = turn_problems(Path(data["transcript_path"]), data.get("last_assistant_message") or "")
    if found:
        print(json.dumps(with_notice("check_reply", data, {"decision": "block", "reason": "답을 고쳐 다시 낸다(HISTORY [378]): " + " / ".join(found)}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
