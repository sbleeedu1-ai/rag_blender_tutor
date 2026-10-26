"""작업 상태 흐름 기록(티켓 28): 진행 관리에 들어간 봉투·버튼을 파일에 남기고, 그 파일을 새 진행 관리에 다시 넣으면 같은 일이 일어난다.

검수(티켓 32)에서 사용자가 따라 한 흐름을 이렇게 회귀 테스트로 쓴다. 기록 폴더는 테스트마다 임시 폴더다.
"""

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
    original = RecordingDesk(CourseDesk([SWORD], tmp_path / "first"), stream)
    said = follow_along(original)

    again = CourseDesk([SWORD], tmp_path / "second")  # 진행 기록 폴더가 다르면 처음 하는 것과 같다
    replayed = [line for _, lines in replay(stream, again) for line in lines]

    assert said and replayed == said
    assert again.view(A) == original.view(A)


def test_다시_돌리며_줄마다_진행_모양을_볼_수_있다(tmp_path):
    """회귀 테스트는 '이 줄 뒤에 물음이 떠야 한다'처럼 줄마다 본다."""
    stream = tmp_path / "stream.jsonl"
    follow_along(RecordingDesk(CourseDesk([SWORD], tmp_path / "first"), stream))
    again = CourseDesk([SWORD], tmp_path / "second")
    prompts = [(entry["call"], again.view(A).prompt) for entry, _ in replay(stream, again)]
    assert ("on_message", "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?") in prompts


def test_기록_파일을_쓸_수_없어도_진행_관리는_그대로_돈다(tmp_path):
    """흐름 기록은 검수용 덤이라 못 써도 도우미는 멈추지 않는다."""
    desk = RecordingDesk(CourseDesk([SWORD], tmp_path / "first"), tmp_path)  # 폴더를 파일 자리에 줘서 쓰기가 실패한다
    assert follow_along(desk)
    assert desk.view(A).step == SWORD.steps[2]
