"""첫 글자 시간 실측 프로그램(티켓 44): 가짜 부품으로 기록 모양과, 손으로 만든 기록으로 방법별 단축 계산을 본다(돈이 들지 않음)."""

import itertools

import pytest

from blender_tutor.answer_engine import AnswerEngine, Settings
from blender_tutor.answer_model import FirstOf
from blender_tutor.speed_trial import Calls, Question, TimedAnswer, TimedRewriter, run, score_queries, summarize
from tests.test_answer_engine import ARRAY, BEVEL, CHUNKS, STATE, TOWARD_ARRAY, TOWARD_BEVEL, VECTORS


class Counted:
    """토큰 수를 세는 가짜 모델(질문 바꾸기·답변 둘 다). 부를 때마다 입력 10·출력 2토큰을 더한다."""

    def __init__(self, pieces):
        self.pieces, self.model = pieces, "luna"
        self.input_tokens = self.output_tokens = self.reasoning_tokens = 0

    def stream(self, messages, timeout=None):
        self.input_tokens, self.output_tokens = self.input_tokens + 10, self.output_tokens + 2
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
                 TimedRewriter(Counted(['{"areas": [], "query": "bevel"}']), calls, 1)]
    answer = FirstOf([TimedAnswer(Counted(["답"]), calls, 0)])
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


def _row(rewrites, answers, first, done=9.0, hits=None):
    """손으로 만든 기록 한 줄. rewrites는 (닫힘, 끝), answers는 (보냄, 첫 조각)."""
    calls = [{"종류": "질문 바꾸기", "몇째": i, "보냄": 0.0, "검색어 닫힘": closed, "끝": end,
              "글": '{"query": "q"}', "적중": (hits or [1.0] * 5)[i]} for i, (closed, end) in enumerate(rewrites)]
    calls += [{"종류": "답변", "몇째": i, "보냄": sent, "첫 조각": got, "끝": done, "생각": 0} for i, (sent, got) in enumerate(answers)]
    return {"회차": 1, "질문": "A1", "첫 글자": first, "답 끝": done, "실패": None, "호출": calls}


def test_방법별_단축을_새_호출_없이_기록에서_가른다():
    # 앞 3개 중 가장 먼저 닫힘 1.4·끝 1.6, 넷째가 1.2에 닫혀 쓰임(끝 1.5). 답변 첫째 0.9초, 둘째 0.7초
    row = _row([(1.4, 1.6), (1.5, 1.7), (1.8, 2.0), (1.2, 1.5), (2.0, 2.2)], [(1.5, 2.4), (1.5, 2.2)], first=2.25,
               hits=[0.5, 1.0, 1.0, 1.0, 0.0])
    summary = summarize([row])
    gains = summary["단축(초, 중앙값)"]
    assert gains["방법 1 흘려 받기"] == pytest.approx(0.3)  # 5개 중 먼저 끝남 1.5 − 먼저 닫힘 1.2
    assert gains["방법 2 3→5개"] == pytest.approx(0.2)  # 앞 3개 중 먼저 닫힘 1.4 − 1.2
    assert gains["방법 3 답변 2개"] == pytest.approx(0.2)  # 0.9 − 0.7
    stages = summary["단계(초, 중앙값·최대값)"]
    assert stages["임베딩+검색"][0] == pytest.approx(0.3) and stages["답변 첫 조각(빠른 쪽)"][0] == pytest.approx(0.75)
    assert stages["첫 글자(옛 방식 어림)"][0] == pytest.approx(2.25 + 0.4 + 0.2)  # 앞 3개 중 먼저 끝남 1.6 − 1.2, 답변 0.2
    assert summary["적중(찾은 비율 평균)"] == {
        "쓴 검색어(5개 중 먼저 닫힘)": 1.0, "앞 3개 중 먼저 닫힘": 0.5, "옛 방식(앞 3개 중 먼저 끝남)": 0.5}
    assert summary["query가 첫 칸인 비율"] == 1.0


def test_실패한_질문은_계산에서_뺀다():
    failed = {**_row([(1.0, 1.1)], [(1.2, 2.0)], first=None), "실패": "문제가 생겼어요"}
    assert summarize([failed])["질문 수(실패 뺌)"] == 0
