"""진행 기록과 이어 하기(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

사용자처럼 사건을 차례로 넣고 돌려준 물음과 지금 단계를 본다. 기록이 남았는지는 같은 기록 폴더로
진행 관리를 새로 만들어(도우미 창을 껐다 켠 것처럼) 같은 파일을 열어 보며 확인한다.
기록은 테스트마다 임시 폴더(tmp_path)에 쓴다.
"""

import json
from datetime import datetime
from pathlib import Path

from blender_tutor.conditions import WorkState
from blender_tutor.progress import Ask, Course, Step, Withdraw, load_course
from blender_tutor.progress_record import AskChangeCourse, AskResume, Notice, ProgressManager

SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기"), Step("join", "부품 합치기")))
SHIELD = Course("shield", "방패", (Step("view", "화면 돌려 보기"), Step("rim", "테두리 만들기")))
# 끝난 조건이 있어 "다음 단계로 갈까요"를 띄울 수 있는 연습 과정과 그 조건이 맞는 작업 상태.
ASKING = Course("asking", "묻는 과정", (Step("blade-tip", "칼끝 모으기", (("방금 조작", "mesh.merge"),)), Step("join", "부품 합치기")))
MERGED = WorkState("EDIT_MESH", ("mesh.merge",), 3, (), 1, (1.0, 1.0, 1.0), (2.0, 2.0, 2.0))
BLEND = str(Path("C:/work/sword.blend"))
OTHER = str(Path("C:/work/other.blend"))
COURSES = Path(__file__).resolve().parent.parent / "courses"


def make(tmp_path, courses=(SWORD, SHIELD)) -> ProgressManager:
    return ProgressManager(list(courses), tmp_path)


def test_저장한_파일을_다시_열면_지난번_단계부터_이어_할지_묻는다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.next_step()
    manager.next_step()

    reopened = make(tmp_path)
    assert reopened.on_file_opened(BLEND) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]


def saved_at_join(tmp_path) -> None:
    """검 연습 과정을 3단계(부품 합치기)까지 하고 BLEND에 저장해 둔다."""
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.next_step()
    manager.next_step()
    manager.on_file_saved(BLEND)


def test_이어_하면_기록의_연습_과정과_단계로_간다(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    assert manager.on_resume_answer(True) == []
    assert manager.course == SWORD
    assert manager.step.label == "join"


def test_이어_하기를_거절하면_연습_과정을_새로_고르고_기록은_남는다(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    assert manager.on_resume_answer(False) == []
    assert manager.course is None
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]


def test_저장_전_진행은_처음_저장할_때_그_파일에_붙는다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.next_step()
    assert make(tmp_path).on_file_opened(BLEND) == []  # 저장 전에는 기록이 없다
    manager.on_file_saved(BLEND)
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 2단계(칼끝 모으기)까지 했어요. 이어 할까요?")]


def test_다른_이름으로_저장하면_새_경로로_복사되고_그_뒤_진행은_새_파일에만_남는다(tmp_path):
    copy = str(Path("C:/work/sword_v2.blend"))
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.next_step()
    manager.on_file_saved(copy)
    manager.next_step()
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 2단계(칼끝 모으기)까지 했어요. 이어 할까요?")]
    assert make(tmp_path).on_file_opened(copy) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]


def test_다른_연습_과정으로_바꾸면_먼저_확인을_묻고_네면_바꾼다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.next_step()
    assert manager.choose_course("shield") == [
        AskChangeCourse("이 파일의 진행 기록(검, 2단계)이 방패로 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?")
    ]
    assert manager.course == SWORD  # 답하기 전에는 그대로
    assert manager.on_change_answer(True) == []
    assert manager.course == SHIELD
    assert manager.step.label == "view"
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 1단계(화면 돌려 보기)까지 했어요. 이어 할까요?")]


def test_다른_파일을_열면_지금_진행을_비우고_앞_파일의_기록은_남는다(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    manager.on_resume_answer(True)
    manager.choose_course("shield")  # 바꿀까요 물음에 답하기 전에 파일을 연다
    assert manager.on_file_opened(OTHER) == []
    assert manager.course is None
    assert manager.on_change_answer(True) == []  # 열기 전의 물음에 늦게 온 답은 무시
    assert manager.next_step() == []  # 연습 과정을 고르기 전에는 버튼이 아무것도 하지 않는다
    manager.choose_course("shield")
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]
    assert make(tmp_path).on_file_opened(OTHER) == [AskResume("지난번 1단계(화면 돌려 보기)까지 했어요. 이어 할까요?")]


def test_이어_할까요에_답하기_전에는_버튼이_기록을_건드리지_않는다(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    assert manager.back() == []
    assert manager.skip_to("view") == []
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]


def test_연습_과정을_고르기_전에는_버튼과_답이_아무것도_하지_않는다(tmp_path):
    manager = make(tmp_path)
    assert manager.next_step() == []
    assert manager.back() == []
    assert manager.skip_to("view") == []
    assert manager.on_answer(True) == []
    assert manager.on_state(MERGED) == []
    assert manager.step is None


def test_진행이_바뀌면_떠_있던_다음_단계_물음을_거둔다(tmp_path):
    manager = make(tmp_path, courses=(ASKING, SWORD))
    manager.choose_course("asking")
    assert [type(c) for c in manager.on_state(MERGED)] == [Ask]
    manager.choose_course("sword")
    assert manager.on_change_answer(True) == [Withdraw("blade-tip")]

    manager = make(tmp_path, courses=(ASKING, SWORD))
    manager.choose_course("asking")
    manager.on_state(MERGED)
    assert manager.on_file_opened(OTHER) == [Withdraw("blade-tip")]


def test_연습_과정_바꾸기를_거절하면_그대로_둔다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.next_step()
    manager.choose_course("shield")
    assert manager.on_change_answer(False) == []
    assert manager.course == SWORD
    assert manager.step.label == "blade-tip"


def test_처음_고르거나_같은_연습_과정을_다시_고르면_묻지_않는다(tmp_path):
    manager = make(tmp_path)
    assert manager.choose_course("sword") == []
    manager.next_step()
    assert manager.choose_course("sword") == []
    assert manager.step.label == "blade-tip"


def test_바꿀_연습_과정_이름의_받침에_맞춰_으로를_붙인다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("shield")
    manager.on_file_saved(BLEND)
    assert manager.choose_course("sword") == [
        AskChangeCourse("이 파일의 진행 기록(방패, 1단계)이 검으로 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?")
    ]


def test_저장_전에_연습_과정을_바꾸면_진행이_남지_않는다고_묻는다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.next_step()
    assert manager.choose_course("shield") == [
        AskChangeCourse("지금 진행(검, 2단계)은 저장 전 파일이라 남지 않아요. 방패로 바꿀까요?")
    ]


def test_기록의_단계가_연습_과정에서_사라졌으면_끝내지_않은_첫_단계로_가고_알린다(tmp_path):
    saved_at_join(tmp_path)  # 화면 돌려 보기·칼끝 모으기를 끝내고 부품 합치기에서 저장
    # 연습 과정 파일이 고쳐져 부품 합치기가 빠지고 코등이 붙이기가 들어왔다.
    edited = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기"), Step("guard", "코등이 붙이기")))
    manager = make(tmp_path, courses=(edited,))
    assert manager.on_file_opened(BLEND) == [
        AskResume("지난번 하던 단계가 연습 과정에서 빠졌어요. 끝내지 않은 첫 단계인 3단계(코등이 붙이기)부터 이어 할까요?")
    ]
    assert manager.on_resume_answer(True) == [
        Notice("연습 과정이 고쳐져 지난번 단계를 찾지 못해, 끝내지 않은 첫 단계(코등이 붙이기)로 왔어요.")
    ]
    assert manager.step.label == "guard"


def test_건너뛰기로_지나친_단계는_끝낸_단계가_아니다(tmp_path):
    manager = make(tmp_path)
    manager.choose_course("sword")
    manager.skip_to("join")
    manager.on_file_saved(BLEND)
    edited = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기")))
    reopened = make(tmp_path, courses=(edited,))
    assert reopened.on_file_opened(BLEND) == [
        AskResume("지난번 하던 단계가 연습 과정에서 빠졌어요. 끝내지 않은 첫 단계인 1단계(화면 돌려 보기)부터 이어 할까요?")
    ]


def test_기록의_연습_과정이_없어졌으면_묻지_않는다(tmp_path):
    saved_at_join(tmp_path)
    assert make(tmp_path, courses=(SHIELD,)).on_file_opened(BLEND) == []


def test_기록_파일이_깨졌으면_없는_것으로_보고_지우지_않는다(tmp_path):
    saved_at_join(tmp_path)
    [record] = tmp_path.glob("*.json")
    record.write_text("{깨진", encoding="utf-8")
    assert make(tmp_path).on_file_opened(BLEND) == []
    assert record.read_text(encoding="utf-8") == "{깨진"


def test_진행_기록에는_사용자가_확인한_것만_남는다(tmp_path):
    course = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기", (("방금 조작", "mesh.merge"),)), Step("join", "부품 합치기")))
    manager = ProgressManager([course], tmp_path, now=lambda: datetime(2026, 10, 20, 15, 30))
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.next_step()  # 화면 돌려 보기를 버튼으로 끝냄
    assert manager.on_state(MERGED) == [Ask("blade-tip", "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?")]
    manager.on_answer(False)  # 물음을 띄운 것도, 거절한 것도 기록에 남지 않는다
    manager.back()  # 뒤로 가도 끝낸 단계는 그대로

    [record] = tmp_path.glob("*.json")
    assert json.loads(record.read_text(encoding="utf-8")) == {
        "파일": BLEND,
        "연습 과정": "sword",
        "현재 단계": "view",
        "끝낸 단계": ["view"],
        "바뀐 시각": "2026-10-20T15:30:00",
    }


def test_다_마친_파일을_열면_다른_연습_과정을_권한다(tmp_path):
    manager = make(tmp_path, courses=(ASKING,))
    manager.choose_course("asking")
    manager.on_file_saved(BLEND)
    manager.on_state(MERGED)
    manager.on_answer(True)  # 칼끝 모으기를 [네]로 끝냄
    manager.next_step()  # 부품 합치기를 버튼으로 끝냄
    assert manager.step is None
    reopened = make(tmp_path, courses=(ASKING,))
    assert reopened.on_file_opened(BLEND) == [
        Notice("이 파일에서 묻는 과정 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")
    ]
    assert reopened.course is None


def test_저장소의_검_연습_과정으로_저장하고_이어_할_수_있다(tmp_path):
    sword = load_course(COURSES / "sword.yaml")
    assert (sword.label, sword.name) == ("sword", "단순한 검")
    manager = ProgressManager([sword], tmp_path)
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.skip_to("blade-stretch")
    assert make(tmp_path, courses=(sword,)).on_file_opened(BLEND) == [
        AskResume(f"지난번 3단계({sword.steps[2].name})까지 했어요. 이어 할까요?")
    ]


def test_blender_창마다_진행_관리를_따로_두면_오가도_기록이_섞이지_않는다(tmp_path):
    # 도우미 창은 Blender 창 번호마다 진행 관리를 하나씩 둔다(티켓 27). 기록 폴더는 함께 쓴다.
    window1, window2 = make(tmp_path), make(tmp_path)
    window1.on_file_opened(BLEND)
    window1.choose_course("sword")
    window2.on_file_opened(OTHER)
    window2.choose_course("shield")
    window1.next_step()
    window2.next_step()
    window1.next_step()
    assert (window1.course, window1.step.label) == (SWORD, "join")
    assert (window2.course, window2.step.label) == (SHIELD, "rim")
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume("지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")]
    assert make(tmp_path).on_file_opened(OTHER) == [AskResume("지난번 2단계(테두리 만들기)까지 했어요. 이어 할까요?")]
