"""자료 준비: 메뉴 이름 한국어-영어 짝(티켓 20).

작은 가짜 ko.po(직접 쓴 것, Blender 번역 원문 아님)와 손으로 만든 청크를 넣고,
블렌더 표기마다 번역 없음·하나·여러 개를 가르는지, 한국어로 영어를 찾는지 본다.
"""

from pathlib import Path

import pytest

from blender_tutor.manual_chunks import Chunk
from blender_tutor.menu_names import MenuName, MenuNames, Source, Status, Translation, build_menu_names, read_po

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
    assert names.get("How the Wand Waves") is None  # 사전에 없는 제목은 블렌더 표기가 아니라고 보고 버린다
    # 어디서 뽑았는지 적는다(제목에서만 뽑은 것은 따로 검수)
    assert [names.get(e).sources for e in ("Add", "Array", "Options")] == [
        (Source.UI,),
        (Source.TITLE,),
        (Source.TITLE,),
    ]


def test_철자_표에_있는_이름은_화면_철자로_ko_po를_찾는다():
    # 지어낸 사전: 설명서는 "Wandsphere", 화면 메뉴는 "Wand Sphere"(Operator 문맥)를 쓴다고 치고
    po = PO + (
        '\nmsgctxt "Mesh"\nmsgid "Wandsphere"\nmsgstr "완드구슬"\n'
        '\nmsgid "Wand Sphere"\nmsgstr "완드 스피어"\n'
        '\nmsgctxt "Operator"\nmsgid "Wand Sphere"\nmsgstr "완드 구체"\n'
    )
    page = chunk("first", ui_names=("Add ‣ Wandsphere",))

    names = build_menu_names([page], po, aliases={"Wandsphere": "Wand Sphere"})

    name = names.get("Wandsphere")  # 이름은 설명서 철자 그대로(모델이 설명서 영어를 옮겨 쓰므로)
    assert name.translations == (Translation("완드 스피어", ("*",)), Translation("완드 구체", ("Operator",)))
    assert names.english_for("완드 구체") == ("Wandsphere",)
    assert names.english_for("완드구슬") == ()  # 화면이 쓰지 않는 철자의 번역은 버린다
    assert build_menu_names([page], po).get("Wandsphere").translations == (Translation("완드구슬", ("Mesh",)),)


def test_철자_표_파일을_읽고_저장소의_표는_실제_ko_po에_있다():
    aliases = MenuNames.load_aliases(REPO / "menu_aliases.json")
    po = REPO / "data" / "ui_ko_5.2" / "ko.po"
    if not po.exists():
        pytest.skip("data/에 ko.po가 없음(커밋하지 않는 자료)")
    spellings = {english for _, english, _ in read_po(po.read_text(encoding="utf-8"))}
    assert all(screen in spellings for screen in aliases.values())


def test_옵션_이름은_출처를_옵션으로_적는다():
    names = build_menu_names([chunk("first", ui_names=("Mesh",), options=("Mesh", "Apply"))], PO)

    assert names.get("Mesh").sources == (Source.UI, Source.OPTION)
    assert names.get("Apply").sources == (Source.OPTION,)


def test_띄어쓰기만_다른_번역이_둘이어도_영어는_한_번만_돌려준다():
    po = 'msgid "Wave"\nmsgstr "웨이브 모드"\n\nmsgctxt "Operator"\nmsgid "Wave"\nmsgstr "웨이브모드"\n'

    names = build_menu_names([chunk("first", ("Wave",))], po)

    assert names.english_for("웨이브 모드") == ("Wave",)


# 번역률 100%인 다른 언어 사전(fr.po 꼴). Blender가 쓰는 (문맥, 영어) 전체 목록으로 쓴다
FULL_PO = '''
msgctxt "Operator"
msgid "At Center"
msgstr "Au centre"

msgctxt "Mesh"
msgid "At Center"
msgstr "Au centre"

msgctxt "Operator"
msgid "Add"
msgstr "Ajouter"
'''


def test_한국어_번역이_빠진_문맥이_있으면_영어_그대로를_후보로_더해_검수에_넘긴다():
    po = PO + '\nmsgctxt "Operator"\nmsgid "At Center"\nmsgstr "센터에서"\n'

    names = build_menu_names([chunk("first", ("Add ‣ At Center",))], po, FULL_PO)

    at_center = names.get("At Center")
    assert at_center.status == Status.MANY
    assert at_center.translations == (Translation("센터에서", ("Operator",)), Translation("At Center", ("Mesh",)))
    assert names.get("Add").status == Status.ONE  # 쓰는 문맥 모두에 번역이 있으면 그대로
    assert [name.english for name in names.to_review()] == ["At Center"]


# 여러 번역의 고정한 짝(티켓 23): 영어 이름 → 화면이 쓰는 문맥. 저장소의 menu_choices.json에 커밋한다

REPO = Path(__file__).resolve().parents[1]
CHOICE_NAMES = [
    MenuName("Apply", (Translation("적용", ("*", "Operator")), Translation("신청하기", ("WindowManager",))), 1, ""),
    MenuName("Mesh", (Translation("메시", ("*",)),), 1, ""),
]


def test_고정한_짝의_문맥으로_화면_한국어를_고른다():
    assert MenuNames(CHOICE_NAMES, {"Apply": "WindowManager"}).korean("Apply") == "신청하기"
    assert MenuNames(CHOICE_NAMES).korean("Apply") is None  # 고정 전은 영어 그대로


def test_바로_앞_단을_붙인_고정_짝이_있으면_그_메뉴_아래서는_그_문맥을_쓴다():
    # 지어낸 예: 같은 Apply가 Object 메뉴 아래에서는 WindowManager 문맥 글자로 보인다고 치고
    names = MenuNames(CHOICE_NAMES, {"Apply": "*", "Object > Apply": "WindowManager"})
    assert names.korean("Apply", parent="Object") == "신청하기"
    assert names.korean("Apply", parent="Mesh") == "적용"  # 다른 메뉴 아래는 이름 하나의 짝
    assert names.korean("Apply") == "적용"
    assert names.korean("Apply", parent=" object ") == "적용"  # 대소문자가 다르면 다른 메뉴(설명서 영어 그대로 적음)


def test_경로_열쇠는_설명서의_경로_글자와_띄어쓰기를_가리지_않는다():
    names = MenuNames(CHOICE_NAMES, {"Object‣Apply": "WindowManager"})
    assert names.korean("Apply", parent=" Object ") == "신청하기"
    assert names.korean("Apply") is None  # 이름 하나의 짝이 없으면 영어 그대로


@pytest.mark.parametrize(
    "choices",
    [
        {"Aply": "Operator"},  # 사전에 없는 이름(오타)
        {"Apply": "Mesh"},  # 그 이름에 없는 문맥
        {"Mesh": "*"},  # 번역이 하나라 고를 것이 없음
        {"Object > Aply": "Operator"},  # 경로 열쇠도 같은 검사
        {"Object > Apply": "Mesh"},
        {" > Apply": "Operator"},  # 앞 단이 빈 경로
    ],
)
def test_잘못된_고정_짝은_바로_알린다(choices):
    with pytest.raises(ValueError):
        MenuNames(CHOICE_NAMES, choices)


def test_고정_짝_파일을_읽는다(tmp_path):
    path = tmp_path / "menu_choices.json"
    path.write_text('{"Apply": "WindowManager"}', encoding="utf-8")
    assert MenuNames.load_choices(path) == {"Apply": "WindowManager"}


# 제목에서만 뽑은 이름의 통과 목록(티켓 31 검수): 통과한 것만 질문 찾기에 쓴다. 저장소의 menu_titles.json에 커밋한다
TITLE_NAMES = [
    MenuName("Join", (Translation("합치기", ("*",)),), 1, "", (Source.UI,)),
    MenuName("Solidify", (Translation("솔리디파이", ("*",)),), 1, "", (Source.TITLE,)),
    MenuName("Recent", (Translation("최근", ("*",)),), 1, "", (Source.TITLE,)),
]


def test_통과한_제목만_질문에서_찾는다():
    question = "최근에 솔리디파이를 합치려면"
    assert MenuNames(TITLE_NAMES, titles=["Solidify"]).english_in(question) == ("Solidify", "Join")
    assert MenuNames(TITLE_NAMES).english_in(question) == ("Join",)  # 통과 목록이 없으면 제목은 모두 뺀다


@pytest.mark.parametrize("titles", [["Solidfy"], ["Join"]])  # 사전에 없는 이름(오타), 제목에서만 뽑은 이름이 아님
def test_잘못된_통과_목록은_바로_알린다(titles):
    with pytest.raises(ValueError):
        MenuNames(TITLE_NAMES, titles=titles)


def test_통과_제목_파일을_읽는다(tmp_path):
    path = tmp_path / "menu_titles.json"
    path.write_text('["Solidify"]', encoding="utf-8")
    assert MenuNames.load_titles(path) == ["Solidify"]


def test_저장소의_고정_짝과_통과_제목은_실제_사전과_맞는다():
    dictionary = REPO / "data" / "menu_names" / "menu_names.json"
    if not dictionary.exists():
        pytest.skip("data/에 메뉴 이름 사전이 없음(커밋하지 않는 자료)")
    choices = MenuNames.load_choices(REPO / "menu_choices.json")
    titles = MenuNames.load_titles(REPO / "menu_titles.json")
    MenuNames.load(dictionary, choices, titles)  # 틀리면 ValueError
