"""연습 과정 파일(courses/*.yaml) 검사."""

import datetime
import json
import re
import sys
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from blender_tutor.conditions import CONDITIONS
from blender_tutor.menu_names import read_po


class Kind(StrEnum):
    """문제 종류. 웹의 404처럼 정해 둔 이름만 쓴다(오타를 내면 바로 오류가 난다)."""

    MISSING = "missing"  # 꼭 있어야 하는 칸이 없거나 값이 비어 있음
    UNKNOWN = "unknown"  # 모르는 칸 이름
    TYPE = "type"  # 값의 모양이 틀림(글이어야 할 곳에 목록 등)
    COUNT = "count"  # 개수가 정해진 범위 밖
    LABEL_FORMAT = "label-format"  # 이름표가 영어 소문자·숫자·하이픈이 아님
    ADDRESS_FORMAT = "address-format"  # 설명서 소제목 주소가 '경로.html#앵커' 꼴이 아님
    DUPLICATE_LABEL = "duplicate-label"  # 이름표 겹침
    CONDITION_KIND = "condition-kind"  # 정해진 7가지 밖의 끝난 조건 종류
    CONDITION_VALUE = "condition-value"  # 끝난 조건 값의 꼴이 그 종류에 맞지 않음
    COMMON_REF = "common-ref"  # 공통 준비 파일을 잘못 가리킴
    ADDRESS_MISSING = "address-missing"  # 설명서 소제목 주소가 청크에 없음(data/가 있을 때만)
    MENU_UNKNOWN = "menu-unknown"  # 메뉴 경로의 한 단이 번역 사전에 없음(data/가 있을 때만)
    COPIED = "copied"  # 설명서와 긴 문장이 똑같이 겹침(data/가 있을 때만)
    YAML_TRAP = "yaml-trap"  # YAML 함정(따옴표 없는 no 등, 같은 칸 두 번)
    YAML_SYNTAX = "yaml-syntax"  # YAML 문법 오류
    FILE_NAME = "file-name"  # 확장자가 .yaml이 아님


@dataclass(frozen=True)
class Problem:
    """검사에서 찾은 문제 하나."""

    kind: Kind  # 문제 종류(테스트가 보는 값)
    file: str  # 파일 이름
    where: str  # 파일 안 위치(예: 구간[1].단계[2].이름)
    message: str  # 사람이 읽을 설명


class _NoDuplicateKeyLoader(yaml.SafeLoader):
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


Report = Callable[[Kind, str, str], None]  # (종류, 위치, 설명)
Checker = Callable[[object, str, Report], None]


def _check_fields(data: object, fields: dict[str, tuple[bool, Checker]], where: str, report: Report) -> None:
    """칸 묶음 하나(YAML 매핑)를 칸 정의표와 맞춰 본다."""
    if not isinstance(data, dict):
        report(Kind.TYPE, where, "칸 이름: 값 꼴이어야 합니다.")
        return
    for name, (required, checker) in fields.items():
        if name in data:
            checker(data[name], f"{where}.{name}" if where else name, report)
        elif required:
            report(Kind.MISSING, where or "맨 위", f"꼭 있어야 하는 '{name}' 칸이 없습니다.")
    for name in data:
        if name not in fields:
            report(Kind.UNKNOWN, where or "맨 위", f"'{name}'은(는) 모르는 칸 이름입니다. 쓸 수 있는 칸: {', '.join(fields)}")


def _text(value: object, where: str, report: Report) -> None:
    if value is None or value == "":
        report(Kind.MISSING, where, "값이 비어 있습니다.")
    elif isinstance(value, (bool, int, float, datetime.date)):
        # YAML 1.1 함정: 따옴표 없는 no/on은 참/거짓, 1.10은 숫자 1.1, 22:30은 60진수 1350으로 읽힌다.
        report(Kind.YAML_TRAP, where, f"글이어야 하는데 YAML이 {value!r}(으)로 읽었습니다. 값을 따옴표로 감싸세요.")
    elif not isinstance(value, str):
        report(Kind.TYPE, where, "글 한 줄이어야 합니다.")


# 이름표는 진행 기록에 그대로 적히므로 바뀌지 않는 영어 소문자·숫자·하이픈만 쓴다(예: blade-tip).
LABEL = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


def _label(value: object, where: str, report: Report) -> None:
    _text(value, where, report)
    if isinstance(value, str) and value and not LABEL.fullmatch(value):
        report(Kind.LABEL_FORMAT, where, f"이름표 '{value}': 영어 소문자·숫자·하이픈만 씁니다(예: blade-tip).")


def _texts(least: int = 1, most: int | None = None) -> Checker:
    """글 목록을 검사하는 함수를 만든다. 개수는 least개 이상 most개 이하."""

    def check(value: object, where: str, report: Report) -> None:
        if not isinstance(value, list):
            report(Kind.TYPE, where, "글 목록이어야 합니다.")
            return
        if len(value) < least or (most is not None and len(value) > most):
            limit = f"{least}-{most}개" if most is not None else f"{least}개 이상"
            report(Kind.COUNT, where, f"{limit}여야 하는데 {len(value)}개입니다.")
        for i, item in enumerate(value, start=1):
            _text(item, f"{where}[{i}]", report)

    return check


# 설명서 소제목 주소: 5.2 설명서 안의 상대 경로 + 앵커(예: modeling/meshes/editing/mesh/merge.html#merge).
ADDRESS = re.compile(r"[a-z0-9_-]+(/[a-z0-9_.-]+)*\.html#[a-z0-9_-]+")


def _addresses(value: object, where: str, report: Report) -> None:
    _texts(1, 3)(value, where, report)
    for i, item in enumerate(value if isinstance(value, list) else [], start=1):
        if isinstance(item, str) and item and not ADDRESS.fullmatch(item):
            report(
                Kind.ADDRESS_FORMAT,
                f"{where}[{i}]",
                f"'{item}': 설명서 소제목 주소는 '경로.html#앵커' 꼴로 적습니다(앞에 / 나 https:// 없이).",
            )


def _list_of(fields: dict[str, tuple[bool, Checker]]) -> Checker:
    """칸 묶음의 목록(구간 목록, 단계 목록 등)을 검사하는 함수를 만든다."""

    def check(value: object, where: str, report: Report) -> None:
        if not isinstance(value, list):
            report(Kind.TYPE, where, "목록이어야 합니다.")
            return
        if not value:
            report(Kind.COUNT, where, "한 개 이상 있어야 합니다.")
        for i, item in enumerate(value, start=1):
            _check_fields(item, fields, f"{where}[{i}]", report)

    return check


def _conditions(value: object, where: str, report: Report) -> None:
    if not isinstance(value, list):
        report(Kind.TYPE, where, "목록이어야 합니다.")
        return
    for i, item in enumerate(value, start=1):
        if not (isinstance(item, dict) and len(item) == 1):
            report(Kind.CONDITION_KIND, f"{where}[{i}]", "끝난 조건은 한 줄에 '종류: 값' 하나씩 적습니다.")
            continue
        condition, condition_value = next(iter(item.items()))
        kind = CONDITIONS.get(condition)
        if kind is None:
            report(
                Kind.CONDITION_KIND,
                f"{where}[{i}]",
                f"'{condition}'은(는) 정해진 끝난 조건 종류가 아닙니다. 쓸 수 있는 종류: {', '.join(CONDITIONS)}",
            )
        elif condition_value is None or condition_value == "":
            report(Kind.MISSING, f"{where}[{i}].{condition}", "값이 비어 있습니다.")
        elif isinstance(condition_value, bool):
            # 숫자(재질 슬롯 수: 2, 배율: [1, 1, 1])는 맞는 값이지만, 참/거짓은 따옴표 없는 no/on 같은 함정이다.
            report(
                Kind.YAML_TRAP,
                f"{where}[{i}].{condition}",
                f"YAML이 {condition_value!r}(으)로 읽었습니다. 값을 따옴표로 감싸세요.",
            )
        elif not kind.is_valid(condition_value):
            report(Kind.CONDITION_VALUE, f"{where}[{i}].{condition}", f"{condition_value!r}: '{condition}' 값은 {kind.hint}")


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
    "먼저 볼 소제목": (True, _addresses),
    "끝난 조건": (False, _conditions),
    "자주 막히는 곳": (False, _texts()),
}

SECTION = {
    "이름": (True, _text),
    "단계": (True, _list_of(STEP)),
}

# 공통 준비 파일(이름이 _로 시작)은 다른 연습 과정이 가리키기만 하므로
# 마지막 결과·비슷한 말·먼저 할 것이 없다. 난이도는 "없음"으로 적는다.
COMMON = {
    "이름표": (True, _label),
    "이름": (True, _text),
    "한 줄 설명": (True, _text),
    "난이도": (True, _text),
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


def _steps(data: object):
    """파일 안 단계를 (위치, 단계) 차례로 돌려준다. 모양이 틀린 곳은 건너뛴다(기본 검사가 이미 알린다)."""
    sections = data.get("구간") if isinstance(data, dict) else None
    for i, section in enumerate(sections if isinstance(sections, list) else [], start=1):
        steps = section.get("단계") if isinstance(section, dict) else None
        for j, step in enumerate(steps if isinstance(steps, list) else [], start=1):
            if isinstance(step, dict):
                yield f"구간[{i}].단계[{j}]", step


def _step_labels(data: object) -> list[tuple[str, str]]:
    """파일 안 단계 이름표를 (위치, 이름표) 목록으로 모은다. 모양이 틀린 곳은 건너뛴다."""
    return [(f"{where}.이름표", step["이름표"]) for where, step in _steps(data) if isinstance(step.get("이름표"), str)]


def _is_common(file_name: str) -> bool:
    """공통 준비 파일은 이름이 _로 시작한다(예: _common.yaml)."""
    return file_name.startswith("_")


@dataclass(frozen=True)
class Manual:
    """data/에 있을 때만 쓰는 자료: 설명서 청크와 Blender 화면 번역 사전."""

    addresses: frozenset[str]  # 청크의 설명서 소제목 주소(경로.html#앵커)
    screen_names: frozenset[str]  # Blender 화면 영어 글자 전체(ko.po + 번역률 100%인 fr.po의 영어 쪽)
    bodies: tuple[tuple[str, str], ...]  # 청크마다 (설명서 링크, 본문)


def load_manual(data: Path) -> Manual | None:
    """data/ 폴더에서 자료를 읽는다. 파일이 하나라도 없으면 None(자료 검사를 건너뛴다)."""
    chunks_file = data / "chunks" / "manual_chunks.jsonl"
    po_files = [data / "ui_ko_5.2" / "ko.po", data / "ui_ko_5.2" / "fr.po"]
    if not all(path.is_file() for path in [chunks_file, *po_files]):
        return None
    chunks = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines() if line]
    # ko.po에는 번역된 글자만 있어서, 번역이 없어 화면에 영어로 보이는 글자(At Center 등)는 fr.po에서 찾는다(티켓 20).
    screen_names = {english for path in po_files for _, english, _ in read_po(path.read_text(encoding="utf-8"))}
    return Manual(
        addresses=frozenset(f"{chunk['page_path']}.html#{chunk['anchor']}" for chunk in chunks),
        screen_names=frozenset(screen_names),
        bodies=tuple((chunk["url"], chunk["body"]) for chunk in chunks),
    )


NO_MENU = "없음"  # 메뉴 없이 단축키·마우스로만 하는 조작


def _check_against_manual(data: object, manual: Manual, report: Report) -> None:
    for where, step in _steps(data):
        addresses = step.get("먼저 볼 소제목")
        for i, address in enumerate(addresses if isinstance(addresses, list) else [], start=1):
            if isinstance(address, str) and ADDRESS.fullmatch(address) and address not in manual.addresses:
                report(
                    Kind.ADDRESS_MISSING,
                    f"{where}.먼저 볼 소제목[{i}]",
                    f"'{address}': 설명서 청크에 이 주소가 없습니다. 웹 설명서에서 쪽과 소제목 앵커를 다시 확인하세요.",
                )
        operations = step.get("조작")
        for i, operation in enumerate(operations if isinstance(operations, list) else [], start=1):
            menu = operation.get("메뉴") if isinstance(operation, dict) else None
            if not isinstance(menu, str) or menu == NO_MENU:
                continue
            for part in menu.split(">"):
                name = part.strip().replace("…", "...")  # 설명서는 말줄임표를 '…'로, 번역 사전은 '...'로 쓴다
                if name not in manual.screen_names:
                    report(
                        Kind.MENU_UNKNOWN,
                        f"{where}.조작[{i}].메뉴",
                        f"'{name}': Blender 화면 글자(번역 사전 ko.po·fr.po)에 없습니다. 화면에 보이는 영어 그대로 적으세요.",
                    )


# 설명서 문장을 그대로 옮기지 않는다(CC BY-SA). 낱말이 이만큼 같은 차례로 이어지면 옮긴 것으로 본다.
# 메뉴 경로·옵션 이름처럼 짧게 겹치는 것은 괜찮다. 검 파일은 6단어에서 메뉴 경로 하나가 겹치고 8단어에서는 겹치지 않는다.
COPY_WORDS = 8
_WORD = re.compile(r"\w+")
# 화면·설명서 글자를 일부러 그대로 적는 칸은 옮김 검사에서 뺀다.
_NOT_PROSE = {"이름표", "메뉴", "먼저 볼 소제목", "끝난 조건"}


def _prose(value: object, where: str):
    """파일 안 우리 말로 쓴 글을 (위치, 글) 차례로 돌려준다."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for name, item in value.items():
            if name not in _NOT_PROSE:
                yield from _prose(item, f"{where}.{name}" if where else str(name))
    elif isinstance(value, list):
        for i, item in enumerate(value, start=1):
            yield from _prose(item, f"{where}[{i}]")


def _word_runs(text: str):
    """글을 소문자 낱말로 나눠, COPY_WORDS개씩 이어진 낱말 묶음을 모두 돌려준다(문장부호·대소문자 무시)."""
    words = [word.lower() for word in _WORD.findall(text)]
    for i in range(len(words) - COPY_WORDS + 1):
        yield tuple(words[i : i + COPY_WORDS])


def _check_copies(loaded: dict[str, object], manual: Manual) -> list[Problem]:
    """연습 과정 글과 설명서 본문이 COPY_WORDS 낱말 이상 똑같이 겹치는 곳을 찾는다. 청크는 한 번만 훑는다."""
    places: dict[tuple[str, ...], list[tuple[str, str]]] = {}  # 낱말 묶음 → (파일, 위치)들
    for name, data in loaded.items():
        for where, text in _prose(data, ""):
            for run in _word_runs(text):
                places.setdefault(run, []).append((name, where))
    found: dict[tuple[str, str], tuple[str, tuple[str, ...]]] = {}  # (파일, 위치) → 처음 겹친 (링크, 낱말 묶음)
    for url, body in manual.bodies:
        for run in _word_runs(body):
            for place in places.get(run, ()):
                found.setdefault(place, (url, run))
    return [
        Problem(
            Kind.COPIED,
            name,
            where,
            f"설명서와 '{' '.join(run)}' 등 {COPY_WORDS}낱말 이상이 똑같습니다({url}). 우리 말로 새로 쓰세요.",
        )
        for (name, where), (url, run) in found.items()
    ]


def check_folder(folder: Path, manual: Manual | None = None) -> list[Problem]:
    """폴더 안 연습 과정 파일을 모두 검사해 문제 목록을 돌려준다.

    manual(data/의 자료)을 주면 소제목 주소·메뉴 경로·설명서 문장 옮김도 본다.
    """
    problems: list[Problem] = []
    loaded: dict[str, object] = {}
    for path in sorted(folder.glob("*.yml")):
        problems.append(Problem(Kind.FILE_NAME, path.name, "", "확장자를 .yaml로 바꾸세요. .yml 파일은 읽지 않습니다."))
    for path in sorted(folder.glob("*.yaml")):

        def report(kind: Kind, where: str, message: str) -> None:
            problems.append(Problem(kind, path.name, where, message))

        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=_NoDuplicateKeyLoader)
        except _DuplicateKey as e:
            report(Kind.YAML_TRAP, f"{e.line}번째 줄", f"'{e.key}' 칸이 한 묶음 안에 두 번 있습니다.")
            loaded[path.name] = None  # 다른 파일이 이 파일을 가리키는 것은 맞으니 이름은 남긴다
            continue
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            report(Kind.YAML_SYNTAX, f"{mark.line + 1}번째 줄" if mark else "", f"YAML 문법 오류: {e}")
            loaded[path.name] = None
            continue
        loaded[path.name] = data
        _check_fields(data, COMMON if _is_common(path.name) else COURSE, "", report)
        if manual is not None:
            _check_against_manual(data, manual, report)

    # 진행 기록은 연습 과정도 이름표로 적으므로, 파일끼리 맨 위 이름표가 겹치면 안 된다.
    top_labels: dict[str, str] = {}
    for name, data in loaded.items():
        label = data.get("이름표") if isinstance(data, dict) else None
        if not isinstance(label, str):
            continue
        if label in top_labels:
            problems.append(
                Problem(Kind.DUPLICATE_LABEL, name, "이름표", f"이름표 '{label}'이(가) {top_labels[label]}와(과) 겹칩니다.")
            )
        else:
            top_labels[label] = name

    # 진행 기록은 단계를 이름표로 적으므로, 한 연습 과정(가리키는 공통 준비 포함) 안에서 이름표가 겹치면 안 된다.
    for name, data in loaded.items():
        common = data.get("먼저 할 것") if isinstance(data, dict) and not _is_common(name) else None
        if not isinstance(common, str):
            common = None
        elif not _is_common(common) or common not in loaded:
            problems.append(
                Problem(
                    Kind.COMMON_REF,
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
                        Kind.DUPLICATE_LABEL,
                        name,
                        where,
                        f"단계 이름표 '{label}'이(가) {first_file or name} {first_where}와(과) 겹칩니다.",
                    )
                )
            else:
                seen[label] = (None, where)

    if manual is not None:
        problems.extend(_check_copies(loaded, manual))
    return problems


def main(argv: list[str]) -> int:
    """`python -m blender_tutor.course_check courses`: 문제를 한 줄씩 보여 주고, 있으면 1로 끝난다.

    지금 폴더 아래 data/에 청크·ko.po·fr.po가 있으면 자료 검사도 한다.
    """
    sys.stdout.reconfigure(encoding="utf-8")  # Windows 터미널에서 한글이 깨지지 않게
    folder = Path(argv[0]) if argv else Path("courses")
    if not any(folder.glob("*.yaml")):
        print(f"{folder}: 연습 과정 파일(.yaml)이 없습니다. 폴더 경로를 확인하세요.")
        return 1
    manual = load_manual(Path("data"))
    if manual is None:
        print("data/에 자료가 없어 소제목 주소·메뉴 경로·설명서 문장 옮김 검사는 건너뜁니다.")
    problems = check_folder(folder, manual)
    for p in problems:
        print(f"{p.file} {p.where}: [{p.kind}] {p.message}")
    print(f"{folder}: 문제 {len(problems)}개")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
