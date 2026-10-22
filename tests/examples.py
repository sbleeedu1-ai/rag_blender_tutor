"""여러 테스트 파일이 함께 쓰는 예시(손으로 쓴 것). 고치면 이것을 쓰는 테스트가 모두 영향받는다."""

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
