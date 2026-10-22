"""답 엔진(시험 경계 ①: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

가짜 임베딩·가짜 답변 모델을 끼우고, 직접 지어낸 작은 청크 묶음(설명서 원문 아님)으로 시험한다.
질문을 넣고 나온 답 조각·근거 목록·검색 결과·오류 표시와, 모델이 받은 것만 본다.
"""

from dataclasses import replace

import pytest

from blender_tutor.answer_engine import AnswerEngine, Done, Failure, Piece, Settings, Source
from blender_tutor.manual_chunks import Chunk, Example, MediaKind
from blender_tutor.menu_names import MenuName, MenuNames, Translation
from blender_tutor.menu_names import Source as MenuSource
from blender_tutor.progress import Course, Step
from blender_tutor.work_state import ActiveObject, WorkState

# 지어낸 청크 6개. 벡터는 세 칸(베벨, 배열, 내보내기)이고 테스트가 가짜 임베딩으로 질문 벡터를 정한다.
BEVEL = Chunk(
    "modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate",
    "Bevel Modifier", ("Options",), "Width sets the size of the chamfer.",
    images=("https://docs.blender.org/manual/en/5.2/_images/bevel.png",),
)
BEVEL_MORE = Chunk(  # BEVEL과 같은 소제목을 나눈 뒤 조각(같은 앵커)
    "modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate",
    "Bevel Modifier", ("Options",), "Segments adds more chamfer cuts.",
)
ARRAY = Chunk(
    "modeling/modifiers/generate/array", "introduction", "modeling", "modeling/modifiers/generate",
    "Array Modifier", ("Introduction",), "Array copies the object in a row.",
    examples=(Example(MediaKind.VIDEO, "Example", "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html#example", ("https://example.org/array.mp4",)),),
)
EXPORT = Chunk(
    "addons/import_export/scene_gltf2", "export", "addons", "addons/import_export",
    "glTF 2.0", ("Export",), "Export writes the scene to a file.",
    videos=("https://example.org/gltf.mp4",),
)
SELECT = Chunk(  # 글 속 그림은 없고 뒤따르는 그림 예시만 있다
    "modeling/meshes/selecting/introduction", "select-mode", "modeling", "modeling/meshes/selecting",
    "Introduction", ("Select Mode",), "Vertex, edge and face select modes.",
    examples=(Example(MediaKind.IMAGE, "Modes", "https://docs.blender.org/manual/en/5.2/modeling/meshes/selecting/introduction.html#modes", ("https://example.org/modes.png",)),),
)
SAVE = Chunk(
    "files/blend/save", "save", "files", "files/blend",
    "Saving", ("Save",), "Save writes the blend file.",
)
CHUNKS = [BEVEL, BEVEL_MORE, ARRAY, EXPORT, SELECT, SAVE]
VECTORS = [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 1.0, 0.0], [0.0, 0.1, 1.0], [0.0, 0.0, 0.1], [0.05, 0.0, 0.02]]
# 질문 벡터: 세 칸 가운데 한쪽으로 기운 것
TOWARD_BEVEL, TOWARD_ARRAY, EVERYWHERE = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 1.0]

STATE = WorkState(
    "OBJECT", ActiveObject("Cube", "MESH", (), (1.0, 1.0, 1.0), (2.0, 2.0, 2.0), 0), ("Cube",),
    "en_US", False, "", 3, "5.2.2", {}, (),
)
TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."


class FakeEmbedder:
    """받은 글마다 정해 둔 벡터를 돌려준다(by_text에 있으면 그것, 없으면 vector). 부를 때마다 받은 글 목록과 시간 한도를 적어 둔다."""

    def __init__(self, vector=TOWARD_BEVEL, error: Exception | None = None, by_text: dict | None = None):
        self.vector = vector
        self.error = error
        self.by_text = by_text or {}
        self.calls: list[list[str]] = []
        self.timeouts: list[float] = []

    def embed(self, texts: list[str], timeout: float) -> list[list[float]]:
        self.calls.append(list(texts))
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return [self.by_text.get(text, self.vector) for text in texts]


class FakeModel:
    """정해 둔 조각을 차례로 돌려준다. error가 있으면 조각을 다 낸 뒤 그 오류를 낸다."""

    def __init__(self, pieces=("베벨 ", "모디파이어의 ", "Width를 바꾸세요."), error: Exception | None = None):
        self.pieces = pieces
        self.error = error
        self.calls: list[list[dict[str, str]]] = []
        self.timeouts: list[float] = []

    def stream(self, messages: list[dict[str, str]], timeout: float):
        self.calls.append(messages)
        self.timeouts.append(timeout)
        yield from self.pieces
        if self.error:
            raise self.error


def ask(question="베벨", *, embedder=None, model=None, settings=Settings(), recent=(), state=STATE, step=None) -> list:
    """답 엔진을 새로 만들어 질문 하나를 묻고, 나온 것을 모두 모은다. step이 없으면 연습 과정을 진행하지 않는 때."""
    engine = AnswerEngine(CHUNKS, VECTORS, embedder or FakeEmbedder(), model or FakeModel(), settings)
    return list(engine.answer(question, state, list(recent), step))


def found(events) -> list[Chunk]:
    """마지막 Done의 검색 결과(순위대로)."""
    return list(events[-1].results)


def sources_by_url(events) -> dict[str, Source]:
    return {source.url: source for source in events[-1].sources}


# 답의 흐름


def test_답_조각이_나오는_대로_흐르고_끝에_근거가_붙는다():
    events = ask()
    assert events[:3] == [Piece("베벨 "), Piece("모디파이어의 "), Piece("Width를 바꾸세요.")]
    assert isinstance(events[3], Done) and len(events) == 4


def test_같은_질문을_두_번_하면_같은_답과_근거가_나온다():
    model = FakeModel()
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), model)
    first = list(engine.answer("베벨", STATE, []))
    second = list(engine.answer("베벨", STATE, []))
    assert first == second and model.calls[0] == model.calls[1]


# 근거 목록


def test_근거에_소제목_경로_주소_그림_영상_표시가_있다():
    sources = sources_by_url(ask("배열 내보내기 베벨", embedder=FakeEmbedder(EVERYWHERE)))
    assert sources["https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options"] == Source(
        "Bevel Modifier > Options",
        "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options",
        has_image=True, has_video=False, videos=(),
    )
    export = sources["https://docs.blender.org/manual/en/5.2/addons/import_export/scene_gltf2.html#export"]
    assert (export.path, export.has_image, export.has_video, export.videos) == (
        "glTF 2.0 > Export", False, True, ("https://example.org/gltf.mp4",),
    )


def test_뒤따르는_영상_예시는_영상_있음과_그_링크로_센다():
    array = sources_by_url(ask("배열", embedder=FakeEmbedder(TOWARD_ARRAY)))[
        "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html#introduction"
    ]
    assert (array.has_image, array.has_video, array.videos) == (False, True, ("https://example.org/array.mp4",))


def test_뒤따르는_그림_예시는_그림_있음으로_센다():
    select = sources_by_url(ask("점 선 면", embedder=FakeEmbedder(EVERYWHERE)))[
        "https://docs.blender.org/manual/en/5.2/modeling/meshes/selecting/introduction.html#select-mode"
    ]
    assert (select.has_image, select.has_video) == (True, False)


def test_그림_영상이_없는_소제목은_둘_다_없음():
    save = sources_by_url(ask("저장", embedder=FakeEmbedder(EVERYWHERE)))["https://docs.blender.org/manual/en/5.2/files/blend/save.html#save"]
    assert (save.path, save.has_image, save.has_video, save.videos) == ("Saving > Save", False, False, ())


def test_같은_소제목을_나눈_청크는_근거에_한_번만_나온다():
    events = ask()
    urls = [source.url for source in events[-1].sources]
    assert urls.count("https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options") == 1
    assert len(urls) == len(set(urls))
    assert found(events)[:2] == [BEVEL, BEVEL_MORE]  # 검색 결과(평가용)에는 두 조각이 다 있다


# 검색


def test_검색_결과는_설정한_개수만큼():
    assert len(found(ask(settings=Settings(top_k=3)))) == 3
    assert len(found(ask())) == 6  # 기본 6개
    assert len(found(ask(settings=Settings(top_k=10)))) == 6  # 청크가 그보다 적으면 있는 만큼


def test_겹치는_낱말이_없으면_뜻_검색_순서_그대로():
    # 한국어 질문은 영어 청크와 겹치는 낱말이 없다. 낱말 점수 0인 청크가 아무 순서로 끼어들면 안 된다
    events = ask("배열 복사", embedder=FakeEmbedder(TOWARD_ARRAY), settings=Settings(top_k=3))
    assert found(events) == [ARRAY, BEVEL_MORE, EXPORT]


def test_뜻과_낱말이_모두_가까운_청크가_한쪽만_가까운_청크보다_위로_온다():
    # 뜻으로는 BEVEL이 1등이고 SAVE는 3등, 낱말("save file")로는 SAVE가 1등이다.
    # SAVE는 두 순위표에 다 높이 있어 뜻 한쪽에서만 1등인 BEVEL보다 위로 온다
    assert found(ask("save file", settings=Settings(top_k=2)))[0] == SAVE


def test_한국어_질문에_섞인_영어_낱말이_순위를_올린다():
    # 뜻으로는 BEVEL이 1등이지만, 질문 속 "Segments"는 BEVEL_MORE에만 있다
    assert found(ask("Segments 늘리기", settings=Settings(top_k=2)))[0] == BEVEL_MORE
    assert found(ask("Segments 늘리기", settings=Settings(top_k=2, use_bm25=False)))[0] == BEVEL


def test_낱말_검색을_끄면_뜻_검색_순서만_쓴다():
    assert found(ask("save file", settings=Settings(top_k=2, use_bm25=False))) == [BEVEL, BEVEL_MORE]


# 검색어 만들기


def test_검색어에_직전_질문_단계_이름_먼저_볼_소제목_경로_방금_조작이_붙는다():
    # "그다음은요?"만으로는 무엇을 찾을지 모른다. 임베딩 호출을 늘리지 않고 아는 것을 검색어에 붙인다
    embedder = FakeEmbedder()
    step = Step("bevel-edges", "모서리 둥글게 깎기", manual=("modeling/modifiers/generate/bevel.html#options",))
    state = replace(STATE, recent_operators=("object.modifier_add", "object.select_all"))
    ask("그다음은요?", embedder=embedder, recent=[("베벨은 어디 있어요?", "Modifiers 탭에서 더해요.")], state=state, step=step)
    assert embedder.calls == [
        ["그다음은요?\n베벨은 어디 있어요?\n모서리 둥글게 깎기\nBevel Modifier > Options\nobject.modifier_add object.select_all"]
    ]


def test_붙일_것이_없으면_검색어는_질문_그대로():
    embedder = FakeEmbedder()
    ask("베벨", embedder=embedder)
    assert embedder.calls == [["베벨"]]


def _name(english: str, korean: str, source: MenuSource = MenuSource.UI) -> MenuName:
    return MenuName(english, (Translation(korean, ("*",)),), 1, "", (source,))


# 지어낸 작은 메뉴 이름 사전. 실제 사전에도 한 글자 이름(면·심·폭 등)과 제목에서만 뽑은 이름(에서 → At)이 있다
MENU_NAMES = MenuNames([
    _name("Edit Mode", "편집 모드"), _name("Merge", "병합"), _name("Center", "중심"), _name("Seam", "심"),
    _name("Facing", "면"), _name("Width", "폭"), _name("Bevel", "베벨"), _name("Join", "합치기"),
    _name("Size", "크기"), _name("Dimensions", "크기"), _name("At", "에서", MenuSource.TITLE),
])  # fmt: skip


@pytest.mark.parametrize(
    "question, english",
    [
        # 낱말 안의 더 짧은 이름(중심의 심)은 보지 않고, 한 글자 이름은 낱말 시작에서만(하려면의 면은 아님)
        ("편집 모드에서 꼭짓점을 중심에 병합하려면", "Edit Mode Center Merge"),
        ("편집모드에서꼭짓점을병합하려면", "Edit Mode Merge"),  # 붙여 써도 찾는다
        ("면을 고르려면", "Facing"),  # 낱말 시작의 한 글자 이름
        ("베벨폭을 줄이려면", "Bevel Width"),  # 앞 이름 바로 뒤의 한 글자 이름
        ("물체를 합치려면", "Join"),  # '기'로 끝나는 이름은 동사 꼴(합치려면)로도
        ("크기를 줄이려면", "Size Dimensions"),  # 한국어 하나에 영어가 여럿이면 모두
        ("꼭짓점을 고르려면", ""),  # 없으면 붙이지 않는다
    ],
)
def test_질문_속_한국어_메뉴_이름에_영어를_덧붙인다(question, english):
    embedder = FakeEmbedder()
    engine = AnswerEngine(CHUNKS, VECTORS, embedder, FakeModel(), menu_names=MENU_NAMES)
    list(engine.answer(question, STATE, []))
    assert embedder.calls == [[f"{question} {english}".strip()]]


def test_제목에서만_뽑은_이름은_아직_쓰지_않는다():
    # 검수 전(제목에서만 뽑은 1,055개)이라 흔한 낱말(에서 → At)이 섞인다. 검수는 초보자 범위 분류(티켓 30) 뒤
    embedder = FakeEmbedder()
    list(AnswerEngine(CHUNKS, VECTORS, embedder, FakeModel(), menu_names=MENU_NAMES).answer("여기에서", STATE, []))
    assert embedder.calls == [["여기에서"]]


def test_붙인_검색어로_낱말_검색도_한다():
    # 질문은 한국어뿐이지만 단계에 걸린 소제목 경로("Saving > Save")의 낱말이 SAVE를 끌어올린다
    step = Step("save-file", "파일 저장하기", manual=("files/blend/save.html#save",))
    assert found(ask("어떻게 해요?", step=step, settings=Settings(top_k=2)))[0] == SAVE


# 모델에 넘기는 것


def test_먼저_볼_소제목을_검색_상위_위에_덧붙이고_검색_결과는_줄이지_않는다():
    model = FakeModel()
    step = Step("export", "내보내기", manual=("files/blend/save.html#save", "addons/import_export/scene_gltf2.html#export"))
    # 낱말 검색을 끈다: 켜면 검색어에 붙은 소제목 경로로 검색 순위도 바뀐다(위 테스트). 여기서는 덧붙이기만 본다
    events = ask(model=model, settings=Settings(top_k=2, use_bm25=False), step=step)
    sent = model.calls[0][-1]["content"]
    order = [sent.index(chunk.text) for chunk in (SAVE, EXPORT, BEVEL, BEVEL_MORE)]
    assert order == sorted(order)  # 먼저 볼 소제목(단계 파일 차례)이 위, 그 아래 검색 상위 2개
    assert found(events) == [BEVEL, BEVEL_MORE]  # 검색 결과(평가용)는 검색 순위 그대로
    assert [source.path for source in events[-1].sources] == [
        "Saving > Save", "glTF 2.0 > Export", "Bevel Modifier > Options",
    ]


def test_먼저_볼_소제목이_검색에도_걸리면_한_번만_넘긴다():
    model = FakeModel()
    step = Step("bevel", "베벨", manual=("modeling/modifiers/generate/bevel.html#options",))
    events = ask(model=model, settings=Settings(top_k=3, use_bm25=False), step=step)
    sent = model.calls[0][-1]["content"]
    assert sent.count(BEVEL.text) == 1 and sent.count(BEVEL_MORE.text) == 1
    assert found(events)[:2] == [BEVEL, BEVEL_MORE]
    assert sent.index(BEVEL_MORE.text) < sent.index(found(events)[2].text)  # 나눈 조각도 함께 위로


def _tool(anchor: str, headings: tuple[str, ...], words: int) -> Chunk:
    """지어낸 '메시 도구' 쪽의 소제목 하나. 본문은 낱말 words개."""
    body = " ".join([anchor] * words)
    return Chunk("modeling/meshes/tools", anchor, "modeling", "modeling/meshes", "Mesh Tools", headings, body)


# 같은 쪽에 Tools 아래 형제 소제목 넷과, 다른 부모(Overview)의 소제목 하나. 저장 차례가 곧 설명서 차례다
OVERVIEW = _tool("overview", ("Overview",), 30)
KNIFE = _tool("knife", ("Tools", "Knife"), 10)
BISECT = _tool("bisect", ("Tools", "Bisect"), 100)
LOOP = _tool("loop", ("Tools", "Loop"), 200)
LOOP_EDGE = _tool("loop-edge", ("Tools", "Loop", "Edge"), 5)  # LOOP의 자식(Tools의 손자)
FILL = _tool("fill", ("Tools", "Fill"), 150)
TOOLS_INTRO = _tool("tools", ("Tools",), 20)  # 아래에 소제목이 있는 짧은 소개
TOOLS = [OVERVIEW, TOOLS_INTRO, KNIFE, BISECT, LOOP, LOOP_EDGE, FILL]
TOOL_VECTORS = [[0.0, 1.0], [1.0, -1.0], [1.0, 0.0], [0.5, 0.5], [0.4, 0.6], [0.2, 0.8], [0.3, 0.7]]


def ask_tools(vector, step=None) -> tuple[list, FakeModel]:
    model = FakeModel()
    engine = AnswerEngine(TOOLS, TOOL_VECTORS, FakeEmbedder(vector), model, Settings(top_k=1, use_bm25=False))
    return list(engine.answer("칼", STATE, [], step)), model


def test_50단어_미만_청크는_형제_소제목을_약_400단어까지_함께_넘기고_링크는_찾은_소제목():
    events, model = ask_tools([1.0, 0.0])  # KNIFE(10단어)만 찾는다
    sent = model.calls[0][-1]["content"]
    # 가까운 형제부터: BISECT(+100) → LOOP(+200) = 310단어. FILL(+150)을 더하면 460이라 넣지 않는다
    assert KNIFE.text in sent and BISECT.text in sent and LOOP.text in sent
    assert FILL.text not in sent and OVERVIEW.text not in sent  # 부모가 다른 소제목은 형제가 아니다
    assert LOOP_EDGE.text not in sent and TOOLS_INTRO.text not in sent  # 형제의 자식·부모도 형제가 아니다
    assert sent.index(KNIFE.text) < sent.index(BISECT.text) < sent.index(LOOP.text)  # 설명서 차례대로
    assert found(events) == [KNIFE]
    assert [source.url for source in events[-1].sources] == [KNIFE.url]


def test_50단어_넘는_청크는_형제를_붙이지_않는다():
    events, model = ask_tools([0.5, 0.5])  # BISECT(100단어)만 찾는다
    sent = model.calls[0][-1]["content"]
    assert BISECT.text in sent and all(chunk.text not in sent for chunk in (OVERVIEW, KNIFE, LOOP, FILL))


def test_50단어_미만이고_아래_소제목이_있으면_형제_대신_자식을_약_400단어까지_넘긴다():
    # 짧은 소개 소제목의 진짜 내용은 아래 소제목에 있다(예: VR Scene Inspection > Location Scouting)
    events, model = ask_tools([1.0, -1.0])  # TOOLS_INTRO(20단어)만 찾는다
    sent = model.calls[0][-1]["content"]
    # 설명서 차례대로 손자까지: KNIFE(+10) → BISECT(+100) → LOOP(+200) → LOOP_EDGE(+5) = 335단어. FILL(+150)은 485라 넣지 않는다
    children = [KNIFE, BISECT, LOOP, LOOP_EDGE]
    assert [sent.index(chunk.text) for chunk in [TOOLS_INTRO, *children]] == sorted(
        sent.index(chunk.text) for chunk in [TOOLS_INTRO, *children]
    )
    assert FILL.text not in sent and OVERVIEW.text not in sent  # 형제(OVERVIEW)는 붙이지 않는다
    assert [source.url for source in events[-1].sources] == [TOOLS_INTRO.url]


def test_먼저_볼_소제목은_짧아도_형제를_붙이지_않는다():
    # 먼저 볼 소제목은 미리 골라 둔 것이라, 짧은 검색 결과를 보완하는 형제 붙이기 대상이 아니다
    step = Step("knife", "칼로 자르기", manual=(KNIFE.address,))
    _, model = ask_tools([0.0, 1.0], step)  # 검색은 OVERVIEW, 먼저 볼 소제목은 KNIFE(10단어)
    sent = model.calls[0][-1]["content"]
    assert KNIFE.text in sent and all(chunk.text not in sent for chunk in (BISECT, LOOP, FILL))


# 지어낸 연습 과정 넷과 그 벡터(실제로는 이름 + 한 줄 설명 + 비슷한 말을 미리 임베딩한 것, 티켓 31)
SWORD = Course("sword", "단순한 검", (), "정육면체를 늘려 칼날을 만든다.")
SHIELD = Course("shield", "둥근 방패", (), "원판에 테두리를 두른다.")
POTION = Course("potion", "물약 병", (), "구에서 병 모양을 뽑는다.")
CHEST = Course("chest", "보물 상자", (), "상자에 뚜껑을 단다.")
COURSES = [SWORD, SHIELD, POTION, CHEST]
COURSE_VECTORS = [[1.0, 0.0, 0.0], [0.6, 0.4, 0.0], [0.0, 0.0, 1.0], [0.3, 0.7, 0.0]]


def ask_with_courses(step=None, embedder=None, recent=()) -> str:
    model = FakeModel()
    engine = AnswerEngine(
        CHUNKS, VECTORS, embedder or FakeEmbedder(TOWARD_BEVEL), model, courses=COURSES, course_vectors=COURSE_VECTORS
    )
    list(engine.answer("칼을 만들고 싶어요", STATE, list(recent), step))
    return model.calls[0][-1]["content"]


def test_비슷한_연습_과정은_덧붙인_검색어가_아니라_질문만으로_고르고_임베딩은_한_번에_부른다():
    # 직전 질문(내보내기)이 붙은 검색어로 고르면 물약 병 쪽으로 끌린다. 질문만의 벡터를 같은 호출에서 함께 받는다
    question, query = "칼을 만들고 싶어요", "칼을 만들고 싶어요\nglb로 내보내려면?"
    embedder = FakeEmbedder([0.0, 0.0, 1.0], by_text={question: [1.0, 0.0, 0.0]})
    sent = ask_with_courses(embedder=embedder, recent=[("glb로 내보내려면?", "File > Export에서 골라요.")])
    assert embedder.calls == [[query, question]]  # 검색어 먼저, 질문만은 둘째. 호출은 한 번
    assert sent.index("- 단순한 검") < sent.index("- 둥근 방패") and "물약 병" not in sent


def test_덧붙인_것이_없어_검색어가_질문과_같으면_글을_하나만_보낸다():
    embedder = FakeEmbedder(TOWARD_BEVEL)
    ask_with_courses(embedder=embedder)
    assert embedder.calls == [["칼을 만들고 싶어요"]]


def test_임베딩이_글_수와_다른_개수의_벡터를_주면_잘못된_응답으로_보고_오류_표시():
    class OneShort(FakeEmbedder):
        def embed(self, texts, timeout):
            return super().embed(texts, timeout)[:-1]

    model = FakeModel()
    assert ask(embedder=OneShort(), model=model) == [Failure(ERROR_MESSAGE)]
    assert model.calls == []


def test_연습_과정을_진행_중이면_질문만의_벡터를_받지_않는다():
    embedder = FakeEmbedder(TOWARD_BEVEL)
    ask_with_courses(Step("blade-tip", "칼끝 모으기"), embedder=embedder)
    assert embedder.calls == [["칼을 만들고 싶어요\n칼끝 모으기"]]


def test_연습_과정을_진행하지_않을_때만_비슷한_연습_과정_3개를_가까운_차례로_붙인다():
    sent = ask_with_courses()
    lines = ["- 단순한 검: 정육면체를 늘려 칼날을 만든다.", "- 둥근 방패: 원판에 테두리를 두른다.", "- 보물 상자: 상자에 뚜껑을 단다."]
    assert "# 비슷한 연습 과정" in sent and [sent.index(line) for line in lines] == sorted(sent.index(line) for line in lines)
    assert "물약 병" not in sent  # 넷째는 넣지 않는다
    assert "가장 가까운 건" in sent  # 딱 맞는 게 없을 때 말할 꼴


def test_연습_과정과_벡터_수가_다르면_만들_때_멈춘다():
    with pytest.raises(ValueError):
        AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(), courses=COURSES, course_vectors=COURSE_VECTORS[:3])


def test_연습_과정을_진행_중이면_비슷한_연습_과정을_붙이지_않는다():
    sent = ask_with_courses(Step("blade-tip", "칼끝 모으기"))
    assert "# 비슷한 연습 과정" not in sent and "단순한 검" not in sent


def test_지금_단계_내용을_모델에_넘긴다():
    model = FakeModel()
    step = Step("blade-tip", "칼끝 모으기", guide="이름: 칼끝 모으기\n쉬운 설명: 맨 위 꼭짓점을 한 점으로 모은다.")
    ask(model=model, step=step)
    assert "# 지금 단계\n\n이름: 칼끝 모으기\n쉬운 설명: 맨 위 꼭짓점을 한 점으로 모은다." in model.calls[0][-1]["content"]


def test_연습_과정을_진행하지_않으면_단계_내용이_없다():
    model = FakeModel()
    ask(model=model)
    assert "# 지금 단계" not in model.calls[0][-1]["content"]


def test_질문_하나에_임베딩_한_번_답변_한_번만_부른다():
    embedder, model = FakeEmbedder(), FakeModel()
    ask(embedder=embedder, model=model, recent=[("배열은요?", "배열 모디파이어를 쓰세요.")])
    assert (len(embedder.calls), len(model.calls)) == (1, 1)


def test_모델에_검색_청크_글과_작업_상태와_질문을_넘긴다():
    model = FakeModel()
    question = "칼날 모서리를 둥글게 하려면?"  # 청크·작업 상태 어디에도 없는 글이라, 들어 있으면 질문에서 온 것이다
    ask(question, model=model, settings=Settings(top_k=2))
    messages = model.calls[0]
    assert messages[0]["role"] == "system"
    sent = messages[-1]["content"]
    assert BEVEL.text in sent and BEVEL_MORE.text in sent  # 검색 상위 2개는 넘기고
    assert all(chunk.text not in sent for chunk in (ARRAY, EXPORT, SELECT, SAVE))  # 나머지는 넘기지 않는다
    assert '"mode": "OBJECT"' in sent and '"name": "Cube"' in sent
    assert question in sent


def test_최근_대화를_차례대로_넘기고_지난_질문은_기억하지_않는다():
    model = FakeModel()
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(TOWARD_ARRAY), model)
    recent = [("배열은요?", "배열 모디파이어를 쓰세요."), ("몇 개까지요?", "Count 칸에 개수를 넣어요.")]
    list(engine.answer("배열은요?", STATE, []))
    list(engine.answer("그거 어떻게 해요?", STATE, recent))
    list(engine.answer("그거 어떻게 해요?", STATE, []))  # 최근 대화를 안 주면 앞 질문을 모른다
    assert [m["role"] for m in model.calls[1]] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert model.calls[1][1:5] == [
        {"role": "user", "content": "배열은요?"},
        {"role": "assistant", "content": "배열 모디파이어를 쓰세요."},
        {"role": "user", "content": "몇 개까지요?"},
        {"role": "assistant", "content": "Count 칸에 개수를 넣어요."},
    ]
    assert [m["role"] for m in model.calls[2]] == ["system", "user"]
    assert "배열은요?" not in str(model.calls[2]) and "몇 개까지요?" not in str(model.calls[2])


def test_응답_없음_한도를_모델과_임베딩에_넘긴다():
    embedder, model = FakeEmbedder(), FakeModel()
    ask(embedder=embedder, model=model)
    assert (embedder.timeouts, model.timeouts) == ([10.0], [10.0])  # 기본 10초(사용자 결정, 2026-10-21)
    ask(embedder=embedder, model=model, settings=Settings(timeout=3.0))
    assert (embedder.timeouts[-1], model.timeouts[-1]) == (3.0, 3.0)


# 오류·시간 초과

SEARCHED = tuple(found(ask()))  # 기본 질문("베벨")의 검색 결과. 검색 뒤에 실패하면 오류 표시에 함께 실린다


def test_답변_모델이_시간_초과면_짧은_오류_표시():
    assert ask(model=FakeModel(pieces=(), error=TimeoutError())) == [Failure(TIMEOUT_MESSAGE, SEARCHED)]


def test_답변_모델이_첫_조각_전에_실패하면_오류_표시():
    assert ask(model=FakeModel(pieces=(), error=ConnectionError("끊김"))) == [Failure(ERROR_MESSAGE, SEARCHED)]


def test_답_도중_오류가_나면_나온_조각_뒤에_오류_표시와_검색_결과가_오고_근거는_없다():
    events = ask(model=FakeModel(pieces=("베벨 ",), error=ConnectionError("끊김")))
    assert events == [Piece("베벨 "), Failure(ERROR_MESSAGE, SEARCHED)]
    assert len(SEARCHED) == 6  # 검색 결과는 평가용으로 그대로 남는다


def test_답_도중_시간_초과도_나온_조각_뒤에_오류_표시():
    events = ask(model=FakeModel(pieces=("베벨 ", "모디파이어의 "), error=TimeoutError()))
    assert events == [Piece("베벨 "), Piece("모디파이어의 "), Failure(TIMEOUT_MESSAGE, SEARCHED)]


def test_임베딩이_시간_초과면_검색_전이라_검색_결과_없이_오류_표시를_내고_답변_모델은_부르지_않는다():
    model = FakeModel()
    assert ask(embedder=FakeEmbedder(error=TimeoutError()), model=model) == [Failure(TIMEOUT_MESSAGE)]
    assert model.calls == []


def test_임베딩이_실패하면_오류_표시를_내고_답변_모델은_부르지_않는다():
    model = FakeModel()
    assert ask(embedder=FakeEmbedder(error=ConnectionError("끊김")), model=model) == [Failure(ERROR_MESSAGE)]
    assert model.calls == []


def test_우리_코드의_오류는_오류_표시로_덮지_않고_그대로_올린다():
    # 임베딩이 청크 벡터(3칸)와 길이가 다른 벡터를 주면 검색에서 실패한다. 서버 문제가 아니라 설정 버그다
    model = FakeModel()
    with pytest.raises(ValueError):
        ask(embedder=FakeEmbedder([1.0, 0.0]), model=model)
    assert model.calls == []


def test_임베딩이_모두_0인_벡터를_주면_잘못된_응답으로_보고_오류_표시():
    # 모두 0이면 뜻 점수가 다 같아 청크 저장 순서가 그대로 순위가 된다(의미 없는 검색 결과)
    model = FakeModel()
    assert ask(embedder=FakeEmbedder([0.0, 0.0, 0.0]), model=model) == [Failure(ERROR_MESSAGE)]
    assert model.calls == []


# 메뉴 이름 표기(티켓 23). 답변 모델은 메뉴 이름을 [[영어]]로 표시해 쓰고, 엔진이 화면 언어에 맞게 바꾼다

KOREAN_SCREEN = replace(STATE, language="ko_KR", translate_interface=True)


def _many(english: str, *candidates: tuple[str, str]) -> MenuName:
    """번역이 여러 개인 이름. candidates는 (한국어, 문맥) 쌍. 한국어가 영어와 같으면 그 문맥은 번역 없음"""
    return MenuName(english, tuple(Translation(korean, (context,)) for korean, context in candidates), 1, "", (MenuSource.UI,))


# 지어낸 표기 사전. Array는 실제 사전처럼 쪽 제목에서만 뽑은 이름
SCREEN_NAMES = [
    _name("Add", "추가"), _name("Mesh", "메시"), _name("Array", "배열", MenuSource.TITLE),
    _many("Edit Mode", ("에디트 모드", "*"), ("편집 모드", "Operator")),
    _many("At Center", ("센터에서", "Operator"), ("At Center", "Mesh")),
    _many("Apply", ("적용", "*"), ("신청하기", "WindowManager")),
]  # fmt: skip


def shown(pieces, state=KOREAN_SCREEN, choices=None) -> str:
    """가짜 모델이 pieces를 낼 때 사용자가 보는 답 글(조각을 이어 붙인 것)."""
    names = MenuNames(SCREEN_NAMES, choices or {})
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    return "".join(event.text for event in engine.answer("메시 추가", state, []) if isinstance(event, Piece))


def test_한국어_화면에_번역이_켜져_있으면_메뉴_이름을_한국어_괄호_영어로():
    assert shown(("[[Add > Mesh]]를 누르세요.",)) == "추가(Add) > 메시(Mesh)를 누르세요."


@pytest.mark.parametrize(
    "state",
    [
        replace(STATE, language="en_US", translate_interface=True),  # 영어 화면
        replace(STATE, language="ko_KR", translate_interface=False),  # 한국어로 골랐지만 인터페이스 번역 꺼짐
        replace(STATE, language="", translate_interface=True),  # 화면 언어를 모름
    ],
)
def test_영어_화면이거나_번역이_꺼져_있으면_메뉴_이름은_영어만(state):
    assert shown(("[[Add > Mesh]]를 누르세요.",), state) == "Add > Mesh를 누르세요."


@pytest.mark.parametrize(
    "pieces, choices, expected",
    [
        (("[[Snap Base]]를 켜세요.",), {}, "Snap Base를 켜세요."),  # 사전에 없음
        (("[[Array]] 모디파이어",), {}, "배열(Array) 모디파이어"),  # 쪽 제목에서만 뽑은 이름도 하나면 그대로
        (("[[Edit Mode]]로",), {}, "Edit Mode로"),  # 여러 개인데 아직 고정 전: 틀린 한국어를 보이지 않는다
        (("[[Edit Mode]]로",), {"Edit Mode": "Operator"}, "편집 모드(Edit Mode)로"),  # 고정한 짝
        # 병합 메뉴의 At Center는 Mesh 문맥이라 번역이 없다. 그 문맥을 고르면 화면처럼 영어 그대로
        (("[[Mesh > Merge > At Center]]",), {"At Center": "Mesh"}, "메시(Mesh) > Merge > At Center"),
    ],
)
def test_번역이_없거나_고정_전이면_영어_그대로이고_여러_번역은_고정한_짝을_쓴다(pieces, choices, expected):
    assert shown(pieces, choices=choices) == expected


def test_표시가_조각_사이에_갈려_와도_바꾼다():
    assert shown(("먼저 [", "[Ad", "d > Me", "sh]", "]를 누르세요.",)) == "먼저 추가(Add) > 메시(Mesh)를 누르세요."


def test_표시가_아닌_대괄호는_글_그대로이고_닫히지_않은_표시는_기호만_뗀다():
    assert shown(("배열 [1, 2]처럼 [", "숫자를 넣어요.",)) == "배열 [1, 2]처럼 [숫자를 넣어요."
    assert shown(("[[Add 끝",)) == "Add 끝"  # 답이 끝날 때까지 닫히지 않으면 표시 기호만 뗀다
    assert shown(("[[[Add]] 메뉴",)) == "[추가(Add) 메뉴"  # 대괄호가 하나 더 붙어도 표시는 찾는다
    long = "[[" + "가" * 100 + " 그리고 [[Mesh]]"  # 닫히지 않은 표시에 뒤 글이 붙들리지 않는다
    assert shown((long,)) == "가" * 100 + " 그리고 메시(Mesh)"


def test_표시가_닫히기_전에_답이_끊겨도_받은_글을_내고_오류_표시():
    names = MenuNames(SCREEN_NAMES)
    model = FakeModel(("[[Add >",), error=ConnectionError("끊김"))
    events = list(AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), model, menu_names=names).answer("추가", KOREAN_SCREEN, []))
    assert events[0] == Piece("Add >") and isinstance(events[1], Failure)


def test_답변_모델에게_메뉴_이름을_영어로_표시해_쓰라고_지시한다():
    model = FakeModel()
    ask(model=model)
    assert "[[Add > Mesh]]" in model.calls[0][0]["content"]
