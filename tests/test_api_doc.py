"""공식 문서 항목 보기(.claude/tools/api_doc.py, HISTORY [214]). 실제 문서 없이 돈다."""

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / ".claude" / "tools" / "api_doc.py"
spec = importlib.util.spec_from_file_location("api_doc", TOOL)
api_doc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_doc)

OPS = """Sculpt Operators¶
bpy.ops.sculpt.brush_stroke(*, stroke=None, override_location=False)¶
Sculpt a stroke into the geometry
Parameters:
override_location (bool) – Override Location, recalculating (optional)
bpy.ops.sculpt.brush_stroke_extra()¶
다른 조작
"""
TYPE = """View3DShading(bpy_struct)¶
class bpy.types.View3DShading(bpy_struct)¶
aov_name¶
Name of the AOV
selected_studio_light¶
Selected StudioLight (readonly)
Type:
StudioLight | None
"""


@pytest.fixture
def docs(tmp_path):
    (tmp_path / "bpy.ops.sculpt.txt").write_text(OPS, encoding="utf-8")
    (tmp_path / "bpy.types.View3DShading.txt").write_text(TYPE, encoding="utf-8")
    return tmp_path


def test_조작_항목을_인자_설명까지_다음_항목_앞까지_보여_준다(docs):
    text = api_doc.lookup("bpy.ops.sculpt.brush_stroke", docs)
    assert "override_location (bool)" in text
    assert "brush_stroke_extra" not in text
    assert text.startswith("bpy.ops.sculpt.txt 2-5줄 (파일 7줄)")
    assert "5: override_location (bool)" in text


def test_타입의_마지막_항목은_파일_끝까지_보여_준다(docs):
    text = api_doc.lookup("bpy.types.View3DShading.selected_studio_light", docs)
    assert "StudioLight | None" in text
    assert "aov_name" not in text


def test_타입_이름만_주면_파일_전체를_보여_준다(docs):
    text = api_doc.lookup("bpy.types.View3DShading", docs)
    assert "aov_name" in text and "selected_studio_light" in text


@pytest.mark.parametrize("name", ["bpy.types.없는타입", "bpy.types.View3DShading.없는칸", "bpy.types.View3DShading.selected"])
def test_못_찾으면_None(docs, name):
    assert api_doc.lookup(name, docs) is None
