"""연습 과정 파일 검사(시험 경계 ③).

일부러 틀린 작은 YAML을 임시 폴더에 써 넣고, 검사가 돌려준 문제의 종류만 본다.
"""

from pathlib import Path

import pytest

from blender_tutor.course_check import check_folder

# 검사를 통과하는 가장 작은 공통 준비 파일과 연습 과정 파일.
# 테스트마다 한 군데만 바꿔서 틀리게 만든다.
COMMON = """\
이름표: common
이름: 공통 준비
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
        먼저 볼 소제목:
          - modeling/meshes/editing/mesh/merge.html#merge
        끝난 조건:
          - 모드: EDIT
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


def test_정해진_7가지_밖의_끝난_조건_종류를_잡는다(tmp_path):
    course = COURSE.replace("          - 모드: EDIT\n", "          - 꼭짓점 수: 8\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["condition-kind"]


def test_7가지_끝난_조건_종류는_모두_받아들인다(tmp_path):
    conditions = """\
          - 모드: EDIT
          - 방금 조작: mesh.merge
          - 물체 수 늘어남: 1
          - 모디파이어: SOLIDIFY
          - 재질 슬롯 수: 2
          - 배율: [1, 1, 1]
          - 크기 비율: 3
"""
    course = COURSE.replace("          - 모드: EDIT\n          - 방금 조작: mesh.merge\n", conditions)
    assert kinds(write_folder(tmp_path, course=course)) == []


def test_끝난_조건이_종류_값_한_줄이_아니면_잡는다(tmp_path):
    course = COURSE.replace("          - 모드: EDIT\n", "          - 모드: EDIT\n            배율: [1, 1, 1]\n")
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
    course = COURSE.replace("          - 모드: EDIT\n", f"          - 모드: {value}\n")
    assert kinds(write_folder(tmp_path, course=course)) == ["yaml-trap" if value else "missing"]


def test_연습_과정끼리_맨_위_이름표가_겹치면_잡는다(tmp_path):
    write_folder(tmp_path)
    (tmp_path / "shield.yaml").write_text(COURSE, encoding="utf-8")
    assert kinds(tmp_path) == ["duplicate-label"]


def test_yaml이_아닌_확장자의_파일을_알린다(tmp_path):
    write_folder(tmp_path)
    (tmp_path / "axe.yml").write_text(COURSE.replace("sword", "axe"), encoding="utf-8")
    assert kinds(tmp_path) == ["file-name"]


COURSES = Path(__file__).resolve().parent.parent / "courses"


def test_저장소의_연습_과정_파일은_검사를_통과한다():
    assert (COURSES / "_common.yaml").is_file()
    assert check_folder(COURSES) == []
