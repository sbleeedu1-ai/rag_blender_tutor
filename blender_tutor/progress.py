"""진행 관리: 작업 상태와 사용자 응답을 사건으로 받아, 띄울 물음·거둘 물음과 지금 단계를 돌려준다.

도우미 창과 떼어 둔 모듈이다(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).
창을 그리거나 앞으로 끌어오는 일은 하지 않고, 돌려준 물음을 창이 자기 안에만 띄운다.
끝난 조건의 판정 규칙은 conditions.py에 있다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from blender_tutor.conditions import CONDITIONS, WorkState


@dataclass(frozen=True)
class Step:
    """연습 과정의 단계 하나에서 진행 관리가 쓰는 것."""

    label: str  # 이름표(예: blade-tip)
    name: str  # 화면에 보이는 이름
    conditions: tuple[tuple[str, object], ...] = ()  # 끝난 조건 (종류, 값) 목록. 비면 버튼으로만 넘어간다


@dataclass(frozen=True)
class Course:
    """연습 과정 하나: 이름표, 화면에 보이는 이름, 공통 준비부터 파일 순서대로 늘어놓은 단계."""

    label: str
    name: str
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Ask:
    """창 안에 띄울 "다음 단계로 갈까요" 물음."""

    step: str  # 물음을 띄운 단계의 이름표
    text: str


@dataclass(frozen=True)
class Withdraw:
    """띄워 둔 물음을 거두라는 알림."""

    step: str


Command = Ask | Withdraw


def load_steps(course: Path) -> list[Step]:
    """연습 과정 파일에서 단계를 파일 순서대로 읽는다. '먼저 할 것'이 가리키는 공통 준비 단계가 맨 앞에 온다.

    파일은 course_check 검사를 통과했다고 본다.
    """
    return _steps_of(yaml.safe_load(course.read_text(encoding="utf-8")), course.parent)


def load_course(course: Path) -> Course:
    """연습 과정 파일 하나를 읽는다. 단계는 load_steps와 같이 공통 준비부터."""
    data = yaml.safe_load(course.read_text(encoding="utf-8"))
    return Course(data["이름표"], data["이름"], tuple(_steps_of(data, course.parent)))


def _steps_of(data: dict, folder: Path) -> list[Step]:
    """읽어 둔 연습 과정 파일 내용에서 단계를 꺼낸다. '먼저 할 것'은 같은 폴더에서 찾는다."""
    steps = load_steps(folder / data["먼저 할 것"]) if "먼저 할 것" in data else []
    for section in data["구간"]:
        for step in section["단계"]:
            conditions = tuple(next(iter(c.items())) for c in step.get("끝난 조건", []))
            steps.append(Step(step["이름표"], step["이름"], conditions))
    return steps


class Progress:
    """한 연습 과정의 진행. 사건 함수마다 창이 할 일(물음 띄우기·거두기) 목록을 돌려준다."""

    def __init__(self, steps: Sequence[Step], start: int = 0, finished: tuple[str, ...] = ()):
        """이어 할 때는 시작할 단계 번호(0부터, 단계 수와 같으면 마친 상태)와 끝낸 단계 이름표를 받는다."""
        self._steps = list(steps)
        self._index = start
        self._finished = list(finished)  # 사용자가 [네]나 '다음 단계' 버튼으로 끝낸 단계 이름표. 건너뛴 단계는 넣지 않는다
        self._asking = False  # 물음을 띄워 두고 답을 기다리는 중
        self._declined: set[str] = set()  # 물음을 거절한 단계 이름표. 이 단계들은 다시 묻지 않는다
        self._latest: WorkState | None = None  # 마지막으로 받은 작업 상태
        self._start_count: int | None = None  # 지금 단계를 시작할 때 장면 물체 수(모르면 다음 상태에서 정함)

    @property
    def step(self) -> Step | None:
        """지금 단계. 연습 과정을 마쳤으면 None."""
        return self._steps[self._index] if self._index < len(self._steps) else None

    @property
    def finished(self) -> tuple[str, ...]:
        """끝낸 단계 이름표(끝낸 차례대로). 뒤로 가도 줄지 않는다."""
        return tuple(self._finished)

    def on_state(self, state: WorkState) -> list[Command]:
        """작업 상태가 도착했을 때."""
        self._latest = state
        if self._start_count is None:
            self._start_count = state.scene_object_count
        step = self.step
        if step is None:
            return []
        met = bool(step.conditions) and all(
            CONDITIONS[kind].is_met(value, state, self._start_count) for kind, value in step.conditions
        )
        if met and not self._asking and step.label not in self._declined:
            self._asking = True
            if self._index + 1 < len(self._steps):
                question = f"다음 단계({self._steps[self._index + 1].name})로 갈까요?"
            else:
                question = "연습 과정을 마칠까요?"
            return [Ask(step.label, f"'{step.name}' 단계를 끝낸 것 같아요. {question}")]
        if not met and self._asking:
            self._asking = False
            return [Withdraw(step.label)]
        return []

    def on_answer(self, yes: bool) -> list[Command]:
        """띄운 물음에 [네]/[아니요]로 답했을 때. 답한 물음은 창이 스스로 닫는다."""
        if not self._asking:
            return []
        self._asking = False
        if yes:
            self._finish()
            self._go_to(self._index + 1)
        else:
            self._declined.add(self.step.label)
        return []

    def next_step(self) -> list[Command]:
        """'다음 단계' 버튼. 끝난 조건과 상관없이 언제나 넘어간다(마지막 단계에서는 연습 과정을 마침)."""
        self._finish()
        return self._go_to(min(self._index + 1, len(self._steps)))

    def skip_to(self, label: str) -> list[Command]:
        """원하는 단계로 건너뛰기. 없는 이름표면 ValueError."""
        return self._go_to([step.label for step in self._steps].index(label))

    def back(self) -> list[Command]:
        """앞 단계로 가기. 첫 단계에서는 그대로 머문다."""
        return self._go_to(max(self._index - 1, 0))

    def close(self) -> list[Command]:
        """이 진행을 그만둘 때(다른 연습 과정·다른 파일로 바뀜). 떠 있던 물음을 거둔다."""
        if not self._asking:
            return []
        self._asking = False
        return [Withdraw(self._steps[self._index].label)]

    def _finish(self) -> None:
        """지금 단계를 끝낸 단계에 넣는다."""
        if self.step is not None and self.step.label not in self._finished:
            self._finished.append(self.step.label)

    def _go_to(self, index: int) -> list[Command]:
        """지금 단계를 바꾸고, 그 순간의 장면 물체 수를 단계 시작 때 수로 기억한다. 떠 있던 물음은 거둔다."""
        commands = self.close()
        self._index = index
        self._start_count = self._latest.scene_object_count if self._latest else None
        return commands
