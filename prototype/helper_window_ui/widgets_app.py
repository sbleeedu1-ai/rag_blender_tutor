# 시제품(버릴 코드): PySide6 위젯만으로(파이썬만) 만든 도우미 창
import sys
import time

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

import common

V = "위젯"
EDGE = 8  # 이 폭 안에서 누르면 크기 조절

STYLE = f"""
QWidget {{ font-family: '{common.FONT}'; color: white; }}
QScrollArea, #inner {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
#tag {{ color: rgba(255,255,255,0.28); font-size: 11px; }}
#close {{ background: rgba(255,255,255,0.10); border: none; border-radius: 12px; color: rgba(255,255,255,0.75); font-size: 12px; }}
#close:hover {{ background: rgba(255,255,255,0.22); }}
#question {{ color: rgba(235,235,245,0.55); font-size: 14px; }}
#answer {{ color: white; font-size: 19px; font-weight: 700; }}
#thinking {{ color: rgba(235,235,245,0.45); font-size: 15px; }}
#card {{ background: rgba(255,255,255,0.08); border-radius: 14px; }}
#cardTitle {{ color: rgba(235,235,245,0.45); font-size: 11px; font-weight: 700; }}
#source {{ font-size: 13px; }}
#input {{ background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px;
          padding: 0 16px; font-size: 15px; color: white; selection-background-color: rgba(120,140,255,0.6); }}
#input:focus {{ border: 1px solid rgba(160,175,255,0.45); }}
"""


class Helper(QWidget):
    def __init__(self, slot):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setGeometry(common.window_rect(slot))
        self.setMinimumSize(300, 220)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 18)
        root.setSpacing(10)

        # 맨 위: 시제품 표시 + 마우스를 올리면 보이는 X
        top = QHBoxLayout()
        tag = QLabel(f"시제품 · {V}")
        tag.setObjectName("tag")
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("close")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide_helper)
        self.close_fx = QGraphicsOpacityEffect(self.close_btn)
        self.close_fx.setOpacity(0.0)
        self.close_btn.setGraphicsEffect(self.close_fx)
        self.close_anim = QPropertyAnimation(self.close_fx, b"opacity", self)
        self.close_anim.setDuration(150)
        top.addWidget(tag)
        top.addStretch()
        top.addWidget(self.close_btn)
        root.addLayout(top)

        # 대화
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("inner")
        self.chat = QVBoxLayout(inner)
        self.chat.setContentsMargins(0, 0, 8, 0)
        self.chat.setSpacing(8)
        self.chat.addStretch()
        self.scroll.setWidget(inner)
        self.scroll.verticalScrollBar().rangeChanged.connect(
            lambda _a, b: self.scroll.verticalScrollBar().setValue(b))
        root.addWidget(self.scroll, 1)

        # 알약 모양 입력칸
        self.input = QLineEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("질문을 입력하세요")
        self.input.setFixedHeight(42)
        self.input.returnPressed.connect(self.send)
        root.addWidget(self.input)

        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setDuration(160)
        self.fade.setEasingCurve(QEasingCurve.OutCubic)
        self.timer = QTimer(self, interval=25)
        self.timer.timeout.connect(self.tick)
        self.busy = False
        self.ask(common.FIRST_QUESTION)

    # ---- 그리기: 둥근 어두운 반투명 판
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 22, 22)
        p.fillPath(path, QColor(22, 22, 28, 214))
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.drawPath(path)

    # ---- 보이기 / 숨기기
    def show_helper(self):
        t0 = time.perf_counter()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()
        self.fade.stop()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()
        QTimer.singleShot(0, lambda: common.log(V, f"보이기 {1000 * (time.perf_counter() - t0):.0f}ms"))

    def hide_helper(self):
        self.hide()
        common.log(V, "숨김(X 또는 Esc)")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide_helper()
        else:
            super().keyPressEvent(e)

    def enterEvent(self, _e):
        self._fade_close(1.0)

    def leaveEvent(self, _e):
        self._fade_close(0.0)
        self.unsetCursor()

    def _fade_close(self, to):
        self.close_anim.stop()
        self.close_anim.setStartValue(self.close_fx.opacity())
        self.close_anim.setEndValue(to)
        self.close_anim.start()

    # ---- 테두리 없는 창의 크기 조절(가장자리)과 옮기기(맨 위 띠)
    def _edges(self, pos):
        r = self.rect()
        edges = Qt.Edges()
        if pos.x() < EDGE: edges |= Qt.LeftEdge
        if pos.x() > r.width() - EDGE: edges |= Qt.RightEdge
        if pos.y() < EDGE: edges |= Qt.TopEdge
        if pos.y() > r.height() - EDGE: edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, e):
        edges = self._edges(e.position().toPoint())
        if edges in (Qt.LeftEdge | Qt.TopEdge, Qt.RightEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (Qt.RightEdge | Qt.TopEdge, Qt.LeftEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edges & (Qt.LeftEdge | Qt.RightEdge):
            self.setCursor(Qt.SizeHorCursor)
        elif edges & (Qt.TopEdge | Qt.BottomEdge):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        pos = e.position().toPoint()
        edges = self._edges(pos)
        if edges:
            self.windowHandle().startSystemResize(edges)
        elif pos.y() < 40:
            self.windowHandle().startSystemMove()

    # ---- 대화
    def _label(self, text, name):
        lab = QLabel(text)
        lab.setObjectName(name)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.chat.addWidget(lab)
        return lab

    def send(self):
        q = self.input.text().strip()
        if not q or self.busy:
            return
        self.input.clear()
        self.ask(q)

    def ask(self, q):
        self.busy = True
        self.t_send = time.perf_counter()
        common.log(V, f"보냄: {q}")
        self._label(q, "question")
        self.thinking = self._label("생각 중…", "thinking")
        self.ans = common.next_answer()
        self.shown = 0
        QTimer.singleShot(600, self.timer.start)  # 가짜 첫 글자 지연

    def tick(self):
        if self.shown == 0:
            self.answer = self.thinking
            self.answer.setObjectName("answer")
            self.answer.style().unpolish(self.answer)  # 바뀐 이름의 스타일 다시 적용
            self.answer.style().polish(self.answer)
            common.log(V, f"첫 글자 {1000 * (time.perf_counter() - self.t_send):.0f}ms")
        self.shown += 2
        self.answer.setText(self.ans["text"][: self.shown])
        if self.shown >= len(self.ans["text"]):
            self.timer.stop()
            self._sources(self.ans["sources"])
            self.busy = False
            common.log(V, f"답 끝 {1000 * (time.perf_counter() - self.t_send):.0f}ms")

    def _sources(self, sources):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(4)
        title = QLabel("근거 · Blender 5.2 설명서")
        title.setObjectName("cardTitle")
        lay.addWidget(title)
        for s in sources:
            note = f" <span style='color:rgba(235,235,245,0.45)'>· {s['note']}</span>" if s["note"] else ""
            lab = QLabel(f"<a style='color:#a9b6ff; text-decoration:none' href='{s['url']}'>{s['path']}</a>{note}")
            lab.setObjectName("source")
            lab.setWordWrap(True)
            lab.setOpenExternalLinks(True)
            lay.addWidget(lab)
        self.chat.addWidget(card)
        fx = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(fx)
        anim = QPropertyAnimation(fx, b"opacity", card)
        anim.setDuration(250)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()


def main():
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 숨겨도 트레이에 남음
    app.setFont(QFont(common.FONT, 10))
    w = Helper(slot)
    tray = common.make_tray(app, V, w.show_helper)
    w.show_helper()
    common.auto_shot(app, w.geometry)
    common.log(V, "준비됨(트레이 아이콘 왼쪽 클릭 = 보이기)")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
