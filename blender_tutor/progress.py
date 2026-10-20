"""진행 관리: 작업 상태와 사용자 응답을 사건으로 받아, 띄울 물음·거둘 물음과 지금 단계를 돌려준다.

도우미 창과 떼어 둔 모듈이다(시험 경계 ②). 창을 그리거나 앞으로 끌어오는 일은 하지 않고,
돌려준 물음을 창이 자기 안에만 띄운다.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class WorkState:
    """애드온이 보낸 작업 상태 가운데 끝난 조건 판정에 쓰는 칸."""

    mode: str  # Blender context.mode 값(예: OBJECT, EDIT_MESH)
    recent_operators: tuple[str, ...]  # 방금 실행한 조작 3개, 'mesh.merge' 꼴
    scene_object_count: int  # 장면 물체 수
    modifiers: tuple[str, ...]  # 활성 물체의 모디파이어 종류(예: BEVEL)
    material_slot_count: int  # 활성 물체의 재질 슬롯 수
    scale: tuple[float, float, float]  # 활성 물체 배율
    dimensions: tuple[float, float, float]  # 활성 물체 크기


@dataclass(frozen=True)
class Step:
    """연습 과정의 단계 하나에서 진행 관리가 쓰는 것."""

    label: str  # 이름표(예: blade-tip)
    name: str  # 화면에 보이는 이름
    conditions: tuple[tuple[str, object], ...] = ()  # 끝난 조건 (종류, 값) 목록. 비면 버튼으로만 넘어간다


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
    data = yaml.safe_load(course.read_text(encoding="utf-8"))
    steps = load_steps(course.parent / data["먼저 할 것"]) if "먼저 할 것" in data else []
    for section in data["구간"]:
        for step in section["단계"]:
            conditions = tuple(next(iter(c.items())) for c in step.get("끝난 조건", []))
            steps.append(Step(step["이름표"], step["이름"], conditions))
    return steps


def _is_met(kind: str, value: object, state: WorkState, start_count: int) -> bool:
    """끝난 조건 하나가 맞는지 본다(AI 없이 정해 둔 규칙으로). start_count는 단계 시작 때 장면 물체 수."""
    if kind == "모드":
        return state.mode == value
    if kind == "방금 조작":
        return value in state.recent_operators
    if kind == "물체 수 늘어남":
        return state.scene_object_count >= start_count + value
    if kind == "모디파이어":
        return value in state.modifiers
    if kind == "재질 슬롯 수":
        return state.material_slot_count == value
    if kind == "배율":
        # Blender가 계산한 소수라 0.9999999처럼 아주 작은 차이는 같다고 본다.
        return all(math.isclose(have, want, rel_tol=1e-3, abs_tol=1e-3) for have, want in zip(state.scale, value))
    if kind == "크기 비율":
        # 치수는 절대 숫자가 아니라 비율로만 본다: 가장 긴 축 ≥ 두 번째로 긴 축 × n.
        longest, second, _ = sorted(state.dimensions, reverse=True)
        return longest > 0 and longest >= second * value
    raise ValueError(f"모르는 끝난 조건 종류: {kind}")


class Progress:
    """한 연습 과정의 진행. 사건 함수마다 창이 할 일(물음 띄우기·거두기) 목록을 돌려준다."""

    def __init__(self, steps: list[Step]):
        self._steps = steps
        self._index = 0
        self._asking = False  # 물음을 띄워 두고 답을 기다리는 중
        self._declined: set[str] = set()  # 물음을 거절한 단계 이름표. 이 단계들은 다시 묻지 않는다
        self._latest: WorkState | None = None  # 마지막으로 받은 작업 상태
        self._start_count: int | None = None  # 지금 단계를 시작할 때 장면 물체 수(모르면 다음 상태에서 정함)

    @property
    def step(self) -> Step | None:
        """지금 단계. 연습 과정을 마쳤으면 None."""
        return self._steps[self._index] if self._index < len(self._steps) else None

    def on_state(self, state: WorkState) -> list[Command]:
        """작업 상태가 도착했을 때."""
        self._latest = state
        if self._start_count is None:
            self._start_count = state.scene_object_count
        step = self.step
        if step is None:
            return []
        met = bool(step.conditions) and all(
            _is_met(kind, value, state, self._start_count) for kind, value in step.conditions
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
            self._go_to(self._index + 1)
        else:
            self._declined.add(self.step.label)
        return []

    def next_step(self) -> list[Command]:
        """'다음 단계' 버튼. 끝난 조건과 상관없이 언제나 넘어간다(마지막 단계에서는 연습 과정을 마침)."""
        return self._go_to(min(self._index + 1, len(self._steps)))

    def skip_to(self, label: str) -> list[Command]:
        """원하는 단계로 건너뛰기. 없는 이름표면 ValueError."""
        return self._go_to([step.label for step in self._steps].index(label))

    def back(self) -> list[Command]:
        """앞 단계로 가기. 첫 단계에서는 그대로 머문다."""
        return self._go_to(max(self._index - 1, 0))

    def _go_to(self, index: int) -> list[Command]:
        """지금 단계를 바꾸고, 그 순간의 장면 물체 수를 단계 시작 때 수로 기억한다. 떠 있던 물음은 거둔다."""
        commands: list[Command] = []
        if self._asking:
            self._asking = False
            commands.append(Withdraw(self._steps[self._index].label))
        self._index = index
        self._start_count = self._latest.scene_object_count if self._latest else None
        return commands
