"""Windows에 창 일을 시키는 얇은 줄(티켓 26). 판단은 넣지 않는다(판단은 window_rules, 화면 없이 시험함).

실제 창·초점을 움직여야 해서 기본 테스트 밖이고 강의실 PC 눈 확인으로 본다. Windows 전용(맥을 붙일 때는 이 파일을 바꾼다).
"""

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
# 64비트 창 번호가 잘리지 않게 자료형을 정해 둔다
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindow.argtypes = user32.IsWindowVisible.argtypes = user32.IsIconic.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]

HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SWP_KEEP = 0x0001 | 0x0002 | 0x0010  # 크기·자리 그대로, 활성화하지 않음(SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
GWL_EXSTYLE, WS_EX_TOPMOST = -20, 0x0008
# 작업 표시줄·트레이(숨김 영역 ^ 포함)의 창 종류 이름
TASKBAR_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland"}


def foreground() -> tuple[int, int, bool]:
    """앞 창의 (창 번호, 프로세스 번호, 작업 표시줄·트레이인가)."""
    hwnd = user32.GetForegroundWindow() or 0
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, name, 64)
    return hwnd, pid.value, name.value in TASKBAR_CLASSES


def any_shown(windows) -> bool:
    """창 가운데 최소화되지 않고 보이는 것이 하나라도 있나."""
    return any(user32.IsWindow(w) and user32.IsWindowVisible(w) and not user32.IsIconic(w) for w in windows)


def put_on_top(hwnd: int) -> None:
    """모든 창 위에(초점은 그대로)."""
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_KEEP)


def put_behind(hwnd: int, front: int) -> None:
    """맨 위를 풀고 front 창 바로 뒤로.

    front가 늘 맨 위인 창(Alt+Tab 고르기 화면 등)이면 맨 위만 푼다. 그런 창 바로 뒤에 놓으면 Windows가 도로 맨 위 창으로 만든다.
    """
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_KEEP)
    if not user32.GetWindowLongW(front, GWL_EXSTYLE) & WS_EX_TOPMOST:
        user32.SetWindowPos(hwnd, front, 0, 0, 0, 0, SWP_KEEP)


def bring_forward(hwnd: int) -> bool:
    """앞으로 가져와 초점을 준다. Windows가 막으면 False(F10은 애드온이 AllowSetForegroundWindow로 허락해 둔다)."""
    return bool(user32.SetForegroundWindow(hwnd))


class _AccentPolicy(ctypes.Structure):
    _fields_ = [("state", ctypes.c_int), ("flags", ctypes.c_int), ("color", ctypes.c_uint), ("animation", ctypes.c_int)]


class _CompositionData(ctypes.Structure):
    _fields_ = [("attribute", ctypes.c_int), ("data", ctypes.c_void_p), ("size", ctypes.c_size_t)]


def blur_behind(hwnd: int) -> bool:
    """창 뒤를 흐리게(문서 없는 SetWindowCompositionAttribute, 끌 수 있는 선택 기능).

    공식 Acrylic은 창이 비활성이면 단색이 되어 늘 비활성인 도우미 창에 맞지 않는다(조사 문서 "유리 창 시험").
    문서가 없어 Windows 업데이트로 깨질 수 있다. 실패하면 False(흐림 없이 판만 보인다).
    """
    accent = _AccentPolicy(4, 2, 0x01000000, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND, 색은 거의 투명(판은 Qt가 그림)
    data = _CompositionData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))  # WCA_ACCENT_POLICY
    function = getattr(user32, "SetWindowCompositionAttribute", None)
    return bool(function and function(wintypes.HWND(hwnd), ctypes.byref(data)))
