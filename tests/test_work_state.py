"""작업 상태 모양: 애드온이 보낸 JSON ↔ 진행 관리·답 엔진이 함께 쓰는 WorkState."""

import pytest

from blender_tutor.work_state import ActiveObject, WorkState

# 애드온이 편집 모드에서 보내는 JSON(손으로 쓴 예)
EDITING = {
    "mode": "EDIT_MESH",
    "active_object": {
        "name": "실린더",
        "type": "MESH",
        "modifiers": ["BEVEL"],
        "scale": [1.0, 1.0, 2.0],
        "dimensions": [2.0, 2.0, 4.0],
        "material_slot_count": 1,
    },
    "selected_objects": ["실린더", "Cube"],
    "language": "ko_KR",
    "translate_interface": True,
    "file_path": "C:/work/sword.blend",
    "scene_object_count": 3,
    "blender_version": "5.2.2",
    "edit_selected": {"VERT": 4},
    "recent_operators": ["mesh.select_all", "mesh.merge"],
}


def test_애드온이_보낸_JSON을_읽는다():
    state = WorkState.from_json(EDITING)
    assert state.mode == "EDIT_MESH"
    assert state.active_object == ActiveObject("실린더", "MESH", ("BEVEL",), (1.0, 1.0, 2.0), (2.0, 2.0, 4.0), 1)
    assert state.selected_objects == ("실린더", "Cube")
    assert state.edit_selected == {"VERT": 4}
    assert state.recent_operators == ("mesh.select_all", "mesh.merge")


def test_JSON으로_되돌리면_받은_것과_같다():
    assert WorkState.from_json(EDITING).to_json() == EDITING


def test_활성_물체가_없어도_읽는다():
    state = WorkState.from_json({**EDITING, "active_object": None})
    assert state.active_object is None
    assert state.to_json()["active_object"] is None


@pytest.mark.parametrize(
    "broken",
    [
        {key: value for key, value in EDITING.items() if key != "mode"},  # 빠진 칸
        {**EDITING, "unknown": 1},  # 모르는 칸
        {**EDITING, "scene_object_count": "3"},  # 꼴이 틀린 칸
        {**EDITING, "active_object": {**EDITING["active_object"], "scale": [1.0, 1.0]}},  # 숫자 셋이 아님
    ],
)
def test_모양이_틀린_JSON은_받지_않는다(broken):
    with pytest.raises(ValueError):
        WorkState.from_json(broken)
