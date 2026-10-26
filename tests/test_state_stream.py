"""작업 상태 흐름 기록(티켓 28): 진행 관리에 들어간 봉투·버튼을 파일에 남기고, 그 파일을 새 진행 관리에 다시 넣으면 같은 일이 일어난다.

검수(티켓 32)에서 사용자가 따라 한 흐름을 이렇게 회귀 테스트로 쓴다. 기록 폴더는 테스트마다 임시 폴더다.
"""

import inspect

from blender_tutor.course_desk import CourseDesk
from blender_tutor.progress import Course, Operation, Step
from blender_tutor.receiver import FileEvent
from blender_tutor.state_stream import RecordingDesk, replay
from blender_tutor.work_state import ActiveObject, View, WorkState

SWORD = Course(
    "sword",
    "검",
    (
        Step("view", "화면 돌려 보기", operations=(Operation("화면 돌리기", "없음", "가운데 버튼 끌기", say="가운데 버튼을 끌어 보세요.", detect=(("화면", "돌림"),)),)),
        Step("blade-tip", "칼끝 모으기", (("방금 조작", "mesh.merge"),)),
        Step("join", "부품 합치기"),
    ),
)
CUBE = ActiveObject("Cube", "MESH", (), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0), 0)
FRONT = View(10.0, (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
TURNED = View(10.0, (0.9, 0.3, 0.1, 0.2), (0.0, 0.0, 0.0))
IDLE = WorkState("OBJECT", CUBE, ("Cube",), "ko_KR", True, "", 3, "5.2.2", {}, (), view=FRONT)
LOOKED = WorkState("OBJECT", CUBE, ("Cube",), "ko_KR", True, "", 3, "5.2.2", {}, (), view=TURNED)
MERGED = WorkState("EDIT_MESH", CUBE, ("Cube",), "ko_KR", True, "", 3, "5.2.2", {"VERT": 1}, ("mesh.merge",), view=TURNED)
A, B = 101, 202  # Blender 창 번호 둘


def recording(records, stream) -> RecordingDesk:
    """진행 기록 폴더 records를 쓰는 진행 관리를 흐름 기록으로 감싼다(도우미가 하는 것과 같게)."""
    return RecordingDesk(CourseDesk([SWORD], records), stream, records)


def follow_along(desk) -> list:
    """사용자가 따라 하는 모습(지어낸 것): 파일 열기 → 검 고르기 → 화면 돌림(감지) → 칼끝 모음(물음) → [네] → 뒤로 → 건너뛰기, 사이에 다른 Blender."""
    said = []
    said += desk.on_message(A, IDLE, FileEvent("opened", "C:/work/sword.blend"))
    said += desk.choose(A, "sword")
    said += desk.on_message(A, LOOKED)
    said += desk.forward(A)
    said += desk.on_message(B, IDLE, FileEvent("opened", ""), shown=False)
    said += desk.on_message(A, MERGED)
    said += desk.answer(A, True)
    said += desk.back(A)
    said += desk.switched_to(B)
    said += desk.switched_to(A)
    said += desk.skip_to(A, "join")
    desk.keep({A})
    return said


def test_기록한_흐름을_새_진행_관리에_다시_넣으면_같은_말과_자리가_나온다(tmp_path):
    stream = tmp_path / "stream.jsonl"
    original = recording(tmp_path / "first", stream)
    said = follow_along(original)

    again = CourseDesk([SWORD], tmp_path / "second")  # 진행 기록 폴더가 다르면 처음 하는 것과 같다
    replayed = [line for _, lines in replay(stream, again, tmp_path / "second") for line in lines]

    assert said and replayed == said
    assert again.view(A) == original.view(A)


def test_다시_돌리며_줄마다_진행_모양을_볼_수_있다(tmp_path):
    """회귀 테스트는 '이 줄 뒤에 물음이 떠야 한다'처럼 줄마다 본다."""
    stream = tmp_path / "stream.jsonl"
    follow_along(recording(tmp_path / "first", stream))
    again = CourseDesk([SWORD], tmp_path / "second")
    prompts = [(entry["call"], again.view(A).prompt) for entry, _ in replay(stream, again, tmp_path / "second")]
    assert ("on_message", "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?") in prompts


def test_기록_파일을_쓸_수_없어도_진행_관리는_그대로_돈다(tmp_path):
    """흐름 기록은 검수용 덤이라 못 써도 도우미는 멈추지 않는다."""
    desk = recording(tmp_path / "first", tmp_path)  # 폴더를 파일 자리에 줘서 쓰기가 실패한다
    assert follow_along(desk)
    assert desk.view(A).step == SWORD.steps[2]


def test_진행_기록이_있는_파일을_이어_한_흐름도_빈_폴더에서_똑같이_다시_돈다(tmp_path):
    """검수가 하루에 안 끝나 다음 날 이어 하면, 도우미는 파일을 열 때 진행 기록을 읽어 '이어 할까요'를 묻는다.

    그날의 흐름 파일만으로 다시 돌려도 같아야 하므로, 열 때의 진행 기록이 흐름에 함께 남아야 한다.
    """
    records = tmp_path / "records"
    first_day = recording(records, tmp_path / "day1.jsonl")
    first_day.on_message(A, IDLE, FileEvent("opened", "C:/work/sword.blend"))
    first_day.choose(A, "sword")
    first_day.on_message(A, LOOKED)
    first_day.forward(A)
    first_day.on_message(A, IDLE, FileEvent("saved", "C:/work/sword.blend"))  # 2단계에서 저장하고 끔

    stream = tmp_path / "day2.jsonl"
    second_day = recording(records, stream)  # 다음 날 도우미를 다시 켬: 새 흐름 파일, 진행 기록은 그대로
    said = second_day.on_message(A, IDLE, FileEvent("opened", "C:/work/sword.blend"))
    said += second_day.answer(A, True)  # 이어 할까요? [네]
    said += second_day.on_message(A, MERGED)

    again = CourseDesk([SWORD], tmp_path / "empty")
    replayed = [line for _, lines in replay(stream, again, tmp_path / "empty") for line in lines]
    assert replayed == said
    assert again.view(A) == second_day.view(A) and again.view(A).number == 2


def test_진행_관리의_함수는_흐름_기록에도_모두_같은_모양으로_있다():
    """진행 관리에 버튼 함수를 더하고 흐름 기록에 빠뜨리면, 도우미 창에서 그 버튼을 누를 때 오류가 난다(도우미 입구는 시험 밖)."""
    public = [name for name in vars(CourseDesk) if not name.startswith("_") and callable(getattr(CourseDesk, name))]
    assert "choose" in public and "keep" in public
    for name in public:
        assert hasattr(RecordingDesk, name), f"흐름 기록에 {name}이 없음"
        assert inspect.signature(getattr(RecordingDesk, name)) == inspect.signature(getattr(CourseDesk, name)), name
