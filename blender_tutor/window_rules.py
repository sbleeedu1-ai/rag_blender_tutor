"""도우미 창의 판단 규칙(ADR-0001 창 동작, 티켓 26). Windows를 직접 만지지 않아 화면 없이 시험한다.

창이 0.1초마다 화면 모습(Screen)을 읽어 place()에 묻고, 돌려받은 자리대로 winapi로 창을 옮긴다.
"""

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

    foreground_pid: int  # 앞 프로그램의 프로세스 번호
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
