import json, ast
ROOT=r"C:\WORK\rag_blender_tutor"
gold={}
for f in ["web","ai"]:
    for l in open(ROOT+f"/data/search_compare/questions/{f}_questions.jsonl",encoding="utf-8"):
        r=json.loads(l)
        if not r.get("dropped"): gold[r["id"]]=[set(g["any_of"]) for g in r["answer_groups"]]
out=[]
for l in open(ROOT+r"/results/20261030/102717_full_large_original_scopes/실행.jsonl",encoding="utf-8"):
    r=json.loads(l)
    if r["조건"]!="text-embedding-3-large / 원문만 / BM25 끔": continue
    p=r["부분"]; p=ast.literal_eval(p) if isinstance(p,str) else p
    s=p["뜻"]; res=[c for c,_ in s]
    f=sum(1 for g in gold[r["질문"]] if g & set(res[:8]))
    out.append((s[0][1], s[0][1]-s[7][1], r["질문"], r["회차"], f, len(gold[r["질문"]])))
for t in sorted(out,reverse=True):
    if str(t[3])=="1": print(f"{t[2]:4} 1위점수 {t[0]:.3f} 1위-8위 {t[1]:.3f} 찾음 {t[4]}/{t[5]}")
