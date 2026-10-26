"""시간 기록: 질문마다 걸린 시간을 스톱워치 없이 재려고 기록 파일에 한 줄씩 남긴다(명세 "도우미 창", User Story 66, 티켓 28).

한 줄(JSON)은 질문 하나: F10 누름 → 받음 → 입력 가능 → 보냄 → 첫 글자 → 답 끝 시각(time.time() 초), 생각 수준, PC 이름.
F10 시각은 F10 뒤 첫 질문에만 붙인다. 창이 떠 있는 채 이어 물으면 준비 시간이 없어 비운다(None).
평가 프로그램(티켓 29)이 이 파일을 읽어 가운데값·최대값을 낸다. 못 써도 답에는 영향이 없게 기록 오류는 삼킨다.
"""

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

from blender_tutor.answer_engine import Event, Failure, Piece

log = logging.getLogger(__name__)


class Stopwatch:
    """도우미 창 하나의 시간 기록. summoned·ready·asked는 화면 스레드에서, Lap.saw는 답 만들기 스레드에서 부른다."""

    def __init__(self, path: Path, pc: str, clock: Callable[[], float] = time.time):
        self._path = path
        self._pc = pc
        self._clock = clock
        self._f10: dict[str, float | None] = {}  # 다음 질문에 붙일 F10 시각(누름·받음·입력 가능)
        self._lock = threading.Lock()  # 답 둘이 겹쳐 끝나도 줄이 섞이지 않게

    def summoned(self, pressed: float | None) -> None:
        """F10 봉투를 받았을 때. pressed는 애드온이 F10을 받은 시각."""
        self._f10 = {"f10_pressed": pressed, "f10_received": self._clock(), "ready": None}

    def ready(self) -> None:
        """F10 뒤 창이 올라와 입력할 수 있게 됐을 때."""
        if self._f10:
            self._f10["ready"] = self._clock()

    def asked(self, question: str, reasoning: str | None) -> "Lap":
        """질문을 보냈을 때. 답 사건을 Lap.saw에 넘기면 답이 끝날 때 한 줄을 쓴다."""
        f10, self._f10 = self._f10, {}
        record = {
            "pc": self._pc,
            "reasoning": reasoning,
            "question": question,
            "f10_pressed": f10.get("f10_pressed"),
            "f10_received": f10.get("f10_received"),
            "ready": f10.get("ready"),
            "sent": self._clock(),
            "first_piece": None,
        }
        return Lap(self, record)

    def _write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        try:
            with self._lock, open(self._path, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError as error:
            log.warning("시간 기록을 쓰지 못함(%s): %s", self._path, error)


class Lap:
    """질문 하나의 시각들. 첫 Piece에 첫 글자, Done·Failure에 답 끝을 적고 그때 기록 파일에 쓴다."""

    def __init__(self, watch: Stopwatch, record: dict):
        self._watch = watch
        self._record = record

    def saw(self, event: Event) -> None:
        if isinstance(event, Piece):
            if self._record["first_piece"] is None:
                self._record["first_piece"] = self._watch._clock()
            return
        self._record["done"] = self._watch._clock()
        self._record["outcome"] = "failure" if isinstance(event, Failure) else "done"
        self._watch._write(self._record)
