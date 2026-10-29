"""임시 엔진 부품(티켓 26, 진짜 모델은 티켓 31·33): 낱말 세기 임베딩과 쉬었다 흘리는 가짜 답변 모델이 답 엔진에 맞게 끼워지나 본다."""

import numpy as np
import pytest

from blender_tutor import manual_vectors, stand_in
from blender_tutor.answer_engine import Done, Piece
from blender_tutor.manual_chunks import Chunk, save_chunks
from blender_tutor.progress import Course, Step
from blender_tutor.stand_in import STAND_IN_ANSWER, StandInModel, WordEmbedder, build_engine
from blender_tutor.work_state import WorkState
from tests.examples import EDITING


def similarity(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_낱말이_많이_겹치는_글일수록_가까운_벡터가_된다():
    question, bevel, array = WordEmbedder().embed(["bevel width", "Bevel Modifier width segments", "Array count offset"], timeout=1)
    assert similarity(question, bevel) > similarity(question, array)
    assert len(question) == len(array)


def test_같은_글은_켤_때마다_같은_벡터():
    # 파이썬 기본 hash는 켤 때마다 달라 쓰지 않는다
    assert WordEmbedder().embed(["Bevel"], 1)[0][:] == WordEmbedder().embed(["bevel"], 1)[0][:]


def test_가짜_답변_모델은_쉬었다가_조각으로_흘려_보낸다():
    slept = []
    model = StandInModel(first_delay=1.5, piece_delay=0.03, sleep=slept.append)
    pieces = list(model.stream([{"role": "user", "content": "질문"}], timeout=10))
    assert "".join(pieces) == STAND_IN_ANSWER
    assert len(pieces) > 1
    assert slept[0] == 1.5 and set(slept[1:]) == {0.03}


def test_청크_파일로_엔진을_만들면_질문에_맞는_근거가_붙는다(tmp_path):
    chunks = [
        Chunk("modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate", "Bevel Modifier", ("Options",), "Width sets the size of the chamfer."),
        Chunk("modeling/modifiers/generate/array", "introduction", "modeling", "modeling/modifiers/generate", "Array Modifier", ("Introduction",), "Array copies the object in a row."),
    ]
    save_chunks(chunks, tmp_path / "chunks" / "manual_chunks.jsonl")
    engine = build_engine(tmp_path, model=StandInModel(0, 0, sleep=lambda _: None))  # 메뉴 이름 사전 없음: 영어 그대로
    events = list(engine.answer("bevel width", WorkState.from_json(EDITING), []))
    assert "".join(event.text for event in events if isinstance(event, Piece)) == STAND_IN_ANSWER.replace("[[Add > Mesh]]", "Add > Mesh")
    assert events[-1].sources[0].path == "Bevel Modifier > Options"
    assert isinstance(events[-1], Done)


def test_연습_과정을_넘기면_연습_과정_밖_질문에_비슷한_연습_과정이_붙는다(tmp_path):
    chunks = [Chunk("modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate", "Bevel Modifier", ("Options",), "Width sets the size of the chamfer.")]
    save_chunks(chunks, tmp_path / "chunks" / "manual_chunks.jsonl")
    sent = []

    class Recording(StandInModel):
        def stream(self, messages, timeout):
            sent.append(messages)
            yield "답"

    sword = Course("sword", "단순한 검", (Step("view", "화면 돌려 보기"),), "기본 정육면체로 검을 만든다.")
    engine = build_engine(tmp_path, model=Recording(), courses=[sword])
    list(engine.answer("활을 만들고 싶어요", WorkState.from_json(EDITING), []))
    assert "단순한 검: 기본 정육면체로 검을 만든다." in str(sent[0])


class QuestionEmbedder:
    """진짜 OpenAI 임베딩 대신: 받은 글을 적어 두고 [1, 0]을 돌려준다(BEVEL 쪽 벡터)."""

    def __init__(self, model, key):
        self.texts = []

    def embed(self, texts, timeout):
        self.texts += texts
        return [[1.0, 0.0] for _ in texts]


def test_진짜_임베딩을_고르면_만들어_둔_설명서_벡터를_읽고_질문만_임베딩한다(tmp_path, monkeypatch):
    bevel = Chunk("modeling/bevel", "options", "modeling", "modeling", "Bevel", ("Options",), "Width sets the size.")
    array = Chunk("modeling/array", "intro", "modeling", "modeling", "Array", ("Introduction",), "Array copies the object.")
    save_chunks([array, bevel], tmp_path / "chunks" / "manual_chunks.jsonl")

    class Stored:  # 미리 만든 벡터 파일: array는 [0, 1], bevel은 [1, 0]
        def embed(self, texts, timeout):
            return [[0.0, 1.0], [1.0, 0.0]]

    manual_vectors.build([array, bevel], Stored(), manual_vectors.path_for("text-embedding-3-large", tmp_path), "fake")
    made = []
    monkeypatch.setattr(stand_in, "openai_key", lambda: "가짜 키")
    monkeypatch.setattr(manual_vectors, "OpenAIEmbedder", lambda model, key: made.append(QuestionEmbedder(model, key)) or made[-1])
    engine = build_engine(tmp_path, model=StandInModel(0, 0, sleep=lambda _: None), embedding="text-embedding-3-large")
    events = list(engine.answer("베벨 너비", WorkState.from_json(EDITING), []))
    assert events[-1].sources[0].path == "Bevel > Options"  # 낱말이 하나도 안 겹쳐도 벡터로 찾는다
    assert len(made[0].texts) == 1 and made[0].texts[0].startswith("베벨 너비")  # 검색어 하나만, 설명서는 다시 임베딩하지 않는다
    assert engine.name == "text-embedding-3-large+stand_in"


def test_진짜_임베딩인데_설명서_벡터_파일이_없으면_FileNotFoundError(tmp_path):
    save_chunks([Chunk("modeling/bevel", "options", "modeling", "modeling", "Bevel", ("Options",), "Width.")], tmp_path / "chunks" / "manual_chunks.jsonl")
    with pytest.raises(FileNotFoundError):  # 도우미 창은 이것을 '설명서 자료가 없어요'로 보인다
        build_engine(tmp_path, embedding="text-embedding-3-large")


def test_연습_과정은_이름_한_줄_설명_비슷한_말을_합친_글로_엔진을_만들_때_한_번_임베딩한다(tmp_path, monkeypatch):
    bevel = Chunk("modeling/bevel", "options", "modeling", "modeling", "Bevel", ("Options",), "Width sets the size.")
    save_chunks([bevel], tmp_path / "chunks" / "manual_chunks.jsonl")

    class Stored:
        def embed(self, texts, timeout):
            return [[1.0, 0.0]]

    manual_vectors.build([bevel], Stored(), manual_vectors.path_for("text-embedding-3-large", tmp_path), "fake")
    made = []
    monkeypatch.setattr(stand_in, "openai_key", lambda: "가짜 키")
    monkeypatch.setattr(manual_vectors, "OpenAIEmbedder", lambda model, key: made.append(QuestionEmbedder(model, key)) or made[-1])
    sword = Course("sword", "단순한 검", (Step("view", "화면 돌려 보기"),), "정육면체로 검을 만든다.", ("장검", "blade"))
    build_engine(tmp_path, courses=[sword], embedding="text-embedding-3-large")
    assert made[0].texts == ["단순한 검 정육면체로 검을 만든다. 장검 blade"]
