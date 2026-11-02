"""t33_none 기록의 검색 결과 주소로 답변 모델 입력을 다시 만들어 길이를 잰다(API 호출 없음).
비슷한 연습 과정 줄은 빠져 있다(짧음). 작업 상태는 문항 파일의 state 파일을 쓴다."""
import json, ast, re, sys
from pathlib import Path
import numpy as np
ROOT = Path(r"C:\WORK\rag_blender_tutor")
sys.path.insert(0, str(ROOT))
from blender_tutor.manual_chunks import load_chunks
from blender_tutor import answer_engine as ae
from blender_tutor.work_state import WorkState

chunks = load_chunks(ROOT / "data/chunks/manual_chunks.jsonl")
eng = ae.AnswerEngine.__new__(ae.AnswerEngine)
eng._chunks = chunks
eng._position = {c: i for i, c in enumerate(chunks)}
eng._families = {}
for i, c in enumerate(chunks):
    if c.parent:
        eng._families.setdefault(c.parent, []).append(i)
by_addr = {}
for c in chunks:
    by_addr.setdefault(c.address, []).append(c)
qs = {q["번호"]: q for q in json.load(open(ROOT / "data/eval/speed/A1-A10.json", encoding="utf-8"))}
tot = []
for l in open(ROOT / "results/20261102/092554_t33_none/답.jsonl", encoding="utf-8"):
    r = json.loads(l)
    res = r["검색 결과"]; res = ast.literal_eval(res) if isinstance(res, str) else res
    sent = []
    for x in res:
        cands = [c for c in chunks if c.key.split("/")[0] == x["주소"] or c.address.endswith(x["주소"])] if False else None
        sent.append(x["주소"])
    # 주소 → 청크(같은 주소 여러 조각이면 첫 것: 근사)
    picked = []
    for a in sent:
        hit = [c for c in chunks if c.address == a or c.address.endswith(a)]
        picked.append(hit[0] if hit else None)
    picked = [c for c in picked if c]
    groups = eng._widened(picked, [])
    sf = ROOT / "data/eval/speed" / qs[r["번호"]]["작업 상태"]
    state = WorkState.from_json(json.load(open(sf, encoding="utf-8"))) if sf.exists() else None
    msgs = ae._messages(r["질문"], state, [], groups, [], None) if state else None
    sysm, user = msgs[0]["content"], msgs[-1]["content"]
    manual = "\n\n---\n\n".join("\n\n".join(c.text for c in g) for g in groups)
    en_words = len(re.findall(r"\S+", manual))
    tot.append((r["번호"], len(picked), sum(len(g) for g in groups), en_words, len(sysm), len(user), len(user) - len(manual)))
print("번호 찾은청크 넘긴청크 설명서낱말 지시글자 사용자글자 사용자중설명서밖글자")
for t in tot:
    print(*t)
import statistics as st
w = [t[3] for t in tot]
print("설명서 낱말 중앙/평균", st.median(w), round(st.mean(w)), "→ 영어 1낱말≈1.3토큰이면 토큰 중앙", round(st.median(w) * 1.3))
