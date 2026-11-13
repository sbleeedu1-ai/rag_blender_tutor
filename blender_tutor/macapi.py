"""Mac에 창 일을 시키는 얇은 줄(winapi의 Mac 짝, HISTORY [312]). 판단은 넣지 않는다(판단은 window_rules, 화면 없이 시험함).

winapi와 같은 이름·같은 뜻의 함수를 둔다. 창 번호는 Mac 창 서버의 창 번호(CGWindowID)다. 애드온도 Blender 주 창의
같은 번호를 보내므로, Blender 창과 도우미 창을 한 가지 번호로 다룬다. 도우미 자신의 창은 Qt winId(NSView)를
native_window로 바꿔 쓴다.
실제 창·초점을 움직여야 해서 기본 테스트 밖이고 Mac 눈 확인으로 본다. pyobjc(Cocoa·Quartz)가 필요하다.
"""

import ctypes
import os
import time

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
    """모든 창 위에(초점은 그대로). 전체 화면 Blender 위에도 보이게 하되, 다른 데스크톱에는 따라가지 않는다
    (모든 데스크톱에 두면 데스크톱을 옮길 때마다 그쪽에 잠깐 나타났다 숨어 깜빡였다, HISTORY [312])."""
    own = _own(window)
    if own is None:
        return
    own.setCollectionBehavior_(  # F10으로 부를 때(활성화)는 지금 데스크톱으로 옮겨 온다
        AppKit.NSWindowCollectionBehaviorMoveToActiveSpace | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    own.setLevel_(AppKit.NSFloatingWindowLevel)
    own.orderFrontRegardless()
    _flush()
    # 창 서버가 실제로 맨 위 층에 둘 때까지 기다린다(최대 50ms). 누름을 붙잡은 동안 기다려야 Blender가 그 뒤에 올라온다:
    # 비우기만 하고 바로 놓아주면 Blender가 먼저 올라와 거의 매번 깜빡였다(2026-11-13 실측, 비우면 6-12ms 안에 반영)
    deadline = time.monotonic() + 0.05
    info = _info(window)
    while info is not None and info[Quartz.kCGWindowLayer] != AppKit.NSFloatingWindowLevel and time.monotonic() < deadline:
        info = _info(window)


def put_behind(window: int, front: int, blender: int = 0) -> None:
    """맨 위를 풀고 다른 프로그램 뒤로. blender(마지막 Blender 창)를 알면 그 창 바로 위에 둔다: 앞 프로그램 창은 늘 그 위라
    결과가 '앞 창 바로 뒤'와 같고, 앞 창이 아직 올라오는 중이어도 어긋나지 않는다(앞 창 기준으로 놓으면 알림 순간 그 창이
    아직 Blender 아래여서 도우미가 Blender 뒤까지 내려가 깜빡였다, 2026-11-13 실측, HISTORY [312]). 모르면 front 바로 뒤."""
    own = _own(window)
    if own is None:
        return
    own.setLevel_(AppKit.NSNormalWindowLevel)
    if blender:
        own.orderWindow_relativeTo_(AppKit.NSWindowAbove, blender)
    elif front:
        own.orderWindow_relativeTo_(AppKit.NSWindowBelow, front)
    _flush()


def _flush() -> None:
    """바꾼 층·차례를 창 서버에 바로 보낸다. 누름을 붙잡은 처리(watch_clicks) 안에서는 처리가 끝날 때까지 보내지 않아
    100ms를 기다려도 그대로였다(2026-11-13 실측)."""
    Quartz.CATransaction.flush()


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


def lost_top(window: int) -> bool:
    """맨 위에 올려 둔 도우미 창이 맨 위에서 내려왔나. Mac은 도우미가 초점을 잃으면(Blender를 누름) 맨 위를 풀어 버린다
    (2026-11-13 실측: 층 3 → 0). window_rules는 맨 위 → 맨 위를 다시 하지 않으므로 도우미가 이것으로 다시 올린다."""
    own = _own(window)
    return own is not None and own.level() < AppKit.NSFloatingWindowLevel


def elsewhere(blenders, window: int, shown: bool) -> bool:
    """사용자가 Blender·도우미가 있는 데스크톱을 떠나 다른 데스크톱을 보고 있나. 그동안 창 자리를 손대지 않는다.

    다른 데스크톱으로 가면 Blender 창도 화면에서 빠져 최소화와 구별되지 않는다. 그래서 보이게 둔(shown) 도우미 창도
    함께 화면에서 빠졌으면 데스크톱을 옮긴 것으로 본다. Blender를 최소화하면 도우미 창은 화면에 남아 있어 숨김으로 간다.
    """
    info = _info(window) if shown and window else None
    return info is not None and not info.get(Quartz.kCGWindowIsOnscreen) and not any_shown(blenders)


_sky = None  # 창이 어느 데스크톱에 있는지 묻는 SkyLight(Mac 비공개 기능, 처음 쓸 때 연다)


def _spaces(window: int) -> set[int]:
    """그 창이 놓인 데스크톱(Space) 번호들. 공식 기능이 없어 창 관리 앱들(yabai 등)이 쓰는 SkyLight 함수로 묻는다.
    macOS가 바꿔 못 물으면 빈 집합(그러면 same_space가 같은 곳으로 본다 = 이전 동작)."""
    global _sky
    if not window:
        return set()
    if _sky is None:
        sky = ctypes.CDLL("/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight")
        sky.SLSMainConnectionID.restype = ctypes.c_int
        sky.SLSCopySpacesForWindows.restype = ctypes.c_void_p
        sky.SLSCopySpacesForWindows.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        _sky = (sky, sky.SLSMainConnectionID())
    sky, connection = _sky
    found = sky.SLSCopySpacesForWindows(connection, 7, objc.pyobjc_id(AppKit.NSArray.arrayWithObject_(window)))  # 7: 모든 종류
    return {int(space) for space in objc.objc_object(c_void_p=found)} if found else set()


def same_space(window: int, front: int) -> bool:
    """도우미 창과 앞 창이 같은 데스크톱에 있나. 세 손가락으로 데스크톱을 옮기는 도중에는 옮겨 간 데스크톱의 앱이 앞이 되는데,
    그 창은 도우미와 다른 데스크톱이라 '뒤로' 가지 않는다(가면 돌아올 때 Blender가 덮었다가 다시 올라오며 깜빡였다,
    2026-11-13 실측: Blender·도우미 데스크톱 1, Claude 207, 같은 데스크톱의 Mail 1, HISTORY [312]). 모르면 같은 곳으로 본다."""
    mine, theirs = _spaces(window), _spaces(front)
    return not mine or not theirs or bool(mine & theirs)


def watch_activation(callback) -> object:
    """앞 앱이 바뀌는 즉시 callback을 부른다(0.1초마다 보는 것보다 빨리 옮겨, 다른 앱을 누를 때 도우미가 그 위에 잠깐 남지 않게).
    돌려준 값을 붙잡아 두어야 알림이 이어진다."""
    center = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
    return center.addObserverForName_object_queue_usingBlock_(
        AppKit.NSWorkspaceDidActivateApplicationNotification, None, AppKit.NSOperationQueue.mainQueue(), lambda note: callback()
    )


def watch_clicks(on_click) -> object | None:
    """마우스 왼쪽 단추를 누르는 순간 on_click(누른 자리 창 번호, 그 창 프로세스 번호)을 부른다(누름은 그대로 흘려보낸다).

    Mac은 누른 창을 먼저 올리고 앞 앱 알림은 그 뒤에 보내, 알림으로 움직이면 Blender를 누를 때 도우미가 0.1초 가려졌다
    (2026-11-13 실측, HISTORY [312]). '손쉬운 사용' 권한이 있으면 누름을 잠깐 붙잡아 Blender가 받기 전에 옮긴다. 없고
    '입력 모니터링' 권한만 있으면 엿듣기만 하는데, Blender를 누른 신호가 10-40ms 늦게 와 가끔 Blender가 먼저 올라온다
    (같은 날 실측). 둘 다 없으면 입력 모니터링 허락을 처음 한 번 묻고 None을 돌려준다(그동안은 알림 방식만 쓴다).
    돌려준 값을 붙잡아 두어야 이어진다.
    """
    taps = []

    def heard(proxy, kind, event, refcon):
        if kind in (Quartz.kCGEventTapDisabledByTimeout, Quartz.kCGEventTapDisabledByUserInput):  # 늦게 답해 꺼졌으면 다시 켠다
            Quartz.CGEventTapEnable(taps[0], True)
        elif kind == Quartz.kCGEventLeftMouseDown:
            x, y = Quartz.CGEventGetLocation(event)
            for item in Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID
            ) or []:  # 앞에서 뒤 차례: 누른 자리를 덮는 첫 창
                box = item[Quartz.kCGWindowBounds]
                if box["X"] <= x < box["X"] + box["Width"] and box["Y"] <= y < box["Y"] + box["Height"]:
                    if item[Quartz.kCGWindowLayer] <= Quartz.kCGFloatingWindowLevel:  # Dock·메뉴 막대를 누른 것은 따라가기에 맡김
                        on_click(int(item[Quartz.kCGWindowNumber]), int(item[Quartz.kCGWindowOwnerPID]))
                    break
        return event

    mask = Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)
    tap = None
    for option in (Quartz.kCGEventTapOptionDefault, Quartz.kCGEventTapOptionListenOnly):  # 붙잡기는 손쉬운 사용 권한이 있어야 만들어진다
        if option == Quartz.kCGEventTapOptionListenOnly and not Quartz.CGPreflightListenEventAccess():
            Quartz.CGRequestListenEventAccess()
            return None
        tap = Quartz.CGEventTapCreate(Quartz.kCGSessionEventTap, Quartz.kCGHeadInsertEventTap, option, mask, heard, None)
        if tap is not None:
            break
    if tap is None:
        return None
    taps.append(tap)
    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetMain(), source, Quartz.kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(tap, True)
    return tap, source, heard


def hide_from_dock() -> None:
    """Dock·Cmd+Tab에 나오지 않게(Windows의 Qt.Tool처럼 트레이 아이콘만). 메뉴 막대 아이콘은 남는다."""
    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
