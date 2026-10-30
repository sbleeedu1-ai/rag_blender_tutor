"""소규모 검색 비교(티켓 40): 같은 질문 20개·청크 묶음(약 200개)으로 검색 조건 18개를 돌려 정답 근거 적중과 시간을 견준다.

조건 = 임베딩 모델(text-embedding-3-large / BGE-M3) × 뜻 검색에 넣는 글(원문만 / 원문+번역 합침 / 원문·번역 분리) × BM25(끔 / 영어 원문 / 원문+번역).
답변 모델은 부르지 않는다. 리랭커는 쓰지 않는다.

- estimate: 유료 임베딩의 어림 비용을 보인다(돈 들지 않음).
- build-db: 묶음 청크의 검색용 DB(벡터)를 만들거나 저장된 것을 재사용한다.
- run: DB를 준비하고 질문 20개 × 회차 × 조건을 돌려 results/<날짜>_<이름>/에 쓴다(폴더가 이미 있으면 멈춤).
유료 모델을 고르면 --yes가 있어야 실행한다(어림 비용을 먼저 보고 확인받은 뒤 붙인다).

예: python -m blender_tutor.search_compare run --name search_compare --note "강의실 PC, Blender에 연습 파일 열어 둠" --yes
"""

import argparse
import hashlib
import json
import platform
import random
import re
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from datetime import datetime
from enum import StrEnum
from itertools import product
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from blender_tutor.answer_engine import RRF_DEPTH, RRF_K, Embedder, _normalized
from blender_tutor.beginner_scope import OpenAIModel, openai_key
from blender_tutor.evaluate import _commit
from blender_tutor import manual_vectors
from blender_tutor.manual_chunks import Chunk, load_chunks
from blender_tutor.manual_vectors import PRICE_PER_MILLION, OpenAIEmbedder  # 요금표에 있는 모델만 돈이 든다
from blender_tutor.menu_names import MenuNames
from blender_tutor.paths import PROJECT
from blender_tutor.local_embeddings import MODELS as LOCAL_MODELS, LocalEmbedder
from blender_tutor.translate import _tokens, pieces
from blender_tutor.translation_check import reviewed

MODELS = ("text-embedding-3-large", "bge-m3")
TOP_KS = (4, 6, 8)  # 같은 검색 순위에서 상위 몇 개까지를 채점하나(티켓 40)
ROUNDS = 3  # 질문마다 몇 회 재나
SEED = 40  # 질문마다 조건 순서를 섞는 씨앗(다시 돌려도 같은 순서)
TIMEOUT = 30.0  # 임베딩 호출 한도(초)
BATCH = 64  # DB를 만들 때 한 번에 보내는 글 수

DATA = PROJECT / "data"
COMPARE = DATA / "search_compare"


class Text(StrEnum):
    """뜻 검색(임베딩)에 넣는 글. 번역이 없는 청크는 어느 조건에서나 영어 원문을 쓴다."""

    ORIGINAL = "원문만"
    COMBINED = "원문+번역 합침"  # 원문 뒤에 번역을 이어 붙여 벡터 하나
    SEPARATE = "원문·번역 분리"  # 원문·번역 벡터를 따로 두고, 같은 청크의 높은 점수 하나로 순위를 만든다


class Bm25(StrEnum):
    """낱말 검색(BM25)에 넣는 글. 켜면 뜻 검색 순위와 RRF로 합친다."""

    OFF = "BM25 끔"
    ENGLISH = "BM25 영어 원문"
    BOTH = "BM25 원문+번역"


class Scope(StrEnum):
    """검색 전에 남길 청크(HISTORY [117]). 거른 청크는 뜻 검색·BM25 모두에서 뺀다."""

    ALL = "범위 전체"
    ASKED = "질문 분야만"  # 질문 바꾸기 모델이 답이 있다고 고른 분야 안에서만
    OTHERS = "질문 보고 뺀 나머지"  # 질문 바꾸기 모델이 확실히 관계없다고 고른 분야만 빼고
    BEGINNER = "초보자 범위만"  # data/beginner_scope/scope.jsonl의 include 쪽(질문과 상관없이 고정)


BIG_FIELDS = ("modeling", "render", "editors")  # 너무 커서 한 단계 더 나눠 고르는 분야(modeling만 설명서의 30%)


def area_of(page_path: str) -> str:
    """질문 분야 고르기의 단위: 큰 세 분야는 둘째 폴더까지(modeling/modifiers), 나머지는 분야(physics)."""
    parts = page_path.split("/")
    return "/".join(parts[:2]) if parts[0] in BIG_FIELDS and len(parts) > 1 else parts[0]


@dataclass(frozen=True)
class Picked:
    """질문 하나에 대해 질문 바꾸기 모델이 고른 분야."""

    asked: tuple[str, ...]  # 답이 있을 분야
    excluded: tuple[str, ...]  # 확실히 관계없는 분야


@dataclass(frozen=True)
class Condition:
    model: str
    text: Text
    bm25: Bm25
    scope: Scope = Scope.ALL

    @property
    def name(self) -> str:
        base = f"{self.model} / {self.text} / {self.bm25}"
        return base if self.scope is Scope.ALL else f"{base} / {self.scope}"


def conditions(models: Sequence[str]) -> list[Condition]:
    """모델마다 넣는 글 3 × BM25 3 = 9개 조건."""
    return [Condition(model, text, bm25) for model, text, bm25 in product(models, Text, Bm25)]


@dataclass(frozen=True)
class PoolChunk:
    """검색 묶음의 청크 하나. english는 검색·답변에 쓰는 글(Chunk.text), korean은 검수한 번역(없으면 None)."""

    key: str  # 주소/같은 주소 안의 차례(translate.pieces와 같은 열쇠)
    english: str
    korean: str | None


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    translated: bool  # 정답 근거에 번역이 있나(결과를 둘로 나눠 본다)
    groups: tuple[tuple[str, ...], ...]  # 필요한 근거들. 묶음 하나 안의 청크는 서로 대신한다


def load_pool(pool_path: Path, chunks_path: Path, translations: Mapping[str, str]) -> list[PoolChunk]:
    """묶음 파일(한 줄에 열쇠 하나)의 청크에 청크 파일의 글과 번역을 붙인다. 같은 청크가 두 번이거나 청크 파일에 없으면 멈춘다."""
    keys = [json.loads(line)["key"] for line in pool_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    twice = [key for key, count in Counter(keys).items() if count > 1]
    if twice:
        raise ValueError(f"{pool_path}: 묶음에 두 번 든 청크 {', '.join(twice)}")
    texts = {piece.key: piece.chunk.text for piece in pieces(load_chunks(chunks_path))}
    missing = [key for key in keys if key not in texts]
    if missing:
        raise ValueError(f"{pool_path}: 청크 파일에 없는 열쇠 {', '.join(missing)}")
    return [PoolChunk(key, texts[key], translations.get(key)) for key in keys]


def load_questions(paths: Sequence[Path], pool: Sequence[PoolChunk]) -> list[Question]:
    """질문 파일들(한 줄에 질문 하나)을 읽는다. 빼기로 한 질문(dropped)은 건너뛰고, 정답이 묶음 밖이면 멈춘다."""
    known = {chunk.key for chunk in pool}
    found = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("dropped"):
                continue
            groups = tuple(tuple(group["any_of"]) for group in row["answer_groups"])
            outside = [key for group in groups for key in group if key not in known]
            if not groups or outside:
                raise ValueError(f"{path} {row['id']}: 정답이 없거나 묶음에 없는 정답 {', '.join(outside)}")
            found.append(Question(row["id"], row["question"], bool(row["answer_translated"]), groups))
    return found


def bm25_words(text: str) -> list[str]:
    """낱말 검색용 자르기: 한글은 두 글자씩 겹쳐 자르고(한 글자 낱말은 그대로), 나머지는 소문자 낱말로 자른다.
    모든 BM25 조건의 문서·질문에 같이 쓴다. 도우미의 지금 자르기(answer_engine._words)는 바꾸지 않는다."""
    words = []
    for word in re.findall(r"[가-힣]+|[^\W가-힣]+", text.lower()):
        if "가" <= word[0] <= "힣" and len(word) > 1:
            words += [word[i : i + 2] for i in range(len(word) - 1)]
        else:
            words.append(word)
    return words


@dataclass(frozen=True)
class Hit:
    found: int  # 찾은 필요 근거 수(대신하는 청크를 여럿 찾아도 근거 하나로 센다)
    needed: int
    first_rank: int | None  # 어느 정답이든 처음 나온 순위(1부터, 남긴 순위 밖이면 None)

    @property
    def ratio(self) -> float:
        return self.found / self.needed

    @property
    def partial(self) -> bool:
        return self.found > 0

    @property
    def full(self) -> bool:
        return self.found == self.needed


def hit(groups: Sequence[Sequence[str]], ranked: Sequence[str], k: int) -> Hit:
    """검색 순위 상위 k개가 필요한 근거를 몇 개 찾았나. 같은 쪽이 아니라 실제 정답 청크로 판정한다."""
    top = set(ranked[:k])
    answers = {key for group in groups for key in group}
    first = next((rank for rank, key in enumerate(ranked, start=1) if key in answers), None)
    return Hit(sum(any(key in top for key in group) for group in groups), len(groups), first)


@dataclass(frozen=True)
class Index:
    """한 모델의 검색용 DB. 모두 묶음 차례로 줄을 맞추고 길이를 1로 맞춘 벡터다."""

    original: np.ndarray
    translation: np.ndarray  # 번역 없는 청크의 줄은 0(translated로 가린다)
    combined: np.ndarray  # 번역 없는 청크의 줄은 원문 벡터
    translated: np.ndarray  # 청크마다 번역이 있나
    records: list[dict]  # 글 종류마다 어떤 글·모델로 만들었나, 새로 만들었나 재사용했나


def build_index(pool: Sequence[PoolChunk], model: str, embedder: Embedder, db: Path, original_only: bool = False) -> Index:
    """원문·번역·합침 글을 한 번씩 임베딩해 저장하고, 같은 글·모델로 저장된 것이 있으면 다시 부르지 않고 읽는다.
    번역 없는 청크의 합침 글은 원문과 같아 다시 임베딩하지 않는다."""
    translated = [chunk for chunk in pool if chunk.korean]
    kinds = {
        "original": [(chunk.key, chunk.english) for chunk in pool],
        "translation": [(chunk.key, chunk.korean) for chunk in translated],
        "combined": [(chunk.key, f"{chunk.english}\n\n{chunk.korean}") for chunk in translated],
    }
    if original_only:
        original, record = _stored(kinds["original"], model, "original", embedder, db)
        original = _normalized(original)
        return Index(original, np.zeros_like(original), original.copy(), np.zeros(len(pool), dtype=bool), [record])
    stored, records = {}, []
    for kind, items in kinds.items():
        stored[kind], record = _stored(items, model, kind, embedder, db)
        records.append(record)
    rows = [index for index, chunk in enumerate(pool) if chunk.korean]
    original = _normalized(stored["original"])
    translation, combined = np.zeros_like(original), original.copy()
    if rows:
        translation[rows] = _normalized(stored["translation"])
        combined[rows] = _normalized(stored["combined"])
    mask = np.zeros(len(pool), dtype=bool)
    mask[rows] = True
    return Index(original, translation, combined, mask, records)


def _stored(items: list[tuple[str, str]], model: str, kind: str, embedder: Embedder, db: Path) -> tuple[np.ndarray, dict]:
    """글 목록의 벡터. 파일 이름에 모델·글의 해시를 넣어, 글이 바뀌면 이전 파일을 두고 새 파일을 만든다."""
    identity = [model, items]
    if hasattr(embedder, "cache_identity"):
        identity.append(embedder.cache_identity)
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    path = db / f"{re.sub(r'[^0-9A-Za-z.-]', '_', model)}_{kind}_{digest}.npz"
    meta = path.with_suffix(".json")
    if path.exists():
        return np.load(path)["vectors"], {**json.loads(meta.read_text(encoding="utf-8")), "상태": "재사용"}
    start = time.perf_counter()
    vectors = []
    embed_documents = getattr(embedder, "embed_documents", embedder.embed)
    for begin in range(0, len(items), BATCH):
        vectors += embed_documents([text for _, text in items[begin : begin + BATCH]], TIMEOUT * 4)
    if len(vectors) != len(items):
        raise ValueError(f"{model} {kind}: 글 {len(items)}개에 벡터 {len(vectors)}개")
    array = np.asarray(vectors, dtype=np.float32).reshape(len(items), -1)
    record = {
        "모델": model, "글": kind, "청크 수": len(items), "해시": digest, "파일": path.name,
        "만든 시각": datetime.now().isoformat(timespec="seconds"), "걸린 초": round(time.perf_counter() - start, 3),
    }
    if hasattr(embedder, "cache_identity"):
        record["임베딩 설정"] = embedder.cache_identity
    db.mkdir(parents=True, exist_ok=True)
    np.savez(path, vectors=array, keys=np.array([key for key, _ in items]))
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return array, {**record, "상태": "새로 만듦"}


@dataclass(frozen=True)
class Search:
    final: list[str]  # 최종 순위(열쇠). BM25를 켜면 RRF에 든 청크만
    parts: dict[str, list[tuple[str, float]]]  # 원문·번역·뜻·BM25·RRF 각각의 순위와 점수(상위 RRF_DEPTH개)
    seconds: dict[str, float]  # 뜻 검색·BM25·RRF 단계 시간


class Searcher:
    """모델별 DB와 BM25 두 가지(영어 원문, 원문+번역)를 들고 조건대로 검색한다."""

    def __init__(self, pool: Sequence[PoolChunk], indexes: Mapping[str, Index], clock: Callable[[], float] = time.perf_counter,
                 scopes: Mapping[Scope, np.ndarray] | None = None):
        self._keys = [chunk.key for chunk in pool]
        self._areas = np.array([area_of(chunk.key.split(".html")[0]) for chunk in pool])
        self._indexes = indexes
        self._clock = clock
        self._scopes = {Scope.ALL: np.ones(len(pool), dtype=bool), **(scopes or {})}  # 범위마다 남길 청크
        self._bm25 = {
            Bm25.ENGLISH: BM25Okapi([bm25_words(chunk.english) for chunk in pool]),
            Bm25.BOTH: BM25Okapi([bm25_words(f"{chunk.english}\n\n{chunk.korean or ''}") for chunk in pool]),
        }

    def search(self, condition: Condition, query: str, vector: Sequence[float], picked: Picked | None = None) -> Search:
        start = self._clock()
        index = self._indexes[condition.model]
        query_vector = _normalized(np.asarray(vector, dtype=np.float32))
        original = index.original @ query_vector
        parts = {}
        if condition.text is Text.ORIGINAL:
            meaning = original
        elif condition.text is Text.COMBINED:
            meaning = index.combined @ query_vector
        else:
            translation = np.where(index.translated, index.translation @ query_vector, -np.inf)
            meaning = np.maximum(original, translation)
            parts["원문"], parts["번역"] = self._top(original), self._top(translation)
        keep = self.keep(condition.scope, picked)
        meaning = np.where(keep, meaning, -np.inf)
        meaning_order = np.argsort(-meaning, kind="stable")[: int(keep.sum())]
        parts["뜻"] = self._top(meaning)
        meaning_done = self._clock()
        if condition.bm25 is Bm25.OFF:
            final = [self._keys[index] for index in meaning_order]
            return Search(final, parts, {"뜻 검색": meaning_done - start, "BM25": 0.0, "RRF": 0.0})
        scores = np.where(keep, self._bm25[condition.bm25].get_scores(bm25_words(query)), 0.0)
        word_order = np.argsort(-scores, kind="stable")[:RRF_DEPTH]
        word_order = word_order[scores[word_order] > 0]  # 겹치는 낱말이 없는 청크는 순위에 넣지 않는다(도우미와 같음)
        parts["BM25"] = [(self._keys[index], float(scores[index])) for index in word_order]
        bm25_done = self._clock()
        rrf: dict[int, float] = {}
        for ranking in (meaning_order[:RRF_DEPTH], word_order):
            for rank, index in enumerate(ranking, start=1):
                rrf[int(index)] = rrf.get(int(index), 0.0) + 1 / (RRF_K + rank)
        best = sorted(rrf, key=lambda index: (-rrf[index], index))
        parts["RRF"] = [(self._keys[index], rrf[index]) for index in best[:RRF_DEPTH]]
        rrf_done = self._clock()
        seconds = {"뜻 검색": meaning_done - start, "BM25": bm25_done - meaning_done, "RRF": rrf_done - bm25_done}
        return Search([self._keys[index] for index in best], parts, seconds)

    def keep(self, scope: Scope, picked: Picked | None = None) -> np.ndarray:
        """이 범위에서 남길 청크. 질문 분야 범위는 질문마다 고른 분야(picked)로 정한다."""
        if scope is Scope.ASKED:
            return np.isin(self._areas, picked.asked)
        if scope is Scope.OTHERS:
            return ~np.isin(self._areas, picked.excluded)
        return self._scopes[scope]

    def _top(self, scores: np.ndarray) -> list[tuple[str, float]]:
        """점수 높은 차례 상위 RRF_DEPTH개(점수가 없는 청크는 뺀다)."""
        order = np.argsort(-scores, kind="stable")[:RRF_DEPTH]
        return [(self._keys[index], round(float(scores[index]), 6)) for index in order if np.isfinite(scores[index])]


class Names:
    """질문 속 한국어 메뉴 이름에 붙일 영어 이름을 찾는 것(MenuNames와 같은 꼴)."""

    def english_in(self, text: str) -> tuple[str, ...]: ...


class NoNames:
    """메뉴 이름을 덧붙이지 않을 때(--menu-names off): 원래 질문 그대로 검색한다."""

    def english_in(self, text: str) -> tuple[str, ...]:
        return ()


class NarrowNames:
    """좁힌 덧붙이기(--menu-names narrow, HISTORY [115]): 영어를 소리대로 적은 한국어 이름만 붙인다.

    일상어와 겹치는 화면 글자(만들 → Make, 바닥 → Floor)는 걸러지고 미러 모디파이어 → Mirror Modifier 같은 이름만 남는다.
    한글이 없는 조각(A·S·Y)은 빼고, 영어 후보가 여럿이면 모두 소리가 닮았을 때만(Object·Objects) 붙인다.
    알려진 한계: 일상어인데 소리도 닮으면 남는다(돌리면 → Dolly).
    """

    def __init__(self, names: MenuNames):
        self._names = names

    def english_in(self, text: str) -> tuple[str, ...]:
        found: dict[str, None] = {}
        for piece, english in self._names.matches_in(text):
            if _HANGUL.search(piece) and all(sounds_alike(piece, name) for name in english):
                found.update(dict.fromkeys(english))
        return tuple(found)


_HANGUL = re.compile("[가-힣]")
_FIRST = "KKNTTLMPPSS-SSSKTPH"  # 한글 첫소리 19개(ㄱ-ㅎ) → 자음 묶음, ㅇ은 소리가 없어 뺀다
_LAST = ("", "K", "K", "K", "N", "N", "N", "T", "L", "L", "L", "L", "L", "L", "L", "L",
         "M", "P", "P", "S", "S", "", "S", "S", "K", "T", "P", "H")  # 받침 28개(없음 포함)
_ENGLISH_SPELLING = (("ph", "p"), ("ch", "s"), ("sh", "s"), ("th", "s"), ("ck", "k"), ("x", "ks"), ("qu", "k"))
_ENGLISH = dict(zip("bpfvdtgkcqszjlrmnh", "PPPPTTKKKKSSSLLMNH"))


def _bones(letters: str) -> str:
    return re.sub(r"(.)\1+", r"\1", letters)  # 같은 묶음이 이어지면 하나로(mirror → MLL → ML)


def sounds_alike(korean: str, english: str) -> bool:
    """한국어 이름이 영어를 소리대로 적은 것인가: 둘을 자음 뼈대(ㅂ·ㅍ·b·p·f·v는 한 묶음 등)로 바꿔 70% 이상 겹치면 그렇다고 본다.
    미러(ML)·mirror(ML), 오리진(LSN)·origin(LSN)은 닮고, 바닥(PTK)·floor(PL), 만들(MNTL)·make(MK)는 닮지 않는다."""
    consonants = []
    for letter in korean:
        code = ord(letter) - 0xAC00
        if 0 <= code < 11172:
            consonants += [_FIRST[code // 588].replace("-", ""), _LAST[code % 28]]
    spelled = re.sub(r"(?<=\w\w)s\b", "", english.lower())  # 복수형 s는 한국어 표기에 없다(Textures → 텍스처)
    for written, sound in _ENGLISH_SPELLING:
        spelled = spelled.replace(written, sound)
    spelled = re.sub(r"[gc](?=[eiy])", "s", spelled)  # origin의 g, face의 c
    left, right = _bones("".join(consonants)), _bones("".join(_ENGLISH.get(letter, "") for letter in spelled))
    return bool(left) and SequenceMatcher(None, left, right).ratio() >= 0.7


def query_of(question: str, names: Names) -> str:
    """실제 검색어: 질문 뒤에 사전으로 찾은 영어 메뉴 이름을 덧붙인다(도우미의 검색어 첫 줄과 같음)."""
    return " ".join((question, *names.english_in(question)))


REWRITE_PROMPT = """너는 Blender 5.2 공식 설명서(영어)를 찾을 검색어와 분야를 고른다.
사용자는 Blender를 처음 쓰는 사람이고, 기능 이름 대신 겪은 증상이나 하고 싶은 일을 한국어로 말한다.
질문에 답하지 말고, 답이 있을 설명서 쪽을 찾기 위한 것만 낸다.
- query: 영어 검색어 하나. 필요할 것 같은 Blender 기능·도구·모디파이어·메뉴·옵션의 공식 영어 이름과 질문의 핵심 상황을 짧은 영어로, 30낱말 이하.
- areas: 답이 있을 가능성이 큰 설명서 분야 1-3개(아래 목록 이름 그대로).
- exclude: 이 질문과 확실히 관계없는 분야(아래 목록 이름 그대로). 조금이라도 관계있을 수 있으면 넣지 않는다.
설명서 분야 목록(폴더 이름):
{areas}
JSON으로만 답한다: {{"query": "...", "areas": ["..."], "exclude": ["..."]}}"""
# 번역만(HISTORY [118]·[120]): 질문 바꾸기의 효과가 영어로 옮긴 데서 왔는지, 기능 이름을 찾아 붙인 데서 왔는지 가른다.
TRANSLATE_PROMPT = """너는 한국어 질문을 영어로 옮긴다.
질문에 답하지 말고, 질문을 뜻 그대로 자연스러운 영어 한 문장(또는 두 문장)으로 옮기기만 한다.
질문에 없는 Blender 기능·도구·모디파이어·메뉴·옵션 이름을 떠올려 더하거나, 증상을 기능 이름으로 바꾸지 않는다.
질문에 한국어로 적힌 메뉴 이름(예: 오리진, 베벨)은 그 낱말 그대로 영어로 옮긴다.
JSON으로만 답한다: {{"query": "..."}}"""
# 짧은 지시(티켓 43): 검색어 지시는 REWRITE_PROMPT와 같고, 분야 목록과 areas·exclude 칸을 뺐다(분야 거르기는 효과가 없었다, [113]-[119]).
SHORT_PROMPT = """너는 Blender 5.2 공식 설명서(영어)를 찾을 검색어를 만든다.
사용자는 Blender를 처음 쓰는 사람이고, 기능 이름 대신 겪은 증상이나 하고 싶은 일을 한국어로 말한다.
질문에 답하지 말고, 답이 있을 설명서 쪽을 찾기 위한 영어 검색어 하나만 낸다.
필요할 것 같은 Blender 기능·도구·모디파이어·메뉴·옵션의 공식 영어 이름과 질문의 핵심 상황을 짧은 영어로, 30낱말 이하.
JSON으로만 답한다: {{"query": "..."}}"""
PROMPTS = {"rewrite": REWRITE_PROMPT, "translate": TRANSLATE_PROMPT, "short": SHORT_PROMPT}
REWRITE_PRICE = {"gpt-6-luna": (0.10, 0.50)}  # 100만 토큰당 입력·출력 달러(.scratch/.../31-번역-모델-조사.md)
TIER_FACTOR = {None: 1, "fast": 2}  # 처리 등급별 값 배수(공식 가격 쪽 Fast: luna 입력 $0.20·출력 $1.00, 2026-10-30 확인)


class Chat:
    """질문 바꾸기에 쓰는 모델(beginner_scope.OpenAIModel과 같은 꼴)."""

    input_tokens: int
    output_tokens: int
    tiers: Counter  # 응답이 알린 처리 등급별 수

    def ask(self, messages: list[dict[str, str]]) -> str: ...


def rewrite(questions: Sequence[Question], chat: Chat, areas: Sequence[str], rounds: int = ROUNDS,
            clock: Callable[[], float] = time.perf_counter, template: str = REWRITE_PROMPT) -> list[dict]:
    """회차마다 질문을 영어 검색어와 분야로 바꾼다. 같은 질문도 회차마다 새로 물어 바뀌는 정도와 걸린 시간을 남긴다.
    목록에 없는 분야 이름은 빼고 "목록 밖"에 남긴다(빠진 만큼 질문 분야 범위가 좁아지는 것을 결과에서 볼 수 있게).
    번역만 지시(TRANSLATE_PROMPT)는 분야를 묻지 않아 분야 칸이 비어 있다."""
    prompt = template.format(areas="\n".join(areas))
    known = set(areas)
    rows = []
    for round_number in range(1, rounds + 1):
        for question in questions:
            start = clock()
            answer = chat.ask([{"role": "system", "content": prompt}, {"role": "user", "content": question.question}])
            seconds = clock() - start
            got = _parsed(answer, f"{question.id} {round_number}회차")
            named = got["areas"] + got["exclude"]
            rows.append({
                "회차": round_number, "질문": question.id, "원래 질문": question.question, "검색어": got["query"],
                "분야": [name for name in got["areas"] if name in known],
                "뺄 분야": [name for name in got["exclude"] if name in known],
                "목록 밖": [name for name in named if name not in known], "초": seconds,
            })
    return rows


def fuse_rounds(rows: Sequence[dict]) -> list[dict]:
    """조건·질문마다 회차별 순위를 RRF로 합친 줄(회차 1로 채점된다). 질문을 여러 번 바꿔 함께 찾으면 나아지는지 본다.
    시간은 회차들을 동시에 보냈다고 보고 가장 느린 회차로 둔다."""
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["조건"], row["질문"]), []).append(row)
    fused = []
    for (name, question), mine in grouped.items():
        mine = sorted(mine, key=lambda row: row["회차"])
        fused.append({
            "회차": 1, "질문": question, "조건": f"{name} / {len(mine)}회차 합침", "원래 질문": mine[0]["원래 질문"],
            "검색어": [row["검색어"] for row in mine], "시간": {"전체": max(row["시간"]["전체"] for row in mine)},
            "결과": rrf_merge([row["결과"] for row in mine]),
        })
    return fused


def rrf_merge(rankings: Sequence[Sequence[str]]) -> list[str]:
    """여러 순위의 상위 RRF_DEPTH개를 RRF로 합친 상위 RRF_DEPTH개. 같은 점수는 먼저 나온 차례(안정 정렬)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking[:RRF_DEPTH], start=1):
            scores[key] = scores.get(key, 0.0) + 1 / (RRF_K + rank)
    return sorted(scores, key=lambda key: -scores[key])[:RRF_DEPTH]


@dataclass(frozen=True)
class FlowWay:
    """흐름 측정의 한 방식: 어떤 지시(PROMPTS 이름)로, 질문 바꾸기를 몇 번 동시에, 어떤 처리 등급으로 부르나."""

    prompt: str
    count: int
    tier: str | None = None


FLOW_WAYS = {
    "한 번 바꾸기": FlowWay("rewrite", 1), "3번 합치기": FlowWay("rewrite", 3),
    "짧은 지시 3번": FlowWay("short", 3), "짧은 지시 3번 fast": FlowWay("short", 3, "fast"),
}


def flow(questions: Sequence[Question], ways: Mapping[str, tuple[str, Sequence[Chat]]], embedder: Embedder, searcher: Searcher,
         condition: Condition, rounds: int = ROUNDS, seed: int = SEED, clock: Callable[[], float] = time.perf_counter) -> list[dict]:
    """도우미에 넣을 흐름 그대로 질문 하나를 처음부터 끝까지 잰다(HISTORY [122]). ways는 방식 이름 → (지시, 동시에 부를 모델들).
    모델 n개를 동시에 부르고 → 검색어 n개를 임베딩 한 번에 보내고 → 검색어마다 찾고 → n이 2 이상이면 RRF로 합친다.
    방식 순서는 질문마다 섞는다(시간대에 따라 바뀌는 응답 속도가 한 방식에만 몰리지 않게).
    "호출별"에 호출마다 걸린 시간과 그 검색어의 순위를 남긴다(먼저 온 몇 개만 쓰는 방식을 새 호출 없이 따져 보려고).
    OpenAIModel·OpenAIEmbedder는 부를 때마다 새로 연결하므로, 잰 시간에는 연결을 맺는 시간(이 PC에서 약 0.03초)도 들어 있다."""
    shuffler = random.Random(seed)
    rows = []
    with ThreadPoolExecutor(max_workers=max(len(chats) for _, chats in ways.values())) as pool:
        for round_number in range(1, rounds + 1):
            for question in questions:
                order = list(ways.items())
                shuffler.shuffle(order)
                for way, (prompt, chats) in order:
                    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": question.question}]

                    def timed(chat: Chat) -> tuple[str, float]:
                        began = clock()
                        answer = chat.ask(messages)
                        return answer, clock() - began

                    start = clock()
                    answers = list(pool.map(timed, chats))
                    asked = clock()
                    queries = [_parsed(answer, f"{question.id} {round_number}회차")["query"] for answer, _ in answers]
                    vectors = embedder.embed(queries, TIMEOUT)
                    embedded = clock()
                    rankings = [searcher.search(condition, query, vector).final for query, vector in zip(queries, vectors)]
                    searched = clock()
                    final = rrf_merge(rankings) if len(chats) > 1 else rankings[0][:RRF_DEPTH]
                    done = clock()
                    rows.append({
                        "회차": round_number, "질문": question.id, "조건": f"흐름 / {way}", "원래 질문": question.question,
                        "검색어": queries, "결과": final,
                        "호출별": [{"초": seconds, "검색어": query, "결과": ranking[:RRF_DEPTH]}
                                  for (_, seconds), query, ranking in zip(answers, queries, rankings)],
                        "시간": {"질문 바꾸기": asked - start, "임베딩": embedded - asked, "검색": searched - embedded,
                                 "합치기": done - searched, "전체": done - start},
                    })
    return rows


def _parsed(answer: str, label: str) -> dict:
    """질문 바꾸기 답(JSON)을 읽는다. 검색어가 없거나 분야 칸이 글자 목록이 아니면 멈춘다
    (빈 검색어나 한 글자씩 쪼개진 분야로 찾은 결과를 '못 찾음'으로 채점하지 않게). 분야 칸이 없으면 빈 목록."""
    got = json.loads(answer)
    query = got.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError(f"{label}: 검색어가 없는 답 {answer!r}")
    areas = {key: got.get(key) or [] for key in ("areas", "exclude")}
    if any(not isinstance(names, list) or not all(isinstance(name, str) for name in names) for names in areas.values()):
        raise ValueError(f"{label}: 분야 칸이 글자 목록이 아닌 답 {answer!r}")
    return {"query": query.strip(), **areas}


def load_rewrites(path: Path) -> dict[tuple[int, str], dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {(row["회차"], row["질문"]): row for row in rows}


def beginner_mask(pool: Sequence[PoolChunk], scope_path: Path) -> np.ndarray:
    """초보자 범위(쪽 단위 분류 파일의 include 쪽)에 드는 청크."""
    beginner = {row["path"] for row in map(json.loads, scope_path.read_text(encoding="utf-8").splitlines()) if row["include"]}
    return np.array([chunk.key.split(".html")[0] in beginner for chunk in pool])


@dataclass(frozen=True)
class Measured:
    rows: list[dict]  # 회차 × 질문 × 조건마다 한 줄
    warmups: list[dict]  # 모델마다 본 측정 전에 한 번 부른 시간(측정 표본에 넣지 않음)


def measure(
    questions: Sequence[Question], chosen: Sequence[Condition], searcher: Searcher, embedders: Mapping[str, Embedder],
    names: Names, rounds: int = ROUNDS, seed: int = SEED, clock: Callable[[], float] = time.perf_counter,
    rewrites: Mapping[tuple[int, str], dict] | None = None, rewritten_query: bool = False,
) -> Measured:
    """회차마다 질문 하나에 조건을 모두(질문마다 섞은 순서로) 돌린 뒤 다음 질문으로 간다.
    질문 임베딩은 저장한 것을 쓰지 않고 매번 새로 부른다. 상위 4·6·8개는 같은 결과에서 채점한다(다시 돌리지 않음).
    rewrites(질문 바꾸기 결과)가 있으면 질문 분야 범위에 그 분야를 쓰고, rewritten_query면 검색어도 바꾼 것을 쓴다."""

    def query_for(round_number: int, question: Question) -> str:
        if rewritten_query:
            return rewrites[(round_number, question.id)]["검색어"]
        return query_of(question.question, names)

    shuffler = random.Random(seed)
    warmups = []
    for model in dict.fromkeys(condition.model for condition in chosen):
        start = clock()
        embedders[model].embed([query_for(1, questions[0])], TIMEOUT)
        warmups.append({"모델": model, "질문": questions[0].id, "초": clock() - start})
    rows = []
    for round_number in range(1, rounds + 1):
        for question in questions:
            query = query_for(round_number, question)
            row = rewrites[(round_number, question.id)] if rewrites else None
            picked = Picked(tuple(row["분야"]), tuple(row["뺄 분야"])) if row else None
            order = list(chosen)
            shuffler.shuffle(order)
            for condition in order:
                start = clock()
                (vector,) = embedders[condition.model].embed([query], TIMEOUT)
                embedded = clock()
                found = searcher.search(condition, query, vector, picked)
                done = clock()
                rows.append({
                    "회차": round_number, "질문": question.id, "조건": condition.name,
                    "원래 질문": question.question, "검색어": query,
                    "남은 청크": int(searcher.keep(condition.scope, picked).sum()),
                    "시간": {"질문 임베딩": embedded - start, **found.seconds, "전체": done - start},
                    "결과": found.final[:RRF_DEPTH], "부분": found.parts,
                })
    return Measured(rows, warmups)


def summarize(rows: Sequence[dict], questions: Sequence[Question], k: int) -> list[dict]:
    """조건마다 상위 k개 채점(1회차 순위로) + 전체 시간 중앙값·최대값(모든 회차). 찾은 비율이 높은 차례.
    찾은 비율은 질문마다 필요한 근거 중 찾은 비율의 평균이라, 질문마다 비중이 같다."""
    by_id = {question.id: question for question in questions}
    lines = []
    for name in dict.fromkeys(row["조건"] for row in rows):
        mine = [row for row in rows if row["조건"] == name]
        hits = {row["질문"]: hit(by_id[row["질문"]].groups, row["결과"], k) for row in mine if row["회차"] == 1}
        rankings: dict[str, set] = {}
        for row in mine:
            rankings.setdefault(row["질문"], set()).add(tuple(row["결과"]))

        def mean(translated: bool | None) -> float | None:
            ratios = [found.ratio for qid, found in hits.items() if translated in (None, by_id[qid].translated)]
            return statistics.mean(ratios) if ratios else None

        seconds = [row["시간"]["전체"] for row in mine]
        lines.append({
            "조건": name, "찾은 비율": mean(None), "전부 찾은 질문": sum(found.full for found in hits.values()),
            "일부라도 찾은 질문": sum(found.partial for found in hits.values()),
            "번역 있음": mean(True), "번역 없음": mean(False),
            "질문별": {qid: (found.found, found.needed, found.first_rank) for qid, found in hits.items()},
            "회차마다 순위 다름": sorted(qid for qid, seen in rankings.items() if len(seen) > 1),
            "중앙값": statistics.median(seconds), "최대값": max(seconds),
        })
    return sorted(lines, key=lambda line: (-line["찾은 비율"], -line["전부 찾은 질문"]))


def estimate(pool: Sequence[PoolChunk], questions: Sequence[Question], models: Sequence[str], rounds: int) -> list[str]:
    """유료 모델의 어림 토큰·비용(어림 토큰은 translate와 같은 셈). 저장된 DB를 재사용하면 DB 몫은 실제로 들지 않는다."""
    lines = []
    for model in models:
        if model not in PRICE_PER_MILLION:
            continue
        db_tokens = sum(_tokens(chunk.english) for chunk in pool) + sum(
            _tokens(chunk.korean) + _tokens(f"{chunk.english}\n\n{chunk.korean}") for chunk in pool if chunk.korean
        )
        calls = rounds * len(questions) * len(Text) * len(Bm25) + 1  # 질문 처리 + 준비 운동 1번
        query_tokens = statistics.mean(_tokens(question.question) for question in questions) * calls
        dollars = (db_tokens + query_tokens) / 1_000_000 * PRICE_PER_MILLION[model]
        lines.append(
            f"{model}: DB 글 약 {db_tokens:,}토큰 + 질문 {calls}회 약 {query_tokens:,.0f}토큰 → 약 ${dollars:.4f}"
            f" (요금 ${PRICE_PER_MILLION[model]}/100만 토큰, 저장된 DB를 재사용하면 DB 몫은 들지 않음)"
        )
    return lines


class BgeEmbedder:
    """로컬 BGE-M3의 뜻 벡터(dense)만 쓴다(CPU). 처음 불러오는 시간을 따로 남긴다."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer  # 무거운 설치 묶음(compare)이라 쓸 때만 불러온다

        start = time.perf_counter()
        self._model = SentenceTransformer("BAAI/bge-m3", device="cpu")
        self.load_seconds = time.perf_counter() - start

    def embed(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        """timeout은 받기만 한다(내 PC에서 계산해 멈출 바깥 서비스가 없음)."""
        return self._model.encode(list(texts), normalize_embeddings=True).tolist()


def _real_embedder(model: str) -> Embedder:
    if model in LOCAL_MODELS:
        return LocalEmbedder(model)
    if model == "bge-m3":
        return BgeEmbedder()
    if model == "text-embedding-3-large":
        return OpenAIEmbedder(model, openai_key())
    raise SystemExit(f"모르는 모델: {model} (고를 수 있는 것: {', '.join((*MODELS, *LOCAL_MODELS))})")


def _load_names() -> MenuNames:
    titles = MenuNames.load_titles(PROJECT / "menu_titles.json")
    return MenuNames.load(DATA / "menu_names" / "menu_names.json", MenuNames.load_choices(PROJECT / "menu_choices.json"), titles)


def main(
    argv: Sequence[str] | None = None, now: datetime | None = None,
    make_embedder: Callable[[str], Embedder] = _real_embedder, load_names: Callable[[], Names] = _load_names,
    make_chat: Callable[[str, str, str | None], Chat] = lambda model, effort, tier: OpenAIModel(model, openai_key(), effort, tier=tier),
) -> int:
    """명령 줄 입구. 돌려주는 값은 종료 코드(0 성공, 1 결과 폴더가 이미 있음, 2 유료 실행에 --yes가 없음)."""
    parser = argparse.ArgumentParser(description="검색 조건 18개를 같은 질문·청크 묶음으로 견줍니다(티켓 40).")
    commands = parser.add_subparsers(dest="command", required=True)
    estimate_command = commands.add_parser("estimate", help="유료 임베딩의 어림 비용을 보인다")
    build_command = commands.add_parser("build-db", help="검색용 DB를 만들거나 저장된 것을 재사용한다")
    run_command = commands.add_parser("run", help="질문 × 회차 × 조건을 돌려 결과 폴더에 쓴다")
    rewrite_command = commands.add_parser("rewrite", help="질문을 영어 검색어로 바꿔 결과 폴더에 쓴다(유료, run --queries로 씀)")
    fuse_command = commands.add_parser("fuse", help="run 결과의 회차별 순위를 RRF로 합쳐 다시 채점한다(새 호출 없음)")
    full_command = commands.add_parser("full-pool", help="설명서 전체 묶음 파일을 쓰고 도우미용 벡터를 DB로 옮긴다(새 호출 없음)")
    full_command.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl", help="청크 파일")
    full_command.add_argument("--pool", type=Path, default=COMPARE / "pool" / "pool_full.jsonl", help="쓸 묶음 파일")
    full_command.add_argument("--db", type=Path, default=COMPARE / "db", help="검색용 DB 폴더")
    full_command.add_argument("--model", default="text-embedding-3-large", help="옮길 도우미용 벡터의 모델")
    full_command.add_argument("--vectors", type=Path, help="도우미용 벡터 파일(기본 data/vectors/manual_<모델>.npz)")
    flow_command = commands.add_parser("flow", help="질문 바꾸기 → 임베딩 → 검색(→ 합치기)을 도우미 흐름대로 처음부터 끝까지 잰다(유료)")
    for command in (estimate_command, build_command, run_command, rewrite_command, fuse_command, flow_command):
        command.add_argument("--models", nargs="+", default=list(MODELS), help="임베딩 모델")
        command.add_argument("--pool", type=Path, default=COMPARE / "pool" / "pool_v1.jsonl", help="검색 묶음 파일")
        command.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl", help="청크 파일")
        command.add_argument("--translations", type=Path, default=DATA / "translations" / "ko_none.jsonl", help="번역(고친 줄 파일을 덮어 읽음)")
        command.add_argument("--questions", type=Path, nargs="+", help="질문 파일들",
                             default=[COMPARE / "questions" / "web_questions.jsonl", COMPARE / "questions" / "ai_questions.jsonl"])
        command.add_argument("--rounds", type=int, default=ROUNDS, help="질문마다 잴 회차")
    for command in (build_command, run_command, flow_command):
        command.add_argument("--db", type=Path, default=COMPARE / "db", help="검색용 DB 폴더")
        command.add_argument("--yes", action="store_true", help="어림 비용을 보고 확인받았다(유료 모델에 필요)")
        command.add_argument("--original-only", action="store_true", help="영어 원문만·BM25 끔 한 조건으로 비교한다(로컬 후보·메뉴 이름 덧붙이기 비교)")
    for command in (run_command, rewrite_command, fuse_command, flow_command):
        command.add_argument("--name", required=True, help="결과 폴더 이름(results/<날짜>/<시각>_<이름>)")
        command.add_argument("--results", type=Path, default=PROJECT / "results", help="결과를 쓸 폴더")
        command.add_argument("--note", required=True, help="측정 환경(PC·Blender에 연 파일·함께 켠 프로그램)")
    rewrite_command.add_argument("--chat", choices=list(REWRITE_PRICE), default="gpt-6-luna", help="질문을 바꿀 모델")
    rewrite_command.add_argument("--effort", default="none", help="생각 수준(도우미 기본 none)")
    rewrite_command.add_argument("--yes", action="store_true", help="어림 비용을 보고 확인받았다")
    rewrite_command.add_argument("--prompt", choices=list(PROMPTS), default="rewrite",
                                 help="rewrite 검색어·분야로 바꾸기, translate 영어로 옮기기만(분야 없음)")
    flow_command.add_argument("--chat", choices=list(REWRITE_PRICE), default="gpt-6-luna", help="질문을 바꿀 모델")
    flow_command.add_argument("--effort", default="none", help="생각 수준(도우미 기본 none)")
    flow_command.add_argument("--seed", type=int, default=SEED, help="방식 순서를 섞는 씨앗")
    flow_command.add_argument("--ways", nargs="+", choices=list(FLOW_WAYS), default=["한 번 바꾸기", "3번 합치기"],
                              help="잴 방식(지시·동시 호출 수·처리 등급, FLOW_WAYS)")
    fuse_command.add_argument("--runs", type=Path, required=True, help="합칠 run 결과 폴더(실행.jsonl·설정.json)")
    run_command.add_argument("--seed", type=int, default=SEED, help="조건 순서를 섞는 씨앗")
    run_command.add_argument("--rewrites", type=Path, help="rewrite가 만든 검색어.jsonl(질문 분야 범위에 그 분야를 쓴다)")
    run_command.add_argument("--rewritten-query", action="store_true", help="메뉴 이름 덧붙이기 대신 --rewrites의 영어 검색어로 찾는다")
    run_command.add_argument("--with-bm25", action="store_true", help="--original-only에 BM25 영어 원문을 켠 조건도 더한다")
    run_command.add_argument("--scopes", nargs="+", choices=[scope.name.lower() for scope in Scope], default=["all"],
                             help="검색 전에 남길 청크: all 전체, asked 질문 분야만, others 질문 보고 뺀 나머지, beginner 초보자 범위만")
    run_command.add_argument("--scope-file", type=Path, default=DATA / "beginner_scope" / "scope.jsonl", help="초보자 범위 분류 파일")
    run_command.add_argument("--menu-names", choices=("all", "narrow", "off"), default="all",
                             help="질문에 붙일 영어 메뉴 이름: all 사전에서 찾은 것 모두, narrow 소리대로 적은 이름만, off 붙이지 않음")
    args = parser.parse_args(argv)
    if args.command == "full-pool":
        index = full_pool(args.chunks, args.pool, args.db, args.model, args.vectors or manual_vectors.path_for(args.model))
        print(f"묶음: {args.pool}\nDB: {index.records[0]['파일']} ({index.records[0]['상태']})")
        return 0

    translations = reviewed(args.translations)
    pool = load_pool(args.pool, args.chunks, translations)
    questions = load_questions(args.questions, pool)
    now = now or datetime.now()
    if args.command == "rewrite":
        return _rewrite_command(args, pool, questions, make_chat, now)
    if args.command == "fuse":
        return _fuse_command(args, questions, now)
    if args.command == "flow":
        return _flow_command(args, pool, questions, make_embedder, make_chat, now)
    costs = estimate(pool, questions, args.models, args.rounds)
    if args.command == "estimate":
        print("\n".join(costs or ["유료 모델 없음"]))
        return 0
    if costs and not _confirmed(costs, args.yes):
        return 2
    folder = _new_folder(args, now) if args.command == "run" else None
    if args.command == "run" and folder is None:
        return 1
    embedders = {model: make_embedder(model) for model in args.models}
    indexes = {model: build_index(pool, model, embedders[model], args.db, args.original_only) for model in args.models}
    for index in indexes.values():
        for record in index.records:
            print(f"DB {record['모델']} {record['글']}: {record['상태']} ({record['파일']})")
    if args.command == "build-db":
        return 0

    scopes = [Scope[name.upper()] for name in args.scopes]
    if args.original_only:
        bm25s = (Bm25.OFF, Bm25.ENGLISH) if args.with_bm25 else (Bm25.OFF,)
        chosen = [Condition(model, Text.ORIGINAL, bm25, scope) for model in args.models for bm25 in bm25s for scope in scopes]
    else:
        chosen = conditions(args.models)
    if (args.rewritten_query or {Scope.ASKED, Scope.OTHERS} & set(scopes)) and not args.rewrites:
        parser.error("--rewritten-query와 asked·others 범위는 --rewrites가 있어야 합니다.")
    masks = {Scope.BEGINNER: beginner_mask(pool, args.scope_file)} if Scope.BEGINNER in scopes else {}
    rewrites = load_rewrites(args.rewrites) if args.rewrites else None
    names = {"all": load_names, "narrow": lambda: NarrowNames(load_names()), "off": NoNames}[args.menu_names]()
    started = datetime.now().isoformat(timespec="seconds")
    measured = measure(questions, chosen, Searcher(pool, indexes, scopes=masks), embedders, names, args.rounds, args.seed,
                       rewrites=rewrites, rewritten_query=args.rewritten_query)
    paid = {
        model: {"토큰": embedder.tokens, "요청": embedder.requests,
                "달러": round(embedder.tokens / 1_000_000 * PRICE_PER_MILLION[model], 6)}
        for model, embedder in embedders.items() if model in PRICE_PER_MILLION
    }
    about = {
        "조건": [condition.name for condition in chosen], "모델": args.models,
        "묶음 파일": str(args.pool), "묶음 해시": hashlib.sha256(args.pool.read_bytes()).hexdigest()[:12],
        "청크 수": len(pool), "번역 있는 청크 수": sum(bool(chunk.korean) for chunk in pool),
        "질문 파일": [str(path) for path in args.questions], "질문 수": len(questions), "번역 파일": str(args.translations),
        "회차": args.rounds, "씨앗": args.seed, "상위 개수": list(TOP_KS), "RRF_K": RRF_K, "RRF_DEPTH": RRF_DEPTH,
        "DB": [record for index in indexes.values() for record in index.records],
        "모델 불러오기 초": {model: embedder.load_seconds for model, embedder in embedders.items() if hasattr(embedder, "load_seconds")},
        "로컬 모델 설정": {model: embedder.metadata for model, embedder in embedders.items() if hasattr(embedder, "metadata")},
        "준비 운동": measured.warmups, "메뉴 이름 덧붙이기": "쓰지 않음(바꾼 검색어)" if args.rewritten_query else args.menu_names,
        "질문 바꾸기 파일": str(args.rewrites) if args.rewrites else None, "유료": paid, "메모": args.note,
        "pc": platform.node(), "운영체제": platform.platform(), "프로세서": platform.processor(),
        "시작 시각": started, "커밋": _commit(),
    }
    folder.mkdir(parents=True)
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "실행.jsonl").open("w", encoding="utf-8") as file:
        for row in measured.rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    (folder / "요약.md").write_text(_summary_markdown(args.name, measured.rows, questions, about), encoding="utf-8")
    print(f"결과: {folder}")
    return 0


class StoredVectors:
    """도우미용 벡터 파일(manual_vectors)에서 청크 글로 벡터를 찾아 돌려준다(API를 부르지 않음)."""

    def __init__(self, chunks: Sequence[Chunk], vectors: np.ndarray):
        self._by_text = {chunk.text: vector for chunk, vector in zip(chunks, vectors)}

    def embed(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        return [self._by_text[text].tolist() for text in texts]


def full_pool(chunks_path: Path, pool_path: Path, db: Path, model: str, vectors_path: Path) -> Index:
    """설명서 전체 청크로 묶음 파일을 쓰고(이미 있으면 같은지 확인), 도우미용 벡터를 비교 프로그램 DB로 옮긴다(HISTORY [117]).
    manual_vectors.load가 지금 청크 파일과 열쇠·글 해시가 모두 같을 때만 읽으므로, 옮긴 벡터는 같은 글로 만든 것이다."""
    chunks = load_chunks(chunks_path)
    lines = "".join(json.dumps({"key": piece.key}) + "\n" for piece in pieces(chunks))
    if pool_path.exists() and pool_path.read_text(encoding="utf-8") != lines:
        raise ValueError(f"{pool_path}가 이미 있고 지금 청크와 다릅니다(덮어쓰지 않음). 옛 파일을 archive/로 옮긴 뒤 다시 만드세요.")
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(lines, encoding="utf-8")
    vectors = manual_vectors.load(vectors_path, chunks)
    index = build_index(load_pool(pool_path, chunks_path, {}), model, StoredVectors(chunks, vectors), db, original_only=True)
    record = index.records[0]
    meta = db / record["파일"].replace(".npz", ".json")
    saved = json.loads(meta.read_text(encoding="utf-8"))
    if "출처" not in saved:
        made = json.loads(vectors_path.with_suffix(".json").read_text(encoding="utf-8"))["만든 시각"]
        saved["출처"] = f"{vectors_path.name}(만든 시각 {made}, 청크 글 해시 일치 확인)을 옮김. 새 API 호출 없음"
        meta.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _new_folder(args: argparse.Namespace, now: datetime) -> Path | None:
    """results/<날짜>/<시각>_<이름>. 이미 있으면 알리고 None(결과는 덮어쓰지 않음). 폴더는 측정이 끝난 뒤 만든다
    (도중에 멈추면 빈 폴더가 다시 돌리기를 막지 않게)."""
    folder = args.results / f"{now:%Y%m%d}" / f"{now:%H%M%S}_{args.name}"
    if folder.exists():
        print(f"{folder}가 이미 있어 멈춥니다(결과는 덮어쓰지 않음). 다른 --name을 주세요.", file=sys.stderr)
        return None
    return folder


def _confirmed(costs: Sequence[str], yes: bool) -> bool:
    """유료 실행은 어림 비용을 보고 확인받은 뒤(--yes)에만 한다."""
    if not yes:
        print("\n".join([*costs, "유료라 멈춥니다. 비용을 확인받은 뒤 --yes를 붙여 주세요."]), file=sys.stderr)
    return yes


def _rewrite_command(args: argparse.Namespace, pool: Sequence[PoolChunk], questions: Sequence[Question],
                     make_chat: Callable[[str, str, str | None], Chat], now: datetime) -> int:
    """질문 바꾸기: 어림 비용을 보이고(--yes 없으면 멈춤) 회차마다 바꾼 검색어·시간·토큰을 새 폴더에 쓴다."""
    template = PROMPTS[args.prompt]
    calls = len(questions) * args.rounds
    tokens_in = calls * (_tokens(template) + 600)  # 분야 목록 약 500, 질문 한 줄 약 80토큰으로 어림
    tokens_out = calls * 120
    price_in, price_out = REWRITE_PRICE[args.chat]
    guess = f"{args.chat}: {calls}번 물음, 약 입력 {tokens_in:,}·출력 {tokens_out:,}토큰 → 약 ${(tokens_in * price_in + tokens_out * price_out) / 1_000_000:.4f}"
    if not _confirmed([guess], args.yes):
        return 2
    folder = _new_folder(args, now)
    if folder is None:
        return 1
    chat = make_chat(args.chat, args.effort, None)
    started = datetime.now().isoformat(timespec="seconds")
    areas = sorted({area_of(chunk.key.split(".html")[0]) for chunk in pool})
    rows = rewrite(questions, chat, areas, args.rounds, template=template)
    seconds = [row["초"] for row in rows]
    about = {
        "모델": args.chat, "생각 수준": args.effort, "지시 종류": args.prompt, "지시": template.format(areas="\n".join(areas)), "분야 수": len(areas),
        "어림": guess,
        "질문 파일": [str(path) for path in args.questions], "질문 수": len(questions), "회차": args.rounds,
        "토큰": {"입력": chat.input_tokens, "출력": chat.output_tokens},
        "달러": round((chat.input_tokens * price_in + chat.output_tokens * price_out) / 1_000_000, 6),
        "시간": {"중앙값": statistics.median(seconds), "최대값": max(seconds)},
        "메모": args.note, "pc": platform.node(), "시작 시각": started, "커밋": _commit(),
    }
    folder.mkdir(parents=True)
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "검색어.jsonl").open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"결과: {folder}\n{guess}\n실제: 입력 {chat.input_tokens:,}·출력 {chat.output_tokens:,}토큰, ${about['달러']}")
    return 0


def _fuse_command(args: argparse.Namespace, questions: Sequence[Question], now: datetime) -> int:
    """run 결과 폴더의 회차별 순위를 합친 조건을 원래 조건과 같은 표로 채점해 새 폴더에 쓴다."""
    folder = _new_folder(args, now)
    if folder is None:
        return 1
    source = json.loads((args.runs / "설정.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (args.runs / "실행.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    fused = fuse_rounds(rows)
    about = {
        **source, "조건": [*source["조건"], *dict.fromkeys(row["조건"] for row in fused)], "유료": {},
        "합친 run": str(args.runs), "합치기": f"조건·질문마다 회차별 상위 {RRF_DEPTH}개를 RRF(K={RRF_K})로 합침. 합친 조건의 시간은 run이 잰 "
              "임베딩·검색 시간 중 가장 느린 회차(질문 바꾸기 시간은 들어 있지 않음)",
        "메모": args.note, "시작 시각": datetime.now().isoformat(timespec="seconds"), "커밋": _commit(),
    }
    folder.mkdir(parents=True)
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "실행.jsonl").open("w", encoding="utf-8") as file:
        for row in fused:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    (folder / "요약.md").write_text(_summary_markdown(args.name, [*rows, *fused], questions, about), encoding="utf-8")
    print(f"결과: {folder}")
    return 0


def _flow_command(args: argparse.Namespace, pool: Sequence[PoolChunk], questions: Sequence[Question],
                  make_embedder: Callable[[str], Embedder], make_chat: Callable[[str, str, str | None], Chat], now: datetime) -> int:
    """흐름 측정: 모델 하나·원문만·BM25 끔·범위 전체. 어림 비용을 보이고(--yes 없으면 멈춤) 결과를 새 폴더에 쓴다."""
    if len(args.models) != 1:
        raise SystemExit("flow는 임베딩 모델 하나로만 잽니다(--models 하나).")
    model = args.models[0]
    areas = sorted({area_of(chunk.key.split(".html")[0]) for chunk in pool})
    prompts = {way: PROMPTS[FLOW_WAYS[way].prompt].format(areas="\n".join(areas)) for way in args.ways}
    price_in, price_out = REWRITE_PRICE[args.chat]

    def dollars(way: str, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in * price_in + tokens_out * price_out) * TIER_FACTOR[FLOW_WAYS[way].tier] / 1_000_000

    guesses = {}
    for way in args.ways:
        calls = len(questions) * args.rounds * FLOW_WAYS[way].count
        tokens_in, tokens_out = calls * (_tokens(prompts[way]) + 80), calls * 60  # 질문 한 줄 약 80, 답 약 54토큰([117])
        guesses[way] = f"{args.chat} {way}: {calls}번 물음, 약 입력 {tokens_in:,}·출력 {tokens_out:,}토큰 → 약 ${dollars(way, tokens_in, tokens_out):.4f}"
    costs = [*guesses.values(), "+ 검색어 임베딩(아주 적음)"]
    if model in PRICE_PER_MILLION:
        db_tokens = sum(_tokens(chunk.english) for chunk in pool)
        costs.append(f"{model} DB: 저장된 것이 없으면 새로 만듦, 약 {db_tokens:,}토큰 → 약 "
                     f"${db_tokens / 1_000_000 * PRICE_PER_MILLION[model]:.4f}(저장된 DB를 재사용하면 들지 않음)")
    if not _confirmed(costs, args.yes):
        return 2
    folder = _new_folder(args, now)
    if folder is None:
        return 1
    embedder = make_embedder(model)
    index = build_index(pool, model, embedder, args.db, original_only=True)
    chats = {way: [make_chat(args.chat, args.effort, FLOW_WAYS[way].tier) for _ in range(FLOW_WAYS[way].count)] for way in args.ways}
    started = datetime.now().isoformat(timespec="seconds")
    rows = flow(questions, {way: (prompts[way], chats[way]) for way in args.ways}, embedder, Searcher(pool, {model: index}),
                Condition(model, Text.ORIGINAL, Bm25.OFF), args.rounds, args.seed)
    stages = {
        way: {stage: {"중앙값": statistics.median(values), "최대값": max(values)}
              for stage in rows[0]["시간"] for values in [[row["시간"][stage] for row in rows if row["조건"] == f"흐름 / {way}"]]}
        for way in args.ways
    }
    paid = {}
    for way, mine in chats.items():
        tokens = {"입력": sum(chat.input_tokens for chat in mine), "출력": sum(chat.output_tokens for chat in mine)}
        tiers = sum((chat.tiers for chat in mine), Counter())
        paid[f"{args.chat} {way}"] = {**tokens, "처리 등급": dict(tiers), "달러": round(dollars(way, tokens["입력"], tokens["출력"]), 6)}
    if model in PRICE_PER_MILLION:
        paid[model] = {"토큰": embedder.tokens, "요청": embedder.requests,
                       "달러": round(embedder.tokens / 1_000_000 * PRICE_PER_MILLION[model], 6)}
    about = {
        "조건": [f"흐름 / {way}" for way in args.ways], "모델": [model], "질문 바꾸기 모델": args.chat, "생각 수준": args.effort,
        "방식": {way: {"지시 종류": FLOW_WAYS[way].prompt, "동시 호출": FLOW_WAYS[way].count, "처리 등급": FLOW_WAYS[way].tier}
                 for way in args.ways},
        "지시": {FLOW_WAYS[way].prompt: prompts[way] for way in args.ways}, "묶음 파일": str(args.pool), "청크 수": len(pool),
        "번역 있는 청크 수": 0, "질문 파일": [str(path) for path in args.questions], "질문 수": len(questions),
        "회차": args.rounds, "씨앗": args.seed, "DB": index.records, "어림": costs, "단계별 시간": stages, "유료": paid,
        "메모": args.note, "pc": platform.node(), "시작 시각": started, "커밋": _commit(),
    }
    folder.mkdir(parents=True)
    (folder / "설정.json").write_text(json.dumps(about, ensure_ascii=False, indent=2), encoding="utf-8")
    with (folder / "실행.jsonl").open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    lines = ["", "## 단계별 시간(초, 모든 회차)", "", "| 방식 | 단계 | 중앙값 | 최대값 |", "|---|---|---|---|"]
    lines += [f"| {way} | {stage} | {value['중앙값']:.3f} | {value['최대값']:.3f} |"
              for way, table in stages.items() for stage, value in table.items()]
    (folder / "요약.md").write_text(_summary_markdown(args.name, rows, questions, about) + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"결과: {folder}\n" + "\n".join(costs) + f"\n실제: {paid}")
    return 0


def _summary_markdown(name: str, rows: Sequence[dict], questions: Sequence[Question], about: dict) -> str:
    """상위 4·6·8개마다 조건 비교표(찾은 비율 높은 차례)와 질문별 표, 그리고 해석할 때의 한계."""
    chunks, translated = about["청크 수"], about["번역 있는 청크 수"]
    lines = [
        f"# {name}", "",
        f"질문 {about['질문 수']}개 × 회차 {about['회차']} × 조건 {len(about['조건'])}개. 채점은 1회차 순위, 시간은 모든 회차.",
        f"묶음 {chunks}청크(번역 있음 {translated}개). 유료: {about['유료'] or '없음'}", "",
        "## 해석할 때 주의", "",
        f"- {chunks:,}청크·{about['질문 수']}문항의 작은 실험이다. 질문마다 필요한 근거 수·난이도가 달라 몇 문항이 결과를 크게 움직인다.",
        "- BM25는 한국어를 두 글자씩, 영어를 낱말로 자른다. 번역 포함 BM25의 효과에는 이 한국어 처리의 영향이 함께 들어 있다.",
    ]
    if translated:
        lines.append(f"- 묶음의 번역 비율은 {translated / chunks:.0%}다(설명서 전체는 약 15%). 비율이 다르면 전체 설명서의 성능으로 읽지 않는다.")
    if "합치기" in about:
        lines.append(f"- {about['합치기']}.")
    if "단계별 시간" in about:
        lines.append("- 흐름 시간에는 호출마다 새로 연결을 맺는 시간이 들어 있다.")
    lines += [
        f"- 처음 정답 순위는 남긴 상위 {RRF_DEPTH}개 안에서만 센다(BM25를 켜면 RRF에 든 청크만).",
        "- '회차마다 순위 다름'은 같은 질문의 2·3회차 순위가 1회차와 달랐던 질문이다(임베딩이 매번 조금 달라질 때).", "",
    ]
    for k in TOP_KS:
        summary = summarize(rows, questions, k)
        lines += [f"## 상위 {k}개", "", "| 차례 | 조건 | 찾은 비율 | 전부 찾은 질문 | 일부라도 | 번역 있음 | 번역 없음 | 중앙값(초) | 최대값(초) | 회차마다 순위 다름 |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for number, line in enumerate(summary, start=1):
            lines.append(
                f"| {number} | {line['조건']} | {line['찾은 비율']:.3f} | {line['전부 찾은 질문']} | {line['일부라도 찾은 질문']} | "
                f"{_ratio(line['번역 있음'])} | {_ratio(line['번역 없음'])} | {line['중앙값']:.3f} | {line['최대값']:.3f} | "
                f"{', '.join(line['회차마다 순위 다름']) or '-'} |"
            )
        lines += ["", f"질문별(찾은 근거/필요 근거, 처음 정답 순위). 열 번호는 위 표의 차례.", "",
                  "| 질문 | 번역 | " + " | ".join(str(number) for number in range(1, len(summary) + 1)) + " |",
                  "|---|---|" + "---|" * len(summary)]
        for question in questions:
            cells = []
            for line in summary:
                found, needed, first = line["질문별"][question.id]
                cells.append(f"{found}/{needed} ({first or '-'})")
            lines.append(f"| {question.id} | {'있음' if question.translated else '없음'} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def _ratio(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    sys.exit(main())
