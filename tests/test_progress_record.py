"""진행 기록과 이어 하기(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

사용자처럼 사건을 차례로 넣고 돌려준 물음과 지금 단계를 본다. 기록이 남았는지는 같은 기록 폴더로
진행 관리를 새로 만들어(도우미 창을 껐다 켠 것처럼) 같은 파일을 열어 보며 확인한다.
기록은 테스트마다 임시 폴더(tmp_path)에 쓴다.
"""

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from blender_tutor.progress import Ask, Course, Operation, Step, Withdraw, load_course
from blender_tutor.progress_record import AskChangeCourse, AskResume, Notice, ProgressManager
from blender_tutor.work_state import WorkState

SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기"), Step("join", "부품 합치기")))
SHIELD = Course("shield", "방패", (Step("view", "화면 돌려 보기"), Step("rim", "테두리 만들기")))
# 끝난 조건이 있어 "다음 단계로 갈까요"를 띄울 수 있는 연습 과정과 그 조건이 맞는 작업 상태.
ASKING = Course("asking", "묻는 과정", (Step("blade-tip", "칼끝 모으기", (("방금 조작", "mesh.merge"),)), Step("join", "부품 합치기")))
MERGED = WorkState("EDIT_MESH", None, (), "en_US", False, "", 3, "5.2.2", {"VERT": 1}, ("mesh.merge",))
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
    manager.on_file_saved(BLEND)  # 저장할 때마다 그 자리를 다시 남긴다

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
    # BLEND는 1단계에서 저장한 뒤 2단계로 넘어갔고 다시 저장하지 않았다
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume(
        "저장한 때는 1단계(화면 돌려 보기)였는데, 그 뒤 2단계(칼끝 모으기)까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]
    assert make(tmp_path).on_file_opened(copy) == [AskResume(
        "저장한 때는 2단계(칼끝 모으기)였는데, 그 뒤 3단계(부품 합치기)까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]


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
    assert make(tmp_path).on_file_opened(BLEND) == [AskResume(  # 바꾼 뒤 저장하지 않아 파일은 검 그대로일 수 있다
        "저장한 때는 검 1단계(화면 돌려 보기)였는데, 그 뒤 방패 1단계(화면 돌려 보기)까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]


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
        "끝낸 조작 수": 0,
        "조작 수": 0,
        "끝낸 단계": ["view"],
        "바뀐 시각": "2026-10-20T15:30:00",
        # Blender에서 저장할 때의 자리. 저장 뒤 바뀐 것은 여기에 들지 않는다
        "저장 때": {"연습 과정": "sword", "현재 단계": "view", "끝낸 조작 수": 0, "조작 수": 0, "끝낸 단계": [], "시각": "2026-10-20T15:30:00"},
    }


def test_다_마친_파일을_열면_다른_연습_과정을_권한다(tmp_path):
    manager = make(tmp_path, courses=(ASKING,))
    manager.choose_course("asking")
    manager.on_file_saved(BLEND)
    manager.on_state(MERGED)
    manager.on_answer(True)  # 칼끝 모으기를 [네]로 끝냄
    manager.next_step()  # 부품 합치기를 버튼으로 끝냄
    assert manager.step is None
    manager.on_file_saved(BLEND)
    reopened = make(tmp_path, courses=(ASKING,))
    assert reopened.on_file_opened(BLEND) == [
        Notice("이 파일에서 묻는 과정 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")
    ]
    assert reopened.course is None


def test_저장소의_검_연습_과정으로_저장하고_이어_할_수_있다(tmp_path):
    sword = load_course(COURSES / "sword.yaml")
    assert (sword.label, sword.name) == ("sword", "단순한 검")
    assert sword.summary.startswith("기본 정육면체를 늘려 칼날을 만들고")  # 비슷한 연습 과정 권하기에 쓰는 한 줄 설명
    manager = ProgressManager([sword], tmp_path)
    manager.choose_course("sword")
    manager.on_file_saved(BLEND)
    manager.skip_to("blade-stretch")
    manager.on_file_saved(BLEND)
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


def test_새_파일_열림은_경로가_비어_오고_저장_전_파일로_받는다(tmp_path):
    # Blender를 켤 때와 File > New 때 애드온은 경로 ""로 열림을 보낸다(티켓 25)
    manager = make(tmp_path)
    assert manager.on_file_opened("") == []
    manager.choose_course("sword")
    assert manager.choose_course("shield") == [AskChangeCourse("지금 진행(검, 1단계)은 저장 전 파일이라 남지 않아요. 방패로 바꿀까요?")]
    assert make(tmp_path).on_file_opened("") == []  # 빈 경로로 기록을 쓰지 않았다
    assert list(tmp_path.iterdir()) == []



# 칼끝 모으기에 조작 셋이 있는 검(조작 안내 자리를 기록하는지 보려고)
TIP_STEP = Step("blade-tip", "칼끝 모으기", operations=(Operation("가", "없음", "Tab", "가요."), Operation("나", "없음", "M", "나요."), Operation("다", "없음", "B", "다요.")))
GUIDED_SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), TIP_STEP, Step("join", "부품 합치기")))


def saved_at_tip_operation(tmp_path, then=lambda manager: None) -> None:
    """검 2단계(칼끝 모으기)의 3번째 조작에서 BLEND로 저장해 두고, then으로 저장 뒤 일을 더 한다."""
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    manager.on_file_opened(BLEND)
    manager.choose_course("sword")
    manager.next_step()
    manager.next_operation()
    manager.next_operation()
    manager.on_file_saved(BLEND)
    then(manager)


def test_저장할_때의_조작_자리까지_남기고_다시_열면_그_조작부터_이어_한다(tmp_path):
    saved_at_tip_operation(tmp_path)
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    assert manager.on_file_opened(BLEND) == [AskResume("지난번 2단계(칼끝 모으기) 3번째 조작을 하던 중이었어요. 이어 할까요?")]
    manager.on_resume_answer(True)
    assert (manager.step, manager.operations_done) == (TIP_STEP, 2)


def test_다음_뒤로_버튼으로_바뀐_조작_자리도_바로_기록한다(tmp_path):
    saved_at_tip_operation(tmp_path, then=lambda manager: (manager.back(), manager.back()))  # 3번째 → 1번째 조작
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    manager.on_file_opened(BLEND)
    manager.on_resume_answer(True)
    assert (manager.step, manager.operations_done) == (TIP_STEP, 0)
    manager.forward()
    manager.forward()
    manager.forward()  # 조작을 다 끝낸 자리
    assert (manager.step, manager.operations_done) == (TIP_STEP, 3)
    manager.forward()  # '다음 단계'
    assert manager.step == GUIDED_SWORD.steps[2]


def test_조작을_더_하고_저장하지_않았으면_다시_열_때_그만큼_되어_있는지_묻는다(tmp_path):
    saved_at_tip_operation(tmp_path, then=lambda manager: manager.next_operation())  # 저장 뒤 [했어요]만 더 누르고 저장하지 않음
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    assert manager.on_file_opened(BLEND) == [AskResume(
        "저장한 때는 2단계(칼끝 모으기) 3번째 조작이었는데, 그 뒤 2단계(칼끝 모으기) 모든 조작까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]
    manager.on_resume_answer(True)
    assert manager.operations_done == 3


def test_조작_자리는_감지되거나_했어요를_누를_때마다_기록한다(tmp_path):
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    manager.on_file_opened(BLEND)
    manager.choose_course("sword")
    manager.next_step()
    manager.next_operation()  # 저장한 적 없는 파일이라도 경로가 있으면 기록한다(저장 때 자리가 없는 기록)
    reopened = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    assert reopened.on_file_opened(BLEND) == [AskResume("지난번 2단계(칼끝 모으기) 2번째 조작을 하던 중이었어요. 이어 할까요?")]


def test_저장_뒤_단계를_더_넘겼으면_파일에도_되어_있는지_묻고_네면_기록대로_간다(tmp_path):
    saved_at_tip_operation(tmp_path, then=lambda manager: manager.next_step())
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    assert manager.on_file_opened(BLEND) == [AskResume(
        "저장한 때는 2단계(칼끝 모으기) 3번째 조작이었는데, 그 뒤 3단계(부품 합치기)까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]
    manager.on_resume_answer(True)
    assert (manager.step.label, manager.operations_done) == ("join", 0)


def test_저장_뒤_진행이_파일에_없다고_하면_저장한_때_자리로_간다(tmp_path):
    saved_at_tip_operation(tmp_path, then=lambda manager: manager.next_step())
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    manager.on_file_opened(BLEND)
    manager.on_resume_answer(False)
    assert (manager.step, manager.operations_done) == (TIP_STEP, 2)
    assert make(tmp_path, courses=(GUIDED_SWORD, SHIELD)).on_file_opened(BLEND) == [  # 고른 자리를 기록에 다시 쓴다
        AskResume("지난번 2단계(칼끝 모으기) 3번째 조작을 하던 중이었어요. 이어 할까요?")
    ]


def test_저장_뒤_연습_과정을_바꿨으면_연습_과정_이름도_함께_묻는다(tmp_path):
    def change(manager):
        manager.choose_course("shield")
        manager.on_change_answer(True)

    saved_at_tip_operation(tmp_path, then=change)
    assert make(tmp_path, courses=(GUIDED_SWORD, SHIELD)).on_file_opened(BLEND) == [AskResume(
        "저장한 때는 검 2단계(칼끝 모으기) 3번째 조작이었는데, 그 뒤 방패 1단계(화면 돌려 보기)까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?"
    )]


def test_연습_과정이_고쳐져_그_단계_조작_수가_달라졌으면_첫_조작부터(tmp_path):
    saved_at_tip_operation(tmp_path)
    fewer = replace(TIP_STEP, operations=TIP_STEP.operations[:2])
    manager = make(tmp_path, courses=(Course("sword", "검", (GUIDED_SWORD.steps[0], fewer, GUIDED_SWORD.steps[2])),))
    assert manager.on_file_opened(BLEND) == [AskResume("지난번 2단계(칼끝 모으기)까지 했어요. 이어 할까요?")]
    manager.on_resume_answer(True)
    assert manager.operations_done == 0


def test_연습_과정을_고르기_전에_받은_작업_상태를_기준으로_고른_뒤_첫_조작을_감지한다(tmp_path):
    scale = Operation("늘리기", "Object > Transform > Scale", "S", "S로 늘려 보세요.", (("방금 조작", "transform.resize"),))
    course = Course("sword", "검", (Step("blade-stretch", "칼날 모양 잡기", operations=(scale, scale)),))
    manager = make(tmp_path, courses=(course,))
    manager.on_state(MERGED)  # 고르기 전 Blender 상태
    manager.choose_course("sword")
    manager.on_state(replace(MERGED, recent_operators=("mesh.merge", "transform.resize")))  # 고른 뒤 처음 한 조작
    assert manager.operations_done == 1


def test_지금_띄울_물음과_네_아니요는_진행_관리가_직접_가린다(tmp_path):
    manager = make(tmp_path, courses=(ASKING, SWORD))
    assert manager.prompt is None
    manager.choose_course("asking")
    manager.on_state(MERGED)
    assert manager.prompt == "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?"
    manager.choose_course("sword")  # 바꿀까요 물음이 위에 뜬다
    assert manager.prompt == "지금 진행(묻는 과정, 1단계)은 저장 전 파일이라 남지 않아요. 검으로 바꿀까요?"
    manager.answer(False)  # 바꾸지 않으면 앞에 떠 있던 물음이 다시 보인다
    assert manager.prompt.startswith("'칼끝 모으기' 단계를 끝낸 것 같아요.")
    manager.answer(True)
    assert (manager.prompt, manager.step.label) == (None, "join")
    assert manager.answer(True) == []  # 물음이 없으면 아무것도 하지 않는다


def test_저장_뒤_진행_물음이_떠_있을_때_연습_과정을_고르면_덮어쓸지_묻고_네면_처음부터(tmp_path):
    # 이어 하기 물음의 [아니요](저장 때 자리로 가기)로 치지 않는다
    saved_at_tip_operation(tmp_path, then=lambda manager: manager.next_step())
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    manager.on_file_opened(BLEND)
    manager.choose_course("sword")
    assert manager.prompt == "이 파일의 진행 기록(검, 3단계)이 검으로 처음부터 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?"
    manager.answer(True)
    assert (manager.prompt, manager.step.label, manager.operations_done) == (None, "view", 0)


def test_기록이_있는_파일에서_이어_하기_전에_고르면_덮어쓸지_묻고_아니요면_이어_하기_물음으로(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    manager.choose_course("shield")
    assert manager.prompt == "이 파일의 진행 기록(검, 3단계)이 방패로 처음부터 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?"
    assert manager.course is None  # 답하기 전에는 아무것도 바뀌지 않는다
    manager.answer(False)
    assert manager.prompt == "지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?"
    manager.answer(True)
    assert manager.step.label == "join"


def test_다_마친_기록이_있는_파일에서_고를_때도_덮어쓸지_묻는다(tmp_path):
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    manager.choose_course("shield")
    manager.next_step()
    manager.next_step()
    manager.on_file_saved(BLEND)
    reopened = make(tmp_path)
    reopened.on_file_opened(BLEND)  # 다 마쳤다는 알림만 뜬다
    reopened.choose_course("sword")
    assert reopened.prompt == "이 파일의 진행 기록(방패, 다 마침)이 검으로 처음부터 바뀌어요. 새 파일에서 시작하면 둘 다 남아요. 바꿀까요?"


def test_이어_하기를_거절한_뒤_고를_때도_덮어쓸지_묻는다(tmp_path):
    saved_at_join(tmp_path)
    manager = make(tmp_path)
    manager.on_file_opened(BLEND)
    manager.answer(False)
    manager.choose_course("sword")
    assert manager.prompt.startswith("이 파일의 진행 기록(검, 3단계)이 검으로 처음부터 바뀌어요.")


def test_바뀐_시각은_진행이_바뀔_때만_쓰고_저장만_하면_그대로(tmp_path):
    clock = iter(datetime(2026, 10, 23, 10, minute) for minute in range(60))
    manager = ProgressManager([SWORD], tmp_path, now=lambda: next(clock))
    manager.on_file_opened(BLEND)
    manager.choose_course("sword")  # 10:00 진행이 바뀜
    manager.on_file_saved(BLEND)  # 10:01 저장만
    manager.on_file_saved(BLEND)  # 10:02 저장만
    [record] = tmp_path.glob("*.json")
    data = json.loads(record.read_text(encoding="utf-8"))
    assert (data["바뀐 시각"], data["저장 때"]["시각"]) == ("2026-10-23T10:00:00", "2026-10-23T10:02:00")

    reopened = ProgressManager([SWORD], tmp_path, now=lambda: next(clock))  # 다시 열어도 앞 시각을 이어받는다
    reopened.on_file_opened(BLEND)
    reopened.answer(True)
    reopened.on_file_saved(BLEND)
    data = json.loads(record.read_text(encoding="utf-8"))
    assert data["바뀐 시각"] == "2026-10-23T10:00:00"


def test_저장_뒤_다_마쳤다는_물음에_네면_다_마친_파일을_열_때와_같게_알리고_고르기로(tmp_path):
    def finish(manager):
        manager.next_step()  # 3단계(마지막)에서 저장한 뒤 버튼으로 마침, 저장 안 함

    saved_at_tip_operation(tmp_path, then=lambda manager: (manager.next_step(), finish(manager)))
    manager = make(tmp_path, courses=(GUIDED_SWORD, SHIELD))
    assert manager.on_file_opened(BLEND)[0].text.endswith("그 뒤 다 마친 상태까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?")
    assert manager.answer(True) == [Notice("이 파일에서 검 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")]
    assert (manager.course, manager.prompt) == (None, None)
    manager.choose_course("shield")
    assert manager.prompt.startswith("이 파일의 진행 기록(검, 다 마침)이 방패로 처음부터 바뀌어요.")


def test_기록_폴더에_쓸_수_없어도_진행은_멈추지_않고_메모리에만_둔다(tmp_path):
    # 관리되는 PC에서 설정 폴더 쓰기가 막힌 경우. 여기서는 폴더 자리에 파일을 둬서 폴더를 못 만들게 한다
    blocked = tmp_path / "blocked"
    blocked.write_text("", encoding="utf-8")
    manager = make(blocked)
    manager.on_file_opened(BLEND)
    manager.choose_course("sword")
    manager.next_step()
    manager.on_file_saved(BLEND)
    assert manager.step.label == "blade-tip"
