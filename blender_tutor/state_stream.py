"""작업 상태 흐름 기록: 진행 관리에 들어간 봉투·버튼을 파일에 남겨, 끝난 조건을 고친 뒤 Blender 없이 다시 돌린다(User Story 80, 티켓 28).

검수(티켓 32)에서 사용자가 따라 한 흐름을 그대로 회귀 테스트에 넣으려는 것이다. 받은 작업 상태만 남기면 연습 과정 고르기·
'다음'·[네] 같은 버튼이 빠져 다시 돌려도 진행이 움직이지 않으므로, CourseDesk를 바꾸는 부름을 모두 차례대로 남긴다.
한 줄(JSON)이 부름 하나: {"call": 함수 이름, "window": 창 번호, ...그 함수의 값}. 작업 상태는 애드온이 보낸 JSON 모양 그대로.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from blender_tutor.course_desk import CourseDesk, Line, StepView
from blender_tutor.progress import Step
from blender_tutor.receiver import FileEvent
from blender_tutor.work_state import WorkState

log = logging.getLogger(__name__)


class RecordingDesk:
    """CourseDesk를 감싸 바꾸는 부름마다 흐름 파일에 한 줄 쓰고 그대로 넘긴다. 못 쓰면 한 번 알리고 기록만 멈춘다."""

    def __init__(self, desk: CourseDesk, path: Path):
        self._desk = desk
        self._path = path
        self._broken = False
        self._windows: set[int] = set()  # 기록한 부름에 나온 창 번호(keep이 버릴 진행이 있는지 가리려고)

    def on_message(self, window: int, state: WorkState, event: FileEvent | None = None, shown: bool = True) -> list[Line]:
        event_json = None if event is None else {"kind": event.kind, "path": event.path}
        self._write("on_message", window=window, state=state.to_json(), event=event_json, shown=shown)
        return self._desk.on_message(window, state, event, shown)

    def switched_to(self, window: int) -> list[Line]:
        self._write("switched_to", window=window)
        return self._desk.switched_to(window)

    def choose(self, window: int, label: str) -> list[Line]:
        self._write("choose", window=window, label=label)
        return self._desk.choose(window, label)

    def forward(self, window: int) -> list[Line]:
        self._write("forward", window=window)
        return self._desk.forward(window)

    def answer(self, window: int, yes: bool) -> list[Line]:
        self._write("answer", window=window, yes=yes)
        return self._desk.answer(window, yes)

    def back(self, window: int) -> list[Line]:
        self._write("back", window=window)
        return self._desk.back(window)

    def skip_to(self, window: int, label: str) -> list[Line]:
        self._write("skip_to", window=window, label=label)
        return self._desk.skip_to(window, label)

    def keep(self, windows: set[int]) -> None:
        if self._windows - windows:  # 자주 불리므로 버릴 진행이 있을 때만 남긴다
            self._write("keep", windows=sorted(windows))
            self._windows &= windows
        self._desk.keep(windows)

    def step(self, window: int) -> Step | None:
        return self._desk.step(window)

    def view(self, window: int) -> StepView:
        return self._desk.view(window)

    def _write(self, call: str, **values) -> None:
        if "window" in values:
            self._windows.add(values["window"])
        if self._broken:
            return
        try:
            with open(self._path, "a", encoding="utf-8") as file:
                file.write(json.dumps({"call": call, **values}, ensure_ascii=False) + "\n")
        except OSError as error:
            self._broken = True
            log.warning("작업 상태 흐름을 쓰지 못해 기록을 멈춤(%s): %s", self._path, error)


def replay(path: Path, desk: CourseDesk) -> Iterator[tuple[dict, list[Line]]]:
    """흐름 파일을 desk에 차례로 넣는다. 줄마다 (그 줄, 돌려받은 대화 말)을 내므로 그 사이에 desk.view로 진행을 볼 수 있다."""
    for text in path.read_text(encoding="utf-8").splitlines():
        entry = json.loads(text)
        call, window = entry["call"], entry.get("window")
        if call == "on_message":
            event = None if entry["event"] is None else FileEvent(entry["event"]["kind"], entry["event"]["path"])
            lines = desk.on_message(window, WorkState.from_json(entry["state"]), event, entry["shown"])
        elif call in ("choose", "skip_to"):
            lines = getattr(desk, call)(window, entry["label"])
        elif call == "answer":
            lines = desk.answer(window, entry["yes"])
        elif call == "keep":
            desk.keep(set(entry["windows"]))
            lines = []
        else:  # switched_to·forward·back
            lines = getattr(desk, call)(window)
        yield entry, lines
