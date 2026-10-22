"""임시 엔진 부품(티켓 26, 진짜 모델은 티켓 31·33): 낱말 세기 임베딩과 쉬었다 흘리는 가짜 답변 모델이 답 엔진에 맞게 끼워지나 본다."""

import numpy as np

from blender_tutor.answer_engine import Done, Piece
from blender_tutor.manual_chunks import Chunk, save_chunks
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
