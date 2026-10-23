"""작업 상태: 애드온이 Blender에서 읽어 보내는 14칸(명세 "애드온").

애드온은 이 모양을 JSON으로 보내고, 진행 관리(끝난 조건 판정)와 답 엔진(모델에 넘기는 글)이 같은 WorkState를 쓴다.
칸 이름은 JSON과 같다. 애드온(addon/blender_tutor_addon)은 Blender 안에서 돌아 이 파일을 가져다 쓰지 못하므로,
칸을 바꾸면 애드온의 read_state도 함께 고친다(Blender 자체 시험이 둘이 맞는지 본다).
"""

from collections.abc import Callable
from dataclasses import dataclass, fields


@dataclass(frozen=True)
class ActiveObject:
    """활성 물체(마지막으로 고른 물체)."""

    name: str  # 한국어 화면에서 만든 물체는 "실린더"처럼 한국어일 수 있다
    type: str  # Blender 물체 종류(예: MESH)
    modifiers: tuple[str, ...]  # 모디파이어 종류(예: BEVEL), 위에서 아래 차례
    scale: tuple[float, float, float]  # 배율
    dimensions: tuple[float, float, float]  # 크기
    material_slot_count: int  # 재질 슬롯 수
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)  # 위치. 테스트에서 줄여 쓰도록 기본값을 둔다


@dataclass(frozen=True)
class View:
    """3D 화면의 시점(Blender RegionView3D 값). 화면 돌리기·확대·옮기기는 조작 기록에 남지 않아 이 값으로 알아챈다(티켓 27).

    확대하면 거리가 줄고, 돌리면 각도가, 옮기면 중심이 바뀐다. Home(장면 전체 담기)은 거리와 중심을 함께 바꾼다.
    """

    distance: float  # 시점 중심에서 화면까지 거리(view_distance)
    rotation: tuple[float, float, float, float]  # 보는 방향(view_rotation, 쿼터니언 w·x·y·z)
    center: tuple[float, float, float]  # 화면이 가운데로 보는 곳(view_location)


@dataclass(frozen=True)
class WorkState:
    """작업 상태 14칸. 활성 물체 칸에 이름·종류·모디파이어·배율·크기·재질 슬롯 수·위치, 시점 칸에 거리·각도·중심이 함께 든다."""

    mode: str  # Blender context.mode 값(예: OBJECT, EDIT_MESH)
    active_object: ActiveObject | None  # 활성 물체가 없으면 None
    selected_objects: tuple[str, ...]  # 고른 물체 이름(수는 길이)
    language: str  # 화면 언어(예: ko_KR). 설정이 '자동'이어도 실제로 쓰는 언어
    translate_interface: bool  # 인터페이스 번역 켜짐
    file_path: str  # 열린 파일 경로. 저장 전이면 ""
    scene_object_count: int  # 장면 물체 수
    blender_version: str  # 예: 5.2.2
    edit_selected: dict[str, int]  # 편집 모드 선택 방식(VERT·EDGE·FACE) → 고른 개수. 메시 편집 모드가 아니면 비움
    recent_operators: tuple[str, ...]  # 방금 실행한 조작(오래된 차례, 최대 3개), 'mesh.merge' 꼴
    # 확정을 기다리며 진행 중인 조작(S·G·화면 끌기 등, 'transform.resize' 꼴). 그동안 배율·시점은 확정 전 값이다
    running_operators: tuple[str, ...] = ()
    view: View | None = None  # 가장 큰 3D 화면의 시점. 3D 화면이 없으면 None. 테스트에서 줄여 쓰도록 기본값을 둔다

    @classmethod
    def from_json(cls, data: object) -> "WorkState":
        """애드온이 보낸 JSON(사전)을 읽는다. 빠진 칸·모르는 칸·꼴이 틀린 칸이 있으면 ValueError."""
        values = _read(data, _STATE, "작업 상태")
        if values["active_object"] is not None:
            values["active_object"] = ActiveObject(**_read(values["active_object"], _OBJECT, "활성 물체"))
        if values["view"] is not None:
            values["view"] = View(**_read(values["view"], _VIEW, "시점"))
        return cls(**values)

    def to_json(self) -> dict:
        """애드온이 보내는 것과 같은 JSON(사전)."""
        data = {field.name: _plain(getattr(self, field.name)) for field in fields(self)}
        for name, part in (("active_object", self.active_object), ("view", self.view)):
            if part is not None:
                data[name] = {field.name: _plain(getattr(part, field.name)) for field in fields(part)}
        return data


def _plain(value):
    return list(value) if isinstance(value, tuple) else dict(value) if isinstance(value, dict) else value


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _text(value) -> str:
    if not isinstance(value, str):
        raise ValueError("글자가 아님")
    return value


def _count(value) -> int:
    if not _is_int(value) or value < 0:
        raise ValueError("0 이상의 정수가 아님")
    return value


def _flag(value) -> bool:
    if not isinstance(value, bool):
        raise ValueError("참/거짓이 아님")
    return value


def _texts(value) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("목록이 아님")
    return tuple(map(_text, value))


def _is_number(value) -> bool:
    return _is_int(value) or isinstance(value, float)


def _number(value) -> float:
    if not _is_number(value):
        raise ValueError("숫자가 아님")
    return float(value)


def _numbers(count: int, name: str) -> Callable:
    def read(value) -> tuple[float, ...]:
        if not (isinstance(value, list) and len(value) == count and all(map(_is_number, value))):
            raise ValueError(f"숫자 {name}이 아님")
        return tuple(float(v) for v in value)

    return read


_three_numbers = _numbers(3, "셋")


def _counts(value) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("사전이 아님")
    return {_text(key): _count(number) for key, number in value.items()}


def _part_or_none(value):
    if value is not None and not isinstance(value, dict):
        raise ValueError("사전도 None도 아님")
    return value


_STATE: dict[str, Callable] = {
    "mode": _text,
    "active_object": _part_or_none,  # 안쪽 칸은 _OBJECT로 따로 읽는다
    "selected_objects": _texts,
    "language": _text,
    "translate_interface": _flag,
    "file_path": _text,
    "scene_object_count": _count,
    "blender_version": _text,
    "edit_selected": _counts,
    "recent_operators": _texts,
    "running_operators": _texts,
    "view": _part_or_none,  # 안쪽 칸은 _VIEW로 따로 읽는다
}
_OBJECT: dict[str, Callable] = {
    "name": _text,
    "type": _text,
    "modifiers": _texts,
    "scale": _three_numbers,
    "dimensions": _three_numbers,
    "material_slot_count": _count,
    "location": _three_numbers,
}
_VIEW: dict[str, Callable] = {
    "distance": _number,
    "rotation": _numbers(4, "넷"),
    "center": _three_numbers,
}


def _read(data: object, readers: dict[str, Callable], what: str) -> dict:
    """칸마다 꼴을 확인하며 읽는다."""
    if not isinstance(data, dict):
        raise ValueError(f"{what}: 사전이 아님")
    if missing := readers.keys() - data.keys():
        raise ValueError(f"{what}: 빠진 칸 {sorted(missing)}")
    if unknown := data.keys() - readers.keys():
        raise ValueError(f"{what}: 모르는 칸 {sorted(unknown)}")
    values = {}
    for key, reader in readers.items():
        try:
            values[key] = reader(data[key])
        except ValueError as error:
            raise ValueError(f"{what}의 {key}: {error}") from None
    return values
