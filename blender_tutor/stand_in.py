"""임시 엔진 부품: 진짜 임베딩(티켓 31)·답변 모델(티켓 33)이 붙기 전에 도우미 창을 돌려 보는 무료 가짜(티켓 26, 사용자 결정 2026-10-22).

- WordEmbedder: 글의 낱말을 세어 숫자 목록으로 바꾼다. 영어 설명서와 한국어 질문은 겹치는 낱말이 거의 없어 검색이 자주 빗나간다.
- StandInModel: 설명을 만들지 않고 정해 둔 글을 흘린다. 첫 글자 전에 쉬어 진짜처럼 기다리게 한다(창이 기다리는 동안 Blender가 멈추지 않는지 보려고).
창 동작(스트리밍·근거 링크·오류 문구)을 보는 데만 쓴다. 답·검색의 질은 진짜 모델로 잰다.
build_engine은 임베딩을 고른다: 낱말 세기(stand_in) 또는 진짜 임베딩(미리 만든 설명서 벡터 + 질문마다 OpenAI, 티켓 31).
답변 모델이 진짜로 바뀌면(티켓 33) 엔진 만들기는 이 파일 밖으로 옮기고 이 파일은 archive/로 간다.
"""

import re
import time
import zlib
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from blender_tutor import manual_vectors
from blender_tutor.answer_engine import AnswerEngine, AnswerModel, Embedder, Settings
from blender_tutor.beginner_scope import openai_key
from blender_tutor.paths import PROJECT
from blender_tutor.manual_chunks import load_chunks
from blender_tutor.menu_names import MenuNames
from blender_tutor.progress import Course

DIMENSIONS = 512  # 낱말을 나눠 담을 칸 수
NAME = "stand_in"  # 시간 기록에 남기는 엔진 이름(진짜 엔진의 줄과 가르려고)
EMBEDDINGS = (NAME, manual_vectors.MODEL)  # 고를 수 있는 임베딩: 낱말 세기(무료) / 진짜(질문마다 돈이 아주 조금 든다)

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
    data_dir: Path,
    model: AnswerModel | None = None,
    menu_choices: Path = PROJECT / "menu_choices.json",
    menu_titles: Path = PROJECT / "menu_titles.json",
    courses: Sequence[Course] = (),
    settings: Settings = Settings(),
    embedding: str = NAME,
) -> AnswerEngine:
    """data_dir(보통 data/)의 청크·메뉴 이름 사전으로 임시 엔진을 만든다. 청크 파일이 없으면 FileNotFoundError.

    메뉴 이름 사전이 없으면 메뉴 이름을 영어 그대로 보인다. courses는 연습 과정 밖 질문에 권할 연습 과정이고,
    벡터는 이름 + 한 줄 설명을 낱말 세기로 만든다. 정해진 것은 이름 + 한 줄 설명 + 비슷한 말이지만(티켓 14·31),
    Course에 비슷한 말 칸이 아직 없어 임시 엔진은 둘만 쓴다(칸은 진짜 벡터를 만드는 티켓 31에서 더한다).
    settings는 평가 프로그램이 바꿔 넘기는 엔진 설정이다(티켓 29).
    embedding이 진짜 임베딩이면 data_dir/vectors/의 설명서 벡터를 읽고(없으면 FileNotFoundError, 청크와 다르면 ValueError)
    질문·연습 과정은 OpenAI로 임베딩한다(키가 없으면 SystemExit). 엔진 이름은 "임베딩+답변"(예: text-embedding-3-large+stand_in).
    """
    chunks = load_chunks(data_dir / "chunks" / "manual_chunks.jsonl")
    embedder: Embedder
    if embedding == NAME:
        embedder = WordEmbedder()
        vectors = embedder.embed([chunk.text for chunk in chunks], timeout=0)
    elif embedding in EMBEDDINGS:
        vectors = manual_vectors.load(manual_vectors.path_for(embedding, data_dir), chunks)
        embedder = manual_vectors.OpenAIEmbedder(embedding, openai_key())
    else:
        raise ValueError(f"모르는 임베딩 {embedding} (고를 수 있는 것: {', '.join(EMBEDDINGS)})")
    names_path = data_dir / "menu_names" / "menu_names.json"
    names = (
        MenuNames.load(names_path, MenuNames.load_choices(menu_choices), MenuNames.load_titles(menu_titles))
        if names_path.exists()
        else None
    )
    # 진짜 임베딩이면 켤 때마다 연습 과정 몇 개를 한 번 부른다(미리 만들어 두기는 티켓 31의 연습 과정 임베딩에서)
    texts = [f"{course.name} {course.summary}" for course in courses]
    course_vectors = embedder.embed(texts, settings.timeout) if texts else []
    name = NAME if embedding == NAME else f"{embedding}+{NAME}"
    return AnswerEngine(
        chunks, vectors, embedder, model or StandInModel(), settings=settings,
        menu_names=names, courses=courses, course_vectors=course_vectors, name=name,
    )
