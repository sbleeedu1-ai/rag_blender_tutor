"""받는 쪽: 도우미 프로그램이 애드온의 작업 상태를 받는 곳(명세 "전체 구성"·"도우미 창", 티켓 08·25).

애드온 → 도우미 프로그램은 내 PC 안 HTTP(127.0.0.1)다. 두 프로그램이 따로 돌아 함수를 바로 부를 수 없어서다.
설치 때 만든 비밀 글자(X-Tutor-Token)가 없는 요청은 버린다. 브라우저의 웹페이지가 127.0.0.1로 보내는 요청을 막으려는 것이다.
창 번호마다 최신 작업 상태 하나를 들고, 닫힌 Blender의 상태는 버리고, 마지막 Blender가 닫히면 끝난다.
도우미 프로그램 입구(blender_tutor.helper)가 이것을 띄운다.
"""

import ctypes
import json
import logging
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

from blender_tutor.work_state import WorkState

PORT = 8766  # 시제품(티켓 01)과 같은 번호. 설치 명령이 애드온 설정 파일에 함께 적는다
TOKEN_ENV = "BLENDER_TUTOR_TOKEN"  # 애드온이 받는 쪽을 켤 때 비밀 글자를 넘기는 환경 변수
TOKEN_HEADER = "X-Tutor-Token"
FILE_EVENTS = ("opened", "saved")  # Blender load_post·save_post 알림(다른 이름으로 저장도 saved, 티켓 18)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileEvent:
    """파일 열기·저장 사건. 경로만으로는 '열기'와 '다른 이름으로 저장'을 가를 수 없어 사건으로 받는다(티켓 18)."""

    kind: str  # opened 또는 saved
    path: str  # 연 파일·저장한 파일 경로. 새 파일을 열면 ""


@dataclass(frozen=True)
class Message:
    """애드온이 한 번 보낸 것."""

    window: int  # 보낸 Blender의 창 번호(Esc로 돌아갈 곳)
    pid: int  # 보낸 Blender의 프로세스 번호(닫혔는지 볼 때 씀)
    state: WorkState
    summon: bool = False  # F10: 도우미 창을 앞으로 부른다
    event: FileEvent | None = None
    pressed: float | None = None  # F10을 누른 시각(애드온의 time.time(), 같은 PC 시계). 시간 기록이 여기서부터 잰다(티켓 28)

    @classmethod
    def from_json(cls, data: object) -> "Message":
        """애드온이 보낸 JSON을 읽는다. 모양이 틀리면 ValueError."""
        if not isinstance(data, dict) or set(data) != {"window", "pid", "state", "summon", "event", "pressed"}:
            raise ValueError("칸이 window·pid·state·summon·event·pressed가 아님")
        window, pid, summon, event, pressed = data["window"], data["pid"], data["summon"], data["event"], data["pressed"]
        if not all(isinstance(n, int) and not isinstance(n, bool) for n in (window, pid)) or not isinstance(summon, bool):
            raise ValueError("창 번호·프로세스 번호는 정수, summon은 참/거짓")
        if pressed is not None and (isinstance(pressed, bool) or not isinstance(pressed, (int, float))):
            raise ValueError("누른 시각은 숫자")
        if event is not None:
            if not (isinstance(event, dict) and event.get("kind") in FILE_EVENTS and isinstance(event.get("path"), str)):
                raise ValueError(f"사건은 {FILE_EVENTS} 가운데 하나와 경로")
            event = FileEvent(event["kind"], event["path"])
        return cls(window, pid, WorkState.from_json(data["state"]), summon, event, None if pressed is None else float(pressed))


def process_started(pid: int) -> int | None:
    """그 프로세스가 켜진 시각(Windows 시각 값). 꺼져 있으면 None(Windows 전용. 맥을 붙일 때는 이 함수만 바꾼다).

    Windows는 꺼진 프로세스의 번호를 다른 프로그램에 다시 주므로, 번호만 보면 닫힌 Blender를 켜져 있다고 볼 수 있다.
    켜진 시각까지 같아야 같은 프로그램으로 본다.
    관리자로 켠 Blender처럼 열어 볼 수 없는 프로세스는 시각을 모르므로 0을 돌려준다(켜져 있다고 봄).
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return 0 if ctypes.get_last_error() == 5 else None  # 5: 접근 거부(있기는 함)
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        created, exited, kernel, user = (ctypes.c_ulonglong() for _ in range(4))
        if not kernel32.GetProcessTimes(ctypes.c_void_p(handle), *map(ctypes.byref, (created, exited, kernel, user))):
            return None
        return created.value
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


class Receiver:
    """애드온이 보낸 작업 상태를 창 번호마다 하나씩 든다. with 블록 안에서 받는다.

    listener는 받은 Message마다 불린다(받는 쪽 스레드에서). 도우미 창·진행 관리가 여기에 붙는다(티켓 26·27).
    """

    def __init__(
        self,
        token: str,
        listener: Callable[[Message], None] = lambda message: None,
        process_started: Callable[[int], object] = process_started,
        port: int = PORT,
    ):
        """port=0이면 비어 있는 번호를 아무거나 쓴다(테스트용). 번호를 이미 누가 쓰면 OSError."""
        self._token = token
        self._listener = listener
        self._process_started = process_started
        self._lock = threading.Lock()
        self._latest: dict[int, tuple[int, WorkState]] = {}  # 창 번호 → (프로세스 번호, 최신 작업 상태)
        self._started: dict[int, object] = {}  # 프로세스 번호 → 처음 받았을 때 그 프로세스가 켜진 시각
        self._heard = False  # Blender가 한 번이라도 보냈나
        self._server = HTTPServer(("127.0.0.1", port), self._handler())
        # 끌 때 기다리는 시간(기본 0.5초)을 줄인다
        self._thread = threading.Thread(target=self._server.serve_forever, args=(0.05,), daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def __enter__(self) -> "Receiver":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()

    def latest(self, window: int) -> WorkState | None:
        """그 창 번호의 최신 작업 상태. 받은 적이 없거나 닫힌 Blender면 None."""
        with self._lock:
            entry = self._latest.get(window)
        return entry[1] if entry else None

    def blenders(self) -> dict[int, int]:
        """켜진 Blender들의 창 번호 → 프로세스 번호(처음 받은 차례)."""
        with self._lock:
            return {window: pid for window, (pid, _) in self._latest.items()}

    def forget_closed(self) -> None:
        """닫힌 Blender의 상태를 버린다. 켜진 시각이 처음과 다르면(번호가 다른 프로그램에 다시 쓰임) 닫힌 것으로 본다."""
        with self._lock:
            entries = list(self._latest.items())
            started = dict(self._started)
        closed_pids = {pid for _, (pid, _) in entries if started.get(pid) is None or self._process_started(pid) != started[pid]}
        with self._lock:
            for window, (pid, _) in entries:
                if pid in closed_pids:
                    self._latest.pop(window, None)
            for pid in closed_pids:
                self._started.pop(pid, None)

    def run_until_no_blender(self, check_every: float = 1.0, grace: float = 30.0) -> None:
        """check_every초마다 닫힌 Blender를 버리고, 켜진 Blender가 하나도 없으면 돌아온다.

        켜진 직후에는 Blender가 첫 상태를 보낼 때까지 grace초 기다린다(애드온이 켠 뒤 0.5초 안에 보낸다).
        """
        started = time.monotonic()
        while True:
            time.sleep(check_every)
            self.forget_closed()
            with self._lock:
                empty, heard = not self._latest, self._heard
            if empty and (heard or time.monotonic() - started >= grace):
                return

    def _receive(self, message: Message) -> None:
        started = None if message.pid in self._started else self._process_started(message.pid)
        with self._lock:
            if started is not None:
                self._started.setdefault(message.pid, started)
            self._latest[message.window] = (message.pid, message.state)
            self._heard = True
        self._listener(message)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            timeout = 5  # 보내다 멈춘 요청이 받는 쪽을 붙잡지 않게

            def do_GET(self):
                if self._allowed() and self.path == "/ping":  # 애드온이 '이미 켜진 도우미'인지 물을 때
                    self._reply(200, {"app": "blender_tutor"})
                elif self._allowed():
                    self._reply(404, {"error": "없는 주소"})

            def do_POST(self):
                if not self._allowed():
                    return
                if self.path != "/state":
                    return self._reply(404, {"error": "없는 주소"})
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length < 0:  # 음수면 연결이 끊길 때까지 읽으려다 다른 Blender의 상태까지 붙잡는다
                        raise ValueError("내용 길이가 음수")
                    body = self.rfile.read(length)
                    message = Message.from_json(json.loads(body.decode("utf-8")))
                except (ValueError, UnicodeDecodeError) as error:  # json 오류도 ValueError
                    log.warning("모양이 틀린 작업 상태: %s", error)
                    return self._reply(400, {"error": str(error)})
                receiver._receive(message)
                self._reply(200, {})

            def _allowed(self) -> bool:
                # 맞든 틀리든 같은 시간이 걸리게 비교한다(앞 글자부터 맞혀 가는 시간 재기 공격 막기)
                if secrets.compare_digest(self.headers.get(TOKEN_HEADER, "").encode(), receiver._token.encode()):
                    return True
                self._reply(403, {"error": "비밀 글자가 틀림"})
                return False

            def _reply(self, status: int, body: dict) -> None:
                data = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # 0.5초마다 오는 요청을 화면에 찍지 않는다
                pass

        return Handler
