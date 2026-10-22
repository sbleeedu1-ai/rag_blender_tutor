"""도우미 창 위젯(티켓 26): 화면 없이(offscreen) 띄워 질문 보내기·답 흐름·근거·오류·X를 본다.

모양·한글 입력·F10·Blender 따라가기는 강의실 PC 눈 확인으로 본다.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # QApplication보다 먼저

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from blender_tutor.answer_engine import Done, Failure, Piece, Source
from blender_tutor.helper_window import HelperWindow

BEVEL = Source("Bevel Modifier > Options", "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options", True, True, ("https://example.org/bevel.mp4",))
ARRAY = Source("Array Modifier", "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html#array-modifier", False, False, ())


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    window = HelperWindow()
    window.asked_questions = []
    window.asked.connect(window.asked_questions.append)
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
