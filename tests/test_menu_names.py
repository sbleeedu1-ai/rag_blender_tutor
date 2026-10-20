"""자료 준비: 메뉴 이름 한국어-영어 짝(티켓 20).

작은 가짜 ko.po(직접 쓴 것, Blender 번역 원문 아님)와 손으로 만든 청크를 넣고,
화면 이름마다 번역 없음·하나·여러 개를 가르는지, 한국어로 영어를 찾는지 본다.
"""

from blender_tutor.manual_chunks import Chunk
from blender_tutor.menu_names import MenuNames, Source, Status, Translation, build_menu_names

PO = r'''
msgid ""
msgstr ""
"Project-Id-Version: Fake\n"
"Language: ko\n"

msgctxt "Operator"
msgid "Add"
msgstr "추가"

msgid "Mesh"
msgstr "메시"

msgid "Apply"
msgstr "적용"

msgctxt "Operator"
msgid "Apply"
msgstr "적용"

msgctxt "WindowManager"
msgid "Apply"
msgstr "신청하기"

msgid "Array"
msgstr "배열"

msgid "Array (Legacy)"
msgstr "배열 (레거시)"

msgid "Translate"
msgstr "옮기기"

msgid "Translation"
msgstr "옮기기"

msgid "Select Pattern..."
msgstr "패턴을 선택..."

msgid ""
"Quote \"Wave\" "
"Mode"
msgstr ""
"\"웨이브\" "
"모드"
'''


def chunk(url_anchor: str, ui_names: tuple[str, ...] = (), options: tuple[str, ...] = ()) -> Chunk:
    return Chunk(
        page_path="modeling/wands/wand_tool",
        anchor=url_anchor,
        field="modeling",
        group="modeling/wands",
        page_title="Wand Tool",
        headings=(),
        body="Body.",
        options=options,
        ui_names=ui_names,
    )


URL = "https://docs.blender.org/manual/en/5.2/modeling/wands/wand_tool.html#"


def test_메뉴_경로를_나눈_이름_버튼_이름_옵션_이름을_ko_po와_짝짓는다():
    chunks = [chunk("first", ui_names=("Add ‣ Mesh", "Array"), options=("Array (Legacy)",)), chunk("second", ("Mesh",))]

    names = build_menu_names(chunks, PO)

    add, mesh, legacy = names.get("Add"), names.get("Mesh"), names.get("Array (Legacy)")
    assert (add.status, add.translations) == (Status.ONE, (Translation("추가", ("Operator",)),))
    assert (mesh.status, mesh.translations) == (Status.ONE, (Translation("메시", ("*",)),))  # *는 기본 문맥
    assert legacy.translations == (Translation("배열 (레거시)", ("*",)),)
    # 몇 청크에 나왔는지, 처음 나온 곳 링크(검수 때 실제 쪽을 열어 보도록)
    assert (mesh.chunks, mesh.example) == (2, URL + "first")


def test_사전에_없는_이름은_번역_없음이다():
    names = build_menu_names([chunk("first", ("Add ‣ At Center",))], PO)

    at_center = names.get("At Center")
    assert (at_center.status, at_center.translations) == (Status.NONE, ())


def test_문맥마다_번역이_다르면_여러_개이고_같은_번역은_문맥을_모은다():
    names = build_menu_names([chunk("first", ("Apply",))], PO)

    apply = names.get("Apply")
    assert apply.status == Status.MANY
    assert apply.translations == (
        Translation("적용", ("*", "Operator")),
        Translation("신청하기", ("WindowManager",)),
    )


def test_설명서의_말줄임표와_여러_줄_글자도_사전과_짝짓는다():
    names = build_menu_names([chunk("first", ("Select ‣ Select Pattern…", 'Quote "Wave" Mode'))], PO)

    assert names.get("Select Pattern…").translations == (Translation("패턴을 선택...", ("*",)),)
    assert names.get('Quote "Wave" Mode').translations == (Translation('"웨이브" 모드', ("*",)),)


def test_한국어_메뉴_이름으로_영어를_찾고_띄어쓰기는_가리지_않는다():
    chunks = [chunk("first", ("Array", "Array (Legacy)", "Translate", "Translation", "Apply"))]

    names = build_menu_names(chunks, PO)

    assert names.english_for("배열") == ("Array",)
    assert names.english_for("배열(레거시)") == ("Array (Legacy)",)
    assert names.english_for("옮기기") == ("Translate", "Translation")  # 같은 한국어가 여러 영어면 모두
    assert names.english_for("신청하기") == ("Apply",)  # 여러 번역 가운데 어느 것으로도 찾는다
    assert names.english_for("메시") == ()  # 설명서에 안 나온 이름은 사전에 없다


def test_여러_번역은_많이_나온_차례로_검수_목록에_뽑는다():
    chunks = [chunk("first", ("Apply", "Mesh")), chunk("second", ("Translate", "Apply")), chunk("third", ("Apply",))]
    po = PO + '\nmsgctxt "Preferences"\nmsgid "Translate"\nmsgstr "번역"\n'

    names = build_menu_names(chunks, po)

    assert [name.english for name in names.to_review()] == ["Apply", "Translate"]


def test_사전을_파일로_쓰고_다시_읽어도_같다(tmp_path):
    names = build_menu_names([chunk("first", ("Add ‣ Mesh", "Apply", "At Center"))], PO)
    path = tmp_path / "menu_names.json"

    names.save(path)
    again = MenuNames.load(path)

    assert [again.get(english) for english in ("Add", "Mesh", "Apply", "At Center")] == [
        names.get(english) for english in ("Add", "Mesh", "Apply", "At Center")
    ]
    assert again.english_for("신청하기") == ("Apply",)


def test_쪽_제목_소제목은_ko_po에_있을_때만_담고_뒤의_Modifier_등을_뗀_이름도_담는다():
    po = PO + '\nmsgid "Array Modifier"\nmsgstr "배열 모디파이어"\n\nmsgid "Options"\nmsgstr "옵션"\n'
    page = Chunk(
        page_path="modeling/modifiers/generate/array",
        anchor="options",
        field="modeling",
        group="modeling/modifiers/generate",
        page_title="Array Modifier",
        headings=("Options", "How the Wand Waves"),
        body="Body.",
        ui_names=("Add",),
    )

    names = build_menu_names([page], po)

    assert names.english_for("배열") == ("Array",)
    assert names.english_for("배열 모디파이어") == ("Array Modifier",)
    assert names.get("Options").translations == (Translation("옵션", ("*",)),)
    assert names.get("How the Wand Waves") is None  # 사전에 없는 제목은 화면 이름이 아니라고 보고 버린다
    # 어디서 뽑았는지 적는다(제목에서만 뽑은 것은 따로 검수)
    assert [names.get(e).sources for e in ("Add", "Array", "Options")] == [
        (Source.UI,),
        (Source.TITLE,),
        (Source.TITLE,),
    ]


def test_옵션_이름은_출처를_옵션으로_적는다():
    names = build_menu_names([chunk("first", ui_names=("Mesh",), options=("Mesh", "Apply"))], PO)

    assert names.get("Mesh").sources == (Source.UI, Source.OPTION)
    assert names.get("Apply").sources == (Source.OPTION,)
