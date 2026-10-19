# 시제품(버릴 코드): 애드온 왕복 최소 시제품. 정식 애드온이 아니다.
# 질문: 단축키·N 패널 채팅·작업 상태 읽기·가짜 서버 왕복이 Blender 5.2에서 되는가,
#       요청 중 화면이 멈추지 않는가, 애드온 쪽 부담은 몇 ms인가.
# 실행: python prototype/addon_roundtrip/run.py  (README.md 참고)
import json
import queue
import textwrap
import threading
import time
import urllib.request

import bpy
from bpy.app import translations

SERVER_URL = "http://127.0.0.1:8765/ask"
SHORTCUT = "F10"  # 기본 키맵에서 비어 있는 키(Ctrl+Alt+T도 비어 있음)

_results = queue.Queue()  # 백그라운드 스레드 → 메인 스레드
_chat = []                # [(누가, 글)]
_last = {}                # 마지막 질문의 시간 기록
_live = {"heartbeat": 0, "waiting": False, "max_gap_ms": 0.0, "last_tick": None}
_keymaps = []

# 화면 언어 확인용: (영어, 문맥). 조사(화면 한국어 번역)의 표에서 몇 개만 골랐다.
_UI_SAMPLES = [
    ("Add", "Operator"),
    ("At Center", "Mesh"),       # 병합 메뉴. 한국어 화면에서도 영어여야 함
    ("At Center", "Operator"),   # 문맥이 틀리면 "센터에서"
    ("Scale", "*"),
    ("Array", "*"),
    ("Edit Mode", "*"),
    ("Edit Mode", "Operator"),
]


def read_state(context):
    """작업 상태: 모드, 선택 물체, 화면 언어."""
    view = context.preferences.view
    active = context.active_object
    return {
        "mode": context.mode,
        "active_object": active.name if active else None,
        "active_type": active.type if active else None,
        "selected_objects": [o.name for o in context.selected_objects],
        "locale": translations.locale,
        "language_setting": view.language,
        "translate_interface": view.use_translate_interface,
        "blender_version": bpy.app.version_string,
    }


def _post(payload, t_send):
    """백그라운드 스레드에서 서버에 보낸다. Blender 데이터(bpy)는 건드리지 않는다."""
    try:
        req = urllib.request.Request(
            SERVER_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        _results.put(("ok", body, time.perf_counter()))
    except Exception as e:  # 시제품이라 오류는 화면에 글로만 보여 준다
        _results.put(("error", str(e), time.perf_counter()))


def _redraw_sidebars():
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _tick():
    """0.05초마다 도는 타이머. 답이 왔는지 보고, 화면이 멈췄는지 재는 심장 박동도 센다."""
    now = time.perf_counter()
    if _live["last_tick"] is not None and _live["waiting"]:
        gap = (now - _live["last_tick"]) * 1000
        _live["max_gap_ms"] = max(_live["max_gap_ms"], gap)
    _live["last_tick"] = now
    _live["heartbeat"] += 1

    try:
        kind, body, t_recv = _results.get_nowait()
    except queue.Empty:
        if _live["waiting"]:
            _redraw_sidebars()
        return 0.05

    if kind == "ok":
        sources = ", ".join(f"{s['title']} ({s['url']})" for s in body.get("sources", []))
        _chat.append(("도우미", body.get("answer", "") + (f"\n근거: {sources}" if sources else "")))
        _last["server_ms"] = body.get("server_ms")
    else:
        _chat.append(("오류", body))
        _last["server_ms"] = None
    _last["t_recv"] = t_recv
    _last["t_display"] = time.perf_counter()  # 다음 다시 그리기 직전. 실제 표시는 그 직후
    _live["waiting"] = False
    _redraw_sidebars()
    _print_timing()
    return 0.05


def _ms(a, b):
    return None if a is None or b is None else round((b - a) * 1000, 1)


def _timing_rows():
    L = _last
    if "t_key" not in L:
        return []
    rows = [
        ("단축키 → 질문 보냄(입력 시간 포함)", _ms(L.get("t_key"), L.get("t_submit"))),
        ("작업 상태 읽기", _ms(L.get("t_submit"), L.get("t_state"))),
        ("보냄 → 답 받음(왕복)", _ms(L.get("t_send"), L.get("t_recv"))),
        ("  그중 서버 처리(서버가 알려 준 값)", L.get("server_ms")),
        ("답 받음 → 채팅에 넣음", _ms(L.get("t_recv"), L.get("t_display"))),
    ]
    rt, srv = _ms(L.get("t_send"), L.get("t_recv")), L.get("server_ms")
    if rt is not None and srv is not None:
        overhead = (rt - srv) + (_ms(L["t_submit"], L["t_state"]) or 0) + (_ms(L["t_recv"], L["t_display"]) or 0)
        rows.append(("애드온 쪽 부담(서버 처리 제외)", round(overhead, 1)))
    rows.append(("기다리는 동안 타이머 최대 간격(멈춤 확인)", round(_live["max_gap_ms"], 1)))
    return rows


def _print_timing():
    print("[시제품] 시간(ms):")
    for name, v in _timing_rows():
        print(f"  {name}: {v}")


class TUTOR_OT_ask(bpy.types.Operator):
    """도우미에게 질문하기(시제품)"""
    bl_idname = "tutor_proto.ask"
    bl_label = "도우미에게 질문"

    question: bpy.props.StringProperty(name="질문", default="")

    def invoke(self, context, event):
        _last.clear()
        _last["t_key"] = time.perf_counter()
        self.question = ""
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        layout.activate_init = True  # 창이 뜨면 바로 입력할 수 있게
        layout.prop(self, "question", text="")

    def execute(self, context):
        if _live["waiting"]:
            self.report({"WARNING"}, "앞 질문의 답을 기다리는 중")
            return {"CANCELLED"}
        _last["t_submit"] = time.perf_counter()
        state = read_state(context)
        _last["t_state"] = time.perf_counter()
        _last["state"] = state
        _chat.append(("나", self.question or "(빈 질문)"))
        _live["waiting"] = True
        _live["max_gap_ms"] = 0.0
        _last["t_send"] = time.perf_counter()
        payload = {"question": self.question, "state": state}
        threading.Thread(target=_post, args=(payload, _last["t_send"]), daemon=True).start()
        _redraw_sidebars()
        return {"FINISHED"}


class TUTOR_OT_clear(bpy.types.Operator):
    """채팅 지우기(시제품)"""
    bl_idname = "tutor_proto.clear"
    bl_label = "채팅 지우기"

    def execute(self, context):
        _chat.clear()
        _last.clear()
        return {"FINISHED"}


class TUTOR_PT_chat(bpy.types.Panel):
    bl_label = "도우미 (시제품)"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tutor"

    def draw(self, context):
        layout = self.layout
        width_chars = max(20, int(context.region.width / (8 * context.preferences.view.ui_scale)))

        row = layout.row()
        row.operator(TUTOR_OT_ask.bl_idname, text=f"질문하기 ({SHORTCUT})", icon="QUESTION")
        row.operator(TUTOR_OT_clear.bl_idname, text="", icon="TRASH")
        status = "답 기다리는 중..." if _live["waiting"] else "대기"
        layout.label(text=f"상태: {status} · 심장 박동 {_live['heartbeat']}")

        box = layout.box()
        box.label(text="채팅", icon="TEXT")
        if not _chat:
            box.label(text=f"{SHORTCUT}를 눌러 질문해 보세요")
        for who, text in _chat[-8:]:
            col = box.column(align=True)
            for i, para in enumerate(text.split("\n")):
                for j, line in enumerate(textwrap.wrap(para, width_chars) or [""]):
                    col.label(text=(f"{who}: " if i == 0 and j == 0 else "    ") + line)

        box = layout.box()
        box.label(text="지금 작업 상태(보낼 값)", icon="INFO")
        for k, v in read_state(context).items():
            box.label(text=f"{k}: {v}")

        box = layout.box()
        box.label(text="메뉴 이름 바꾸기 확인(pgettext_iface)", icon="WORLD")
        for msgid, ctxt in _UI_SAMPLES:
            box.label(text=f"{msgid} [{ctxt}] → {translations.pgettext_iface(msgid, ctxt)}")

        rows = _timing_rows()
        if rows:
            box = layout.box()
            box.label(text="마지막 질문 시간(ms)", icon="TIME")
            for name, v in rows:
                box.label(text=f"{name}: {v}")


_classes = (TUTOR_OT_ask, TUTOR_OT_clear, TUTOR_PT_chat)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:  # 화면 없이(background) 실행하면 없을 수 있다
        km = kc.keymaps.new(name="Window", space_type="EMPTY")
        _keymaps.append((km, km.keymap_items.new(TUTOR_OT_ask.bl_idname, SHORTCUT, "PRESS")))
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
