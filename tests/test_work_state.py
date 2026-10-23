"""작업 상태 모양: 애드온이 보낸 JSON ↔ 진행 관리·답 엔진이 함께 쓰는 WorkState."""

import pytest

from blender_tutor.work_state import ActiveObject, View, WorkState
from tests.examples import EDITING


def test_애드온이_보낸_JSON을_읽는다():
    state = WorkState.from_json(EDITING)
    assert state.mode == "EDIT_MESH"
    assert state.active_object == ActiveObject("실린더", "MESH", ("BEVEL",), (1.0, 1.0, 2.0), (2.0, 2.0, 4.0), 1, (0.0, 0.0, -3.5))
    assert state.selected_objects == ("실린더", "Cube")
    assert state.edit_selected == {"VERT": 4}
    assert state.recent_operators == ("mesh.select_all", "mesh.merge")
    assert state.running_operators == ()
    assert state.view == View(18.388, (0.712, 0.441, 0.287, 0.464), (0.0, 0.0, 0.0))


def test_JSON으로_되돌리면_받은_것과_같다():
    assert WorkState.from_json(EDITING).to_json() == EDITING


def test_활성_물체가_없어도_읽는다():
    state = WorkState.from_json({**EDITING, "active_object": None})
    assert state.active_object is None
    assert state.to_json()["active_object"] is None


def test_3D_화면이_없어도_읽는다():
    state = WorkState.from_json({**EDITING, "view": None})
    assert state.view is None
    assert state.to_json()["view"] is None


@pytest.mark.parametrize(
    "broken",
    [
        {key: value for key, value in EDITING.items() if key != "mode"},  # 빠진 칸
        {**EDITING, "unknown": 1},  # 모르는 칸
        {**EDITING, "scene_object_count": "3"},  # 꼴이 틀린 칸
        {**EDITING, "active_object": {**EDITING["active_object"], "scale": [1.0, 1.0]}},  # 숫자 셋이 아님
        {**EDITING, "view": {**EDITING["view"], "rotation": [1.0, 0.0, 0.0]}},  # 각도가 숫자 넷이 아님
    ],
)
def test_모양이_틀린_JSON은_받지_않는다(broken):
    with pytest.raises(ValueError):
        WorkState.from_json(broken)
