"""화면 확인 표 검사(.claude/tools/screen_table_check.py) 시험. HISTORY [444].

지난 실수 원문: 11-18 화면확인.tsv의 2D Vector Value 줄은 소스만 읽고(증거 "읽기만") "일반 화면에 없음"으로 적혔다.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("screen_table_check", ROOT / ".claude/tools/screen_table_check.py")
stc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stc)

HEAD = ["영어", "판정", "자리", "화면 글자", "그림", "화면 증거", "ko.po 번역", "화면 글자=번역"]
OLD_ROW = ["2D Vector Value", "일반 화면에 없음(다른 글자로 그림), 데이터 API는 안 봄",
           "스프레드시트 행 필터 value_float2·value_int2 속성 이름.", "-", "-", "읽기만", "2D 벡터 값", "같음"]
FIXED_ROW = ["2D Vector Value", "툴팁 제목으로만 뜸(칸 글자는 다름)", "행 필터 '값' 칸 툴팁",
             "2D 벡터 값", "화면/58_행필터_2D벡터값_툴팁.jpg", "봄", "2D 벡터 값", "같음"]


def test_지난_실수_줄은_걸린다(tmp_path):
    bad = stc.check_rows([HEAD, OLD_ROW], tmp_path)
    assert [name for name, _ in bad] == ["2D Vector Value"]


def test_그림이_있는_화면_판정은_통과(tmp_path):
    (tmp_path / "화면").mkdir()
    (tmp_path / "화면/58_행필터_2D벡터값_툴팁.jpg").write_bytes(b"x")
    # 설정 칸 검사([457]) 뒤로는 설정 칸도 있어야 통과
    assert stc.check_rows([HEAD + ["설정"], FIXED_ROW + ["새 데이터 켬"]], tmp_path) == []


def test_그림_파일이_없으면_걸린다(tmp_path):
    bad = stc.check_rows([HEAD, FIXED_ROW], tmp_path)
    assert "그림 파일이 없음" in bad[0][1]


def test_소스로만_밝힌_줄은_통과(tmp_path):
    row = list(OLD_ROW)
    row[1] = "소스로만 판정: 일반 화면에 없음"
    assert stc.check_rows([HEAD, row], tmp_path) == []


def test_증거_칸이_없는_표도_그림을_본다(tmp_path):
    head = ["영어", "판정", "화면 글자", "그림"]
    row = ["(De)select All Files", "실행으로 확인(키맵 항목 이름, 화면은 안 봄)", "모든 파일을 선택(취소)", "ko_gui.log KMHIT"]
    assert [n for n, _ in stc.check_rows([head, row], tmp_path)] == ["(De)select All Files"]


# '설정' 칸 검사(HISTORY [457]). 지난 실수 원문: 11-18 오전 화면확인.tsv는 장면 스크립트가 '새로운 데이터' 번역을 꺼 둔 채 찍었는데
# 표에 설정 칸이 없어 아무도 몰랐다. 그 표의 4 by 4 Float Matrix 줄("Attribute"로 뜸)은 켜면 "속성"으로 뜬다([455]).
MORNING_HEAD = ["영어", "판정", "자리", "화면 글자", "그림", "화면 증거", "ko.po 번역", "화면 글자=번역"]
MORNING_ROW = ["4 by 4 Float Matrix", "화면에 없음을 봄",
               '속성 추가 창에서 이름을 비우고 4x4 매트릭스로 추가하면 목록에 "Attribute"로 뜸. 파이썬으로 이름 비워 만들어도 "Attribute"',
               "-", "화면/66_속성추가_이름비움_4x4.jpg", "없음을 봄", "4 x 4 실수 매트릭스", "-"]
SET_HEAD = ["영어", "판정", "그림", "화면 증거", "설정"]


def _picture(tmp_path, name="화면/01.jpg"):
    (tmp_path / "화면").mkdir(exist_ok=True)
    (tmp_path / name).write_bytes(b"x")
    return name


def test_설정_칸이_없는_표의_화면_판정은_걸린다(tmp_path):
    _picture(tmp_path, MORNING_ROW[4])
    bad = stc.check_rows([MORNING_HEAD, MORNING_ROW], tmp_path)
    assert [(n, "설정" in why) for n, why in bad] == [("4 by 4 Float Matrix", True)]


def test_설정_칸이_비면_걸린다(tmp_path):
    pic = _picture(tmp_path)
    for value in ("", "-"):
        assert len(stc.check_rows([SET_HEAD, ["Bevel", "우리 자리", pic, "봄", value]], tmp_path)) == 1


def test_끔인데_까닭이_없으면_걸리고_있으면_통과(tmp_path):
    pic = _picture(tmp_path)
    assert len(stc.check_rows([SET_HEAD, ["Bevel", "새 데이터 번역 끔: 스택 이름이 영어", pic, "봄", "새 데이터 끔"]], tmp_path)) == 1
    assert stc.check_rows([SET_HEAD, ["Bevel", "새 데이터 번역 끔: 스택 이름이 영어", pic, "봄", "새 데이터 끔(켬과 견주려고)"]], tmp_path) == []


def test_켬은_통과하고_소스로만_줄은_설정을_안_본다(tmp_path):
    pic = _picture(tmp_path)
    assert stc.check_rows([SET_HEAD, ["Bevel", "우리 자리", pic, "봄", "새 데이터 켬"]], tmp_path) == []
    assert stc.check_rows([SET_HEAD, ["Up", "소스로만: fr.po만", "-", "읽기만", "-"]], tmp_path) == []
