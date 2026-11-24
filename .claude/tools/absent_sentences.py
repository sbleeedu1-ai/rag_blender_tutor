"""차례 14번(묶음 5) 관문 셈의 앞뒤: 답에서 "설명서에 없다" 꼴 문장을 넓게 뽑아, 판 이름을 가리고 섞은 목록으로 만든다(make),
하위 에이전트가 붙인 본론/사족 표지를 판별로 다시 모아 센다(count).

뽑는 규칙은 조사 4(`results/20261119/222431_실패분석/2_조사4.md` 1절)를 따른다: 답을 줄바꿈과 문장 끝으로 나누고,
"설명서·매뉴얼·받은/제공된 글·내용"이 들고 부정어(없·않·못·확인할 수 없·찾을 수 없)가 든 문장, 또는 "범위 밖"이 든 문장.
조사 4가 4낱말만으로는 54%만 잡았다고 적어 넓게 뽑고, 오탐은 표지 붙이는 쪽이 "아님"으로 거른다.

make: .venv/bin/python .claude/tools/absent_sentences.py make <답 목록.jsonl> <나갈 폴더> [--batch N]
  답 목록 한 줄 = {"판": 이름, "회": 회차, "번호": 문항, "질문": …, "핵심": [...], "답": …}
  나갈 폴더에 묶음_K.jsonl(가린 목록: 표지 id·질문·핵심·답·문장)을, 옆 폴더 <나갈 폴더>_열쇠/에 열쇠.json(id → 판·회·번호)을 쓴다.
count: .venv/bin/python .claude/tools/absent_sentences.py count <나갈 폴더>
  표지_K.jsonl(한 줄 = {"id": …, "표지": "본론"|"사족"|"아님"|"모호"})을 모아 판별·문항별로 센다 → 셈.json
reuse: .venv/bin/python .claude/tools/absent_sentences.py reuse <옛 폴더> <새 폴더>
  같은 답의 같은 문장에 옛 폴더가 붙인 표지를 새 폴더로 옮기고, 남은 줄을 묶음_남은.jsonl로 쓴다.
표지 붙이는 에이전트에게 주는 글: .claude/tools/absent_labels_prompt.md
"""

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SOURCE = r"(설명서|매뉴얼|자료|문서|안내|받은 (?:설명서 )?(?:글|내용)|제공된 (?:설명서|내용|글)|주어진 (?:설명서|내용|글))"
# 출처 낱말 없이도 뽑는 꼴(조사 4의 4낱말 + 새 문구가 예로 든 말, 설계 독립 검토 1-1)
ALONE = r"(나와 있지 않|나오지 않|범위 밖|확인되지 않|다루지 않)"
NEGATIVE = r"(없|않|못|확인할 수 없|찾을 수 없)"
SPLIT = re.compile(r"\n+|(?<=[다요까])[.?!]\s+|(?<=[.?!])\s+(?=\S)")
LABELS = ("본론", "사족", "아님", "모호")


def sentences(answer: str) -> list[str]:
    return [s.strip() for s in SPLIT.split(answer or "") if s and s.strip()]


def claims(answer: str) -> list[str]:
    """설명서에 없다고 말할 수 있는 문장(넓게). 표지 붙이는 쪽이 아님을 거른다."""
    found = []
    for s in sentences(answer):
        if (re.search(SOURCE, s) and re.search(NEGATIVE, s)) or re.search(ALONE, s):
            found.append(s)
    return found


def key_dir(out: Path) -> Path:
    """판 이름이 든 열쇠는 표지 붙이는 쪽에 넘기는 폴더 밖에 둔다(설계 독립 검토 3-2)."""
    return out.parent / f"{out.name}_열쇠"


def make(answers_path: Path, out: Path, batch: int, seed: int = 20261124) -> None:
    rows = [json.loads(line) for line in answers_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    items, key = [], {}
    for row in rows:
        for k, s in enumerate(claims(row["답"])):
            items.append((row, k, s))
    random.Random(seed).shuffle(items)
    out.mkdir(parents=True, exist_ok=False)
    batches = defaultdict(list)
    for n, (row, k, s) in enumerate(items):
        sid = f"s{n:04d}"
        key[sid] = {"판": row["판"], "회": row["회"], "번호": row["번호"], "몇째": k}
        batches[n // batch].append({"id": sid, "질문": row["질문"], "핵심": row.get("핵심", []), "답": row["답"], "문장": s})
    for b, lines in batches.items():
        (out / f"묶음_{b}.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    key_dir(out).mkdir(parents=True, exist_ok=True)
    (key_dir(out) / "열쇠.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    answers_by_arm = Counter(row["판"] for row in rows)
    print(json.dumps({"답": dict(answers_by_arm), "뽑은 문장": len(items), "묶음": len(batches)}, ensure_ascii=False))


def reuse(old: Path, new: Path) -> None:
    """뽑기 규칙을 넓혀 다시 만든 new 폴더에, old 폴더에서 같은 답의 같은 문장(판·회·번호·문장)에 붙였던 표지를 옮긴다.
    옮긴 것은 표지_재사용.jsonl에, 남은 줄은 묶음_남은.jsonl에 쓴다(남은 줄만 새로 표지를 붙인다)."""
    old_key = json.loads((key_dir(old) / "열쇠.json").read_text(encoding="utf-8"))
    old_labels = {}
    for path in old.glob("표지_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                old_labels[row["id"]] = row["표지"]
    by_text = {}
    for path in old.glob("묶음_*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                w = old_key[row["id"]]
                by_text[(w["판"], w["회"], w["번호"], row["문장"])] = old_labels[row["id"]]
    new_key = json.loads((key_dir(new) / "열쇠.json").read_text(encoding="utf-8"))
    kept, left = [], []
    for path in sorted(new.glob("묶음_[0-9]*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                w = new_key[row["id"]]
                label = by_text.get((w["판"], w["회"], w["번호"], row["문장"]))
                if label is None:
                    left.append(row)
                else:
                    kept.append({"id": row["id"], "표지": label})
    (new / "표지_재사용.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in kept), encoding="utf-8")
    (new / "묶음_남은.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in left), encoding="utf-8")
    print(json.dumps({"옮긴 표지": len(kept), "남은 문장": len(left), "옛 폴더 표지": len(old_labels)}, ensure_ascii=False))


def count(out: Path) -> dict:
    key = json.loads((key_dir(out) / "열쇠.json").read_text(encoding="utf-8"))
    labels = {}
    for path in sorted(out.glob("표지_*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row["표지"] not in LABELS:
                    raise SystemExit(f"모르는 표지 {row['표지']!r}: {row['id']}")
                labels[row["id"]] = row["표지"]
    missing = sorted(set(key) - set(labels))
    if missing:
        raise SystemExit(f"표지 없는 문장 {len(missing)}개: {missing[:5]}")
    by_arm: dict = defaultdict(Counter)
    by_question: dict = defaultdict(lambda: defaultdict(Counter))
    answers_with: dict = defaultdict(lambda: defaultdict(set))
    for sid, where in key.items():
        label = labels[sid]
        by_arm[where["판"]][label] += 1
        by_question[where["판"]][where["번호"]][label] += 1
        answers_with[where["판"]][label].add((where["회"], where["번호"]))
    result = {
        "판별 문장": {arm: dict(c) for arm, c in by_arm.items()},
        "판별 답 수(그 표지 문장이 하나라도 든 답)": {arm: {lab: len(s) for lab, s in d.items()} for arm, d in answers_with.items()},
        "판별 문항별 문장": {arm: {q: dict(c) for q, c in sorted(d.items())} for arm, d in by_question.items()},
        "판별 회차별 사족 문장": {arm: dict(sorted(Counter(key[s]["회"] for s in key if key[s]["판"] == arm and labels[s] == "사족").items()))
                            for arm in by_arm},
    }
    (out / "셈.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("판별 문장", "판별 답 수(그 표지 문장이 하나라도 든 답)", "판별 회차별 사족 문장")}, ensure_ascii=False, indent=1))
    return result


if __name__ == "__main__":
    if sys.argv[1] == "make":
        batch = int(sys.argv[sys.argv.index("--batch") + 1]) if "--batch" in sys.argv else 80
        make(Path(sys.argv[2]), Path(sys.argv[3]), batch)
    elif sys.argv[1] == "count":
        count(Path(sys.argv[2]))
    elif sys.argv[1] == "reuse":
        reuse(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit("make, count 또는 reuse")
