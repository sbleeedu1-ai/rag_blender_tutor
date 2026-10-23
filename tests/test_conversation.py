"""대화(티켓 26): 최근 대화 3쌍을 들고 답 엔진을 부른다. 가짜 엔진을 끼워 엔진이 받은 최근 대화와 창에 나간 것을 본다."""

import logging

from blender_tutor.answer_engine import Done, Failure, Piece
from blender_tutor.conversation import NOT_READY, PROGRAM_ERROR, Conversation
from blender_tutor.work_state import WorkState
from tests.examples import EDITING

STATE = WorkState.from_json(EDITING)


class FakeEngine:
    """질문마다 정해 둔 사건을 낸다. 받은 최근 대화를 적어 둔다."""

    def __init__(self, events=None, error: Exception | None = None):
        self.events = events
        self.error = error
        self.recent: list[list[tuple[str, str]]] = []

    def answer(self, question, state, recent, step=None):
        self.recent.append(list(recent))
        assert state is STATE and step is None
        yield from self.events or [Piece(f"{question}의 "), Piece("답"), Done((), ())]
        if self.error:
            raise self.error


def ask(conversation: Conversation, question: str) -> list:
    return list(conversation.ask(question, STATE))


def test_최근_대화는_질문과_답_글_3쌍만_엔진에_넘긴다():
    conversation = Conversation()
    conversation.engine = engine = FakeEngine()
    for question in ("가", "나", "다", "라", "마"):
        ask(conversation, question)
    assert engine.recent[0] == []
    assert engine.recent[1] == [("가", "가의 답")]
    assert engine.recent[4] == [("나", "나의 답"), ("다", "다의 답"), ("라", "라의 답")]


def test_오류로_끝난_답은_최근_대화에_넣지_않는다():
    conversation = Conversation()
    conversation.engine = FakeEngine([Piece("반쯤 "), Failure("잠시 뒤 다시 물어봐 주세요.")])
    assert ask(conversation, "가") == [Piece("반쯤 "), Failure("잠시 뒤 다시 물어봐 주세요.")]
    conversation.engine = engine = FakeEngine()
    ask(conversation, "나")
    assert engine.recent == [[]]


def test_엔진의_버그는_짧은_문구로_바꾸고_기록에_남기고_계속_쓴다(caplog):
    conversation = Conversation()
    conversation.engine = FakeEngine([Piece("반쯤 ")], error=KeyError("없는 칸"))
    with caplog.at_level(logging.ERROR):
        assert ask(conversation, "가") == [Piece("반쯤 "), Failure(PROGRAM_ERROR)]
    assert "없는 칸" in caplog.text
    conversation.engine = engine = FakeEngine()
    assert ask(conversation, "나")[-1] == Done((), ())
    assert engine.recent == [[]]


def test_엔진이_준비되기_전에는_기다리라는_문구():
    conversation = Conversation()
    assert ask(conversation, "가") == [Failure(NOT_READY)]
    conversation.waiting_message = "설명서 자료가 없어요."
    assert ask(conversation, "가") == [Failure("설명서 자료가 없어요.")]
