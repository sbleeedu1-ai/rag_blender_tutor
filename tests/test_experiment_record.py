"""실험 기록(docs/experiment.md)의 "넘어간 것" 표 검사. 실행 뒤 점검을 적은 절은 표가 있고 처리가 정해져 있어야 한다.

이 검사는 칸이 채워졌는지만 본다. 내용이 맞는지는 실행 뒤 독립 검토가 맡는다(HISTORY [196]).
"""

import re
from pathlib import Path

RECORD = Path(__file__).resolve().parents[1] / "docs" / "experiment.md"
KINDS = {"예상 밖", "제외", "못 만듦", "추측", "못 본 것"}
AFTER_RUN = "**실행 뒤 점검**"
TABLE_HEAD = "**넘어간 것**"
REVIEW_DONE = "- [x] 실행 뒤 독립 검토"


def _handled(cell: str) -> bool:
    if re.fullmatch(r"지금 함: \S.*", cell) or re.fullmatch(r"다음 할 일 \d+번.*", cell):
        return True
    return re.fullmatch(r'사용자가 뺌: ".+".*', cell) is not None


def _row_problems(title: str, line: str) -> list[str]:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) != 4:
        return [f"{title}: 칸이 4개가 아닙니다: {line[:60]}"]
    kind, what, how, handling = cells
    found = []
    if kind not in KINDS:
        found.append(f"{title}: 종류가 틀립니다: {kind}")
    if not what or not how:
        found.append(f"{title}: 비어 있는 칸: {line[:60]}")
    if not _handled(handling):
        found.append(f"{title}: 처리가 정해지지 않았습니다: {line[:60]}")
    return found


def problems(text: str) -> list[str]:
    """실행 뒤 점검을 적은 절마다 표와 독립 검토를 본다. 문제 설명 목록을 돌려준다."""
    found = []
    for section in re.split(r"(?m)^(?=### )", text.replace("\r\n", "\n")):
        if AFTER_RUN not in section:
            continue
        title = section.splitlines()[0][:50]
        if REVIEW_DONE not in section:
            found.append(f"{title}: 실행 뒤 독립 검토가 끝나지 않았습니다")
        if TABLE_HEAD not in section:
            found.append(f"{title}: 넘어간 것 표가 없습니다")
            continue
        lines = section[section.index(TABLE_HEAD):].splitlines()[1:]
        rows = []
        for line in lines:
            if line.startswith("|"):
                rows.append(line)
            elif rows:
                break
        body = [row for row in rows[1:] if not re.fullmatch(r"\|[-| ]+\|", row)]
        if not body:
            found.append(f"{title}: 넘어간 것 표에 줄이 없습니다")
        for row in body:
            found.extend(_row_problems(title, row))
    return found


GOOD = """### [E2] 가설 · 2026-11-06

- [x] 실행 뒤 독립 검토: Sonnet

**실행 뒤 점검**

**넘어간 것**

| 종류 | 무엇 | 확인한 방법 | 처리 |
|---|---|---|---|
| 예상 밖 | 키맵 개수 | 전체 읽기로 잼 | 지금 함: 원인 확인 |
| 제외 | 취소된 조작 | 점 수를 직접 읽음 | 다음 할 일 2번 |
| 못 본 것 | 집 PC | 이 PC만 있음 | 사용자가 뺌: "집에서 해" |

다음 글
"""


def test_표가_채워졌으면_문제가_없다():
    assert problems(GOOD) == []


def test_실행_뒤_점검이_없는_옛_절은_보지_않는다():
    assert problems("### [E2] 옛 가설\n\n결론만 있음\n") == []


def test_표가_없으면_알린다():
    text = GOOD.split("**넘어간 것**")[0]
    assert any("표가 없습니다" in item for item in problems(text))


def test_독립_검토가_안_끝났으면_알린다():
    assert any("독립 검토" in item for item in problems(GOOD.replace("- [x] 실행 뒤", "- [ ] 실행 뒤")))


def test_처리가_비었으면_알린다():
    assert any("처리가" in item for item in problems(GOOD.replace("다음 할 일 2번", "")))


def test_처리에_없는_말이면_알린다():
    assert any("처리가" in item for item in problems(GOOD.replace("다음 할 일 2번", "안 봤음")))


def test_사용자가_뺐다면서_말이_없으면_알린다():
    assert any("처리가" in item for item in problems(GOOD.replace('사용자가 뺌: "집에서 해"', "사용자가 뺌")))


def test_확인한_방법이_비었으면_알린다():
    assert any("비어 있는" in item for item in problems(GOOD.replace("점 수를 직접 읽음", "")))


def test_종류가_틀리면_알린다():
    assert any("종류가" in item for item in problems(GOOD.replace("| 제외 |", "| 기타 |")))


def test_실제_실험_기록():
    assert problems(RECORD.read_text(encoding="utf-8")) == []
