"""도우미 창 화면: PySide6 위젯(파이썬만, QML 쓰지 않음, HISTORY [17]·[18], 티켓 26·27).

테두리·제목 표시줄 없는 어두운 반투명 판에 맨 위 연습 과정 카드 / 대화(도우미 안내 말, 회색 질문, 크고 굵은 흰 답,
근거 카드) / [네] [아니요] 물음 줄 / 알약 입력칸.
연습 과정 카드는 연습 과정·n단계, 단계 이름, 뒤로·다음과 오른쪽 끝 '단계 ▼'만 둔다(사용자 결정, 티켓 27, HISTORY [55]).
'다음'은 조작 하나씩 넘기고 조작을 다 끝내면 '다음 단계'가 된다. '단계 ▼'는 다섯 줄 높이 단계 목록과 그 아래 연습 과정 바꾸기.
목표 모양은 보이지 않고, 조작은 도우미가 대화에 하나씩 안내한다(course_desk).
작업 표시줄·Alt+Tab에 나오지 않는 도구 창이고 트레이 아이콘만 둔다. Apple·Siri 이름·로고는 쓰지 않는다.
창은 그리기와 입력만 한다. 언제 맨 위·뒤·숨김인지(window_rules)와 답 만들기(conversation)는 helper가 잇는다.
"""

import html

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QScrollArea, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget, QWidgetAction,
)

from blender_tutor.answer_engine import Done, Event, Failure, Piece, Source
from blender_tutor.course_desk import Line, StepView
from blender_tutor.progress import Course
from blender_tutor.window_rules import by_sentence

WIDTH, HEIGHT = 420, 560  # 처음 크기(시제품 위젯 판에서 사용자가 써 본 크기)
MIN_WIDTH, MIN_HEIGHT = 300, 220  # 줄여도 입력칸과 최근 답 몇 줄은 보이는 크기
MARGIN = 24  # 화면 오른쪽 아래 모서리에서 띄우는 거리
EDGE = 8  # 가장자리에서 이 폭 안을 끌면 크기 조절
CORNER = 24  # 모서리에서 이만큼 안쪽 네모를 끌면 대각선 조절(둥근 모서리의 투명한 곳은 클릭이 아래 창으로 가서 넓게 잡음)
MOVE_BAND = 40  # 맨 위 이 높이 안을 끌면 창 옮기기
PANEL_ALPHA = 235  # 판 진하기(0-255, 사용자 결정 HISTORY [18])
FONT = "Malgun Gothic"
THINKING = "생각 중…"
COURSES_UNREADABLE = "연습 과정 파일을 읽지 못했어요. 질문은 그대로 할 수 있어요."  # 검 파일이 늘 있으니 빈 목록은 읽기 실패
STEP_ROWS = 5  # '단계 ▼' 목록에 한 번에 보이는 줄 수(넘으면 스크롤, 사용자 결정)
PICK_HINT = "목록에 없으면 만들고 싶은 것을 아래에 물어보세요. 비슷한 연습 과정을 알려 드려요. 연습 과정 없이 질문만 해도 돼요."

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
#courseCard {{ background: rgba(255,255,255,0.07); border-radius: 14px; }}
#stepHeader, #pickTitle {{ color: rgba(235,235,245,0.55); font-size: 12px; font-weight: 700; }}
#stepName {{ font-size: 16px; font-weight: 700; }}
#guide {{ color: white; font-size: 15px; background: rgba(120,140,255,0.12); border-radius: 12px; padding: 8px 12px; }}
#hint {{ color: rgba(235,235,245,0.55); font-size: 12px; }}
#notice {{ color: rgba(190,205,255,0.85); font-size: 13px; }}
#promptBar {{ background: rgba(120,140,255,0.18); border-radius: 14px; }}
#promptText {{ font-size: 14px; }}
#course, #cardButton {{ background: rgba(255,255,255,0.10); border: none; border-radius: 10px; padding: 5px 12px; font-size: 13px; }}
#course:hover, #cardButton:hover {{ background: rgba(255,255,255,0.20); }}
#cardButton::menu-indicator {{ image: none; width: 0; }}
#stepList {{ background: transparent; border: none; outline: none; font-size: 13px; }}
#stepList::item {{ padding: 5px 10px; border-radius: 6px; }}
#stepList::item:hover {{ background: rgba(120,140,255,0.45); }}
QMenu {{ background: rgb(40,40,48); color: white; border: 1px solid rgba(255,255,255,0.12); padding: 4px; }}
QMenu::item {{ padding: 5px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: rgba(120,140,255,0.45); }}
"""


class HelperWindow(QWidget):
    """도우미 창. Enter로 보낸 질문은 asked로 알리고, 답 사건은 show_answer_event로 받아 그린다(화면 스레드에서).

    연습 과정 카드와 물음 줄은 show_progress로 받은 모양을 그리기만 하고, 누른 것은 신호로 알린다.
    """

    asked = Signal(str)  # Enter로 보낸 질문
    escape = Signal()  # Esc: Blender로 돌아가기
    chose_course = Signal(str)  # 고른 연습 과정 이름표(처음 고르기·바꾸기)
    went_next = Signal()  # '다음' 버튼(조작을 다 끝냈으면 '다음 단계')
    went_back = Signal()  # '뒤로' 버튼
    skipped_to = Signal(str)  # '단계 ▼' 목록에서 고른 단계 이름표
    answered = Signal(bool)  # 물음에 [네](True)/[아니요](False)

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool)  # Tool: 작업 표시줄·Alt+Tab에 나오지 않음
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # Blender를 따라 보일 때 초점을 빼앗지 않는다
        self.setMouseTracking(True)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setGeometry(_home())
        self.setStyleSheet(STYLE)
        self.put_away = False  # 사용자가 X로 직접 내렸나(F10·트레이로 부를 때까지 내린 채)
        self._busy = False  # 답을 기다리는 중
        self._answer: QLabel | None = None
        self._answer_text = ""
        self._course_labels: tuple[str, ...] = ()  # 고르기 버튼·바꾸기 메뉴를 만든 연습 과정 목록
        self._steps_for: Course | None = None  # 단계 목록을 만든 연습 과정
        self._marked = -1  # 단계 목록에서 ▶로 표시한 줄(0부터)

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
        root.addWidget(self._build_card())

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
        root.addWidget(self._build_prompt())

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

    # ---- 연습 과정 카드와 물음 줄
    def _build_card(self) -> QFrame:
        self.card = QFrame()
        self.card.setObjectName("courseCard")
        self.card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)  # 남는 높이는 대화 칸이 갖는다
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        self._picker = QWidget()  # 고르기 전: 연습 과정 버튼 + 안내
        picker = QVBoxLayout(self._picker)
        picker.setContentsMargins(0, 0, 0, 0)
        picker.setSpacing(6)
        title = QLabel("연습 과정 고르기")
        title.setObjectName("pickTitle")
        picker.addWidget(title)
        self._course_row = QHBoxLayout()
        self._course_row.setSpacing(6)
        picker.addLayout(self._course_row)
        self._pick_hint = QLabel(PICK_HINT)
        self._pick_hint.setObjectName("hint")
        self._pick_hint.setWordWrap(True)
        picker.addWidget(self._pick_hint)
        layout.addWidget(self._picker)

        self._stepper = QWidget()  # 진행 중: 연습 과정 · n단계 / 단계 이름 / 뒤로 · 다음 ··· 단계 ▼
        stepper = QVBoxLayout(self._stepper)
        stepper.setContentsMargins(0, 0, 0, 0)
        stepper.setSpacing(6)
        self._header = QLabel()
        self._header.setObjectName("stepHeader")
        stepper.addWidget(self._header)
        self._name = QLabel()
        self._name.setObjectName("stepName")
        self._name.setWordWrap(True)
        stepper.addWidget(self._name)
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.back_button = _button("◀ 뒤로", "cardButton")
        self.back_button.clicked.connect(self.went_back)
        self.next_button = _button("다음 ▶", "cardButton")
        self.next_button.clicked.connect(self.went_next)
        self.step_button = _button("단계 ▼", "cardButton")
        self.step_button.setMenu(self._build_step_menu())
        row.addWidget(self.back_button)
        row.addWidget(self.next_button)
        row.addStretch()
        row.addWidget(self.step_button)
        stepper.addWidget(buttons)
        layout.addWidget(self._stepper)
        return self.card

    def _build_step_menu(self) -> QMenu:
        """'단계 ▼' 메뉴: 다섯 줄 높이로 스크롤하는 단계 목록, 구분선, 연습 과정 바꾸기(하위 메뉴)."""
        menu = QMenu(self)
        self.step_list = QListWidget()
        self.step_list.setObjectName("stepList")
        self.step_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.step_list.setFocusPolicy(Qt.NoFocus)

        def chosen(item: QListWidgetItem) -> None:
            menu.close()
            self.skipped_to.emit(item.data(Qt.UserRole))

        def opening() -> None:  # 열 때마다 지금 단계가 보이게 스크롤한다(12단계 중 10단계에 있어도 찾아 내려가지 않게)
            if self._marked >= 0:
                self.step_list.scrollToItem(self.step_list.item(self._marked), QAbstractItemView.PositionAtCenter)

        self.step_list.itemClicked.connect(chosen)
        menu.aboutToShow.connect(opening)
        rows = QWidgetAction(menu)
        rows.setDefaultWidget(self.step_list)
        menu.addAction(rows)
        menu.addSeparator()
        self._change_menu = menu.addMenu("연습 과정 바꾸기")
        return menu

    def _build_prompt(self) -> QFrame:
        self.prompt = QFrame()
        self.prompt.setObjectName("promptBar")
        layout = QHBoxLayout(self.prompt)
        layout.setContentsMargins(12, 8, 8, 8)
        self._prompt_text = QLabel()
        self._prompt_text.setObjectName("promptText")
        self._prompt_text.setWordWrap(True)
        layout.addWidget(self._prompt_text, 1)
        self.yes_button = _button("네", "cardButton")
        self.yes_button.clicked.connect(lambda: self.answered.emit(True))
        self.no_button = _button("아니요", "cardButton")
        self.no_button.clicked.connect(lambda: self.answered.emit(False))
        layout.addWidget(self.yes_button)
        layout.addWidget(self.no_button)
        self.prompt.hide()
        return self.prompt

    def show_progress(self, view: StepView | None, courses: list[Course]) -> None:
        """연습 과정 카드와 물음 줄을 그 Blender의 진행 모양대로 다시 그린다. Blender가 없으면(None) 누를 수 없게 둔다."""
        self._set_courses(courses)
        self.card.setEnabled(view is not None)
        view = view or StepView(None, 0, None, None)
        self._picker.setVisible(view.course is None)
        self._stepper.setVisible(view.course is not None)
        if view.course is not None:
            self._show_step(view)
        self._prompt_text.setText(view.prompt or "")
        self.prompt.setVisible(view.prompt is not None)  # 창을 앞으로 끌어오지 않고 창 안에만 띄운다

    def show_line(self, line: Line) -> None:
        """도우미 안내 말(guide)이나 진행 관리의 알림(notice) 한 줄을 대화에 붙인다."""
        self._label(line.text, line.kind)

    def _set_courses(self, courses: list[Course]) -> None:
        """고르기 버튼과 바꾸기 메뉴는 연습 과정 목록이 바뀌었을 때만 다시 만든다(진행 모양은 자주 다시 그린다)."""
        self._pick_hint.setText(PICK_HINT if courses else COURSES_UNREADABLE)
        labels = tuple(course.label for course in courses)
        if labels == self._course_labels:
            return
        self._course_labels = labels
        while self._course_row.count():
            if widget := self._course_row.takeAt(0).widget():
                widget.deleteLater()
        menu = self._change_menu
        menu.clear()
        for course in courses:
            button = _button(course.name, "course")
            button.clicked.connect(lambda _=False, label=course.label: self.chose_course.emit(label))
            self._course_row.addWidget(button)
            button.show()  # 이미 보이는 창에 더한 버튼은 Qt가 다음 차례에야 보이므로 바로 보인다
            menu.addAction(course.name, lambda label=course.label: self.chose_course.emit(label))
        self._course_row.addStretch()

    def _show_step(self, view: StepView) -> None:
        course, step = view.course, view.step
        if course is not self._steps_for:
            self._steps_for = course
            self.step_list.clear()
            for each in course.steps:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, each.label)
                self.step_list.addItem(item)
        self._mark(view.number - 1)
        self.next_button.setVisible(step is not None)
        self.next_button.setText("다음 ▶" if view.operating else "다음 단계 ▶")
        if step is None:
            self._header.setText(f"{course.name} · 다 마쳤어요")
            self._name.setText("다른 연습 과정은 '단계 ▼'의 '연습 과정 바꾸기'에서 고를 수 있어요.")
            return
        self._header.setText(f"{course.name} · {view.number}단계 / {len(course.steps)}")
        self._name.setText(step.name)

    def _mark(self, index: int) -> None:
        """단계 목록의 지금 단계 줄 앞에 ▶(마쳤으면 index가 -1이라 표시 없음). 높이는 다섯 줄까지만."""
        self._marked = index
        for row, each in enumerate(self._steps_for.steps):
            self.step_list.item(row).setText(f"{'▶' if row == index else '  '} {row + 1}. {each.name}")
        rows = min(self.step_list.count(), STEP_ROWS)
        self.step_list.setFixedHeight(self.step_list.sizeHintForRow(0) * rows + 2 * self.step_list.frameWidth())

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

    def show_answer_event(self, event: Event) -> None:
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
        painter.fillPath(path, QColor(22, 22, 28, PANEL_ALPHA))
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
        return resize_edges(pos.x(), pos.y(), self.width(), self.height())

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


def resize_edges(x: int, y: int, width: int, height: int) -> Qt.Edges:
    """창 안 (x, y)를 끌면 늘릴 가장자리. 모서리 네모(CORNER) 안이면 두 가장자리(대각선), 가장자리 띠(EDGE) 안이면 하나."""
    horizontal = Qt.LeftEdge if x < CORNER else Qt.RightEdge if x > width - CORNER else None
    vertical = Qt.TopEdge if y < CORNER else Qt.BottomEdge if y > height - CORNER else None
    if horizontal and vertical:
        return horizontal | vertical
    edges = Qt.Edge(0)
    if x < EDGE:
        edges |= Qt.LeftEdge
    elif x > width - EDGE:
        edges |= Qt.RightEdge
    if y < EDGE:
        edges |= Qt.TopEdge
    elif y > height - EDGE:
        edges |= Qt.BottomEdge
    return edges


def _button(text: str, name: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(name)
    button.setCursor(Qt.PointingHandCursor)
    button.setFocusPolicy(Qt.NoFocus)  # 눌러도 입력칸 초점을 빼앗지 않는다(Enter가 버튼으로 가지 않게)
    return button


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


class Tray:
    """트레이 아이콘: 왼쪽 클릭 = 보이기(숨기지 않음), 오른쪽 메뉴 = 보이기 / 끝내기."""

    TITLE = "Blender 첫걸음 도우미"
    OPEN_BLENDER_FIRST = "Blender를 먼저 열어 주세요"

    def __init__(self, on_show, on_quit):
        self._icon = QSystemTrayIcon(_icon())
        self._menu = QMenu()  # 붙잡아 두어야 메뉴가 지워지지 않는다
        self._show = self._menu.addAction("보이기", on_show)
        self._menu.addAction("끝내기", on_quit)
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(lambda reason: on_show() if reason == QSystemTrayIcon.Trigger else None)
        self._icon.setToolTip(self.TITLE)
        self._icon.show()

    def blender_shown(self, shown: bool) -> None:
        """보이는 Blender가 없으면 메뉴의 보이기를 막고 아이콘 글로 알린다(왼쪽 클릭은 helper가 막음)."""
        self._icon.setToolTip(self.TITLE if shown else self.OPEN_BLENDER_FIRST)
        self._show.setEnabled(shown)


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
