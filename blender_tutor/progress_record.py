"""진행 기록과 이어 하기: 연습 과정 고르기와 파일 열림·저장을 받아 진행 기록을 남기고 이어 할지 묻는다.

한 연습 과정 안의 진행(끝난 조건 판정, 다음 단계 물음)은 progress.Progress가 맡고, 이 모듈은 그 위에서
어느 연습 과정을 어느 파일에서 하는지와 진행 기록을 맡는다. 창은 이 모듈의 사건 함수만 부른다.
진행 기록은 열린 파일 경로마다 작은 JSON 하나이고(사용자 설정 폴더, 저장소 밖), 지우지 않는다.
사용자가 확인한 변화([네], 버튼, 건너뛰기·뒤로, 연습 과정 고르기·바꾸기)만 기록에 쓴다.
Blender에서 저장할 때마다 그때의 자리(단계, 몇 번째 조작, 끝낸 단계)도 "저장 때"로 함께 쓴다(티켓 27).
조작 안내 자리는 저장할 때만 남는다(저장 안 한 Blender 파일과 어긋나지 않게).
다시 열 때 기록이 저장 때보다 앞서 있으면, 저장 뒤 진행이 파일에도 있는지 물어 어느 자리로 갈지 정한다.
도우미 창 하나를 여러 파일이 함께 쓰므로, 다른 파일을 열면 지금 진행을 비운다(앞 파일의 진행은 그 파일 기록에 남아 있다).
파일 열림·저장은 애드온이 Blender의 알림 함수(load_post·save_post)로 알아채 사건으로 보낸다(티켓 25).
경로만 바뀌고 사건이 오지 않으면 아무것도 하지 않는다(열기와 다른 이름 저장을 경로로는 가를 수 없어서).
"""

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from blender_tutor.work_state import WorkState
from blender_tutor.progress import Command, Course, Progress, Step


@dataclass(frozen=True)
class AskResume:
    """파일을 열었을 때 띄울 "이어 할까요" 물음."""

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


def _final(word: str) -> int:
    """마지막 글자의 받침 번호(0이면 받침 없음, 8이면 ㄹ). 한글 음절이 아니면 받침 없음으로 본다."""
    last = ord(word[-1]) - 0xAC00
    return last % 28 if 0 <= last < 11172 else 0


def has_final(word: str) -> bool:
    """마지막 글자에 받침이 있나. '이에요/예요'처럼 받침에 따라 바뀌는 말을 고를 때 쓴다."""
    return _final(word) != 0


def _with_euro(name: str) -> str:
    """이름 뒤에 '(으)로'를 붙인다: 마지막 글자에 받침이 있으면 '으로'(검으로), 없거나 ㄹ 받침이면 '로'(방패로)."""
    return f"{name}으로" if _final(name) not in (0, 8) else f"{name}로"


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
    walk: int = 0  # 이어 할 조작 번호(0부터)

    def where(self, with_course: bool = False) -> str:
        """'2단계(칼끝 모으기) 3번째 조작'처럼 화면에 보일 자리. 단계 번호는 파일 순서로 센다."""
        prefix = f"{self.course.name} " if with_course else ""
        if self.index == len(self.course.steps):
            return f"{prefix}다 마친 상태"
        walk = f" {self.walk + 1}번째 조작" if self.walk else ""
        return f"{prefix}{self.index + 1}단계({self.course.steps[self.index].name}){walk}"


class ProgressManager:
    """진행 관리 전체. 사건 함수마다 창이 할 일 목록을 돌려주고, 사용자가 확인한 변화만 진행 기록에 쓴다."""

    def __init__(self, courses: list[Course], record_dir: Path, now: Callable[[], datetime] = datetime.now):
        self._courses = {course.label: course for course in courses}
        self._record_dir = record_dir
        self._now = now
        self._course: Course | None = None
        self._progress: Progress | None = None
        self._path: str | None = None  # 열린 파일 경로. 저장 전이면 None(진행은 메모리에만)
        self._resume: _Resume | None = None  # 이어 할까요 물음에 답을 기다리는 중
        self._fallback: _Resume | None = None  # 저장 뒤 진행이 파일에 있나 물음에 [아니요]면 갈 저장 때 자리
        self._saved: dict | None = None  # 열린 파일 기록의 "저장 때" 칸(기록을 다시 쓸 때 그대로 남긴다)
        self._change: Course | None = None  # 바꿀까요 물음을 띄우고 기다리는, 새로 고른 연습 과정
        self._state: WorkState | None = None  # 마지막으로 받은 작업 상태(진행을 새로 만들 때 넘긴다)

    @property
    def course(self) -> Course | None:
        """지금 연습 과정. 고르지 않았으면 None."""
        return self._course

    @property
    def step(self) -> Step | None:
        """지금 단계. 연습 과정을 고르지 않았거나 마쳤으면 None."""
        return self._progress.step if self._progress else None

    @property
    def walk(self) -> int:
        """지금 단계에서 안내하는 조작 번호(0부터). 연습 과정을 고르지 않았으면 0."""
        return self._progress.walk if self._progress else 0

    def choose_course(self, label: str) -> list[ManagerCommand]:
        """연습 과정 고르기. 다른 연습 과정을 하던 중이면 바로 바꾸지 않고 확인을 묻는다."""
        course = self._courses[label]
        if self._course is None:
            return self._start(course)
        if course == self._course:
            return []
        self._change = course
        now, to = f"{self._course.name}, {self._where()}", _with_euro(course.name)
        if self._path is None:
            return [AskChangeCourse(f"지금 진행({now})은 저장 전 파일이라 남지 않아요. {to} 바꿀까요?")]
        return [AskChangeCourse(f"이 파일의 진행 기록({now})이 {to} 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?")]

    def on_change_answer(self, yes: bool) -> list[ManagerCommand]:
        """바꿀까요 물음에 답했을 때. 물음이 없으면(늦게 온 답) 무시한다."""
        course, self._change = self._change, None
        return self._start(course) if yes and course is not None else []

    def on_file_opened(self, path: str) -> list[ManagerCommand]:
        """파일을 열었을 때. 지금 진행을 비우고, 그 파일의 진행 기록이 있으면 이어 할지 한 번 묻는다.

        경로가 비었으면(Blender를 켤 때·File > New) 저장 전 새 파일이다.
        """
        commands = self._leave()
        self._path = path or None
        resume, saved = self._read(path) if path else (None, None)
        if resume is None:
            return commands
        if saved is not None:  # 저장 뒤 진행이 더 있다: 파일에도 그만큼 되어 있는지 묻는다
            self._resume, self._fallback = resume, saved
            with_course = resume.course != saved.course
            was = "이었는데" if saved.walk or saved.index == len(saved.course.steps) else "였는데"
            return commands + [AskResume(
                f"저장한 때는 {saved.where(with_course)}{was}, 그 뒤 {resume.where(with_course)}까지 진행하신 것 같아요. "
                "파일에도 그만큼 되어 있나요?"
            )]
        course, index = resume.course, resume.index
        if index == len(course.steps):
            return commands + [Notice(f"이 파일에서 {course.name} 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")]
        self._resume = resume
        if resume.moved:
            return commands + [AskResume(f"지난번 하던 단계가 연습 과정에서 빠졌어요. 끝내지 않은 첫 단계인 {resume.where()}부터 이어 할까요?")]
        if resume.walk:
            return commands + [AskResume(f"지난번 {resume.where()}을 하던 중이었어요. 이어 할까요?")]
        return commands + [AskResume(f"지난번 {resume.where()}까지 했어요. 이어 할까요?")]

    def on_resume_answer(self, yes: bool) -> list[ManagerCommand]:
        """이어 할까요 물음에 답했을 때. 거절하면 연습 과정을 새로 고르게 두고, 기록은 지우지 않는다.

        저장 뒤 진행이 파일에 있나 물음이었으면 [네]는 기록대로, [아니요]는 저장한 때 자리로 간다(그 자리를 기록에 다시 쓴다).
        """
        resume, fallback = self._resume, self._fallback
        self._resume = self._fallback = None
        if resume is None:
            return []
        if fallback is not None and not yes:
            resume = fallback
        elif not yes:
            return []
        self._course = resume.course
        self._progress = Progress(resume.course.steps, resume.index, resume.finished, resume.walk, self._state)
        if resume is fallback:
            self._save()  # 사용자가 고른 자리라 기록한다. 기록대로 갈 때는 있던 그대로라 다시 쓰지 않는다
        if resume.moved:
            return [Notice(f"연습 과정이 고쳐져 지난번 단계를 찾지 못해, 끝내지 않은 첫 단계({self.step.name})로 왔어요.")]
        return []

    def on_file_saved(self, path: str) -> list[ManagerCommand]:
        """파일을 저장했을 때. 처음 저장이면 메모리의 진행을 붙이고, 다른 이름으로 저장이면 새 경로로 복사한다.

        저장할 때마다 그때의 자리(조작 번호까지)를 "저장 때"로 쓴다.
        """
        self._path = path
        if self._course is not None:
            step = self._progress.step
            self._saved = {
                "연습 과정": self._course.label,
                "현재 단계": step.label if step else None,
                "조작": self._progress.walk,
                "조작 수": len(step.operations) if step else 0,
                "끝낸 단계": list(self._progress.finished),
                "시각": self._now().isoformat(timespec="seconds"),
            }
            self._save()
        return []

    def walked(self) -> list[ManagerCommand]:
        """[했어요]: 다음 조작으로. 조작 자리는 저장할 때만 기록하므로 여기서는 기록하지 않는다."""
        return self._progress.walked() if self._progress else []

    # 아래는 한 연습 과정 안의 사건. Progress에 넘기고, 단계나 끝낸 단계가 바뀌었으면 기록한다.
    # 연습 과정을 고르기 전(이어 할까요 답을 기다리는 동안 포함)에는 아무것도 하지 않는다.

    def on_state(self, state: WorkState) -> list[ManagerCommand]:
        """작업 상태가 도착했을 때."""
        self._state = state
        return self._recorded(lambda progress: progress.on_state(state))

    def on_answer(self, yes: bool) -> list[ManagerCommand]:
        """다음 단계로 갈까요 물음에 답했을 때."""
        return self._recorded(lambda progress: progress.on_answer(yes))

    def next_step(self) -> list[ManagerCommand]:
        """'다음 단계' 버튼."""
        return self._recorded(lambda progress: progress.next_step())

    def skip_to(self, label: str) -> list[ManagerCommand]:
        """원하는 단계로 건너뛰기."""
        return self._recorded(lambda progress: progress.skip_to(label))

    def back(self) -> list[ManagerCommand]:
        """앞 단계로 가기."""
        return self._recorded(lambda progress: progress.back())

    def _recorded(self, event: Callable[[Progress], list[Command]]) -> list[ManagerCommand]:
        """지금 진행에 사건을 넘기고, 지금 단계나 끝낸 단계가 바뀌었으면 기록한다."""
        if self._progress is None:
            return []
        before = (self._progress.step, self._progress.finished)
        commands = event(self._progress)
        if (self._progress.step, self._progress.finished) != before:
            self._save()
        return commands

    def _start(self, course: Course) -> list[ManagerCommand]:
        """연습 과정을 첫 단계부터 시작해 기록한다. 앞 진행에 떠 있던 물음은 거둔다."""
        commands = self._progress.close() if self._progress else []
        self._course = course
        self._progress = Progress(course.steps, latest=self._state)
        self._save()
        return commands

    def _leave(self) -> list[ManagerCommand]:
        """지금 진행을 비운다(다른 파일을 열 때). 답을 기다리던 물음은 버리고, 떠 있던 물음은 거둔다."""
        commands = self._progress.close() if self._progress else []
        self._course = self._progress = self._resume = self._fallback = self._change = self._saved = None
        return commands

    def _where(self) -> str:
        """지금 단계를 화면에 보일 'n단계'(파일 순서로 셈)로. 마쳤으면 '마침'."""
        step = self._progress.step
        return f"{self._course.steps.index(step) + 1}단계" if step else "마침"

    def _read(self, path: str) -> tuple[_Resume | None, _Resume | None]:
        """그 파일의 진행 기록을 읽어 (이어 할 자리, 저장 때와 다를 때만 저장 때 자리)로.

        기록이 없거나 깨졌거나 연습 과정이 없어졌으면 (None, None).
        """
        record_path = _record_path(self._record_dir, path)
        if not record_path.exists():
            return None, None
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
            now = (record["연습 과정"], record["현재 단계"], tuple(record["끝낸 단계"]))
            saved = record.get("저장 때")
            then = (saved["연습 과정"], saved["현재 단계"], tuple(saved["끝낸 단계"])) if saved else None
            walk = (saved["조작"], saved["조작 수"]) if saved else (0, 0)
        except (ValueError, KeyError, TypeError):
            return None, None  # 깨진 기록은 없는 것으로 본다(지우지는 않는다)
        resume = self._place(*now)
        if resume is None:
            return None, None
        self._saved = saved
        if then is None:  # 예전 기록: 단계 단위로만 이어 한다
            return resume, None
        if then == now:
            return self._place(*now, *walk), None
        return resume, self._place(*then, *walk)

    def _place(
        self, label: str, current: str | None, finished: tuple[str, ...], walk: int = 0, walk_count: int = 0
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
            walk = walk if len(course.steps[index].operations) == walk_count else 0
            return _Resume(course, index, finished, moved=False, walk=walk)
        first_unfinished = next((i for i, label in enumerate(labels) if label not in finished), len(labels))
        return _Resume(course, first_unfinished, finished, moved=True)

    def _save(self) -> None:
        """지금 진행을 열린 파일의 진행 기록에 쓴다. 저장 전 파일이면 메모리에만 둔다."""
        if self._path is None or self._course is None:
            return
        step = self._progress.step
        record = {
            "파일": self._path,
            "연습 과정": self._course.label,
            "현재 단계": step.label if step else None,
            "끝낸 단계": list(self._progress.finished),
            "바뀐 시각": self._now().isoformat(timespec="seconds"),
        }
        if self._saved is not None:
            record["저장 때"] = self._saved
        self._record_dir.mkdir(parents=True, exist_ok=True)
        _record_path(self._record_dir, self._path).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
