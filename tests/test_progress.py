"""진행 관리(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

작업 상태와 사용자 응답을 차례로 넣고, 진행 관리가 돌려준 물음(띄울 것·거둘 것)과 지금 단계·끝낸 조작 수만 본다.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from blender_tutor.conditions import CONDITIONS
from blender_tutor.progress import Ask, Operation, Progress, Step, Withdraw, load_courses, load_steps
from blender_tutor.work_state import ActiveObject, View, WorkState

COURSES = Path(__file__).resolve().parent.parent / "courses"

# 검 연습 과정을 줄인 단계 셋. 끝난 조건은 연습 과정 파일과 같은 '종류: 값' 꼴이다.
BLADE_TIP = Step("blade-tip", "칼끝 모으기", (("모드", "EDIT_MESH"), ("방금 조작", "mesh.merge")))
GUARD_ADD = Step("guard-add", "코등이 붙이기", (("물체 수 늘어남", 1),))
JOIN_PARTS = Step("join-parts", "부품 합치기", (("방금 조작", "object.join"),))

# 아무 조건도 맞지 않는 작업 상태. 테스트마다 몇 칸만 바꿔 쓴다.
IDLE = WorkState(
    mode="OBJECT",
    active_object=ActiveObject("Cube", "MESH", (), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0), 1),
    selected_objects=("Cube",),
    language="en_US",
    translate_interface=False,
    file_path="",
    scene_object_count=3,
    blender_version="5.2.2",
    edit_selected={},
    recent_operators=(),
    view=View(18.4, (0.71, 0.44, 0.29, 0.46), (0.0, 0.0, 0.0)),
)
MERGED = replace(IDLE, mode="EDIT_MESH", recent_operators=("mesh.select_all", "mesh.merge"))


def with_object(**changes) -> WorkState:
    """IDLE에서 활성 물체 칸 몇 개만 바꾼 작업 상태."""
    return replace(IDLE, active_object=replace(IDLE.active_object, **changes))


def test_끝난_조건이_맞으면_다음_단계로_갈지_묻는다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    assert progress.on_state(IDLE) == []
    assert progress.on_state(MERGED) == [Ask("blade-tip", "'칼끝 모으기' 단계를 끝낸 것 같아요. 다음 단계(코등이 붙이기)로 갈까요?")]


def test_답하기_전에는_같은_물음을_또_띄우지_않는다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.on_state(MERGED)
    assert progress.on_state(replace(MERGED, scene_object_count=4)) == []


def test_답하기_전에_조건이_깨지면_물음을_거둔다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.on_state(MERGED)
    assert progress.on_state(replace(MERGED, mode="OBJECT")) == [Withdraw("blade-tip")]
    assert progress.step == BLADE_TIP


def test_네라고_답하면_다음_단계로_간다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.on_state(MERGED)
    assert progress.on_answer(True) == []
    assert progress.step == GUARD_ADD


def test_한_번_거절하면_그_단계에서는_다시_묻지_않는다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.on_state(MERGED)
    assert progress.on_answer(False) == []
    assert progress.step == BLADE_TIP
    # 조건이 깨졌다가 다시 맞아도 묻지 않는다.
    assert progress.on_state(IDLE) == []
    assert progress.on_state(MERGED) == []


def test_조건이_깨져_물음을_거둔_뒤_다시_맞으면_또_묻는다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.on_state(MERGED)
    progress.on_state(IDLE)
    assert [type(c) for c in progress.on_state(MERGED)] == [Ask]


def test_물음이_없을_때의_응답은_무시한다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    assert progress.on_answer(True) == []
    assert progress.step == BLADE_TIP


def test_물체_수는_단계_시작_때보다_늘었는지로_본다():
    progress = Progress([BLADE_TIP, GUARD_ADD, JOIN_PARTS])
    progress.on_state(MERGED)  # 물체 3개
    progress.on_answer(True)  # 코등이 붙이기 시작: 3개를 기억
    assert progress.on_state(replace(IDLE, scene_object_count=3)) == []
    assert [type(c) for c in progress.on_state(replace(IDLE, scene_object_count=4))] == [Ask]


def test_단계_시작_뒤_처음_온_작업_상태의_물체_수를_시작_때_수로_삼는다():
    progress = Progress([GUARD_ADD, JOIN_PARTS])
    assert progress.on_state(replace(IDLE, scene_object_count=4)) == []
    assert [type(c) for c in progress.on_state(replace(IDLE, scene_object_count=5))] == [Ask]


def test_다음_단계_버튼은_조건과_상관없이_넘어간다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    assert progress.next_step() == []
    assert progress.step == GUARD_ADD


def test_물음이_떠_있을_때_버튼으로_넘어가면_물음을_거둔다():
    progress = Progress([BLADE_TIP, GUARD_ADD, JOIN_PARTS])
    progress.on_state(MERGED)
    assert progress.next_step() == [Withdraw("blade-tip")]
    assert progress.on_answer(True) == []  # 늦게 온 응답은 무시
    assert progress.step == GUARD_ADD


def test_원하는_단계로_건너뛰고_뒤로_갈_수_있다():
    progress = Progress([BLADE_TIP, GUARD_ADD, JOIN_PARTS])
    assert progress.skip_to("join-parts") == []
    assert progress.step == JOIN_PARTS
    assert progress.back() == []
    assert progress.step == GUARD_ADD


def test_첫_단계에서_뒤로_가기는_그대로_머문다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    assert progress.back() == []
    assert progress.step == BLADE_TIP


def test_건너뛴_단계는_그때부터_조건을_본다():
    progress = Progress([BLADE_TIP, GUARD_ADD, JOIN_PARTS])
    progress.on_state(IDLE)
    progress.skip_to("join-parts")
    assert progress.on_state(MERGED) == []  # 칼끝 모으기 조건은 이제 보지 않는다
    joined = replace(IDLE, recent_operators=("object.select_all", "object.join"))
    assert [type(c) for c in progress.on_state(joined)] == [Ask]


def test_마지막_단계에서는_연습_과정을_마칠지_묻고_네면_끝난다():
    progress = Progress([BLADE_TIP])
    assert progress.on_state(MERGED) == [Ask("blade-tip", "'칼끝 모으기' 단계를 끝낸 것 같아요. 연습 과정을 마칠까요?")]
    progress.on_answer(True)
    assert progress.step is None
    assert progress.on_state(IDLE) == []
    assert progress.next_step() == []
    assert progress.step is None


def test_마친_뒤에도_뒤로_가면_마지막_단계로_돌아온다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    progress.next_step()
    progress.next_step()
    assert progress.back() == []
    assert progress.step == GUARD_ADD


@pytest.mark.parametrize(
    ("condition", "met", "not_met"),
    [
        (("모디파이어", "BEVEL"), {"modifiers": ("MIRROR", "BEVEL")}, {"modifiers": ("MIRROR",)}),
        (("재질 슬롯 수", 2), {"material_slot_count": 3}, {"material_slot_count": 1}),  # 2개 이상
        # 배율은 Blender가 계산한 소수라 아주 작은 차이는 같다고 본다.
        (("배율", [1, 1, 1]), {"scale": (1.0, 0.9999999, 1.0)}, {"scale": (1.0, 1.0, 0.5)}),
        # 크기 비율: 가장 긴 축이 두 번째로 긴 축의 n배 이상(축 순서는 상관없다).
        (("크기 비율", 3), {"dimensions": (0.3, 0.1, 0.9)}, {"dimensions": (0.4, 0.1, 0.9)}),
    ],
)
def test_활성_물체_조건_종류마다_맞고_틀림을_가른다(condition, met, not_met):
    step = Step("any", "아무 단계", (condition,))
    progress = Progress([step, GUARD_ADD])
    assert progress.on_state(with_object(**not_met)) == []
    assert [type(c) for c in progress.on_state(with_object(**met))] == [Ask]


@pytest.mark.parametrize("condition", [("모디파이어", "BEVEL"), ("재질 슬롯 수", 1), ("배율", [1, 1, 1]), ("크기 비율", 1)])
def test_활성_물체가_없으면_활성_물체_조건은_맞지_않는다(condition):
    progress = Progress([Step("any", "아무 단계", (condition,)), GUARD_ADD])
    assert progress.on_state(replace(IDLE, active_object=None)) == []
    assert [type(c) for c in progress.on_state(with_object(modifiers=("BEVEL",)))] == [Ask]


def test_적힌_끝난_조건이_모두_맞아야_묻는다():
    progress = Progress([BLADE_TIP, GUARD_ADD])
    assert progress.on_state(replace(MERGED, mode="OBJECT")) == []
    assert progress.on_state(replace(MERGED, recent_operators=("mesh.select_all",))) == []


def test_끝난_조건이_없는_단계는_묻지_않는다():
    progress = Progress([Step("free", "자유 단계"), GUARD_ADD])
    assert progress.on_state(MERGED) == []


def test_연습_과정_파일에서_공통_준비_단계부터_차례로_읽는다(tmp_path):
    (tmp_path / "_common.yaml").write_text(
        "구간:\n  - 단계:\n      - {이름표: view-navigate, 이름: 화면 돌려 보기}\n", encoding="utf-8"
    )
    (tmp_path / "sword.yaml").write_text(
        """\
먼저 할 것: _common.yaml
구간:
  - 단계:
      - 이름표: blade-tip
        이름: 칼끝 모으기
        끝난 조건:
          - 모드: EDIT_MESH
          - 방금 조작: mesh.merge
  - 단계:
      - 이름표: export-gltf
        이름: 내보내기
""",
        encoding="utf-8",
    )
    assert [(s.label, s.name, s.conditions) for s in load_steps(tmp_path / "sword.yaml")] == [
        ("view-navigate", "화면 돌려 보기", ()),
        ("blade-tip", "칼끝 모으기", (("모드", "EDIT_MESH"), ("방금 조작", "mesh.merge"))),
        ("export-gltf", "내보내기", ()),
    ]


def test_단계마다_먼저_볼_소제목과_답변_모델에_넘길_단계_내용을_읽는다(tmp_path):
    (tmp_path / "sword.yaml").write_text(
        """\
구간:
  - 단계:
      - 이름표: blade-tip
        이름: 칼끝 모으기
        목표 모양: 칼날 맨 위가 한 점으로 모였다.
        참고 치수: 칼날 길이의 5분의 1쯤.
        쉬운 설명: 맨 위 꼭짓점 넷을 골라 가운데로 모은다.
        조작:
          - 설명: 편집 모드로 들어가기
            메뉴: 없음
            단축키: Tab
          - 설명: 가운데로 모으기
            메뉴: Mesh > Merge > At Center
            단축키: M
        먼저 볼 소제목:
          - modeling/meshes/editing/mesh/merge.html#merge
        끝난 조건:
          - 모드: EDIT_MESH
        자주 막히는 곳:
          - 뒤쪽 꼭짓점이 안 골라지면 X-ray를 켠다.
      - 이름표: export-gltf
        이름: 내보내기
""",
        encoding="utf-8",
    )
    tip, export = load_steps(tmp_path / "sword.yaml")
    assert tip.manual == ("modeling/meshes/editing/mesh/merge.html#merge",)
    assert tip.guide == (
        "이름: 칼끝 모으기\n"
        "목표 모양: 칼날 맨 위가 한 점으로 모였다.\n"
        "참고 치수: 칼날 길이의 5분의 1쯤.\n"
        "쉬운 설명: 맨 위 꼭짓점 넷을 골라 가운데로 모은다.\n"
        "조작:\n"
        "- 편집 모드로 들어가기 (메뉴: 없음, 단축키: Tab)\n"
        "- 가운데로 모으기 (메뉴: Mesh > Merge > At Center, 단축키: M)\n"
        "자주 막히는 곳:\n"
        "- 뒤쪽 꼭짓점이 안 골라지면 X-ray를 켠다."
    )
    assert export.guide == "이름: 내보내기"  # 다른 단계 내용은 섞이지 않는다
    assert tip.operations == (Operation("편집 모드로 들어가기", "없음", "Tab"), Operation("가운데로 모으기", "Mesh > Merge > At Center", "M"))
    assert export.operations == ()


def test_검사가_받아들이는_끝난_조건_종류는_모두_판정할_수_있다():
    values = {"모드": "OBJECT", "방금 조작": "object.join", "물체 수 늘어남": 1, "모디파이어": "BEVEL",
              "재질 슬롯 수": 2, "배율": [1, 1, 1], "크기 비율": 3, "화면": "확대",
              "배율 늘어남": "Z", "배율 줄어듦": ["X", "Y"], "위치 늘어남": "X", "위치 줄어듦": "Z"}  # fmt: skip
    assert set(values) == set(CONDITIONS)
    for kind, value in values.items():
        Progress([Step("any", "아무 단계", ((kind, value),))]).on_state(IDLE)  # 판정 규칙이 값과 작업 상태로 오류 없이 돈다


def test_저장소의_검_연습_과정을_읽어_첫_단계부터_시작한다():
    steps = load_steps(COURSES / "sword.yaml")
    assert [s.label for s in steps[:3]] == ["view-navigate", "interface-language", "blade-stretch"]
    assert Progress(steps).step.label == "view-navigate"


def test_연습_과정_폴더에서_공통_준비_파일을_뺀_연습_과정을_이름_차례로_읽는다():
    courses = load_courses(COURSES)
    assert [course.label for course in courses] == ["sword"]
    assert courses[0].steps[0].label == "view-navigate"  # 공통 준비는 각 연습 과정 맨 앞에 들어 있다


# 조작 셋을 차례로 안내하는 단계. 둘째 조작만 감지 조건이 있다(나머지는 [했어요]로 넘어감).
STRETCH = Step("blade-stretch", "칼날 모양 잡기", operations=(
    Operation("정육면체 고르기", "없음", "왼쪽 버튼 클릭", "정육면체를 눌러 보세요."),
    Operation("크기 바꾸기", "Object > Transform > Scale", "S", "S로 늘려 보세요.", (("방금 조작", "transform.resize"),)),
    Operation("옆 패널 보기", "View > Sidebar", "N", "N으로 치수를 보세요."),
))
RESIZED = replace(IDLE, recent_operators=("transform.resize",))


def test_조작은_첫_조작부터_차례로_안내하고_했어요를_누르면_다음_조작으로_간다():
    progress = Progress([STRETCH, JOIN_PARTS])
    assert progress.operations_done == 0
    progress.next_operation()
    assert progress.operations_done == 1


def test_감지_조건이_맞으면_다음_조작으로_간다():
    progress = Progress([STRETCH, JOIN_PARTS], operations_done=1)
    progress.on_state(IDLE)
    progress.on_state(RESIZED)
    assert progress.operations_done == 2


def test_방금_조작_감지는_그_조작을_안내한_뒤에_새로_한_것만_센다():
    # S로 이미 한 번 늘린 뒤(기록에 transform.resize가 남아 있음) 같은 조작을 다시 안내하는 걸음
    progress = Progress([STRETCH, JOIN_PARTS], operations_done=1)
    progress.on_state(RESIZED)  # 이 걸음을 시작할 때 이미 있던 기록
    progress.on_state(replace(RESIZED, selected_objects=()))  # 다른 것만 바뀜
    assert progress.operations_done == 1
    progress.on_state(replace(RESIZED, recent_operators=("transform.resize", "transform.resize")))
    assert progress.operations_done == 2


def test_한_번_바뀐_상태로는_조작_하나만_넘어간다():
    twice = replace(STRETCH, operations=(STRETCH.operations[1], STRETCH.operations[1]))
    progress = Progress([twice])
    progress.on_state(IDLE)
    progress.on_state(RESIZED)
    assert progress.operations_done == 1


def test_마지막_조작_뒤에는_했어요가_아무것도_하지_않고_단계가_바뀌면_첫_조작부터():
    progress = Progress([STRETCH, JOIN_PARTS], operations_done=3)
    progress.next_operation()
    assert progress.operations_done == 3
    progress.next_step()
    assert progress.operations_done == 0
    progress.back()
    assert progress.operations_done == 0


def test_조작마다_안내_말과_감지_조건을_읽는다(tmp_path):
    (tmp_path / "sword.yaml").write_text(
        """\
구간:
  - 단계:
      - 이름표: blade-stretch
        이름: 칼날 모양 잡기
        조작:
          - 설명: 크기 바꾸기
            메뉴: Object > Transform > Scale
            단축키: S
            안내: S로 늘려 보세요.
            감지:
              - 방금 조작: transform.resize
          - 설명: 옆 패널 보기
            메뉴: View > Sidebar
            단축키: N
            안내: N으로 치수를 보세요.
""",
        encoding="utf-8",
    )
    [step] = load_steps(tmp_path / "sword.yaml")
    assert step.operations == (
        Operation("크기 바꾸기", "Object > Transform > Scale", "S", "S로 늘려 보세요.", (("방금 조작", "transform.resize"),)),
        Operation("옆 패널 보기", "View > Sidebar", "N", "N으로 치수를 보세요."),
    )


# 공통 준비 1단계를 줄인 것. 화면 조작은 조작 기록에 남지 않아 시점 값으로 알아챈다(2026-10-23 사용자가 직접 해 본 결과).
NAVIGATE = Step("view-navigate", "화면 돌리고 당기고 옮겨 보기", operations=tuple(
    Operation(name, "없음", "없음", f"{name}해 보세요.", (("화면", value),))
    for name, value in (("돌리기", "돌림"), ("확대", "확대"), ("축소", "축소"), ("옮기기", "옮김"), ("전체 담기", "전체"))
))


def with_view(**changes) -> WorkState:
    """IDLE에서 시점 칸 몇 개만 바꾼 작업 상태."""
    return replace(IDLE, view=replace(IDLE.view, **changes))


ORBITED = with_view(rotation=(0.77, 0.48, 0.22, 0.35))
ZOOMED_IN = replace(ORBITED, view=replace(ORBITED.view, distance=10.6))
ZOOMED_OUT = replace(ZOOMED_IN, view=replace(ZOOMED_IN.view, distance=15.3))
PANNED = replace(ZOOMED_OUT, view=replace(ZOOMED_OUT.view, center=(1.0, 0.0, 0.0)))
FRAMED = replace(PANNED, view=replace(PANNED.view, distance=16.3, center=(3.7, -3.0, 3.0)))  # Home


def test_화면_조작은_그_조작을_안내한_때보다_시점이_어떻게_바뀌었나로_알아챈다():
    progress = Progress([NAVIGATE], latest=IDLE)
    for state, done in ((ORBITED, 1), (ZOOMED_IN, 2), (ZOOMED_OUT, 3), (PANNED, 4), (FRAMED, 5)):
        progress.on_state(state)
        assert progress.operations_done == done


@pytest.mark.parametrize(
    ("value", "state"),
    [
        ("확대", with_view(distance=19.0)),  # 거리가 늘면 축소
        ("확대", with_view(distance=10.0, center=(3.7, -3.0, 3.0))),  # 중심도 바뀌면 Home(장면 전체 담기)
        ("축소", with_view(distance=10.0)),
        ("전체", with_view(center=(1.0, 0.0, 0.0))),  # 중심만 바뀌면 옮기기
        ("돌림", with_view(distance=18.4004)),  # 아주 작은 흔들림은 바뀐 것이 아니다
        ("돌림", replace(IDLE, view=None)),  # 3D 화면이 없어짐
    ],
)
def test_화면_감지는_다른_화면_조작이나_작은_흔들림으로는_넘어가지_않는다(value, state):
    step = Step("any", "아무 단계", operations=(Operation("화면", "없음", "없음", "해 보세요.", (("화면", value),)),))
    progress = Progress([step], latest=IDLE)
    progress.on_state(state)
    assert progress.operations_done == 0


# 칼날 1단계를 줄인 것. S로 크기를 바꾼 방향은 조작 이름(transform.resize)에 없어 활성 물체 배율로 알아챈다.
STRETCH_AXES = Step("blade-stretch", "칼날 모양 잡기", operations=(
    Operation("길게 늘이기", "Object > Transform > Scale", "S", "S Z로 늘여 보세요.", (("배율 늘어남", "Z"),)),
    Operation("폭 줄이기", "Object > Transform > Scale", "S", "S X로 좁혀 보세요.", (("배율 줄어듦", "X"),)),
    Operation("두께 줄이기", "Object > Transform > Scale", "S", "S Y로 얇게 해 보세요.", (("배율 줄어듦", "Y"),)),
))


def test_크기_바꾸기는_그_조작을_안내한_때보다_어느_방향_배율이_바뀌었나로_알아챈다():
    progress = Progress([STRETCH_AXES], latest=IDLE)
    for scale, done in (((1.0, 1.0, 7.0), 1), ((0.5, 1.0, 7.0), 2), ((0.5, 0.2, 7.0), 3)):
        progress.on_state(with_object(scale=scale))
        assert progress.operations_done == done


@pytest.mark.parametrize(
    ("condition", "state"),
    [
        (("배율 늘어남", "Z"), with_object(scale=(1.0, 1.0, 0.5))),  # 반대 방향
        (("배율 늘어남", "Z"), with_object(scale=(2.0, 1.0, 1.0))),  # 다른 방향
        (("배율 늘어남", "Z"), with_object(name="Cylinder", scale=(1.0, 1.0, 2.0))),  # 배율이 다른 물체를 골랐을 뿐
        (("배율 늘어남", "Z"), replace(IDLE, active_object=None)),
        (("배율 줄어듦", ["Y", "Z"]), with_object(scale=(1.0, 0.2, 1.0))),  # 둘 다 줄어야 한다
        (("배율 줄어듦", "X"), with_object(scale=(0.9999, 1.0, 1.0))),  # 아주 작은 흔들림
    ],
)
def test_배율_감지는_다른_방향이나_다른_물체로는_넘어가지_않는다(condition, state):
    step = Step("any", "아무 단계", operations=(Operation("크기", "없음", "S", "해 보세요.", (condition,)),))
    progress = Progress([step], latest=IDLE)
    progress.on_state(state)
    assert progress.operations_done == 0


def test_배율_감지는_여러_방향을_함께_볼_수_있다():
    step = Step("any", "아무 단계", operations=(Operation("크기", "없음", "S", "해 보세요.", (("배율 줄어듦", ["Y", "Z"]),)),))
    progress = Progress([step], latest=IDLE)
    progress.on_state(with_object(scale=(1.5, 0.2, 0.3)))
    assert progress.operations_done == 1


def test_옮기기는_그_조작을_안내한_때보다_어느_방향으로_옮겼나로_알아챈다():
    # 코등이를 "G 다음 Z로 칼날 아래 끝까지 내려" 붙이는 조작. 얼마나 옮겼는지(끝까지 붙었나)는 보지 않는다
    step = Step("guard-add", "코등이 붙이기", operations=(
        Operation("옮기기", "Object > Transform > Move", "G", "G Z로 내려 보세요.", (("위치 줄어듦", "Z"),)),
    ))
    progress = Progress([step], latest=IDLE)
    progress.on_state(with_object(location=(1.5, 0.0, 0.0)))  # 옆으로만 옮김
    assert progress.operations_done == 0
    progress.on_state(with_object(location=(1.5, 0.0, 2.0)))  # 위로 올림
    assert progress.operations_done == 0
    progress.on_state(with_object(location=(1.5, 0.0, -1.0)))  # 아래로 내림(조금만 내려도 넘어간다)
    assert progress.operations_done == 1


def test_크기를_조절하는_동안에는_넘어가지_않고_확정한_뒤에_넘어간다():
    # S를 누르면 Blender는 확정 전에도 마우스대로 배율을 바꿔 보인다(2026-10-23 사용자 눈 확인에서 찾음)
    progress = Progress([STRETCH_AXES], latest=IDLE)
    adjusting = replace(with_object(scale=(1.0, 1.0, 1.3)), running_operators=("transform.resize",))
    progress.on_state(adjusting)
    assert progress.operations_done == 0
    progress.on_state(with_object(scale=(1.0, 1.0, 3.5)))  # 클릭으로 확정
    assert progress.operations_done == 1


def test_화면을_끄는_동안에는_단계_끝_물음도_기다린다():
    step = Step("view", "화면 돌려 보기", (("화면", "돌림"),))
    progress = Progress([step, JOIN_PARTS], latest=IDLE)
    assert progress.on_state(replace(ORBITED, running_operators=("view3d.rotate",))) == []
    assert progress.on_state(ORBITED) == [Ask("view", "'화면 돌려 보기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?")]


def test_다른_조작이_진행_중이어도_감지는_멈추지_않는다():
    # 다른 애드온이 늘 켜 두는 조작이 있어도 감지가 계속 기다리지 않게, 크기·옮기기·화면 조작만 기다린다
    progress = Progress([STRETCH_AXES], latest=IDLE)
    progress.on_state(replace(with_object(scale=(1.0, 1.0, 3.5)), running_operators=("screencast.keys",)))
    assert progress.operations_done == 1


def test_처음_받은_상태가_조작_중이어도_그때를_기준으로_삼는다():
    progress = Progress([STRETCH_AXES])  # 고르기 전에 받아 둔 작업 상태가 없을 때
    progress.on_state(replace(with_object(scale=(1.0, 1.0, 1.3)), running_operators=("transform.resize",)))
    progress.on_state(with_object(scale=(1.0, 1.0, 3.5)))
    assert progress.operations_done == 1


# 끝난 조건(크기 비율 3)이 첫 조작(길게 늘이기)만으로 맞아 버리는 단계(2026-10-23 사용자 눈 확인에서 찾음)
STRETCH_WITH_END = replace(STRETCH_AXES, conditions=(("크기 비율", 3),))
STRETCHED = with_object(scale=(1.0, 1.0, 3.5), dimensions=(2.0, 2.0, 7.0))


def test_조작을_다_끝내기_전에는_끝난_조건이_맞아도_묻지_않는다():
    progress = Progress([STRETCH_WITH_END, JOIN_PARTS], latest=IDLE)
    assert progress.on_state(STRETCHED) == []
    assert progress.operations_done == 1


def test_마지막_조작을_했어요로_끝냈을_때_끝난_조건이_맞아_있으면_바로_묻는다():
    progress = Progress([STRETCH_WITH_END, JOIN_PARTS], latest=IDLE)
    progress.on_state(STRETCHED)
    progress.next_operation()
    assert progress.next_operation() == [
        Ask("blade-stretch", "'칼날 모양 잡기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?")
    ]


def test_마지막_조작이_감지로_끝나고_끝난_조건이_맞으면_그때_묻는다():
    one = replace(STRETCH_WITH_END, operations=STRETCH_WITH_END.operations[:1])  # 길게 늘이기 하나뿐
    progress = Progress([one, JOIN_PARTS], latest=IDLE)
    assert progress.on_state(STRETCHED) == [
        Ask("blade-stretch", "'칼날 모양 잡기' 단계를 끝낸 것 같아요. 다음 단계(부품 합치기)로 갈까요?")
    ]


def test_앞_조작의_휠이_더_굴러_거리가_바뀐_뒤에도_옮기기를_알아챈다():
    # 휠 여러 칸 중 첫 칸에서 축소가 판정되면, 나머지 칸이 굴러 거리가 기준과 달라진다(2026-10-23 사용자 눈 확인에서 찾음)
    step = Step("view-navigate", "화면 익히기", operations=NAVIGATE.operations[2:4])  # 축소, 옮기기
    progress = Progress([step], latest=ZOOMED_IN)
    first_notch = replace(ZOOMED_IN, view=replace(ZOOMED_IN.view, distance=15.0))
    progress.on_state(first_notch)
    assert progress.operations_done == 1
    rolled_on = replace(first_notch, view=replace(first_notch.view, distance=18.4))
    progress.on_state(rolled_on)
    progress.on_state(replace(rolled_on, view=replace(rolled_on.view, center=(1.0, 0.0, 0.0))))  # Shift + 가운데 끌기
    assert progress.operations_done == 2
