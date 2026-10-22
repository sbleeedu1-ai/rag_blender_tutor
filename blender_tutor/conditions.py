"""끝난 조건: 종류마다 '값의 꼴'과 '맞는지 판정하는 규칙'을 한곳에 둔다.

연습 과정 파일 검사(course_check)는 값의 꼴을, 진행 관리(progress)는 판정을 가져다 쓴다.
새 종류를 더할 때는 이 파일의 CONDITIONS 표에 한 줄만 더한다.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from blender_tutor.work_state import ActiveObject, WorkState


@dataclass(frozen=True)
class ConditionKind:
    """끝난 조건 종류 하나."""

    is_valid: Callable[[object], bool]  # 연습 과정 파일에 적힌 값이 맞는 꼴인가
    hint: str  # 값의 꼴이 틀렸을 때 보여 줄 설명
    is_met: Callable[[object, WorkState, int], bool]  # (값, 작업 상태, 단계 시작 때 장면 물체 수) → 맞으면 참


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


def _of_active(rule: Callable[[object, ActiveObject], bool]) -> Callable[[object, WorkState, int], bool]:
    """활성 물체를 보는 규칙. 활성 물체가 없으면 맞지 않는다."""
    return lambda value, state, start_count: state.active_object is not None and rule(value, state.active_object)


def _scale_is(value, active: ActiveObject) -> bool:
    # Blender가 계산한 소수라 0.9999999처럼 아주 작은 차이는 같다고 본다.
    return all(math.isclose(have, want, rel_tol=1e-3, abs_tol=1e-3) for have, want in zip(active.scale, value))


def _size_ratio_is(value, active: ActiveObject) -> bool:
    # 치수는 절대 숫자가 아니라 비율로만 본다: 가장 긴 축 ≥ 두 번째로 긴 축 × n.
    longest, second, _ = sorted(active.dimensions, reverse=True)
    return longest > 0 and longest >= second * value


# 끝난 조건 종류(명세에서 정한 7가지). 판정은 AI 없이 이 규칙으로만 한다.
CONDITIONS: dict[str, ConditionKind] = {
    "모드": ConditionKind(
        lambda v: v in MODES,
        "Blender 모드 이름입니다(예: OBJECT, EDIT_MESH).",
        lambda v, state, start_count: state.mode == v,
    ),
    "방금 조작": ConditionKind(
        lambda v: isinstance(v, str) and bool(OPERATOR.fullmatch(v)),
        "Blender 조작 이름입니다(예: mesh.merge).",
        lambda v, state, start_count: v in state.recent_operators,
    ),
    "물체 수 늘어남": ConditionKind(
        _is_positive_int,
        "1 이상의 정수입니다(단계 시작 때보다 몇 개 늘었나).",
        lambda v, state, start_count: state.scene_object_count >= start_count + v,
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
}
