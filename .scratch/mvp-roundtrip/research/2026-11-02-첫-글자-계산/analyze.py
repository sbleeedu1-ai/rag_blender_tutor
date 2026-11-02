"""저장소 결과 파일만으로 흐름 바꾸기 효과를 어림한다(새 API 호출 없음)."""
import json, statistics as st, sys, ast
from pathlib import Path

ROOT = Path(r"C:\WORK\rag_blender_tutor")
R = ROOT / "results" / "20261030"
K = 8

gold = {}
for f in ["web", "ai"]:
    for l in open(ROOT / f"data/search_compare/questions/{f}_questions.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r.get("dropped"):
            continue
        gold[r["id"]] = [set(g["any_of"]) for g in r["answer_groups"]]


def found(qid, results, k=K):
    top = set(results[:k])
    return sum(1 for g in gold[qid] if g & top)


def ratio(pairs):  # pairs: (qid, results)
    f = sum(found(q, r) for q, r in pairs)
    n = sum(len(gold[q]) for q, r in pairs)
    return f / n


def as_list(v):
    return v if isinstance(v, list) else ast.literal_eval(v)


# 1) 긴 지시 3번 동시: 호출별 시간·결과
rows = [json.loads(l) for l in open(R / "124302_flow_short_vs_long/실행.jsonl", encoding="utf-8")]
long_rows = [r for r in rows if r["조건"] == "흐름 / 3번 합치기"]
short_rows = [r for r in rows if r["조건"] == "흐름 / 짧은 지시 3번"]

first = []  # (qid, round, sec_rewrite, embed, search, results, query)
for r in long_rows:
    c = min(r["호출별"], key=lambda c: c["초"])
    first.append((r["질문"], r["회차"], c["초"], r["시간"]["임베딩"], r["시간"]["검색"], c["결과"], c["검색어"]))

print("== 먼저 온 1개 (긴 지시, 모든 회차) ==")
print("적중(상위8):", round(ratio([(q, res) for q, _, _, _, _, res, _ in first]), 3))
tot = [s + e + x for _, _, s, e, x, _, _ in first]
print("바꾸기 중앙:", round(st.median([s for _, _, s, *_ in first]), 3), "임베딩 중앙:", round(st.median([e for *_, e, _, _, _ in [(a, b, c, d, e, f, g) for a, b, c, d, e, f, g in first]]), 3))
print("검색까지 중앙/최대:", round(st.median(tot), 3), round(max(tot), 3))

# 2) 바꾸기 출력 중 query 몫: 낱말 수
allcalls = [c for r in long_rows for c in r["호출별"]]
qwords = [len(c["검색어"].split()) for c in allcalls]
print("\n== 검색어 길이 (긴 지시) ==")
print("검색어 낱말 수 중앙/평균:", st.median(qwords), round(st.mean(qwords), 1))
print("긴 지시 출력 토큰 평균:", round(8020 / 180, 1), " 짧은 지시:", round(4704 / 180, 1))
scalls = [c for r in short_rows for c in r["호출별"]]
print("짧은 지시 검색어 낱말 수 평균:", round(st.mean(len(c['검색어'].split()) for c in scalls), 1))
print("호출 하나 중앙(초) 긴/짧은:", round(st.median(c["초"] for c in allcalls), 3), round(st.median(c["초"] for c in scalls), 3))
# 호출 시간 vs 검색어 낱말 수 상관(긴 지시)
xs, ys = qwords, [c["초"] for c in allcalls]
mx, my = st.mean(xs), st.mean(ys)
cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / len(xs)
vx = sum((x - mx) ** 2 for x in xs) / len(xs)
vy = sum((y - my) ** 2 for y in ys) / len(ys)
print("상관계수:", round(cov / (vx * vy) ** 0.5, 3), "기울기(초/낱말):", round(cov / vx, 4))
# 회차 1의 첫 요청 제외
xs2 = [len(c["검색어"].split()) for r in long_rows if not (r["회차"] == 1 and r["질문"] == "W1") for c in r["호출별"]]
ys2 = [c["초"] for r in long_rows if not (r["회차"] == 1 and r["질문"] == "W1") for c in r["호출별"]]
mx, my = st.mean(xs2), st.mean(ys2)
cov = sum((x - mx) * (y - my) for x, y in zip(xs2, ys2)) / len(xs2)
vx = sum((x - mx) ** 2 for x in xs2) / len(xs2)
print("첫 요청 뺀 기울기(초/낱말):", round(cov / vx, 4))

# 3) 질문별: 한국어 그대로 / 번역만 / 먼저 온 1개
def by_q(path, cond):
    out = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        if r["조건"] == cond and str(r["회차"]) == "1":
            out[r["질문"]] = (as_list(r["결과"]), ast.literal_eval(r["시간"]) if isinstance(r["시간"], str) else r["시간"])
    return out

ko = by_q(R / "102717_full_large_original_scopes/실행.jsonl", "text-embedding-3-large / 원문만 / BM25 끔")
tr = by_q(R / "113346_full_large_translated/실행.jsonl", "text-embedding-3-large / 원문만 / BM25 끔")
fa1 = {q: res for q, rd, _, _, _, res, _ in first if rd == 1}
print("\n== 질문별 상위8 찾은 수/필요 (1회차) ==")
print("질문  한국어그대로  번역만  먼저온1개")
for q in gold:
    print(q, f"{found(q, ko[q][0])}/{len(gold[q])}", f"{found(q, tr[q][0])}/{len(gold[q])}", f"{found(q, fa1[q])}/{len(gold[q])}")
print("합계 한국어:", round(ratio([(q, ko[q][0]) for q in gold]), 3), "번역:", round(ratio([(q, tr[q][0]) for q in gold]), 3), "먼저온1개:", round(ratio([(q, fa1[q]) for q in gold]), 3))

# 4) 고르기(라우팅): 질문에 공식 기능 이름(영어 또는 음역)이 있으면 바꾸기를 건너뛰고 한국어 그대로 검색
named = ["W1", "W2", "W3", "W4", "W5", "W6", "W8", "A11"]  # 손으로 고름(아래 문서에 근거)
for label, skip in [("이름 든 8문항을 한국어 그대로", ko), ("이름 든 8문항을 번역만(호출은 남음)", tr)]:
    pairs = [(q, skip[q][0] if q in named else fa1[q]) for q in gold]
    print(label, "→ 전체 적중", round(ratio(pairs), 3),
          "| 이름 든 문항만: 고르기", round(ratio([(q, skip[q][0]) for q in named]), 3),
          "바꾸기", round(ratio([(q, fa1[q]) for q in named]), 3))

# 5) 겹쳐 돌리기: 한국어 그대로 결과와 먼저 온 1개 결과를 RRF로 섞으면?
def rrf(lists, k=60):
    sc = {}
    for L in lists:
        for i, c in enumerate(L):
            sc[c] = sc.get(c, 0) + 1 / (k + i + 1)
    return [c for c, _ in sorted(sc.items(), key=lambda x: -x[1])]
print("\n먼저온1개 + 한국어그대로 RRF:", round(ratio([(q, rrf([fa1[q], ko[q][0]])) for q in gold]), 3))
print("먼저온1개 + 번역만 RRF:", round(ratio([(q, rrf([fa1[q], tr[q][0]])) for q in gold]), 3))
# 한국어 그대로 상위 8개 중 몇 개가 먼저온1개 상위8에도 있나(겹쳐 돌린 검색이 쓸모 있나)
ov = [len(set(ko[q][0][:8]) & set(fa1[q][:8])) for q in gold]
print("한국어 그대로 상위8과 바꾼 검색 상위8의 겹침 평균:", round(st.mean(ov), 2))

# 6) 첫 검색어만으로 근거 제목이 맞는가: 먼저 온 검색어에 정답 쪽 이름이 들었나(화면에 먼저 흘릴 값의 질)
print("\n== 먼저 온 검색어 (1회차) ==")
for q, rd, s, *_ , res, qq in first:
    if rd == 1:
        print(q, round(s, 2), qq[:90])
