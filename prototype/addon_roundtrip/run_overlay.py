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
root.attributes("-topmost", True)
root.attributes("-alpha", 0.93)
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
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
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
root.mainloop()
server.shutdown()
