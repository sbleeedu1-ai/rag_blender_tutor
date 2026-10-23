"""연습 과정 파일 검사(시험 경계 ③).

일부러 틀린 작은 YAML을 임시 폴더에 써 넣고, 검사가 돌려준 문제의 종류만 본다.
"""

import json
from pathlib import Path

import pytest

from unittest.mock import ANY

from blender_tutor.course_check import Problem, check_folder, load_manual

# 검사를 통과하는 가장 작은 공통 준비 파일과 연습 과정 파일.
# 테스트마다 한 군데만 바꿔서 틀리게 만든다.
COMMON = """\
이름표: common
이름: 공통 준비
한 줄 설명: 화면을 돌려 보고 화면 언어를 확인한다.
난이도: 없음
구간:
  - 이름: 화면 익히기
    단계:
      - 이름표: view-navigate
        이름: 화면 돌려 보기
        목표 모양: 정육면체를 여러 방향에서 본다.
        쉬운 설명: 가운데 버튼을 누른 채 끌면 화면이 돈다.
        조작:
          - 설명: 화면 돌리기
            메뉴: View > Navigation > Orbit
            단축키: 가운데 버튼 끌기
            안내: 가운데 버튼을 누른 채 끌어 화면을 돌려 보세요.
        먼저 볼 소제목:
          - editors/3dview/navigate/navigation.html#orbit
"""

COURSE = """\
이름표: sword
이름: 단순한 검
한 줄 설명: 정육면체 하나로 시작해 검을 만든다.
난이도: 쉬움
마지막 결과: sword.glb
비슷한 말: [칼, 단검]
먼저 할 것: _common.yaml
구간:
  - 이름: 칼날 만들기
    단계:
      - 이름표: blade-tip
        이름: 칼끝 모으기
        목표 모양: 칼날 끝이 한 점으로 뾰족하다.
        참고 치수: 칼날 길이는 폭의 5배쯤.
        쉬운 설명: 편집 모드에서 끝 모서리를 골라 한 점으로 모은다.
        조작:
          - 설명: 고른 점을 가운데로 모으기
            메뉴: Mesh > Merge > At Center
            단축키: M
            안내: 이제 M을 눌러 가운데로 모아 볼까요?
            감지:
              - 방금 조작: mesh.merge
        먼저 볼 소제목:
          - modeling/meshes/editing/mesh/merge.html#merge
        끝난 조건:
          - 모드: EDIT_MESH
          - 방금 조작: mesh.merge
        자주 막히는 곳:
          - 물체 모드에서는 Merge 메뉴가 보이지 않는다.
"""


def write_folder(tmp_path: Path, common: str = COMMON, course: str = COURSE) -> Path:
    (tmp_path / "_common.yaml").write_text(common, encoding="utf-8")
    (tmp_path / "sword.yaml").write_text(course, encoding="utf-8")
    return tmp_path


def kinds(folder: Path) -> list[str]:
    return [p.kind for p in check_folder(folder)]


def test_올바른_파일은_문제가_없다(tmp_path):
    assert check_folder(write_folder(tmp_path)) == []


def test_꼭_있어야_하는_칸이_빠지면_잡는다(tmp_path):
    course = COURSE.replace("        목표 모양: 칼날 끝이 한 점으로 뾰족하다.\n", "")
    assert kinds(write_folder(tmp_path, course=course)) == ["missing"]


def test_모르는_칸_이름을_잡는다(tmp_path):
    course = COURSE.replace("            단축키: M\n", "            단축키: M\n            단축귀: M\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["unknown"]


def test_한_파일_안에서_단계_이름표가_겹치면_잡는다(tmp_path):
    step = COURSE[COURSE.index("      - 이름표: blade-tip") :]
    assert kinds(write_folder(tmp_path, course=COURSE + step)) == ["duplicate-label"]


def test_공통_준비와_단계_이름표가_겹치면_잡는다(tmp_path):
    course = COURSE.replace("이름표: blade-tip", "이름표: view-navigate")
    assert kinds(write_folder(tmp_path, course=course)) == ["duplicate-label"]


def test_정해진_종류_밖의_끝난_조건_종류를_잡는다(tmp_path):
    course = COURSE.replace("          - 모드: EDIT_MESH\n", "          - 꼭짓점 수: 8\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["condition-kind"]


def test_정해진_끝난_조건_종류는_모두_받아들인다(tmp_path):
    conditions = """\
          - 모드: EDIT_MESH
          - 방금 조작: mesh.merge
          - 물체 수 늘어남: 1
          - 모디파이어: SOLIDIFY
          - 재질 슬롯 수: 2
          - 배율: [1, 1, 1]
          - 크기 비율: 3
          - 배율 늘어남: Z
          - 배율 줄어듦: [Y, Z]
          - 위치 늘어남: X
          - 위치 줄어듦: Z
          - 배율 그대로: [X, Y]
          - 화면: 확대
"""
    course = COURSE.replace("          - 모드: EDIT_MESH\n          - 방금 조작: mesh.merge\n", conditions)
    assert kinds(write_folder(tmp_path, course=course)) == []


def test_끝난_조건이_종류_값_한_줄이_아니면_잡는다(tmp_path):
    course = COURSE.replace("          - 모드: EDIT_MESH\n", "          - 모드: EDIT_MESH\n            배율: [1, 1, 1]\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["condition-kind"]


def test_없는_공통_준비_파일을_가리키면_잡는다(tmp_path):
    course = COURSE.replace("먼저 할 것: _common.yaml", "먼저 할 것: _comon.yaml")
    assert kinds(write_folder(tmp_path, course=course)) == ["common-ref"]


def test_공통_준비가_아닌_파일을_가리키면_잡는다(tmp_path):
    course = COURSE.replace("먼저 할 것: _common.yaml", "먼저 할 것: sword.yaml")
    assert kinds(write_folder(tmp_path, course=course)) == ["common-ref"]


@pytest.mark.parametrize("value", ["no", "Yes", "on", "OFF", "1.10", "22:30"])
def test_따옴표_없는_값이_글이_아닌_것으로_읽히면_잡는다(tmp_path, value):
    course = COURSE.replace("단축키: M", f"단축키: {value}")
    assert kinds(write_folder(tmp_path, course=course)) == ["yaml-trap"]


def test_따옴표로_감싼_값은_글로_받아들인다(tmp_path):
    course = COURSE.replace("단축키: M", '단축키: "no"')
    assert kinds(write_folder(tmp_path, course=course)) == []


def test_한_묶음_안에_같은_칸_이름이_두_번_있으면_잡는다(tmp_path):
    course = COURSE.replace("            단축키: M\n", "            단축키: M\n            단축키: G\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["yaml-trap"]


def test_YAML_문법이_깨지면_잡는다(tmp_path):
    course = COURSE.replace("비슷한 말: [칼, 단검]", "비슷한 말: [칼, 단검")
    assert kinds(write_folder(tmp_path, course=course)) == ["yaml-syntax"]


@pytest.mark.parametrize("label", ["Blade-Tip", "blade tip", "칼끝", "-blade"])
def test_단계_이름표가_영어_소문자_숫자_하이픈이_아니면_잡는다(tmp_path, label):
    course = COURSE.replace("이름표: blade-tip", f"이름표: {label}")
    assert kinds(write_folder(tmp_path, course=course)) == ["label-format"]


@pytest.mark.parametrize("count", [0, 4])
def test_먼저_볼_소제목이_1에서_3개가_아니면_잡는다(tmp_path, count):
    lines = "".join(f"          - modeling/page.html#part-{i}\n" for i in range(count))
    course = COURSE.replace(
        "        먼저 볼 소제목:\n          - modeling/meshes/editing/mesh/merge.html#merge\n",
        f"        먼저 볼 소제목:{' []' if count == 0 else ''}\n{lines}",
    )
    assert kinds(write_folder(tmp_path, course=course)) == ["count"]


def test_조작_목록이_비어_있으면_잡는다(tmp_path):
    start = COURSE.index("        조작:\n")
    end = COURSE.index("        먼저 볼 소제목:")
    course = COURSE[:start] + "        조작: []\n" + COURSE[end:]
    assert kinds(write_folder(tmp_path, course=course)) == ["count"]


@pytest.mark.parametrize("value", ["no", "on", ""])
def test_끝난_조건_값의_YAML_함정과_빈_값을_잡는다(tmp_path, value):
    course = COURSE.replace("          - 모드: EDIT_MESH\n", f"          - 모드: {value}\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["yaml-trap" if value else "missing"]


def test_연습_과정끼리_맨_위_이름표가_겹치면_잡는다(tmp_path):
    write_folder(tmp_path)
    (tmp_path / "shield.yaml").write_text(COURSE, encoding="utf-8")
    assert kinds(tmp_path) == ["duplicate-label"]


def test_yaml이_아닌_확장자의_파일을_알린다(tmp_path):
    write_folder(tmp_path)
    (tmp_path / "axe.yml").write_text(COURSE.replace("sword", "axe"), encoding="utf-8")
    assert kinds(tmp_path) == ["file-name"]


@pytest.mark.parametrize(
    "address",
    [
        "modeling/meshes/editing/mesh/merge.html",
        "modeling/meshes/editing/mesh/merge#merge",
        "/modeling/meshes/editing/mesh/merge.html#merge",
        "https://docs.blender.org/manual/en/5.2/modeling/meshes/editing/mesh/merge.html#merge",
    ],
)
def test_먼저_볼_소제목이_경로_html_앵커_꼴이_아니면_잡는다(tmp_path, address):
    course = COURSE.replace("          - modeling/meshes/editing/mesh/merge.html#merge", f"          - {address}")
    assert kinds(write_folder(tmp_path, course=course)) == ["address-format"]


def test_공통_준비_파일의_YAML이_깨지면_그_파일만_알린다(tmp_path):
    common = COMMON.replace("이름: 화면 익히기", "이름: [화면 익히기")
    assert check_folder(write_folder(tmp_path, common=common)) == [
        Problem("yaml-syntax", "_common.yaml", ANY, ANY)
    ]


COURSES = Path(__file__).resolve().parent.parent / "courses"


def test_저장소의_연습_과정_파일은_검사를_통과한다():
    assert (COURSES / "_common.yaml").is_file()
    assert (COURSES / "sword.yaml").is_file()
    assert check_folder(COURSES) == []


@pytest.mark.parametrize(
    "condition",
    [
        "모드: EDIT",  # Blender가 보내는 모드 이름은 EDIT_MESH
        "모드: edit_mesh",
        "모드: EDIT_GPENCIL",  # 5.2에서 실제로 나오지 않는 옛 이름
        "방금 조작: MESH_OT_merge",  # 조작 이름은 mesh.merge 꼴
        "방금 조작: Merge",
        "물체 수 늘어남: 0",
        "물체 수 늘어남: 1.5",
        "물체 수 늘어남: 하나",
        "모디파이어: bevel",  # 모디파이어 종류 이름은 BEVEL 꼴
        "재질 슬롯 수: 0",
        "재질 슬롯 수: '2'",
        "배율: [1, 1]",
        "배율: 1",
        "배율: [1, 1, 큼]",
        "크기 비율: 0.5",  # 1보다 작으면 언제나 맞아 쓸모가 없다
        "크기 비율: 3배",
    ],
)
def test_끝난_조건_값의_꼴이_틀리면_잡는다(tmp_path, condition):
    course = COURSE.replace("          - 모드: EDIT_MESH\n", f"          - {condition}\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["condition-value"]


# --- data/가 있을 때만 하는 검사(티켓 24) ---
# 아래 자료는 테스트용으로 지어낸 것이다(설명서 원문 아님). 실제 data/와 같은 파일 자리에 둔다.

MANUAL_BODY = "Merge combines the selected vertices into one single vertex placed at their center point."


def write_data(tmp_path: Path, chunks: list[dict] | None = None, ko: str = "", fr: str = "") -> Path:
    """가짜 data/ 폴더: 청크 파일, ko.po, fr.po."""
    data = tmp_path / "data"
    (data / "chunks").mkdir(parents=True)
    (data / "ui_ko_5.2").mkdir()
    if chunks is None:
        chunks = [
            {"page_path": "editors/3dview/navigate/navigation", "anchor": "orbit", "url": "https://x/orbit", "body": "Orbit."},
            {"page_path": "modeling/meshes/editing/mesh/merge", "anchor": "merge", "url": "https://x/merge", "body": MANUAL_BODY},
        ]  # fmt: skip
    lines = "".join(json.dumps(chunk) + "\n" for chunk in chunks)
    (data / "chunks" / "manual_chunks.jsonl").write_text(lines, encoding="utf-8")
    (data / "ui_ko_5.2" / "ko.po").write_text(ko or KO_PO, encoding="utf-8")
    (data / "ui_ko_5.2" / "fr.po").write_text(fr or FR_PO, encoding="utf-8")
    return data


def po(*entries: tuple[str, str, str]) -> str:
    return "".join(f'msgctxt "{context}"\nmsgid "{english}"\nmsgstr "{translated}"\n\n' for context, english, translated in entries)


KO_PO = po(("*", "View", "보기"), ("*", "Navigation", "내비게이션"), ("*", "Orbit", "궤도"), ("*", "Mesh", "메쉬"), ("*", "Merge", "병합"))
# At Center는 한국어 번역이 없어 ko.po에 없고, 번역률 100%인 fr.po에만 있다(화면에는 영어로 보인다).
FR_PO = po(("Operator", "At Center", "Au centre"))


def data_kinds(folder: Path, data: Path) -> list[str]:
    return [p.kind for p in check_folder(folder, load_manual(data))]


def test_자료가_있어도_올바른_파일은_문제가_없다(tmp_path):
    assert data_kinds(write_folder(tmp_path), write_data(tmp_path)) == []


def test_먼저_볼_소제목_주소가_청크에_없으면_잡는다(tmp_path):
    course = COURSE.replace("merge.html#merge", "merge.html#merge-by-distance")
    assert data_kinds(write_folder(tmp_path, course=course), write_data(tmp_path)) == ["address-missing"]


def test_메뉴_경로의_한_단이_번역_사전에_없으면_잡는다(tmp_path):
    # 설명서 소제목 이름 "Zoom In/Out"은 화면 메뉴 글자가 아니다(화면에는 Zoom In, Zoom Out이 따로 있다).
    common = COMMON.replace("View > Navigation > Orbit", "View > Navigation > Zoom In/Out")
    assert data_kinds(write_folder(tmp_path, common=common), write_data(tmp_path)) == ["menu-unknown"]


def test_한국어_번역이_없어도_fr_po에_있는_화면_글자는_받아들인다(tmp_path):
    # COURSE의 Mesh > Merge > At Center에서 At Center는 FR_PO에만 있다.
    assert "At Center" not in KO_PO
    assert data_kinds(write_folder(tmp_path), write_data(tmp_path)) == []


def test_메뉴가_없음이면_메뉴_경로를_보지_않는다(tmp_path):
    course = COURSE.replace("메뉴: Mesh > Merge > At Center", "메뉴: 없음")
    assert data_kinds(write_folder(tmp_path, course=course), write_data(tmp_path)) == []


def test_설명서의_말줄임표는_화면의_점_세_개와_같게_본다(tmp_path):
    common = COMMON.replace("View > Navigation > Orbit", "View > Navigation…")
    data = write_data(tmp_path, ko=KO_PO + po(("*", "Navigation...", "내비게이션...")))
    assert data_kinds(write_folder(tmp_path, common=common), data) == []


def test_설명서와_8단어_이상_똑같이_겹치면_잡는다(tmp_path):
    # 대소문자·문장부호가 달라도 같은 낱말이 같은 차례로 이어지면 옮긴 것으로 본다.
    copied = "편집 모드에서 Combines the selected vertices, into one single VERTEX 한다."
    course = COURSE.replace("편집 모드에서 끝 모서리를 골라 한 점으로 모은다.", copied)
    problems = check_folder(write_folder(tmp_path, course=course), load_manual(write_data(tmp_path)))
    assert [(p.kind, p.where) for p in problems] == [("copied", "구간[1].단계[1].쉬운 설명")]
    assert "https://x/merge" in problems[0].message  # 어느 청크와 겹쳤는지 링크를 보여 준다


def test_설명서와_7단어까지_겹치는_것은_받아들인다(tmp_path):
    course = COURSE.replace("물체 모드에서는 Merge 메뉴가 보이지 않는다.", "combines the selected vertices into one single 로 모은다.")
    assert data_kinds(write_folder(tmp_path, course=course), write_data(tmp_path)) == []


def test_자료_파일이_하나라도_없으면_자료_검사를_건너뛴다(tmp_path):
    data = write_data(tmp_path)
    (data / "ui_ko_5.2" / "fr.po").unlink()
    assert load_manual(data) is None
    assert load_manual(tmp_path / "없는 폴더") is None


DATA = Path(__file__).resolve().parent.parent / "data"


def test_저장소의_연습_과정_파일은_실제_자료로도_검사를_통과한다():
    manual = load_manual(DATA)
    if manual is None:
        pytest.skip("data/에 청크·ko.po·fr.po가 없음(커밋하지 않는 자료)")
    assert check_folder(COURSES, manual) == []


def test_조작에_안내_말이_빠지면_잡는다(tmp_path):
    course = COURSE.replace("            안내: 이제 M을 눌러 가운데로 모아 볼까요?\n", "")
    assert kinds(write_folder(tmp_path, course=course)) == ["missing"]


def test_감지는_빼도_되고_끝난_조건과_같은_종류만_받는다(tmp_path):
    without = COURSE.replace("            감지:\n              - 방금 조작: mesh.merge\n", "")
    assert kinds(write_folder(tmp_path, course=without)) == []
    wrong_kind = COURSE.replace("              - 방금 조작: mesh.merge\n", "              - 꼭짓점 수: 8\n")
    assert kinds(write_folder(tmp_path, course=wrong_kind)) == ["condition-kind"]
    wrong_value = COURSE.replace("              - 방금 조작: mesh.merge\n", "              - 방금 조작: Merge At Center\n")
    assert kinds(write_folder(tmp_path, course=wrong_value)) == ["condition-value"]
