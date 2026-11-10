"""설정 값 읽기의 표(state_tables/)와 애드온 읽기의 Blender 없이 볼 수 있는 부분(HISTORY [270]). 키·Blender 없이 돈다.

Blender 안에서의 읽기(줄 수·시간)는 addon/settings_selftest.py가 따로 본다.
"""

import importlib.util
import json
import sys
import types

import pytest

from blender_tutor import state_tables
from blender_tutor.paths import PROJECT
from blender_tutor.setting_fields import load_bundles

CSV = "갈래6,칸,원래 갈래,쉬운 묶음,바꾼 조작 수,쓸모(참고),갈래\n" + "\n".join([
    "x,BevelModifier.segments,x,x,0,중,3",
    "x,Object.location,x,x,0,상,1",
    "x,Object.rna_type,x,x,0,뺌,뺌",
    "x,MeshVertex.co,x,x,0,하,1-a 메시 편집",
    "x,SubsurfModifier.levels,x,x,0,상,4",
])
BASE = {  # 지어낸 공장값 표(Baseline 모양)
    "exact": {"Object.modifiers[Bevel]|BevelModifier.segments": ["1"], "Object|Object.rna_type": ["'x'"], "Object|Object.location": ["[0.0, 0.0, 0.0]"],
              "Object|Unknown.prop": ["0"], "Object.modifiers[Subsurf]|SubsurfModifier.levels": ["1"]},
    "loose": {"Object.modifiers[]|BevelModifier.segments": ["1"], "Object|Object.rna_type": ["'x'"]},
    "shaky": ["Object|Object.rna_type", "Object|Unknown.prop"],
}


def test_표_만들기는_갈래를_다_남기고_공장값은_견주는_칸만_남긴다(tmp_path):
    groups, factory = tmp_path / "g.csv", tmp_path / "f.json"
    groups.write_text(CSV, encoding="utf-8-sig")
    factory.write_text(json.dumps(BASE), encoding="utf-8")
    rules_path, factory_path = state_tables.build(groups, factory, tmp_path / "out")
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    assert rules["Object.rna_type"] == "뺌" and rules["MeshVertex.co"] == "1-a 메시 편집" and len(rules) == 5
    kept = json.loads(factory_path.read_text(encoding="utf-8"))
    # 견주는 칸: 갈래 1·3·5·6과 표에 없는 칸. 뺌(rna_type)·4(levels)는 공장값 표에서 뺀다
    assert sorted(kept["exact"]) == ["Object.modifiers[Bevel]|BevelModifier.segments", "Object|Object.location", "Object|Unknown.prop"]
    assert sorted(kept["loose"]) == ["Object.modifiers[]|BevelModifier.segments"] and kept["shaky"] == ["Object|Unknown.prop"]


def test_저장소의_표는_읽히고_묶음_칸은_갈래_표에_있다():
    rules = json.loads((PROJECT / "state_tables" / "rules.json").read_text(encoding="utf-8"))
    factory = json.loads((PROJECT / "state_tables" / "factory.json").read_text(encoding="utf-8"))
    assert set(factory) == {"exact", "loose", "shaky"} and factory["exact"]
    assert all(state_tables.compared(key.rsplit("|", 1)[1], rules) for key in factory["exact"])
    missing = {site for sites in load_bundles().values() for site in sites if site not in rules}
    assert not missing, sorted(missing)[:10]


# ---- 애드온 읽기의 순수한 부분(bpy를 가짜로 끼워 불러온다) ----


@pytest.fixture
def reader(monkeypatch):
    fake = types.ModuleType("bpy")
    fake.types = types.SimpleNamespace(ID=type("ID", (), {}), bpy_struct=type("bpy_struct", (), {}), Object=type("Object", (), {}), LayerCollection=type("LC", (), {}))
    monkeypatch.setitem(sys.modules, "bpy", fake)
    monkeypatch.setitem(sys.modules, "bmesh", types.ModuleType("bmesh"))
    spec =importlib.util.spec_from_file_location("settings_reader_test", PROJECT / "addon" / "blender_tutor_addon" / "settings_reader.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_공장값과_견주기는_정확한_칸_다음_이름_지운_칸_모르면_보냄(reader):
    tables = {"exact": {"Object.modifiers[Bevel]|BevelModifier.segments": {"1"}}, "loose": {"Object.modifiers[]|BevelModifier.segments": {"1"}},
              "shaky": {"Object|Object.hide_viewport"}}
    assert not reader._differs(tables, "Object.modifiers[Bevel]|BevelModifier.segments", "1")
    assert reader._differs(tables, "Object.modifiers[Bevel]|BevelModifier.segments", "3")
    assert not reader._differs(tables, "Object.modifiers[Bevel.001]|BevelModifier.segments", "1")  # 이름을 바꾼 항목은 이름 지운 모양으로
    assert reader._differs(tables, "Object|Object.hide_viewport", "False")  # 흔들리는 칸은 늘 보냄
    assert reader._differs(tables, "Object|Object.never_seen", "0")  # 공장값을 모르면 보냄


def test_한_줄은_자리_칸_값이고_긴_값은_잘라_총_글자_수를_붙인다(reader):
    assert reader._line("Object[Cube].modifiers[Bevel]|BevelModifier.segments", "3") == "Object[Cube].modifiers[Bevel].segments = 3"
    assert reader._line("Object[Cube]|Object.select_get()", "True") == "Object[Cube].select_get() = True"
    assert reader._line('Object[Cube]|Object["note"]', "'x'") == 'Object[Cube]["note"] = \'x\''
    long = reader._line("BlendData|BlendData.objects", "'" + "a" * 300 + "'")
    assert long.endswith("…(총 302자)") and len(long) < 220


def test_점_면처럼_크기만큼_느는_칸과_화면_기록_칸은_가린다(reader):
    assert reader._is_element("MeshVertex.co") and reader._is_element("FloatAttribute.data") and not reader._is_element("Attribute.name")
    assert reader._not_sent("SpaceView3D.lens") and reader._not_sent("OBJECT_OT_join.x") and not reader._not_sent("BevelModifier.width")


def test_뼈와_곡선_점은_활성_고른_것만_같이_고른_뼈는_위치만(reader):
    scope = reader._Scope.__new__(reader._Scope)  # 범위 계산(Blender 필요)을 건너뛰고 고른 결과만 지어 넣는다
    scope.actives, scope.picked = {"edit_bones": "B050"}, {"edit_bones": {"B051"}}
    scope.picked_points = {"Curve[C].splines[0].bezier_points[40]", "Lattice[L].points[7]"}
    assert scope.item_ok("Armature[R].edit_bones[B050]", "EditBone.roll")  # 활성 뼈는 다
    assert scope.item_ok("Armature[R].edit_bones[B051]", "EditBone.head") and not scope.item_ok("Armature[R].edit_bones[B051]", "EditBone.roll")
    assert not scope.item_ok("Armature[R].edit_bones[B099]", "EditBone.head")  # 안 고른 뼈
    assert scope.point_ok("Curve[C].splines[0].bezier_points[40]") and not scope.point_ok("Curve[C].splines[0].bezier_points[41]")
    assert scope.point_ok("Lattice[L].points[7]") and not scope.point_ok("Lattice[L].points[0]")
    assert scope.point_ok("Brush[Draw].curve.curves[0].points[3]")  # 붓 감쇠 곡선 같은 설정의 점은 점 항목이 아니다
    assert reader._unpicked_flag("Curve[C].splines[0].bezier_points[40]|BezierSplinePoint.select_left_handle", "False")
    assert not reader._unpicked_flag("Curve[C].splines[0].bezier_points[40]|BezierSplinePoint.select_control_point", "True")


def test_사용자_폴더가_든_공장값은_표에_넣지_않는다():
    from blender_tutor.state_tables import factory_from

    base = {"exact": {"Prefs|UserAssetLibrary.path": ["'C:\\Users\\누구\\Assets'"], "Scene|Scene.frame_end": ["250"]},
            "loose": {"Prefs[]|UserAssetLibrary.path": ["'/home/누구/x'"]}, "shaky": []}
    made = factory_from(base, {"UserAssetLibrary.path": "3", "Scene.frame_end": "3"})
    assert made["exact"] == {"Scene|Scene.frame_end": ["250"]} and made["loose"] == {}
