# 시제품(버릴 코드): Blender 위에 떠 있는 채팅 창 + 가짜 답 + Blender 실행을 명령 하나로.
#   python prototype/addon_roundtrip/run_overlay.py            (답 지연 2초)
#   python prototype/addon_roundtrip/run_overlay.py --delay 5
# 확인할 것: Blender에서 F10 → 이 창이 앞으로 나와 클릭 없이 바로 한글을 칠 수 있는가.
# 창에서 Enter = 보내기, Esc = Blender로 돌아가기.
import argparse
import ctypes
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
user32 = ctypes.windll.user32
# 64비트 창 번호가 잘리지 않게 자료형을 정해 둔다
from ctypes import wintypes
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
user32.IsWindowVisible.argtypes = user32.IsIconic.argtypes = user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 글자가 흐리게 보이지 않게
except Exception:
    pass

p = argparse.ArgumentParser()
p.add_argument("--delay", type=float, default=2.0)
args = p.parse_args()

events = queue.Queue()  # 서버 스레드·답 스레드 → 창(메인 스레드)
S = {"summon": None, "t_focus": None, "t_send": None}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        body["t_arrive"] = time.time()
        events.put(("summon", body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 8766), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

# ---- 창 ----
root = tk.Tk()
root.title("도우미 (시제품)")
root.attributes("-alpha", 0.93)  # 맨 위 여부는 follow_blender가 정한다
sw = root.winfo_screenwidth()
root.geometry(f"460x560+{sw - 500}+120")
FONT = ("Malgun Gothic", 11)

chat = tk.Text(root, wrap="word", font=FONT, state="disabled", height=16)
chat.pack(fill="both", expand=True, padx=8, pady=(8, 4))
entry = tk.Entry(root, font=FONT)
entry.pack(fill="x", padx=8)
status = tk.Label(root, font=("Malgun Gothic", 9), justify="left", anchor="w", text="Blender에서 F10을 누르세요")
status.pack(fill="x", padx=8, pady=(4, 8))


def say(who, text):
    chat.configure(state="normal")
    chat.insert("end", f"{who}: {text}\n\n")
    chat.configure(state="disabled")
    chat.see("end")


def hwnd():
    return int(root.wm_frame(), 16)


def ms(a, b):
    return None if a is None or b is None else round((b - a) * 1000, 1)


def show_status(extra=""):
    s = S["summon"] or {}
    lines = [
        f"F10 → 창 신호 도착: {ms(s.get('t_key'), s.get('t_arrive'))} ms",
        f"F10 → 입력 가능(앞으로 나옴): {ms(s.get('t_key'), S['t_focus'])} ms",
        f"앞으로 나오기 성공: {S.get('fg_ok')} · Blender 허락: {s.get('allow_foreground')}",
        f"작업 상태: {json.dumps(s.get('state'), ensure_ascii=False)}",
    ]
    if extra:
        lines.append(extra)
    status.configure(text="\n".join(lines), wraplength=440)
    print("[떠 있는 창] " + " | ".join(lines), flush=True)


def summon(body):
    S["summon"] = body
    user32.ShowWindow(hwnd(), SW_SHOWNOACTIVATE)
    user32.SetWindowPos(hwnd(), HWND_TOPMOST, 0, 0, 0, 0, SWP_KEEP)
    user32.SetForegroundWindow(hwnd())
    entry.focus_force()

    def check():
        S["fg_ok"] = user32.GetForegroundWindow() == hwnd()
        S["t_focus"] = time.time() if S["fg_ok"] else None
        show_status()

    root.after(30, check)


def send(_event=None):
    q = entry.get().strip()
    if not q:
        return
    entry.delete(0, "end")
    say("나", q)
    S["t_send"] = time.time()
    state = (S["summon"] or {}).get("state", {})

    def work():  # 가짜 서버: 기다렸다가 고정된 답
        time.sleep(args.delay)
        events.put(("answer", (
            f"(가짜 답) 지금 {state.get('mode')} 모드, 선택 물체 "
            f"{', '.join(state.get('selected_objects') or []) or '없음'}, 화면 언어 {state.get('locale')}.\n"
            "근거: Blender 5.2 설명서: 3D 뷰포트 (https://docs.blender.org/manual/en/5.2/editors/3dview/index.html)"
        )))

    threading.Thread(target=work, daemon=True).start()


def back_to_blender(_event=None):
    h = (S["summon"] or {}).get("blender_hwnd")
    if h:
        user32.SetForegroundWindow(h)


entry.bind("<Return>", send)
root.bind("<Escape>", back_to_blender)

blender = subprocess.Popen([BLENDER, "--python", str(HERE / "tutor_overlay_addon.py")])


MY_PID = os.getpid()
_owner = {"mode": None}
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_KEEP = 0x0002 | 0x0001 | 0x0010  # 위치·크기 그대로, 앞으로 가져오지(활성화하지) 않음
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4


def pid_of(h):
    pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return pid.value


def blender_minimized():
    """이 시제품이 띄운 Blender의 보이는 창이 모두 최소화돼 있으면 True."""
    wins = []
    cb_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        if user32.IsWindowVisible(h) and pid_of(h) == blender.pid and user32.GetWindowTextLengthW(h):
            wins.append(h)
        return True

    user32.EnumWindows(cb_type(cb), 0)
    return bool(wins) and all(user32.IsIconic(h) for h in wins)


def follow_blender():
    """Blender나 이 창이 앞이면 맨 위, 다른 프로그램이 앞이면 그 뒤로, Blender를 최소화하면 숨김."""
    fg = user32.GetForegroundWindow()
    fg_pid = pid_of(fg)
    if fg_pid in (blender.pid, MY_PID):
        mode = "top"
    elif blender_minimized():
        mode = "hidden"
    else:
        mode = "behind"
    if mode != _owner["mode"]:
        h = hwnd()
        if mode == "hidden":
            user32.ShowWindow(h, SW_HIDE)
        else:
            if _owner["mode"] == "hidden":
                user32.ShowWindow(h, SW_SHOWNOACTIVATE)
            if mode == "top":
                user32.SetWindowPos(h, HWND_TOPMOST, 0, 0, 0, 0, SWP_KEEP)
            else:
                user32.SetWindowPos(h, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_KEEP)
                user32.SetWindowPos(h, fg, 0, 0, 0, 0, SWP_KEEP)  # 앞에 있는 프로그램 바로 뒤로
        print(f"[떠 있는 창] {_owner['mode']} → {mode} (앞 프로그램 번호 {fg_pid}, 우리 Blender {blender.pid})", flush=True)
        _owner["mode"] = mode
    root.after(100, follow_blender)


def poll():
    while True:
        try:
            kind, data = events.get_nowait()
        except queue.Empty:
            break
        if kind == "summon":
            summon(data)
        else:
            say("도우미", data)
            s = S["summon"] or {}
            show_status(
                f"입력 시간(입력 가능 → 보냄): {ms(S['t_focus'], S['t_send'])} ms · "
                f"보냄 → 답 표시: {ms(S['t_send'], time.time())} ms (가짜 지연 {args.delay}초)"
            )
    if blender.poll() is not None:  # Blender를 닫으면 창도 닫는다
        root.destroy()
        return
    root.after(30, poll)


root.after(30, poll)
root.after(100, follow_blender)
root.mainloop()
server.shutdown()
