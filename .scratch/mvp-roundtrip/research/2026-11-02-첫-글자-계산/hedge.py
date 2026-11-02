import json, statistics as st, random
rows=[json.loads(l) for l in open(r"C:\WORK\rag_blender_tutor\results\20261030\124302_flow_short_vs_long\실행.jsonl",encoding="utf-8")]
L=[r for r in rows if r["조건"]=="흐름 / 3번 합치기"]
secs=[[c["초"] for c in r["호출별"]] for r in L]
emb=[r["시간"]["임베딩"]+r["시간"]["검색"] for r in L]
for n in (1,2,3):
    # 같은 줄 안에서 앞 n개 중 최소(실제 상관 포함)
    m=[min(s[:n]) for s in secs]
    print(f"실제 줄 안 먼저 온 {n}개 중 1개: 중앙 {st.median(m):.3f} 90% {sorted(m)[int(.9*len(m))]:.3f} 2초 넘은 비율(검색 포함) {sum(1 for a,e in zip(m,emb) if a+e>2)/len(m):.2f}")
allc=[x for s in secs for x in s]
random.seed(0)
for n in (1,2,3,5,8):
    m=[min(random.choice(allc) for _ in range(n)) for _ in range(20000)]
    print(f"독립 가정 n={n}: 중앙 {st.median(m):.3f} 90% {sorted(m)[int(.9*len(m))]:.3f}")
# 줄(질문·회차)마다 평균 차이로 상관 보기
rowmeans=[st.mean(s) for s in secs]
print("줄 평균의 표준편차",round(st.pstdev(rowmeans),3),"줄 안 표준편차 평균",round(st.mean(st.pstdev(s) for s in secs),3))
print("호출 최소값 하위: ", sorted(allc)[:5])
