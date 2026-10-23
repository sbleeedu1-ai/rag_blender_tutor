"""창 번호마다 진행 관리(티켓 27): Blender에서 온 봉투와 창의 버튼·답을 차례로 넣고, 창에 보일 단계·물음과 대화에 붙일 안내 말을 본다.

진행 관리 자체의 규칙은 test_progress_record.py가 보고, 여기서는 Blender 창 번호로 나누기, 카드에 보일 모양, 대화에 붙일 말을 본다.
기록은 테스트마다 임시 폴더(tmp_path)에 쓴다.
"""

from pathlib import Path

from blender_tutor.course_desk import CourseDesk, Line, LineKind, StepView
from blender_tutor.progress import Course, Operation, Step
from blender_tutor.receiver import FileEvent
from blender_tutor.work_state import WorkState

SWORD = Course("sword", "검", (Step("view", "화면 돌려 보기"), Step("blade-tip", "칼끝 모으기", (("방금 조작", "mesh.merge"),)), Step("join", "부품 합치기")))
SHIELD = Course("shield", "방패", (Step("view", "화면 돌려 보기"), Step("rim", "테두리 만들기")))
IDLE = WorkState("OBJECT", None, (), "en_US", False, "", 3, "5.2.2", {}, ())
MERGED = WorkState("EDIT_MESH", None, (), "en_US", False, "", 3, "5.2.2", {"VERT": 1}, ("mesh.merge",))
BLEND = str(Path("C:/work/sword.blend"))
OTHER = str(Path("C:/work/shield.blend"))
A, B = 101, 202  # Blender 창 번호 둘


def make(tmp_path) -> CourseDesk:
    return CourseDesk([SWORD, SHIELD], tmp_path)


def test_blender_둘을_오가도_창마다_진행이_따로_남는다(tmp_path):
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.on_message(B, IDLE, FileEvent("opened", OTHER))
    desk.choose(A, "sword")
    desk.choose(B, "shield")
    desk.next_step(A)
    desk.on_message(B, IDLE)  # B에서 상태가 와도 A의 진행은 그대로
    assert desk.view(A) == StepView(SWORD, 2, SWORD.steps[1], None)
    assert desk.view(B) == StepView(SHIELD, 1, SHIELD.steps[0], None)
    assert desk.step(A) == SWORD.steps[1]


def at_blade_tip(tmp_path) -> CourseDesk:
    """A에서 검 연습 과정 2단계(칼끝 모으기, 끝난 조건 있음)에 와 있는 상태."""
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", ""))
    desk.choose(A, "sword")
    desk.next_step(A)
    return desk


def test_끝난_조건이_맞으면_물음을_띄우고_깨지면_거둔다(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.on_message(A, MERGED)
    assert desk.view(A).prompt == "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?"
    assert desk.view(B).prompt is None  # 다른 Blender 창에는 뜨지 않는다
    desk.on_message(A, IDLE)  # Ctrl+Z 등으로 조건이 깨짐
    assert desk.view(A).prompt is None


def test_물음에_네를_누르면_다음_단계로_가고_물음을_닫는다(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.on_message(A, MERGED)
    desk.answer(A, True)
    assert desk.view(A) == StepView(SWORD, 3, SWORD.steps[2], None)


def test_물음에_아니요를_누르면_그_단계에_머물고_다시_묻지_않는다(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.on_message(A, MERGED)
    desk.answer(A, False)
    desk.on_message(A, IDLE)
    desk.on_message(A, MERGED)
    assert desk.view(A) == StepView(SWORD, 2, SWORD.steps[1], None)


def saved_at_join(tmp_path) -> None:
    """도우미를 껐다 켠 것처럼: 검 연습 과정 3단계(부품 합치기)까지 하고 BLEND에 저장해 둔다."""
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", ""))
    desk.choose(A, "sword")
    desk.next_step(A)
    desk.next_step(A)
    desk.on_message(A, IDLE, FileEvent("saved", BLEND))


def test_저장한_파일을_다시_열면_이어_할지_묻고_네면_그_단계로_간다(tmp_path):
    saved_at_join(tmp_path)
    desk = make(tmp_path)
    desk.on_message(B, IDLE, FileEvent("opened", BLEND))
    assert desk.view(B) == StepView(None, 0, None, "지난번 3단계(부품 합치기)까지 했어요. 이어 할까요?")
    desk.answer(B, True)
    assert desk.view(B) == StepView(SWORD, 3, SWORD.steps[2], None)


def test_이어_하기를_묻는_중에_다른_파일을_열면_물음을_거둔다(tmp_path):
    saved_at_join(tmp_path)
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.on_message(A, IDLE, FileEvent("opened", ""))
    assert desk.view(A) == StepView(None, 0, None, None)


def test_이어_하기를_묻는_중에_연습_과정을_고르면_덮어쓸지_묻고_네면_고른_것을_시작한다(tmp_path):
    saved_at_join(tmp_path)
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.choose(A, "shield")
    assert desk.view(A).prompt.startswith("이 파일의 진행 기록(검, 3단계)이 방패로 처음부터 바뀌어요.")
    desk.answer(A, True)
    assert desk.view(A) == StepView(SHIELD, 1, SHIELD.steps[0], None)
    desk.answer(A, True)  # 물음이 없을 때 온 답은 아무것도 하지 않는다
    assert desk.view(A).course == SHIELD


def test_다른_연습_과정을_고르면_바꿀지_묻고_네면_바꾼다(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.choose(A, "shield")
    assert desk.view(A) == StepView(SWORD, 2, SWORD.steps[1], "지금 진행(검, 2단계)은 저장 전 파일이라 남지 않아요. 방패로 바꿀까요?")
    desk.answer(A, True)
    assert desk.view(A) == StepView(SHIELD, 1, SHIELD.steps[0], None)


def test_바꿀지_묻는_물음에_아니요면_그대로_두고_앞에_떠_있던_물음이_다시_보인다(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.on_message(A, MERGED)
    desk.choose(A, "shield")
    desk.answer(A, False)
    assert desk.view(A) == StepView(SWORD, 2, SWORD.steps[1], "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?")
    desk.answer(A, True)
    assert desk.view(A).number == 3


def test_진행_관리의_알림은_대화에_붙일_글로_돌려준다(tmp_path):
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.choose(A, "shield")
    desk.next_step(A)
    desk.next_step(A)
    assert desk.view(A) == StepView(SHIELD, 0, None, None)  # 다 마침
    desk.on_message(A, IDLE, FileEvent("saved", BLEND))
    assert make(tmp_path).on_message(A, IDLE, FileEvent("opened", BLEND)) == [
        Line(LineKind.NOTICE, "이 파일에서 방패 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")
    ]


def test_뒤로와_건너뛰기(tmp_path):
    desk = at_blade_tip(tmp_path)
    desk.back(A)
    assert desk.view(A).number == 1
    desk.skip_to(A, "join")
    assert desk.view(A).number == 3


def test_닫힌_blender의_진행은_버리고_기록은_남는다(tmp_path):
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.choose(A, "sword")
    desk.keep({B})
    assert desk.view(A) == StepView(None, 0, None, None)  # 같은 창 번호가 다시 쓰여도 앞 진행을 물려받지 않는다
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    assert desk.view(A).prompt == "지난번 1단계(화면 돌려 보기)까지 했어요. 이어 할까요?"



# 조작 안내가 있는 연습 과정: 1단계는 조작 둘(둘째만 감지), 2단계는 조작 없음
GRAB = Operation("정육면체 고르기", "없음", "왼쪽 버튼 클릭", "화면 가운데 정육면체로 칼날을 만들어 볼게요. 정육면체를 눌러 보시겠어요?")
SCALE = Operation("크기 바꾸기", "Object > Transform > Scale", "S", "좋아요. 이제 S를 눌러 길게 늘여 보세요.", (("방금 조작", "transform.resize"),))
GUIDED = Course("guided", "단순한 검", (Step("blade-stretch", "정육면체를 늘려 칼날 모양 잡기", operations=(GRAB, SCALE)), Step("join", "부품 합치기")))
RESIZED = WorkState("OBJECT", None, (), "en_US", False, "", 3, "5.2.2", {}, ("transform.resize",))


def guided(tmp_path) -> CourseDesk:
    desk = CourseDesk([GUIDED], tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", ""))
    return desk


def test_연습_과정을_고르면_인사와_단계_시작과_첫_조작_안내를_대화에_붙인다(tmp_path):
    desk = guided(tmp_path)
    assert desk.choose(A, "guided") == [
        Line(LineKind.GUIDE, "단순한 검 연습 과정을 시작할게요."),
        Line(LineKind.GUIDE, "1단계, 정육면체를 늘려 칼날 모양 잡기예요."),
        Line(LineKind.GUIDE, GRAB.say),
    ]
    assert desk.view(A).done_button  # 감지 조건이 없는 조작이라 [했어요]로 넘어간다


def test_했어요를_누르면_다음_조작_안내만_붙고_감지되면_그다음으로(tmp_path):
    desk = guided(tmp_path)
    desk.choose(A, "guided")
    assert desk.next_operation(A) == [Line(LineKind.GUIDE, SCALE.say)]
    assert desk.on_message(A, IDLE) == []  # 같은 자리면 다시 말하지 않는다
    assert desk.on_message(A, RESIZED) == [Line(LineKind.GUIDE, "이 단계에서 할 조작은 다 했어요. 다 됐으면 '다음 단계'를 눌러 주세요.")]
    assert not desk.view(A).done_button


def test_다음_단계로_가면_단계_시작을_알리고_조작이_없으면_버튼으로_넘어가라고_한다(tmp_path):
    desk = guided(tmp_path)
    desk.choose(A, "guided")
    assert desk.next_step(A) == [
        Line(LineKind.GUIDE, "2단계, 부품 합치기예요."),
        Line(LineKind.GUIDE, "이 단계는 다 되면 '다음 단계'를 눌러 넘어가요."),
    ]
    assert desk.next_step(A) == [Line(LineKind.GUIDE, "단순한 검 연습 과정을 다 마쳤어요. 수고하셨어요!")]


def test_이어_하면_이어서_한다고_말하고_그_조작부터_안내한다(tmp_path):
    desk = guided(tmp_path)
    desk.on_message(A, IDLE, FileEvent("saved", BLEND))
    desk.choose(A, "guided")
    desk.next_operation(A)
    desk.on_message(A, IDLE, FileEvent("saved", BLEND))

    reopened = CourseDesk([GUIDED], tmp_path)
    reopened.on_message(A, IDLE, FileEvent("opened", BLEND))
    assert reopened.answer(A, True) == [
        Line(LineKind.GUIDE, "단순한 검 연습 과정을 이어서 할게요."),
        Line(LineKind.GUIDE, "1단계, 정육면체를 늘려 칼날 모양 잡기예요."),
        Line(LineKind.GUIDE, SCALE.say),
    ]


def test_뒤에_있는_blender의_말은_대화에_붙이지_않고_옮겨_오면_지금_자리를_알려_준다(tmp_path):
    desk = guided(tmp_path)  # A: 앞
    desk.on_message(B, IDLE, FileEvent("opened", ""), shown=False)
    assert desk.on_message(B, IDLE, shown=False) == []
    desk.choose(A, "guided")
    desk.next_operation(A)
    assert desk.switched_to(B) == []  # B는 연습 과정을 고르지 않았다(카드에 고르기 목록이 보임)
    assert desk.switched_to(A) == [
        Line(LineKind.GUIDE, "이 Blender는 단순한 검 1단계, 정육면체를 늘려 칼날 모양 잡기예요."),
        Line(LineKind.GUIDE, SCALE.say),
    ]


def test_뒤에_있을_때_생긴_알림은_옮겨_올_때_보인다(tmp_path):
    desk = CourseDesk([GUIDED, SHIELD], tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.choose(A, "shield")
    desk.next_step(A)
    desk.next_step(A)
    desk.on_message(A, IDLE, FileEvent("saved", BLEND))  # 방패를 다 마치고 저장

    other = CourseDesk([GUIDED, SHIELD], tmp_path)
    assert other.on_message(B, IDLE, FileEvent("opened", BLEND), shown=False) == []
    assert other.switched_to(B) == [Line(LineKind.NOTICE, "이 파일에서 방패 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")]
    assert other.switched_to(B) == []  # 한 번만


def test_단추로_답했을_때_진행_관리가_돌려준_알림도_대화_말로_나온다(tmp_path):
    # 3단계에서 저장한 뒤 버튼으로 마치고 저장하지 않음 → 다시 열면 "그 뒤 다 마친 상태까지…" 물음 → [네]
    saved_at_join(tmp_path)
    desk = make(tmp_path)
    desk.on_message(A, IDLE, FileEvent("opened", BLEND))
    desk.answer(A, True)
    desk.next_step(A)
    reopened = make(tmp_path)
    reopened.on_message(A, IDLE, FileEvent("opened", BLEND))
    assert reopened.view(A).prompt.endswith("그 뒤 다 마친 상태까지 진행하신 것 같아요. 파일에도 그만큼 되어 있나요?")
    assert reopened.answer(A, True) == [
        Line(LineKind.NOTICE, "이 파일에서 검 연습 과정을 다 마쳤어요. 다음엔 다른 연습 과정을 골라 볼까요?")
    ]
