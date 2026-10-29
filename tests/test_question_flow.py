"""질문 한 번(티켓 39): 대상 Blender 고르기 → 작업 상태 확인 → 지금 단계 → 대화 → 시간 기록 → 창에 보이기를 화면 없이 본다.

받는 쪽·진행 관리·대화·시간 기록은 진짜를 쓰고, 창 쪽 연결과 답 엔진만 가짜로 바꿔 끼운다.
작업 상태는 test_receiver처럼 애드온인 척 내 PC 안 HTTP로 보낸다.
"""

import json

import pytest

from blender_tutor.answer_engine import Done, Failure, Piece, Settings
from blender_tutor.conversation import Conversation
from blender_tutor.course_desk import CourseDesk
from blender_tutor.progress import Course, Step
from blender_tutor.question_flow import NO_STATE, OLD_ADDON, QuestionFlow
from blender_tutor.receiver import FileEvent, Receiver
from blender_tutor.timing import Stopwatch
from blender_tutor.work_state import WorkState
from blender_tutor.window_rules import FrontBlender
from tests.examples import EDITING, TOKEN, send

OBJECT_MODE = {**EDITING, "mode": "OBJECT", "edit_selected": {}}
SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("join", "부품 합치기")))


class Collected:
    """시험용 창 쪽 연결: 창에 보일 답 사건을 모으고, 답을 기다리는 일은 그 자리에서 바로 돌린다."""

    def __init__(self):
        self.shown: list = []

    def show(self, event) -> None:
        self.shown.append(event)

    def start(self, work) -> None:
        work()


class FakeEngine:
    """질문마다 정해 둔 사건을 낸다. 받은 작업 상태·최근 대화·단계를 적어 둔다."""

    settings = Settings()
    name = "stand_in"

    def __init__(self, events=None):
        self.events = events
        self.got: list[tuple] = []

    def answer(self, question, state, recent, step=None):
        self.got.append((state, list(recent), step))
        yield from self.events or [Piece(f"{question}의 "), Piece("답"), Done((), ())]


@pytest.fixture
def receiver():
    with Receiver(TOKEN, process_started={100: 1.0, 200: 2.0}.get, port=0) as receiver:
        yield receiver


@pytest.fixture
def side():
    return Collected()


@pytest.fixture
def front():
    return FrontBlender()


@pytest.fixture
def desk(tmp_path):
    return CourseDesk([SWORD], tmp_path / "progress")


@pytest.fixture
def make(tmp_path, receiver, front, desk, side):
    def make(engine=None) -> QuestionFlow:
        conversation = Conversation()
        conversation.engine = engine
        return QuestionFlow(receiver, front, desk, conversation, Stopwatch(tmp_path / "timings.jsonl", "PC"), side)

    return make


def timings(tmp_path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "timings.jsonl").read_text(encoding="utf-8").splitlines()]


def test_작업_상태가_없으면_F10_안내를_보이고_실패_한_줄을_남긴다(tmp_path, make, side):
    make().ask("칼끝은 어떻게 모아요?")
    assert side.shown == [Failure(NO_STATE)]
    [line] = timings(tmp_path)
    assert (line["question"], line["outcome"], line["first_piece"]) == ("칼끝은 어떻게 모아요?", "failure", None)


def test_옛_애드온의_봉투만_받았으면_다시_설치하라고_안내한다(make, receiver, side):
    old_addon = {"window": 1, "pid": 100, "state": EDITING, "summon": True, "event": None}  # 누른 시각 칸이 없음
    assert send(receiver, 1, 100, body=old_addon) == 400
    make().ask("칼끝은 어떻게 모아요?")
    assert side.shown == [Failure(OLD_ADDON)]


def test_F10을_누른_Blender의_작업_상태와_지금_단계로_답하고_끝난_줄을_남긴다(tmp_path, make, receiver, front, desk, side):
    send(receiver, 1, 100, EDITING)
    send(receiver, 2, 200, OBJECT_MODE)
    front.summoned(2)
    desk.on_message(2, WorkState.from_json(OBJECT_MODE), FileEvent("opened", ""))
    desk.choose(2, "sword")
    desk.forward(2)  # 2단계(부품 합치기)
    make(engine := FakeEngine()).ask("합치려면?")
    assert engine.got == [(WorkState.from_json(OBJECT_MODE), [], SWORD.steps[1])]
    assert side.shown == [Piece("합치려면?의 "), Piece("답"), Done((), ())]
    [line] = timings(tmp_path)
    assert (line["engine"], line["settings"]["recent_pairs"], line["outcome"]) == ("stand_in", 3, "done")
    assert line["first_piece"] is not None


def test_중간에_실패한_답은_다음_질문의_최근_대화에_들어가지_않는다(tmp_path, make, receiver, side):
    send(receiver, 1, 100, EDITING)
    flow = make(engine := FakeEngine([Piece("반쯤 "), Failure("잠시 뒤 다시 물어봐 주세요.")]))
    flow.ask("가")
    engine.events = None
    flow.ask("나")
    flow.ask("다")  # 끝난 "나"는 들어가야 "가"가 빠진 이유가 실패해서임을 안다
    assert [recent for _, recent, _ in engine.got] == [[], [], [("나", "나의 답")]]
    assert [line["outcome"] for line in timings(tmp_path)] == ["failure", "done", "done"]
