"""첫 글자 시간 실측 프로그램(티켓 44): 가짜 부품으로 기록 모양과, 손으로 만든 기록으로 흘려 받기로 준 시간·단계 계산을 본다(돈이 들지 않음)."""

import itertools
import time

import pytest

from blender_tutor.answer_engine import AnswerEngine, Settings
from blender_tutor.speed_trial import Calls, Question, TimedAnswer, TimedRewriter, run, score_queries, summarize
from tests.test_answer_engine import ARRAY, BEVEL, CHUNKS, STATE, TOWARD_ARRAY, TOWARD_BEVEL, VECTORS


class Counted:
    """토큰 수를 세는 가짜 모델(질문 바꾸기·답변 둘 다). 부를 때마다 입력 10·출력 2토큰을 더한다."""

    def __init__(self, pieces, wait=0.0):
        self.pieces, self.model, self.wait = pieces, "luna", wait
        self.input_tokens = self.output_tokens = self.reasoning_tokens = 0

    def stream(self, messages, timeout=None):
        self.input_tokens, self.output_tokens = self.input_tokens + 10, self.output_tokens + 2
        time.sleep(self.wait)
        yield from self.pieces

    def dollars(self):
        return 0.0


class Embed:
    def __init__(self):
        self.tokens = 0

    def embed(self, texts, timeout=None):
        return [TOWARD_ARRAY if "array" in text else TOWARD_BEVEL for text in texts]


def test_호출마다_시각과_토큰을_남기고_쓰지_않은_검색어도_채점한다():
    ticks = itertools.count()
    calls = Calls(clock=lambda: next(ticks))  # 시각을 물을 때마다 1초씩 간다
    rewriters = [TimedRewriter(Counted(['{"query": "array', ' copies", "areas": []}']), calls, 0),
                 TimedRewriter(Counted(['{"areas": [], "query": "bevel"}'], wait=0.3), calls, 1)]  # 늦게 와서 쓰이지 않는다
    answer = TimedAnswer(Counted(["답"]), calls, 0)
    engine = AnswerEngine(CHUNKS, VECTORS, Embed(), answer, Settings(top_k=1), rewriters=rewriters)  # 청크가 6개뿐이라 상위 1개로 채점
    keys = {chunk: chunk.address for chunk in CHUNKS}
    question = Question("A1", "배열?", ((ARRAY.address,),))
    rows = run(engine, [question], STATE, calls, keys, rounds=1)
    score_queries(rows, [question], engine, Embed().embed, keys)
    (row,) = rows
    assert row["적중"] == 1.0 and row["첫 글자"] is not None and row["실패"] is None
    by_kind = {(r["종류"], r["몇째"]): r for r in row["호출"]}
    first = by_kind[("질문 바꾸기", 0)]
    assert first["보냄"] < first["첫 조각"] < first["검색어 닫힘"] <= first["끝"]
    assert (first["입력"], first["출력"], first["검색어"], first["적중"]) == (10, 2, "array copies", 1.0)
    assert by_kind[("질문 바꾸기", 1)]["적중"] == 0.0  # 쓰지 않은 검색어도 같은 검색으로 채점
    assert by_kind[("답변", 0)]["글"] == "답"


def _row(rewrites, answer, first, done=9.0, hits=None):
    """손으로 만든 기록 한 줄. rewrites는 (닫힘, 끝), answer는 (보냄, 첫 조각)."""
    calls = [{"종류": "질문 바꾸기", "몇째": i, "보냄": 0.0, "검색어 닫힘": closed, "끝": end,
              "글": '{"query": "q"}', "적중": (hits or [1.0] * 3)[i]} for i, (closed, end) in enumerate(rewrites)]
    calls.append({"종류": "답변", "몇째": 0, "보냄": answer[0], "첫 조각": answer[1], "끝": done, "생각": 0})
    return {"회차": 1, "질문": "A1", "첫 글자": first, "답 끝": done, "실패": None, "호출": calls}


def test_흘려_받기로_준_시간과_단계를_새_호출_없이_기록에서_가른다():
    # 셋째가 1.2에 닫혀 쓰임(끝 1.6). 가장 먼저 끝난 것은 첫째(1.5)라 흘려 받지 않았다면 1.5까지 기다렸다
    row = _row([(1.4, 1.5), (1.45, 1.7), (1.2, 1.6)], (1.5, 2.2), first=2.25, hits=[0.5, 1.0, 1.0])
    summary = summarize([row])
    assert summary["흘려 받기로 준 시간(초, 중앙값·평균)"] == (pytest.approx(0.3), pytest.approx(0.3))
    stages = summary["단계(초, 중앙값·최대값)"]
    assert stages["임베딩+검색"][0] == pytest.approx(0.3) and stages["답변 첫 조각"][0] == pytest.approx(0.75)
    assert stages["첫 글자(흘려 받지 않을 때 어림)"][0] == pytest.approx(2.55)
    assert summary["적중(찾은 비율 평균)"] == {"쓴 검색어(먼저 닫힘)": 1.0, "흘려 받지 않을 때(먼저 끝남)": 0.5}
    assert summary["호출 하나 보냄→첫 조각(초, 중앙값·최소값)"]["답변"] == (pytest.approx(0.7), pytest.approx(0.7))
    assert summary["query가 첫 칸인 비율"] == 1.0


def test_실패한_질문은_계산에서_뺀다():
    failed = {**_row([(1.0, 1.1)], (1.2, 2.0), first=None), "실패": "문제가 생겼어요"}
    assert summarize([failed])["질문 수(실패 뺌)"] == 0


def test_빈_검색어는_닫힘으로_적지_않고_채점하지_않으며_줄마다_바로_넘긴다():
    ticks = itertools.count()
    calls = Calls(clock=lambda: next(ticks))
    rewriters = [TimedRewriter(Counted(['{"query": " ", "areas": []}']), calls, 0),
                 TimedRewriter(Counted(['{"query": "array"}'], wait=0.1), calls, 1)]
    engine = AnswerEngine(CHUNKS, VECTORS, Embed(), TimedAnswer(Counted(["답"]), calls, 0), Settings(top_k=1), rewriters=rewriters)
    keys = {chunk: chunk.address for chunk in CHUNKS}
    question = Question("A1", "배열?", ((ARRAY.address,),))
    kept = []
    rows = run(engine, [question], STATE, calls, keys, rounds=2, keep=kept.append)
    score_queries(rows, [question], engine, Embed().embed, keys)  # 빈 검색어에서 멈추지 않는다
    assert kept == rows and len(rows) == 2
    empty = next(r for r in rows[0]["호출"] if r["몇째"] == 0 and r["종류"] == "질문 바꾸기")
    assert "빈 검색어" in empty and "검색어 닫힘" not in empty and "적중" not in empty
