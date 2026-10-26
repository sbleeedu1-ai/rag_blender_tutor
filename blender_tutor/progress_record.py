"""진행 기록과 이어 하기: 연습 과정 고르기와 파일 열림·저장을 받아 진행 기록을 남기고 이어 할지 묻는다.

한 연습 과정 안의 진행(끝난 조건 판정, 다음 단계 물음)은 progress.Progress가 맡고, 이 모듈은 그 위에서
어느 연습 과정을 어느 파일에서 하는지와 진행 기록을 맡는다. 도우미 창은 course_desk를 거쳐 Blender 창마다
하나씩 만든 이 모듈의 ProgressManager에 사건을 넘긴다.
진행 기록은 열린 파일 경로마다 작은 JSON 하나이고(사용자 설정 폴더, 저장소 밖), 지우지 않는다.
단계 옮기기와 끝낸 단계는 사용자가 확인한 변화([네], 다음·뒤로 버튼, '단계' 목록, 연습 과정 고르기·바꾸기)만 기록에 쓴다.
단계 안 몇 번째 조작인지는 감지·다음·뒤로로 바뀔 때마다 쓴다(티켓 27).
Blender에서 저장할 때마다 그때의 자리도 "저장 때"로 따로 쓴다. 다시 열 때 기록이 저장 때와 다르면(저장 뒤 진행했는데
저장하지 않고 닫음) 그 진행이 파일에도 있는지 사람에게 물어 어느 자리로 갈지 정한다.
한 Blender 창에서 다른 파일을 열면 지금 진행을 비운다(앞 파일의 진행은 그 파일 기록에 남아 있다).
파일 열림·저장은 애드온이 Blender의 알림 함수(load_post·save_post)로 알아채 사건으로 보낸다(티켓 25).
경로만 바뀌고 사건이 오지 않으면 아무것도 하지 않는다(열기와 다른 이름 저장을 경로로는 가를 수 없어서).
"""

import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blender_tutor.korean_particles import with_euro
from blender_tutor.work_state import WorkState
from blender_tutor.progress import Ask, Command, Course, Operation, Progress, Step, Withdraw

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AskResume:
    """파일을 열었을 때 띄울 "이어 할까요" 물음. 저장 뒤 진행이 파일에도 있는지 묻는 물음도 이것으로 띄운다."""

    text: str


@dataclass(frozen=True)
class AskChangeCourse:
    """진행 중인 연습 과정을 다른 것으로 바꾸기 전에 띄울 확인 물음."""

    text: str


@dataclass(frozen=True)
class Notice:
    """창에 한 줄 알림."""

    text: str


# 창이 할 일: 한 연습 과정 안의 물음·거둠(progress.Command)에 이어 하기·바꾸기 물음과 알림을 더한 것.
ManagerCommand = Command | AskResume | AskChangeCourse | Notice


def _finished_notice(course: Course) -> Notice:
    """다 마친 연습 과정의 파일을 열었을 때 알림."""
    return Notice(f"이 파일에서 {course.name} 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")


def _place_key(record: dict) -> tuple:
    """기록 칸에서 자리를 꺼낸다: (연습 과정, 현재 단계, 끝낸 단계, 끝낸 조작 수, 조작 수). 조작 칸이 없는 기록은 첫 조작."""
    return (
        record["연습 과정"], record["현재 단계"], tuple(record["끝낸 단계"]),
        record.get("끝낸 조작 수", 0), record.get("조작 수", 0),
    )


def _record_path(record_dir: Path, blend: str) -> Path:
    """파일 경로마다 기록 파일 하나. 이름은 경로의 해시라 경로에 어떤 글자가 있어도 된다."""
    key = os.path.normcase(os.path.abspath(blend))
    return record_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]}.json"


@dataclass(frozen=True)
class _Resume:
    """진행 기록에서 읽은 이어 할 자리."""

    course: Course
    index: int  # 이어 할 단계 번호(0부터). 단계 수와 같으면 마친 상태
    finished: tuple[str, ...]
    moved: bool  # 기록의 단계가 사라져 끝내지 않은 첫 단계로 옮겼는가
    operations_done: int = 0  # 그 단계에서 끝낸 조작 수(이어 할 조작의 번호)

    def where(self, with_course: bool = False) -> str:
        """'2단계(칼끝 모으기) 3번째 조작'처럼 화면에 보일 자리. 단계 번호는 파일 순서로 센다."""
        prefix = f"{self.course.name} " if with_course else ""
        if self.index == len(self.course.steps):
            return f"{prefix}다 마친 상태"
        step = self.course.steps[self.index]
        done = self.operations_done
        tail = "" if not done else " 모든 조작" if done == len(step.operations) else f" {done + 1}번째 조작"
        return f"{prefix}{self.index + 1}단계({step.name}){tail}"


class ProgressManager:
    """진행 관리 전체. 사건 함수마다 창이 할 일 목록을 돌려주고 진행 기록을 쓴다.

    단계 옮기기·끝낸 단계는 사용자가 확인한 변화만, 끝낸 조작 수는 바뀔 때마다 쓴다(맨 위 설명 참고).
    """

    def __init__(self, courses: list[Course], record_dir: Path, now: Callable[[], datetime] = datetime.now):
        self._courses = {course.label: course for course in courses}
        self._record_dir = record_dir
        self._now = now
        self._course: Course | None = None
        self._progress: Progress | None = None
        self._path: str | None = None  # 열린 파일 경로. 저장 전이면 None(진행은 메모리에만)
        self._resume: _Resume | None = None  # 이어 할까요 물음에 답을 기다리는 중
        self._fallback: _Resume | None = None  # 저장 뒤 진행이 파일에 있나 물음에 [아니요]면 갈 저장 때 자리
        self._on_file: _Resume | None = None  # 연 파일의 기록 자리. 진행을 되살리기 전에 고르면 덮어쓸지 묻는 데 쓴다
        self._saved: dict | None = None  # 열린 파일 기록의 "저장 때" 칸(기록을 다시 쓸 때 그대로 남긴다)
        self._changed_at: str | None = None  # 진행이 마지막으로 바뀐 시각(저장만 해서는 바뀌지 않는다)
        self._change: Course | None = None  # 바꿀까요 물음을 띄우고 기다리는, 새로 고른 연습 과정
        self._state: WorkState | None = None  # 마지막으로 받은 작업 상태(진행을 새로 만들 때 넘긴다)
        # 답을 기다리는 물음 글. 바꿀까요 > 이어 할까요 > 다음 단계로 갈까요 차례로 위에 보인다(prompt)
        self._change_text: str | None = None
        self._resume_text: str | None = None
        self._ask_text: str | None = None

    @property
    def course(self) -> Course | None:
        """지금 연습 과정. 고르지 않았으면 None."""
        return self._course

    @property
    def step(self) -> Step | None:
        """지금 단계. 연습 과정을 고르지 않았거나 마쳤으면 None."""
        return self._progress.step if self._progress else None

    @property
    def prompt(self) -> str | None:
        """지금 [네]/[아니요]로 답을 기다리는 물음 글. 없으면 None. 창은 이것만 띄운다."""
        return self._change_text or self._resume_text or self._ask_text

    def answer(self, yes: bool) -> list[ManagerCommand]:
        """지금 보이는 물음(prompt)에 [네]/[아니요]. 어느 물음의 답인지는 여기서 가린다. 물음이 없으면 무시한다."""
        if self._change_text is not None:
            return self.on_change_answer(yes)
        if self._resume_text is not None:
            return self.on_resume_answer(yes)
        if self._ask_text is not None:
            return self.on_answer(yes)
        return []

    @property
    def number(self) -> int:
        """지금 단계가 몇 번째인지(화면의 'n단계', 파일 순서로 1부터). 고르지 않았거나 마쳤으면 0."""
        return self._progress.number if self._progress else 0

    @property
    def operation(self) -> Operation | None:
        """지금 안내 중인 조작. 연습 과정을 고르지 않았거나 이 단계 조작을 다 끝냈으면 None."""
        return self._progress.operation if self._progress else None

    @property
    def operations_done(self) -> int:
        """지금 단계에서 끝낸 조작 수. 연습 과정을 고르지 않았으면 0."""
        return self._progress.operations_done if self._progress else 0

    def choose_course(self, label: str) -> list[ManagerCommand]:
        """연습 과정 고르기. 다른 연습 과정을 하던 중이면 바로 바꾸지 않고 확인을 묻는다.

        연 파일에 기록이 있는데 아직 진행을 되살리지 않았으면(이어 하기 물음 중·거절 뒤·다 마친 기록) 그 기록을
        덮어쓰게 되므로 역시 확인을 묻는다. [아니요]면 떠 있던 이어 하기 물음으로 돌아간다.
        이어 하기 물음의 [아니요]로 치지 않는다: 저장 뒤 진행 물음에서는 [아니요]가 저장 때 자리로 가기라서.
        """
        course = self._courses[label]
        if self._course is None and self._on_file is None:
            return self._track(self._start(course))
        if self._course is None:
            self._change = course
            record = self._on_file
            place = "다 마침" if record.index == len(record.course.steps) else f"{record.index + 1}단계"
            return self._track([AskChangeCourse(
                f"이 파일의 진행 기록({record.course.name}, {place})이 {with_euro(course.name)} 처음부터 바뀌어요. "
                "새 파일에서 시작하면 둘 다 남아요. 바꿀까요?"
            )])
        if course == self._course:
            return []
        self._change = course
        now, to = f"{self._course.name}, {self._where()}", with_euro(course.name)
        if self._path is None:
            return self._track([AskChangeCourse(f"지금 진행({now})은 저장 전 파일이라 남지 않아요. {to} 바꿀까요?")])
        return self._track([AskChangeCourse(f"이 파일의 진행 기록({now})이 {to} 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?")])

    def on_change_answer(self, yes: bool) -> list[ManagerCommand]:
        """바꿀까요 물음에 답했을 때. 물음이 없으면(늦게 온 답) 무시한다."""
        course, self._change, self._change_text = self._change, None, None
        return self._track(self._start(course)) if yes and course is not None else []

    def on_file_opened(self, path: str) -> list[ManagerCommand]:
        """파일을 열었을 때. 지금 진행을 비우고, 그 파일의 진행 기록이 있으면 이어 할지 한 번 묻는다.

        경로가 비었으면(Blender를 켤 때·File > New) 저장 전 새 파일이다.
        """
        return self._track(self._open(path))

    def _open(self, path: str) -> list[ManagerCommand]:
        commands = self._leave()
        self._path = path or None
        resume, saved = self._read(path) if path else (None, None)
        if resume is None:
            return commands
        self._on_file = resume
        if saved is not None:  # 저장 뒤 진행이 더 있다: 파일에도 그만큼 되어 있는지 묻는다
            self._resume, self._fallback = resume, saved
            with_course = resume.course != saved.course
            was = "이었는데" if saved.operations_done and saved.index < len(saved.course.steps) else "였는데"  # 조작이었는데 / 단계(…)였는데
            return commands + [AskResume(
                f"저장한 때는 {saved.where(with_course)}{was}, 그 뒤 {resume.where(with_course)}까지 진행하신 것 같아요. "
                "파일에도 그만큼 되어 있나요?"
            )]
        course, index = resume.course, resume.index
        if index == len(course.steps):
            return commands + [_finished_notice(course)]
        self._resume = resume
        if resume.moved:
            return commands + [AskResume(f"지난번 하던 단계가 연습 과정에서 빠졌어요. 끝내지 않은 첫 단계인 {resume.where()}부터 이어 할까요?")]
        if resume.operations_done and resume.operations_done == len(course.steps[index].operations):
            return commands + [AskResume(f"지난번 {index + 1}단계({course.steps[index].name}) 조작을 다 했어요. 이어 할까요?")]
        if resume.operations_done:
            return commands + [AskResume(f"지난번 {resume.where()}을 하던 중이었어요. 이어 할까요?")]
        return commands + [AskResume(f"지난번 {resume.where()}까지 했어요. 이어 할까요?")]

    def on_resume_answer(self, yes: bool) -> list[ManagerCommand]:
        """이어 할까요 물음에 답했을 때. 거절하면 연습 과정을 새로 고르게 두고, 기록은 지우지 않는다.

        저장 뒤 진행이 파일에 있나 물음이었으면 [네]는 기록대로, [아니요]는 저장한 때 자리로 간다(그 자리를 기록에 다시 쓴다).
        """
        resume, fallback = self._resume, self._fallback
        self._resume = self._fallback = self._resume_text = None
        if resume is None:
            return []
        if fallback is not None and not yes:
            resume = fallback
        elif not yes:
            return []
        self._course = resume.course
        self._progress = Progress(resume.course.steps, resume.index, resume.finished, resume.operations_done, self._state)
        if resume is fallback:
            self._save()  # 사용자가 고른 자리라 기록한다. 기록대로 갈 때는 있던 그대로라 다시 쓰지 않는다
        if resume.index == len(resume.course.steps):
            # 다 마친 자리면 다 마친 파일을 열 때와 같게: 알리고 진행은 되살리지 않는다(고르면 덮어쓸지 묻는다)
            self._course = self._progress = None
            self._on_file = resume
            return [_finished_notice(resume.course)]
        if resume.moved:
            return [Notice(f"연습 과정이 고쳐져 지난번 단계를 찾지 못해, 끝내지 않은 첫 단계({self.step.name})로 왔어요.")]
        return []

    def on_file_saved(self, path: str) -> list[ManagerCommand]:
        """파일을 저장했을 때. 처음 저장이면 메모리의 진행을 붙이고, 다른 이름으로 저장이면 새 경로로 복사한다.

        저장할 때마다 그때의 자리(끝낸 조작 수까지)를 "저장 때"로 쓴다.
        """
        self._path = path
        if self._course is not None:
            self._saved = {**self._place_record(), "시각": self._now().isoformat(timespec="seconds")}
            self._save(changed=False)
        return []

    def next_operation(self) -> list[ManagerCommand]:
        """다음 조작으로 가고 기록한다."""
        return self._recorded(lambda progress: progress.next_operation())

    # 아래는 한 연습 과정 안의 사건. Progress에 넘기고, 단계·끝낸 단계·끝낸 조작 수가 바뀌었으면 기록한다.
    # 연습 과정을 고르기 전(이어 할까요 답을 기다리는 동안 포함)에는 아무것도 하지 않는다.

    def on_state(self, state: WorkState) -> list[ManagerCommand]:
        """작업 상태가 도착했을 때."""
        self._state = state
        return self._recorded(lambda progress: progress.on_state(state))

    def on_answer(self, yes: bool) -> list[ManagerCommand]:
        """다음 단계로 갈까요 물음에 답했을 때. 답한 물음은 닫는다."""
        self._ask_text = None
        return self._recorded(lambda progress: progress.on_answer(yes))

    def next_step(self) -> list[ManagerCommand]:
        """다음 단계로(조작이 남아 있어도)."""
        return self._recorded(lambda progress: progress.next_step())

    def forward(self) -> list[ManagerCommand]:
        """'다음' 버튼: 조작이 남았으면 다음 조작, 다 끝냈으면 다음 단계."""
        return self._recorded(lambda progress: progress.forward())

    def skip_to(self, label: str) -> list[ManagerCommand]:
        """'단계' 목록에서 고른 단계로 건너뛰기."""
        return self._recorded(lambda progress: progress.skip_to(label))

    def back(self) -> list[ManagerCommand]:
        """'뒤로' 버튼: 앞 조작, 첫 조작에서는 앞 단계의 다 끝낸 자리."""
        return self._recorded(lambda progress: progress.back())

    def _recorded(self, event: Callable[[Progress], list[Command]]) -> list[ManagerCommand]:
        """지금 진행에 사건을 넘기고, 지금 단계·끝낸 단계·끝낸 조작 수가 바뀌었으면 기록한다."""
        if self._progress is None:
            return []
        before = (self._progress.step, self._progress.finished, self._progress.operations_done)
        commands = event(self._progress)
        if (self._progress.step, self._progress.finished, self._progress.operations_done) != before:
            self._save()
        return self._track(commands)

    def _track(self, commands: list[ManagerCommand]) -> list[ManagerCommand]:
        """돌려줄 할 일에서 띄운 물음·거둔 물음을 보고 지금 답을 기다리는 물음 글을 맞춘다."""
        for command in commands:
            if isinstance(command, Ask):
                self._ask_text = command.text
            elif isinstance(command, Withdraw):
                self._ask_text = None
            elif isinstance(command, AskResume):
                self._resume_text = command.text
            elif isinstance(command, AskChangeCourse):
                self._change_text = command.text
        return commands

    def _start(self, course: Course) -> list[ManagerCommand]:
        """연습 과정을 첫 단계부터 시작해 기록한다. 앞 진행에 떠 있던 물음은 거두고, 기다리던 이어 하기 물음은 버린다."""
        commands = self._progress.close() if self._progress else []
        self._resume = self._fallback = self._resume_text = self._on_file = None
        self._course = course
        self._progress = Progress(course.steps, latest=self._state)
        self._save()
        return commands

    def _leave(self) -> list[ManagerCommand]:
        """지금 진행을 비운다(다른 파일을 열 때). 답을 기다리던 물음은 버리고, 떠 있던 물음은 거둔다."""
        commands = self._progress.close() if self._progress else []
        self._course = self._progress = self._resume = self._fallback = self._change = self._saved = self._on_file = None
        self._changed_at = None
        self._resume_text = self._change_text = None
        return commands

    def _where(self) -> str:
        """지금 단계를 화면에 보일 'n단계'(파일 순서로 셈)로. 마쳤으면 '마침'."""
        return f"{self._progress.number}단계" if self._progress.step else "마침"

    def _read(self, path: str) -> tuple[_Resume | None, _Resume | None]:
        """그 파일의 진행 기록을 읽어 (이어 할 자리, 저장 때와 다를 때만 저장 때 자리)로.

        기록이 없거나 깨졌거나 연습 과정이 없어졌으면 (None, None).
        """
        record_path = _record_path(self._record_dir, path)
        if not record_path.exists():
            return None, None
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            saved = record.get("저장 때")
            now, then = _place_key(record), _place_key(saved) if saved else None
        except (ValueError, KeyError, TypeError):
            return None, None  # 깨진 기록은 없는 것으로 본다(지우지는 않는다)
        resume = self._place(*now)
        if resume is None:
            return None, None
        self._saved, self._changed_at = saved, record.get("바뀐 시각")
        if then is None or then == now:  # 저장 때 자리가 없는 예전 기록이거나, 저장 뒤 바뀐 것이 없다
            return resume, None
        return resume, self._place(*then)

    def _place(
        self, label: str, current: str | None, finished: tuple[str, ...], operations_done: int = 0, operation_count: int = 0
    ) -> _Resume | None:
        """기록의 이름표를 지금 연습 과정 파일의 자리로. 연습 과정이 없어졌으면 None.

        단계가 사라졌으면 끝내지 않은 첫 단계로, 그 단계의 조작 수가 기록 때와 다르면 첫 조작으로 간다(조작에는 이름표가 없어서).
        """
        course = self._courses.get(label)
        if course is None:
            return None
        labels = [step.label for step in course.steps]
        if current is None:
            return _Resume(course, len(labels), finished, moved=False)
        if current in labels:
            index = labels.index(current)
            operations_done = operations_done if len(course.steps[index].operations) == operation_count else 0
            return _Resume(course, index, finished, moved=False, operations_done=operations_done)
        first_unfinished = next((i for i, label in enumerate(labels) if label not in finished), len(labels))
        return _Resume(course, first_unfinished, finished, moved=True)

    def _place_record(self) -> dict:
        """지금 자리를 기록 칸으로. 늘 쓰는 기록과 "저장 때"가 같은 칸을 쓴다."""
        step = self._progress.step
        return {
            "연습 과정": self._course.label,
            "현재 단계": step.label if step else None,
            "끝낸 조작 수": self._progress.operations_done,
            "조작 수": len(step.operations) if step else 0,  # 연습 과정이 고쳐져 조작 수가 바뀌면 끝낸 조작 수를 믿지 않는다
            "끝낸 단계": list(self._progress.finished),
        }

    def _save(self, changed: bool = True) -> None:
        """지금 진행을 열린 파일의 진행 기록에 쓴다. 저장 전 파일이면 메모리에만 둔다.

        changed는 진행이 바뀌어 쓰는가(바뀐 시각을 새로 씀). Blender 저장으로 "저장 때"만 새로 쓸 때는 False.
        """
        if changed or self._changed_at is None:
            self._changed_at = self._now().isoformat(timespec="seconds")
        if self._path is None or self._course is None:
            return
        record = {"파일": self._path, **self._place_record(), "바뀐 시각": self._changed_at}
        if self._saved is not None:
            record["저장 때"] = self._saved
        try:
            self._record_dir.mkdir(parents=True, exist_ok=True)
            _record_path(self._record_dir, self._path).write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:  # 기록 폴더에 쓸 수 없음(paths.progress_records가 고를 곳이 없었음): 진행은 메모리에서 계속한다
            log.exception("진행 기록을 쓰지 못함: %s", self._record_dir)
