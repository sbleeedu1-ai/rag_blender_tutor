"""도우미 창 위젯(티켓 26·27): 화면 없이(offscreen) 띄워 질문 보내기·답 흐름·근거·오류·X와 연습 과정 카드를 본다.

모양·한글 입력·F10·Blender 따라가기는 강의실 PC 눈 확인으로 본다.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # QApplication보다 먼저

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from blender_tutor.answer_engine import Done, Failure, Piece, Source
from blender_tutor.course_desk import Line, LineKind, StepView
from blender_tutor.helper_window import COURSES_UNREADABLE, PICK_HINT, HelperWindow, resize_edges
from blender_tutor.progress import Course, Operation, Step

BEVEL = Source("Bevel Modifier > Options", "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options", True, True, ("https://example.org/bevel.mp4",))
ARRAY = Source("Array Modifier", "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html#array-modifier", False, False, ())


TIP = Step("blade-tip", "칼끝 모으기", operations=(Operation("가운데로 모으기", "Mesh > Merge > At Center", "M", "M으로 모아 보세요."),))
SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), TIP, Step("join", "부품 합치기")))
SHIELD = Course("shield", "방패", (Step("view", "화면 돌려 보기"),))
COURSES = [SWORD, SHIELD]
AT_TIP = StepView(SWORD, 2, TIP, None)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    window = HelperWindow()
    window.asked_questions = []
    window.asked.connect(window.asked_questions.append)
    window.sent = []  # 연습 과정 카드에서 나간 신호
    window.chose_course.connect(lambda label: window.sent.append(("고름", label)))
    window.went_next.connect(lambda: window.sent.append(("다음",)))
    window.went_back.connect(lambda: window.sent.append(("뒤로",)))
    window.skipped_to.connect(lambda label: window.sent.append(("건너뜀", label)))
    window.answered.connect(lambda yes: window.sent.append(("답", yes)))
    window.show()
    yield window
    window.close()


def type_and_enter(window: HelperWindow, text: str) -> None:
    window.input.setText(text)  # 한글 조합은 화면 없이 흉내 낼 수 없어 글을 바로 넣는다
    QTest.keyClick(window.input, Qt.Key_Return)


def texts(window: HelperWindow, name: str) -> list[str]:
    return [label.text() for label in window.findChildren(QLabel, name)]


def test_Enter_한_번에_질문을_보내고_입력칸을_비운다(window):
    type_and_enter(window, "  베벨 어디 있어요?  ")
    assert window.asked_questions == ["베벨 어디 있어요?"]
    assert window.input.text() == ""
    assert texts(window, "question") == ["베벨 어디 있어요?"]


def test_빈_질문과_답을_기다리는_동안의_질문은_보내지_않는다(window):
    type_and_enter(window, "   ")
    type_and_enter(window, "가")
    type_and_enter(window, "나")
    assert window.asked_questions == ["가"]
    assert window.input.text() == "나"  # 쓴 글은 지우지 않고 남긴다


def test_답_조각을_이어_붙이고_문장마다_줄을_바꾼다(window):
    type_and_enter(window, "가")
    for text in ("Tab을 눌", "러요. Blender 5.", "2에서도 같아요."):
        window.show_answer_event(Piece(text))
    assert texts(window, "answer") == ["Tab을 눌러요.\nBlender 5.2에서도 같아요."]


def test_근거는_끝에_한꺼번에_링크와_그림_영상_표시로_붙고_다시_보낼_수_있다(window):
    type_and_enter(window, "가")
    window.show_answer_event(Piece("답이에요."))
    window.show_answer_event(Done((BEVEL, ARRAY), ()))
    [bevel, array] = texts(window, "source")
    assert f"href='{BEVEL.url}'" in bevel and "Bevel Modifier &gt; Options" in bevel and "그림 있음 · 영상 있음" in bevel
    assert f"href='{ARRAY.url}'" in array and "있음" not in array
    assert all(label.openExternalLinks() for label in window.findChildren(QLabel, "source"))  # 누르면 브라우저로 설명서가 열린다
    type_and_enter(window, "나")
    assert window.asked_questions == ["가", "나"]


def test_오류는_짧은_문구로_보이고_다시_보낼_수_있다(window):
    type_and_enter(window, "가")
    window.show_answer_event(Failure("답이 너무 늦어져 멈췄어요."))
    assert texts(window, "failure") == ["답이 너무 늦어져 멈췄어요."]
    type_and_enter(window, "나")
    assert window.asked_questions == ["가", "나"]


def test_질문과_답은_서식_없이_글_그대로_보인다(window):
    type_and_enter(window, "<b>굵게</b>")
    window.show_answer_event(Piece("<i>기울임</i>"))
    labels = window.findChildren(QLabel, "question") + window.findChildren(QLabel, "answer")
    assert all(label.textFormat() == Qt.PlainText for label in labels)


def test_X로_내리면_숨기고_부르면_다시_보이며_입력칸에_초점(window):
    window.close_button.click()
    assert not window.isVisible() and window.put_away
    window.summon()
    assert window.isVisible() and not window.put_away


def test_Esc는_Blender로_돌아가라고_알린다(window):
    escaped = []
    window.escape.connect(lambda: escaped.append(True))
    QTest.keyClick(window.input, Qt.Key_Escape)
    assert escaped == [True]


def test_모서리_근처를_끌면_대각선으로_늘린다():
    # 둥근 모서리(반지름 22)의 투명한 곳은 Windows가 클릭을 아래 창으로 넘기므로, 모서리 구역을 가장자리를 따라 넓게 잡는다
    size = (420, 560)
    assert resize_edges(2, 20, *size) == Qt.LeftEdge | Qt.TopEdge
    assert resize_edges(20, 2, *size) == Qt.LeftEdge | Qt.TopEdge
    assert resize_edges(417, 550, *size) == Qt.RightEdge | Qt.BottomEdge
    assert resize_edges(2, 300, *size) == Qt.LeftEdge  # 가운데는 가로만
    assert not resize_edges(200, 300, *size)  # 안쪽은 늘리지 않음


def test_연습_과정을_고르지_않았으면_목록과_자유_질문_안내를_보이고_누르면_고른다(window):
    window.show_progress(StepView(None, 0, None, None), COURSES)
    buttons = [b for b in window.findChildren(QPushButton, "course") if b.isVisible()]
    assert [b.text() for b in buttons] == ["검", "방패"]
    assert "물어보세요" in " ".join(texts(window, "hint"))
    buttons[1].click()
    assert window.sent == [("고름", "shield")]


def test_단계_카드는_n단계와_이름만_보이고_버튼은_뒤로_다음_그리고_오른쪽_끝에_단계(window):
    window.show_progress(AT_TIP, COURSES)
    assert texts(window, "stepHeader") == ["검 · 2단계 / 3"]
    assert texts(window, "stepName") == ["칼끝 모으기"]
    assert window.step_button.text() == "단계 ▼"
    buttons = window.back_button.parentWidget().layout()
    order = [buttons.itemAt(i).widget() for i in range(buttons.count())]
    assert order == [window.back_button, window.next_button, None, window.step_button]  # 사용자가 정한 차례(None은 빈 칸)
    window.back_button.click()
    window.next_button.click()
    assert window.sent == [("뒤로",), ("다음",)]


def test_다음_버튼은_안내_중인_조작이_있으면_다음_다_끝냈으면_다음_단계(window):
    window.show_progress(StepView(SWORD, 2, TIP, None, operating=True), COURSES)
    assert window.next_button.text() == "다음 ▶"
    window.show_progress(AT_TIP, COURSES)
    assert window.next_button.text() == "다음 단계 ▶"


def step_rows(window: HelperWindow) -> list[str]:
    return [window.step_list.item(i).text() for i in range(window.step_list.count())]


def test_단계_목록은_지금_단계를_표시하고_고르면_건너뛴다(window):
    window.show_progress(AT_TIP, COURSES)
    assert step_rows(window) == ["   1. 화면 돌려 보기", "▶ 2. 칼끝 모으기", "   3. 부품 합치기"]
    window.show_progress(StepView(SWORD, 3, SWORD.steps[2], None), COURSES)
    assert step_rows(window)[2] == "▶ 3. 부품 합치기"
    window.step_list.itemClicked.emit(window.step_list.item(0))
    assert window.sent == [("건너뜀", "view")]


def test_단계_목록은_다섯_줄_높이로_스크롤하고_열면_지금_단계가_보인다(window, app):
    long = Course("long", "긴 과정", tuple(Step(f"s{n}", f"단계 {n}") for n in range(1, 13)))
    rows, menu = window.step_list, window.step_button.menu()

    def open_and_see(number: int) -> bool:
        window.show_progress(StepView(long, number, long.steps[number - 1], None), [long])
        menu.popup(window.step_button.mapToGlobal(QPoint(0, 0)))
        app.processEvents()
        seen = rows.viewport().rect().intersects(rows.visualItemRect(rows.item(number - 1)))
        menu.close()
        return seen

    assert open_and_see(1)
    assert rows.viewport().height() < rows.sizeHintForRow(0) * 6  # 12줄을 다 보이지 않고 다섯 줄
    assert not rows.viewport().rect().intersects(rows.visualItemRect(rows.item(9)))  # 10단계는 스크롤해야 보인다
    assert open_and_see(10)


def test_다른_연습_과정으로_바꾸기는_단계_목록_아래의_메뉴에서_고른다(window):
    window.show_progress(AT_TIP, COURSES)
    [change] = [action for action in window.step_button.menu().actions() if action.menu()]
    assert change.text() == "연습 과정 바꾸기"
    {action.text(): action for action in change.menu().actions()}["방패"].trigger()
    assert window.sent == [("고름", "shield")]


def test_물음은_입력칸_위에_네_아니요로_띄우고_없으면_거둔다(window):
    window.show_progress(StepView(SWORD, 2, TIP, "다음 단계로 갈까요?"), COURSES)
    assert window.prompt.isVisible() and texts(window, "promptText") == ["다음 단계로 갈까요?"]
    window.yes_button.click()
    window.no_button.click()
    assert window.sent == [("답", True), ("답", False)]
    window.show_progress(AT_TIP, COURSES)
    assert not window.prompt.isVisible()


def test_연습_과정을_마치면_마쳤다고_보이고_뒤로_갈_수_있다(window):
    window.show_progress(StepView(SWORD, 0, None, None), COURSES)
    assert texts(window, "stepHeader") == ["검 · 다 마쳤어요"]
    assert not window.next_button.isVisible()
    window.back_button.click()
    assert window.sent == [("뒤로",)]


def test_blender가_없으면_카드를_누를_수_없다(window):
    window.show_progress(None, COURSES)
    assert not window.card.isEnabled()
    window.show_progress(AT_TIP, COURSES)
    assert window.card.isEnabled()


def test_안내_말과_알림은_대화에_한_줄씩_붙는다(window):
    window.show_line(Line(LineKind.GUIDE, "정육면체를 눌러 보시겠어요?"))
    window.show_line(Line(LineKind.NOTICE, "이 파일에서 검 연습 과정을 다 마쳤어요."))
    assert texts(window, "guide") == ["정육면체를 눌러 보시겠어요?"]
    assert texts(window, "notice") == ["이 파일에서 검 연습 과정을 다 마쳤어요."]


def test_연습_과정을_하나도_읽지_못했으면_고르기_카드에_그렇다고_보인다(window):
    # 연습 과정 파일이 깨졌을 때(helper._courses가 빈 목록을 줌). 원래 연습 과정이 없는 프로그램처럼 보이지 않게
    window.show_progress(StepView(None, 0, None, None), [])
    assert texts(window, "hint") == [COURSES_UNREADABLE]
    window.show_progress(StepView(None, 0, None, None), COURSES)
    assert texts(window, "hint") == [PICK_HINT]
