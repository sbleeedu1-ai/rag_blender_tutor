"""도우미 창의 판단 규칙(ADR-0001 창 동작, 티켓 26). Windows를 직접 만지지 않아 화면 없이 시험한다.

창이 0.1초마다 화면 모습(Screen)을 읽어 place()에 묻고, 돌려받은 자리대로 winapi로 창을 옮긴다.
"""

import html
import math
import re
from dataclasses import dataclass
from enum import StrEnum


class Place(StrEnum):
    """창을 둘 자리."""

    TOP = "맨 위"  # Blender나 도우미 자신이 앞일 때
    BEHIND = "뒤로"  # 다른 프로그램이 앞이면 그 프로그램 바로 뒤
    HIDDEN = "숨김"  # Blender가 모두 최소화됐거나 사용자가 직접 내렸을 때
    KEEP = "그대로"  # 작업 표시줄·트레이가 앞일 때(트레이를 누르는 순간의 깜빡임 막기)


@dataclass(frozen=True)
class Screen:
    """한 번 읽은 화면 모습."""

    foreground_pid: int
    foreground_is_taskbar: bool  # 앞 창이 작업 표시줄·트레이인가
    blender_pids: frozenset[int]  # 켜진 Blender들(작업 상태를 보낸 것)
    blender_visible: bool  # 최소화되지 않은 Blender 창이 하나라도 있나


def place(screen: Screen, own_pid: int, put_away: bool) -> Place:
    """창을 둘 자리. put_away는 사용자가 X로 직접 내렸는가(F10·트레이로 부를 때까지 내린 채 둔다)."""
    # 최소화를 앞 창보다 먼저 본다: 작업 표시줄 단추로 Blender를 내리면 앞이 작업 표시줄로 남거나 도우미 창이 대신 앞이 된다
    if put_away or not screen.blender_visible:
        return Place.HIDDEN
    if screen.foreground_pid == own_pid or screen.foreground_pid in screen.blender_pids:
        return Place.TOP
    # 앞 창 없음(0, 초점이 넘어가는 사이)도 그대로 둔다. 0 '뒤로' 보내면 Windows는 맨 앞으로 올린다
    if screen.foreground_is_taskbar or not screen.foreground_pid:
        return Place.KEEP
    return Place.BEHIND


def needs_move(where: Place, front_window: int, last: tuple[Place, int] | None) -> bool:
    """창을 다시 옮겨야 하나. last는 지난번에 옮긴 (자리, 그때 앞 창 번호).

    '그 뒤로'는 앞 창이 바뀌면 다시 한다. Alt+Tab 고르기 화면(늘 맨 위인 창) 뒤로 간 뒤 다른 프로그램이 앞이 돼도
    자리가 같다고 건너뛰면 창이 맨 위에 남는다(2026-10-22 사용자 확인).
    """
    if where == Place.KEEP or last is None:
        return where != Place.KEEP
    last_place, last_front = last
    return where != last_place or (where == Place.BEHIND and front_window != last_front)


class FrontBlender:
    """마지막으로 앞에 있던 Blender 창. 질문은 이 Blender의 작업 상태로 보내고 Esc도 여기로 돌아간다."""

    def __init__(self):
        self._window: int | None = None

    def saw_foreground(self, pid: int, blenders: dict[int, int]) -> None:
        """앞 프로그램을 봤다. blenders는 켜진 Blender의 창 번호 → 프로세스 번호."""
        for window, blender_pid in blenders.items():
            if blender_pid == pid:
                self._window = window

    def summoned(self, window: int) -> None:
        """그 Blender에서 F10을 눌렀다."""
        self._window = window

    def window(self, blenders: dict[int, int]) -> int | None:
        """질문을 보낼 Blender 창 번호. 마지막 Blender가 닫혔으면 남은 것 아무거나, 하나도 없으면 None."""
        if self._window in blenders:
            return self._window
        return next(iter(blenders), None)


# 문장 끝 글자 뒤 빈칸. 5.2처럼 뒤에 빈칸이 없거나 "1. "처럼 숫자 바로 뒤 점(번호 목록)이면 그대로
_SENTENCE_END = re.compile(r"((?<![0-9])\.|[!?])[ \t]+")


def by_sentence(text: str) -> str:
    """문장 끝(. ! ? 뒤 빈칸)마다 줄을 바꾼다(HISTORY [18], 사용자 요청)."""
    return _SENTENCE_END.sub(r"\1\n", text)


SENDING = "질문을 보내는 중"  # 보낸 뒤 첫 단계가 오기 전(답 모델 thinking을 꺼도 참인 말, 검토 1(b))


def waiting_line(stage: str | None, seconds: float) -> str:
    """답을 기다리는 동안 보일 한 줄: 지금 단계 이름과 보낸 뒤 흐른 초(티켓 51, 단계를 늘어놓지 않고 지금 것 하나만)."""
    return f"{stage or SENDING} · {int(seconds)}초"


GREEN = (52, 199, 89)  # 지난 단계·지금 단계 점
GREY = (142, 142, 147)  # 남은 단계 점과 점 사이 줄(밝은·어두운 테마 모두에서 보이는 중간 회색)
PULSE = 1.2  # 지금 점의 밝기가 한 번 오르내리는 초


def waiting_html(current: int, total: int, stage: str | None, seconds: float) -> str:
    """기다림 줄 앞에 단계 점을 붙인 서식 글(사용자 11-23 "o - o - o - o … 한 단계 넘어갈때마다 초록색으로").

    지난 단계는 초록 ●, 지금 단계는 밝기가 오르내리는 빈 초록 ○(단계를 넘어가야 칠함), 남은 단계는 회색 ○. 단계 이름은 서식으로 읽히지 않게 바꾼다.
    """
    pulse = 0.35 + 0.65 * (0.5 + 0.5 * math.cos(2 * math.pi * seconds / PULSE))
    dots = []
    for i in range(total):
        rgb, alpha, shape = (GREEN, 1.0, "●") if i < current else (GREEN, pulse, "○") if i == current else (GREY, 1.0, "○")
        dots.append(f"<span style='color:rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha:.2f})'>{shape}</span>")
    line = f"<span style='color:rgb{GREY}'> ─ </span>".join(dots)
    return f"{line}&nbsp;&nbsp;{html.escape(waiting_line(stage, seconds))}"
