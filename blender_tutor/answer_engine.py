"""답 엔진: 질문 + 작업 상태 → 설명서 검색 → 답 글 흐름 + 근거 목록.

시험 경계 ①(.scratch/mvp-roundtrip/spec.md의 "답 엔진"과 Testing Decisions 참고).
Blender·창 없이 부를 수 있고, 아무것도 기억하지 않는다(최근 대화는 부를 때마다 입력으로 받음, 티켓 09).
답변 모델·임베딩은 밖에서 받는다. 테스트는 가짜를 끼우고, 실제 모델을 끼우는 일은 유료 티켓에서 한다.
"""

import json
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from itertools import islice
from typing import Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from blender_tutor.manual_chunks import MAX_WORDS, Chunk
from blender_tutor.menu_names import MenuNames
from blender_tutor.progress import Course, Step
from blender_tutor.work_state import WorkState

RRF_K = 60  # RRF 합치기 상수. 순위 r인 청크는 1 / (RRF_K + r)점을 받는다(널리 쓰는 값)
RRF_DEPTH = 50  # 뜻 검색·낱말 검색 각각 상위 몇 개까지 합치기에 넣나
SIMILAR_COURSES = 3  # 연습 과정을 진행하지 않을 때 붙이는 비슷한 연습 과정 수
SHORT_WORDS = 50  # 찾은 청크 본문이 이보다 짧으면 형제 소제목을 MAX_WORDS(청크 나누는 기준과 같은 값)까지 함께 넘긴다(명세 "검색")

MARK_OPEN, MARK_CLOSE = "[[", "]]"  # 답변 모델이 메뉴 이름을 감싸는 표시. 엔진이 화면 언어에 맞게 바꾼다(티켓 23)
MARK_LIMIT = 80  # 표시가 열린 뒤 이만큼(글자) 닫히지 않으면 표시가 아닌 글로 보고 그대로 낸다

TIMEOUT_MESSAGE = "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요."
ERROR_MESSAGE = "답을 만들다 문제가 생겼어요. 잠시 뒤 다시 물어봐 주세요."

# 문장 속 Blender 낱말의 한국어 표기(영어 → 한국어). 번역 검수에서 화면 글자(ko.po)에 맞춰 정한 것(HISTORY [78]-[92], [104]).
# 메뉴·버튼·옵션 이름은 [[ ]] 표시로 프로그램이 바꾸므로 여기에는 문장 속에 일반 낱말로 나오는 것만 둔다.
# 괄호: 영어 발음을 옮긴 낱말은 붙이지 않고, 한국어로 바꿔 영어가 안 보이는 낱말과 여러 낱말 이름은 처음 한 번 붙인다([83]).
TERMS = (
    ("vertex", "버텍스"),  # 정점·꼭짓점 아님 [78]
    ("edge", "에지"),  # 모서리 아님. 선택 모드 버튼 이름은 화면 글자가 '엣지'라 [[Edge]]로 [78][80]
    ("face", "페이스"),  # 면 아님 [78]
    ("face corner", "페이스 코너(Face Corner)"),  # [78]
    ("mesh", "메시"),  # 메쉬 아님 [85]
    ("normal", "노멀"),  # 법선 아님 [83]
    ("custom normal", "커스텀 노멀"),  # [85]
    ("custom split normals", "커스텀 분할 노멀(Custom Split Normals)"),  # [85]
    ("geometry", "지오메트리"),  # 기하 아님 [88]
    ("empty", "엠프티"),  # 빈 오브젝트 아님 [83]
    ("material", "머티리얼"),  # 재질 아님 [81]
    ("armature", "아마츄어"),  # [79]
    ("bone", "뼈대(Bone)"),  # 본 아님 [79]
    ("modifier", "모디파이어"),  # 수정자 아님 [90]
    ("modifier key", "보조 키(Modifier)"),  # Ctrl·Shift처럼 함께 누르는 키 [80][82]
    ("operator", "작업자(Operator)"),  # 연산자 아님 [81]
    ("pack / unpack", "포장(Pack) / 포장 해제(Unpack)"),  # 압축 아님 [81]
    ("unwrap", "포장 해제(Unwrap)"),  # 사용자가 화면에서 확인한 글자 [84]
    ("mirror", "미러, 미러링"),  # [86]
    ("edit mode", "에디트 모드(Edit Mode)"),  # 편집 모드 아님 [82]
    ("sculpt mode", "스컬프트 모드(Sculpt Mode)"),  # 조각 모드 아님 [92]
    ("orbit", "오비트(Orbit)"),  # 궤도 아님 [80]
    ("median point", "평균 포인트(Median Point)"),  # 중앙점 아님 [88]
    ("offset", "오프셋(Offset)"),  # 간격 아님 [84]
    ("pole", "폴(Pole)"),  # 극점 아님 [85]
    ("emitter", "이미터(Emitter)"),  # 발광체 아님 [84]
    ("sheen", "셰인함(Sheen)"),  # 광택 아님 [87]
    ("attribute", "속성(Attributes)"),  # 특성 아님 [84]
    ("properties", "속성(Properties)"),  # [81]
    ("preferences", "환경 설정(Preferences)"),  # [85]
    ("file browser", "파일 브라우져(File Browser)"),  # 화면 글자 그대로 [83]
    ("rest position", "휴식 위치(Rest Position)"),  # [91]
    ("focal length", "초점의 길이(Focal Length)"),  # 초점 거리는 Focus Distance의 화면 글자 [91]
    ("legacy", "레거시(Legacy)"),  # 기존 아님 [92]
)

INSTRUCTIONS = """너는 Blender 5.2를 처음 쓰는 사람을 돕는 도우미다.
- 쉬운 한국어로 짧게 답하고, 처음 나오는 용어는 한 줄로 풀어 준다.
- Blender 5.2 기준으로 답한다. 아래 '설명서 내용'에 있는 것만 근거로 쓴다.
- 설명서 내용에 답이 없으면 지어내지 말고 "설명서에 없어요"라고 말한 뒤 가장 가까운 내용을 권한다.
- 그림은 캡션 글만 쓴다. [그림] 자리가 중요해 보이면 "설명서 그림을 함께 보세요"라고 안내한다.
- '작업 상태'는 사용자의 Blender 화면에서 지금 읽은 값이다. 사용자가 설명하지 않아도 이것을 보고 답한다.
- Blender 화면의 메뉴·버튼·옵션 이름은 설명서의 영어 그대로 [[ ]]로 감싼다. 메뉴 경로는 통째로 감싸고 단 사이를 >로 가른다(예: [[Add > Mesh]]). 한국어로 옮기지 않는다(프로그램이 사용자 화면 언어에 맞춰 바꾼다).
- [[ ]] 밖 문장에 나오는 Blender 낱말은 아래 표기를 쓴다(Blender 한국어 화면 글자에 맞춘 것). 괄호 속 영어는 답에서 처음 한 번만 붙인다.
""" + "\n".join(f"  - {english} → {korean}" for english, korean in TERMS)

SIMILAR_NOTE = (
    "사용자가 연습 과정을 진행하지 않고 있다. 아래는 질문과 가까운 연습 과정이다(가까운 차례). "
    "만들고 싶은 것을 말하면 맞는 연습 과정을 권하고, 딱 맞는 게 없으면 \"가장 가까운 건 …\"이라고 말한다."
)


class Embedder(Protocol):
    """글 여러 개를 한 번의 호출로 벡터로 바꾼다(글 차례대로). timeout초 동안 응답이 없으면 TimeoutError를 낸다."""

    def embed(self, texts: Sequence[str], timeout: float) -> Sequence[Sequence[float]]: ...


class AnswerModel(Protocol):
    """대화 글(역할 system·user·assistant)을 받아 답 글 조각을 나오는 대로 돌려준다.

    timeout초 동안 다음 조각이 오지 않으면 TimeoutError를 낸다(답 전체 시간 한도가 아님).
    """

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterable[str]: ...


class Reasoning(StrEnum):
    """답변 모델의 생각 수준. 정해 둔 이름만 쓴다(오타를 내면 바로 오류가 난다).

    명세의 none·low·medium. 실제 모델이 받는 값과 다르면 모델을 붙이는 티켓 33에서 고친다.
    """

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"  # 최후의 수단. 답 끝 6초를 넘기면 고르지 않는다(명세)


@dataclass(frozen=True)
class Settings:
    """답 엔진 설정. 평가 때 바꿔 같은 문항을 다시 잰다."""

    top_k: int = 6  # 답변 모델에 넘길 검색 결과 수(명세 6-8개, 22번의 먼저 볼 소제목이 이 위에 더 붙는다)
    timeout: float = 10.0  # 모델이 이만큼(초) 아무것도 보내지 않으면 멈춘 것으로 본다(사용자 결정, 2026-10-21)
    use_bm25: bool = True  # 낱말 검색(BM25)을 섞을지. 끄면 뜻 검색만(평가에서 견줄 스위치)
    # 답변 모델의 생각 수준(명세 기본 none). 시간 기록에 남긴다. 실제 모델에 넘기는 일은 티켓 33
    reasoning: Reasoning = Reasoning.NONE

    def __post_init__(self):
        object.__setattr__(self, "reasoning", Reasoning(self.reasoning))  # "low"처럼 글자로 줘도 받고, 모르는 이름이면 ValueError


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
    # 모델에 붙인 비슷한 연습 과정(가까운 차례, 연습 과정을 진행 중이면 빈 묶음). 평가에서 단순한 질문에
    # 엉뚱하게 권했는지 보려고 알린다(티켓 29). 창은 쓰지 않는다
    similar: tuple[Course, ...] = ()


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

    @property
    def settings(self) -> Settings:
        return self._settings

    def answer(
        self, question: str, state: WorkState, recent: Sequence[tuple[str, str]], step: Step | None = None
    ) -> Iterator[Event]:
        """질문에 답한다. state는 애드온이 보낸 작업 상태 JSON, recent는 최근 대화 (질문, 답) 쌍 목록,
        step은 진행 중인 연습 과정의 지금 단계(연습 과정을 진행하지 않으면 None)."""
        query = self._query(question, state, recent, step)
        # 비슷한 연습 과정은 덧붙인 검색어(직전 질문·조작에 끌림)가 아니라 질문만으로 고른다.
        # 질문만의 벡터는 따로 부르지 않고 같은 호출에 글을 하나 더 실어 받는다(호출 2번 유지, 비용은 질문 길이만큼 늚)
        recommend = step is None and bool(self._courses)
        texts = [query, question] if recommend and question != query else [query]
        # 바깥 서비스(임베딩·답변 모델)를 부르는 두 곳만 오류 표시로 바꾼다.
        # 검색·글 만들기 같은 우리 코드의 오류는 그대로 올려 보내 버그가 "잠시 뒤 다시"에 숨지 않게 한다
        try:
            vectors = self._embedder.embed(texts, self._settings.timeout)
            if len(vectors) != len(texts):
                raise ValueError(f"임베딩이 글 {len(texts)}개에 벡터 {len(vectors)}개를 돌려줌")
            if not all(np.any(vector) for vector in vectors):  # 모두 0이면 뜻 점수가 다 같아 저장 순서가 그대로 순위가 된다
                raise ValueError("임베딩이 모두 0인 벡터를 돌려줌")
        except Exception as error:
            yield _failure(error, [])
            return
        results = self._search(query, vectors[0])
        # 먼저 볼 소제목은 검색 상위를 대신하지 않고 그 위에 덧붙인다. 검색에도 걸렸으면 한 번만
        preview = self._preview(step)
        sent = list(dict.fromkeys(preview + results))
        similar = self._similar_courses(vectors[-1]) if recommend else []
        messages = _messages(question, state, recent, self._widened(sent, preview), similar, step)
        marks = _MenuMarks(self._menu_names if _translated(state) else None)
        try:
            for text in self._model.stream(messages, self._settings.timeout):
                if text := marks.feed(text):
                    yield Piece(text)
        except Exception as error:
            if text := marks.finish():
                yield Piece(text)
            yield _failure(error, results)
            return
        if text := marks.finish():
            yield Piece(text)
        yield Done(_sources(sent), tuple(results), tuple(similar))

    def _widened(self, sent: list[Chunk], preview: list[Chunk]) -> list[list[Chunk]]:
        """넘길 청크마다 함께 읽을 묶음. 작게 찾고 크게 읽기: 찾은 청크가 SHORT_WORDS 미만이면
        아래 소제목(손자 포함)을 설명서 차례로, 아래 소제목이 없으면 같은 부모의 형제 소제목을 가까운 것부터
        MAX_WORDS 안에서 붙인다(묶음 안은 설명서 차례). 이미 넘긴 청크는 다시 넣지 않는다.

        먼저 볼 소제목은 미리 골라 둔 것이라 짧아도 붙이지 않는다(짧은 검색 결과를 보완하려는 일이라서).
        """
        groups, used = [], set()
        for chunk in sent:
            if chunk in used:
                continue
            group = [chunk]
            if chunk.words < SHORT_WORDS and chunk not in preview:
                total = chunk.words
                for extra in self._descendants(chunk) or self._siblings(chunk):
                    if total + extra.words > MAX_WORDS:
                        break
                    if extra not in used and extra not in sent:
                        group.append(extra)
                        total += extra.words
                group.sort(key=self._position.__getitem__)
            groups.append(group)
            used.update(group)
        return groups

    def _descendants(self, chunk: Chunk) -> list[Chunk]:
        """chunk 아래 소제목 청크들(손자 포함, 설명서 차례). 설명서 차례로 저장되어 있어 바로 뒤에 이어 있다."""
        depth, found = len(chunk.headings), []
        for later in islice(self._chunks, self._position[chunk] + 1, None):
            if later.page_path != chunk.page_path or later.headings[:depth] != chunk.headings:
                break
            if len(later.headings) > depth:  # 같은 소제목을 나눈 뒤 조각은 자식이 아니다
                found.append(later)
        return found

    def _siblings(self, chunk: Chunk) -> list[Chunk]:
        """같은 부모 아래 다른 소제목 청크들, 찾은 청크와 가까운 것부터."""
        if not chunk.parent:
            return []
        here = self._position[chunk]
        family = [i for i in self._families[chunk.parent] if self._chunks[i].headings != chunk.headings]
        return [self._chunks[i] for i in sorted(family, key=lambda i: abs(i - here))]

    def _similar_courses(self, vector: Sequence[float]) -> list[Course]:
        """질문 벡터와 가까운 연습 과정 SIMILAR_COURSES개."""
        scores = self._course_vectors @ _normalized(np.asarray(vector, dtype=np.float32))
        return [self._courses[index] for index in np.argsort(-scores, kind="stable")[:SIMILAR_COURSES]]

    def _preview(self, step: Step | None) -> list[Chunk]:
        """지금 단계의 먼저 볼 소제목 청크들(단계 파일 차례, 나눈 조각 모두). 1-3개는 연습 과정 파일 검사가 지킨다."""
        if step is None:
            return []
        return [chunk for address in step.manual for chunk in self._by_address.get(address, [])]

    def _query(self, question: str, state: WorkState, recent: Sequence[tuple[str, str]], step: Step | None) -> str:
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
        if state.recent_operators:
            lines.append(" ".join(state.recent_operators))
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


def _translated(state: WorkState) -> bool:
    """한국어 화면에 인터페이스 번역이 켜져 있나."""
    return state.language.startswith("ko") and state.translate_interface


class _MenuMarks:
    """답 글 속 [[Add > Mesh]] 표시를 화면 글로 바꾼다(티켓 23). 표시가 조각 사이에 갈려 와도 닫힐 때까지 모아 둔다.

    names가 있으면(한국어 화면에 번역 켜짐) 단마다 "추가(Add)"처럼 한국어(영어), 영어로 보이는 단은 영어 그대로.
    names가 없으면 표시만 떼고 영어 그대로.
    """

    def __init__(self, names: MenuNames | None):
        self._names = names
        self._held = ""  # 아직 내보내지 않은 글(열린 표시나, 표시의 시작일지 모르는 마지막 '[')

    def feed(self, text: str) -> str:
        """조각 하나를 받아 지금 내보낼 수 있는 글을 돌려준다."""
        held, shown = self._held + text, []
        while (start := held.find(MARK_OPEN)) >= 0:
            inner = start + len(MARK_OPEN)
            end, again = held.find(MARK_CLOSE, inner), held.find(MARK_OPEN, start + 1)
            if 0 <= again and (end < 0 or again < end):
                # 닫히기 전에 새 표시가 열리면 앞의 것은 짝이 없는 표시. [[[처럼 겹치면 앞 [ 하나만 글이다
                shown.append(held[:start] + (held[start:again] if again < inner else held[inner:again]))
                held = held[again:]
            elif (end < 0 and len(held) - inner > MARK_LIMIT) or end - inner > MARK_LIMIT:
                shown.append(held[:start])  # 닫히지 않는(너무 긴) 표시에 답이 멈춰 보이지 않게 기호만 떼고 낸다
                held = held[inner:]
            elif end < 0:
                break  # 닫힐 때까지 모은다
            else:
                shown += [held[:start], self._screen(held[inner:end])]
                held = held[end + len(MARK_CLOSE) :]
        else:
            start = len(held) - 1 if held.endswith(MARK_OPEN[0]) else len(held)
        self._held = held[start:]
        return "".join(shown) + held[:start]

    def finish(self) -> str:
        """답이 끝났거나 끊겼을 때 남은 글. 닫히지 않은 표시는 기호만 뗀다(사용자에게 [[가 보이지 않게)."""
        held, self._held = self._held, ""
        return held.replace(MARK_OPEN, "", 1)

    def _screen(self, path: str) -> str:
        parts = [part.strip() for part in re.split(r"[>‣]", path)]
        if self._names:
            parents = ["", *parts[:-1]]  # 단마다 바로 앞 단(같은 이름도 메뉴마다 글자가 달라서, 티켓 31)
            parts = [
                f"{korean}({part})" if (korean := self._names.korean(part, parent)) else part
                for part, parent in zip(parts, parents)
            ]
        return " > ".join(parts)


def _failure(error: Exception, results: list[Chunk]) -> Failure:
    """바깥 서비스 오류를 짧은 오류 표시로. 시간 초과면 그 문구로."""
    message = TIMEOUT_MESSAGE if isinstance(error, TimeoutError) else ERROR_MESSAGE
    return Failure(message, tuple(results))


def _for_model(state: WorkState) -> dict:
    """모델에 넘길 작업 상태. 시점(거리·각도·중심 숫자)은 화면 조작 감지에만 쓰고 답에는 도움이 안 되어 뺀다."""
    return {key: value for key, value in state.to_json().items() if key != "view"}


def _messages(
    question: str,
    state: WorkState,
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
        f"# 작업 상태\n\n{json.dumps(_for_model(state), ensure_ascii=False, indent=2)}\n\n"
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
