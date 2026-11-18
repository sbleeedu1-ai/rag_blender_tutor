"""흔히 옮기는 말 목록 전체로 문장을 지어 답 바꾸기를 시험한다(돈 0, 약 25초). HISTORY [375]·[380].

저장된 답 468개(answer_diff.py)에는 안 나오는 목록 말까지 본다. 단위 판정(Fable 5.2 high)이 만든 시험 스크립트를 옮긴 것이다.
1) 한 번에 넣은 결과와 조각으로 흘려 넣은 결과가 다른 자리(다르면 도우미 창에서만 안 바뀜)
2) 화면 글자가 꼬리 낱말로 끝나는데 꼬리가 또 붙는 자리("값(Value) 값")
쓰는 법: .venv/bin/python .claude/tools/list_check.py [코드 폴더(기본: 이 저장소)]. 둘 중 하나라도 0이 아니면 종료 코드 1.
"""
import sys, json, random, re, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; CODE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT
sys.path.insert(0, str(CODE))
import blender_tutor; assert str(CODE) in blender_tutor.__file__
from blender_tutor.menu_names import load_menu_names, COMMON_TAILS
from blender_tutor.answer_engine import _MenuMarks
names = load_menu_names(ROOT / "data"); off = load_menu_names(ROOT / "data"); off._common = {}; off.common_prefixes = set()
raw = json.loads((ROOT / "menu_tables/common_ko.json").read_text(encoding="utf-8"))["lists"]
def run(parts, n=names):
    m = _MenuMarks(n, "메시 추가", ())
    return "".join(m.feed(p) for p in parts) + m.finish()
def pieces(text, seed, hi=6):
    rng, out, i = random.Random(seed), [], 0
    while i < len(text):
        k = rng.randint(1, hi); out.append(text[i:i+k]); i += k
    return out
tx = "여기서 UV 편집기(UV Editor)를 엽니다."
print("UV 한 번에:", run([tx])); print("UV 조각:", run(pieces(tx, 1))); print("UV 목록 끔:", run([tx], off))
# 1) 흐름에서 갈리는 자리의 조각 결과가 '목록을 끈 결과'와 같은가
same = diff = 0; ex = []
for english, vs in raw.items():
    for v in names.common(english):
        text = f"먼저 {v}({english})를 쓰고 다시 봅니다."
        w = run([text]); s = run(pieces(text, 1))
        if s != w:
            o = run([text], off)
            if s == o: same += 1
            else:
                diff += 1
                if len(ex) < 5: ex.append((text, w, s, o))
print("맨 꼴 흐름 갈림: 목록 끈 결과와 같음", same, "다름", diff); [print("  ", e) for e in ex]
# 2) 화면 글자가 꼬리 낱말로 끝나는데 꼬리가 또 붙는가
dup = collections.Counter(); dex = []
sq = lambda s: "".join(s.split())
for english, vs in raw.items():
    found, glyph = names.in_prose(english)
    if not found or not glyph or glyph == english: continue
    for T in COMMON_TAILS:
        if not sq(glyph).endswith(sq(T)): continue
        for v in names.common(english):
            if sq(v).endswith(sq(T)): continue
            text = f"먼저 {v} {T}({english})로 갑니다."
            w = run(pieces(text, 1))
            if re.search(rf"{re.escape(sq(T))}\({re.escape(english)}\){re.escape(sq(T))}", sq(w)):
                dup[T] += 1
                if len(dex) < 12 or english in ("Edit Mode", "Object Mode", "Sculpt Mode", "Preferences", "Render Settings"): dex.append((text, w))
print("꼬리 겹침(조각으로 넣은 결과):", sum(dup.values()), dict(dup)); [print("  ", e) for e in dex[:20]]
sys.exit(1 if diff or sum(dup.values()) else 0)
