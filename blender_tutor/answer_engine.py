"""답 엔진: 질문 + 작업 상태 → 설명서 검색 → 답 글 흐름 + 근거 목록.

시험 경계 ①(.scratch/mvp-roundtrip/spec.md의 "답 엔진"과 Testing Decisions 참고).
Blender·창 없이 부를 수 있고, 아무것도 기억하지 않는다(최근 대화는 부를 때마다 입력으로 받음, 티켓 09).
답변 모델·임베딩은 밖에서 받는다. 테스트는 가짜를 끼우고, 실제 모델을 끼우는 일은 유료 티켓에서 한다.
"""

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from blender_tutor.manual_chunks import Chunk, MediaKind

RRF_K = 60  # RRF 합치기 상수. 순위 r인 청크는 1 / (RRF_K + r)점을 받는다(널리 쓰는 값)
RRF_DEPTH = 50  # 뜻 검색·낱말 검색 각각 상위 몇 개까지 합치기에 넣나

TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."

INSTRUCTIONS = """너는 Blender 5.2를 처음 쓰는 사람을 돕는 도우미다.
- 쉬운 한국어로 짧게 답하고, 처음 나오는 용어는 한 줄로 풀어 준다.
- Blender 5.2 기준으로 답한다. 아래 '설명서 내용'에 있는 것만 근거로 쓴다.
- 설명서 내용에 답이 없으면 지어내지 말고 "설명서에 없어요"라고 말한 뒤 가장 가까운 내용을 권한다.
- 그림은 캡션 글만 쓴다. [그림] 자리가 중요해 보이면 "설명서 그림을 함께 보세요"라고 안내한다.
- '작업 상태'는 사용자의 Blender 화면에서 지금 읽은 값이다. 사용자가 설명하지 않아도 이것을 보고 답한다."""


class Embedder(Protocol):
    """글 하나를 벡터로 바꾼다. timeout초 동안 응답이 없으면 TimeoutError를 낸다."""

    def embed(self, text: str, timeout: float) -> Sequence[float]: ...


class AnswerModel(Protocol):
    """대화 글(역할 system·user·assistant)을 받아 답 글 조각을 나오는 대로 돌려준다.

    timeout초 동안 다음 조각이 오지 않으면 TimeoutError를 낸다(답 전체 시간 한도가 아님).
    """

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterable[str]: ...


@dataclass(frozen=True)
class Settings:
    """답 엔진 설정. 평가 때 바꿔 같은 문항을 다시 잰다."""

    top_k: int = 6  # 답변 모델에 넘길 검색 결과 수(명세 6-8개, 22번의 먼저 볼 소제목이 이 위에 더 붙는다)
    timeout: float = 10.0  # 모델이 이만큼(초) 아무것도 보내지 않으면 멈춘 것으로 본다(사용자 결정, 2026-10-21)
    use_bm25: bool = True  # 낱말 검색(BM25)을 섞을지. 끄면 뜻 검색만(평가에서 견줄 스위치)


@dataclass(frozen=True)
class Piece:
    """답 글 조각 하나. 나오는 대로 창에 이어 붙인다."""

    text: str


@dataclass(frozen=True)
class Source:
    """근거 하나: 설명서 소제목 하나."""

    path: str  # 쪽 제목 > 소제목 경로(예: Bevel Modifier > Options)
    url: str  # /en/5.2/<경로>.html#<앵커>
    has_image: bool  # 그림 있음
    has_video: bool  # 영상 있음
    videos: tuple[str, ...]  # 영상 링크


@dataclass(frozen=True)
class Done:
    """답이 끝났다는 알림. 근거 목록과 검색 결과(평가용, 순위대로)를 함께 준다."""

    sources: tuple[Source, ...]
    results: tuple[Chunk, ...]


@dataclass(frozen=True)
class Failure:
    """오류·시간 초과 표시. 이것이 오면 답은 거기서 끝나고 근거는 없다.

    검색이 끝난 뒤 실패했으면 검색 결과를 함께 준다(평가에서 시간 초과 문항의 검색 적중도 세려고).
    """

    message: str
    results: tuple[Chunk, ...] = ()


Event = Piece | Done | Failure


class AnswerEngine:
    """청크와 그 벡터(미리 만들어 둔 것)를 들고, 질문마다 임베딩 1번 + 답변 1번을 부른다."""

    def __init__(
        self,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        embedder: Embedder,
        model: AnswerModel,
        settings: Settings = Settings(),
    ):
        self._chunks = list(chunks)
        self._vectors = _normalized(np.asarray(vectors, dtype=np.float32))
        self._bm25 = BM25Okapi([_words(chunk.text) for chunk in self._chunks])
        self._embedder = embedder
        self._model = model
        self._settings = settings

    def answer(self, question: str, state: dict, recent: Sequence[tuple[str, str]]) -> Iterator[Event]:
        """질문에 답한다. state는 애드온이 보낸 작업 상태 JSON, recent는 최근 대화 (질문, 답) 쌍 목록."""
        # 바깥 서비스(임베딩·답변 모델)를 부르는 두 곳만 오류 표시로 바꾼다.
        # 검색·글 만들기 같은 우리 코드의 오류는 그대로 올려 보내 버그가 "잠시 뒤 다시"에 숨지 않게 한다
        try:
            vector = self._embedder.embed(question, self._settings.timeout)
            if not np.any(vector):  # 모두 0이면 뜻 점수가 다 같아 청크 저장 순서가 그대로 순위가 된다. 잘못된 응답으로 본다
                raise ValueError("임베딩이 모두 0인 벡터를 돌려줌")
        except Exception as error:
            yield _failure(error, [])
            return
        results = self._search(question, vector)
        messages = _messages(question, state, recent, results)
        try:
            for text in self._model.stream(messages, self._settings.timeout):
                yield Piece(text)
        except Exception as error:
            yield _failure(error, results)
            return
        yield Done(_sources(results), tuple(results))

    def _search(self, query: str, vector: Sequence[float]) -> list[Chunk]:
        """뜻 검색과 낱말 검색 순위를 RRF로 합쳐 상위 top_k개를 고른다."""
        meaning_scores = self._vectors @ _normalized(np.asarray(vector, dtype=np.float32))
        rankings = [np.argsort(-meaning_scores, kind="stable")[:RRF_DEPTH]]
        if self._settings.use_bm25:
            word_scores = self._bm25.get_scores(_words(query))
            order = np.argsort(-word_scores, kind="stable")[:RRF_DEPTH]
            rankings.append(order[word_scores[order] > 0])  # 낱말 점수가 0인(겹치는 낱말이 없는) 청크는 순위에 넣지 않는다
        rrf_scores: dict[int, float] = {}
        for ranking in rankings:
            for rank, index in enumerate(ranking, start=1):
                rrf_scores[int(index)] = rrf_scores.get(int(index), 0.0) + 1 / (RRF_K + rank)
        best = sorted(rrf_scores, key=lambda index: (-rrf_scores[index], index))[: self._settings.top_k]
        return [self._chunks[index] for index in best]


def _failure(error: Exception, results: list[Chunk]) -> Failure:
    """바깥 서비스 오류를 짧은 오류 표시로. 시간 초과면 그 문구로."""
    message = TIMEOUT_MESSAGE if isinstance(error, TimeoutError) else ERROR_MESSAGE
    return Failure(message, tuple(results))


def _messages(question: str, state: dict, recent: Sequence[tuple[str, str]], results: list[Chunk]) -> list[dict[str, str]]:
    """답변 모델에 넘길 대화 글: 지시, 최근 대화, 그리고 설명서 내용·작업 상태·질문을 담은 마지막 글."""
    messages = [{"role": "system", "content": INSTRUCTIONS}]
    for asked, answered in recent:
        messages += [{"role": "user", "content": asked}, {"role": "assistant", "content": answered}]
    manual = "\n\n---\n\n".join(chunk.text for chunk in results)
    content = (
        f"# 설명서 내용\n\n{manual}\n\n"
        f"# 작업 상태\n\n{json.dumps(state, ensure_ascii=False, indent=2)}\n\n"
        f"# 질문\n\n{question}"
    )
    return messages + [{"role": "user", "content": content}]


def _sources(results: list[Chunk]) -> tuple[Source, ...]:
    """검색 결과를 근거 목록으로. 같은 소제목을 나눈 청크(같은 주소)는 한 번만, 그림·영상 표시는 합친다."""
    by_url: dict[str, list[Chunk]] = {}
    for chunk in results:
        by_url.setdefault(chunk.url, []).append(chunk)
    sources = []
    for url, chunks in by_url.items():
        examples = [example for chunk in chunks for example in chunk.examples]
        videos = [video for chunk in chunks for video in chunk.videos]
        videos += [media for example in examples if example.kind == MediaKind.VIDEO for media in example.media]
        has_image = any(chunk.images for chunk in chunks) or any(example.kind == MediaKind.IMAGE for example in examples)
        first = chunks[0]
        path = " > ".join((first.page_title, *first.headings))
        sources.append(Source(path, url, has_image, bool(videos), tuple(dict.fromkeys(videos))))
    return tuple(sources)


def _words(text: str) -> list[str]:
    """낱말 검색용으로 글을 소문자 낱말로 자른다(object.join 같은 조작 이름은 object, join으로 갈린다)."""
    return re.findall(r"\w+", text.lower())


def _normalized(vectors: np.ndarray) -> np.ndarray:
    """벡터 길이를 1로 맞춘다(그러면 곱이 곧 코사인 유사도다). 길이 0인 벡터는 그대로 둔다."""
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(lengths == 0, 1, lengths)
