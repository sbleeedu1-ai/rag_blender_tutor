# 시제품(버릴 코드): "Blender 위에 떠 있는 창" 방식용 애드온.
# F10을 누르면 작업 상태를 읽어 떠 있는 창(overlay_window.py)에 보내고, 그 창이 앞으로 나와 입력을 받게 한다.
# 실행: python prototype/addon_roundtrip/run_overlay.py
import ctypes
import json
import threading
import time
import urllib.request

import bpy
from bpy.app import translations

SUMMON_URL = "http://127.0.0.1:8766/summon"
SHORTCUT = "F10"
_keymaps = []


def read_state(context):
    view = context.preferences.view
    active = context.active_object
    return {
        "mode": context.mode,
        "active_object": active.name if active else None,
        "selected_objects": [o.name for o in context.selected_objects],
        "locale": translations.locale,
        "translate_interface": view.use_translate_interface,
    }


def _post(payload):
    try:
        req = urllib.request.Request(
            SUMMON_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        urllib.request.urlopen(req, timeout=5).read()
    except Exception as e:
        print("[시제품] 떠 있는 창에 못 보냄:", e)


class TUTOR_OT_summon(bpy.types.Operator):
    """떠 있는 도우미 창 부르기(시제품)"""
    bl_idname = "tutor_proto.summon"
    bl_label = "도우미 창 부르기"

    def execute(self, context):
        t_key = time.time()  # 다른 프로그램과 비교해야 해서 벽시계 시간
        user32 = ctypes.windll.user32
        blender_hwnd = user32.GetForegroundWindow()  # Esc로 돌아올 때 쓸 Blender 창
        # Windows는 뒤에 있는 프로그램이 스스로 앞으로 나오는 것을 막는다.
        # 지금 앞에 있는 Blender가 "다른 프로그램이 앞으로 나와도 된다"고 허락해 준다(ASFW_ANY = -1).
        allowed = bool(user32.AllowSetForegroundWindow(-1))
        payload = {
            "t_key": t_key,
            "blender_hwnd": blender_hwnd,
            "allow_foreground": allowed,
            "state": read_state(context),
        }
        threading.Thread(target=_post, args=(payload,), daemon=True).start()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(TUTOR_OT_summon)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Window", space_type="EMPTY")
        _keymaps.append((km, km.keymap_items.new(TUTOR_OT_summon.bl_idname, SHORTCUT, "PRESS")))


def unregister():
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    bpy.utils.unregister_class(TUTOR_OT_summon)


if __name__ == "__main__":
    register()
