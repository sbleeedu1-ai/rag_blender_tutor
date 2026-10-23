"""창 번호마다 진행 관리: Blender 창 번호마다 ProgressManager를 하나씩 두고, 창에 보일 단계·물음과 대화에 붙일 말을 정리한다(티켓 27).

Blender 둘을 오가도 창을 바꿀 때 "파일 열림"이 오지 않으므로, 진행 관리를 하나만 두면 다른 창의 버튼이 엉뚱한 파일 기록에
적힌다(HISTORY [31]). 그래서 창 번호마다 따로 두고 기록 폴더만 함께 쓴다. 각 창의 진행은 그 창 파일의 기록에만 남는다.
도우미 창(helper)은 사건과 버튼을 여기 넘기고, 돌려받은 말(Line)을 대화에 붙이고 view로 단계 카드를 다시 그린다.

대화에 붙이는 말: 연습 과정을 시작하거나 이어 할 때 인사, 단계가 바뀌면 단계 시작, 조작마다 연습 과정 파일의 안내 말.
조작은 감지 조건이 맞거나 [했어요]를 누르면 다음으로 간다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from blender_tutor.korean_particles import has_final
from blender_tutor.progress import Course, Step
from blender_tutor.progress_record import ManagerCommand, Notice, ProgressManager
from blender_tutor.receiver import FileEvent
from blender_tutor.work_state import WorkState

# 감지 조건이 있는 조작에도 [했어요]를 보인다. 감지 조건(조작 이름·배율·위치·시점)은 아직 도우미 창에서 사람이 직접
# 해 보며 확인하지 않아, 감지가 빗나가도 막히지 않게 하려는 것이다. 티켓 32(검 연습 과정 따라 하며 고치기)에서 감지가 잘
# 되는 것을 확인하면 False로 바꿔, 감지 조건이 없는 조작(옆 패널 열기·X-ray 켜기처럼 작업 상태로 알 수 없는 것)에만 [했어요]를 남긴다.
DONE_BUTTON_EVEN_IF_DETECTED = True

ALL_OPERATIONS_DONE = "이 단계에서 할 조작은 다 했어요. 다 됐으면 '다음 단계'를 눌러 주세요."
NO_OPERATIONS = "이 단계는 다 되면 '다음 단계'를 눌러 넘어가요."


@dataclass(frozen=True)
class StepView:
    """창에 보일 진행 모양."""

    course: Course | None  # 고르지 않았으면 None(연습 과정 고르기를 보인다)
    number: int  # 지금 단계가 몇 번째인지(파일 순서, 1부터). 고르지 않았거나 마쳤으면 0
    step: Step | None  # 지금 단계. 고르지 않았거나 마쳤으면 None
    prompt: str | None  # [네] [아니요]로 답할 물음 글. 없으면 None
    done_button: bool = False  # [했어요]를 보이나(안내 중인 조작이 있음)


class LineKind(StrEnum):
    """대화 말 종류. 정해 둔 이름만 쓴다(오타를 내면 바로 오류가 난다). 창은 이 이름으로 글씨 모양을 고른다."""

    GUIDE = "guide"  # 도우미 안내 말(인사·단계 시작·조작 안내)
    NOTICE = "notice"  # 진행 관리의 알림


@dataclass(frozen=True)
class Line:
    """대화에 붙일 한 줄."""

    kind: LineKind
    text: str


class CourseDesk:
    """Blender 창 번호마다 진행 관리 하나. 함수마다 대화에 붙일 말 목록을 돌려준다."""

    def __init__(self, courses: list[Course], record_dir: Path, now: Callable[[], datetime] = datetime.now):
        self.courses = courses
        self._record_dir = record_dir
        self._now = now
        self._managers: dict[int, ProgressManager] = {}
        # 창 번호마다 대화에 마지막으로 말한 자리 (연습 과정, 단계, 끝낸 조작 수). 바뀌면 그만큼 말한다
        self._said: dict[int, tuple[Course | None, Step | None, int]] = {}
        # 창 번호마다 뒤에 있을 때 생긴 알림(옮겨 오면 보인다)
        self._held: dict[int, list[Line]] = {}

    def on_message(self, window: int, state: WorkState, event: FileEvent | None = None, shown: bool = True) -> list[Line]:
        """Blender에서 봉투가 왔을 때. 파일 사건을 먼저 넘기고 작업 상태를 넘긴다.

        shown은 이 Blender가 도우미 창에 보이는(마지막으로 앞에 있던) Blender인가. 도우미 창 하나를 Blender 여럿이
        함께 쓰므로, 뒤에 있는 Blender의 말은 대화에 붙이지 않는다. 알림은 모아 두었다가 그 Blender로 옮겨 오면
        switched_to가 보이고, 안내 말은 그때의 자리로 다시 말한다.
        """
        manager = self._manager(window)
        lines = []
        if event is not None and event.kind == "opened":
            lines += self._apply(window, manager.on_file_opened(event.path))
        elif event is not None:
            lines += self._apply(window, manager.on_file_saved(event.path))
        lines += self._apply(window, manager.on_state(state))
        if shown:
            return lines
        self._held.setdefault(window, []).extend(line for line in lines if line.kind == LineKind.NOTICE)
        return []

    def switched_to(self, window: int) -> list[Line]:
        """도우미 창이 다른 Blender를 보이게 됐을 때. 뒤에 있는 동안 생긴 알림과 그 Blender의 지금 자리를 알려 준다."""
        lines = self._held.pop(window, [])
        manager = self._manager(window)
        course, step = manager.course, manager.step
        self._said[window] = (course, step, manager.operations_done)  # 지금 자리까지 말한 것으로 친다
        if course is None:
            return lines  # 고르지 않았으면 카드의 고르기 목록이 대신 보인다
        if step is None:
            return lines + [Line(LineKind.GUIDE, f"이 Blender는 {course.name} 연습 과정을 다 마쳤어요.")]
        lines.append(Line(LineKind.GUIDE, f"이 Blender는 {course.name} {manager.number}단계, {_is(step.name)}."))
        return lines + self._operation_line(manager)

    def choose(self, window: int, label: str) -> list[Line]:
        """연습 과정 고르기(처음 고르기·바꾸기). 떠 있는 물음을 어떻게 할지는 진행 관리가 정한다."""
        return self._apply(window, self._manager(window).choose_course(label))

    def next_step(self, window: int) -> list[Line]:
        """'다음 단계' 버튼."""
        return self._apply(window, self._manager(window).next_step())

    def next_operation(self, window: int) -> list[Line]:
        """[했어요]: 안내 중인 조작을 했다."""
        return self._apply(window, self._manager(window).next_operation())

    def answer(self, window: int, yes: bool) -> list[Line]:
        """떠 있는 물음에 [네]/[아니요]. 어느 물음의 답인지는 진행 관리가 가린다(물음이 없으면 아무것도 하지 않음)."""
        return self._apply(window, self._manager(window).answer(yes))

    def back(self, window: int) -> list[Line]:
        """'뒤로' 버튼."""
        return self._apply(window, self._manager(window).back())

    def skip_to(self, window: int, label: str) -> list[Line]:
        """원하는 단계로 건너뛰기."""
        return self._apply(window, self._manager(window).skip_to(label))

    def keep(self, windows: set[int]) -> None:
        """켜진 Blender 창 번호만 남기고 나머지 진행은 버린다(진행 기록은 파일에 남아 있다)."""
        for window in set(self._managers) - windows:
            del self._managers[window]
            self._said.pop(window, None)
            self._held.pop(window, None)

    def step(self, window: int) -> Step | None:
        """그 창의 지금 단계(답 엔진에 넘김)."""
        return self._manager(window).step

    def view(self, window: int) -> StepView:
        """그 창에 보일 진행 모양."""
        manager = self._manager(window)
        course, step, operation = manager.course, manager.step, manager.operation
        done_button = operation is not None and (DONE_BUTTON_EVEN_IF_DETECTED or not operation.detect)
        return StepView(course, manager.number, step, manager.prompt, done_button)

    def _manager(self, window: int) -> ProgressManager:
        if window not in self._managers:
            self._managers[window] = ProgressManager(self.courses, self._record_dir, self._now)
        return self._managers[window]

    def _apply(self, window: int, commands: list[ManagerCommand]) -> list[Line]:
        """진행 관리가 돌려준 할 일에서 알림을 대화 말로 꺼내고, 바뀐 자리의 안내 말을 붙인다.

        물음(띄우기·거두기)은 진행 관리가 들고 있어 view가 prompt로 읽는다.
        """
        lines = [Line(LineKind.NOTICE, command.text) for command in commands if isinstance(command, Notice)]
        return lines + self._narrate(window)

    def _narrate(self, window: int) -> list[Line]:
        """지난번 말한 자리에서 바뀐 만큼 안내 말을 만든다: 연습 과정 시작·이어 함, 단계 시작, 조작 안내, 마침."""
        manager = self._manager(window)
        course, step, operations_done = manager.course, manager.step, manager.operations_done
        said_course, said_step, said_done = self._said.get(window, (None, None, 0))
        self._said[window] = (course, step, operations_done)
        if course is None or (course, step, operations_done) == (said_course, said_step, said_done):
            return []
        number = manager.number
        lines = []
        if course != said_course:
            again = number > 1 or operations_done > 0
            lines.append(Line(LineKind.GUIDE, f"{course.name} 연습 과정을 {'이어서 할게요' if again else '시작할게요'}."))
        if step is None:
            return lines + [Line(LineKind.GUIDE, f"{course.name} 연습 과정을 다 마쳤어요. 수고하셨어요!")]
        if step != said_step or course != said_course:
            lines.append(Line(LineKind.GUIDE, f"{number}단계, {_is(step.name)}."))
        elif operations_done == said_done:
            return lines
        return lines + self._operation_line(manager)

    @staticmethod
    def _operation_line(manager: ProgressManager) -> list[Line]:
        """지금 조작의 안내 말. 조작을 다 끝냈거나 조작이 없는 단계면 '다음 단계'를 누르라는 말."""
        if manager.operation is not None:
            return [Line(LineKind.GUIDE, manager.operation.say)]
        return [Line(LineKind.GUIDE, ALL_OPERATIONS_DONE if manager.step.operations else NO_OPERATIONS)]


def _is(name: str) -> str:
    """이름 뒤에 '이에요/예요'를 붙인다(받침에 따라)."""
    return f"{name}{'이에요' if has_final(name) else '예요'}"
