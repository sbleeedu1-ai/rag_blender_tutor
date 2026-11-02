"""같은 줄(같은 순간) 호출끼리 함께 느려지는 것을 살려 n개 동시의 '먼저 온 1개'를 흉내 낸다(API 호출 없음).
모형: 호출 시간 = 줄 평균 + 줄 안 흔들림. 줄 평균은 실제 60줄에서, 흔들림은 실제 줄 안 편차(평균을 뺀 값 180개)에서 뽑는다."""
import json, random, statistics as st
rows = [json.loads(l) for l in open(r"C:\WORK\rag_blender_tutor\results\20261030\124302_flow_short_vs_long\실행.jsonl", encoding="utf-8")]
L = [r for r in rows if r["조건"] == "흐름 / 3번 합치기"]
secs = [[c["초"] for c in r["호출별"]] for r in L]
means = [st.mean(s) for s in secs]
resid = [x - m for s, m in zip(secs, means) for x in s]
# 3개 줄 안 편차는 표본 3개라 실제 흔들림보다 작다(자유도 보정: sqrt(3/2) 배)
k = (3 / 2) ** 0.5
random.seed(1)
for n in (1, 2, 3, 4, 5, 8):
    m = []
    for _ in range(20000):
        base = random.choice(means)
        m.append(min(base + k * random.choice(resid) for _ in range(n)))
    m.sort()
    print(f"n={n}: 중앙 {st.median(m):.3f}  90% {m[int(.9*len(m))]:.3f}")
