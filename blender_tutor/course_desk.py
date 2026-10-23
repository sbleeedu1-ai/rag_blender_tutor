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
from pathlib import Path

from blender_tutor.progress import Ask, Course, Step, Withdraw
from blender_tutor.progress_record import AskChangeCourse, AskResume, ManagerCommand, Notice, ProgressManager, has_final
from blender_tutor.receiver import FileEvent
from blender_tutor.work_state import WorkState

# 감지 조건이 있는 조작에도 [했어요]를 보인다. 감지 조건의 조작 이름은 아직 Blender에서 사람이 직접 해 보며 확인하지 않아,
# 감지가 빗나가도 막히지 않게 하려는 것이다. 티켓 32(검 연습 과정 따라 하며 고치기)에서 감지가 잘 되는 것을 확인하면
# False로 바꿔, 감지 조건이 없는 조작(화면 돌리기처럼 Blender 조작 기록에 남지 않는 것)에만 [했어요]를 남긴다.
WALK_BUTTON_EVEN_IF_DETECTED = True

ALL_WALKED = "이 단계에서 할 조작은 다 했어요. 다 됐으면 '다음 단계'를 눌러 주세요."
NO_WALKS = "이 단계는 다 되면 '다음 단계'를 눌러 넘어가요."


@dataclass(frozen=True)
class StepView:
    """창에 보일 진행 모양."""

    course: Course | None  # 고르지 않았으면 None(연습 과정 고르기를 보인다)
    number: int  # 지금 단계가 몇 번째인지(파일 순서, 1부터). 고르지 않았거나 마쳤으면 0
    step: Step | None  # 지금 단계. 고르지 않았거나 마쳤으면 None
    prompt: str | None  # [네] [아니요]로 답할 물음 글. 없으면 None
    can_walk: bool = False  # [했어요]를 보이나(안내 중인 조작이 있음)


@dataclass(frozen=True)
class Line:
    """대화에 붙일 한 줄. kind는 guide(도우미 안내 말) 또는 notice(진행 관리의 알림)."""

    kind: str
    text: str


class CourseDesk:
    """Blender 창 번호마다 진행 관리 하나. 함수마다 대화에 붙일 말 목록을 돌려준다."""

    def __init__(self, courses: list[Course], record_dir: Path, now: Callable[[], datetime] = datetime.now):
        self.courses = courses
        self._record_dir = record_dir
        self._now = now
        self._managers: dict[int, ProgressManager] = {}
        # 창 번호마다 답을 기다리는 물음. 마지막 것을 보이고, 답하면 그 앞 물음이 다시 보인다
        self._prompts: dict[int, list[Ask | AskResume | AskChangeCourse]] = {}
        # 창 번호마다 대화에 마지막으로 말한 자리 (연습 과정, 단계, 조작 번호). 바뀌면 그만큼 말한다
        self._said: dict[int, tuple[Course | None, Step | None, int]] = {}

    def on_message(self, window: int, state: WorkState, event: FileEvent | None = None) -> list[Line]:
        """Blender에서 봉투가 왔을 때. 파일 사건을 먼저 넘기고 작업 상태를 넘긴다."""
        manager = self._manager(window)
        lines = []
        if event is not None and event.kind == "opened":
            self._prompts[window] = []  # 진행 관리가 지금 진행을 비우며 기다리던 물음도 버린다
            lines += self._apply(window, manager.on_file_opened(event.path))
        elif event is not None:
            lines += self._apply(window, manager.on_file_saved(event.path))
        return lines + self._apply(window, manager.on_state(state))

    def choose(self, window: int, label: str) -> list[Line]:
        """연습 과정 고르기. 이어 할까요 물음이 떠 있으면 거절한 것으로 보고 거둔다(기록은 남는다)."""
        manager = self._manager(window)
        prompts = self._prompts.setdefault(window, [])
        if any(isinstance(p, AskResume) for p in prompts):
            prompts[:] = [p for p in prompts if not isinstance(p, AskResume)]
            manager.on_resume_answer(False)
        # 바꿀까요 물음은 진행 관리가 새로 고른 것만 기억하므로 앞 물음을 거둔다
        prompts[:] = [p for p in prompts if not isinstance(p, AskChangeCourse)]
        return self._apply(window, manager.choose_course(label))

    def next_step(self, window: int) -> list[Line]:
        """'다음 단계' 버튼."""
        return self._apply(window, self._manager(window).next_step())

    def walked(self, window: int) -> list[Line]:
        """[했어요]: 안내 중인 조작을 했다."""
        return self._apply(window, self._manager(window).walked())

    def answer(self, window: int, yes: bool) -> list[Line]:
        """떠 있는 물음에 [네]/[아니요]. 답한 물음은 닫는다. 물음이 없으면(늦게 누름) 아무것도 하지 않는다."""
        prompts = self._prompts.get(window)
        if not prompts:
            return []
        prompt, manager = prompts.pop(), self._manager(window)
        if isinstance(prompt, AskResume):
            return self._apply(window, manager.on_resume_answer(yes))
        if isinstance(prompt, AskChangeCourse):
            return self._apply(window, manager.on_change_answer(yes))
        return self._apply(window, manager.on_answer(yes))

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
            self._prompts.pop(window, None)
            self._said.pop(window, None)

    def step(self, window: int) -> Step | None:
        """그 창의 지금 단계(답 엔진에 넘김)."""
        return self._manager(window).step

    def view(self, window: int) -> StepView:
        """그 창에 보일 진행 모양."""
        manager = self._manager(window)
        course, step, walk = manager.course, manager.step, manager.walk
        number = course.steps.index(step) + 1 if course and step else 0
        prompts = self._prompts.get(window)
        operation = step.operations[walk] if step and walk < len(step.operations) else None
        can_walk = operation is not None and (WALK_BUTTON_EVEN_IF_DETECTED or not operation.detect)
        return StepView(course, number, step, prompts[-1].text if prompts else None, can_walk)

    def _manager(self, window: int) -> ProgressManager:
        if window not in self._managers:
            self._managers[window] = ProgressManager(self.courses, self._record_dir, self._now)
        return self._managers[window]

    def _apply(self, window: int, commands: list[ManagerCommand]) -> list[Line]:
        """진행 관리가 돌려준 할 일을 그 창의 떠 있는 물음에 반영하고, 알림과 바뀐 자리의 안내 말을 돌려준다."""
        prompts = self._prompts.setdefault(window, [])
        lines = []
        for command in commands:
            if isinstance(command, Notice):
                lines.append(Line("notice", command.text))
            elif isinstance(command, Withdraw):
                prompts[:] = [p for p in prompts if not (isinstance(p, Ask) and p.step == command.step)]
            else:
                prompts.append(command)
        return lines + self._narrate(window)

    def _narrate(self, window: int) -> list[Line]:
        """지난번 말한 자리에서 바뀐 만큼 안내 말을 만든다: 연습 과정 시작·이어 함, 단계 시작, 조작 안내, 마침."""
        manager = self._manager(window)
        course, step, walk = manager.course, manager.step, manager.walk
        said_course, said_step, said_walk = self._said.get(window, (None, None, 0))
        self._said[window] = (course, step, walk)
        if course is None or (course, step, walk) == (said_course, said_step, said_walk):
            return []
        number = course.steps.index(step) + 1 if step else 0
        lines = []
        if course != said_course:
            again = number > 1 or walk > 0
            lines.append(Line("guide", f"{course.name} 연습 과정을 {'이어서 할게요' if again else '시작할게요'}."))
        if step is None:
            return lines + [Line("guide", f"{course.name} 연습 과정을 다 마쳤어요. 수고하셨어요!")]
        if step != said_step or course != said_course:
            lines.append(Line("guide", f"{number}단계, {step.name}{'이에요' if has_final(step.name) else '예요'}."))
            if not step.operations:
                lines.append(Line("guide", NO_WALKS))
        elif walk == said_walk:
            return lines
        if walk < len(step.operations):
            lines.append(Line("guide", step.operations[walk].say))
        elif step.operations:
            lines.append(Line("guide", ALL_WALKED))
        return lines
