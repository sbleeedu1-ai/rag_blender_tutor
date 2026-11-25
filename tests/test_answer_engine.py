"""답 엔진(시험 경계 ①: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

가짜 임베딩·가짜 답변 모델을 끼우고, 직접 지어낸 작은 청크 묶음(설명서 원문 아님)으로 시험한다.
질문을 넣고 나온 답 조각·근거 목록·검색 결과·오류 표시와, 모델이 받은 것만 본다.
"""

import json
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import httpx2
import pytest

from blender_tutor.answer_engine import (
    INSTRUCTIONS,
    AnswerEngine,
    Done,
    Failure,
    Piece,
    Reasoning,
    Settings,
    Source,
    Stage,
    _messages,
    _terms_for,
)
from blender_tutor.claude_model import ClaudeModel
from blender_tutor.manual_chunks import Chunk, Example, MediaKind
from blender_tutor.menu_names import MenuName, MenuNames, Translation
from blender_tutor.menu_names import Source as MenuSource
from blender_tutor.progress import Course, Step
from blender_tutor.work_state import ActiveObject, View, WorkState

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
    "en_US", False, "", 3, "5.2.2", {}, (), view=View(18.4, (0.71, 0.44, 0.29, 0.46), (0.0, 0.0, 0.0)),
)
TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."
ANSWERING = [Stage.SEARCH, Stage.ANSWER]  # 질문 바꾸기 없는 엔진이 답변 모델을 부르기까지 내는 단계(티켓 51)


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

    def stream(self, messages: list[dict[str, str]], timeout: float, first_timeout: float | None = None):
        self.calls.append(messages)
        self.timeouts.append((timeout, first_timeout))
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
    assert events[:5] == [*ANSWERING, Piece("베벨 "), Piece("모디파이어의 "), Piece("Width를 바꾸세요.")]
    assert isinstance(events[5], Done) and len(events) == 6


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
    assert found(ask("save file", settings=Settings(top_k=2, use_bm25=True)))[0] == SAVE


def test_한국어_질문에_섞인_영어_낱말이_순위를_올린다():
    # 뜻으로는 BEVEL이 1등이지만, 질문 속 "Segments"는 BEVEL_MORE에만 있다
    assert found(ask("Segments 늘리기", settings=Settings(top_k=2, use_bm25=True)))[0] == BEVEL_MORE
    assert found(ask("Segments 늘리기", settings=Settings(top_k=2, use_bm25=False)))[0] == BEVEL


def test_낱말_검색을_끄면_뜻_검색_순서만_쓴다():
    assert found(ask("save file", settings=Settings(top_k=2, use_bm25=False))) == [BEVEL, BEVEL_MORE]


# 리랭킹(위 200을 판정기 확률 순으로 다시 세움, HISTORY [626])

# TOWARD_BEVEL일 때 뜻 검색 순서: BEVEL, BEVEL_MORE, SAVE, ARRAY, EXPORT, SELECT(EXPORT·SELECT는 점수 0, 저장 차례)
BY_MEANING = [BEVEL, BEVEL_MORE, SAVE, ARRAY, EXPORT, SELECT]


class FakeReranker:
    """글마다 정해 둔 확률(없으면 default)을 돌려준다. 받은 검색어·글·시간 한도를 적어 둔다."""

    def __init__(self, probs: dict | None = None, default=0.5, error: Exception | None = None, short=False):
        self.probs, self.default, self.error, self.short = probs or {}, default, error, short
        self.calls: list[tuple[str, list[str], float]] = []

    def judge(self, query, passages, timeout):
        self.calls.append((query, list(passages), timeout))
        if self.error:
            raise self.error
        probs = [self.probs.get(text, self.default) for text in passages]
        return probs[:-1] if self.short else probs


def ask_reranked(reranker, settings=Settings(top_k=2)) -> list:
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(), settings, reranker=reranker)
    return list(engine.answer("베벨", STATE, []))


def test_리랭커가_가장_높게_본_청크는_뜻_순위가_맨_끝이어도_위로_올라온다():
    events = ask_reranked(FakeReranker({SELECT.text: 0.99, SAVE.text: 0.8}))
    assert found(events) == [SELECT, SAVE]
    assert events[-1].rerank_failed is False


def test_확률이_같으면_뜻_검색_순서를_지킨다():
    assert found(ask_reranked(FakeReranker(default=0.5), Settings(top_k=6))) == BY_MEANING


def test_리랭커에는_검색어와_뜻_검색_위_rerank_depth개의_글을_순서대로_한도와_함께_넘긴다():
    reranker = FakeReranker()
    ask_reranked(reranker, Settings(top_k=2, rerank_depth=4, rerank_timeout=3.0))
    assert reranker.calls == [("베벨", [chunk.text for chunk in BY_MEANING[:4]], 3.0)]


def test_위_rerank_depth_밖의_청크는_확률이_높아도_오르지_않는다():
    events = ask_reranked(FakeReranker({SELECT.text: 0.99}), Settings(top_k=1, rerank_depth=5))
    assert found(events) == [BEVEL]


@pytest.mark.parametrize("reranker", [FakeReranker(error=TimeoutError("늦음")), FakeReranker(short=True)])
def test_리랭커가_실패하면_뜻_검색_위_k개로_답하고_실패를_알린다(reranker, caplog):
    events = ask_reranked(reranker)
    assert isinstance(events[-1], Done) and "".join(e.text for e in events if isinstance(e, Piece))  # 답은 멈추지 않는다
    assert found(events) == [BEVEL, BEVEL_MORE]
    assert events[-1].rerank_failed is True
    assert "리랭킹 실패" in caplog.text


def test_리랭커가_우리_코드_오류를_내면_숨기지_않고_올린다():
    # 바깥 서비스 실패(연결·시간 초과·답 꼴)만 뜻 검색 길로 보낸다. 다른 오류는 버그라 "리랭킹 실패"로 숨기지 않는다
    with pytest.raises(KeyError):
        ask_reranked(FakeReranker(error=KeyError("c00")))


def test_리랭커를_끄면_부르지_않는다():
    reranker = FakeReranker({SELECT.text: 0.99})
    assert found(ask_reranked(reranker, Settings(top_k=2, rerank=False))) == [BEVEL, BEVEL_MORE]
    assert reranker.calls == []


def test_search는_리랭커를_부르지_않는다():
    # 실측 프로그램(speed_trial)이 쓰지 않은 검색어도 search로 채점한다. 거기서 유료 판정기를 부르면 안 된다
    reranker = FakeReranker({SELECT.text: 0.99})
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(), Settings(top_k=2), reranker=reranker)
    assert engine.search("bevel", TOWARD_BEVEL) == [BEVEL, BEVEL_MORE] and reranker.calls == []


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
def test_질문_속_한국어_메뉴_이름의_영어를_찾는다(question, english):
    # 도우미 검색어에는 더 붙이지 않지만([127]) 검색 비교(search_compare)의 덧붙이기 조건이 이 규칙을 쓴다
    assert " ".join(MENU_NAMES.english_in(question)) == english


def test_검색어에_메뉴_이름을_덧붙이지_않는다():
    # 메뉴 이름 덧붙이기는 효과가 없어 뺐다(HISTORY [115]·[127]). 메뉴 이름 사전은 답 글의 [[ ]]를 바꾸는 데만 쓴다
    embedder = FakeEmbedder()
    list(AnswerEngine(CHUNKS, VECTORS, embedder, FakeModel(), menu_names=MENU_NAMES).answer("베벨폭을 줄이려면", STATE, []))
    assert embedder.calls == [["베벨폭을 줄이려면"]]


def test_붙인_검색어로_낱말_검색도_한다():
    # 질문은 한국어뿐이지만 단계에 걸린 소제목 경로("Saving > Save")의 낱말이 SAVE를 끌어올린다
    step = Step("save-file", "파일 저장하기", manual=("files/blend/save.html#save",))
    assert found(ask("어떻게 해요?", step=step, settings=Settings(top_k=2, use_bm25=True)))[0] == SAVE


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
    assert ask(embedder=OneShort(), model=model) == [Stage.SEARCH, Failure(ERROR_MESSAGE)]
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


def test_답_끝_알림에_모델에_붙인_비슷한_연습_과정을_가까운_차례로_알린다():
    # 평가에서 단순한 질문에 엉뚱하게 권했는지 보려고(티켓 29). 연습 과정을 진행 중이면 붙이지 않아 비어 있다
    def done(step=None) -> Done:
        engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(TOWARD_BEVEL), FakeModel(), courses=COURSES, course_vectors=COURSE_VECTORS)
        return list(engine.answer("칼을 만들고 싶어요", STATE, [], step))[-1]

    assert done().similar == (SWORD, SHIELD, CHEST)
    assert done(Step("blade-tip", "칼끝 모으기")).similar == ()


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


def test_넘긴_청크에_나온_낱말의_용어표_줄만_지시에_붙인다():
    model = FakeModel()
    ask(model=model, settings=Settings(top_k=len(CHUNKS)))  # SELECT의 "Vertex, edge and face"가 함께 넘어간다
    system = model.calls[0][0]["content"]
    assert all(line in system for line in ("vertex → 버텍스", "edge → 에지", "face → 페이스"))
    assert "bone → 뼈대(Bone)" not in system  # 청크에 없는 낱말의 줄은 붙이지 않는다


def test_넘긴_글에_용어표_낱말이_없으면_용어표_안내도_붙이지_않는다():
    assert _terms_for("Export writes the scene to a file.") == ""
    assert "Blender 낱말은 아래 표기" not in INSTRUCTIONS  # 안내는 줄이 있을 때만 _terms_for가 붙인다


def test_용어표_낱말은_복수형과_꼴이_바뀐_말도_찾는다():
    found = _terms_for("Select vertices and faces, then unwrapping. Empties have properties.")
    assert all(line in found for line in ("vertex →", "face →", "unwrap →", "empty →", "properties →"))
    assert "pack / unpack" not in found  # unwrapping 안의 글자가 pack으로 잘못 잡히지 않는다


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
    assert '"view"' not in sent  # 시점 숫자는 화면 조작 감지에만 쓰고 모델에는 넘기지 않는다
    assert question in sent


@pytest.mark.parametrize(
    "path, name",
    [
        ("C:\\Users\\someone\\scenes\\boolean_wrong\\상자.blend", "상자.blend"),  # Windows에서 찍은 상태는 Mac에서도 같게
        ("/Users/someone/scenes/boolean_wrong/상자.blend", "상자.blend"),
        ("", ""),  # 저장 전
    ],
)
def test_열린_파일은_폴더_없이_파일_이름만_모델에_넘긴다(path, name):
    # 폴더 이름에는 사용자 계정 이름이 들 수 있고, 시험 장면은 폴더 이름이 원인을 말한다(HISTORY [321]·[322])
    model = FakeModel()
    ask(model=model, state=replace(STATE, file_path=path))
    sent = model.calls[0][-1]["content"]
    assert f'"file_path": {json.dumps(name, ensure_ascii=False)}' in sent
    assert "someone" not in sent and "boolean_wrong" not in sent


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
    # 임베딩 10초(2026-10-21), 답 모델은 글 뒤 5초·첫 글자까지 20초(사용자 결정 [561])
    assert (embedder.timeouts, model.timeouts) == ([10.0], [(5.0, 20.0)])
    ask(embedder=embedder, model=model, settings=Settings(timeout=3.0, answer_timeout=2.0, answer_first_timeout=7.0))
    assert (embedder.timeouts[-1], model.timeouts[-1]) == (3.0, (2.0, 7.0))


# 오류·시간 초과

SEARCHED = tuple(found(ask()))  # 기본 질문("베벨")의 검색 결과. 검색 뒤에 실패하면 오류 표시에 함께 실린다


def test_답변_모델이_시간_초과면_짧은_오류_표시():
    assert ask(model=FakeModel(pieces=(), error=TimeoutError())) == [*ANSWERING, Failure(TIMEOUT_MESSAGE, SEARCHED)]


def test_답변_모델이_첫_조각_전에_실패하면_오류_표시():
    assert ask(model=FakeModel(pieces=(), error=ConnectionError("끊김"))) == [*ANSWERING, Failure(ERROR_MESSAGE, SEARCHED)]


def test_답_도중_오류가_나면_나온_조각_뒤에_오류_표시와_검색_결과가_오고_근거는_없다():
    events = ask(model=FakeModel(pieces=("베벨 ",), error=ConnectionError("끊김")))
    assert events == [*ANSWERING, Piece("베벨 "), Failure(ERROR_MESSAGE, SEARCHED)]
    assert len(SEARCHED) == 6  # 검색 결과는 평가용으로 그대로 남는다


def test_답_도중_시간_초과도_나온_조각_뒤에_오류_표시():
    events = ask(model=FakeModel(pieces=("베벨 ", "모디파이어의 "), error=TimeoutError()))
    assert events == [*ANSWERING, Piece("베벨 "), Piece("모디파이어의 "), Failure(TIMEOUT_MESSAGE, SEARCHED)]


def test_임베딩이_시간_초과면_검색_전이라_검색_결과_없이_오류_표시를_내고_답변_모델은_부르지_않는다():
    model = FakeModel()
    assert ask(embedder=FakeEmbedder(error=TimeoutError()), model=model) == [Stage.SEARCH, Failure(TIMEOUT_MESSAGE)]
    assert model.calls == []


def test_임베딩이_실패하면_오류_표시를_내고_답변_모델은_부르지_않는다():
    model = FakeModel()
    assert ask(embedder=FakeEmbedder(error=ConnectionError("끊김")), model=model) == [Stage.SEARCH, Failure(ERROR_MESSAGE)]
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
    assert ask(embedder=FakeEmbedder([0.0, 0.0, 0.0]), model=model) == [Stage.SEARCH, Failure(ERROR_MESSAGE)]
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
    _name("Bevel", "베벨"), _name("Segments", "부분"), _name("Face", "페이스"), _name("Scale", "스케일"),
    _name("Merge by Distance", "거리로 병합"), _name("Cube", "큐브"), _name("Axis", "축"),
    _many("Union", ("결합", "*"), ("Union", "NodeTree")), _many("Difference", ("차이", "*"), ("차이점", "Color")),
    _many("Modifiers", ("모디파이어", "*"), ("수정자", "ID")), _many("Render", ("렌더", "*"), ("렌더링", "ID")),
    _many("Physics", ("피직스", "*"), ("물리학", "ID")),
]  # fmt: skip
SCREEN_EXTRA = {"Origins": "오리진", "Set Parent To": "다음으로 부모를 설정", "X-Ray": "X-Ray", "S": "S", "W": "W",
                "Forward": "앞으로", "Unselected": "선택되지 않은", "By Distance": "거리에 의해",
                "Orthographic": "정사법", "Navigation Controls": "네비게이션 컨트롤"}  # 넓힌 목록(티켓 49)


def shown(pieces, state=KOREAN_SCREEN, choices=None, question="메시 추가") -> str:
    """가짜 모델이 pieces를 낼 때 사용자가 보는 답 글(조각을 이어 붙인 것)."""
    names = MenuNames(SCREEN_NAMES, choices or {}, extra=SCREEN_EXTRA)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    return "".join(event.text for event in engine.answer(question, state, []) if isinstance(event, Piece))


def test_한국어_화면에_번역이_켜져_있으면_메뉴_이름을_한국어_괄호_영어로():
    assert shown(("[[Add > Mesh]]를 누르세요.",)) == "추가(Add) > 메시(Mesh)를 누르세요."


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Add 메뉴가 어디예요?", "Add(추가) > 메시(Mesh)를 누르세요."),  # 질문이 영어로 쓴 이름만 영어(한국어)
        ("add > mesh 눌렀는데 안 보여요", "Add(추가) > Mesh(메시)를 누르세요."),  # 대소문자는 가리지 않는다
        ("Addon 설치하고 메시 추가", "추가(Add) > 메시(Mesh)를 누르세요."),  # 더 긴 영어 낱말 속 글자는 아님
    ],
)
def test_질문에_영어로_쓴_메뉴_이름은_영어_괄호_한국어로(question, expected):
    assert shown(("[[Add > Mesh]]를 누르세요.",), question=question) == expected


def test_질문에_영어_이름이_있어도_영어_화면이면_영어만():
    english = replace(STATE, language="en_US", translate_interface=True)
    assert shown(("[[Add > Mesh]]를 누르세요.",), english, question="Add 메뉴가 어디예요?") == "Add > Mesh를 누르세요."


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
        # 바로 앞 단을 붙인 짝(지어낸 예): Mesh 아래 Apply만 다른 글자, 혼자 쓰면 이름 하나의 짝
        (("[[Mesh > Apply]], [[Apply]]",), {"Apply": "*", "Mesh > Apply": "WindowManager"},
         "메시(Mesh) > 신청하기(Apply), 적용(Apply)"),
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
    assert events[:3] == [*ANSWERING, Piece("Add >")] and isinstance(events[3], Failure)


def test_답변_모델에게_메뉴_이름을_영어로_표시해_쓰라고_지시한다():
    model = FakeModel()
    ask(model=model)
    assert "[[Add > Mesh]]" in model.calls[0][0]["content"]


def test_생각_수준은_정해_둔_이름만_받는다():
    """평가 때 설정을 바꿔 가며 사람이 넣는 값이라, 오타가 그대로 기록되지 않게 바로 오류를 낸다(티켓 28).

    값은 명세의 none·low·medium. 실제 모델이 받는 값은 티켓 33에서 맞춘다.
    """
    assert Settings().reasoning is Reasoning.LOW  # 결정 7: 기본 low(사용자 "그럼 답 모델은 일단 low 로 가자", HISTORY [578])
    assert Settings(reasoning="low").reasoning is Reasoning.LOW
    with pytest.raises(ValueError):
        Settings(reasoning="nnoe")


# 질문 바꾸기(티켓 43, HISTORY [127])


class FakeRewriter:
    """질문 바꾸기 모델 대신: release가 열릴 때까지 기다렸다가 answer를 cut 글자에서 두 조각으로 흘려 준다(error면 그 오류를 낸다).
    tail을 주면 둘째 조각 앞에서 그것이 열릴 때까지 기다리고, tail_error를 주면 둘째 조각 대신 그 오류를 낸다.
    받은 글을 적어 두고, 끝까지 읽혔으면 finished가 열린다."""

    def __init__(self, answer='{"query": "array copies"}', release: threading.Event | None = None, error: Exception | None = None,
                 cut: int | None = None, tail: threading.Event | None = None, tail_error: Exception | None = None):
        self.answer, self.error, self.tail, self.tail_error = answer, error, tail, tail_error
        self.cut = len(answer) // 2 if cut is None else cut
        self.release = release or threading.Event()
        if release is None:
            self.release.set()
        self.calls: list[list[dict[str, str]]] = []
        self.finished = threading.Event()

    def stream(self, messages):
        self.calls.append(messages)
        self.release.wait(5)
        if self.error:
            raise self.error
        yield self.answer[: self.cut]
        if self.tail:
            self.tail.wait(5)
        if self.tail_error:
            raise self.tail_error
        yield self.answer[self.cut :]
        self.finished.set()


def ask_rewritten(rewriters, question="배열로 복사하려면?", embedder=None, model=None, settings=Settings(), recent=(), state=STATE, step=None):
    engine = AnswerEngine(CHUNKS, VECTORS, embedder or FakeEmbedder(), model or FakeModel(), settings, rewriters=rewriters)
    return list(engine.answer(question, state, list(recent), step))


def test_질문_바꾸기를_동시에_불러_먼저_온_답의_검색어만_임베딩한다():
    late = threading.Event()  # 첫 모델은 셋째가 답한 뒤에야 답한다
    rewriters = [FakeRewriter('{"query": "bevel width"}', late), FakeRewriter("{}"), FakeRewriter('{"query": " array copies "}')]
    embedder = FakeEmbedder(by_text={"array copies": TOWARD_ARRAY})
    events = ask_rewritten(rewriters, embedder=embedder)
    late.set()
    assert embedder.calls == [["array copies"]]  # 검색어 없는 둘째 답은 버리고, 늦은 첫째는 기다리지 않는다
    assert found(events)[0] == ARRAY
    assert all(len(rewriter.calls) == 1 for rewriter in rewriters)  # 셋 다 불렀다


def test_검색어_칸이_닫히면_나머지_칸을_기다리지_않고_찾고_호출은_뒤에서_끝까지_읽는다():
    tail = threading.Event()  # 분야 칸은 답이 끝난 뒤에야 온다
    answer = '{"query": "array copies", "areas": ["modeling/modifiers"], "exclude": []}'
    rewriter = FakeRewriter(answer, cut=answer.index(","), tail=tail)
    embedder = FakeEmbedder(by_text={"array copies": TOWARD_ARRAY})
    events = ask_rewritten([rewriter], embedder=embedder)
    assert found(events)[0] == ARRAY and not rewriter.finished.is_set()
    tail.set()
    assert rewriter.finished.wait(5)  # 요금 기록(마지막 조각)을 받으려고 끝까지 읽는다


def test_검색어_칸이_뒤에_있어도_닫힌_곳에서_쓰고_따옴표_풀이를_지킨다():
    rewriter = FakeRewriter('{"areas": [], "query": "array \\"copies\\"", "exclude": []}')
    embedder = FakeEmbedder()
    ask_rewritten([rewriter], embedder=embedder)
    assert embedder.calls == [['array "copies"']]


def test_검색어를_쓴_뒤에_난_오류는_답을_멈추지_않고_기록만_남긴다(caplog):
    answer = '{"query": "array copies", "areas": []}'
    rewriter = FakeRewriter(answer, cut=answer.index(","), tail_error=OSError("끊김"))
    events = ask_rewritten([rewriter])
    assert isinstance(events[-1], Done)
    assert rewriter.calls and _waited(lambda: "끊김" in caplog.text)


def _waited(check, seconds=5.0):
    """뒤에서 도는 일이 check를 참으로 만들 때까지 조금씩 기다린다."""
    deadline = time.monotonic() + seconds
    while not check() and time.monotonic() < deadline:
        time.sleep(0.01)
    return check()


def test_빈_검색어는_쓸_수_없는_답으로_버린다():
    late = threading.Event()  # 빈 검색어가 먼저 온다
    threading.Timer(0.1, late.set).start()
    embedder = FakeEmbedder()
    events = ask_rewritten([FakeRewriter('{"query": "  ", "areas": []}'), FakeRewriter('{"query": "array copies"}', late)], embedder=embedder)
    assert embedder.calls == [["array copies"]] and isinstance(events[-1], Done)


def test_질문_바꾸기에는_분야_목록을_담은_지시와_질문만_보낸다():
    rewriter = FakeRewriter()
    ask_rewritten([rewriter])
    system, user = rewriter.calls[0]
    assert "목록(폴더 이름):\naddons\nfiles\nmodeling/meshes\nmodeling/modifiers\nJSON" in system["content"]  # 청크의 분야(큰 분야는 둘째 폴더까지)
    assert user == {"role": "user", "content": "배열로 복사하려면?"}  # 맥락이 없으면 측정 때처럼 질문 한 줄


def test_맥락이_있으면_질문_아래에_참고로_붙이고_먼저_볼_소제목_경로는_보내지_않는다():
    rewriter = FakeRewriter()
    step = Step("save-file", "파일 저장하기", manual=("files/blend/save.html#save",))
    state = replace(STATE, recent_operators=("wm.save_mainfile",))
    ask_rewritten([rewriter], question="그다음은요?", recent=[("저장은 어떻게 해요?", "답")], state=state, step=step)
    assert rewriter.calls[0][1]["content"] == (
        "그다음은요?\n\n# 참고(질문을 이해하는 데만 쓴다)\n"
        "- 직전 질문: 저장은 어떻게 해요?\n- 지금 연습 단계: 파일 저장하기\n- 방금 실행한 조작: wm.save_mainfile"
    )


# 기다리는 동안 단계 보이기(티켓 51)


class Journal:
    """가짜 부품이 불린 차례와 엔진이 낸 단계를 한 줄로 적는다(단계가 그 호출보다 먼저 왔는지 보려고)."""

    def __init__(self):
        self.lines: list[str] = []

    def wrap(self, name, method):
        def called(*args, **kwargs):
            self.lines.append(name)
            return method(*args, **kwargs)
        return called


def test_단계는_엔진이_그_단계의_호출에_들어가기_바로_전에_하나씩_낸다():
    journal = Journal()
    rewriter, embedder, model = FakeRewriter(), FakeEmbedder(), FakeModel()
    rewriter.stream = journal.wrap("질문 바꾸기 부름", rewriter.stream)
    embedder.embed = journal.wrap("임베딩 부름", embedder.embed)
    model.stream = journal.wrap("답변 모델 부름", model.stream)
    engine = AnswerEngine(CHUNKS, VECTORS, embedder, model, rewriters=[rewriter])
    for event in engine.answer("배열로 복사하려면?", STATE, []):
        journal.lines.append(event.value if isinstance(event, Stage) else type(event).__name__)
    assert journal.lines == [
        Stage.REWRITE.value, "질문 바꾸기 부름", Stage.SEARCH.value, "임베딩 부름", Stage.ANSWER.value, "답변 모델 부름",
        "Piece", "Piece", "Piece", "Done",
    ]


def test_질문_바꾸기가_없는_엔진은_그_단계를_내지_않는다():
    assert [event for event in ask() if isinstance(event, Stage)] == [Stage.SEARCH, Stage.ANSWER]


def test_단계_이름은_생각을_끄든_켜든_참인_쉬운_말이다():
    # 답 모델 thinking이 none이 될 수 있어([578]) '생각하는 중'처럼 켠 때만 맞는 말은 쓰지 않는다
    assert [stage.value for stage in Stage] == ["Blender 설정을 읽는 중", "질문을 정리하는 중", "설명서에서 찾는 중", "답을 만드는 중"]


def test_질문_바꾸기가_모두_실패하면_한국어_질문으로_찾지_않고_오류_표시로_멈춘다():
    embedder, model = FakeEmbedder(), FakeModel()
    events = ask_rewritten([FakeRewriter(error=OSError("연결 끊김")), FakeRewriter("검색어 아님")], embedder=embedder, model=model)
    assert events == [Stage.REWRITE, Failure(ERROR_MESSAGE)]  # 찾기·답 단계는 들어가지 않았으니 내지 않는다
    assert embedder.calls == [] and model.calls == []


def test_오류_표시로_멈추면_어떤_답이_와서_실패했는지_기록에_남긴다(caplog):
    events = ask_rewritten([FakeRewriter("[]")])
    assert events == [Stage.REWRITE, Failure(ERROR_MESSAGE)]
    assert "ValueError" in caplog.text and "'[]'" in caplog.text


def test_질문_바꾸기가_한도_안에_하나도_오지_않으면_시간_초과_표시로_멈춘다():
    never = threading.Event()
    model = FakeModel()
    events = ask_rewritten([FakeRewriter(release=never), FakeRewriter(release=never)], model=model, settings=Settings(rewrite_timeout=0.05))
    never.set()
    assert events == [Stage.REWRITE, Failure(TIMEOUT_MESSAGE)] and model.calls == []


def test_예열은_질문_바꾸기_하나와_임베딩을_한_번씩_부른다():
    rewriters, embedder = [FakeRewriter(), FakeRewriter()], FakeEmbedder()
    AnswerEngine(CHUNKS, VECTORS, embedder, FakeModel(), rewriters=rewriters).warm_up()
    assert [len(rewriter.calls) for rewriter in rewriters] == [1, 0] and len(embedder.calls) == 1


# 감싸지 않은 이름·화면과 다른 한국어(티켓 49). 모델이 [[ ]]로 감싸지 않아도 한국어 화면이면 사전·넓힌 목록의 이름을 화면 글자로


def test_감싼_이름이_사전에_없으면_넓힌_목록으로_바꾼다():
    assert shown(("[[Origins]] 체크를 끄세요.",)) == "오리진(Origins) 체크를 끄세요."


def test_감싸지_않은_영어_이름도_한국어_화면이면_화면_글자로_바꾼다():
    text = "지금 Bevel 모디파이어는 Segments가 1이에요. Origins를 끄고 Set Parent To 메뉴를 여세요."
    assert shown((text,)) == ("지금 베벨(Bevel) 모디파이어는 부분(Segments)이 1이에요. "
                              "오리진(Origins)을 끄고 다음으로 부모를 설정(Set Parent To) 메뉴를 여세요.")
    assert shown(("Merge by Distance를 고르세요.",)) == "거리로 병합(Merge by Distance)을 고르세요."  # 긴 이름 먼저


@pytest.mark.parametrize(
    "text",
    [
        "Cube를 고르세요.",  # 작업 상태의 물체 이름(아웃라이너에 보이는 글자 그대로)
        "불리언 대상은 Cube로 되어 있어요.",  # 고르지 않은 물체도 기본 이름이면 물체 이름일 수 있다
        "`Bevel` 값을 보세요.",  # 코드
        "Space 키를 누르세요. Shift+Bevel은 없어요.",  # 단축키
        "설명서의 Bevel 쪽을 보세요. 설명서에 \"Scale\"이 있어요.",  # 설명서 대목 인용
        "Blender에서 SCULPT 모드예요.",  # 프로그램 이름·대문자 값
        "Primary Bevel Axis를 바꾸세요.",  # 사전에 없는 낱말이 섞인 덩이는 통째로 둔다
        "Edit Mode에서 Array를 보세요.",  # 번역 여러 개(고정 짝이 있어도 자리를 몰라서)·통과 안 한 제목 이름은 영어 그대로
        "bpy.ops.Bevel 이나 Bevel_edges",  # 코드 이름 속
        "Bevel Segments 값",  # 낱말마다는 사전에 있어도 덩이 전체가 이름 하나가 아니면(화면에 없는 글이 된다)
        "Bevel/Segments 칸",  # 빗금으로 이은 영어
    ],
)
def test_바꾸면_안_되는_영어는_그대로_둔다(text):
    assert shown((text,)) == text
    assert shown((text,), choices={"Edit Mode": "Operator"}) == text  # 기본 문맥과 다른 고정 짝


def test_화면과_다른_한국어를_붙인_이름은_화면_글자로_고친다():
    # 괄호 앞 글은 이름을 옮긴 말이 아니라 설명·동사일 때가 많아(옵션(Only Selected), 녹여(Dissolve)) 고치지 않고 괄호 속에 넣는다
    assert shown(("3을 눌러 면(Face) 고르기",)) == "3을 눌러 면 '페이스'(Face) 고르기"
    assert shown(("모서리 다듬기(Bevel)를",)) == "모서리 다듬기 '베벨'(Bevel)을"
    assert shown(("1. 평평한 쪽(Face) 고르기",)) == "1. 평평한 쪽 '페이스'(Face) 고르기"  # Fable 꼴([393])
    assert shown(("메뉴에서 병합(Merge by Distance)을",)) == "메뉴에서 '거리로 병합'(Merge by Distance)을"  # 앞말이 화면 글자 낱말뿐이면 지움
    assert shown(("하나로 녹여(Dissolve) 없앱니다",)) == "하나로 녹여(Dissolve) 없앱니다"  # 이어 주는 꼴은 모델 꼴 그대로
    assert shown(("하나로 녹여(Dissolve) 없앱니다. 다시 [[Dissolve]]",)).endswith("다시 " + shown(("[[Dissolve]]",)))  # 모델 꼴로 둔 이름은 아직 안 보인 것
    # 영어 뒤 풀이 괄호는 지운다("스케일(Scale, 크기 조절)"은 거부된 꼴 [349], 덧붙인 괄호는 지우기로 [353]·[354])
    assert shown(("Scale(크기 조절)을 쓰세요.",)) == "스케일(Scale)을 쓰세요."
    assert shown(("Bevel(또는 Segments)로",)) == "베벨(Bevel)로"  # 지운 괄호 속 영어는 다시 건드리지 않는다
    assert shown(("베벨(Bevel)과 스케일 (Scale), Bevel(베벨)",)) == "베벨(Bevel)과 스케일 (Scale), Bevel(베벨)"  # 이미 화면 글자
    assert shown(("거리로 병합(Merge by Distance)",)) == "거리로 병합(Merge by Distance)"  # 여러 낱말 화면 글자
    assert shown(("엑스레이(X-Ray), X-Ray(엑스레이)",)) == "엑스레이(X-Ray), X-Ray(엑스레이)"  # 화면도 영어인 이름
    assert shown(("S(크기 조절)를 누르고 와트(W)로",)) == "S(크기 조절)를 누르고 와트(W)로"  # 한 글자는 키·단위


def test_영어_뒤_풀이_괄호는_지우고_화면_글자_꼴로_낸다():
    # 거부된 "결합(Union, 합집합)"·"Focal Length(초점의 길이, 초점의 길이)" 꼴을 내지 않는다([349], 2026-11-17)
    union = {"Union": "*", "Difference": "*"}
    assert shown(("방식을 Union(합집합), Difference(차집합) 중",), choices=union) == "방식을 결합(Union), 차이(Difference) 중"
    assert shown(("Union(합집합)과 다시 Union(합집합)을",), choices=union) == "결합(Union)과 다시 결합을"  # 두 번째는 화면 글자만
    assert shown(("연산은 **Difference(차집합)** 입니다",), choices=union) == "연산은 **차이(Difference)** 입니다"
    assert shown(("연산은 **Union(합집합)**을 고릅니다",), choices=union) == "연산은 **결합(Union)**을 고릅니다"
    assert shown(("**Bevel(베벨, Bevel)** 값",)) == "**Bevel(베벨)** 값"  # 화면 글자로 시작하면 영어(화면 글자) 그대로, 뒤 풀이만 지움
    assert shown(("Bevel(베벨 모디파이어) 값",)) == "Bevel(베벨 모디파이어) 값"  # 쉼표 없이 이어진 풀이는 둔다


def test_Fable_꼴_뒤_굵은_글씨를_건너_조사를_맞춘다():
    union = {"Difference": "*"}
    assert shown(("연산이 **차집합(Difference)**으로 되어",), choices=union) == "연산이 **차집합 '차이'(Difference)**로 되어"
    assert shown(("연산이 **차집합(Diff", "erence)*", "*으", "로 되어"), choices=union) == "연산이 **차집합 '차이'(Difference)**로 되어"  # 조각으로
    assert shown(("**합치기(Merge by Distance)**으로",)) == "**합치기 '거리로 병합'(Merge by Distance)**으로"  # 받침 있는 화면 글자
    # 앞말이 화면 글자 낱말뿐이면 굵은 글씨 표시를 건너 앞말을 지운다("**병합 '거리로 병합'" 되풀이 막기, 2026-11-17)
    assert shown(("**병합(Merge by Distance)**을",)) == "**'거리로 병합'(Merge by Distance)**을"
    assert shown(("메뉴에서 **병합(Merge by Distance)**을 고릅니다",)) == "메뉴에서 **'거리로 병합'(Merge by Distance)**을 고릅니다"
    # 굵은 글씨가 앞말 가운데서 시작하면 앞 낱말("거리로 ")을 흐름에서 먼저 내보내 지울 수 없다(전과 같은 꼴, 저장된 답에 없음)
    assert shown(("거리로 **병합(Merge by Distance)**을",)) == "거리로 **병합 '거리로 병합'(Merge by Distance)**을"


@pytest.mark.parametrize("cut", range(1, 40))
def test_굵은_글씨_앞말_지우기는_조각으로_와도_같다(cut):
    text = "메뉴에서 **병합(Merge by Distance)**을 고릅니다"
    assert shown((text[:cut], text[cut:])) == "메뉴에서 **'거리로 병합'(Merge by Distance)**을 고릅니다", (text[:cut], text[cut:])


def test_Fable_꼴도_어색한_화면_글자면_항목을_넣는다():
    # 조사·어미로 끝나는 화면 글자에 조사가 바로 붙으면 "'거리에 의해'(By Distance)를"처럼 읽혀 '항목'을 넣는다([355]-[357])
    assert shown(("M 키를 누르고 거리로 병합(By Distance)를 골라도",)) == "M 키를 누르고 거리로 병합 '거리에 의해'(By Distance) 항목을 골라도"
    assert shown(("선택 안 된 것과 병합(Unselected)을 켜세요.",)) == "선택 안 된 것과 병합 '선택되지 않은'(Unselected) 항목을 켜세요."
    assert shown(("모두(By Distance)로",)) == "모두 '거리에 의해'(By Distance) 항목으로"
    assert shown(("세계 배경(Face)이 보입니다.",)) == "세계 배경 '페이스'(Face)가 보입니다."  # 멀쩡한 화면 글자는 그대로
    assert shown(("거리로 병합(By Distance) 옵션을",)) == "거리로 병합 '거리에 의해'(By Distance) 옵션을"  # 조사가 없으면 그대로


@pytest.mark.parametrize("cut", range(1, 40))
def test_Fable_꼴은_앞말을_감싼_모델_따옴표를_뗀다(cut):
    # "'정투영' '정사법'(Orthographic)"처럼 따옴표가 겹치지 않게, 앞말을 감싼 따옴표는 떼고 화면 글자에만 둔다(2026-11-17)
    for text, expected in [
        ("타입이 '정투영(Orthographic)'으로 되어", "타입이 정투영 '정사법'(Orthographic)으로 되어"),
        ("설명서의 '탐색 조작 버튼(Navigation Controls)'입니다.", "설명서의 탐색 조작 버튼 '네비게이션 컨트롤'(Navigation Controls)입니다."),
        ('합치려면 "선택되지 않은 것 포함(Unselected)" 옵션을', "합치려면 선택되지 않은 것 포함 '선택되지 않은'(Unselected) 옵션을"),
    ]:
        assert shown((text[:cut], text[cut:])) == expected, (text[:cut], text[cut:])


TABS = {"Modifiers": "*", "Render": "*"}  # 실제 고정 짝처럼 메뉴·패널 글자(기본 문맥)로 고정


@pytest.mark.parametrize(
    "pieces, expected",
    [
        # 속성 창 탭은 ID 문맥 글자(화면대로, 사용자 "화면대로가 원칙인데", 2026-11-17)
        (("충돌은 Physics 탭에서 켭니다.",), "충돌은 물리학(Physics) 탭에서 켭니다."),
        (("오른쪽 위 [[Render]] 탭에서 엔진을",), "오른쪽 위 렌더링(Render) 탭에서 엔진을"),
        (("속성 창의 렌더(Render) 탭을 엽니다.",), "속성 창의 렌더링(Render) 탭을 엽니다."),  # 앞말이 같은 이름의 다른 글자면 통째로
        (("파란 렌치 모양 탭(Modifiers)을 누릅니다.",), "파란 렌치 모양 탭 '수정자'(Modifiers)를 누릅니다."),  # 탭이 앞
        (("[[Render]] > [[Bake]]와 [[Modifiers]]를",), "렌더(Render) > Bake와 모디파이어(Modifiers)를"),  # 탭이 아니면 메뉴 글자
        (("상단 메뉴에서 [[Render]] 탭을 엽니다.",), "상단 메뉴에서 렌더(Render) 탭을 엽니다."),  # 메뉴라고 한 절은 둔다
        (("[[Render]] 메뉴와 [[Render]] 탭",), "렌더(Render) 메뉴와 렌더링(Render) 탭"),  # 한 답에 둘 다
        (("충돌은 Phys", "ics", " ", "탭", "에서 켭니다."), "충돌은 물리학(Physics) 탭에서 켭니다."),  # 조각으로
        (("렌더(Render)", " 탭을 엽", "니다."), "렌더링(Render) 탭을 엽니다."),
        (("오른쪽 위 [[Render]]", " ", "탭"), "오른쪽 위 렌더링(Render) 탭"),
    ],
)
def test_속성_창_탭_이름은_탭_글자로(pieces, expected):
    assert shown(pieces, choices=TABS) == expected


def test_번역이_여러_개인_이름은_고정_짝이_기본_문맥_글자일_때만_감싸지_않은_글에서_바꾼다():
    assert shown(("Edit Mode에서",), choices={"Edit Mode": "*"}) == "에디트 모드(Edit Mode)에서"
    assert shown(("Edit Mode에서",), choices={"Edit Mode": "Operator"}) == "Edit Mode에서"  # 자리마다 글자가 갈림
    assert shown(("[[Edit Mode]]에서",), choices={"Edit Mode": "Operator"}) == "편집 모드(Edit Mode)에서"  # 감싼 이름은 짝대로


def test_메뉴_경로_속_기본_물체_이름은_메뉴_이름으로_바꾼다():
    nothing = replace(KOREAN_SCREEN, active_object=None, selected_objects=())  # Cube라는 물체를 고르지 않음
    assert shown(("Shift+A > Mesh > Cube를 누르세요.",), nothing) == "Shift+A > 메시(Mesh) > 큐브(Cube)를 누르세요."
    assert shown(("대상은 Cube예요.",), nothing) == "대상은 Cube예요."


def test_질문에_영어로_쓴_이름은_감싸지_않아도_영어_괄호_한국어로():
    assert shown(("Bevel을 다시 넣으세요.",), question="Bevel이 안 먹어요") == "Bevel(베벨)을 다시 넣으세요."


def test_영어_이름과_괄호가_조각_사이에_갈려_와도_바꾼다():
    pieces = ("A로 Merge by ", "Distance를 고르고 3으로 면(", "Face) 고", "르기. 끝에 Bevel")
    assert shown(pieces) == "A로 거리로 병합(Merge by Distance)을 고르고 3으로 면 '페이스'(Face) 고르기. 끝에 베벨(Bevel)"


@pytest.mark.parametrize(
    "pieces, expected",
    [
        # 표시 바로 뒤에 모델이 덧붙인 괄호(단축키·풀이)는 지운다. 겹친 괄호가 되지 않게(티켓 50 나).
        # 단축키 하나뿐인 괄호는 지우고 그 문장 뒤에 "단축키는 …입니다."로 옮긴다([353] 사용자 예문, [423])
        (("[[Face]](단축키 Alt-F)를 누르세요.",), "페이스(Face)를 누르세요. 단축키는 Alt-F입니다."),
        (("[[Face]] (Alt-F)를 누르세요.",), "페이스(Face)를 누르세요. 단축키는 Alt-F입니다."),
        (("[[Face]](또는 면 채우기)를 누르세요.",), "페이스(Face)를 누르세요."),  # 단축키가 아닌 풀이는 지우기만
        # 괄호 속에 표시가 든 것은 풀이가 아니라 내용이라 둔다
        (("[[Face]](또는 [[Add]])를 누르세요.",), "페이스(또는 추가)를 누르세요."),  # 괄호가 남아 겹치는 자리는 화면 글자만([458], 옛 기대 "페이스(Face)(또는 추가(Add))")
        # 조각 사이에 갈려 와도 같다
        (("[[Fa", "ce]]", "(단축", "키 Alt-F)", "를 누르세요."), "페이스(Face)를 누르세요. 단축키는 Alt-F입니다."),
    ],
)
def test_표시_뒤에_덧붙인_괄호는_지운다(pieces, expected):
    assert shown(pieces) == expected


@pytest.mark.parametrize(
    "pieces, expected",
    [
        # 모델이 영어 이름에 맞춰 쓴 조사를 화면 글자 받침에 맞춘다(티켓 50, 번역 때 [91]과 같은 규칙)
        (("[[Add]]을 누르세요.",), "추가(Add)를 누르세요."),
        (("[[Axis]]로 맞추세요.",), "축(Axis)으로 맞추세요."),
        (("[[Bevel]]으로 다듬어요.",), "베벨(Bevel)로 다듬어요."),  # ㄹ 받침 뒤는 '로'
        (("[[Face]]이 하나 생겨요.",), "페이스(Face)가 하나 생겨요."),
        (("[[Segments]]이 1이에요.",), "부분(Segments)이 1이에요."),  # 받침이 있으면 그대로
        (("[[Add]]", "을 누르세요."), "추가(Add)를 누르세요."),  # 조사가 다음 조각에 와도
        (("[[Add]]이라는 메뉴",), "추가(Add)이라는 메뉴"),  # 뒤가 한글이면 조사인지 몰라 둔다
        (("[[Snap Base]]을 켜세요.",), "Snap Base을 켜세요."),  # 화면 글자가 영어면 둔다
    ],
)
def test_표시_뒤_조사를_화면_글자에_맞춘다(pieces, expected):
    assert shown(pieces) == expected


def test_감싸지_않은_이름을_바꾸면_뒤_조사도_화면_글자에_맞춘다():
    assert shown(("Axis로 두고 Add을 누르고 Face(면)을 보세요.",)) == (
        "축(Axis)으로 두고 추가(Add)를 누르고 페이스(Face)를 보세요.")  # 지운 풀이 괄호 뒤 조사도 화면 글자에


@pytest.mark.parametrize(
    "pieces, expected",
    [
        # 조사·어미로 끝나거나 명령 구절인 화면 글자 뒤에 조사가 바로 붙으면 "앞으로로"처럼 읽혀,
        # 따옴표로 묶고 '항목'을 넣는다(티켓 50, HISTORY [355]·[356]). 되풀이면 영어 괄호만 빠진다
        (("[[Forward]]로 두고 다시 [[Forward]]는 -Z",), "'앞으로'(Forward) 항목으로 두고 다시 '앞으로' 항목은 -Z"),
        (("[[Unselected]]은 끄세요.",), "'선택되지 않은'(Unselected) 항목은 끄세요."),
        (("[[Set Parent To]]를 누르세요.",), "'다음으로 부모를 설정'(Set Parent To) 항목을 누르세요."),
        (("Forward를 고르세요.",), "'앞으로'(Forward) 항목을 고르세요."),  # 감싸지 않은 이름도
        (("[[Forward]] 칸",), "앞으로(Forward) 칸"),  # 조사가 바로 붙지 않으면 그대로
    ],
)
def test_어색한_화면_글자에_조사가_붙으면_따옴표와_항목으로(pieces, expected):
    assert shown(pieces) == expected


def test_같은_이름이_되풀이되면_처음_한_번만_영어_괄호():
    """답이 쓸데없이 길어지지 않게, 낱말 표의 '처음 한 번만'과 같이(티켓 50 라, HISTORY [353])."""
    text = ("[[Add > Mesh]]를 누르고 Bevel을 켠 뒤 다시 [[Add]]와 [[Bevel]]을 보세요.",)
    assert shown(text) == "추가(Add) > 메시(Mesh)를 누르고 베벨(Bevel)을 켠 뒤 다시 추가와 베벨을 보세요."


def test_영어_화면이면_덧붙인_괄호와_조사는_그대로():
    english = replace(STATE, language="en_US", translate_interface=True)
    assert shown(("[[Face]](단축키 Alt-F)을 누르고 [[Face]]",), english) == "Face(단축키 Alt-F)을 누르고 Face"


def test_영어_화면이면_감싸지_않은_이름은_그대로():
    english = replace(STATE, language="en_US", translate_interface=True)
    assert shown(("지금 Bevel과 면(Face)",), english) == "지금 Bevel과 면(Face)"


@pytest.mark.parametrize(
    "text",
    [
        "지금 [[Add > Mesh]]에서 Bevel 모디파이어의 Segments를 올리고 면(Face)을 고르세요.",
        "`Bevel` 값과 `Scale` 값을 보고 Merge by Distance를 누르세요.",  # 백틱이 조각 사이에 갈릴 수 있다
        "the quick brown fox jumps over the lazy Bevel 이라는 영어 문장",  # 일곱 낱말이 넘는 영어 끝의 이름
        "설명 (the quick brown fox jumps over the lazy dog Bevel 닫히지 않은 괄호",
        "Scale(크기 조절)과 Bevel(또는 Segments)와 Origins와 Set Parent To 메뉴",
        # 티켓 50: 표시 뒤 덧붙인 괄호·조사·되풀이 이름
        "[[Face]](단축키 Alt-F)을 누르고 [[Add > Mesh]] (메시 추가)이 나오면 다시 [[Face]]을 고르세요.",
        "[[Axis]]로 [[Bevel]]으로 Bevel 값과 [[Bevel]](또는 [[Add]])를 끝에 [[Face]]",
    ],
)
def test_조각을_어떻게_나눠_흘려도_한꺼번에_바꾼_것과_같다(text):
    import random

    whole = shown((text,))
    rng = random.Random(7)
    for _ in range(100):
        pieces, i = [], 0
        while i < len(text):
            n = rng.randint(1, 6)
            pieces.append(text[i : i + n])
            i += n
        assert shown(tuple(pieces)) == whole


# 티켓 50 가(HISTORY [358]-[360]): 모델이 스스로 옮긴 이름. 흔히 옮기는 말 목록은 지어낸 것
COMMON = {"Orthographic": ["직교 투영", "직교"], "Face": ["면", "페이스"], "Bevel": ["모깎기", "모서리 다듬기"], "Orbit": ["회전"],
          "UV Editor": ["UV 편집기"], "Value": ["명도"], "Mirror": ["좌우 대칭 거울 복사 기능"]}
COMMON_EXTRA = {**SCREEN_EXTRA, "Orthographic": "정사법", "Orbit": "궤도", "UV Editor": "UV 에디터", "Value": "값", "Mirror": "미러"}


def shown_common(pieces) -> str:
    names = MenuNames(SCREEN_NAMES, extra=COMMON_EXTRA, common=COMMON)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    return "".join(event.text for event in engine.answer("메시 추가", KOREAN_SCREEN, []) if isinstance(event, Piece))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("직교 투영(Orthographic)으로 바꿉니다.", "정사법(Orthographic)으로 바꿉니다."),  # 여러 낱말 앞말을 통째로
        ("모깎기(Bevel)를 씁니다.", "베벨(Bevel)을 씁니다."),  # 조사도 화면 글자에
        ("면 선택 모드(Face)를 켭니다.", "페이스(Face) 선택 모드를 켭니다."),  # 꼬리는 괄호 뒤로(㉠ [360])
        ("먼저 면(Face) 고르기", "먼저 페이스(Face) 고르기"),
        ("화면이 회전(Orbit)합니다.", "화면이 회전(Orbit)합니다."),  # 괄호 뒤 '하다' 꼴은 모델 꼴 그대로([393])
        ("모깎기(Bevel) 하나를 겁니다.", "베벨(Bevel) 하나를 겁니다."),  # 띄어 쓴 '하나'는 '하다' 꼴이 아니다
        ("모깎기(Bevel)하나", "베벨(Bevel)하나"),  # 붙여 쓴 '하나'도
        ("옆면(Face) 고르기", "옆면 '페이스'(Face) 고르기"),  # 목록 말 앞에 한글이 붙어 있으면 다른 낱말
        ("평평한 쪽(Face) 고르기", "평평한 쪽 '페이스'(Face) 고르기"),  # 목록에 없는 말은 Fable 꼴([393])
        ("페이스(Face)를", "페이스(Face)를"),  # 이미 화면 글자
        ("페이스 선택 모드(Face)를", "페이스(Face) 선택 모드를"),  # 앞말이 화면 글자 + 꼬리여도 꼬리는 괄호 뒤로(㉠)
        ("베벨 노드(Bevel)에", "베벨(Bevel) 노드에"),  # '노드'도 꼬리
        ("먼저 베벨 노드(Bevel)만", "먼저 베벨(Bevel) 노드만"),  # 앞에 다른 글이 있어도
        ("종류가 '직교(Orthographic)'로", "종류가 '정사법(Orthographic)'으로"),  # 따옴표·굵은 글씨 뒤 조사도 화면 글자에
        ("명도 값(Value)로 바꿉니다.", "값(Value)으로 바꿉니다."),  # 화면 글자가 꼬리 낱말로 끝나면 꼬리를 또 붙이지 않는다
        ("**모깎기(Bevel)**를 씁니다.", "**베벨(Bevel)**을 씁니다."),
    ],
)
def test_흔히_옮기는_말이면_앞말을_통째로_화면_글자로(text, expected):
    assert shown_common((text,)) == expected


def test_흔히_옮기는_말도_되풀이되면_두번째부터_화면_글자만():
    assert shown_common(("직교 투영(Orthographic)을 켜고 다시 직교(Orthographic)를 끕니다.",)) == (
        "정사법(Orthographic)을 켜고 다시 정사법을 끕니다.")


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_흔히_옮기는_말을_조각으로_흘려도_같다(seed):
    import random

    text = ("먼저 직교 투영(Orthographic)으로 바꾸고 면 선택 모드(Face)를 켭니다. 그다음 모깎기(Bevel)를 씁니다. "
            "여기서 UV 편집기(UV Editor)를 열고 좌우 대칭 거울 복사 기능(Mirror)을 씁니다.")  # 영어가 든 말, 긴 말
    rng, parts, i = random.Random(seed), [], 0
    while i < len(text):
        k = rng.randint(1, 6)
        parts.append(text[i : i + k])
        i += k
    assert shown_common(tuple(parts)) == shown_common((text,))


def test_맨_영어_이름_뒤_면도_화면_글자_받침에_맞춘다():
    # 2026-11-17 [420]: 저장된 답 Q43 "Bump Only면"이 "범프 만(Bump Only)면"으로 나왔다(조사 목록에 이면/면이 없어서)
    assert shown(("Bevel면 됩니다.",)) == "베벨(Bevel)이면 됩니다."


def test_맨_영어_이름_뒤_덧붙인_괄호는_표시_뒤처럼_지운다():
    # 2026-11-17 [422]: "Join(Ctrl-J)" → "합치기(Join)(Ctrl-J)"로 괄호가 겹쳤다(answer-forms "겹친 괄호 없음").
    # 표시 뒤 덧붙인 괄호를 지우는 규칙([353], _after_mark)과 맨 영어 뒤 한글 풀이를 지우는 규칙([397])을 맨 영어 뒤 단축키·값·영어 괄호까지 넓힌다
    assert shown(("Bevel(Ctrl-B)로 깎습니다.",)) == "베벨(Bevel)로 깎습니다. 단축키는 Ctrl-B입니다."  # 단축키는 문장으로([423])
    assert shown(("Bevel (Ctrl + B)을 누릅니다.",)) == "베벨(Bevel)을 누릅니다. 단축키는 Ctrl + B입니다."  # 빈칸 하나 뒤 괄호, 조사는 화면 글자 받침에
    assert shown(("Scale(0.5)는 그대로",)) == "스케일(Scale)은 그대로"  # 값 괄호도 표시 뒤처럼 지운다
    assert shown(("Bevel", " (Ctrl", "+B)을 누릅니다.")) == "베벨(Bevel)을 누릅니다. 단축키는 Ctrl+B입니다."  # 괄호 중간에서 끊겨 와도 같다
    assert shown(("Bevel (Ctrl+B)", "을 누릅니다.")) == "베벨(Bevel)을 누릅니다. 단축키는 Ctrl+B입니다."  # 괄호가 닫힌 채 조각이 끝나도 같다(저장된 답 Q37 흐름 대조에서 찾음)
    assert shown(("X-Ray(Alt-Z)를 켭니다.",)) == "X-Ray(Alt-Z)를 켭니다."  # 이름이 안 바뀌면 괄호도 둔다


def test_괄호까지가_이름인_것은_괄호를_지우지_않는다():
    # "Mix (Legacy)"처럼 괄호까지가 화면 이름이면 덧붙인 괄호가 아니다(사전 175개·넓힌 목록 270개에 이런 꼴이 있음, 2026-11-17)
    names = MenuNames(SCREEN_NAMES, extra={**SCREEN_EXTRA, "Bevel (Legacy)": "베벨 (레거시)"})
    for answer in ("Bevel (Legacy) 노드를 씁니다.", "Bevel(Legacy) 노드를 씁니다."):  # 모델은 빈칸 없이도 쓴다("Intersect(Boolean)", [422])
        engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel((answer,)), menu_names=names)
        text = "".join(event.text for event in engine.answer("메시 추가", KOREAN_SCREEN, []) if isinstance(event, Piece))
        assert "베벨 (레거시) 노드를" in text, answer  # 괄호까지 통째로 화면 글자만([458], 옛 기대는 "(Legacy)"가 남음: "베벨(Bevel) (Legacy)")


@pytest.mark.parametrize(
    "answer, expected",
    [
        ("Math(Multiply) 노드와 연결합니다.", "수학(Math) 곱하기(Multiply) 노드와 연결합니다."),
        ("[[Math]](Multiply) → 변위", "수학(Math) 곱하기(Multiply) → 변위"),  # 표시 뒤도 같게(저장된 답 Q43 꼴)
        ("Math (power) 노드", "수학(Math) 전원(Power) 노드"),  # 노드 머리 글자는 목록 칸 문맥('NodeTree')의 글자, 대소문자는 화면 철자로
        ("Math(Ping-Pong) 노드", "수학(Math) Ping-Pong 노드"),  # 사전에 없는 계산 이름은 영어로 남긴다
        ("Math(계산) 노드", "수학(Math) 노드"),  # 계산 이름이 아닌 풀이는 지금처럼 지운다([422])
        ("Bevel(Multiply)", "베벨(Bevel)"),  # 머리 제목이 바뀌는 노드가 아니면 지운다
        # 조사는 뒤 이름(계산 이름) 받침에 맞춘다(Fable 검토 11-18: "곱하기(Multiply)과", "전원(Power)를"이 나왔다)
        ("Math(Multiply)와 연결합니다.", "수학(Math) 곱하기(Multiply)와 연결합니다."),
        ("[[Math]](Power)를 고릅니다.", "수학(Math) 전원(Power)을 고릅니다."),
        # 표시 뒤에 넣은 계산 이름이 맨 글 바꾸기를 다시 지나며 기본 문맥 글자로 바뀌지 않는다(Fable 검토: "라운드" → "둥근")
        ("[[Math]](Round) 노드", "수학(Math) 라운드(Round) 노드"),
        ("Math(Round) 노드", "수학(Math) 라운드(Round) 노드"),
        # 되풀이는 처음 한 번만 괄호([353]): 계산 이름도 노드 이름처럼
        ("Math(Multiply) 노드와 Math(Multiply) 노드", "수학(Math) 곱하기(Multiply) 노드와 수학 곱하기 노드"),
        # 조각으로 끊겨 와도 같다(통째·조각 대조)
        (("[[Math]](Mul", "tiply)를 고릅니다."), "수학(Math) 곱하기(Multiply)를 고릅니다."),
        (("Math(Mul", "tiply)", "를 고릅니다."), "수학(Math) 곱하기(Multiply)를 고릅니다."),
        # 사전에 없는 계산 이름도 노드 머리 문맥 번역이 있으면 한국어로([438], 저장된 사전에 "Divide"가 없었다)
        ("Math(Divide) 노드", "수학(Math) 나누기(Divide) 노드"),
    ],
)
def test_머리_제목이_계산_이름인_노드_뒤_괄호의_계산_이름은_남긴다(answer, expected):
    # 2026-11-18: 저장된 답 Q43 "Math(Multiply) 노드"가 "수학(Math) 노드"가 되어, 놓인 노드 머리에 뜨는 "곱하기"가 사라졌다
    # (사용자 "그냥 물어본대로 Multiply 던지 곱하기 라고 답변하면됐엇는데", [429]). 머리 제목이 목록 칸 값인 노드는 Blender 소스 labelfunc로 찾은 표
    names = MenuNames([*SCREEN_NAMES, _name("Math", "수학"), _many("Multiply", ("곱하기", "*"), ("곱하기", "NodeTree")),
                       _many("Power", ("파워", "*"), ("전원", "NodeTree")), _many("Round", ("둥근", "*"), ("라운드", "NodeTree"))],
                      choices={"Round": "*"}, extra=SCREEN_EXTRA, node_glyphs={"NodeTree": {"Multiply": "곱하기", "Power": "전원", "Round": "라운드", "Divide": "나누기"}})  # fmt: skip  Round 짝을 기본 문맥으로 둬야 맨 글 바꾸기가 "둥근"으로 바꾼다
    pieces = answer if isinstance(answer, tuple) else (answer,)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    assert "".join(event.text for event in engine.answer("메시 추가", KOREAN_SCREEN, []) if isinstance(event, Piece)) == expected


@pytest.mark.parametrize(
    "pieces, expected",
    [
        # [423] 덧붙인 단축키 괄호는 지운 뒤 그 문장 끝에 "단축키는 …입니다."로 옮긴다([353] 사용자 "단축키는 Alt-F 입니다")
        (("[[Face]](Alt-F)를 누르면 면이 생겨요.", " 다음은"), "페이스(Face)를 누르면 면이 생겨요. 단축키는 Alt-F입니다. 다음은"),
        (("[[Face]](Alt-F)를 누르면 면이 생", "겨요", ".", " 다음은"), "페이스(Face)를 누르면 면이 생겨요. 단축키는 Alt-F입니다. 다음은"),  # "." 앞뒤에서 끊김
        (("[[Bevel]](Ctrl-B) 폭을 0.5로 바꿉니다.",), "베벨(Bevel) 폭을 0.5로 바꿉니다. 단축키는 Ctrl-B입니다."),  # 소수점은 문장 끝이 아님
        (("1. [[Face]](Alt-F)를 누릅니다\n2. 끝",), "1. 페이스(Face)를 누릅니다 단축키는 Alt-F입니다.\n2. 끝"),  # 줄 끝에 마침표가 없어도
        (("[[Face]](Alt-F)를 누릅니다",), "페이스(Face)를 누릅니다 단축키는 Alt-F입니다."),  # 답 끝
        (("[[Face]](Alt-F)와 [[Bevel]](Ctrl-B)를 씁니다.",), "페이스(Face)와 베벨(Bevel)을 씁니다."),  # 한 문장에 둘이면 어느 것인지 몰라 지우기만
        (("단축키 Alt-F로도 됩니다. [[Face]](Alt-F)를 누릅니다.",), "단축키 Alt-F로도 됩니다. 페이스(Face)를 누릅니다."),  # 앞에 이미 나온 단축키
        (("[[Face]](Alt-F)를 누르고 Alt-F를 또 누릅니다.",), "페이스(Face)를 누르고 Alt-F를 또 누릅니다."),  # 같은 문장에 이미 씀
        (("[[Bevel]](B)를 누릅니다.",), "베벨(Bevel)을 누릅니다."),  # 한 글자 괄호는 칸·축 이름일 수 있어 지우기만
        # 같은 문장에 다른 키가 나오면 어느 것의 단축키인지 헷갈려 지우기만(저장된 답 Q26 "Ctrl + L로 고릅니다. 단축키는 Tab", Q28 "G로 옮기세요. 단축키는 4")
        (("[[Face]](Tab)를 누른 뒤 Ctrl + L로 고릅니다.",), "페이스(Face)를 누른 뒤 Ctrl + L로 고릅니다."),
        (("[[Face]](단축키 4)로 골라 G로 옮기세요.",), "페이스(Face)로 골라 G로 옮기세요."),
        (("[[Bevel]](단축키 B)를 누릅니다.",), "베벨(Bevel)을 누릅니다. 단축키는 B입니다."),  # 단축키라고 밝힌 한 글자는 옮김
        (("| [[Face]](Alt-F) | 채움 |\n다음",), "| 페이스(Face) | 채움 |\n다음"),  # 표 줄에는 넣지 않는다
        # 마침표 뒤에 닫는 기호가 붙은 문장 끝은 다음 문장에 붙지 않게 지우기만(advisor 지적, 2026-11-17)
        (("**[[Face]](Alt-F)를 누릅니다.** 그러면 면이 생깁니다.",), "**페이스(Face)를 누릅니다.** 그러면 면이 생깁니다."),
        (("면을 채웁니다(먼저 [[Face]](Alt-F)를 누르세요.) 그러면 됩니다.",), "면을 채웁니다(먼저 페이스를 누르세요.) 그러면 됩니다."),  # 괄호 안은 화면 글자만([458])
        (("\"[[Face]](Alt-F)를 누릅니다.\" 그다음",), "\"페이스(Face)를 누릅니다.\" 그다음"),
        (("Bevel(Ctrl-B)", "로 깎", "습니다.", " 끝"), "베벨(Bevel)로 깎습니다. 단축키는 Ctrl-B입니다. 끝"),  # 맨 영어 쪽도 같은 곳에서 넣는다
    ],
)
def test_덧붙인_단축키_괄호는_문장_뒤로_옮긴다(pieces, expected):
    assert shown(pieces) == expected


def test_단축키를_옮겨도_조각을_어떻게_나눠_흘려도_같다():
    import random

    text = "1. [[Face]](Alt-F)를 누르면 면이 생겨요. 폭은 0.5로 둡니다.\n2. Bevel (Ctrl+B)을 누릅니다\n| [[Add]](Shift-A) | 표 |\n끝"
    whole = shown((text,))
    assert "단축키는 Alt-F입니다." in whole and "단축키는 Ctrl+B입니다." in whole and "Shift-A" not in whole
    rng = random.Random(11)
    for _ in range(200):
        pieces, i = [], 0
        while i < len(text):
            k = rng.randint(1, 12)
            pieces.append(text[i : i + k])
            i += k
        assert shown(tuple(pieces)) == whole, pieces


def test_답이_오류로_끊기면_단축키_문장을_넣지_않는다():
    # [423]: 끊긴 문장 뒤에 "단축키는 …입니다."가 붙으면 끊긴 줄 모르고 읽게 된다
    from blender_tutor.answer_engine import _MenuMarks

    marks = _MenuMarks(MenuNames(SCREEN_NAMES, extra=SCREEN_EXTRA))
    text = marks.feed("[[Face]](Alt-F)를 누르") + marks.finish(cut=True)
    assert text == "페이스(Face)를 누르"


# 괄호 겹침(HANDOFF 2번, HISTORY [458]). 지금 코드가 모델 원문 796글에 새로 만든 겹침 121자리의 실제 꼴을 이 사전 이름으로 옮겼다
# (`results/20261118/143729_괄호겹침/갈래.md`). 사용자 결정: 이름·화면 글자에 괄호가 든 이름은 화면 글자만("어 권하는대로 해
# 예외여도 바꾼게 훨씬 낫네"), 덧말 괄호 안 이름도 화면 글자만이고 영어는 괄호 밖에 처음 나올 때("아 ㅇㅋ 화면글자만 ㅇㅇ")
PAREN_EXTRA = {**SCREEN_EXTRA, "glTF Binary (.glb)": "glTF 바이너리(.glb)", "Metric": "메트릭(미터법)", "Frame All": "모든 프레임",
               "Frame Selected": "선택한 프레임", "Edge": "엣지", "Loop Cut and Slide": "루프를 잘라내고 슬라이드", "Increment": "증가",
               "Merge Distance": "병합 거리", "Intersect": "교차", "Intersect (Boolean)": "교차 (불리언)", "Max": "최대",
               "Vertices": "버텍스", "Front": "앞쪽", "Right": "오른쪽", "Pin": "고정", "Pole": "폴", "Rotation": "회전",
               "Rotation & Scale": "회전 & 스케일", "Origin": "오리진", "New Edge/Face from Vertices": "버텍스에서 새로운 에지/페이스",
               "UVMap": "UV 맵", "Boolean": "불리언", "(Unassigned)": "(할당되지 않음)"}


def shown_paren(pieces) -> str:
    names = MenuNames(SCREEN_NAMES, extra=PAREN_EXTRA)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    return "".join(event.text for event in engine.answer("메시 추가", KOREAN_SCREEN, []) if isinstance(event, Piece))


@pytest.mark.parametrize(
    "answer, expected",
    [
        # 이름에 괄호가 든 이름: 화면 글자만(전: "glTF 바이너리(.glb)(glTF Binary (.glb))", Q35 21자리)
        ("형식은 [[glTF Binary (.glb)]]로 둡니다.", "형식은 glTF 바이너리(.glb)로 둡니다."),
        ("단위가 Metric인지 확인합니다.", "단위가 메트릭(미터법)인지 확인합니다."),  # 화면 글자에만 괄호(전: "메트릭(미터법)(Metric)", Q36)
        ("편집 모드에서 Intersect (Boolean) 기능을 씁니다.", "편집 모드에서 교차 (불리언) 기능을 씁니다."),  # 전: "교차(Intersect) (Boolean)"(Q47)
        ("[[Face > Intersect (Boolean)]] 메뉴를 씁니다.", "페이스(Face) > 교차 (불리언) 메뉴를 씁니다."),
        # 덧말·메뉴 길 괄호 안: 화면 글자만(전: "Ctrl + R(또는 엣지(Edge) > 루프를 잘라내고 슬라이드(Loop Cut and Slide))로", Q05)
        ("Ctrl + R(또는 [[Edge > Loop Cut and Slide]])로 고리를 정합니다.", "Ctrl + R(또는 엣지 > 루프를 잘라내고 슬라이드)로 고리를 정합니다."),
        ("모서리 둥글림([[Bevel]] 모디파이어)은 남아 있습니다.", "모서리 둥글림(베벨 모디파이어)은 남아 있습니다."),  # Q36
        ("Home 키(또는 Frame All)를 누르세요.", "Home 키(또는 모든 프레임)를 누르세요."),  # 맨 영어도 같게
        ("측면(Front, Right) 보기에서 봅니다.", "측면(앞쪽, 오른쪽) 보기에서 봅니다."),  # 괄호 속 영어 목록(전: "측면(Front, 오른쪽(Right))", Q04-1)
        ("측면(Union, Right) 보기에서 봅니다.", "측면(Union, Right) 보기에서 봅니다."),  # 첫 이름이 맨 글에서 영어로 남으면 목록을 둔다(뒤만 바뀐 "측면(Union, 오른쪽)"은 거부한 꼴)
        ("방식(Shift Snap, Right 중 하나)", "방식(Shift Snap, Right 중 하나)"),  # 첫 이름이 키 이름 덩이라 건너뛰어도 같게(사전 전체 문장에서 19곳)
        # 괄호 안에서 바로 앞 한국어가 이미 화면 글자면 영어는 그 풀이라 둔다(이 규칙 첫 판이 "고정(고정, 단축키 P)"·"(폴, 폴이라고"를 만듦, Q28·Q05)
        ("UV 조각을 고정(Pin, 단축키 P)해 둡니다.", "UV 조각을 고정(Pin, 단축키 P)해 둡니다."),
        ("적용 > 회전 & 스케일(Rotation & Scale) 메뉴를 씁니다.", "적용 > 회전 & 스케일(Rotation & Scale) 메뉴를 씁니다."),  # 저장된 답 Q35-1
        ("교차 (불리언)(Intersect (Boolean))을 씁니다.", "교차 (불리언)(Intersect (Boolean))을 씁니다."),  # 이 규칙 첫 판이 "교차 (불리언)(교차 (불리언))"을 만듦(저장된 답 Q47)
        # 괄호 첫머리 영어 뒤에 한국어 풀이가 이어지면 앞말의 영어 풀이라 둔다(첫 판이 "원점(오리진, 물체의 기준점)"으로 영어를 지움, 저장된 답 Q08)
        ("원점(Origin, 물체의 기준점)만 옮겨졌어요.", "원점(Origin, 물체의 기준점)만 옮겨졌어요."),
        ("고리가 끊어지는 곳(폴, Pole이라고 부르는 점)에서 멈춥니다.", "고리가 끊어지는 곳(폴, Pole이라고 부르는 점)에서 멈춥니다."),
        # 괄호 안에서 화면 글자만 보인 이름은 괄호 밖에 처음 나올 때 영어를 붙인다
        ("A(또는 [[Frame All]])를 누르고, 다시 [[Frame All]]을 누릅니다.", "A(또는 모든 프레임)를 누르고, 다시 모든 프레임(Frame All)을 누릅니다."),
        # 한국어 낱말 뒤 괄호에 표시 하나면 표시 없는 같은 꼴과 같게([393], 전: "격자 간격(증가(Increment))", Q06)
        ("격자 간격([[Increment]])으로 맞춰집니다.", "격자 간격 '증가'(Increment)로 맞춰집니다."),
        ("병합 거리([[Merge Distance]])는 0.001입니다.", "병합 거리(Merge Distance)는 0.001입니다."),  # 전: "병합 거리(병합 거리(Merge Distance))"(Q12-1)
        # 문장 끝 말 뒤는 덧말 괄호(첫 판이 "눌러요 '선택한 프레임'(Frame Selected)"를 만듦, Q21)
        ("물체를 고르고 F를 눌러요([[Frame Selected]]).", "물체를 고르고 F를 눌러요(선택한 프레임)."),
        # 뒤에 지우지 않는 괄호가 붙으면 화면 글자만(전: "선택한 프레임(Frame Selected)(단축키 Numpad. 또는 F)", Q21)
        ("[[Frame Selected]](단축키 [[Numpad.]] 또는 F)를 누르세요.", "선택한 프레임(단축키 Numpad. 또는 F)를 누르세요."),
        # 괄호와 상관없이 더 긴 영어 이름의 끝 낱말만 바꾸지 않는다(전: "3ds 최대(Max)", "from 버텍스(Vertices)")
        ("원본이 3ds Max 같은 프로그램이면", "원본이 3ds Max 같은 프로그램이면"),
        # '/'가 든 이름은 통째로(전: "F(New Edge/Face from 버텍스(Vertices))", 이 규칙 첫 판은 영어로 둠, 사용자 "ㅇㅇ 그럼 고치긴 하는데")
        ("F(New Edge/Face from Vertices)는 면을 만듭니다.", "F(버텍스에서 새로운 에지/페이스)는 면을 만듭니다."),
        ("F 키는 New Edge/Face from Vertices 기능입니다.", "F 키는 버텍스에서 새로운 에지/페이스(New Edge/Face from Vertices) 기능입니다."),
        ('좌표는 기본 이름 "UVMap"을 씁니다.', '좌표는 기본 이름 "UVMap"을 씁니다.'),  # UV 맵 기본 이름은 자료 이름이라 둔다(사용자 "ㅇㅇ 그럼 바꾸지 말고")
        ("메뉴의 **거리로 병합**(Merge by Distance)도 같습니다.", "메뉴의 **거리로 병합**(Merge by Distance)도 같습니다."),  # 굵은 글씨 앞말의 풀이는 둔다(첫 판 "(거리로 병합)")
        ("G(Increment)로 옮깁니다.", "G(증가)로 옮깁니다."),  # 앞이 한국어가 아니면 덧말 괄호
        # 앞 낱말과 괄호 속이 합쳐 괄호가 든 이름이면 이름의 일부라 둔다(첫 판 "Intersect(불리언)", 저장된 답 Q47)
        ("설명서의 Intersect(Boolean) 기능입니다.", "설명서의 Intersect(Boolean) 기능입니다."),
        ("Tab(Increment)로 옮깁니다.", "Tab(증가)로 옮깁니다."),
        # 화면 글자가 통째로 괄호면 괄호 속 한국어 받침에 조사를 맞춘다(전: "(할당되지 않음)를", 11-18 괄호 든 이름 넣어 보기)
        ("[[(Unassigned)]]를 고릅니다.", "(할당되지 않음)을 고릅니다."),
        # 한국어 낱말과 괄호 사이 빈칸은 Fable 꼴에서 하나만(전: "형식은  '증가'(Increment)로", 빈칸 둘)
        ("형식은 (Increment)로 둡니다.", "형식은 '증가'(Increment)로 둡니다."),
        ("제목\n(Increment)로 둡니다.", "제목\n(증가)로 둡니다."),  # 줄바꿈 뒤 괄호는 앞말 풀이가 아니라 덧말(첫 판은 "제목 '증가'(Increment)"로 줄을 붙임)  # 여러 글자 키 뒤는 덧말 괄호(영어 낱말이면 늘 두는 판은 "Tab(Increment)")
    ],
)
def test_괄호가_겹치지_않게_바꾼다(answer, expected):
    assert shown_paren((answer,)) == expected
    assert shown_paren(tuple(answer)) == expected  # 한 글자씩 흘려 넣어도 같다


def test_맨_글에서_영어로_남는_이름의_표시는_떼지_않고_괄호_안_화면_글자만():
    # 고정 짝이 기본 문맥 글자와 다른 이름(실제 사전 Strength·Normal·Edge 등)은 맨 글 규칙이 영어로 남긴다([425]). 한국어 뒤 "([[X]])"의
    # 표시를 떼면 "모드(Edit Mode)"처럼 화면 글자를 잃는다(advisor 지적, 지어낸 문장으로 확인: "법선(Normal)", "세기(Strength)")
    names = MenuNames(SCREEN_NAMES, {"Edit Mode": "Operator"}, extra=PAREN_EXTRA)
    for pieces in (("모드([[Edit Mode]])로 들어갑니다.",), tuple("모드([[Edit Mode]])로 들어갑니다.")):
        engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
        text = "".join(event.text for event in engine.answer("메시 추가", KOREAN_SCREEN, []) if isinstance(event, Piece))
        assert text == "모드(편집 모드)로 들어갑니다."


def test_질문에_영어로_쓴_이름은_괄호_안에서_사용자가_쓴_영어로():
    # [311] "Add(추가)" 꼴은 괄호 안에서 겹치므로 사용자가 쓴 영어 하나만, 괄호 밖에 처음 나올 때 영어(한국어)([458], 원문 796글 중 2자리)
    names = MenuNames(SCREEN_NAMES, extra=PAREN_EXTRA)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(("A(또는 [[Frame All]])를 누르고, 다시 [[Frame All]]을 누릅니다.",)), menu_names=names)
    text = "".join(event.text for event in engine.answer("Frame All 어디 있어요?", KOREAN_SCREEN, []) if isinstance(event, Piece))
    assert text == "A(또는 Frame All)를 누르고, 다시 Frame All(모든 프레임)을 누릅니다."



class _ClaudeClient:
    """ClaudeModel에 끼울 가짜 anthropic client: 정해 둔 조각을 낸 뒤 error를 내거나 stop으로 끝난다."""

    def __init__(self, pieces=(), error=None, stop="end_turn"):
        self.pieces, self.error, self.stop = pieces, error, stop
        self.messages = SimpleNamespace(stream=lambda **_: self)
        self.text_stream = self._text()

    def with_options(self, timeout):
        return self

    def _text(self):
        yield from self.pieces
        if self.error:
            raise self.error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=4096), stop_reason=self.stop)


def test_실제_Claude_연결에서_답_도중_바이트가_끊겨_늦으면_시간_초과_문구를_보인다():
    error = httpx2.ReadTimeout("The read operation timed out")
    model = ClaudeModel("claude-haiku-5-5", "k", "medium", client=_ClaudeClient(error=error))
    assert ask(model=model) == [*ANSWERING, Failure(TIMEOUT_MESSAGE, SEARCHED)]


def test_실제_Claude_연결에서_생각이_한도를_다_써_글이_0자면_빈_답_대신_오류_표시():
    model = ClaudeModel("claude-haiku-5-5", "k", "medium", client=_ClaudeClient(stop="max_tokens"))
    assert ask(model=model) == [*ANSWERING, Failure(ERROR_MESSAGE, SEARCHED)]


# 차례 9번(계획 4-1): 환경 설정 안의 탭으로 가는 길인데 여는 길이 없으면 "편집(Edit) > "을 채운다(설명서 "Menu: Edit ‣ Preferences…",
# Q20 채점 사유 "키맵 가는 길에 편집(Edit) > 환경 설정 없이 '환경 설정의 키맵'만 말함 = 부분")
PREFS_EXTRA = {**SCREEN_EXTRA, "Edit": "편집", "Preferences": "환경 설정", "Keymap": "키맵", "Viewport": "뷰포트", "File": "파일",
               "Defaults": "기본값", "Load Factory Preferences": "최초 환경 설정을 불러오기", "Add-on Preferences": "애드온 환경 설정"}


def shown_prefs(pieces, question="메시 추가", state=KOREAN_SCREEN) -> str:
    names = MenuNames(SCREEN_NAMES, extra=PREFS_EXTRA)
    engine = AnswerEngine(CHUNKS, VECTORS, FakeEmbedder(), FakeModel(pieces), menu_names=names)
    return "".join(event.text for event in engine.answer(question, state, []) if isinstance(event, Piece))


@pytest.mark.parametrize(
    "answer, expected",
    [
        # 탭으로 가는 길: 모델이 맨 글로 쓴 꼴, 표시 꼴, 띄어 쓰지 않은 꼴
        ("환경 설정(Preferences)의 키맵을 여세요.", "편집(Edit) > 환경 설정(Preferences)의 키맵을 여세요."),
        ("[[Preferences > Keymap]]에서 찾으세요.", "편집(Edit) > 환경 설정(Preferences) > 키맵(Keymap)에서 찾으세요."),
        ("[[Preferences]]의 [[Keymap]] 탭", "편집(Edit) > 환경 설정(Preferences)의 키맵(Keymap) 탭"),
        ("환경설정의 키맵을 여세요.", "편집(Edit) > 환경설정의 키맵을 여세요."),
        # 이미 길이 있으면 그대로(한 표시, 나눠 쓴 길, 뒤에 길이 나오는 꼴)
        ("[[Edit > Preferences > Keymap]]을 여세요.", "편집(Edit) > 환경 설정(Preferences) > 키맵(Keymap)을 여세요."),
        ("[[Edit]] 메뉴를 열고 [[Preferences]]의 [[Keymap]]을 누릅니다.", "편집(Edit) 메뉴를 열고 환경 설정(Preferences)의 키맵(Keymap)을 누릅니다."),
        ("1. 환경 설정(Preferences)을 엽니다. 메뉴에서 [[Edit > Preferences]]를 누르고", "1. 환경 설정(Preferences)을 엽니다. 메뉴에서 편집(Edit) > 환경 설정을 누르고"),
        # 상태를 설명하는 말은 두고, 처음 언급만 본다
        ("현재 환경 설정에서 버튼이 꺼져 있어요. 다시 켜려면 환경 설정의 뷰포트로.", "현재 환경 설정에서 버튼이 꺼져 있어요. 다시 켜려면 환경 설정의 뷰포트로."),
        ("1. 환경 설정의 키맵을 엽니다.\n2. 환경 설정의 키맵에서 찾습니다.", "1. 편집(Edit) > 환경 설정의 키맵을 엽니다.\n2. 환경 설정의 키맵에서 찾습니다."),
        # 괄호·코드 속, 더 긴 이름의 일부는 건너뛴다
        ("(설명서의 환경 설정 쪽입니다) 그리고 환경 설정의 키맵", "(설명서의 환경 설정 쪽입니다) 그리고 편집(Edit) > 환경 설정의 키맵"),
        ("`환경 설정의 키맵` 다음", "`환경 설정의 키맵` 다음"),
        ("애드온 환경 설정의 키맵", "애드온 환경 설정의 키맵"),  # 넓힌 목록의 더 긴 이름(이 건너뛰기가 없으면 채워진다)
        # 다른 프로그램·운영체제의 환경 설정, ">" 뒤가 탭 이름이 아닌 꼴
        ("macOS 시스템 환경 설정 > 키보드에서 단축키를 끄세요.", "macOS 시스템 환경 설정 > 키보드에서 단축키를 끄세요."),
        ("윈도우 환경 설정 > 키맵", "윈도우 환경 설정 > 키맵"),
        ("환경 설정 > 다른 곳에서 바꿉니다.", "환경 설정 > 다른 곳에서 바꿉니다."),
        # 표·제목 줄은 둔다
        ("| 환경 설정의 키맵 | 값 |", "| 환경 설정의 키맵 | 값 |"),
        ("## 환경 설정의 키맵", "## 환경 설정의 키맵"),
        # 붙잡은 글 바로 뒤 표시도 붙잡은 글을 앞 글로 본다(괄호 안 이름은 화면 글자만, [458])
        ("현재 환경 설정에서 꺼져 있어요 (예: [[Keymap]] 탭)", "현재 환경 설정에서 꺼져 있어요 (예: 키맵 탭)"),
        ("환경 설정 메뉴에서 [[Render]] 탭", "환경 설정 메뉴에서 Render 탭"),  # HEAD와 같다(이 지어낸 사전의 Render는 짝을 안 고른 이름)
        # 붙잡는 동안 표시 뒤 단축키도 글 순서대로(앞 문장 끝에 붙지 않는다, [423])
        ("환경 설정의 키맵을 여세요. [[Face]](Alt-F)를 누르면 면이 생겨요.",
         "편집(Edit) > 환경 설정의 키맵을 여세요. 페이스(Face)를 누르면 면이 생겨요. 단축키는 Alt-F입니다."),
        ("현재 환경 설정에서 꺼져 있어요. [[Face]](Alt-F)를 누르면 면이 생겨요.",
         "현재 환경 설정에서 꺼져 있어요. 페이스(Face)를 누르면 면이 생겨요. 단축키는 Alt-F입니다."),
        # 넣은 글은 앞에 "(Edit)"이 보였는지로만 괄호를 정한다(뒤 글은 HEAD와 같게 둔다. 그래서 뒤에 "편집(Edit)"이 또 나올 수 있다)
        ("환경 설정의 키맵에서 고친 뒤 [[Edit]] 메뉴를 보세요.", "편집(Edit) > 환경 설정의 키맵에서 고친 뒤 편집(Edit) 메뉴를 보세요."),
        ("[[File > Defaults > Load Factory Preferences]]를 누른 뒤", "파일(File) > 기본값(Defaults) > '최초 환경 설정을 불러오기'(Load Factory Preferences) 항목을 누른 뒤"),  # 따옴표·'항목'은 [356] 꼴
        # 앞에 편집이 이미 나왔으면 영어 괄호는 처음 한 번만([353])
        ("[[Edit]] 메뉴를 봅니다. 그다음 줄에서 한참 다른 이야기를 한 뒤 환경 설정의 키맵", "편집(Edit) 메뉴를 봅니다. 그다음 줄에서 한참 다른 이야기를 한 뒤 편집 > 환경 설정의 키맵"),
    ],
)
def test_환경_설정_탭으로_가는_길에_여는_길이_없으면_편집을_채운다(answer, expected):
    assert shown_prefs((answer,)) == expected


def test_환경_설정_채우기는_질문이_영어면_괄호_속이라_두고_영어_화면은_손대지_않는다():
    assert shown_prefs(("[[Preferences]]의 [[Keymap]]",), question="Preferences 어디") == "Preferences(환경 설정)의 키맵(Keymap)"
    assert shown_prefs(("[[Preferences]]의 [[Keymap]]",), state=STATE) == "Preferences의 Keymap"


def test_환경_설정_채우기는_조각을_어떻게_나눠_흘려도_같고_끊겨도_붙잡은_글을_낸다():
    import random

    from blender_tutor.answer_engine import _MenuMarks

    text = "단축키를 보려면 환경 설정(Preferences)의 키맵을 여세요. 다시 [[Preferences]]에서.\n현재 환경 설정에서 꺼짐\n그리고 환경 설정의 키맵에서 다시 봅니다\n환경 설정에서 [[Face]](Alt-F)를 누르면 돼요."
    whole = shown_prefs((text,))
    assert whole.startswith("단축키를 보려면 편집(Edit) > 환경 설정(Preferences)의") and whole.count("편집") == 1  # 처음 언급만
    rng = random.Random(9)
    for _ in range(300):
        pieces, i = [], 0
        while i < len(text):
            k = rng.randint(1, 12)
            pieces.append(text[i : i + k])
            i += k
        assert shown_prefs(tuple(pieces)) == whole, pieces
    marks = _MenuMarks(MenuNames(SCREEN_NAMES, extra=PREFS_EXTRA))
    assert marks.feed("그럼 환경 설정의 키") + marks.finish(cut=True) == "그럼 환경 설정의 키"


def test_messages_put_errata_line_below_its_chunk():
    # 바로잡기 줄은 그 청크 글 바로 아래, 다음 청크 앞에 들어간다(HISTORY [690])
    fbx = Chunk(
        "files/import_export/fbx_legacy", "id15", "files", "files/import_export", "FBX (Legacy)", ("Export",),
        "Scale the exported data by this value. 10 is the default because this fits best.",
    )
    content = _messages("크기가 작아요", STATE, (), [[fbx, SAVE]], [], None)[-1]["content"]
    assert f"{fbx.text}\n\n위 글의 Scale 기본값 10은 1.0이다.\n\n{SAVE.text}" in content
