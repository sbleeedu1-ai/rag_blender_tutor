"""도우미 창 화면: PySide6 위젯(파이썬만, QML 쓰지 않음, HISTORY [17]·[18], 티켓 26).

테두리·제목 표시줄 없는 어두운 반투명 판에 회색 질문 / 크고 굵은 흰 답 / 근거 카드 / 알약 입력칸.
작업 표시줄·Alt+Tab에 나오지 않는 도구 창이고 트레이 아이콘만 둔다. Apple·Siri 이름·로고는 쓰지 않는다.
창은 그리기와 입력만 한다. 언제 맨 위·뒤·숨김인지(window_rules)와 답 만들기(conversation)는 helper가 잇는다.
"""

import html

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QScrollArea,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

from blender_tutor.answer_engine import Done, Event, Failure, Piece, Source
from blender_tutor.window_rules import by_sentence

WIDTH, HEIGHT = 420, 560  # 처음 크기(시제품 위젯 판에서 사용자가 써 본 크기)
MIN_WIDTH, MIN_HEIGHT = 300, 220  # 줄여도 입력칸과 최근 답 몇 줄은 보이는 크기
MARGIN = 24  # 화면 오른쪽 아래 모서리에서 띄우는 거리
EDGE = 8  # 가장자리에서 이 폭 안을 끌면 크기 조절
MOVE_BAND = 40  # 맨 위 이 높이 안을 끌면 창 옮기기
PANEL_ALPHA = 235  # 판 진하기(0-255, 사용자 결정 HISTORY [18])
BLUR_PANEL_ALPHA = 170  # 진짜 흐림을 켰을 때는 뒤가 흐려 보이므로 판을 덜 진하게
FONT = "Malgun Gothic"
THINKING = "생각 중…"

STYLE = f"""
QWidget {{ font-family: '{FONT}'; color: white; }}
QScrollArea, #inner {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 6px; margin: 0; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
#close {{ background: rgba(255,255,255,0.10); border: none; border-radius: 12px; color: rgba(255,255,255,0.75); font-size: 12px; }}
#close:hover {{ background: rgba(255,255,255,0.22); }}
#question {{ color: rgba(235,235,245,0.55); font-size: 14px; }}
#thinking {{ color: rgba(235,235,245,0.45); font-size: 15px; }}
#answer {{ color: white; font-size: 19px; font-weight: 700; }}
#failure {{ color: rgba(255,190,170,0.85); font-size: 14px; }}
#card {{ background: rgba(255,255,255,0.08); border-radius: 14px; }}
#cardTitle {{ color: rgba(235,235,245,0.45); font-size: 11px; font-weight: 700; }}
#source {{ font-size: 13px; }}
#input {{ background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px;
          padding: 0 16px; font-size: 15px; color: white; selection-background-color: rgba(120,140,255,0.6); }}
#input:focus {{ border: 1px solid rgba(160,175,255,0.45); }}
"""


class HelperWindow(QWidget):
    """도우미 창. Enter로 보낸 질문은 asked로 알리고, 답 사건은 show_event로 받아 그린다(화면 스레드에서)."""

    asked = Signal(str)  # Enter로 보낸 질문
    escape = Signal()  # Esc: Blender로 돌아가기

    def __init__(self, blur: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)  # Tool: 작업 표시줄·Alt+Tab에 나오지 않음
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # Blender를 따라 보일 때 초점을 빼앗지 않는다
        self.setMouseTracking(True)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setGeometry(_home())
        self.setStyleSheet(STYLE)
        self._panel_alpha = BLUR_PANEL_ALPHA if blur else PANEL_ALPHA
        self.put_away = False  # 사용자가 X로 직접 내렸나(F10·트레이로 부를 때까지 내린 채)
        self._busy = False  # 답을 기다리는 중
        self._answer: QLabel | None = None
        self._answer_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()  # 마우스를 올렸을 때만 보이는 X(숨기기) 하나
        self.close_button = QPushButton("✕")
        self.close_button.setObjectName("close")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self._put_away)
        self._close_effect = QGraphicsOpacityEffect(self.close_button)
        self._close_effect.setOpacity(0.0)
        self.close_button.setGraphicsEffect(self._close_effect)
        self._close_fade = QPropertyAnimation(self._close_effect, b"opacity", self)
        self._close_fade.setDuration(150)
        top.addStretch()
        top.addWidget(self.close_button)
        root.addLayout(top)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("inner")
        self._chat = QVBoxLayout(inner)
        self._chat.setContentsMargins(0, 0, 8, 0)
        self._chat.setSpacing(8)
        self._chat.addStretch()
        self._scroll.setWidget(inner)
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _low, high: bar.setValue(high))  # 새 글이 붙으면 맨 아래로
        root.addWidget(self._scroll, 1)

        self.input = QLineEdit()
        self.input.setObjectName("input")
        self.input.setPlaceholderText("질문을 쓰고 Enter")
        self.input.setFixedHeight(42)
        self.input.returnPressed.connect(self._send)
        root.addWidget(self.input)

    # ---- 보이기
    def summon(self) -> None:
        """F10·트레이: 내린 것을 풀고 보이고 입력칸에 초점(앞으로 끌어오기는 helper가 Windows에 부탁)."""
        self.put_away = False
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def _put_away(self) -> None:
        self.put_away = True
        self.hide()

    # ---- 대화
    def _send(self) -> None:
        question = self.input.text().strip()
        if not question or self._busy:
            return
        self.input.clear()
        self._busy = True
        self._label(question, "question")
        self._answer = self._label(THINKING, "thinking")
        self._answer_text = ""
        self.asked.emit(question)

    def show_event(self, event: Event) -> None:
        """답 사건 하나를 그린다: 조각은 이어 붙이고, 끝이면 근거 카드, 오류면 짧은 문구."""
        if isinstance(event, Piece):
            if not self._answer_text:  # 첫 조각: "생각 중…"을 답 글씨로 바꾼다
                self._restyle(self._answer, "answer")
            self._answer_text += event.text
            self._answer.setText(by_sentence(self._answer_text))
            return
        if not self._answer_text:  # 조각 없이 끝났으면 "생각 중…"을 치운다
            self._answer.deleteLater()
        if isinstance(event, Done) and event.sources:
            self._chat.addWidget(_sources_card(event.sources))
        elif isinstance(event, Failure):
            self._label(event.message, "failure")
        self._answer = None
        self._busy = False

    def _label(self, text: str, name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setTextFormat(Qt.PlainText)  # 질문·답에 든 <b> 같은 글을 서식으로 읽지 않는다
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._chat.addWidget(label)
        return label

    @staticmethod
    def _restyle(label: QLabel, name: str) -> None:
        label.setObjectName(name)
        label.style().unpolish(label)  # 바뀐 이름의 모양을 다시 입힌다
        label.style().polish(label)

    # ---- 그리기: 둥근 어두운 반투명 판
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 22, 22)
        painter.fillPath(path, QColor(22, 22, 28, self._panel_alpha))
        painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
        painter.drawPath(path)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.escape.emit()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, _event) -> None:
        self._fade_close(1.0)

    def leaveEvent(self, _event) -> None:
        self._fade_close(0.0)
        self.unsetCursor()

    def _fade_close(self, to: float) -> None:
        self._close_fade.stop()
        self._close_fade.setStartValue(self._close_effect.opacity())
        self._close_fade.setEndValue(to)
        self._close_fade.setEasingCurve(QEasingCurve.OutCubic)
        self._close_fade.start()

    # ---- 테두리 없는 창의 크기 조절(가장자리)과 옮기기(맨 위 띠): Windows 기본 동작을 부른다
    def _edges(self, pos: QPoint) -> Qt.Edges:
        edges = Qt.Edges()
        if pos.x() < EDGE:
            edges |= Qt.LeftEdge
        if pos.x() > self.width() - EDGE:
            edges |= Qt.RightEdge
        if pos.y() < EDGE:
            edges |= Qt.TopEdge
        if pos.y() > self.height() - EDGE:
            edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, event) -> None:
        edges = self._edges(event.position().toPoint())
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

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        if edges := self._edges(pos):
            self.windowHandle().startSystemResize(edges)
        elif pos.y() < MOVE_BAND:
            self.windowHandle().startSystemMove()


def _home() -> QRect:
    """정해진 자리: 주 화면 오른쪽 아래(작업 표시줄 위)."""
    area = QGuiApplication.primaryScreen().availableGeometry()
    return QRect(area.right() - WIDTH - MARGIN, area.bottom() - HEIGHT - MARGIN, WIDTH, HEIGHT)


def _sources_card(sources: tuple[Source, ...]) -> QFrame:
    """근거 카드: 소제목 경로마다 설명서 링크와 그림·영상 표시."""
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 10, 14, 12)
    layout.setSpacing(4)
    title = QLabel("근거 · Blender 5.2 설명서 (CC BY-SA 4.0)")
    title.setObjectName("cardTitle")
    layout.addWidget(title)
    for source in sources:
        notes = " · ".join(note for note, has in (("그림 있음", source.has_image), ("영상 있음", source.has_video)) if has)
        note = f" <span style='color:rgba(235,235,245,0.45)'>· {notes}</span>" if notes else ""
        label = QLabel(
            f"<a style='color:#a9b6ff; text-decoration:none' href='{html.escape(source.url, quote=True)}'>"
            f"{html.escape(source.path)}</a>{note}"
        )
        label.setObjectName("source")
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)  # 누르면 기본 브라우저로 설명서 그 소제목이 열린다
        layout.addWidget(label)
    return card


def tray_icon(parent, on_show, on_quit) -> QSystemTrayIcon:
    """트레이 아이콘: 왼쪽 클릭 = 보이기(숨기지 않음), 오른쪽 메뉴 = 보이기 / 끝내기."""
    tray = QSystemTrayIcon(_icon(), parent)
    menu = QMenu()
    show_action = menu.addAction("보이기", on_show)
    menu.addAction("끝내기", on_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: on_show() if reason == QSystemTrayIcon.Trigger else None)
    tray.show_action = show_action  # helper가 Blender가 모두 숨었을 때 막는다
    tray.menu = menu  # 메뉴가 지워지지 않게 붙잡아 둔다
    return tray


def _icon() -> QIcon:
    """로고 없이 직접 그린 동그라미."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(120, 140, 255))
    painter.drawEllipse(6, 6, 52, 52)
    painter.setBrush(QColor(255, 255, 255, 220))
    painter.drawEllipse(24, 24, 16, 16)
    painter.end()
    return QIcon(pixmap)
