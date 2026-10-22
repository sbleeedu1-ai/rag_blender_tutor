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

from blender_tutor.manual_chunks import MAX_WORDS, Chunk
from blender_tutor.menu_names import MenuNames
from blender_tutor.progress import Course, Step

RRF_K = 60  # RRF 합치기 상수. 순위 r인 청크는 1 / (RRF_K + r)점을 받는다(널리 쓰는 값)
RRF_DEPTH = 50  # 뜻 검색·낱말 검색 각각 상위 몇 개까지 합치기에 넣나
SIMILAR_COURSES = 3  # 연습 과정을 진행하지 않을 때 붙이는 비슷한 연습 과정 수
SHORT_WORDS = 50  # 찾은 청크 본문이 이보다 짧으면 형제 소제목을 MAX_WORDS(청크 나누는 기준과 같은 값)까지 함께 넘긴다(명세 "검색")

TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."

INSTRUCTIONS = """너는 Blender 5.2를 처음 쓰는 사람을 돕는 도우미다.
- 쉬운 한국어로 짧게 답하고, 처음 나오는 용어는 한 줄로 풀어 준다.
- Blender 5.2 기준으로 답한다. 아래 '설명서 내용'에 있는 것만 근거로 쓴다.
- 설명서 내용에 답이 없으면 지어내지 말고 "설명서에 없어요"라고 말한 뒤 가장 가까운 내용을 권한다.
- 그림은 캡션 글만 쓴다. [그림] 자리가 중요해 보이면 "설명서 그림을 함께 보세요"라고 안내한다.
- '작업 상태'는 사용자의 Blender 화면에서 지금 읽은 값이다. 사용자가 설명하지 않아도 이것을 보고 답한다."""

SIMILAR_NOTE = (
    "사용자가 연습 과정을 진행하지 않고 있다. 아래는 질문과 가까운 연습 과정이다(가까운 차례). "
    "만들고 싶은 것을 말하면 맞는 연습 과정을 권하고, 딱 맞는 게 없으면 \"가장 가까운 건 …\"이라고 말한다."
)


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
        menu_names: MenuNames | None = None,
        courses: Sequence[Course] = (),
        course_vectors: Sequence[Sequence[float]] = (),
    ):
        """menu_names는 질문 속 한국어 메뉴 이름에 영어를 덧붙일 사전(없으면 덧붙이지 않음).
        courses·course_vectors는 비슷한 연습 과정을 권할 연습 과정과 그 벡터(이름 + 한 줄 설명 + 비슷한 말, 티켓 31)."""
        self._chunks = list(chunks)
        self._menu_names = menu_names
        self._courses = list(courses)
        if len(course_vectors) != len(self._courses):  # 엉뚱한 연습 과정을 권하지 않게 바로 멈춘다(설정 버그)
            raise ValueError(f"연습 과정 {len(self._courses)}개, 벡터 {len(course_vectors)}개로 수가 다름")
        self._course_vectors = _normalized(np.asarray(course_vectors, dtype=np.float32)) if self._courses else None
        self._by_address: dict[str, list[Chunk]] = {}  # 먼저 볼 소제목 주소 → 그 소제목 청크들(나눈 조각 모두)
        self._position: dict[Chunk, int] = {}  # 청크 → 저장 차례(= 설명서 차례)
        self._families: dict[tuple[str, tuple[str, ...]], list[int]] = {}  # Chunk.parent → 자식 청크 차례들
        for index, chunk in enumerate(self._chunks):
            self._by_address.setdefault(chunk.address, []).append(chunk)
            self._position[chunk] = index
            if chunk.parent:
                self._families.setdefault(chunk.parent, []).append(index)
        self._vectors = _normalized(np.asarray(vectors, dtype=np.float32))
        self._bm25 = BM25Okapi([_words(chunk.text) for chunk in self._chunks])
        self._embedder = embedder
        self._model = model
        self._settings = settings

    def answer(
        self, question: str, state: dict, recent: Sequence[tuple[str, str]], step: Step | None = None
    ) -> Iterator[Event]:
        """질문에 답한다. state는 애드온이 보낸 작업 상태 JSON, recent는 최근 대화 (질문, 답) 쌍 목록,
        step은 진행 중인 연습 과정의 지금 단계(연습 과정을 진행하지 않으면 None)."""
        query = self._query(question, state, recent, step)
        # 바깥 서비스(임베딩·답변 모델)를 부르는 두 곳만 오류 표시로 바꾼다.
        # 검색·글 만들기 같은 우리 코드의 오류는 그대로 올려 보내 버그가 "잠시 뒤 다시"에 숨지 않게 한다
        try:
            vector = self._embedder.embed(query, self._settings.timeout)
            if not np.any(vector):  # 모두 0이면 뜻 점수가 다 같아 청크 저장 순서가 그대로 순위가 된다. 잘못된 응답으로 본다
                raise ValueError("임베딩이 모두 0인 벡터를 돌려줌")
        except Exception as error:
            yield _failure(error, [])
            return
        results = self._search(query, vector)
        # 먼저 볼 소제목은 검색 상위를 대신하지 않고 그 위에 덧붙인다. 검색에도 걸렸으면 한 번만
        sent = list(dict.fromkeys(self._preview(step) + results))
        similar = self._similar_courses(vector) if step is None else []
        messages = _messages(question, state, recent, self._widened(sent), similar, step)
        try:
            for text in self._model.stream(messages, self._settings.timeout):
                yield Piece(text)
        except Exception as error:
            yield _failure(error, results)
            return
        yield Done(_sources(sent), tuple(results))

    def _widened(self, sent: list[Chunk]) -> list[list[Chunk]]:
        """넘길 청크마다 함께 읽을 묶음. 작게 찾고 크게 읽기: SHORT_WORDS 미만이면 같은 부모의 형제 소제목을
        가까운 것부터 MAX_WORDS 안에서 붙인다(설명서 차례로). 이미 넘긴 청크는 다시 넣지 않는다."""
        groups, used = [], set()
        for chunk in sent:
            if chunk in used:
                continue
            group = [chunk]
            if chunk.words < SHORT_WORDS and chunk.parent:
                here = self._position[chunk]
                family = self._families[chunk.parent]
                siblings = [i for i in family if self._chunks[i].headings != chunk.headings]
                total = chunk.words
                for index in sorted(siblings, key=lambda i: abs(i - here)):
                    sibling = self._chunks[index]
                    if total + sibling.words > MAX_WORDS:
                        break
                    if sibling not in used and sibling not in sent:
                        group.append(sibling)
                        total += sibling.words
                group.sort(key=self._position.__getitem__)
            groups.append(group)
            used.update(group)
        return groups

    def _similar_courses(self, vector: Sequence[float]) -> list[Course]:
        """검색에 쓴 질문 벡터를 그대로 다시 써서(추가 호출 없음) 가까운 연습 과정 SIMILAR_COURSES개."""
        if not self._courses:
            return []
        scores = self._course_vectors @ _normalized(np.asarray(vector, dtype=np.float32))
        return [self._courses[index] for index in np.argsort(-scores, kind="stable")[:SIMILAR_COURSES]]

    def _preview(self, step: Step | None) -> list[Chunk]:
        """지금 단계의 먼저 볼 소제목 청크들(단계 파일 차례, 나눈 조각 모두). 1-3개는 연습 과정 파일 검사가 지킨다."""
        if step is None:
            return []
        return [chunk for address in step.manual for chunk in self._by_address.get(address, [])]

    def _query(self, question: str, state: dict, recent: Sequence[tuple[str, str]], step: Step | None) -> str:
        """검색어: 질문 + 직전 질문 + 지금 단계 이름과 먼저 볼 소제목 경로 + 방금 실행한 조작(추가 호출 없이 아는 것만).

        "그다음은요?"처럼 앞말에 기대는 질문도 무엇을 찾는지 알 수 있게 하고, 영어 설명서와 겹치는 낱말을 늘려
        낱말 검색(BM25)이 한국어 질문에도 일하게 한다.
        """
        english = self._menu_names.english_in(question) if self._menu_names else ()
        lines = [" ".join((question, *english))]
        if recent:
            lines.append(recent[-1][0])
        if step:
            lines.append(step.name)
            lines += dict.fromkeys(chunk.path for chunk in self._preview(step))  # 나눈 조각은 경로가 같아 한 번만
        operators = state.get("recent_operators") or []
        if operators:
            lines.append(" ".join(operators))
        return "\n".join(lines)

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


def _messages(
    question: str,
    state: dict,
    recent: Sequence[tuple[str, str]],
    groups: list[list[Chunk]],
    similar: list[Course],
    step: Step | None,
) -> list[dict[str, str]]:
    """답변 모델에 넘길 대화 글: 지시, 최근 대화, 그리고 설명서 내용·작업 상태·질문을 담은 마지막 글.

    groups는 넘길 청크마다 함께 읽을 묶음(찾은 청크와 그 형제 소제목). 묶음 사이를 ---로 가른다.
    similar는 연습 과정을 진행하지 않을 때만 붙이는 비슷한 연습 과정, step은 지금 단계(그 단계 내용만 넘긴다).
    """
    messages = [{"role": "system", "content": INSTRUCTIONS}]
    for asked, answered in recent:
        messages += [{"role": "user", "content": asked}, {"role": "assistant", "content": answered}]
    manual = "\n\n---\n\n".join("\n\n".join(chunk.text for chunk in group) for group in groups)
    content = f"# 설명서 내용\n\n{manual}\n\n"
    if similar:
        courses = "\n".join(f"- {course.name}: {course.summary}" for course in similar)
        content += f"# 비슷한 연습 과정\n\n{SIMILAR_NOTE}\n\n{courses}\n\n"
    if step and step.guide:
        content += f"# 지금 단계\n\n{step.guide}\n\n"
    content += (
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
        videos = tuple(dict.fromkeys(video for chunk in chunks for video in chunk.video_links))
        has_image = any(chunk.has_image for chunk in chunks)
        sources.append(Source(chunks[0].path, url, has_image, bool(videos), videos))
    return tuple(sources)


def _words(text: str) -> list[str]:
    """낱말 검색용으로 글을 소문자 낱말로 자른다(object.join 같은 조작 이름은 object, join으로 갈린다)."""
    return re.findall(r"\w+", text.lower())


def _normalized(vectors: np.ndarray) -> np.ndarray:
    """벡터 길이를 1로 맞춘다(그러면 곱이 곧 코사인 유사도다). 길이 0인 벡터는 그대로 둔다."""
    lengths = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(lengths == 0, 1, lengths)
