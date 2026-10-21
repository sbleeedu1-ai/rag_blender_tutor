"""답 엔진(시험 경계 ①: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

가짜 임베딩·가짜 답변 모델을 끼우고, 직접 지어낸 작은 청크 묶음(설명서 원문 아님)으로 시험한다.
질문을 넣고 나온 답 조각·근거 목록·검색 결과·오류 표시와, 모델이 받은 것만 본다.
"""

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
SELECT = Chunk(
    "modeling/meshes/selecting/introduction", "select-mode", "modeling", "modeling/meshes/selecting",
    "Introduction", ("Select Mode",), "Vertex, edge and face select modes.",
)
SAVE = Chunk(
    "files/blend/save", "save", "files", "files/blend",
    "Saving", ("Save",), "Save writes the blend file.",
)
CHUNKS = [BEVEL, BEVEL_MORE, ARRAY, EXPORT, SELECT, SAVE]
VECTORS = [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.1, 1.0, 0.0], [0.0, 0.1, 1.0], [0.0, 0.0, 0.1], [0.05, 0.0, 0.02]]

STATE = {"mode": "OBJECT", "active_object": {"name": "Cube", "type": "MESH", "modifiers": []}}


class FakeEmbedder:
    """질문 글마다 정해 둔 벡터를 돌려준다. 부른 횟수와 받은 시간 한도를 센다."""

    def __init__(self, vectors: dict[str, list[float]], error: Exception | None = None):
        self.vectors = vectors
        self.error = error
        self.calls: list[str] = []
        self.timeouts: list[float] = []

    def embed(self, text: str, timeout: float) -> list[float]:
        self.calls.append(text)
        self.timeouts.append(timeout)
        if self.error:
            raise self.error
        return self.vectors[text]


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


def engine(embedder, model, settings=Settings()) -> AnswerEngine:
    return AnswerEngine(CHUNKS, VECTORS, embedder, model, settings)


def ask(engine: AnswerEngine, question: str, recent=()) -> list:
    return list(engine.answer(question, STATE, list(recent)))


def found(events) -> list[Chunk]:
    return list(events[-1].results)


def test_답_조각이_나오는_대로_흐르고_끝에_근거가_붙는다():
    events = ask(engine(FakeEmbedder({"베벨 폭": [1.0, 0.0, 0.0]}), FakeModel()), "베벨 폭")
    assert events[:3] == [Piece("베벨 "), Piece("모디파이어의 "), Piece("Width를 바꾸세요.")]
    assert isinstance(events[3], Done) and len(events) == 4


def test_근거에_소제목_경로_주소_그림_영상_표시가_있다():
    question = "배열 내보내기 베벨"
    embedder = FakeEmbedder({question: [1.0, 1.0, 1.0]})
    sources = {source.url: source for source in ask(engine(embedder, FakeModel()), question)[-1].sources}
    assert sources["https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options"] == Source(
        "Bevel Modifier > Options",
        "https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options",
        has_image=True, has_video=False, videos=(),
    )
    # 뒤따르는 영상 예시도 '영상 있음'으로 세고 그 링크를 함께 준다
    array = sources["https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/array.html#introduction"]
    assert (array.has_video, array.videos) == (True, ("https://example.org/array.mp4",))
    export = sources["https://docs.blender.org/manual/en/5.2/addons/import_export/scene_gltf2.html#export"]
    assert (export.path, export.has_image, export.videos) == ("glTF 2.0 > Export", False, ("https://example.org/gltf.mp4",))


def test_같은_소제목을_나눈_청크는_근거에_한_번만_나온다():
    events = ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel()), "베벨")
    urls = [source.url for source in events[-1].sources]
    assert urls.count("https://docs.blender.org/manual/en/5.2/modeling/modifiers/generate/bevel.html#options") == 1
    assert found(events)[:2] == [BEVEL, BEVEL_MORE]  # 검색 결과(평가용)에는 두 조각이 다 있다


def test_검색_결과는_설정한_개수만큼():
    events = ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel(), Settings(top_k=3)), "베벨")
    assert len(found(events)) == 3
    assert len(ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel()), "베벨")[-1].results) == 6


def test_겹치는_낱말이_없으면_뜻_검색_순서_그대로():
    # 한국어 질문은 영어 청크와 겹치는 낱말이 없다. 낱말 점수 0인 청크가 아무 순서로 끼어들면 안 된다
    events = ask(engine(FakeEmbedder({"배열 복사": [0.0, 1.0, 0.0]}), FakeModel(), Settings(top_k=3)), "배열 복사")
    assert found(events) == [ARRAY, BEVEL_MORE, EXPORT]


def test_뜻과_낱말이_모두_가까운_청크가_한쪽만_가까운_청크보다_위로_온다():
    # 뜻으로는 BEVEL이 1등이고 SAVE는 3등, 낱말("save file")로는 SAVE가 1등이다.
    # SAVE는 두 순위표에 다 높이 있어 뜻 한쪽에서만 1등인 BEVEL보다 위로 온다
    question = "save file"
    events = ask(engine(FakeEmbedder({question: [1.0, 0.0, 0.0]}), FakeModel(), Settings(top_k=2)), question)
    assert found(events)[0] == SAVE


def test_낱말_검색을_끄면_뜻_검색_순서만_쓴다():
    question = "save file"
    off = Settings(top_k=2, use_bm25=False)
    events = ask(engine(FakeEmbedder({question: [1.0, 0.0, 0.0]}), FakeModel(), off), question)
    assert found(events) == [BEVEL, BEVEL_MORE]


def test_질문_하나에_임베딩_한_번_답변_한_번만_부른다():
    embedder, model = FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel()
    ask(engine(embedder, model), "베벨", recent=[("배열은요?", "배열 모디파이어를 쓰세요.")])
    assert (len(embedder.calls), len(model.calls)) == (1, 1)


def test_모델에_검색_청크_글과_작업_상태와_질문을_넘긴다():
    model = FakeModel()
    ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), model, Settings(top_k=1)), "베벨")
    messages = model.calls[0]
    assert messages[0]["role"] == "system"
    last = messages[-1]["content"]
    assert BEVEL.text in last and ARRAY.text not in last
    assert '"mode": "OBJECT"' in last and "Cube" in last
    assert last.rstrip().endswith("베벨")


def test_최근_대화를_넘기고_지난_질문은_기억하지_않는다():
    model = FakeModel()
    answer_engine = engine(FakeEmbedder({"배열은요?": [0.0, 1.0, 0.0], "그거 어떻게 해요?": [0.0, 1.0, 0.0]}), model)
    ask(answer_engine, "배열은요?")
    ask(answer_engine, "그거 어떻게 해요?", recent=[("배열은요?", "배열 모디파이어를 쓰세요.")])
    ask(answer_engine, "그거 어떻게 해요?")  # 최근 대화를 안 주면 앞 질문을 모른다
    roles = [[m["role"] for m in messages] for messages in model.calls]
    assert roles == [["system", "user"], ["system", "user", "assistant", "user"], ["system", "user"]]
    assert model.calls[1][1:3] == [
        {"role": "user", "content": "배열은요?"},
        {"role": "assistant", "content": "배열 모디파이어를 쓰세요."},
    ]
    assert "배열은요?" not in str(model.calls[2])


def test_응답_없음_한도를_모델과_임베딩에_넘긴다():
    embedder, model = FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel()
    ask(engine(embedder, model), "베벨")
    assert (embedder.timeouts, model.timeouts) == ([10.0], [10.0])  # 기본 10초(사용자 결정, 2026-10-21)


def test_답변_모델이_시간_초과면_짧은_오류_표시():
    events = ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel(pieces=(), error=TimeoutError())), "베벨")
    assert events == [Failure("답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요.")]


def test_답_도중_오류가_나면_나온_조각_뒤에_오류_표시가_오고_근거는_없다():
    events = ask(engine(FakeEmbedder({"베벨": [1.0, 0.0, 0.0]}), FakeModel(pieces=("베벨 ",), error=ConnectionError("끊김"))), "베벨")
    assert events == [Piece("베벨 "), Failure("답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요.")]


def test_임베딩이_실패해도_오류_표시를_내고_답변_모델은_부르지_않는다():
    model = FakeModel()
    events = ask(engine(FakeEmbedder({}, error=TimeoutError()), model), "베벨")
    assert events == [Failure("답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요.")]
    assert model.calls == []
