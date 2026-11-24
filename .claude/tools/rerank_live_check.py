"""위 200 리랭킹 실제 키 확인(유료, Google): 제품 판정기(DecisionReranker)가 진짜 Gemini 답을 바르게 풀고, 보낸 요청이 차례 13번 시험과 같은지 본다.

돈 0 대조(rerank_replay.py)는 가짜 판정기라 제품 judge가 실제 응답을 푼 적이 없다. 이 도구가 그 빈칸을 채운다.
- 시험 위200.json과 후보 차례까지 같은 검색어에서 앞 N개를 고른다(저장한 벡터를 써서 임베딩 호출 없음)
- 제품 AnswerEngine._ranked에 진짜 판정기를 끼워 돌리고, 검색마다 걸린 초·입력 토큰·실패를 센다
- 청크마다 받은 확률을 시험 받음.jsonl의 확률과 견준다(같은 요청이면 차가 거의 0, 시험의 같은 조각 두 번 보냄 차 최대 1.6e-8)

통과 줄: 리랭킹 실패 0, 검색 한 번 입력 토큰 약 4만(시험 평균), 확률 차 최대 1e-6 이하.
예: .venv/bin/python .claude/tools/rerank_live_check.py results/20261124/110339_차례13_위200전체 10
"""

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "data" / "eval" / "dev50")]

import rerank_trial as base  # noqa: E402  (시험 도구: 청크 읽기)

from blender_tutor import manual_vectors  # noqa: E402
from blender_tutor.answer_engine import AnswerEngine, Settings  # noqa: E402
from blender_tutor.decision_rerank import DecisionReranker, gemini_key  # noqa: E402


class Timed:
    """진짜 판정기를 감싸 검색마다 걸린 초와 받은 확률을 남긴다."""

    def __init__(self, inner: DecisionReranker):
        self.inner, self.seconds, self.got = inner, [], {}

    def judge(self, query, passages, timeout):
        start = time.perf_counter()
        probs = self.inner.judge(query, passages, timeout)
        self.seconds.append(time.perf_counter() - start)
        self.got[query] = probs
        return probs


def main(folder: Path, n: int) -> dict:
    chunks, _rows_of, _needed, _runs = base.load_all()
    wide = json.loads((folder / "위200.json").read_text(encoding="utf-8"))
    queries = json.loads((folder / "검색어.json").read_text(encoding="utf-8"))
    vectors = np.load(folder / "검색어벡터.npy")
    saved = {}
    for line in (folder / "받음.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        saved.setdefault(row["검색어"], row["확률"])
    stored = manual_vectors.load(manual_vectors.path_for(manual_vectors.MODEL), chunks)
    judge = Timed(DecisionReranker(gemini_key()))
    engine = AnswerEngine(chunks, stored, embedder=None, model=None, settings=Settings(), reranker=judge)
    picked = [(q, v) for q, v in zip(queries, vectors) if engine._by_meaning(v)[: engine.settings.rerank_depth] == wide[q]][:n]
    failed, diffs = 0, []
    for q, v in picked:
        _results, rerank_failed = engine._ranked(q, v)
        failed += rerank_failed
        if not rerank_failed:
            diffs.append(max(abs(a - b) for a, b in zip(judge.got[q], saved[q])))
    tokens = judge.inner.input_tokens
    result = {"고른 검색어": len(picked), "리랭킹 실패": failed, "요청": judge.inner.requests,
              "입력 토큰 합": tokens, "검색 한 번 입력 토큰": round(tokens / max(judge.inner.requests, 1)),
              "요금(달러)": judge.inner.dollars(), "왕복 초(중앙·최대)": [round(statistics.median(judge.seconds), 3), round(max(judge.seconds), 3)] if judge.seconds else None,
              "확률 차 최대": max(diffs) if diffs else None, "확률 차 검색어별": diffs}
    result["통과"] = failed == 0 and bool(diffs) and max(diffs) <= 1e-6
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return result


if __name__ == "__main__":
    sys.exit(0 if main(Path(sys.argv[1]), int(sys.argv[2]))["통과"] else 1)
