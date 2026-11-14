"""분야 고르기와 설정 값 줄(명세 "답 엔진"의 분야 고르기, HISTORY [270]).

가짜 분야 모델을 끼우고 지어낸 설정 줄(Blender에서 읽은 값 아님)로 시험한다. 키 없이 돈다.
"""

import threading
from dataclasses import replace

import pytest

from blender_tutor.answer_engine import AnswerEngine, Done, Settings
from blender_tutor.setting_fields import (
    MAX_LINES, SettingLines, choose_fields, field_schema, lines_for, load_bundles, load_fields,
)
from tests.test_answer_engine import CHUNKS, STATE, VECTORS, FakeEmbedder, FakeModel, FakeRewriter

FIELDS = {"MO": "모디파이어", "MT": "재질", "RD": "렌더"}
SETTINGS = SettingLines(
    ("bpy.context.object.location = (0, 0, 0)",),
    {"MO": ("bpy.context.object.modifiers['Bevel'].segments = 1",), "RD": ("bpy.context.scene.render.engine = 'BLENDER_EEVEE'",)},
)


class FakeFieldModel:
    """정해 둔 답(또는 오류)을 돌려주고 받은 글·스키마·한도를 적어 둔다. wait을 주면 그만큼 열릴 때까지 기다린다."""

    def __init__(self, answer=None, error: Exception | None = None, wait: threading.Event | None = None):
        self.answer = {"분야": ["MO"]} if answer is None else answer
        self.error, self.wait = error, wait
        self.calls = []

    def ask_json(self, messages, schema, timeout=None):
        self.calls.append((messages, schema, timeout))
        if self.wait:
            self.wait.wait(5)
        if self.error:
            raise self.error
        return self.answer


# 자료 파일


def test_저장소의_분야_목록과_묶음은_같은_32분야다():
    fields, bundles = load_fields(), load_bundles()
    assert len(fields) == 32 and set(bundles) == set(fields)
    assert all(cells and all("." in cell for cell in cells) for cells in bundles.values())


def test_분야_스키마는_분야_코드만_받는다():
    schema = field_schema(["MT", "MO"])
    assert schema["properties"]["분야"]["items"]["enum"] == ["MO", "MT"] and schema["additionalProperties"] is False


# 분야 고르기


def test_분야_고르기는_질문_검색어_작업_상태를_주고_고른_차례대로_돌려준다():
    model = FakeFieldModel({"분야": ["RD", "MO", "RD"]})
    assert choose_fields(model, FIELDS, "왜 어둡지?", "render dark", {"mode": "OBJECT"}, 3.0) == ("RD", "MO")
    messages, schema, timeout = model.calls[0]
    assert '"MO": "모디파이어"' in messages[0]["content"] and timeout == 3.0
    assert messages[1]["content"] == '{"질문": "왜 어둡지?", "검색어": "render dark", "작업 상태": {"mode": "OBJECT"}}'


@pytest.mark.parametrize("answer", [{"분야": []}, {"분야": ["MO", "MT", "RD", "MO", "MT"]}, {"분야": "MO"}, {"분야": ["ZZ"]}, []])
def test_분야_고르기_답이_모양에_안_맞으면_ValueError(answer):
    with pytest.raises(ValueError):
        choose_fields(FakeFieldModel(answer), FIELDS, "질문", "query", {}, 1.0)


# 설정 값 줄


def test_설정_값은_들어오는_곳에서_모양을_검사한다():
    assert SettingLines.from_json(SETTINGS.to_json()) == SETTINGS
    empty = {"always": [], "situation": [], "computed": [], "fields": {}}
    for bad in ({"always": []}, {**empty, "always": "x"}, {**empty, "fields": {"MO": [1]}}, [], {**empty, "x": 1}, {**empty, "situation": [2]}):
        with pytest.raises(ValueError):
            SettingLines.from_json(bad)


def test_넘길_줄은_늘_보내는_줄_다음에_고른_분야_차례로_겹침_없이_한도까지():
    settings = SettingLines(("a",), {"MO": ("b", "a"), "RD": ("c",)}, situation=("상황",), computed=("계산",))
    assert lines_for(settings, ("RD", "MO")) == ["a", "상황", "계산", "c", "b"]
    assert lines_for(settings, ("RD",), situation=False, computed=False) == ["a", "c"]  # 1-a·2 초안을 끈 판
    assert lines_for(settings, ()) == ["a", "상황", "계산"]
    many = SettingLines(tuple(f"줄{i}" for i in range(MAX_LINES + 5)), {})
    assert len(lines_for(many, ())) == MAX_LINES


def test_설정_줄에_든_사용자_폴더는_가리고_나머지_경로는_그대로_넘긴다():
    # 줄의 값은 Blender에서 읽은 값의 repr 글이라 Windows 구분 글자가 둘씩 겹쳐 있다. 계정 이름이 모델에 가지 않게 한다(HISTORY [323])
    settings = SettingLines(
        (
            r"Preferences.filepaths.asset_libraries[User Library].path = 'C:\\Users\\some one\\Documents\\Blender\\Assets'",
            "Image[wood].filepath = '/Users/someone/Pictures/wood.png'",
            "Image[linux].filepath = '/home/someone/wood.png'",
            r"Scene[Scene].render.filepath = '/tmp\\'",  # 사용자 폴더가 아닌 절대 경로
            "Image[rel].filepath = '//textures/wood.png'",  # .blend 기준 상대 경로
            "Text[note].name = 'https://example.com/home/page'",  # 경로가 아닌 글
        ),
        {"MO": (r"Preferences.filepaths.temporary_directory = 'D:\\Users\\someone\\Temp\\'",)},
    )
    assert lines_for(settings, ("MO",)) == [
        r"Preferences.filepaths.asset_libraries[User Library].path = '(사용자 폴더)\\Documents\\Blender\\Assets'",
        "Image[wood].filepath = '(사용자 폴더)/Pictures/wood.png'",
        "Image[linux].filepath = '(사용자 폴더)/wood.png'",
        r"Scene[Scene].render.filepath = '/tmp\\'",
        "Image[rel].filepath = '//textures/wood.png'",
        "Text[note].name = 'https://example.com/home/page'",
        r"Preferences.filepaths.temporary_directory = '(사용자 폴더)\\Temp\\'",
    ]


# 답 엔진에 붙였을 때


def engine(field_model=None, model=None, fallback=None, settings=Settings(), rewriters=None):
    return AnswerEngine(
        CHUNKS, VECTORS, FakeEmbedder(), model or FakeModel(), settings,
        rewriters=rewriters or [FakeRewriter('{"query": "bevel width"}')],
        field_model=field_model, fields=FIELDS if field_model else None, fallback_model=fallback,
    )


def test_설정_값을_받으면_분야를_골라_늘_보내는_줄과_그_분야_줄을_답변_모델에_넘긴다():
    model, field_model = FakeModel(), FakeFieldModel({"분야": ["MO"]})
    events = list(engine(field_model, model).answer("베벨이 안 둥글어", STATE, [], settings=SETTINGS))
    content = model.calls[0][-1]["content"]
    assert "# 설정 값" in content and "location = (0, 0, 0)" in content and "segments = 1" in content
    assert "render.engine" not in content  # 고르지 않은 분야의 줄은 넘기지 않는다
    assert '"검색어": "bevel width"' in field_model.calls[0][0][1]["content"]  # 바꾼 검색어로 고른다
    assert isinstance(events[-1], Done) and events[-1].fields == ("MO",) and not events[-1].field_failed
    # 평가에서 검색이 왜 흔들리는지 보려고 바꾼 검색어와 실제로 넘긴 설정 줄을 알린다
    assert events[-1].query == "bevel width"
    assert events[-1].lines == ("bpy.context.object.location = (0, 0, 0)", "bpy.context.object.modifiers['Bevel'].segments = 1")


def test_분야_고르기에도_열린_파일은_폴더_없이_파일_이름만_넘긴다():
    field_model = FakeFieldModel({"분야": ["MO"]})
    state = replace(STATE, file_path="C:\\Users\\someone\\scenes\\boolean_wrong\\상자.blend")
    list(engine(field_model).answer("베벨이 안 둥글어", state, [], settings=SETTINGS))
    sent = field_model.calls[0][0][1]["content"]
    assert '"file_path": "상자.blend"' in sent and "someone" not in sent and "boolean_wrong" not in sent


def test_분야_고르기가_실패하면_묶음_없이_생각을_올린_모델로_답한다():
    model, fallback = FakeModel(), FakeModel(("생각한 답",))
    events = list(engine(FakeFieldModel(error=RuntimeError("끊김")), model, fallback).answer("베벨", STATE, [], settings=SETTINGS))
    assert not model.calls and fallback.calls
    content = fallback.calls[0][-1]["content"]
    assert "location = (0, 0, 0)" in content and "segments = 1" not in content
    assert events[-1].fields == () and events[-1].field_failed


def test_분야_고르기가_한도를_넘기면_기다리지_않고_실패로_본다():
    hold = threading.Event()
    fallback = FakeModel(("생각한 답",))
    events = list(engine(FakeFieldModel(wait=hold), FakeModel(), fallback, Settings(field_timeout=0.05)).answer("베벨", STATE, [], settings=SETTINGS))
    hold.set()
    assert events[-1].field_failed and fallback.calls


def test_분야_묶음을_끄면_분야를_고르지_않고_늘_보내는_줄만_넘긴다():
    model, field_model = FakeModel(), FakeFieldModel()
    events = list(engine(field_model, model, settings=Settings(field_lines=False)).answer("베벨", STATE, [], settings=SETTINGS))
    content = model.calls[0][-1]["content"]
    assert not field_model.calls and "location = (0, 0, 0)" in content and "segments = 1" not in content
    assert events[-1].fields == () and not events[-1].field_failed


def test_설정_값이_없으면_분야를_고르지_않고_설정_칸도_넣지_않는다():
    model, field_model = FakeModel(), FakeFieldModel()
    events = list(engine(field_model, model).answer("베벨", STATE, []))
    assert not field_model.calls and "# 설정 값" not in model.calls[0][-1]["content"]
    assert events[-1].fields == () and not events[-1].field_failed


def test_분야_모델과_분야_목록은_함께_줘야_한다():
    with pytest.raises(ValueError):
        AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(), field_model=FakeFieldModel())
