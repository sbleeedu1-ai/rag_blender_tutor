"""설명서 번역(티켓 31 2단계): 청크별 이름표, 번역 돌리기, 비용 어림, 시험용 청크 고르기.

모델은 늘 가짜를 끼운다(돈이 드는 실제 호출은 시험하지 않는다). 청크와 사전은 모두 지어낸 것이다(설명서 원문 아님).
"""

import json

import pytest

from blender_tutor.manual_chunks import Chunk
from blender_tutor.menu_names import MenuName, MenuNames, Source, Translation
from blender_tutor.translate import (
    KOREAN_PER_ENGLISH,
    BodyNames,
    TranslateError,
    estimate,
    glossary,
    pieces,
    sample,
    screen_words,
    translate,
)


def chunk(body: str, ui_names: tuple[str, ...] = (), options: tuple[str, ...] = (), anchor: str = "a",
          reference: tuple[tuple[str, str], ...] = ()) -> Chunk:
    return Chunk("modeling/bevel", anchor, "modeling", "modeling", "Bevel", ("Options",), body,
                 options=options, reference=reference, ui_names=ui_names)


def name(english: str, *translations: tuple[str, tuple[str, ...]]) -> MenuName:
    return MenuName(english, tuple(Translation(k, c) for k, c in translations), 1, "x", (Source.UI,))


NAMES = MenuNames(
    [
        name("Edit Mode", ("에디트 모드", ("*",))),
        name("Width"),  # 번역 없음: 화면도 영어
        name("Add", ("추가", ("*",))),
        name("Mesh", ("메시", ("*",))),
        name("Empty", ("비어 있음", ("*",)), ("엠프티", ("ID",))),
        name("Smart UV Project", ("스마트 UV 투사", ("Operator",)), ("스마트 UV 프로젝트", ("*",))),
        name("UV", ("UV", ("*",))),  # 한국어 화면도 같은 글자
        name("3D Viewport", ("3D 뷰포트", ("*",))),
    ],
    choices={"Empty": "ID", "Add > Empty": "*"},
)


def test_이름표는_번역이_있으면_한국어_괄호_영어_없으면_영어_그대로다():
    chunks = [chunk("Go to Edit Mode and set Width.", ui_names=("Edit Mode",), options=("Width",))]
    assert glossary(chunks, NAMES) == [("Edit Mode", "에디트 모드(Edit Mode)"), ("Width", "Width")]


def test_짝을_고르지_않은_여러_번역_이름은_영어_그대로다():
    assert glossary([chunk("Use Smart UV Project.", ui_names=("Smart UV Project",))], NAMES) == [
        ("Smart UV Project", "Smart UV Project")
    ]


def test_메뉴_경로는_단마다_바꾸고_앞_단에_따른_짝을_쓴다():
    chunks = [chunk("Add ‣ Mesh, Add ‣ Empty, Empty.", ui_names=("Add ‣ Mesh", "Add ‣ Empty", "Empty"))]
    assert glossary(chunks, NAMES) == [
        ("Add ‣ Mesh", "추가(Add) ‣ 메시(Mesh)"),
        ("Add ‣ Empty", "추가(Add) ‣ 비어 있음(Empty)"),
        ("Empty", "엠프티(Empty)"),
    ]


def test_한국어가_영어와_같은_글자면_괄호를_붙이지_않는다():
    assert glossary([chunk("UV ‣ Smart UV Project", ui_names=("UV ‣ Smart UV Project",))], NAMES) == [
        ("UV ‣ Smart UV Project", "UV ‣ Smart UV Project")
    ]


def test_모드_메뉴_단축키_상자의_편집기와_모드_이름도_이름표에_넣는다():
    box = (("Editor", "3D Viewport"), ("Mode", "Edit Mode, Width"), ("Shortcut", "U"))
    assert glossary([chunk("Reference ...", reference=box)], NAMES) == [
        ("3D Viewport", "3D 뷰포트(3D Viewport)"), ("Edit Mode", "에디트 모드(Edit Mode)"), ("Width", "Width")
    ]


def test_사전에_없는_것은_이름표에_넣지_않는다():  # 상자 칸에는 All Modes·and Pose Mode 같은 글 조각도 있어 보통 글로 번역하게 둔다
    box = (("Mode", "All Modes, Edit Mode"), ("Menu", "Add ‣ Nothing"))
    assert glossary([chunk("Reference ...", reference=box)], NAMES) == [("Edit Mode", "에디트 모드(Edit Mode)")]


def test_여러_청크의_이름표는_처음_나온_차례로_한_번씩이다():
    chunks = [chunk("a", ui_names=("Edit Mode",)), chunk("b", ui_names=("Width", "Edit Mode"))]
    assert [english for english, _ in glossary(chunks, NAMES)] == ["Edit Mode", "Width"]


TITLE_NAMES = MenuNames(
    [
        name("Mesh", ("메시", ("*",))),
        name("Empty", ("비어 있음", ("*",)), ("엠프티", ("ID",))),
        name("Smart UV Project", ("스마트 UV 투사", ("Operator",)), ("스마트 UV 프로젝트", ("*",))),
        name("UV", ("UV", ("*",))),
        name("Width"),
        MenuName("Usage", (Translation("사용법", ("*",)),), 1, "x", (Source.TITLE,)),  # 검수에서 떨어진 제목
        MenuName("Gizmos", (Translation("기즈모", ("*",)),), 1, "x", (Source.TITLE,)),  # 통과한 제목
    ],
    choices={"Empty": "ID"},
    titles=["Gizmos"],
)
PO = """
msgid "Subsurface Radius"
msgstr "부분체 반지름"

msgctxt "Operator"
msgid "Slab"
msgstr "슬래브"

msgid "Material"
msgstr "머티리얼"

msgctxt "ID"
msgid "Material"
msgstr "소재"

msgid "The type of data"
msgstr "데이터 유형"

msgid "Save file?"
msgstr "파일을 저장할까요?"

msgid "Usage"
msgstr "사용법"
"""


def test_화면_글자_표는_사전에서_한국어가_정해진_이름과_ko_po에서_번역이_하나뿐인_이름이다():
    words = screen_words(TITLE_NAMES, ["Gizmos"], PO)
    assert words == {
        "Mesh": "메시", "Empty": "엠프티", "Gizmos": "기즈모",  # 사전: 하나, 고정 짝, 통과 제목
        "Subsurface Radius": "부분체 반지름", "Slab": "슬래브",  # ko.po: 문맥이 달라도 번역이 하나면
    }
    # 빠진 것: 짝 없는 여러 번역(Smart UV Project), 화면도 영어(UV·Width), 떨어진 제목(Usage, ko.po에 있어도),
    # ko.po에서 번역이 여럿(Material), 관사로 시작하거나 문장 부호가 든 문구


BODY = BodyNames({"Mesh": "메시", "Material": "머티리얼", "Radius": "반경", "Subsurface Radius": "부분체 반지름",
                  "Object data": "오브젝트 데이터", "3D Viewport": "3D 뷰포트"})


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("Subsurface Radius is ignored.", ["Subsurface Radius"]),  # 여러 낱말 이름은 문장 첫머리여도
        ("You can select the Mesh here.", ["Mesh"]),  # 한 낱말 이름은 문장 중간 대문자일 때
        ("Mesh is shown. Material is not.", []),  # 문장 첫머리의 한 낱말은 일상 낱말일 수 있어 뺀다
        ("Choose a mesh and a material.", []),  # 대소문자가 다르면 이름이 아니다
        ("go to Mesh Material Properties", []),  # 붙은 대문자 낱말이 있으면 사전에 없는 더 긴 이름의 일부
        ("The Subsurface Radius, then the Mesh.", ["Subsurface Radius", "Mesh"]),  # 관사는 이름의 앞 단이 아니다
        ("the Object data-block holds it", []),  # 하이픈으로 이어진 낱말의 앞부분은 이름이 아니다
        ("in the 3D Viewport, the Mesh and the 3D Viewport", ["3D Viewport", "Mesh"]),  # 나온 차례로 한 번씩
    ],
)
def test_본문에서_화면_이름을_찾는다(text, found):
    assert BODY.find(text) == found


def test_이름표에_본문에서_찾은_이름을_뒤에_더하고_이미_있는_이름은_다시_넣지_않는다():
    chunks = [chunk("Use Add ‣ Mesh in the 3D Viewport, then the Mesh.", ui_names=("Add ‣ Mesh",))]
    assert glossary(chunks, NAMES, BODY) == [
        ("Add ‣ Mesh", "추가(Add) ‣ 메시(Mesh)"), ("3D Viewport", "3D 뷰포트(3D Viewport)")
    ]


def test_번역할_때_본문_이름을_이름표에_함께_보낸다(tmp_path):
    model = FakeModel()
    translate(pieces([chunk("Open the 3D Viewport.")]), NAMES, model, tmp_path / "ko.jsonl", body=BODY)
    assert model.asked[0]["glossary"] == {"3D Viewport": "3D 뷰포트(3D Viewport)"}


def test_청크_열쇠는_주소와_같은_주소_안의_차례다():
    chunks = [chunk("a", anchor="x"), chunk("b", anchor="x"), chunk("c", anchor="y")]
    assert [piece.key for piece in pieces(chunks)] == [
        "modeling/bevel.html#x/1", "modeling/bevel.html#x/2", "modeling/bevel.html#y/1"
    ]


class FakeModel:
    """물음에 든 청크마다 "번역:열쇠"를 돌려준다. skip에 든 열쇠는 빼고 답한다. 받은 물음을 모두 적어 둔다."""

    def __init__(self, skip: set[str] = frozenset()):
        self.skip = skip
        self.asked: list[dict] = []  # 물음마다 모델에게 보낸 JSON

    def ask(self, messages: list[dict[str, str]]) -> str:
        sent = json.loads(messages[-1]["content"])
        self.asked.append(sent)
        rows = [{"key": c["key"], "korean": f"번역:{c['key']}"} for c in sent["chunks"] if c["key"] not in self.skip]
        return json.dumps({"chunks": rows}, ensure_ascii=False)


def three():
    return pieces([
        chunk("Go to Edit Mode.", ui_names=("Edit Mode",), anchor="x"),
        chunk("Set Width.", options=("Width",), anchor="y"),
        chunk("Add ‣ Mesh.", ui_names=("Add ‣ Mesh",), anchor="z"),
    ])


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_묶음마다_그_청크의_글과_이름표만_보내고_번역을_한_줄에_하나씩_쓴다(tmp_path):
    out, model = tmp_path / "ko.jsonl", FakeModel()
    got = translate(three(), NAMES, model, out, batch=2)
    first, second = model.asked
    assert [c["key"] for c in first["chunks"]] == ["modeling/bevel.html#x/1", "modeling/bevel.html#y/1"]
    assert first["chunks"][0]["text"] == "Bevel > Options\n\nGo to Edit Mode."
    assert first["glossary"] == {"Edit Mode": "에디트 모드(Edit Mode)", "Width": "Width"}
    assert second["glossary"] == {"Add ‣ Mesh": "추가(Add) ‣ 메시(Mesh)"}
    assert lines(out) == [{"key": k, "korean": f"번역:{k}"} for k in got] and len(got) == 3


def test_파일에_이미_있는_청크는_다시_묻지_않는다(tmp_path):
    out = tmp_path / "ko.jsonl"
    translate(three()[:1], NAMES, FakeModel(), out)
    model = FakeModel()
    got = translate(three(), NAMES, model, out)
    assert [c["key"] for sent in model.asked for c in sent["chunks"]] == ["modeling/bevel.html#y/1", "modeling/bevel.html#z/1"]
    assert len(lines(out)) == 3 and list(got) == [piece.key for piece in three()]


def test_빠진_청크는_한_번_다시_묻고_그래도_없으면_받은_것을_남기고_멈춘다(tmp_path):
    out, model = tmp_path / "ko.jsonl", FakeModel(skip={"modeling/bevel.html#y/1"})
    with pytest.raises(TranslateError) as stopped:
        translate(three(), NAMES, model, out, batch=2)
    assert [[c["key"] for c in sent["chunks"]] for sent in model.asked] == [
        ["modeling/bevel.html#x/1", "modeling/bevel.html#y/1"], ["modeling/bevel.html#y/1"]
    ]  # 다음 묶음은 묻지 않는다(돈을 더 쓰지 않게)
    assert stopped.value.keys == ["modeling/bevel.html#y/1"]
    assert [row["key"] for row in lines(out)] == ["modeling/bevel.html#x/1"]


@pytest.mark.parametrize("answer", ["깨진 글", '{"chunks": [{"key": "modeling/bevel.html#x/1", "korean": "  "}]}'])
def test_깨진_답이나_빈_번역은_받지_않은_것으로_본다(tmp_path, answer):
    class Broken:
        def ask(self, messages):
            return answer
    with pytest.raises(TranslateError):
        translate(three()[:1], NAMES, Broken(), tmp_path / "ko.jsonl")


def test_비용_어림은_실제로_보낼_물음_수와_글_양을_센다():
    small = estimate(three(), NAMES, batch=2)
    assert small.requests == 2
    long = pieces([chunk("word " * 4000)])  # 본문 2만 글자 → 입력만 약 5천 토큰 더
    big = estimate(long, NAMES, batch=2)
    assert big.input_tokens > small.input_tokens + 4000
    assert big.output_tokens >= 5000 * KOREAN_PER_ENGLISH  # 출력은 번역할 영어 글의 몇 배로 어림


def many(n: int) -> list:
    return pieces([chunk(f"c{i}", anchor=f"a{i}") for i in range(n)])


def test_시험용_청크는_같은_씨앗이면_같고_원래_차례로_돌려준다():
    first, again, other = sample(many(30), 5, seed=1), sample(many(30), 5, seed=1), sample(many(30), 5, seed=2)
    assert first == again and first != other and len(first) == 5
    keys = [piece.key for piece in many(30)]
    assert [piece.key for piece in first] == sorted((p.key for p in first), key=keys.index)


def test_시험용_청크에는_꼭_볼_이름이_든_청크를_넣는다():
    chosen = many(30)[:-1] + pieces([chunk("Use it.", ui_names=("Smart UV Project",), anchor="uv")])
    for seed in range(5):
        assert "modeling/bevel.html#uv/1" in [p.key for p in sample(chosen, 3, seed=seed, must=("Smart UV Project",))]
