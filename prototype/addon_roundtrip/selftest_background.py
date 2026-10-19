# 시제품(버릴 코드): 화면 없이 확인할 수 있는 것만 확인한다.
#   python prototype/addon_roundtrip/selftest_background.py
# 확인: 애드온 등록, 작업 상태 읽기(물체·편집 모드), 한국어 화면에서 메뉴 이름, 가짜 서버 왕복, 애드온 쪽 ms.
# 화면 없이 돌리므로 단축키·N 패널 그리기·화면 멈춤은 여기서 볼 수 없다(README의 눈 확인 목록).
import os
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent

if "bpy" not in sys.modules:  # 1) 보통 Python: 가짜 서버(지연 0.3초)를 켜고 Blender를 화면 없이 띄운다
    sys.path.insert(0, str(HERE))
    from fake_server import serve
    server = serve(delay=0.3)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    blender = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
    r = subprocess.run([blender, "-b", "--factory-startup", "--python", __file__])
    server.shutdown()
    sys.exit(r.returncode)

# 2) Blender 안
import time
import bpy

sys.path.insert(0, str(HERE))
import tutor_proto_addon as addon

addon.register()
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"[{'통과' if cond else '실패'}] {name} {detail}")


ctx = bpy.context
check("애드온 등록", hasattr(bpy.ops.tutor_proto, "ask"))

cube = bpy.data.objects.get("Cube")
cube.select_set(True)
ctx.view_layer.objects.active = cube
s = addon.read_state(ctx)
check("물체 모드 상태", s["mode"] == "OBJECT" and s["active_object"] == "Cube", s)

bpy.ops.object.mode_set(mode="EDIT")
s = addon.read_state(bpy.context)
check("편집 모드 상태", s["mode"] == "EDIT_MESH", s["mode"])
bpy.ops.object.mode_set(mode="OBJECT")

# 상태 읽기 시간(1000번 평균)
t = time.perf_counter()
for _ in range(1000):
    addon.read_state(bpy.context)
check("상태 읽기 1회 평균(ms)", True, round((time.perf_counter() - t), 4))

# 한국어 화면
prefs = bpy.context.preferences
prefs.use_preferences_save = False
prefs.view.language = "ko_KR"
s = addon.read_state(bpy.context)
check("화면 언어 읽기", s["locale"] == "ko_KR", s["locale"])
from bpy.app.translations import pgettext_iface
for msgid, ctxt in addon._UI_SAMPLES:
    print(f"    {msgid} [{ctxt}] → {pgettext_iface(msgid, ctxt)}")
check("At Center [Mesh]는 영어 그대로", pgettext_iface("At Center", "Mesh") == "At Center")
bpy.ops.mesh.primitive_cylinder_add()
check("한국어 화면에서 새 물체 이름", True, bpy.context.active_object.name)

# 왕복: 연산자 실행 부분과 같은 순서로 직접 부른다(대화창은 화면 없이 못 띄움)
addon._last.clear()
addon._last["t_key"] = addon._last["t_submit"] = time.perf_counter()
addon._last["state"] = addon.read_state(bpy.context)
addon._last["t_state"] = time.perf_counter()
addon._live["waiting"] = True
addon._last["t_send"] = time.perf_counter()
th = threading.Thread(target=addon._post, args=({"question": "베벨은 어떻게 해요?", "state": addon._last["state"]}, 0))
th.start()
while addon._live["waiting"]:  # 화면 없이는 타이머가 안 돌아서 손으로 돌린다
    time.sleep(0.05)
    try:
        addon._tick()
    except AttributeError:  # 화면 없으면 창 목록이 비어 다시 그리기에서 날 수 있음
        pass
check("가짜 서버 왕복", addon._chat and addon._chat[-1][0] == "도우미", addon._chat[-1:])
addon._print_timing()

addon.unregister()
print("전체:", "통과" if ok else "실패")
sys.exit(0 if ok else 1)
