"""Mac에 창 일을 시키는 얇은 줄(winapi의 Mac 짝, HISTORY [312]). 판단은 넣지 않는다(판단은 window_rules, 화면 없이 시험함).

winapi와 같은 이름·같은 뜻의 함수를 둔다. 창 번호는 Mac 창 서버의 창 번호(CGWindowID)다. 애드온도 Blender 주 창의
같은 번호를 보내므로, Blender 창과 도우미 창을 한 가지 번호로 다룬다. 도우미 자신의 창은 Qt winId(NSView)를
native_window로 바꿔 쓴다.
실제 창·초점을 움직여야 해서 기본 테스트 밖이고 Mac 눈 확인으로 본다. pyobjc(Cocoa·Quartz)가 필요하다.
"""

import os

import AppKit
import objc
import Quartz

# 앞 프로그램이 Dock이면 작업 표시줄처럼 다룬다(누르는 순간 창이 깜빡이지 않게 그대로 둠)
TASKBAR_APPS = {"com.apple.dock"}


def _info(window: int) -> dict | None:
    """창 하나의 창 서버 정보(주인 프로세스·보이는지). 닫힌 창이면 None."""
    found = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionIncludingWindow, window) or []
    return next((item for item in found if item.get(Quartz.kCGWindowNumber) == window), None)


def native_window(win_id: int) -> int:
    """Qt 창의 winId(NSView 주소)를 창 서버 번호로. 창이 아직 만들어지지 않았으면 0."""
    view = objc.objc_object(c_void_p=win_id)
    window = view.window()
    return int(window.windowNumber()) if window is not None else 0


def foreground() -> tuple[int, int, bool]:
    """앞 창의 (창 번호, 프로세스 번호, Dock인가). 앞 프로그램의 맨 앞 보통 창 번호를 고른다(없으면 0)."""
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return 0, 0, False
    pid = int(app.processIdentifier())
    shown = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID
    ) or []  # 앞에서 뒤 차례
    window = next((int(item[Quartz.kCGWindowNumber]) for item in shown if item.get(Quartz.kCGWindowOwnerPID) == pid and item.get(Quartz.kCGWindowLayer) == 0), 0)
    return window, pid, (app.bundleIdentifier() or "") in TASKBAR_APPS


def any_shown(windows) -> bool:
    """창 가운데 최소화·숨김이 아니고 화면에 보이는 것이 하나라도 있나."""
    return any((info := _info(w)) is not None and bool(info.get(Quartz.kCGWindowIsOnscreen)) for w in windows)


def _own(window: int):
    """도우미 자신의 NSWindow(창 번호로 찾음). 없으면 None."""
    return AppKit.NSApp.windowWithWindowNumber_(window)


def put_on_top(window: int) -> None:
    """모든 창 위에(초점은 그대로). 전체 화면 Blender 위에도 보이게 모든 데스크탑 공간에 함께 둔다."""
    own = _own(window)
    if own is None:
        return
    own.setCollectionBehavior_(
        AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    own.setLevel_(AppKit.NSFloatingWindowLevel)
    own.orderFrontRegardless()


def put_behind(window: int, front: int) -> None:
    """맨 위를 풀고 front 창 바로 뒤로. front를 모르면(0) 맨 위만 푼다."""
    own = _own(window)
    if own is None:
        return
    own.setLevel_(AppKit.NSNormalWindowLevel)
    if front:
        own.orderWindow_relativeTo_(AppKit.NSWindowBelow, front)


def bring_forward(window: int) -> bool:
    """그 창의 프로그램을 앞으로 가져와 초점을 준다. 도우미 자신의 창이면 그 창을 열쇠 창으로. 못 하면 False."""
    info = _info(window)
    if info is None:
        return False
    pid = int(info.get(Quartz.kCGWindowOwnerPID, 0))
    if pid == os.getpid():
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        own = _own(window)
        if own is not None:
            own.makeKeyAndOrderFront_(None)
        return True
    app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    return bool(app and app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps))


def hide_from_dock() -> None:
    """Dock·Cmd+Tab에 나오지 않게(Windows의 Qt.Tool처럼 트레이 아이콘만). 메뉴 막대 아이콘은 남는다."""
    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
