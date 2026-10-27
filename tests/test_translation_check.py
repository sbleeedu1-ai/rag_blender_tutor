"""번역 검사(티켓 31 3단계): 이름표의 화면 글자, 단축키, 잘림.

청크·사전·번역은 모두 지어낸 것이다(설명서 원문 아님).
"""

import json

import pytest

from blender_tutor.manual_chunks import Chunk
from blender_tutor.menu_names import MenuName, MenuNames, Source, Translation
from blender_tutor.translate import BodyNames, pieces
from blender_tutor.translation_check import Problem, check, english_dropped, reviewed


def name(english: str, *translations: tuple[str, tuple[str, ...]]) -> MenuName:
    return MenuName(english, tuple(Translation(k, c) for k, c in translations), 1, "x", (Source.UI,))


NAMES = MenuNames([
    name("Edit Mode", ("에디트 모드", ("*",))),
    name("Add", ("추가", ("*",))),
    name("Mesh", ("메시", ("*",))),
    name("Width"),  # 화면도 영어
    name("Bevel Width", ("베벨 폭", ("*",))),
])
BODY = BodyNames({"3D Cursor": "3D 커서", "Cursor": "커서"})


def piece(body: str, ui_names: tuple[str, ...] = ()):
    return pieces([Chunk("modeling/bevel", "a", "modeling", "modeling", "Bevel", ("Options",), body, ui_names=ui_names)])[0]


KEY = "modeling/bevel.html#a/1"


def test_이름표의_화면_글자가_있으면_괄호_영어를_빼도_문제가_아니다():
    p = piece("Go to Edit Mode and use Add ‣ Mesh.", ui_names=("Edit Mode", "Add ‣ Mesh"))
    assert check(p, "베벨 > 옵션\n\n에디트 모드로 가서 추가(Add) ‣ 메시(Mesh)를 씁니다.", NAMES, BODY) == []
    assert check(p, "베벨 > 옵션\n\n에디트 모드(Edit Mode)로 가서 추가 ‣ 메시를 씁니다.", NAMES, BODY) == []


def test_화면_글자가_없으면_글자_없음이다():
    p = piece("Go to Edit Mode.", ui_names=("Edit Mode",))
    assert check(p, "베벨 > 옵션\n\n편집 모드(Edit Mode)로 갑니다.", NAMES, BODY) == [
        Problem(KEY, "글자 없음", "에디트 모드(Edit Mode)")
    ]


def test_영어로_둘_이름을_한국어로_옮기면_문제다():
    p = piece("Set the Width.", ui_names=("Width",))
    assert check(p, "베벨 > 옵션\n\nWidth를 정합니다.", NAMES, BODY) == []
    assert check(p, "베벨 > 옵션\n\n폭(Width)을 정합니다.", NAMES, BODY) == [Problem(KEY, "영어로 둘 이름을 옮김", "Width")]
    assert check(p, "베벨 > 옵션\n\n폭을 정합니다.", NAMES, BODY) == [Problem(KEY, "영어로 둘 이름을 옮김", "Width")]


def test_긴_이름_안에만_나오는_짧은_이름은_따로_보지_않는다():
    p = piece("Set the Bevel Width.", ui_names=("Bevel Width", "Width"))  # Width는 Bevel Width 안에만 있다
    assert check(p, "베벨 > 옵션\n\n베벨 폭을 정합니다.", NAMES, BODY) == []
    alone = piece("Set the Bevel Width, then the Width.", ui_names=("Bevel Width", "Width"))  # 따로도 나오면 본다
    assert check(alone, "베벨 > 옵션\n\n베벨 폭을 정하고 폭을 정합니다.", NAMES, BODY) == [
        Problem(KEY, "영어로 둘 이름을 옮김", "Width")
    ]


def test_원문의_단축키가_번역에서_사라지면_문제다():
    p = piece("Previous Folder Backspace, Alt-Left, Mouse4. Click LMB or press Tab, Ctrl-F, NumpadPeriod, F2.")
    kept = "베벨 > 옵션\n\n이전 폴더 Backspace, Alt-Left, Mouse4. 마우스 왼쪽 버튼을 누르거나 탭, Ctrl-F, NumpadPeriod, F2."
    assert check(p, kept, NAMES, BODY) == []  # LMB·Tab을 풀어 쓴 것은 괜찮다(사용자 결정, HISTORY [71])
    assert check(p, "베벨 > 옵션\n\n이전 폴더 Backspace, , . 클릭하거나 탭, Ctrl-F, NumpadPeriod.", NAMES, BODY) == [
        Problem(KEY, "키 사라짐", "Alt-Left, Mouse4, F2")
    ]


def test_원문보다_한참_짧거나_한글이_없으면_덜_옮긴_것이다():
    p = piece("word " * 60)
    assert check(p, "베벨 > 옵션\n\n" + "낱말 " * 30, NAMES, BODY) == []
    assert check(p, "베벨 > 옵션\n\n낱말", NAMES, BODY) == [Problem(KEY, "잘림", "원문의 0.03배")]  # 317글자 → 11글자
    assert check(p, "Bevel > Options\n\n" + "word " * 60, NAMES, BODY) == [Problem(KEY, "번역 안 됨", "한글 없음")]


def test_괄호_영어를_뺀_수를_따로_센다():
    p = piece("Go to Edit Mode and use Add ‣ Mesh.", ui_names=("Edit Mode", "Add ‣ Mesh"))
    assert english_dropped(p, "에디트 모드로 가서 추가(Add) ‣ 메시(Mesh)를 씁니다.", NAMES, BODY) == 1


def write(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_고친_줄_파일이_있으면_원본_위에_덮어_읽는다(tmp_path):
    original = tmp_path / "ko_none.jsonl"
    write(original, [{"key": "a/1", "korean": "모델 번역"}, {"key": "b/1", "korean": "모델 번역"}])
    assert reviewed(original) == {"a/1": "모델 번역", "b/1": "모델 번역"}
    write(tmp_path / "ko_none_fixes.jsonl", [{"key": "b/1", "korean": "고친 번역", "why": "글자 없음: 에디트 모드"}])
    assert reviewed(original) == {"a/1": "모델 번역", "b/1": "고친 번역"}


def test_원본에_없는_청크를_고친_줄은_바로_알린다(tmp_path):
    original = tmp_path / "ko_none.jsonl"
    write(original, [{"key": "a/1", "korean": "모델 번역"}])
    write(tmp_path / "ko_none_fixes.jsonl", [{"key": "x/1", "korean": "고친 번역", "why": "오타"}])
    with pytest.raises(ValueError, match="x/1"):
        reviewed(original)
