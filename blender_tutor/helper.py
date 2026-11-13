"""도우미 프로그램 입구: 받는 쪽 + 도우미 창 + 진행 관리 + 답 엔진을 한 프로그램으로 잇는다(명세 "전체 구성", ADR-0001, 티켓 26·27).

애드온이 Blender를 켤 때 켜 준다(config.json의 명령). 마지막 Blender가 닫히거나 트레이에서 끝내면 끝난다.
손으로 켤 때: `set BLENDER_TUTOR_TOKEN=<애드온 폴더 config.json의 token>` 뒤 `.venv\\Scripts\\python -m blender_tutor.helper`
(Mac: `BLENDER_TUTOR_TOKEN=<token> .venv/bin/python -m blender_tutor.helper`)

부품끼리 잇기만 한다. 판단은 window_rules, 질문 한 번의 순서는 question_flow, 대화는 conversation, 진행은 course_desk, 그리기는 helper_window에 있고 각각 시험한다.
이 파일과 winapi(Mac은 macapi)는 실제 화면·Blender가 있어야 해서 애드온 자체 시험과 눈 확인으로 본다.
"""

import argparse
import json
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

if sys.platform == "win32":
    from blender_tutor import winapi as screen_api
else:  # Mac(HISTORY [312]): 같은 이름의 함수를 pyobjc로
    from blender_tutor import macapi as screen_api
from blender_tutor.answer_engine import Event, Settings
from blender_tutor.conversation import PROGRAM_ERROR, Conversation
from blender_tutor.course_desk import CourseDesk, Line
from blender_tutor.helper_window import FONT, HelperWindow, Tray
from blender_tutor.paths import COURSES, PROJECT, default_progress_records
from blender_tutor.progress import Course, load_courses
from blender_tutor.question_flow import QuestionFlow
from blender_tutor.receiver import PORT, TOKEN_ENV, Message, Receiver
from blender_tutor.manual_vectors import MODEL as EMBEDDING
from blender_tutor.engine_setup import build_engine
from blender_tutor.menu_names import load_menu_names
from blender_tutor.state_stream import RecordingDesk
from blender_tutor.timing import Stopwatch
from blender_tutor.window_rules import FrontBlender, Place, Screen, needs_move, place

WARM_UP_ENV = "BLENDER_TUTOR_WARM_UP"  # 1이면 엔진을 만든 뒤 예열한다(질문 바꾸기·임베딩을 한 번씩, 돈이 아주 조금 든다)
REASONING_ENV = "BLENDER_TUTOR_REASONING"  # 답변 모델의 생각 수준(none·low·medium). 없으면 명세 기본 none(티켓 33 실측용)

FOLLOW_EVERY_MS = 100  # Blender를 따라 창 자리를 다시 보는 간격
ACTIVATION_SETTLE_MS = 120  # Mac: 앞 앱이 바뀐 뒤 그 앱의 창이 맨 위로 올라올 때까지 기다렸다 자리를 다시 맞추는 시간
CLICK_SETTLE_S = 0.3  # Mac: 누른 앱이 앞 앱으로 알려지기까지 따라가기가 누른 결과를 뒤집지 않고 기다리는 시간
# 작업 상태 흐름을 늘 기록한다(검수 동안 쓰려고, 2026-10-26 사용자 결정). 코드 동결 전에 False로 바꾼다(티켓 37)
RECORD_STREAM = True
NO_DATA = "설명서 자료(data/)가 없어 답할 수 없어요. HANDOFF.md의 'data/ 다시 만들기'를 봐 주세요."

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
        self._course_desk = CourseDesk(self._courses, records)  # 메뉴 이름 사전은 _prepare_engine이 읽어 넣는다
        self._desk = _recording(self._course_desk, records, records.parent / "streams")
        self._stopwatch = Stopwatch(records.parent / "timings.jsonl", platform.node())
        self._own_pid = os.getpid()
        self._moved: tuple[Place, int] | None = None  # 지난번에 옮긴 (자리, 그때 앞 창 번호)
        self._clicked: tuple[int, float] | None = None  # Mac: 마지막으로 누른 순간 옮긴 (그 창 프로세스 번호, 시각)
        self._progress_of: int | None = None  # 연습 과정 카드에 진행을 보이는 Blender 창 번호
        self.window = HelperWindow()
        self._tray = Tray(self._tray_show, app.quit)
        # 붙잡아 둔다: Qt는 메서드에 이은 연결을 그 객체가 살아 있을 때만 지켜, 지역 변수면 Enter가 아무것도 부르지 않는다
        self._flow = QuestionFlow(receiver, self._front, self._desk, self._conversation, self._stopwatch, _QtWindowSide(bridge))
        self.window.asked.connect(self._flow.ask)
        self.window.started_typing.connect(lambda: self._receiver.want_settings())  # 설정 값을 미리 읽어 두게(HISTORY [270])
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
        self._activation = screen_api.watch_activation(self._on_activation)  # Mac: 앞 앱이 바뀌면 0.1초를 기다리지 않고 바로
        # Mac: 누르는 순간 먼저(권한이 없으면 None). 손쉬운 사용 권한은 처음 한 번만 묻는다(거부한 사람에게 켤 때마다 묻지
        # 않게, HISTORY [316]). 물었다는 표시는 진행 기록 옆에 둔다
        asked = records.parent / "accessibility_asked"
        self._clicks = screen_api.watch_clicks(self._on_click, ask=not asked.exists())
        if sys.platform == "darwin":
            asked.parent.mkdir(parents=True, exist_ok=True)
            asked.touch()
        if self._clicks is None and sys.platform == "darwin":
            log.info("손쉬운 사용·입력 모니터링 권한이 없어 누르는 순간 옮기기를 쓰지 않음(앞 앱 알림으로만 옮김)")
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
            # 모르는 생각 수준이면 ValueError → 아래에서 기록에 남기고 "문제가 생겼어요"를 보인다
            # 연습 과정 안내 말의 메뉴 이름도 화면 언어로(티켓 32). 답 엔진을 못 만들어도(키 없음 등) 안내 말은 바뀌게 먼저 넣는다
            self._course_desk.menu_names = load_menu_names(PROJECT / "data")
            settings = Settings(reasoning=os.environ.get(REASONING_ENV, Settings().reasoning))
            self._conversation.engine = build_engine(PROJECT / "data", courses=self._courses, settings=settings, embedding=EMBEDDING)
        except SystemExit as error:  # OpenAI 키가 없음(openai_key). 스레드 안이라 잡지 않으면 '읽는 중'에 머문다
            log.warning("OpenAI 키 없음: %s", error)
            self._conversation.waiting_message = str(error)
            return
        except FileNotFoundError as error:
            log.warning("설명서 자료가 없음: %s", error)
            self._conversation.waiting_message = NO_DATA
            return
        except Exception:
            log.exception("답 엔진을 만들지 못함")
            self._conversation.waiting_message = PROGRAM_ERROR
            return
        log.info(
            "답 엔진 준비 %.1f초(%s, 생각 수준 %s)",
            time.perf_counter() - started, self._conversation.engine.name, self._conversation.engine.settings.reasoning,
        )
        if os.environ.get(WARM_UP_ENV) == "1":  # 예열은 사용자가 켤 때만(몰래 처리하는 인상을 주지 않게, HISTORY [127])
            started = time.perf_counter()
            self._conversation.engine.warm_up()
            log.info("예열 %.1f초", time.perf_counter() - started)

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
        hwnd = screen_api.native_window(int(self.window.winId()))
        screen_api.put_on_top(hwnd)
        if not screen_api.bring_forward(hwnd):
            log.info("Windows가 앞으로 가져오기를 막음(입력칸 초점 없음)")
        self._moved = (Place.TOP, hwnd)

    def _tray_show(self) -> None:
        """트레이 보이기: 보이는 Blender가 있으면 F10과 똑같이, 모두 최소화면 막는다(안내는 아이콘 글)."""
        if screen_api.any_shown(self._receiver.blenders()):
            self._bring_up()

    def _back_to_blender(self) -> None:
        """Esc: 마지막으로 앞에 있던 Blender로 초점을 돌린다(창은 그대로, Blender가 앞이니 그 위에 남는다)."""
        window = self._front.window(self._receiver.blenders())
        if window:
            screen_api.bring_forward(window)

    def _on_activation(self) -> None:
        """Mac: 앞 앱이 바뀐 즉시 옮기고(새 앞 앱을 덮지 않게), 그 앱의 창이 맨 위로 올라간 뒤 자리를 한 번 더 맞춘다.
        알림이 오는 순간에는 새 앞 앱의 창이 아직 아래에 있어, 그 창 '바로 뒤'에 놓으면 Blender 뒤까지 내려가 사라졌다
        (2026-11-13 실측: Mail을 누르자 차례가 Mail, Blender, 도우미, HISTORY [312])."""
        self._follow()
        QTimer.singleShot(ACTIVATION_SETTLE_MS, self._follow_again)

    def _on_click(self, window: int, pid: int) -> None:
        """Mac: 마우스를 누른 순간. 누른 창이 Blender면 바로 맨 위로, 같은 데스크톱의 다른 프로그램이면 바로 Blender 위로 내린다.
        도우미 자신·바탕·숨김·내린 상태는 따라가기(_follow)가 정한 대로 둔다."""
        blenders = self._receiver.blenders()
        if pid == self._own_pid or not self.window.isVisible() or self.window.put_away:
            return
        hwnd = screen_api.native_window(int(self.window.winId()))
        if pid in blenders.values():
            screen_api.put_on_top(hwnd)
            self._moved = (Place.TOP, window)
        elif screen_api.same_space(hwnd, window):
            screen_api.put_behind(hwnd, window, self._front.window(blenders) or 0)
            self._moved = (Place.BEHIND, window)
        else:
            return
        self._clicked = (pid, time.monotonic())

    def _follow_again(self) -> None:
        self._moved = None  # 자리가 같아도 다시 옮긴다
        self._follow()

    # ---- Blender 따라가기(0.1초마다)
    def _follow(self) -> None:
        blenders = self._receiver.blenders()
        front_hwnd, front_pid, taskbar = screen_api.foreground()
        self._front.saw_foreground(front_pid, blenders)
        if self._front.window(blenders) != self._progress_of:  # 다른 Blender로 옮겨 갔거나 닫혔다
            self._show_progress()
        # Mac: 누른 앱이 아직 앞 앱으로 알려지기 전이면 지난 앞 앱 기준으로 되돌리지 않는다(2026-11-13 실측: Blender를 누른 직후
        # 0.1초 따라가기가 아직 Mail을 앞 앱으로 읽고 도우미를 내려 깜빡였다)
        if self._clicked and front_pid != self._clicked[0] and time.monotonic() - self._clicked[1] < CLICK_SETTLE_S:
            return
        hwnd = screen_api.native_window(int(self.window.winId()))
        if screen_api.elsewhere(blenders, hwnd, self.window.isVisible()):  # Mac: 다른 데스크톱을 보는 중이면 그대로
            return
        shown = screen_api.any_shown(blenders)
        self._tray.blender_shown(shown)
        screen = Screen(front_pid, taskbar, frozenset(blenders.values()), shown)
        where = place(screen, self._own_pid, self.window.put_away)
        # Mac은 도우미가 초점을 잃으면 맨 위가 풀려서, 자리가 그대로 맨 위여도 실제로 내려왔으면 다시 올린다
        if not needs_move(where, front_hwnd, self._moved) and not (where == Place.TOP and screen_api.lost_top(hwnd)):
            return
        if where == Place.BEHIND and not screen_api.same_space(hwnd, front_hwnd):  # Mac: 데스크톱을 옮기는 도중이면 그대로
            return
        if where == Place.HIDDEN:
            self.window.hide()
        else:
            self.window.show()  # 초점은 빼앗지 않는다(WA_ShowWithoutActivating)
            if where == Place.TOP:
                screen_api.put_on_top(hwnd)
            else:
                screen_api.put_behind(hwnd, front_hwnd, self._front.window(blenders) or 0)
        self._moved = (where, front_hwnd)


class _QtWindowSide:
    """질문 한 번(question_flow)의 실제 창 연결: 답 사건은 Qt 신호로 화면 스레드에 넘기고, 답은 따로 도는 스레드에서 기다린다."""

    def __init__(self, bridge: _Bridge):
        self._bridge = bridge

    def show(self, event: Event) -> None:
        self._bridge.answer_event.emit(event)

    def start(self, work: Callable[[], None]) -> None:
        threading.Thread(target=work, daemon=True).start()  # 답을 기다리는 동안 창과 Blender가 멈추지 않게


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
    # Mac은 애드온이 open으로 앱 묶음을 켜서 환경 변수가 넘어오지 않는다. 그때 애드온 config.json에서 비밀 글자를 읽는다
    parser.add_argument("--token-file", type=Path, default=None, help="비밀 글자를 읽을 애드온 config.json(환경 변수가 없을 때)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    token = os.environ.get(TOKEN_ENV)
    if not token and args.token_file:
        token = json.loads(args.token_file.read_text(encoding="utf-8"))["token"]
    if not token:
        log.error("환경 변수 %s가 없습니다. 애드온이 켜 주거나, 애드온 config.json의 token을 넣고 켜세요.", TOKEN_ENV)
        return 2

    # 그래픽 카드를 Blender와 나눠 쓰지 않게: 위젯은 CPU로 그리고, 혹시 OpenGL을 쓰는 곳이 생겨도 소프트웨어로
    QCoreApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 창을 숨겨도 트레이에 남는다
    screen_api.hide_from_dock()  # Mac: Dock·Cmd+Tab에 나오지 않게(Windows는 Qt.Tool이 이미 뺌)
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
