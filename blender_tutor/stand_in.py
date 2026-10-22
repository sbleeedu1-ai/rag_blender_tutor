"""임시 엔진 부품: 진짜 임베딩(티켓 31)·답변 모델(티켓 33)이 붙기 전에 도우미 창을 돌려 보는 무료 가짜(티켓 26, 사용자 결정 2026-10-22).

- WordEmbedder: 글의 낱말을 세어 숫자 목록으로 바꾼다. 영어 설명서와 한국어 질문은 겹치는 낱말이 거의 없어 검색이 자주 빗나간다.
- StandInModel: 설명을 만들지 않고 정해 둔 글을 흘린다. 첫 글자 전에 쉬어 진짜처럼 기다리게 한다(창이 기다리는 동안 Blender가 멈추지 않는지 보려고).
창 동작(스트리밍·근거 링크·오류 문구)을 보는 데만 쓴다. 답·검색의 질은 진짜 모델로 잰다.
"""

import re
import time
import zlib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from blender_tutor.answer_engine import AnswerEngine, AnswerModel
from blender_tutor.manual_chunks import load_chunks
from blender_tutor.menu_names import MenuNames

PROJECT = Path(__file__).resolve().parent.parent
DIMENSIONS = 512  # 낱말을 나눠 담을 칸 수

STAND_IN_ANSWER = (
    "(임시 답) 아직 진짜 답변 모델을 붙이지 않아 설명은 만들지 못해요. "
    "아래 근거는 이 질문으로 실제 설명서를 검색해 찾은 소제목이에요. "
    "메뉴 이름은 [[Add > Mesh]]처럼 화면 언어에 맞춰 보여요. "
    "진짜 답은 티켓 33에서 붙어요."
)


class WordEmbedder:
    """낱말마다 칸 하나를 정해(crc32, 켤 때마다 같음) 그 칸의 수를 센다. 대소문자는 가리지 않는다."""

    def embed(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * DIMENSIONS
            for word in re.findall(r"\w+", text.lower()):
                vector[zlib.crc32(word.encode("utf-8")) % DIMENSIONS] += 1.0
            vectors.append(vector)
        return vectors


class StandInModel:
    """STAND_IN_ANSWER를 몇 글자씩 흘린다. 첫 조각 전에 first_delay초, 조각 사이에 piece_delay초 쉰다."""

    def __init__(self, first_delay: float = 1.5, piece_delay: float = 0.03, sleep: Callable[[float], None] = time.sleep):
        self._first_delay = first_delay
        self._piece_delay = piece_delay
        self._sleep = sleep

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterator[str]:
        self._sleep(self._first_delay)
        for start in range(0, len(STAND_IN_ANSWER), 4):
            if start:
                self._sleep(self._piece_delay)
            yield STAND_IN_ANSWER[start : start + 4]


def build_engine(
    data_dir: Path, model: AnswerModel | None = None, menu_choices: Path = PROJECT / "menu_choices.json"
) -> AnswerEngine:
    """data_dir(보통 data/)의 청크·메뉴 이름 사전으로 임시 엔진을 만든다. 청크 파일이 없으면 FileNotFoundError.

    메뉴 이름 사전이 없으면 메뉴 이름을 영어 그대로 보인다.
    """
    chunks = load_chunks(data_dir / "chunks" / "manual_chunks.jsonl")
    embedder = WordEmbedder()
    names_path = data_dir / "menu_names" / "menu_names.json"
    names = MenuNames.load(names_path, MenuNames.load_choices(menu_choices)) if names_path.exists() else None
    vectors = embedder.embed([chunk.text for chunk in chunks], timeout=0)
    return AnswerEngine(chunks, vectors, embedder, model or StandInModel(), menu_names=names)
