"""질문 한 번: 대상 Blender 고르기 → 작업 상태 확인 → 지금 단계 → 대화 → 시간 기록 → 창에 보이기(티켓 39).

실제 도우미 창(helper)과 자동 시험이 이 입구 하나를 함께 쓴다. 창 쪽만 바꿔 끼운다: 실제 창 연결은 helper의 Qt 신호와
스레드, 시험용 연결은 사건을 모으고 그 자리에서 돌린다. 창 그리기·Windows 초점·진행 판정은 여기서 하지 않는다.
"""

from collections.abc import Callable
from typing import Protocol

from blender_tutor import stand_in
from blender_tutor.answer_engine import Event, Failure
from blender_tutor.conversation import Conversation, settings_record
from blender_tutor.course_desk import CourseDesk
from blender_tutor.receiver import Receiver
from blender_tutor.timing import Stopwatch
from blender_tutor.window_rules import FrontBlender

NO_STATE = "Blender 작업 상태를 아직 받지 못했어요. Blender에서 F10을 눌러 주세요."
# 봉투 모양이 바뀐 뒤 설치 명령을 다시 돌리지 않으면 옛 애드온의 봉투를 모두 거절한다. 그때 F10을 눌러도 소용없어서 따로 알린다
OLD_ADDON = "Blender의 도우미 애드온이 도우미와 판이 달라요. 설치 명령을 다시 돌리고 Blender를 다시 켜 주세요."


class WindowSide(Protocol):
    """창 쪽 연결. 실제 창(helper)과 시험용 두 가지만 둔다."""

    def show(self, event: Event) -> None:
        """답 사건 하나를 창에 보인다. 답 만들기 스레드에서도 불린다."""

    def start(self, work: Callable[[], None]) -> None:
        """답을 기다리는 일을 돌린다(실제 창은 창과 Blender가 멈추지 않게 따로 돌린다)."""


class QuestionFlow:
    """도우미 창에서 보낸 질문 하나를 끝까지 처리한다. 질문을 보낸 화면 스레드에서 ask를 부른다."""

    def __init__(
        self,
        receiver: Receiver,
        front: FrontBlender,
        desk: CourseDesk,
        conversation: Conversation,
        stopwatch: Stopwatch,
        window_side: WindowSide,
    ):
        self._receiver = receiver
        self._front = front
        self._desk = desk
        self._conversation = conversation
        self._stopwatch = stopwatch
        self._window_side = window_side

    def ask(self, question: str) -> None:
        lap = self._stopwatch.asked(question, self._engine_info())
        window = self._front.window(self._receiver.blenders())
        state = None if window is None else self._receiver.latest(window)
        if state is None:  # 실패도 한 줄 남긴다(F10 시각이 다음 질문으로 넘어가지 않게)
            failure = Failure(OLD_ADDON if self._receiver.rejected else NO_STATE)
            lap.saw(failure)
            self._window_side.show(failure)
            return

        step = self._desk.step(window)  # 답이 끝나도 진행은 그대로라 카드는 같은 단계에 머문다

        def work() -> None:
            for event in self._conversation.ask(question, state, step):
                lap.saw(event)
                self._window_side.show(event)

        self._window_side.start(work)

    def _engine_info(self) -> dict | None:
        """시간 기록에 남길 엔진 이름과 설정. 엔진 준비 전이면 None."""
        engine = self._conversation.engine
        if engine is None:
            return None
        return {"name": stand_in.NAME, "settings": settings_record(engine.settings, self._conversation.recent_pairs)}
