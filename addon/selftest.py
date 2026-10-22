"""애드온 자체 시험: Blender 5.2를 화면 없이 띄워 작업 상태 읽기와 보내기를 확인한다(기본 테스트 밖, 명세 Testing Decisions).

실행(프로젝트 폴더): .venv\\Scripts\\python addon\\selftest.py
Blender 위치가 다르면 환경 변수 BLENDER로 알려 준다.

확인하는 것: 애드온 켜기(설치 명령으로 임시 폴더에 설치), 12칸 읽기와 WorkState 모양 맞음, 조작 이름 바꾸기,
편집 모드 선택 방식·개수와 읽기 시간, 바뀐 때만 보내기, 파일 사건, glTF 내보내기 잡기, 화면 언어,
도우미 프로그램 켜기(이미 켜져 있으면 그것을 씀)와 Blender가 닫히면 꺼지기.
화면 없이는 F10·사람이 한 조작 기록·메뉴로 한 glTF 내보내기는 볼 수 없다(사용자가 눈으로 확인).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
TEST_PORT = 8797  # 실제로 설치해 쓰는 도우미(8766)와 겹치지 않게

if "bpy" not in sys.modules:  # 1) 보통 파이썬: 임시 폴더에 설치하고 Blender를 화면 없이 띄운다
    import urllib.error
    import urllib.request

    sys.path.insert(0, str(PROJECT))
    from blender_tutor.install_addon import ADDON_NAME, install
    from blender_tutor.receiver import TOKEN_HEADER

    blender = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
    with tempfile.TemporaryDirectory() as scripts:
        target = install(Path(scripts) / "addons", Path(sys.executable))
        config = json.loads((target / "config.json").read_text(encoding="utf-8"))
        config["command"] += ["--port", str(TEST_PORT)]
        config["port"] = TEST_PORT
        (target / "config.json").write_text(json.dumps(config), encoding="utf-8")
        env = {**os.environ, "BLENDER_USER_SCRIPTS": scripts, "TUTOR_PROJECT": str(PROJECT), "TUTOR_ADDON": ADDON_NAME}
        result = subprocess.run([blender, "-b", "--factory-startup", "--python", __file__], env=env)

        # Blender가 닫혔으니 도우미 프로그램도 몇 초 안에 끝나야 한다
        def answering() -> bool:
            request = urllib.request.Request(f"http://127.0.0.1:{TEST_PORT}/ping", headers={TOKEN_HEADER: config["token"]})
            try:
                urllib.request.urlopen(request, timeout=1).read()
                return True
            except OSError:
                return False

        deadline = time.monotonic() + 10
        while answering() and time.monotonic() < deadline:
            time.sleep(0.2)
        closed = not answering()
        print(f"[{'통과' if closed else '실패'}] Blender가 닫히자 도우미 프로그램도 끝남")
    ok = result.returncode == 0 and closed
    print("전체:", "통과" if ok else "실패")
    sys.exit(0 if ok else 1)

# 2) Blender 안
import addon_utils  # noqa: E402
import bpy  # noqa: E402

sys.path.insert(0, os.environ["TUTOR_PROJECT"])
from blender_tutor.work_state import WorkState  # noqa: E402

ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"[{'통과' if cond else '실패'}] {name} {detail}")


addon_utils.enable(os.environ["TUTOR_ADDON"], default_set=True)
addon = sys.modules.get(os.environ["TUTOR_ADDON"])
check("애드온 켜기", addon is not None and hasattr(bpy.ops.tutor, "summon"))

check(
    "조작 이름 바꾸기",
    addon.operator_name("OBJECT_OT_join") == "object.join" and addon.operator_name("MESH_OT_merge") == "mesh.merge"
    and addon.operator_name("EXPORT_SCENE_OT_gltf") == "export_scene.gltf",
)

context = bpy.context
cube = bpy.data.objects["Cube"]
cube.select_set(True)
context.view_layer.objects.active = cube
state = addon.read_state(context, [])
check("물체 모드 12칸이 WorkState 모양과 맞음", WorkState.from_json(state).mode == "OBJECT", json.dumps(state, ensure_ascii=False))
check("활성 물체", state["active_object"]["name"] == "Cube" and state["active_object"]["type"] == "MESH")
check("장면 물체 수·버전", state["scene_object_count"] == 3 and state["blender_version"].startswith("5.2"), state["blender_version"])

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
state = addon.read_state(bpy.context, [])
check("편집 모드 점 선택 개수", state["mode"] == "EDIT_MESH" and state["edit_selected"] == {"VERT": 8}, state["edit_selected"])
bpy.context.tool_settings.mesh_select_mode = (False, False, True)
check("편집 모드 면 선택 개수", addon.read_state(bpy.context, [])["edit_selected"] == {"FACE": 6})
bpy.context.tool_settings.mesh_select_mode = (True, False, False)
bpy.ops.object.mode_set(mode="OBJECT")


def read_ms(times=200) -> float:
    started = time.perf_counter()
    for _ in range(times):
        addon.read_state(bpy.context, [])
    return (time.perf_counter() - started) * 1000 / times


check("읽기 시간(물체 모드, ms)", True, round(read_ms(), 3))
for size in (10_000, 100_000, 1_000_000):  # 편집 모드 개수 읽기 시간: 메시 크기에 따라
    side = int(size**0.5)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=side - 1, y_subdivisions=side - 1)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    check(f"읽기 시간(편집 모드, 점 약 {size:,}개, ms)", True, round(read_ms(5), 2))
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.data.objects.remove(bpy.context.active_object)
context.view_layer.objects.active = cube


# 바뀐 때만 보내기: 보내는 쪽을 가짜로 바꿔 끼운다
class FakeSender:
    def __init__(self):
        self.sent = []

    def send(self, payload, launch=False):
        self.sent.append(payload)


real_sender, addon._sender = addon._sender, FakeSender()
addon.tick()
addon.tick()
check("바뀌지 않으면 다시 보내지 않음", len(addon._sender.sent) == 1, len(addon._sender.sent))
bpy.ops.object.mode_set(mode="EDIT")
addon.tick()
check("바뀌면 보냄", len(addon._sender.sent) == 2 and addon._sender.sent[-1]["state"]["mode"] == "EDIT_MESH")
bpy.ops.object.mode_set(mode="OBJECT")
addon.tick()
sent = addon._sender.sent[-1]
check("창 번호·프로세스 번호를 함께 보냄", sent["pid"] == os.getpid() and isinstance(sent["window"], int), (sent["window"], sent["pid"]))

with tempfile.TemporaryDirectory() as folder:
    blend = str(Path(folder) / "sword.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    addon.tick()
    sent = addon._sender.sent[-1]
    check("저장 사건", sent["event"] == {"kind": "saved", "path": blend} and sent["state"]["file_path"] == blend, sent["event"])
    bpy.ops.wm.open_mainfile(filepath=blend)
    addon.tick()
    check("열기 사건", addon._sender.sent[-1]["event"] == {"kind": "opened", "path": blend})

    gltf = str(Path(folder) / "sword.glb")
    bpy.ops.export_scene.gltf(filepath=gltf)
    check("glTF 내보내기를 방금 조작에 넣음", addon.read_state(bpy.context, addon._recent.names)["recent_operators"][-1:] == ["export_scene.gltf"], addon._recent.names)
    bpy.ops.wm.read_homefile(use_empty=True)  # 임시 폴더를 지울 수 있게 파일을 닫는다

prefs = bpy.context.preferences
prefs.use_preferences_save = False
prefs.view.language = "ko_KR"
state = addon.read_state(bpy.context, [])
check("화면 언어", state["language"] == "ko_KR" and isinstance(state["translate_interface"], bool), (state["language"], state["translate_interface"]))
prefs.view.language = "en_US"

# 도우미 프로그램 켜기: 실제로 켜고 보낸다. 두 번째는 켜진 것을 쓴다
addon._sender = real_sender
started = time.perf_counter()
check("도우미 프로그램 켜기", real_sender.launch(), f"{time.perf_counter() - started:.2f}초")
started = time.perf_counter()
check("이미 켜져 있으면 그것을 씀", real_sender.launch() and time.perf_counter() - started < 1, f"{time.perf_counter() - started:.2f}초")
check("보내기", real_sender._post(addon._payload(addon.read_state(bpy.context, []), summon=True)))
# 비밀 글자가 다른 애드온(예: 다시 설치하기 전 것)은 켜진 도우미를 '다른 도우미'로 보고, 새로 켜지 않고 바로 알린다
stranger = addon.Sender({**json.loads(addon.CONFIG.read_text(encoding="utf-8")), "token": "other-token"})
started = time.perf_counter()
check("다른 도우미가 자리를 쓰면 켜지 않고 알림", stranger.answer() == "other" and not stranger.launch() and addon._notice,
      f"{time.perf_counter() - started:.2f}초")
stranger.stop()

addon_utils.disable(os.environ["TUTOR_ADDON"])
print("Blender 안:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
