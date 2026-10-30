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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import product
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from blender_tutor.answer_engine import RRF_DEPTH, RRF_K, Embedder, _normalized
from blender_tutor.beginner_scope import openai_key
from blender_tutor.evaluate import _commit
from blender_tutor.manual_chunks import load_chunks
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


@dataclass(frozen=True)
class Condition:
    model: str
    text: Text
    bm25: Bm25

    @property
    def name(self) -> str:
        return f"{self.model} / {self.text} / {self.bm25}"


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

    def __init__(self, pool: Sequence[PoolChunk], indexes: Mapping[str, Index], clock: Callable[[], float] = time.perf_counter):
        self._keys = [chunk.key for chunk in pool]
        self._indexes = indexes
        self._clock = clock
        self._bm25 = {
            Bm25.ENGLISH: BM25Okapi([bm25_words(chunk.english) for chunk in pool]),
            Bm25.BOTH: BM25Okapi([bm25_words(f"{chunk.english}\n\n{chunk.korean or ''}") for chunk in pool]),
        }

    def search(self, condition: Condition, query: str, vector: Sequence[float]) -> Search:
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
        meaning_order = np.argsort(-meaning, kind="stable")
        parts["뜻"] = self._top(meaning)
        meaning_done = self._clock()
        if condition.bm25 is Bm25.OFF:
            final = [self._keys[index] for index in meaning_order]
            return Search(final, parts, {"뜻 검색": meaning_done - start, "BM25": 0.0, "RRF": 0.0})
        scores = self._bm25[condition.bm25].get_scores(bm25_words(query))
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

    def _top(self, scores: np.ndarray) -> list[tuple[str, float]]:
        """점수 높은 차례 상위 RRF_DEPTH개(점수가 없는 청크는 뺀다)."""
        order = np.argsort(-scores, kind="stable")[:RRF_DEPTH]
        return [(self._keys[index], round(float(scores[index]), 6)) for index in order if np.isfinite(scores[index])]


class Names:
    """질문 속 한국어 메뉴 이름에 붙일 영어 이름을 찾는 것(MenuNames와 같은 꼴)."""

    def english_in(self, text: str) -> tuple[str, ...]: ...


class NoNames:
    """메뉴 이름을 덧붙이지 않을 때(--no-menu-names): 원래 질문 그대로 검색한다."""

    def english_in(self, text: str) -> tuple[str, ...]:
        return ()


def query_of(question: str, names: Names) -> str:
    """실제 검색어: 질문 뒤에 사전으로 찾은 영어 메뉴 이름을 덧붙인다(도우미의 검색어 첫 줄과 같음)."""
    return " ".join((question, *names.english_in(question)))


@dataclass(frozen=True)
class Measured:
    rows: list[dict]  # 회차 × 질문 × 조건마다 한 줄
    warmups: list[dict]  # 모델마다 본 측정 전에 한 번 부른 시간(측정 표본에 넣지 않음)


def measure(
    questions: Sequence[Question], chosen: Sequence[Condition], searcher: Searcher, embedders: Mapping[str, Embedder],
    names: Names, rounds: int = ROUNDS, seed: int = SEED, clock: Callable[[], float] = time.perf_counter,
) -> Measured:
    """회차마다 질문 하나에 조건을 모두(질문마다 섞은 순서로) 돌린 뒤 다음 질문으로 간다.
    질문 임베딩은 저장한 것을 쓰지 않고 매번 새로 부른다. 상위 4·6·8개는 같은 결과에서 채점한다(다시 돌리지 않음)."""
    shuffler = random.Random(seed)
    warmups = []
    for model in dict.fromkeys(condition.model for condition in chosen):
        start = clock()
        embedders[model].embed([query_of(questions[0].question, names)], TIMEOUT)
        warmups.append({"모델": model, "질문": questions[0].id, "초": clock() - start})
    rows = []
    for round_number in range(1, rounds + 1):
        for question in questions:
            query = query_of(question.question, names)
            order = list(chosen)
            shuffler.shuffle(order)
            for condition in order:
                start = clock()
                (vector,) = embedders[condition.model].embed([query], TIMEOUT)
                embedded = clock()
                found = searcher.search(condition, query, vector)
                done = clock()
                rows.append({
                    "회차": round_number, "질문": question.id, "조건": condition.name,
                    "원래 질문": question.question, "검색어": query,
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
) -> int:
    """명령 줄 입구. 돌려주는 값은 종료 코드(0 성공, 1 결과 폴더가 이미 있음, 2 유료 실행에 --yes가 없음)."""
    parser = argparse.ArgumentParser(description="검색 조건 18개를 같은 질문·청크 묶음으로 견줍니다(티켓 40).")
    commands = parser.add_subparsers(dest="command", required=True)
    estimate_command = commands.add_parser("estimate", help="유료 임베딩의 어림 비용을 보인다")
    build_command = commands.add_parser("build-db", help="검색용 DB를 만들거나 저장된 것을 재사용한다")
    run_command = commands.add_parser("run", help="질문 × 회차 × 조건을 돌려 결과 폴더에 쓴다")
    for command in (estimate_command, build_command, run_command):
        command.add_argument("--models", nargs="+", default=list(MODELS), help="임베딩 모델")
        command.add_argument("--pool", type=Path, default=COMPARE / "pool" / "pool_v1.jsonl", help="검색 묶음 파일")
        command.add_argument("--chunks", type=Path, default=DATA / "chunks" / "manual_chunks.jsonl", help="청크 파일")
        command.add_argument("--translations", type=Path, default=DATA / "translations" / "ko_none.jsonl", help="번역(고친 줄 파일을 덮어 읽음)")
        command.add_argument("--questions", type=Path, nargs="+", help="질문 파일들",
                             default=[COMPARE / "questions" / "web_questions.jsonl", COMPARE / "questions" / "ai_questions.jsonl"])
        command.add_argument("--rounds", type=int, default=ROUNDS, help="질문마다 잴 회차")
    for command in (build_command, run_command):
        command.add_argument("--db", type=Path, default=COMPARE / "db", help="검색용 DB 폴더")
        command.add_argument("--yes", action="store_true", help="어림 비용을 보고 확인받았다(유료 모델에 필요)")
        command.add_argument("--original-only", action="store_true", help="영어 원문만·BM25 끔 한 조건으로 비교한다(로컬 후보·메뉴 이름 덧붙이기 비교)")
    run_command.add_argument("--name", required=True, help="결과 폴더 이름(results/<날짜>_<이름>)")
    run_command.add_argument("--results", type=Path, default=PROJECT / "results", help="결과를 쓸 폴더")
    run_command.add_argument("--seed", type=int, default=SEED, help="조건 순서를 섞는 씨앗")
    run_command.add_argument("--note", required=True, help="측정 환경(PC·Blender에 연 파일·함께 켠 프로그램)")
    run_command.add_argument("--no-menu-names", action="store_true", help="질문에 영어 메뉴 이름을 덧붙이지 않는다(덧붙이기 효과 비교)")
    args = parser.parse_args(argv)

    translations = reviewed(args.translations)
    pool = load_pool(args.pool, args.chunks, translations)
    questions = load_questions(args.questions, pool)
    costs = estimate(pool, questions, args.models, args.rounds)
    if args.command == "estimate":
        print("\n".join(costs or ["유료 모델 없음"]))
        return 0
    if costs and not args.yes:
        print("\n".join([*costs, "유료 모델이 있어 멈춥니다. 비용을 확인받은 뒤 --yes를 붙여 주세요."]), file=sys.stderr)
        return 2
    folder = args.results / f"{now or datetime.now():%Y%m%d-%H%M}_{args.name}" if args.command == "run" else None
    if folder and folder.exists():  # 측정이 끝난 뒤 폴더를 만든다(도중에 멈추면 빈 폴더가 다시 돌리기를 막지 않게)
        print(f"{folder}가 이미 있어 멈춥니다(결과는 덮어쓰지 않음). 다른 --name을 주세요.", file=sys.stderr)
        return 1
    embedders = {model: make_embedder(model) for model in args.models}
    indexes = {model: build_index(pool, model, embedders[model], args.db, args.original_only) for model in args.models}
    for index in indexes.values():
        for record in index.records:
            print(f"DB {record['모델']} {record['글']}: {record['상태']} ({record['파일']})")
    if args.command == "build-db":
        return 0

    chosen = [Condition(model, Text.ORIGINAL, Bm25.OFF) for model in args.models] if args.original_only else conditions(args.models)
    started = datetime.now().isoformat(timespec="seconds")
    measured = measure(questions, chosen, Searcher(pool, indexes), embedders, NoNames() if args.no_menu_names else load_names(), args.rounds, args.seed)
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
        "준비 운동": measured.warmups, "메뉴 이름 덧붙이기": not args.no_menu_names, "유료": paid, "메모": args.note,
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


def _summary_markdown(name: str, rows: Sequence[dict], questions: Sequence[Question], about: dict) -> str:
    """상위 4·6·8개마다 조건 비교표(찾은 비율 높은 차례)와 질문별 표, 그리고 해석할 때의 한계."""
    lines = [
        f"# {name}", "",
        f"질문 {about['질문 수']}개 × 회차 {about['회차']} × 조건 {len(about['조건'])}개. 채점은 1회차 순위, 시간은 모든 회차.",
        f"묶음 {about['청크 수']}청크(번역 있음 {about['번역 있는 청크 수']}개). 유료: {about['유료'] or '없음'}", "",
        "## 해석할 때 주의", "",
        "- 200청크·20문항의 작은 실험이다. 질문마다 필요한 근거 수·난이도가 달라 몇 문항이 결과를 크게 움직인다.",
        "- BM25는 한국어를 두 글자씩, 영어를 낱말로 자른다. 번역 포함 BM25의 효과에는 이 한국어 처리의 영향이 함께 들어 있다.",
        "- 묶음의 번역 비율은 설명서 전체(약 15%)보다 높다. 전체 설명서의 최종 성능으로 읽지 않는다.",
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
