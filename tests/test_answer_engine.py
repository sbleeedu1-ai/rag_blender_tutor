"""답 엔진(시험 경계 ①: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

가짜 임베딩·가짜 답변 모델을 끼우고, 직접 지어낸 작은 청크 묶음(설명서 원문 아님)으로 시험한다.
질문을 넣고 나온 답 조각·근거 목록·검색 결과·오류 표시와, 모델이 받은 것만 본다.
"""

import pytest

from blender_tutor.answer_engine import AnswerEngine, Done, Failure, Piece, Settings, Source
from blender_tutor.manual_chunks import Chunk, Example, MediaKind

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

STATE = {"mode": "OBJECT", "active_object": {"name": "Cube", "type": "MESH", "modifiers": []}}
TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."


class FakeEmbedder:
    """어떤 질문이든 정해 둔 벡터 하나를 돌려준다. 받은 글과 시간 한도를 적어 둔다."""

    def __init__(self, vector=TOWARD_BEVEL, error: Exception | None = None):
        self.vector = vector
        self.error = error
        self.calls: list[str] = []
        self.timeouts: list[float] = []

    def embed(self, text: str, timeout: float) -> list[float]:
        self.calls.append(text)
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return self.vector


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


def ask(question="베벨", *, embedder=None, model=None, settings=Settings(), recent=()) -> list:
    """답 엔진을 새로 만들어 질문 하나를 묻고, 나온 것을 모두 모은다."""
    engine = AnswerEngine(CHUNKS, VECTORS, embedder or FakeEmbedder(), model or FakeModel(), settings)
    return list(engine.answer(question, STATE, list(recent)))


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


# 모델에 넘기는 것


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
