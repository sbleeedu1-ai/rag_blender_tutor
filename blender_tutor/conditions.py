"""끝난 조건·감지 조건: 종류마다 '값의 꼴'과 '맞는지 판정하는 규칙'을 한곳에 둔다.

단계의 끝난 조건과 조작의 감지 조건은 같은 종류 표를 쓴다(티켓 27). 규칙은 지금 작업 상태와 기준 작업 상태를 받는다:
끝난 조건은 그 단계를 시작할 때, 감지 조건은 그 조작을 안내하기 시작할 때의 작업 상태가 기준이다.
연습 과정 파일 검사(course_check)는 값의 꼴을, 진행 관리(progress)는 판정을 가져다 쓴다.
새 종류를 더할 때는 이 파일의 CONDITIONS 표에 한 줄만 더한다.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from blender_tutor.work_state import ActiveObject, View, WorkState


@dataclass(frozen=True)
class ConditionKind:
    """조건 종류 하나(끝난 조건·감지 조건 공통)."""

    is_valid: Callable[[object], bool]  # 연습 과정 파일에 적힌 값이 맞는 꼴인가
    hint: str  # 값의 꼴이 틀렸을 때 보여 줄 설명
    is_met: Callable[[object, WorkState, WorkState], bool]  # (값, 지금 작업 상태, 기준 작업 상태) → 맞으면 참


# Blender 5.2 context.mode 값 목록(2026-10-20 설치본에서 뽑음). 애드온이 보내는 '모드' 칸과 같은 이름이다.
# 목록에만 남은 옛 그리스 펜슬 이름(EDIT_GPENCIL 등 5개)은 뺐다. 5.2에서 모드를 바꿔 보면 새 이름(EDIT_GREASE_PENCIL 등)만 나온다.
MODES = (
    "OBJECT", "EDIT_MESH", "EDIT_CURVE", "EDIT_CURVES", "EDIT_SURFACE", "EDIT_TEXT", "EDIT_ARMATURE",
    "EDIT_METABALL", "EDIT_LATTICE", "EDIT_GREASE_PENCIL", "EDIT_POINTCLOUD", "POSE", "SCULPT",
    "PAINT_WEIGHT", "PAINT_VERTEX", "PAINT_TEXTURE", "PARTICLE", "SCULPT_CURVES", "PAINT_GREASE_PENCIL",
    "SCULPT_GREASE_PENCIL", "WEIGHT_GREASE_PENCIL", "VERTEX_GREASE_PENCIL",
)  # fmt: skip

OPERATOR = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")  # Blender 조작 이름(예: mesh.merge)
MODIFIER = re.compile(r"[A-Z][A-Z0-9_]*")  # 모디파이어 종류 이름(예: BEVEL)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _of_active(rule: Callable[[object, ActiveObject], bool]) -> Callable[[object, WorkState, WorkState], bool]:
    """활성 물체를 보는 규칙. 활성 물체가 없으면 맞지 않는다."""
    return lambda value, state, start: state.active_object is not None and rule(value, state.active_object)


def _scale_is(value, active: ActiveObject) -> bool:
    # Blender가 계산한 소수라 0.9999999처럼 아주 작은 차이는 같다고 본다.
    return all(math.isclose(have, want, rel_tol=1e-3, abs_tol=1e-3) for have, want in zip(active.scale, value))


def _size_ratio_is(value, active: ActiveObject) -> bool:
    # 치수는 절대 숫자가 아니라 비율로만 본다: 가장 긴 축 ≥ 두 번째로 긴 축 × n.
    longest, second, _ = sorted(active.dimensions, reverse=True)
    return longest > 0 and longest >= second * value


def _close(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    # 손을 뗀 화면은 값이 그대로지만, 계산 소수의 아주 작은 차이는 같다고 본다.
    return all(math.isclose(x, y, rel_tol=1e-4, abs_tol=1e-3) for x, y in zip(a, b))


# 화면 조작 → (지금 시점, 기준 시점)으로 맞는지. 2026-10-23 사용자가 직접 해 본 결과: 휠·Ctrl+가운데 끌기·메뉴 Zoom·돋보기는
# 거리만, 가운데 끌기·색 공은 각도만, Shift+가운데 끌기·손바닥은 중심만, Home은 거리와 중심을 함께 바꾼다.
VIEW_CHANGES: dict[str, Callable[[View, View], bool]] = {
    "확대": lambda now, start: now.distance < start.distance and not _close((now.distance,), (start.distance,)) and _close(now.center, start.center),
    "축소": lambda now, start: now.distance > start.distance and not _close((now.distance,), (start.distance,)) and _close(now.center, start.center),
    "돌림": lambda now, start: not _close(now.rotation, start.rotation),
    # 옮김은 중심만 본다. 앞 조작(휠 여러 칸)이 판정 뒤에도 굴러 거리가 기준과 달라질 수 있어서다(2026-10-23 눈 확인).
    # 그래서 Home도 옮김으로 맞지만, 공통 준비에서는 옮기기 다음이 Home이라 순서상 괜찮다.
    "옮김": lambda now, start: not _close(now.center, start.center),
    "전체": lambda now, start: not _close(now.center, start.center) and not _close((now.distance,), (start.distance,)),
}


AXES = ("X", "Y", "Z")


def _is_axes(value: object) -> bool:
    """방향 하나("Z") 또는 겹치지 않는 방향 목록(["Y", "Z"])."""
    axes = value if isinstance(value, list) else [value]
    return bool(axes) and all(axis in AXES for axis in axes) and len(set(axes)) == len(axes)


def _changed(field: str, grew: bool | None) -> Callable[[object, WorkState, WorkState], bool]:
    """기준 때보다 같은 활성 물체의 배율·위치(field)가 그 방향으로 모두 커졌나(grew 참) / 작아졌나(거짓) / 그대로인가(None).

    '그대로'는 한 축만 바꾸는 조작에 함께 적는다: S Z 중 가운데 버튼으로 축이 바뀐 채 확정해도 Z만 보면 넘어가서다
    (2026-10-23 사용자 눈 확인). 잘못 바꾼 뒤에는 Ctrl+Z로 되돌려야 다시 맞는다.

    S·G 다음 X·Y·Z로 방향을 정해도 조작 이름은 transform.resize·transform.translate 하나라 방향을 모른다.
    값으로 보면 옆 패널(N)에서 숫자로 고친 것(조작 기록에 남지 않음)도 잡힌다. 다른 물체를 골라 값이 달라진 것은
    치지 않는다. 얼마나 바뀌었는지(예: 칼날 아래 끝까지 붙였나)는 보지 않는다: 그러려면 단계를 넘어 "이 물체가
    코등이"를 따라가야 하는데, 지우고 다시 만들기·복제·되돌리기·합치기에서 어긋나기 쉬워서다(2026-10-23 사용자 결정).
    """

    def rule(value, state: WorkState, start: WorkState) -> bool:
        now, before = state.active_object, start.active_object
        if now is None or before is None or now.name != before.name:
            return False
        for axis in value if isinstance(value, list) else [value]:
            have, had = getattr(now, field)[AXES.index(axis)], getattr(before, field)[AXES.index(axis)]
            same = math.isclose(have, had, rel_tol=1e-3, abs_tol=1e-3)
            if same != (grew is None) or (grew is not None and (have > had) != grew):
                return False
        return True

    return rule


def _view_is(value, state: WorkState, start: WorkState) -> bool:
    """기준 때보다 시점이 그 화면 조작처럼 바뀌었나. 어느 쪽이든 3D 화면이 없으면 맞지 않는다."""
    return state.view is not None and start.view is not None and VIEW_CHANGES[value](state.view, start.view)


# 끝난 조건 종류(명세에서 정한 7가지와 티켓 27에서 더한 배율·위치 늘어남/줄어듦, 배율 그대로, 화면). 판정은 AI 없이 이 규칙으로만 한다.
CONDITIONS: dict[str, ConditionKind] = {
    "모드": ConditionKind(
        lambda v: v in MODES,
        "Blender 모드 이름입니다(예: OBJECT, EDIT_MESH).",
        lambda v, state, start: state.mode == v,
    ),
    "방금 조작": ConditionKind(
        lambda v: isinstance(v, str) and bool(OPERATOR.fullmatch(v)),
        "Blender 조작 이름입니다(예: mesh.merge).",
        lambda v, state, start: v in state.recent_operators,
    ),
    "물체 수 늘어남": ConditionKind(
        _is_positive_int,
        "1 이상의 정수입니다(기준 때보다 몇 개 늘었나).",
        lambda v, state, start: state.scene_object_count >= start.scene_object_count + v,
    ),
    "모디파이어": ConditionKind(
        lambda v: isinstance(v, str) and bool(MODIFIER.fullmatch(v)),
        "모디파이어 종류 이름입니다(예: BEVEL).",
        _of_active(lambda v, active: v in active.modifiers),
    ),
    "재질 슬롯 수": ConditionKind(
        _is_positive_int,
        "1 이상의 정수입니다.",
        # 칸을 더 만든 사용자도 놓치지 않게 '이상'으로 본다(잘못 물어도 손해는 거절 한 번).
        _of_active(lambda v, active: active.material_slot_count >= v),
    ),
    "배율": ConditionKind(
        lambda v: isinstance(v, list) and len(v) == 3 and all(map(_is_number, v)),
        "숫자 셋입니다(예: [1, 1, 1]).",
        _of_active(_scale_is),
    ),
    "크기 비율": ConditionKind(
        lambda v: _is_number(v) and v >= 1,
        "1 이상의 숫자입니다(가장 긴 축이 두 번째 축의 몇 배 이상인가).",
        _of_active(_size_ratio_is),
    ),
    "배율 늘어남": ConditionKind(
        _is_axes,
        "방향 하나(예: Z)나 방향 목록(예: [Y, Z])입니다. 기준 때보다 그 방향 배율이 모두 커졌나.",
        _changed("scale", grew=True),
    ),
    "배율 줄어듦": ConditionKind(
        _is_axes,
        "방향 하나(예: X)나 방향 목록(예: [Y, Z])입니다. 기준 때보다 그 방향 배율이 모두 작아졌나.",
        _changed("scale", grew=False),
    ),
    "배율 그대로": ConditionKind(
        _is_axes,
        "방향 하나(예: X)나 방향 목록(예: [X, Y])입니다. 기준 때와 그 방향 배율이 모두 같은가(한 축만 바꾸는 조작에 함께 적음).",
        _changed("scale", grew=None),
    ),
    "위치 늘어남": ConditionKind(
        _is_axes,
        "방향 하나(예: Z)나 방향 목록입니다. 기준 때보다 그 방향 좌표가 모두 커졌나(Z가 크면 위로 옮김).",
        _changed("location", grew=True),
    ),
    "위치 줄어듦": ConditionKind(
        _is_axes,
        "방향 하나(예: Z)나 방향 목록입니다. 기준 때보다 그 방향 좌표가 모두 작아졌나(Z가 작으면 아래로 옮김).",
        _changed("location", grew=False),
    ),
    "화면": ConditionKind(
        lambda v: v in VIEW_CHANGES,
        f"화면 조작입니다({', '.join(VIEW_CHANGES)}).",
        _view_is,
    ),
}
