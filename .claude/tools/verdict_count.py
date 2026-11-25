"""판정 말 훅을 넣기 전에 잰다(돈 0, HISTORY [665] 뒤 사용자 "그걸 위해서 일단 얼마나 그랬는지 보고?" → "ㄱㄱ").

재는 규칙(넣을 후보): 차례의 마지막 답에 시험 판정 말(통과·안 넣음·버림 등)이 든 줄이 있으면
  ① 그 줄에 출처(HISTORY [번호], docs/experiment.md:줄, 판정.json, 실험 기록 N줄)가 붙어 있고
  ② 그 차례에 실험 기록(docs/experiment.md)이나 판정 파일(*판정*.json·셈 결과)을 읽은 도구 호출이 있어야 한다.
하나라도 없으면 "막힘"으로 센다. 계획 파일·HISTORY에 쓰기만 한 것은 읽기로 치지 않는다.
[434]에서 근거 표시 강제 규칙이 56줄 중 47줄을 헛막아 넣지 않았으므로, 넣기 전에 대화 기록에 돌려 막힘 수를 본다.

실행: .venv/bin/python -I .claude/tools/verdict_count.py [--narrow] <대화 기록.jsonl> [...]
뽑기: .venv/bin/python -I .claude/tools/verdict_count.py --dump <폴더> <사람 메시지 시각(UTC, 2026-11-24T10:55:16)>... -- <대화 기록.jsonl> [...]
  차례마다 사람 말, 도구 호출(이름·입력 앞 400자), 마지막 답을 <폴더>/<시각>.md로 쓴다(agent 훅 재판정 [669]).
"""

import json
import re
import sys
from pathlib import Path

WIDE = re.compile(r"통과|안 넣|넣지 않|넣지 않는|버림|버려|버린다|버렸|떨어졌|떨어짐|미달|탈락")
NARROW = re.compile(r"규칙(대로|상|으로)[^.。]{0,12}(통과|안 넣|넣지 않|버림|버린|떨어)")  # 11-24 밤 잘못 말한 넷을 본 뒤 만든 꼴(낙관적)
QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|`[^`\n]*`|'[^'\n]*'")
NOT_EXPERIMENT = re.compile(r"pytest|테스트|시험 \d+ 통과|훅 시험|CI|ruff|검사.{0,6}통과|그대로 통과")  # 코드 시험 통과는 시험 판정이 아니다
CITE = re.compile(r"\[\d{3}\]|docs/experiment\.md:\d+|판정\.json|실험 기록 \d+줄|experiment\.md \d+줄")
SOURCE = re.compile(r"docs/experiment\.md|판정[^\s\"']*\.json|셈_결과|읽기별_셈|먼저볼_셈")
READS = re.compile(r"\b(grep|sed|cat|head|tail|awk|rg|python)\b")
WRITES = re.compile(r">>|git (add|commit)|\.write\(|replace\(")


def human(e: dict) -> bool:
    return (e.get("type") == "user" and (e.get("origin") or {}).get("kind") == "human"
            and not (e.get("isMeta") or e.get("isCompactSummary") or e.get("isSidechain")))


def reads_source(block: dict) -> bool:
    name, args = block.get("name", ""), block.get("input") or {}
    if name in ("Read", "Grep"):
        return bool(SOURCE.search(json.dumps(args, ensure_ascii=False)))
    if name != "Bash":
        return False
    command = re.sub(r"\"[^\"]*\"|'[^']*'", '""', args.get("command", ""))  # 따옴표 속 |에서 쪼개지 않게([434], check_reply._reads_records와 같음)
    return any(SOURCE.search(p) and READS.search(p) and not WRITES.search(p) for p in re.split(r"[;&|\n]+", command))


def turns(path: Path):
    """(사람 메시지 시각, 사람 말 앞부분, 마지막 답 글, 그 차례에 판정 자료를 읽었나)."""
    entries = [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]
    cur = None
    for e in entries + [None]:
        if e is None or human(e):
            if cur and cur["texts"]:
                yield cur["ts"], cur["ask"], cur["texts"][-1], cur["read"]
            if e is None:
                return
            c = (e.get("message") or {}).get("content")
            ask = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c or [] if isinstance(b, dict))
            cur = {"ts": e.get("timestamp", ""), "ask": ask[:40].replace("\n", " "), "texts": [], "read": False}
            continue
        if cur is None or e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        if any(t.strip() for t in texts):
            cur["texts"].append("\n".join(texts))
        cur["read"] |= any(isinstance(b, dict) and b.get("type") == "tool_use" and reads_source(b) for b in content)


def dump_turns(path: Path, wanted: set[str], out: Path):
    """wanted 시각의 차례를 사람이 읽는 꼴로 쓴다. 쓴 시각 목록을 돌려준다."""
    entries = [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]
    found, cur = [], None
    for e in entries + [None]:
        if e is None or human(e):
            if cur:
                (out / f"{cur['ts']}.md").write_text(
                    f"# 차례 {cur['ts']} (UTC)\n\n## 사람 말\n{cur['ask']}\n\n## 이 차례의 도구 호출\n"
                    + ("\n".join(cur["tools"]) or "(없음)") + "\n\n## 마지막 답\n" + (cur["texts"][-1] if cur["texts"] else ""),
                    encoding="utf-8")
                found.append(cur["ts"])
            cur = None
            if e is None:
                break
            ts = e.get("timestamp", "")[:19]
            if ts in wanted:
                c = (e.get("message") or {}).get("content")
                ask = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c or [] if isinstance(b, dict))
                cur = {"ts": ts, "ask": ask, "tools": [], "texts": []}
            continue
        if cur is None or e.get("type") != "assistant":
            continue
        for b in (e.get("message") or {}).get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                cur["tools"].append(f"- {b.get('name')}: {json.dumps(b.get('input'), ensure_ascii=False)[:400]}")
            elif b.get("type") == "text" and b.get("text", "").strip():
                cur["texts"].append(b["text"])
    return found


def main(paths: list[str]) -> None:
    if paths[:1] == ["--dump"]:
        out, rest = Path(paths[1]), paths[2:]
        wanted, files = set(rest[:rest.index("--")]), rest[rest.index("--") + 1:]
        out.mkdir(parents=True, exist_ok=True)
        got = [ts for f in files for ts in dump_turns(Path(f), wanted, out)]
        print(f"뽑음 {len(got)}/{len(wanted)}", "빠짐:", sorted(wanted - set(got)))
        return
    narrow = "--narrow" in paths
    paths = [p for p in paths if p != "--narrow"]
    VERDICT = NARROW if narrow else WIDE
    total = with_verdict = blocked = unread = 0
    for p in paths:
        for ts, ask, text, read in turns(Path(p)):
            total += 1
            lines = [ln for ln in text.splitlines() if VERDICT.search(QUOTED.sub("", ln)) and not NOT_EXPERIMENT.search(ln)]
            if not lines:
                continue
            with_verdict += 1
            bad = [] if read else [ln for ln in lines if not CITE.search(ln)]  # 읽었거나 출처를 붙였으면 통과([669] 뒤, 결과 본 뒤 바꿈·낙관적)
            if bad:
                blocked += 1
                why = "판정 자료 안 읽음" if not read else "출처 없음"
                unread += not read
                print(f"막힘 {ts[:19]} [{why}] 사람: {ask}")
                for ln in bad[:3]:
                    print("    ", ln.strip()[:150])
    print(f"\n차례 {total} · 판정 말 든 마지막 답 {with_verdict} · 막힘 {blocked}(그중 판정 자료 안 읽음 {unread}, 읽었는데 줄에 출처 없음 {blocked - unread})")


if __name__ == "__main__":
    main(sys.argv[1:])
