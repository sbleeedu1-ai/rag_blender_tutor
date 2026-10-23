"""진행 관리: 작업 상태와 사용자 응답을 사건으로 받아, 띄울 물음·거둘 물음과 지금 단계를 돌려준다.

도우미 창과 떼어 둔 모듈이다(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).
창을 그리거나 앞으로 끌어오는 일은 하지 않고, 돌려준 물음을 창이 자기 안에만 띄운다.
단계 안의 조작은 파일 순서대로 하나씩 안내하고, 감지 조건이 맞거나 [했어요]를 받으면 다음 조작으로 간다(티켓 27).
끝난 조건·감지 조건의 판정 규칙은 conditions.py에 있다.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from blender_tutor.conditions import CONDITIONS
from blender_tutor.work_state import WorkState


@dataclass(frozen=True)
class Operation:
    """단계의 조작 하나: 한 줄 설명, 영어 메뉴 경로(없으면 "없음"), 단축키, 도우미가 대화에 띄울 안내 말, 감지 조건.

    도우미는 한 단계 안에서 조작을 파일 순서대로 하나씩 안내하고, 감지 조건이 맞거나 [했어요]를 누르면 다음 조작으로 간다.
    """

    description: str
    menu: str
    keys: str
    say: str = ""  # 안내 말(선생님 말투, 연습 과정 파일에 미리 써 둠)
    detect: tuple[tuple[str, object], ...] = ()  # 감지 조건 (종류, 값). 끝난 조건과 같은 종류. 비면 [했어요]로만 넘어간다


@dataclass(frozen=True)
class Step:
    """연습 과정의 단계 하나에서 진행 관리가 쓰는 것."""

    label: str  # 이름표(예: blade-tip)
    name: str  # 화면에 보이는 이름
    conditions: tuple[tuple[str, object], ...] = ()  # 끝난 조건 (종류, 값) 목록. 비면 버튼으로만 넘어간다
    manual: tuple[str, ...] = ()  # 먼저 볼 설명서 소제목 주소(경로.html#앵커). 답 엔진이 검색어와 검색 결과 위에 붙인다
    guide: str = ""  # 답변 모델에 넘길 이 단계 내용 글(연습 과정 파일 전체가 아니라 이 단계만)
    operations: tuple[Operation, ...] = ()  # 도우미가 대화에 하나씩 안내할 조작(파일 순서)


@dataclass(frozen=True)
class Course:
    """연습 과정 하나: 이름표, 화면에 보이는 이름, 공통 준비부터 파일 순서대로 늘어놓은 단계."""

    label: str
    name: str
    steps: tuple[Step, ...]
    summary: str = ""  # 한 줄 설명. 답 엔진이 비슷한 연습 과정을 권할 때 이름과 함께 넘긴다


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
    return Course(data["이름표"], data["이름"], tuple(_steps_of(data, course.parent)), data.get("한 줄 설명", ""))


def load_courses(folder: Path) -> list[Course]:
    """연습 과정 폴더(courses/)의 연습 과정을 파일 이름 차례로 읽는다. '_'로 시작하는 공통 준비 파일은 뺀다.

    '_'로 공통 준비를 알아보는 규칙은 연습 과정 파일 검사의 _is_common(course_check.py)과 같다. 바꾸면 둘 다 고친다.
    """
    return [load_course(path) for path in sorted(folder.glob("*.yaml")) if not path.name.startswith("_")]


def _steps_of(data: dict, folder: Path) -> list[Step]:
    """읽어 둔 연습 과정 파일 내용에서 단계를 꺼낸다. '먼저 할 것'은 같은 폴더에서 찾는다."""
    steps = load_steps(folder / data["먼저 할 것"]) if "먼저 할 것" in data else []
    for section in data["구간"]:
        for step in section["단계"]:
            conditions = _conditions(step.get("끝난 조건", []))
            manual = tuple(step.get("먼저 볼 소제목", []))
            operations = tuple(
                Operation(o["설명"], o["메뉴"], o["단축키"], o.get("안내", ""), _conditions(o.get("감지", [])))
                for o in step.get("조작", [])
            )
            steps.append(Step(step["이름표"], step["이름"], conditions, manual, _guide(step), operations))
    return steps


def _conditions(items: list[dict]) -> tuple[tuple[str, object], ...]:
    """'종류: 값' 한 줄씩 적힌 조건 목록을 (종류, 값) 묶음으로."""
    return tuple(next(iter(item.items())) for item in items)


def _guide(step: dict) -> str:
    """답변 모델에 넘길 단계 내용 글. 사람이 읽는 칸만(이름표·먼저 볼 소제목·끝난 조건은 뺀다)."""
    lines = [f"{key}: {step[key]}" for key in ("이름", "목표 모양", "참고 치수", "쉬운 설명") if key in step]
    if step.get("조작"):
        lines.append("조작:")
        lines += [f"- {o['설명']} (메뉴: {o['메뉴']}, 단축키: {o['단축키']})" for o in step["조작"]]
    if step.get("자주 막히는 곳"):
        lines.append("자주 막히는 곳:")
        lines += [f"- {tip}" for tip in step["자주 막히는 곳"]]
    return "\n".join(lines)


# 이 조작이 진행 중이면(확정 전) 감지·단계 끝 물음을 기다린다. Blender는 S·G·화면 끌기 동안 배율·위치·시점을
# 마우스대로 바로 바꿔 보여서, 확정 전 값으로 넘어가 버리기 때문이다(2026-10-23 사용자 눈 확인에서 찾음).
# 다른 애드온이 늘 켜 두는 조작 때문에 계속 기다리지 않게 이름 앞부분으로 좁힌다.
WAIT_WHILE_RUNNING = ("transform.", "view3d.")


class Progress:
    """한 연습 과정의 진행. 사건 함수마다 창이 할 일(물음 띄우기·거두기) 목록을 돌려준다."""

    def __init__(
        self,
        steps: Sequence[Step],
        start: int = 0,
        finished: tuple[str, ...] = (),
        operations_done: int = 0,
        latest: WorkState | None = None,
    ):
        """이어 할 때는 시작할 단계 번호(0부터, 단계 수와 같으면 마친 상태)와 끝낸 단계 이름표, 그 단계에서 끝낸 조작 수를 받는다.

        latest는 진행을 만들기 전에 받아 둔 작업 상태다. 주면 그때를 단계 시작·조작 안내 시작으로 삼아,
        고른 뒤 처음 온 변화(사용자의 첫 조작)도 감지한다.
        """
        self._steps = list(steps)
        self._index = start
        self._finished = list(finished)  # 사용자가 [네]나 '다음 단계' 버튼으로 끝낸 단계 이름표. 건너뛴 단계는 넣지 않는다
        self._asking = False  # 물음을 띄워 두고 답을 기다리는 중
        self._declined: set[str] = set()  # 물음을 거절한 단계 이름표. 이 단계들은 다시 묻지 않는다
        self._latest = latest  # 마지막으로 받은 작업 상태
        self._step_started_at = latest  # 지금 단계를 시작할 때의 작업 상태, 끝난 조건의 기준(모르면 다음 상태에서 정함)
        self._operations_done = operations_done  # 이 단계에서 끝낸 조작 수(0부터 조작 수까지). 다음에 안내할 조작의 번호이기도 하다
        self._operation_started_at = latest  # 지금 조작을 안내하기 시작할 때의 작업 상태(모르면 다음 상태에서 정함)

    @property
    def step(self) -> Step | None:
        """지금 단계. 연습 과정을 마쳤으면 None."""
        return self._steps[self._index] if self._index < len(self._steps) else None

    @property
    def number(self) -> int:
        """지금 단계가 몇 번째인지(화면의 'n단계', 공통 준비부터 파일 순서로 1부터). 마쳤으면 0."""
        return self._index + 1 if self.step else 0

    @property
    def operations_done(self) -> int:
        """지금 단계에서 끝낸 조작 수. 조작 수와 같으면 이 단계 조작을 다 끝냈다."""
        return self._operations_done

    @property
    def operation(self) -> Operation | None:
        """지금 안내 중인 조작. 연습 과정을 마쳤거나 이 단계 조작을 다 끝냈으면 None."""
        step = self.step
        return step.operations[self._operations_done] if step and self._operations_done < len(step.operations) else None

    @property
    def finished(self) -> tuple[str, ...]:
        """끝낸 단계 이름표(끝낸 차례대로). 뒤로 가도 줄지 않는다."""
        return tuple(self._finished)

    def on_state(self, state: WorkState) -> list[Command]:
        """작업 상태가 도착했을 때."""
        self._latest = state
        if self._step_started_at is None:
            self._step_started_at = state
        if self._operation_started_at is None:  # 기준은 조작 중이어도 잡는다(그 뒤 확정한 상태를 기준으로 삼으면 놓친다)
            self._operation_started_at = state
        step = self.step
        if step is None or any(name.startswith(WAIT_WHILE_RUNNING) for name in state.running_operators):
            return []
        self._detect_operation(step, state)
        return self._ask_if_done(step, state)

    def _ask_if_done(self, step: Step, state: WorkState) -> list[Command]:
        """끝난 조건이 맞으면 다음 단계로 갈지 묻고, 깨지면 거둔다. 조작 안내 중에는 보지 않는다.

        첫 조작만으로 끝난 조건이 맞는 단계가 있어서다(예: 길게 늘이기만 해도 크기 비율 3, 2026-10-23 사용자 눈 확인).
        조작을 다 끝내기 전에 넘어가고 싶으면 [다음 단계]를 누른다.
        """
        met = (
            self.operation is None
            and bool(step.conditions)
            and all(CONDITIONS[kind].is_met(value, state, self._step_started_at) for kind, value in step.conditions)
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

    def next_operation(self) -> list[Command]:
        """[했어요]·감지: 지금 조작을 끝낸 것으로 치고 다음 조작으로 간다. 조작을 다 끝냈으면 그대로."""
        if not self._advance():
            return []
        # 마지막 조작을 끝냈는데 끝난 조건이 이미 맞아 있으면 다음 작업 상태를 기다리지 않고 묻는다
        if self.operation is None and self._latest is not None:
            return self._ask_if_done(self.step, self._latest)
        return []

    def _advance(self) -> bool:
        """지금 조작을 끝낸 것으로 치고 다음 조작 안내를 시작한다. 조작을 다 끝냈으면 그대로 두고 거짓."""
        if self.operation is None:
            return False
        self._operations_done += 1
        self._operation_started_at = self._latest
        return True

    def close(self) -> list[Command]:
        """이 진행을 그만둘 때(다른 연습 과정·다른 파일로 바뀜). 떠 있던 물음을 거둔다."""
        if not self._asking:
            return []
        self._asking = False
        return [Withdraw(self._steps[self._index].label)]

    def _detect_operation(self, step: Step, state: WorkState) -> None:
        """지금 조작의 감지 조건이 맞으면 다음 조작으로. 안내를 시작한 때와 같은 상태로는 넘어가지 않는다(한 번에 하나씩)."""
        operation = self.operation
        if operation is None or state == self._operation_started_at:
            return
        if operation.detect and all(self._detected(kind, value, state) for kind, value in operation.detect):
            self._advance()  # 단계 끝 물음은 on_state가 이어서 본다

    def _detected(self, kind: str, value: object, state: WorkState) -> bool:
        """감지 조건 하나. '방금 조작'은 안내를 시작한 뒤 새로 한 조작이 그것일 때만 맞는다.

        조작 기록은 최근 3개라 앞 조작을 안내할 때 한 같은 조작이 남아 있을 수 있어서다.
        """
        if kind == "방금 조작":
            operators = state.recent_operators
            return operators != self._operation_started_at.recent_operators and bool(operators) and operators[-1] == value
        return CONDITIONS[kind].is_met(value, state, self._operation_started_at)

    def _finish(self) -> None:
        """지금 단계를 끝낸 단계에 넣는다."""
        if self.step is not None and self.step.label not in self._finished:
            self._finished.append(self.step.label)

    def _go_to(self, index: int) -> list[Command]:
        """지금 단계를 바꾸고, 그 순간의 작업 상태를 끝난 조건의 기준으로 기억한다. 떠 있던 물음은 거두고 조작 안내는 첫 조작부터."""
        commands = self.close()
        self._index = index
        self._step_started_at = self._latest
        self._operations_done, self._operation_started_at = 0, self._latest
        return commands
