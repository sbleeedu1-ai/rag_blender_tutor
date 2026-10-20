"""연습 과정 파일(courses/*.yaml) 검사."""

import datetime
import re
import sys
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Problem:
    """검사에서 찾은 문제 하나."""

    kind: str  # 문제 종류(테스트가 보는 값)
    file: str  # 파일 이름
    where: str  # 파일 안 위치(예: 구간[1].단계[2].이름)
    message: str  # 사람이 읽을 설명


class _Loader(yaml.SafeLoader):
    """같은 칸 이름이 한 묶음에 두 번 나오면 멈추는 읽기 도구(PyYAML은 기본으로 뒤엣것만 조용히 남긴다)."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # 목록 같은 이상한 칸 이름은 super()가 알아서 오류를 낸다
            if key in seen:
                raise _DuplicateKey(key, key_node.start_mark.line + 1)
            seen.add(key)
        return super().construct_mapping(node, deep)


class _DuplicateKey(Exception):
    def __init__(self, key: object, line: int):
        self.key, self.line = key, line


Report = Callable[[str, str, str], None]  # (종류, 위치, 설명)
Checker = Callable[[object, str, Report], None]


def _check_fields(data: object, fields: dict[str, tuple[bool, Checker]], where: str, report: Report) -> None:
    """칸 묶음 하나(YAML 매핑)를 칸 정의표와 맞춰 본다."""
    if not isinstance(data, dict):
        report("type", where, "칸 이름: 값 꼴이어야 합니다.")
        return
    for name, (required, checker) in fields.items():
        if name in data:
            checker(data[name], f"{where}.{name}" if where else name, report)
        elif required:
            report("missing", where or "맨 위", f"꼭 있어야 하는 '{name}' 칸이 없습니다.")
    for name in data:
        if name not in fields:
            report("unknown", where or "맨 위", f"'{name}'은(는) 모르는 칸 이름입니다. 쓸 수 있는 칸: {', '.join(fields)}")


def _text(value: object, where: str, report: Report) -> None:
    if value is None or value == "":
        report("missing", where, "값이 비어 있습니다.")
    elif isinstance(value, (bool, int, float, datetime.date)):
        # YAML 1.1 함정: 따옴표 없는 no/on은 참/거짓, 1.10은 숫자 1.1, 22:30은 60진수 1350으로 읽힌다.
        report("yaml-trap", where, f"글이어야 하는데 YAML이 {value!r}(으)로 읽었습니다. 값을 따옴표로 감싸세요.")
    elif not isinstance(value, str):
        report("type", where, "글 한 줄이어야 합니다.")


# 이름표는 진행 기록에 그대로 적히므로 바뀌지 않는 영어 소문자·숫자·하이픈만 쓴다(예: blade-tip).
LABEL = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def _label(value: object, where: str, report: Report) -> None:
    _text(value, where, report)
    if isinstance(value, str) and value and not LABEL.fullmatch(value):
        report("label-format", where, f"이름표 '{value}': 영어 소문자·숫자·하이픈만 씁니다(예: blade-tip).")


def _texts(least: int = 1, most: int | None = None) -> Checker:
    """글 목록을 검사하는 함수를 만든다. 개수는 least개 이상 most개 이하."""

    def check(value: object, where: str, report: Report) -> None:
        if not isinstance(value, list):
            report("type", where, "글 목록이어야 합니다.")
            return
        if len(value) < least or (most is not None and len(value) > most):
            limit = f"{least}-{most}개" if most is not None else f"{least}개 이상"
            report("count", where, f"{limit}여야 하는데 {len(value)}개입니다.")
        for i, item in enumerate(value, start=1):
            _text(item, f"{where}[{i}]", report)

    return check


def _list_of(fields: dict[str, tuple[bool, Checker]]) -> Checker:
    """칸 묶음의 목록(구간 목록, 단계 목록 등)을 검사하는 함수를 만든다."""

    def check(value: object, where: str, report: Report) -> None:
        if not isinstance(value, list):
            report("type", where, "목록이어야 합니다.")
            return
        if not value:
            report("count", where, "한 개 이상 있어야 합니다.")
        for i, item in enumerate(value, start=1):
            _check_fields(item, fields, f"{where}[{i}]", report)

    return check


# 끝난 조건 검사 종류(명세에서 정한 7가지). 새 종류는 진행 관리 코드에 판정을 더할 때 여기에도 더한다.
CONDITION_KINDS = ("모드", "방금 조작", "물체 수 늘어남", "모디파이어", "재질 슬롯 수", "배율", "크기 비율")


def _conditions(value: object, where: str, report: Report) -> None:
    if not isinstance(value, list):
        report("type", where, "목록이어야 합니다.")
        return
    for i, item in enumerate(value, start=1):
        if not (isinstance(item, dict) and len(item) == 1):
            report("condition-kind", f"{where}[{i}]", "끝난 조건은 한 줄에 '종류: 값' 하나씩 적습니다.")
            continue
        kind = next(iter(item))
        if kind not in CONDITION_KINDS:
            report(
                "condition-kind",
                f"{where}[{i}]",
                f"'{kind}'은(는) 정해진 끝난 조건 종류가 아닙니다. 쓸 수 있는 종류: {', '.join(CONDITION_KINDS)}",
            )


OPERATION = {
    "설명": (True, _text),
    "메뉴": (True, _text),
    "단축키": (True, _text),
}

STEP = {
    "이름표": (True, _label),
    "이름": (True, _text),
    "목표 모양": (True, _text),
    "참고 치수": (False, _text),
    "쉬운 설명": (True, _text),
    "조작": (True, _list_of(OPERATION)),
    "먼저 볼 소제목": (True, _texts(1, 3)),
    "끝난 조건": (False, _conditions),
    "자주 막히는 곳": (False, _texts()),
}

SECTION = {
    "이름": (True, _text),
    "단계": (True, _list_of(STEP)),
}

# 공통 준비 파일(이름이 _로 시작)은 다른 연습 과정이 가리키기만 하므로 맨 위 칸이 적다.
COMMON = {
    "이름표": (True, _label),
    "이름": (True, _text),
    "구간": (True, _list_of(SECTION)),
}

COURSE = {
    "이름표": (True, _label),
    "이름": (True, _text),
    "한 줄 설명": (True, _text),
    "난이도": (True, _text),
    "마지막 결과": (True, _text),
    "비슷한 말": (True, _texts()),
    "먼저 할 것": (True, _text),
    "구간": (True, _list_of(SECTION)),
}


def _step_labels(data: object) -> list[tuple[str, str]]:
    """파일 안 단계 이름표를 (위치, 이름표) 목록으로 모은다. 모양이 틀린 곳은 건너뛴다."""
    labels = []
    sections = data.get("구간") if isinstance(data, dict) else None
    for i, section in enumerate(sections if isinstance(sections, list) else [], start=1):
        steps = section.get("단계") if isinstance(section, dict) else None
        for j, step in enumerate(steps if isinstance(steps, list) else [], start=1):
            if isinstance(step, dict) and isinstance(step.get("이름표"), str):
                labels.append((f"구간[{i}].단계[{j}].이름표", step["이름표"]))
    return labels


def check_folder(folder: Path) -> list[Problem]:
    """폴더 안 연습 과정 파일을 모두 검사해 문제 목록을 돌려준다."""
    problems: list[Problem] = []
    loaded: dict[str, object] = {}
    for path in sorted(folder.glob("*.yaml")):

        def report(kind: str, where: str, message: str) -> None:
            problems.append(Problem(kind, path.name, where, message))

        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
        except _DuplicateKey as e:
            report("yaml-trap", f"{e.line}번째 줄", f"'{e.key}' 칸이 한 묶음 안에 두 번 있습니다.")
            loaded[path.name] = None  # 다른 파일이 이 파일을 가리키는 것은 맞으니 이름은 남긴다
            continue
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            report("yaml-syntax", f"{mark.line + 1}번째 줄" if mark else "", f"YAML 문법 오류: {e}")
            loaded[path.name] = None
            continue
        loaded[path.name] = data
        _check_fields(data, COMMON if path.name.startswith("_") else COURSE, "", report)

    # 진행 기록은 단계를 이름표로 적으므로, 한 연습 과정(가리키는 공통 준비 포함) 안에서 이름표가 겹치면 안 된다.
    for name, data in loaded.items():
        common = data.get("먼저 할 것") if isinstance(data, dict) and not name.startswith("_") else None
        if not isinstance(common, str):
            common = None
        elif not common.startswith("_") or common not in loaded:
            problems.append(
                Problem(
                    "common-ref",
                    name,
                    "먼저 할 것",
                    f"'{common}'은(는) 같은 폴더의 공통 준비 파일(이름이 _로 시작하는 .yaml)이 아닙니다.",
                )
            )
            common = None
        seen = {label: (common, where) for where, label in _step_labels(loaded.get(common))} if common else {}
        for where, label in _step_labels(data):
            if label in seen:
                first_file, first_where = seen[label]
                problems.append(
                    Problem(
                        "duplicate-label",
                        name,
                        where,
                        f"단계 이름표 '{label}'이(가) {first_file or name} {first_where}와(과) 겹칩니다.",
                    )
                )
            else:
                seen[label] = (None, where)
    return problems


def main(argv: list[str]) -> int:
    """`python -m blender_tutor.course_check courses`: 문제를 한 줄씩 보여 주고, 있으면 1로 끝난다."""
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 터미널에서 한글이 깨지지 않게
    folder = Path(argv[0]) if argv else Path("courses")
    problems = check_folder(folder)
    for p in problems:
        print(f"{p.file} {p.where}: [{p.kind}] {p.message}")
    print(f"{folder}: 문제 {len(problems)}개")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
