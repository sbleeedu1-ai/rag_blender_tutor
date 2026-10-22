"""진행 관리(시험 경계 ②: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

작업 상태와 사용자 응답을 차례로 넣고, 진행 관리가 돌려준 물음(띄울 것·거둘 것)과 지금 단계만 본다.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from blender_tutor.conditions import CONDITIONS
from blender_tutor.progress import Ask, Progress, Step, Withdraw, WorkState, load_steps

COURSES = Path(__file__).resolve().parent.parent / "courses"

# 검 연습 과정을 줄인 단계 셋. 끝난 조건은 연습 과정 파일과 같은 '종류: 값' 꼴이다.
BLADE_TIP = Step("blade-tip", "칼끝 모으기", (("모드", "EDIT_MESH"), ("방금 조작", "mesh.merge")))
GUARD_ADD = Step("guard-add", "코등이 붙이기", (("물체 수 늘어남", 1),))
JOIN_PARTS = Step("join-parts", "부품 합치기", (("방금 조작", "object.join"),))

# 아무 조건도 맞지 않는 작업 상태. 테스트마다 몇 칸만 바꿔 쓴다.
IDLE = WorkState(
    mode="OBJECT",
    recent_operators=(),
    scene_object_count=3,
    modifiers=(),
    material_slot_count=1,
    scale=(1.0, 1.0, 1.0),
    dimensions=(2.0, 2.0, 2.0),
)
MERGED = replace(IDLE, mode="EDIT_MESH", recent_operators=("mesh.select_all", "mesh.merge"))


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
def test_끝난_조건_종류마다_맞고_틀림을_가른다(condition, met, not_met):
    step = Step("any", "아무 단계", (condition,))
    progress = Progress([step, GUARD_ADD])
    assert progress.on_state(replace(IDLE, **not_met)) == []
    assert [type(c) for c in progress.on_state(replace(IDLE, **met))] == [Ask]


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


def test_검사가_받아들이는_끝난_조건_종류는_모두_판정할_수_있다():
    values = {"모드": "OBJECT", "방금 조작": "object.join", "물체 수 늘어남": 1, "모디파이어": "BEVEL",
              "재질 슬롯 수": 2, "배율": [1, 1, 1], "크기 비율": 3}  # fmt: skip
    assert set(values) == set(CONDITIONS)
    for kind, value in values.items():
        Progress([Step("any", "아무 단계", ((kind, value),))]).on_state(IDLE)  # 판정 규칙이 값과 작업 상태로 오류 없이 돈다


def test_저장소의_검_연습_과정을_읽어_첫_단계부터_시작한다():
    steps = load_steps(COURSES / "sword.yaml")
    assert [s.label for s in steps[:3]] == ["view-navigate", "interface-language", "blade-stretch"]
    assert Progress(steps).step.label == "view-navigate"
