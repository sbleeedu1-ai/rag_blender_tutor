"""도우미 프로그램 입구: 받는 쪽 + 도우미 창 + 진행 관리 + 답 엔진을 한 프로그램으로 잇는다(명세 "전체 구성", ADR-0001, 티켓 26·27).

애드온이 Blender를 켤 때 켜 준다(config.json의 명령). 마지막 Blender가 닫히거나 트레이에서 끝내면 끝난다.
손으로 켤 때: `set BLENDER_TUTOR_TOKEN=<애드온 폴더 config.json의 token>` 뒤 `.venv\\Scripts\\python -m blender_tutor.helper`

부품끼리 잇기만 한다. 판단은 window_rules, 대화는 conversation, 진행은 course_desk, 그리기는 helper_window에 있고 각각 시험한다.
이 파일과 winapi는 실제 화면·Blender가 있어야 해서 애드온 자체 시험과 눈 확인으로 본다.
"""

import argparse
import logging
import os
import platform
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from blender_tutor import stand_in, winapi
from blender_tutor.answer_engine import Failure
from blender_tutor.conversation import PROGRAM_ERROR, Conversation, settings_record
from blender_tutor.course_desk import CourseDesk, Line
from blender_tutor.helper_window import FONT, HelperWindow, Tray
from blender_tutor.paths import COURSES, PROJECT, default_progress_records
from blender_tutor.progress import Course, load_courses
from blender_tutor.receiver import PORT, TOKEN_ENV, Message, Receiver
from blender_tutor.stand_in import build_engine
from blender_tutor.state_stream import RecordingDesk
from blender_tutor.timing import Stopwatch
from blender_tutor.window_rules import FrontBlender, Place, Screen, needs_move, place

FOLLOW_EVERY_MS = 100  # Blender를 따라 창 자리를 다시 보는 간격
# 작업 상태 흐름을 늘 기록한다(검수 동안 쓰려고, 2026-10-26 사용자 결정). 코드 동결 전에 False로 바꾼다(티켓 37)
RECORD_STREAM = True
NO_DATA = "설명서 자료(data/)가 없어 답할 수 없어요. HANDOFF.md의 'data/ 다시 만들기'를 봐 주세요."
NO_STATE = "Blender 작업 상태를 아직 받지 못했어요. Blender에서 F10을 눌러 주세요."
# 봉투 모양이 바뀐 뒤 설치 명령을 다시 돌리지 않으면 옛 애드온의 봉투를 모두 거절한다. 그때 F10을 눌러도 소용없어서 따로 알린다
OLD_ADDON = "Blender의 도우미 애드온이 도우미와 판이 달라요. 설치 명령을 다시 돌리고 Blender를 다시 켜 주세요."

log = logging.getLogger(__name__)


class _Bridge(QObject):
    """다른 스레드(받는 쪽·답 만들기·엔진 준비)에서 화면 스레드로 넘기는 신호. Qt가 화면 스레드에서 차례로 부른다."""

    summoned = Signal(int, object)  # F10을 누른 Blender 창 번호, 누른 시각(없으면 None)
    message = Signal(object)  # 받은 봉투(진행 관리에 넘긴다)
    answer_event = Signal(object)  # 답 사건(Piece·Done·Failure)
    no_blender = Signal()  # 켜진 Blender가 없어 끝낼 때


class Helper:
    """도우미 창 하나와 그 둘레: Blender 따라가기, F10·Esc·트레이, 질문 → 답 엔진, 연습 과정 카드 ↔ 진행 관리(course_desk)."""

    def __init__(self, app: QApplication, receiver: Receiver, bridge: _Bridge):
        self._receiver = receiver
        self._bridge = bridge
        self._front = FrontBlender()
        self._conversation = Conversation()
        self._courses = _courses()
        records = default_progress_records()
        self._desk = _recording(CourseDesk(self._courses, records), records, records.parent / "streams")
        self._stopwatch = Stopwatch(records.parent / "timings.jsonl", platform.node())
        self._own_pid = os.getpid()
        self._moved: tuple[Place, int] | None = None  # 지난번에 옮긴 (자리, 그때 앞 창 번호)
        self._progress_of: int | None = None  # 연습 과정 카드에 진행을 보이는 Blender 창 번호
        self.window = HelperWindow()
        self._tray = Tray(self._tray_show, app.quit)
        self.window.asked.connect(self._ask)
        self.window.escape.connect(self._back_to_blender)
        self.window.chose_course.connect(lambda label: self._on_card(lambda window: self._desk.choose(window, label)))
        self.window.went_next.connect(lambda: self._on_card(self._desk.forward, to_blender=True))
        self.window.went_back.connect(lambda: self._on_card(self._desk.back, to_blender=True))
        self.window.skipped_to.connect(lambda label: self._on_card(lambda window: self._desk.skip_to(window, label), to_blender=True))
        self.window.answered.connect(lambda yes: self._on_card(lambda window: self._desk.answer(window, yes), to_blender=True))
        bridge.summoned.connect(self._summon)
        bridge.message.connect(self._on_message)
        bridge.answer_event.connect(self.window.show_answer_event)
        self._show_progress()
        self._timer = QTimer(interval=FOLLOW_EVERY_MS, timeout=self._follow)
        self._timer.start()
        threading.Thread(target=self._prepare_engine, daemon=True).start()

    def on_message(self, message: Message) -> None:
        """받는 쪽 스레드에서 봉투마다 불린다. 다른 Blender 봉투가 막히지 않게 화면 일은 넘기고 바로 돌아온다."""
        if message.event:
            log.info("창 %s: %s %s", message.window, message.event.kind, message.event.path)
        self._bridge.message.emit(message)
        if message.summon:
            self._bridge.summoned.emit(message.window, message.pressed)

    def _prepare_engine(self) -> None:
        """설명서를 읽어 엔진을 만든다(약 2초). 창은 먼저 떠 있고, 그동안 물으면 '읽는 중' 문구를 보인다."""
        started = time.perf_counter()
        try:
            self._conversation.engine = build_engine(PROJECT / "data", courses=self._courses)
        except FileNotFoundError as error:
            log.warning("설명서 자료가 없음: %s", error)
            self._conversation.waiting_message = NO_DATA
            return
        except Exception:
            log.exception("답 엔진을 만들지 못함")
            self._conversation.waiting_message = PROGRAM_ERROR
            return
        log.info("답 엔진 준비 %.1f초(임시 엔진: 낱말 세기 임베딩 + 가짜 답변, 티켓 31·33에서 진짜로)", time.perf_counter() - started)

    # ---- 질문
    def _ask(self, question: str) -> None:
        lap = self._stopwatch.asked(question, self._engine_info())
        window = self._front.window(self._receiver.blenders())
        state = None if window is None else self._receiver.latest(window)
        if state is None:  # 실패도 한 줄 남긴다(F10 시각이 다음 질문으로 넘어가지 않게)
            failure = Failure(OLD_ADDON if self._receiver.rejected else NO_STATE)
            lap.saw(failure)
            self.window.show_answer_event(failure)
            return

        step = self._desk.step(window)  # 답이 끝나도 진행은 그대로라 카드는 같은 단계에 머문다

        def work() -> None:  # 답을 기다리는 동안 창과 Blender가 멈추지 않게 따로 돈다
            for event in self._conversation.ask(question, state, step):
                lap.saw(event)
                self._bridge.answer_event.emit(event)

        threading.Thread(target=work, daemon=True).start()

    def _engine_info(self) -> dict | None:
        """시간 기록에 남길 엔진 이름과 설정. 엔진 준비 전이면 None."""
        engine = self._conversation.engine
        if engine is None:
            return None
        return {"name": stand_in.NAME, "settings": settings_record(engine.settings, self._conversation.recent_pairs)}

    # ---- 연습 과정(진행 관리는 창 번호마다 하나, course_desk)
    def _on_message(self, message: Message) -> None:
        """화면 스레드에서: 봉투의 파일 사건·작업 상태를 그 Blender의 진행 관리에 넘긴다.

        대화에는 지금 보이는(마지막으로 앞에 있던) Blender의 말만 붙인다. 뒤에 있는 Blender의 알림은 course_desk가
        모아 두었다가 그 Blender로 옮겨 올 때 보인다.
        """
        shown = message.window == self._front.window(self._receiver.blenders())
        self._show_lines(self._desk.on_message(message.window, message.state, message.event, shown))
        self._show_progress()

    def _on_card(self, action: Callable[[int], list[Line]], to_blender: bool = False) -> None:
        """카드 버튼·[네]/[아니요]: 지금 카드에 보이는 Blender의 진행 관리에 넘긴다.

        to_blender면 누른 뒤 Esc처럼 Blender로 초점을 돌린다. 누르고 나면 보통 Blender에서 조작을 이어 하므로,
        Blender를 한 번 더 누르지 않아도 단축키가 들게 하려는 것이다(2026-10-26 사용자 요청, HISTORY [55]).
        연습 과정 고르기는 고른 뒤 안내를 읽을 때라 돌리지 않는다.
        """
        if self._progress_of is not None:
            self._show_lines(action(self._progress_of))
        self._show_progress()
        if to_blender:
            self._back_to_blender()

    def _show_lines(self, lines: list[Line]) -> None:
        for line in lines:
            self.window.show_line(line)

    def _show_progress(self) -> None:
        """마지막으로 앞에 있던 Blender의 진행을 카드에 그린다. 닫힌 Blender의 진행은 버린다(기록은 파일에 남음)."""
        blenders = self._receiver.blenders()
        self._desk.keep(set(blenders))
        front = self._front.window(blenders)
        if front is not None and front != self._progress_of:  # 다른 Blender로 옮겨 왔다: 그 Blender의 지금 자리를 알려 준다
            self._show_lines(self._desk.switched_to(front))
        self._progress_of = front
        view = None if front is None else self._desk.view(front)
        self.window.show_progress(view, self._courses)

    # ---- 부르기·돌아가기
    def _summon(self, window: int, pressed: float | None) -> None:
        """F10: 그 Blender를 '앞에 있던 Blender'로 삼고 창을 맨 위로, 입력칸에 초점. 시각은 시간 기록에 남긴다."""
        self._stopwatch.summoned(pressed)
        started = time.perf_counter()
        self._front.summoned(window)
        self._show_progress()
        self._bring_up()
        self._stopwatch.ready()
        log.info("F10 받음 → 입력 가능 %.0fms", 1000 * (time.perf_counter() - started))

    def _bring_up(self) -> None:
        self.window.summon()
        hwnd = int(self.window.winId())
        winapi.put_on_top(hwnd)
        if not winapi.bring_forward(hwnd):
            log.info("Windows가 앞으로 가져오기를 막음(입력칸 초점 없음)")
        self._moved = (Place.TOP, hwnd)

    def _tray_show(self) -> None:
        """트레이 보이기: 보이는 Blender가 있으면 F10과 똑같이, 모두 최소화면 막는다(안내는 아이콘 글)."""
        if winapi.any_shown(self._receiver.blenders()):
            self._bring_up()

    def _back_to_blender(self) -> None:
        """Esc: 마지막으로 앞에 있던 Blender로 초점을 돌린다(창은 그대로, Blender가 앞이니 그 위에 남는다)."""
        window = self._front.window(self._receiver.blenders())
        if window:
            winapi.bring_forward(window)

    # ---- Blender 따라가기(0.1초마다)
    def _follow(self) -> None:
        blenders = self._receiver.blenders()
        front_hwnd, front_pid, taskbar = winapi.foreground()
        self._front.saw_foreground(front_pid, blenders)
        if self._front.window(blenders) != self._progress_of:  # 다른 Blender로 옮겨 갔거나 닫혔다
            self._show_progress()
        shown = winapi.any_shown(blenders)
        self._tray.blender_shown(shown)
        screen = Screen(front_pid, taskbar, frozenset(blenders.values()), shown)
        where = place(screen, self._own_pid, self.window.put_away)
        if not needs_move(where, front_hwnd, self._moved):
            return
        hwnd = int(self.window.winId())
        if where == Place.HIDDEN:
            self.window.hide()
        else:
            self.window.show()  # 초점은 빼앗지 않는다(WA_ShowWithoutActivating)
            if where == Place.TOP:
                winapi.put_on_top(hwnd)
            else:
                winapi.put_behind(hwnd, front_hwnd)
        self._moved = (where, front_hwnd)


def _recording(desk: CourseDesk, records: Path, folder: Path) -> CourseDesk | RecordingDesk:
    """RECORD_STREAM이면 진행 관리를 흐름 기록으로 감싼다. 도우미를 켤 때마다 새 파일(켠 시각 이름)이고 지우지 않는다."""
    if not RECORD_STREAM:
        return desk
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        log.warning("작업 상태 흐름 폴더를 만들지 못해 기록하지 않음(%s): %s", folder, error)
        return desk
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    log.info("작업 상태 흐름 기록: %s", path)
    return RecordingDesk(desk, path, records)


def _courses() -> list[Course]:
    """저장소의 연습 과정을 읽는다. 파일이 깨졌으면 연습 과정 없이 자유 질문만 받는다(고르기 카드에 읽지 못했다고 보임, 검사: course_check)."""
    try:
        return load_courses(COURSES)
    except Exception:
        log.exception("연습 과정을 읽지 못함(course_check로 검사해 보세요)")
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Blender 첫걸음 도우미 창을 켭니다.")
    parser.add_argument("--port", type=int, default=PORT, help=f"받을 자리 번호(기본 {PORT}, 자체 시험은 다른 번호를 씀)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    token = os.environ.get(TOKEN_ENV)
    if not token:
        log.error("환경 변수 %s가 없습니다. 애드온이 켜 주거나, 애드온 config.json의 token을 넣고 켜세요.", TOKEN_ENV)
        return 2

    # 그래픽 카드를 Blender와 나눠 쓰지 않게: 위젯은 CPU로 그리고, 혹시 OpenGL을 쓰는 곳이 생겨도 소프트웨어로
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 창을 숨겨도 트레이에 남는다
    app.setFont(QFont(FONT, 10))
    bridge = _Bridge()
    helper: Helper | None = None

    def listen(message: Message) -> None:
        if helper is not None:
            helper.on_message(message)

    try:
        receiver = Receiver(token, listen, port=args.port)
    except OSError as error:
        log.error("%s번 자리를 열 수 없습니다(다른 프로그램이 쓰는 중일 수 있음): %s", args.port, error)
        return 1
    with receiver:
        helper = Helper(app, receiver, bridge)
        bridge.no_blender.connect(app.quit)

        def watch() -> None:
            receiver.run_until_no_blender()
            log.info("켜진 Blender가 없어 끝냅니다.")
            bridge.no_blender.emit()

        threading.Thread(target=watch, daemon=True).start()
        log.info("도우미 창 준비(127.0.0.1:%s). 마지막 Blender가 닫히면 끝납니다.", receiver.port)
        app.exec()
    return 0


if __name__ == "__main__":
    sys.exit(main())
