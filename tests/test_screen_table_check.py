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
    assert stc.check_rows([HEAD, FIXED_ROW], tmp_path) == []


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
