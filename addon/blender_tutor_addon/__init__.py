"""Blender 첫걸음 도우미 애드온(명세 "애드온", ADR-0001, 티켓 25).

작업 상태 12칸을 읽어 도우미 프로그램에 내 PC 안 HTTP로 보낸다. 검색·답 생성은 하지 않는다.
- 0.5초마다 읽어 바뀌었을 때만 보내고, F10이면 바뀌지 않아도 보내며 도우미 창을 부른다.
- 파일 열기·저장은 사건(opened·saved)으로 함께 보낸다(티켓 18).
- Blender를 켤 때와 F10 때 도우미 프로그램이 없으면 켠다. 끄는 일은 도우미 프로그램이 한다(켜진 Blender가 없으면 끝남).

이 애드온은 Blender 안 파이썬에서 돌아 blender_tutor 패키지를 가져다 쓰지 못한다. 작업 상태 칸은
blender_tutor/work_state.py와 같게 맞추고, 바꾸면 둘 다 고친다(addon/selftest.py가 맞는지 본다).
설치: 프로젝트 폴더에서 `.venv\\Scripts\\python -m blender_tutor.install_addon`(옆에 config.json을 적어 줌).
Windows에만 있는 부분: 이 파일의 _own_window(창 번호)·TUTOR_OT_summon(창 앞으로 부르기 허락)·Sender.launch(창 없이 켜기),
blender_tutor/receiver.py의 process_alive, blender_tutor/install_addon.py의 설치 폴더·pythonw. 맥을 붙일 때는 이곳들을 바꾼다.
"""

import ctypes
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from ctypes import wintypes
from pathlib import Path

import bpy
from bpy.app.handlers import persistent

bl_info = {
    "name": "Blender 첫걸음 도우미",
    "author": "rag_blender_tutor",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "F10",
    "description": "작업 상태를 읽어 도우미 창 프로그램에 보낸다",
    "category": "Interface",
}

CONFIG = Path(__file__).resolve().parent / "config.json"  # 설치 명령이 적는다
INTERVAL = 0.5  # 작업 상태를 읽는 간격(초)
RECENT = 3  # 방금 실행한 조작을 몇 개 보내나
SHORTCUT = "F10"
TOKEN_ENV = "BLENDER_TUTOR_TOKEN"  # blender_tutor/receiver.py의 TOKEN_ENV와 같아야 함
TOKEN_HEADER = "X-Tutor-Token"  # blender_tutor/receiver.py의 TOKEN_HEADER와 같아야 함(어긋나면 자체 시험의 '보내기'가 실패)
LOG = Path(tempfile.gettempdir()) / "blender_tutor_receiver.log"  # 애드온이 켠 도우미 프로그램의 기록


def operator_name(bl_idname: str) -> str:
    """Blender 조작 기록의 이름을 연습 과정 파일 꼴로 바꾼다: OBJECT_OT_join → object.join."""
    prefix, separator, rest = bl_idname.partition("_OT_")
    return f"{prefix.lower()}.{rest}" if separator else bl_idname


class RecentOperators:
    """방금 실행한 조작(오래된 차례, 최대 RECENT개).

    Blender 조작 기록(window_manager.operators)에는 사람이 키보드·메뉴로 실행한 조작만 남는다(티켓 17).
    기록이 바뀔 때 새로 생긴 것만 더하고, 기록에 남지 않는 glTF 내보내기는 add로 직접 더한다.
    """

    def __init__(self):
        self.names: list[str] = []
        self._seen: set[int] = set()  # 지난번에 본 조작 기록(메모리 주소)

    def update(self, operators, record: bool = True) -> None:
        current = [(operator.as_pointer(), operator.bl_idname) for operator in operators]
        if record:
            for pointer, idname in current:
                if pointer not in self._seen:
                    self.add(operator_name(idname))
        self._seen = {pointer for pointer, _ in current}

    def add(self, name: str) -> None:
        self.names = (self.names + [name])[-RECENT:]


def _edit_selected(context) -> dict[str, int]:
    """메시 편집 모드의 선택 방식(VERT·EDGE·FACE) → 고른 개수. 켜진 선택 방식만 넣는다.

    Blender가 편집 모드에서 세어 두는 개수(total_*_sel)를 읽어, 메시가 커도 시간이 들지 않는다
    (점 100만 개에서 하나하나 세면 약 0.5초, 이 숫자를 읽으면 0.00001초 미만, 2026-10-22 잼).
    여러 물체를 함께 편집할 때는 활성 물체만 센다.
    """
    obj = context.edit_object
    if context.mode != "EDIT_MESH" or obj is None or obj.type != "MESH":
        return {}
    mesh = obj.data
    counts = (mesh.total_vert_sel, mesh.total_edge_sel, mesh.total_face_sel)
    return {name: count for name, on, count in zip(("VERT", "EDGE", "FACE"), context.tool_settings.mesh_select_mode, counts) if on}


def read_state(context, recent_operators) -> dict:
    """작업 상태 12칸(blender_tutor/work_state.py의 WorkState와 같은 칸)."""
    active = context.active_object
    return {
        "mode": context.mode,
        "active_object": None if active is None else {
            "name": active.name,
            "type": active.type,
            "modifiers": [modifier.type for modifier in active.modifiers],
            "scale": list(active.scale),
            "dimensions": list(active.dimensions),
            "material_slot_count": len(active.material_slots),
        },
        "selected_objects": [obj.name for obj in context.selected_objects],
        "language": bpy.app.translations.locale,  # 설정이 '자동'이어도 실제로 쓰는 언어(예: ko_KR)
        "translate_interface": context.preferences.view.use_translate_interface,
        "file_path": bpy.data.filepath,
        "scene_object_count": len(context.scene.objects),
        "blender_version": bpy.app.version_string,
        "edit_selected": _edit_selected(context),
        "recent_operators": list(recent_operators),
    }


_window = 0  # 처음 찾은 주 창 번호. 그 창이 살아 있는 동안 계속 쓴다


def _own_window() -> int:
    """이 Blender의 주 창 번호(Windows). Blender 하나에 번호 하나가 되도록, 다른 창의 주인이 아닌 Blender 창을 고른다.

    처음 찾은 번호를 기억해 둔다. Window > New Main Window로 주 창이 둘이 되면 Windows가 알려 주는 차례가
    앞뒤로 바뀌는데, 매번 찾으면 번호가 흔들려 받는 쪽이 Blender 둘로 여기기 때문이다. 그 창이 닫히면 다시 찾는다.
    화면 없이 띄운 Blender(-b)에는 창이 없어 0이다.
    """
    global _window
    user32 = ctypes.windll.user32
    user32.IsWindow.argtypes = [wintypes.HWND]
    if _window and user32.IsWindow(_window):
        return _window
    user32.GetWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if pid.value == os.getpid() and name.value == "GHOST_WindowClass" and not user32.GetWindow(hwnd, 4):  # GW_OWNER
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    _window = int(found[0] or 0) if found else 0
    return _window


class Sender:
    """보낼 것을 줄 세워 한 스레드에서 차례로 보낸다(Blender 화면이 기다리지 않게, 보낸 차례가 뒤바뀌지 않게)."""

    def __init__(self, config: dict):
        self._config = config
        self._base = f"http://127.0.0.1:{config['port']}"
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def send(self, payload: dict, launch: bool = False) -> None:
        """payload를 보낸다. launch면 도우미 프로그램이 없을 때 켜고 보낸다(F10)."""
        self._queue.put((payload, launch))

    def start_helper(self) -> None:
        """도우미 프로그램이 없으면 켠다(Blender 시작). 같은 줄에 세워, 뒤에 보낼 것은 켜진 뒤에 나간다."""
        self._queue.put((None, True))

    def stop(self) -> None:
        self._queue.put(None)

    def answer(self) -> str:
        """자리 번호에 누가 있나: 'ours'(이 비밀 글자로 대답하는 도우미), 'other'(비밀 글자가 다른 도우미 등), 'none'."""
        try:
            with urllib.request.urlopen(self._request("/ping"), timeout=1) as response:
                return "ours" if json.loads(response.read()).get("app") == "blender_tutor" else "other"
        except urllib.error.HTTPError:
            return "other"
        except (OSError, ValueError):
            return "none"

    def launch(self, wait: float = 10.0) -> bool:
        """도우미 프로그램을 켜고 대답할 때까지 기다린다. 이미 켜져 있으면 그것을 쓴다.

        다른 도우미(예: 다시 설치하기 전 비밀 글자로 켜진 것)가 자리를 쓰고 있으면 켜도 자리를 못 열어 꺼지므로,
        켜지 않고 알린다. 그 도우미는 자기 Blender가 모두 닫히면 스스로 끝난다.
        """
        found = self.answer()
        if found == "other":
            _warn(f"{self._config['port']}번 자리를 다른 도우미가 쓰고 있어요. 열린 Blender를 모두 닫았다가 다시 켜 주세요.")
            return False
        if found == "ours":
            return True
        env = {**os.environ, TOKEN_ENV: self._config["token"], "PYTHONUTF8": "1"}  # 기록 파일을 UTF-8로
        with open(LOG, "a", encoding="utf-8") as log:
            subprocess.Popen(
                self._config["command"], cwd=self._config["cwd"], env=env, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
            )
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.answer() == "ours":
                return True
            time.sleep(0.1)
        _warn(f"도우미 프로그램이 켜지지 않았어요. 기록: {LOG}")
        return False

    def _request(self, path: str, payload: dict | None = None) -> urllib.request.Request:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return urllib.request.Request(
            self._base + path, data=data,
            headers={"Content-Type": "application/json; charset=utf-8", TOKEN_HEADER: self._config["token"]},
        )

    def _post(self, payload: dict) -> bool:
        try:
            urllib.request.urlopen(self._request("/state", payload), timeout=2).read()
            return True
        except urllib.error.HTTPError as error:  # 도우미가 받지 않음(모양이 틀림 등): 다시 보내도 같다
            print(f"[도우미] 도우미 프로그램이 받지 않았습니다({error.code}): {error.read().decode('utf-8', 'replace')}")
            return True
        except OSError:  # 도우미 프로그램이 꺼져 있음
            return False

    def _run(self) -> None:
        while (item := self._queue.get()) is not None:
            payload, launch = item
            if payload is None:
                self.launch()
            elif not self._post(payload) and launch and self.launch():
                self._post(payload)


def _warn(text: str) -> None:
    """콘솔과 Blender 아래 상태 줄에 알린다. 보내는 스레드에서 불리므로 상태 줄은 다음 tick이 띄운다."""
    global _notice
    print(f"[도우미] {text}")
    _notice = text


# 애드온이 켜져 있는 동안의 상태
_recent = RecentOperators()
_events: list[dict] = []  # 다음 읽기 때 보낼 파일 사건
_last: dict | None = None  # 마지막으로 보낸 작업 상태
_sender: Sender | None = None
_notice = ""  # 상태 줄에 띄울 알림(보내는 스레드가 적고 tick이 띄움)
_keymaps = []


def _payload(state: dict, summon: bool = False, event: dict | None = None) -> dict:
    return {"window": _own_window(), "pid": os.getpid(), "state": state, "summon": summon, "event": event}


def tick() -> float:
    """0.5초마다: 작업 상태를 읽어 바뀌었거나 파일 사건이 있으면 보낸다."""
    global _last, _notice
    try:
        context = bpy.context
        if _notice and context.workspace is not None:
            context.workspace.status_text_set(_notice)  # 다음 상태 줄 갱신까지 보인다
            _notice = ""
        _recent.update(context.window_manager.operators)
        state = read_state(context, _recent.names)
        if _sender is not None:
            for event in _events:
                _sender.send(_payload(state, event=event))
            if state != _last and not _events:
                _sender.send(_payload(state))
        _events.clear()
        _last = state
    except Exception:  # 한 번 실패해도 다음 읽기는 계속한다
        traceback.print_exc()
    return INTERVAL


def glTF2_post_export_callback(export_settings):
    """glTF 내보내기가 끝나면 Blender의 glTF 내보내기가 부른다(켜진 애드온 모듈에서 이 이름을 찾음, 티켓 17·HISTORY [27]).

    glTF 내보내기는 조작 기록에 남지 않아 여기서 '방금 조작'에 더한다. 공식 설명서에 없는 내부 장치라 버전마다 바뀔 수 있다.
    """
    _recent.add("export_scene.gltf")


@persistent
def _on_load(*_):
    _events.append({"kind": "opened", "path": bpy.data.filepath})


@persistent
def _on_save(*_):
    _events.append({"kind": "saved", "path": bpy.data.filepath})


class TUTOR_OT_summon(bpy.types.Operator):
    """작업 상태를 보내고 도우미 창을 부른다"""

    bl_idname = "tutor.summon"
    bl_label = "도우미 창 부르기"

    def execute(self, context):
        # Windows는 뒤에 있는 프로그램이 스스로 앞으로 나오는 것을 막는다. 지금 앞에 있는 Blender가 허락해 준다(ASFW_ANY = -1).
        ctypes.windll.user32.AllowSetForegroundWindow(-1)
        if _sender is None:
            self.report({"ERROR"}, "도우미 애드온 설치가 끝나지 않았습니다(config.json 없음). 설치 명령을 실행해 주세요.")
            return {"CANCELLED"}
        _recent.update(context.window_manager.operators)
        _sender.send(_payload(read_state(context, _recent.names), summon=True), launch=True)
        return {"FINISHED"}


def register():
    global _sender
    bpy.utils.register_class(TUTOR_OT_summon)
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig:
        keymap = keyconfig.keymaps.new(name="Window", space_type="EMPTY")
        _keymaps.append((keymap, keymap.keymap_items.new(TUTOR_OT_summon.bl_idname, SHORTCUT, "PRESS")))
    bpy.app.handlers.load_post.append(_on_load)
    bpy.app.handlers.save_post.append(_on_save)
    _recent.update(bpy.context.window_manager.operators, record=False)  # 켜기 전 조작은 '방금'이 아니다
    if not CONFIG.exists():
        print(f"[도우미] {CONFIG}가 없습니다. 프로젝트 폴더에서 설치 명령을 실행해 주세요.")
        return
    _sender = Sender(json.loads(CONFIG.read_text(encoding="utf-8")))
    if not bpy.app.background:  # 화면 없이 띄운 Blender(자료 준비·자체 시험)에서는 켜지 않는다
        _sender.start_helper()
        bpy.app.timers.register(tick, first_interval=INTERVAL, persistent=True)


def unregister():
    global _sender, _last
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    for handlers, handler in ((bpy.app.handlers.load_post, _on_load), (bpy.app.handlers.save_post, _on_save)):
        if handler in handlers:
            handlers.remove(handler)
    for keymap, item in _keymaps:
        keymap.keymap_items.remove(item)
    _keymaps.clear()
    bpy.utils.unregister_class(TUTOR_OT_summon)
    if _sender is not None:
        _sender.stop()
    _sender, _last = None, None
    _events.clear()  # 껐다 켤 때 지난 파일 사건·조작이 다시 나가지 않게
    _recent.names.clear()
