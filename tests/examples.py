"""여러 테스트 파일이 함께 쓰는 예시(손으로 쓴 것)와 도구. 고치면 이것을 쓰는 테스트가 모두 영향받는다."""

import json
import urllib.error
import urllib.request

from blender_tutor.receiver import TOKEN_HEADER

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
        "location": [0.0, 0.0, -3.5],
    },
    "selected_objects": ["실린더", "Cube"],
    "language": "ko_KR",
    "translate_interface": True,
    "file_path": "C:/work/sword.blend",
    "scene_object_count": 3,
    "blender_version": "5.2.2",
    "edit_selected": {"VERT": 4},
    "recent_operators": ["mesh.select_all", "mesh.merge"],
    "running_operators": [],
    "view": {"distance": 18.388, "rotation": [0.712, 0.441, 0.287, 0.464], "center": [0.0, 0.0, 0.0]},
}

TOKEN = "test-token"  # 받는 쪽 시험의 비밀 글자


def send(
    receiver, window, pid, state=EDITING, *, summon=False, event=None, pressed=None, token=TOKEN, path="/state", body=None
) -> int:
    """애드온처럼 보내고 응답 번호를 돌려준다."""
    if body is None:
        body = {"window": window, "pid": pid, "state": state, "summon": summon, "event": event, "pressed": pressed}
    request = urllib.request.Request(
        f"http://127.0.0.1:{receiver.port}{path}",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", TOKEN_HEADER: token},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
