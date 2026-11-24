"""위 200 리랭킹 제품 대조(돈 0): 차례 13번 위 200 전체 시험에서 저장한 검색어 벡터와 Gemini 확률을 제품 답 엔진에 그대로 넣어 다시 센다.

같은 확률을 같은 rerank에 넣는 것만으로는 아무것도 증명하지 않으므로, 제품의 길을 처음부터 따라간다.
1. 저장한 검색어 벡터 → 제품 AnswerEngine의 뜻 검색 후보(위 rerank_depth) → 시험의 위200.json과 같은 청크 묶음인지(다르면 멈춤),
   차례까지 같은지(같은 글 조각은 벡터가 같아 차례가 위 8 자리를 가른다. 다른 검색어는 따로 센다)
2. 가짜 판정기는 받은 글 묶음이 시험 때 보낸 것과 같은지 보고, 시험에서 그 청크가 받은 확률을 청크마다 돌려준다
3. 제품 _ranked가 고른 위 top_k를 시험 도구의 세는 함수(base.count)로 센다 → 시험 판정.json의 "위 200 다시 세움"과 같아야 한다

예: .venv/bin/python .claude/tools/rerank_replay.py results/20261124/110339_차례13_위200전체
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "data" / "eval" / "dev50")]

import rerank_trial as base  # noqa: E402  (시험 도구: 세는 함수·474실행·정답 청크 묶음)

from blender_tutor import manual_vectors  # noqa: E402
from blender_tutor.answer_engine import AnswerEngine, Settings  # noqa: E402
from blender_tutor.decision_rerank import INSTRUCTION  # noqa: E402


class SavedJudge:
    """시험에서 받은 확률을 돌려주는 판정기. 받은 글이 시험 때 보낸 글과 다르면 멈춘다."""

    def __init__(self, probs: dict, wide: dict, chunks, engine_order: dict):
        self.by_chunk = {q: dict(zip(wide[q], probs[q])) for q in probs}
        self.wide, self.chunks, self.engine_order, self.calls = wide, chunks, engine_order, 0

    def judge(self, query, passages, timeout):
        self.calls += 1
        order = self.engine_order[query]  # 엔진이 이 차례로 글을 보냄(아래 main이 먼저 구해 둠)
        if list(passages) != [self.chunks[c].text for c in order] or set(order) != set(self.wide[query]):
            raise SystemExit(f"보낸 글 묶음이 시험과 다름: {query}")
        return [self.by_chunk[query][c] for c in order]


def main(folder: Path) -> dict:
    chunks, rows_of, needed, runs = base.load_all()
    wide = json.loads((folder / "위200.json").read_text(encoding="utf-8"))
    queries = json.loads((folder / "검색어.json").read_text(encoding="utf-8"))
    vectors = np.load(folder / "검색어벡터.npy")
    probs = {}
    for line in (folder / "받음.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        probs.setdefault(row["검색어"], row["확률"])  # 처음 보낸 것(두 번 보낸 10개는 판정에 쓰지 않음, 시험 judge와 같음)
    stored = manual_vectors.load(manual_vectors.path_for(manual_vectors.MODEL), chunks)
    engine_order = {}
    judge = SavedJudge(probs, wide, chunks, engine_order)
    engine = AnswerEngine(chunks, stored, embedder=None, model=None, settings=Settings(), reranker=judge)
    position = {chunk: i for i, chunk in enumerate(chunks)}
    same_candidates, orders, moved = 0, {}, []
    for q, v in zip(queries, vectors):
        engine_order[q] = engine._by_meaning(v)[: engine.settings.rerank_depth]
        if engine_order[q] == wide[q]:
            same_candidates += 1
        else:
            first = next(i for i, (a, b) in enumerate(zip(engine_order[q], wide[q])) if a != b)
            moved.append({"검색어": q, "처음 다른 자리": first + 1, "같은 글": chunks[engine_order[q][first]].text == chunks[wide[q][first]].text})
        results, failed = engine._ranked(q, v)
        if failed:
            raise SystemExit(f"리랭킹 실패로 셈: {q}")
        orders[q] = [position[chunk] for chunk in results]
    counted = base.count(orders, runs, needed, rows_of)["수"]
    trial = json.loads((folder / "판정.json").read_text(encoding="utf-8"))["위 200 다시 세움"]
    # 시험 차례 그대로 세운 셈(차례가 다른 검색어에서 제품 차례가 셈을 바꾸는지 가르려고)
    trial_order = base.count({q: base.rerank(wide[q], probs[q])[:8] for q in wide}, runs, needed, rows_of)["수"]
    result = {"검색어": len(queries), "후보 위 200이 시험과 차례까지 같음": same_candidates, "차례만 다른 검색어": moved, "판정기 호출": judge.calls,
              "지시 문구가 시험과 같음": INSTRUCTION == base.INSTRUCTION, "센 실행": len(runs), "제품 길로 센 위 8 안": counted,
              "시험 차례로 센 위 8 안": trial_order, "시험 판정.json": trial, "같음": counted == trial}
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return result


if __name__ == "__main__":
    sys.exit(0 if main(Path(sys.argv[1]))["같음"] else 1)
