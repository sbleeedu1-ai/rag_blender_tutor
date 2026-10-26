"""시간 기록: 질문마다 걸린 시간을 스톱워치 없이 재려고 기록 파일에 한 줄씩 남긴다(명세 "도우미 창", User Story 66, 티켓 28).

한 줄(JSON)은 질문 하나: F10 누름 → 받음 → 입력 가능 → 보냄 → 첫 글자 → 답 끝 시각(time.time() 초), PC 이름,
그때의 엔진 이름과 설정(생각 수준·검색 개수·최근 대화 쌍 수 등). 임시 엔진의 줄과 진짜 엔진의 줄, 설정을 바꿔 잰 줄을 가르려는 것이다.
F10 시각은 F10 뒤 첫 질문에만, 입력 가능 뒤 F10_VALID초 안에 보냈을 때만 붙인다. 창이 떠 있는 채 이어 물었거나,
F10을 누르고 묻지 않은 채 Blender에서 작업하다 창을 눌러 물었으면 준비 시간이 아니라서 비운다(None).
평가 프로그램(티켓 29)이 이 파일을 읽어 가운데값·최대값을 낸다. 못 써도 답에는 영향이 없게 기록 오류는 삼킨다.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from blender_tutor.answer_engine import Event, Failure, Piece

# F10 시각을 붙이는 한도(초). 다른 창에서 복사해 붙여 넣느라 오가는 시간은 넉넉히 들고,
# 묻지 않고 떠났다 돌아온 질문은 거른다(2026-10-26 사용자 결정)
F10_VALID = 60.0

log = logging.getLogger(__name__)


class Outcome(StrEnum):
    """질문 하나가 어떻게 끝났나. 정해 둔 이름만 쓴다."""

    DONE = "done"  # 답이 끝까지 나옴
    FAILURE = "failure"  # 오류·시간 초과·작업 상태 없음 등으로 멈춤


@dataclass
class _F10:
    """다음 질문에 붙일 F10 시각 셋. 칸 이름을 틀리면 바로 오류가 나게 묶는다."""

    pressed: float | None  # 애드온이 F10을 받은 시각(옛 봉투면 None)
    received: float  # 도우미가 받은 시각
    ready: float | None = None  # 입력 가능해진 시각


class Stopwatch:
    """도우미 창 하나의 시간 기록. summoned·ready·asked는 화면 스레드에서, Lap.saw는 답 만들기 스레드에서 부른다."""

    def __init__(self, path: Path, pc: str, clock: Callable[[], float] = time.time):
        self._path = path
        self._pc = pc
        self._clock = clock
        self._f10: _F10 | None = None  # 다음 질문에 붙일 F10 시각
        self._lock = threading.Lock()  # 답 둘이 겹쳐 끝나도 줄이 섞이지 않게

    def summoned(self, pressed: float | None) -> None:
        """F10 봉투를 받았을 때. pressed는 애드온이 F10을 받은 시각."""
        self._f10 = _F10(pressed, self._clock())

    def ready(self) -> None:
        """F10 뒤 창이 올라와 입력할 수 있게 됐을 때."""
        if self._f10 is not None:
            self._f10.ready = self._clock()

    def asked(self, question: str, engine: dict | None) -> "Lap":
        """질문을 보냈을 때. engine은 {"name": 엔진 이름, "settings": 설정 사전}, 엔진 준비 전이면 None.

        답 사건을 Lap.saw에 넘기면 답이 끝날 때 한 줄을 쓴다.
        """
        f10, self._f10 = self._f10, None
        sent = self._clock()
        if f10 is not None and sent - (f10.ready or f10.received) > F10_VALID:
            f10 = None
        record = {
            "pc": self._pc,
            "engine": None if engine is None else engine["name"],
            "settings": None if engine is None else engine["settings"],
            "question": question,
            "f10_pressed": None if f10 is None else f10.pressed,
            "f10_received": None if f10 is None else f10.received,
            "ready": None if f10 is None else f10.ready,
            "sent": sent,
            "first_piece": None,
        }
        return Lap(record, self._clock, self._write)

    def _write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._lock, open(self._path, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError as error:
            log.warning("시간 기록을 쓰지 못함(%s): %s", self._path, error)


class Lap:
    """질문 하나의 시각들. 첫 Piece에 첫 글자, Done·Failure에 답 끝을 적고 그때 기록 파일에 쓴다."""

    def __init__(self, record: dict, clock: Callable[[], float], write: Callable[[dict], None]):
        self._record = record
        self._clock = clock
        self._write = write  # 답이 끝나면 한 줄을 쓴다(Stopwatch._write)

    def saw(self, event: Event) -> None:
        if isinstance(event, Piece):
            if self._record["first_piece"] is None:
                self._record["first_piece"] = self._clock()
            return
        self._record["done"] = self._clock()
        self._record["outcome"] = Outcome.FAILURE if isinstance(event, Failure) else Outcome.DONE
        self._write(self._record)
