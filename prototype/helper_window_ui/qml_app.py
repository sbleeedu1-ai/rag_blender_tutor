# 시제품(버릴 코드): PySide6 + QML로 만든 도우미 창. 화면은 helper.qml, 여기는 가짜 답과 트레이
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")  # 입력칸 모양을 직접 꾸미려면 Basic 스타일

from PySide6.QtCore import QMetaObject, QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

import common

V = "QML"


class Backend(QObject):
    """QML이 부르는 쪽. 가짜 답을 글자 조각으로 흘려보낸다."""
    answerStarted = Signal()
    chunk = Signal(str)
    finished = Signal("QVariantList")

    def __init__(self):
        super().__init__()
        self.timer = QTimer(self, interval=25)
        self.timer.timeout.connect(self._tick)

    @Slot(str)
    def ask(self, q):
        self.t_send = time.perf_counter()
        common.log(V, f"보냄: {q}")
        self.ans = common.next_answer()
        self.shown = 0
        QTimer.singleShot(600, self.timer.start)  # 가짜 첫 글자 지연

    def _tick(self):
        if self.shown == 0:
            self.answerStarted.emit()
            common.log(V, f"첫 글자 {1000 * (time.perf_counter() - self.t_send):.0f}ms")
        text = self.ans["text"]
        self.chunk.emit(text[self.shown:self.shown + 2])
        self.shown += 2
        if self.shown >= len(text):
            self.timer.stop()
            self.finished.emit(self.ans["sources"])
            common.log(V, f"답 끝 {1000 * (time.perf_counter() - self.t_send):.0f}ms")

    @Slot(str)
    def log(self, msg):
        common.log(V, msg)


def main():
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 숨겨도 트레이에 남음
    app.setFont(QFont(common.FONT, 10))
    backend = Backend()
    engine = QQmlApplicationEngine()
    r = common.window_rect(slot)
    engine.setInitialProperties({
        "backend": backend, "fontName": common.FONT, "firstQuestion": common.FIRST_QUESTION,
        "x": r.x(), "y": r.y(), "width": r.width(), "height": r.height(),
    })
    engine.load(Path(__file__).with_name("helper.qml"))
    if not engine.rootObjects():
        sys.exit("helper.qml을 읽지 못했습니다(위 오류 참고)")
    win = engine.rootObjects()[0]

    def show_helper():
        t0 = time.perf_counter()
        QMetaObject.invokeMethod(win, "showHelper")
        win.frameSwapped.connect(
            lambda: common.log(V, f"보이기 {1000 * (time.perf_counter() - t0):.0f}ms"), type=Qt.SingleShotConnection)

    tray = common.make_tray(app, V, show_helper)
    show_helper()
    common.auto_shot(app, win.geometry)
    common.log(V, "준비됨(트레이 아이콘 왼쪽 클릭 = 보이기)")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
