"""소규모 검색 비교(티켓 40): 조건 18개, 낱말 자르기, 검색용 DB 재사용, 분리 검색, 근거 채점, 시간 측정, 명령 줄.

임베딩은 정해 둔 낱말을 세는 가짜를 쓴다(API 키·유료 호출 없음). 청크·번역·질문은 모두 지어낸 것이다(설명서 원문 아님).
"""

import json
from datetime import datetime

import numpy as np
import pytest

from blender_tutor.manual_chunks import Chunk, save_chunks
from blender_tutor.search_compare import (
    MODELS,
    Bm25,
    NarrowNames,
    Picked,
    Scope,
    area_of,
    Condition,
    PoolChunk,
    Question,
    Searcher,
    rewrite,
    sounds_alike,
    Text,
    bm25_words,
    build_index,
    conditions,
    hit,
    load_pool,
    load_questions,
    main,
    measure,
    summarize,
)

VOCAB = ("origin", "merge", "bevel", "오리진", "합치", "베벨")


class FakeEmbedder:
    """VOCAB 낱말을 센 벡터(맨 끝 칸은 0 벡터를 막는 작은 값). 부른 횟수와 받은 글을 남긴다."""

    def __init__(self):
        self.calls, self.texts = 0, []

    def embed(self, texts, timeout):
        self.calls += 1
        self.texts += texts
        return [[text.lower().count(word) for word in VOCAB] + [0.01] for text in texts]


class FakeNames:
    """메뉴 이름 사전 대신: 질문에 '오리진'이 있으면 Origin을 덧붙인다."""

    def english_in(self, text):
        return ("Origin",) if "오리진" in text else ()


class Clock:
    """부를 때마다 1초씩 가는 시계."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1.0
        return self.now


POOL = [
    PoolChunk("set.html#origin/1", "Set Origin\n\nMove the origin.", "오리진 설정\n\n오리진을 옮긴다."),
    PoolChunk("merge.html#merge/1", "Merge\n\nMerge vertices.", "합치기\n\n점을 합치기."),
    PoolChunk("bevel.html#bevel/1", "Bevel\n\nBevel edges.", None),
    PoolChunk("other.html#other/1", "Other\n\nNothing here.", None),
]


def questions():
    return [
        Question("Q1", "오리진 옮기기", True, (("set.html#origin/1",),)),
        Question("Q2", "bevel 둥글게", False, (("bevel.html#bevel/1",),)),
    ]


def test_conditions_cover_every_combination_once():
    found = conditions(MODELS)
    assert len(found) == 18 == len(set(found))
    assert {(c.text, c.bm25) for c in found} == {(t, b) for t in Text for b in Bm25}


def test_bm25_words_cut_korean_into_overlapping_pairs_and_english_into_words():
    assert bm25_words("오리진 Origin을 object.join 해") == ["오리", "리진", "origin", "을", "object", "join", "해"]


def test_hit_counts_each_needed_group_once_even_with_alternatives():
    groups = (("a", "b"), ("c",))
    ranked = ["b", "a", "x", "c"]
    two, four = hit(groups, ranked, 2), hit(groups, ranked, 4)
    assert (two.found, two.needed, two.partial, two.full, two.first_rank) == (1, 2, True, False, 1)
    assert (four.found, four.full, four.ratio) == (2, True, 1.0)
    assert hit(groups, ["x", "y"], 2).first_rank is None


def test_index_embeds_each_text_once_and_reuses_saved_db(tmp_path):
    embedder = FakeEmbedder()
    first = build_index(POOL, "fake", embedder, tmp_path)
    # 원문 4 + 번역 2 + 합침 2(번역 없는 청크는 원문 벡터를 그대로 쓴다)
    assert len(embedder.texts) == 8
    assert np.allclose(first.combined[2], first.original[2])
    assert {record["상태"] for record in first.records} == {"새로 만듦"}

    again = FakeEmbedder()
    second = build_index(POOL, "fake", again, tmp_path)
    assert again.calls == 0 and {record["상태"] for record in second.records} == {"재사용"}
    assert np.allclose(second.translation, first.translation)

    changed = [POOL[0], PoolChunk("merge.html#merge/1", "Merge\n\nMerge vertices.", "합치기 다른 번역"), *POOL[2:]]
    third = FakeEmbedder()
    build_index(changed, "fake", third, tmp_path)
    assert third.calls > 0  # 글이 바뀌면 새 파일을 만든다(이전 파일은 그대로)


def test_separate_search_keeps_best_score_once_and_records_both(tmp_path):
    searcher = Searcher(POOL, {"fake": build_index(POOL, "fake", FakeEmbedder(), tmp_path)})
    vector = FakeEmbedder().embed(["오리진 origin"], 0)[0]
    found = searcher.search(Condition("fake", Text.SEPARATE, Bm25.OFF), "오리진 origin", vector)
    assert found.final[0] == "set.html#origin/1"
    assert len(found.final) == len(set(found.final)) == len(POOL)
    assert {"원문", "번역", "뜻"} <= set(found.parts)
    assert [key for key, _ in found.parts["번역"]] == ["set.html#origin/1", "merge.html#merge/1"]  # 번역 있는 청크만


def test_bm25_condition_merges_word_ranking_with_rrf(tmp_path):
    searcher = Searcher(POOL, {"fake": build_index(POOL, "fake", FakeEmbedder(), tmp_path)})
    vector = [0, 0, 0, 0, 0, 0, 1]  # 낱말 없는 청크(other)가 뜻 검색 1위가 되는 질문 벡터
    off = searcher.search(Condition("fake", Text.ORIGINAL, Bm25.OFF), "베벨 bevel", vector)
    on = searcher.search(Condition("fake", Text.ORIGINAL, Bm25.ENGLISH), "베벨 bevel", vector)
    assert off.final[0] == "other.html#other/1"
    assert on.final[0] == "bevel.html#bevel/1"
    assert [key for key, _ in on.parts["BM25"]] == ["bevel.html#bevel/1"]  # 겹치는 낱말 없는 청크는 순위에 넣지 않는다
    korean = searcher.search(Condition("fake", Text.ORIGINAL, Bm25.BOTH), "합치기", vector)
    assert korean.final[0] == "merge.html#merge/1"  # 번역을 넣은 BM25는 한국어 질문 낱말로도 찾는다


def test_measure_embeds_fresh_for_every_round_question_and_condition(tmp_path):
    embedders = {"fake": FakeEmbedder()}
    searcher = Searcher(POOL, {"fake": build_index(POOL, "fake", FakeEmbedder(), tmp_path)})
    chosen = conditions(("fake",))
    found = measure(questions(), chosen, searcher, embedders, FakeNames(), rounds=3, seed=1, clock=Clock())
    assert len(found.rows) == 3 * 2 * 9
    assert embedders["fake"].calls == 3 * 2 * 9 + 1  # 준비 운동 1번은 따로
    assert len(found.warmups) == 1 and found.warmups[0]["모델"] == "fake"
    first = found.rows[0]
    assert first["원래 질문"] == "오리진 옮기기" and first["검색어"] == "오리진 옮기기 Origin"
    assert set(first["시간"]) == {"질문 임베딩", "뜻 검색", "BM25", "RRF", "전체"}
    one_question = [row["조건"] for row in found.rows[:9]]
    assert sorted(one_question) == sorted(c.name for c in chosen)  # 질문 하나에 조건을 모두 돈 뒤 다음 질문
    orders = {tuple(row["조건"] for row in found.rows[start:start + 9]) for start in range(0, len(found.rows), 9)}
    assert len(orders) > 1  # 질문마다 조건 순서를 섞는다


def test_summarize_scores_first_round_per_top_k_and_marks_changed_rankings(tmp_path):
    rows = [
        {"회차": 1, "질문": "Q1", "조건": "c", "결과": ["x", "set.html#origin/1"], "시간": {"전체": 1.0}},
        {"회차": 2, "질문": "Q1", "조건": "c", "결과": ["set.html#origin/1", "x"], "시간": {"전체": 3.0}},
        {"회차": 1, "질문": "Q2", "조건": "c", "결과": ["bevel.html#bevel/1"], "시간": {"전체": 2.0}},
        {"회차": 2, "질문": "Q2", "조건": "c", "결과": ["bevel.html#bevel/1"], "시간": {"전체": 2.0}},
    ]
    summary = summarize(rows, questions(), 1)
    (line,) = summary
    assert line["조건"] == "c" and line["찾은 비율"] == 0.5 and line["전부 찾은 질문"] == 1
    assert line["번역 있음"] == 0.0 and line["번역 없음"] == 1.0
    assert line["회차마다 순위 다름"] == ["Q1"]
    assert line["중앙값"] == 2.0 and line["최대값"] == 3.0


def write_data(folder):
    """청크 파일·번역·묶음·질문 파일을 쓰고 경로를 돌려준다."""
    chunks = [
        Chunk("set", "origin", "scene", "scene", "Set Origin", ("Origin",), "Move the origin."),
        Chunk("bevel", "bevel", "modeling", "modeling", "Bevel", ("Bevel",), "Bevel edges."),
        Chunk("other", "other", "files", "files", "Other", ("Other",), "Nothing here."),
    ]
    save_chunks(chunks, folder / "chunks.jsonl")
    (folder / "ko.jsonl").write_text(json.dumps({"key": "set.html#origin/1", "korean": "오리진 설정"}, ensure_ascii=False) + "\n", encoding="utf-8")
    pool = [{"key": key} for key in ("set.html#origin/1", "bevel.html#bevel/1", "other.html#other/1")]
    (folder / "pool.jsonl").write_text("".join(json.dumps(row) + "\n" for row in pool), encoding="utf-8")
    rows = [
        {"id": "Q1", "question": "오리진 옮기기", "answer_translated": True, "answer_groups": [{"any_of": ["set.html#origin/1"]}]},
        {"id": "Q2", "question": "bevel", "answer_translated": False, "answer_groups": [{"any_of": ["bevel.html#bevel/1"]}]},
        {"id": "Q3", "question": "빠진 문항", "dropped": "이유", "answer_translated": False, "answer_groups": []},
    ]
    (folder / "q.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def test_load_pool_attaches_text_and_translation_and_questions_skip_dropped(tmp_path):
    write_data(tmp_path)
    pool = load_pool(tmp_path / "pool.jsonl", tmp_path / "chunks.jsonl", {"set.html#origin/1": "오리진 설정"})
    assert pool[0] == PoolChunk("set.html#origin/1", "Set Origin > Origin\n\nMove the origin.", "오리진 설정")
    assert pool[1].korean is None
    assert [q.id for q in load_questions([tmp_path / "q.jsonl"], pool)] == ["Q1", "Q2"]


def test_load_stops_on_answer_outside_pool_or_duplicate_chunk(tmp_path):
    write_data(tmp_path)
    pool = load_pool(tmp_path / "pool.jsonl", tmp_path / "chunks.jsonl", {})
    with pytest.raises(ValueError, match="묶음에 없는 정답"):
        load_questions([tmp_path / "q.jsonl"], pool[1:])
    (tmp_path / "pool.jsonl").write_text('{"key": "set.html#origin/1"}\n' * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="두 번"):
        load_pool(tmp_path / "pool.jsonl", tmp_path / "chunks.jsonl", {})


def run_args(folder, *extra):
    return [
        "run", "--name", "t", "--models", "fake", "--rounds", "1", "--pool", str(folder / "pool.jsonl"),
        "--chunks", str(folder / "chunks.jsonl"), "--translations", str(folder / "ko.jsonl"),
        "--questions", str(folder / "q.jsonl"), "--db", str(folder / "db"), "--results", str(folder / "results"),
        "--note", "시험", *extra,
    ]


def test_main_writes_new_result_folder_and_never_overwrites(tmp_path):
    write_data(tmp_path)
    made = []

    def make(model):
        made.append(FakeEmbedder())
        return made[-1]

    def run():
        return main(run_args(tmp_path), now=datetime(2026, 10, 29, 9, 5), make_embedder=make, load_names=lambda: FakeNames())

    assert run() == 0
    folder = tmp_path / "results" / "20261029" / "090500_t"
    about = json.loads((folder / "설정.json").read_text(encoding="utf-8"))
    assert about["메모"] == "시험" and len(about["조건"]) == 9
    assert len((folder / "실행.jsonl").read_text(encoding="utf-8").splitlines()) == 2 * 9
    assert "상위 4개" in (folder / "요약.md").read_text(encoding="utf-8")
    before = (folder / "실행.jsonl").read_text(encoding="utf-8")
    assert run() == 1  # 같은 이름이면 덮어쓰지 않고 멈춘다
    assert (folder / "실행.jsonl").read_text(encoding="utf-8") == before


def test_main_refuses_paid_model_without_yes(tmp_path):
    write_data(tmp_path)
    args = run_args(tmp_path)
    args[args.index("fake")] = "text-embedding-3-large"
    calls = []
    assert main(args, make_embedder=lambda model: calls.append(model), load_names=lambda: FakeNames()) == 2
    assert calls == [] and not (tmp_path / "results").exists()


def test_original_only_uses_document_encoder_and_keeps_all_time_samples(tmp_path):
    """문서는 passage 형식, 질문은 query 형식이어야 한다. 시간 표본은 3회 모두 남긴다."""
    write_data(tmp_path)

    class SplitEmbedder(FakeEmbedder):
        def __init__(self):
            super().__init__()
            self.documents = []

        def embed_documents(self, texts, timeout):
            self.documents.extend(texts)
            return FakeEmbedder().embed(texts, timeout)

    embedder = SplitEmbedder()
    args = run_args(tmp_path, "--original-only", "--rounds", "3")
    assert main(args, make_embedder=lambda _: embedder, load_names=lambda: FakeNames()) == 0
    folder = next((tmp_path / "results").glob("*/*"))
    about = json.loads((folder / "설정.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (folder / "실행.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(about["조건"]) == 1 and about["조건"][0] == "fake / 원문만 / BM25 끔"
    assert len(embedder.documents) == 3 and all("오리진 설정" not in text for text in embedder.documents)
    assert embedder.calls == 7  # 질문 2개 × 3회 + 준비 운동 1회
    assert len(rows) == 6 and {row["회차"] for row in rows} == {1, 2, 3}


def test_no_menu_names_searches_the_question_as_is(tmp_path):
    """--menu-names off면 '오리진' 질문에도 Origin을 붙이지 않고, 설정에 꺼진 것을 남긴다."""
    write_data(tmp_path)
    embedder = FakeEmbedder()
    assert main(run_args(tmp_path, "--original-only", "--menu-names", "off"), make_embedder=lambda _: embedder,
                load_names=lambda: FakeNames()) == 0
    folder = next((tmp_path / "results").glob("*/*"))
    about = json.loads((folder / "설정.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (folder / "실행.jsonl").read_text(encoding="utf-8").splitlines()]
    assert about["메뉴 이름 덧붙이기"] == "off"
    assert any("오리진" in row["원래 질문"] for row in rows)  # 켜 두었다면 Origin이 붙었을 질문
    assert all(row["검색어"] == row["원래 질문"] for row in rows)


def test_cache_separates_model_revisions_and_prompts(tmp_path):
    embedder = FakeEmbedder()
    embedder.cache_identity = {"revision": "v1", "document": "passage: "}
    build_index(POOL, "fake", embedder, tmp_path, original_only=True)
    same = FakeEmbedder()
    same.cache_identity = embedder.cache_identity
    build_index(POOL, "fake", same, tmp_path, original_only=True)
    assert same.calls == 0
    changed = FakeEmbedder()
    changed.cache_identity = {"revision": "v2", "document": "document: "}
    build_index(POOL, "fake", changed, tmp_path, original_only=True)
    assert changed.calls == 1 and len(list(tmp_path.glob("*.npz"))) == 2


def test_sounds_alike_keeps_spelled_out_names_and_drops_everyday_words():
    """실제 평가 질문에서 걸린 조각(HISTORY [113]): 소리대로 적은 이름만 닮았다고 본다."""
    for korean, english in [("미러모디파이어", "Mirror Modifier"), ("오리진", "Origin"), ("큐브", "Cube"),
                            ("오브젝트", "Object"), ("텍스처", "Textures"), ("버텍스", "Vertices")]:
        assert sounds_alike(korean, english), (korean, english)
    for korean, english in [("만들", "Make"), ("바닥", "Floor"), ("회전", "Rotate"), ("감싸", "Wrap"),
                            ("표면", "Surface"), ("복사", "Copy"), ("아래", "Bottom")]:
        assert not sounds_alike(korean, english), (korean, english)


def test_narrow_names_needs_hangul_and_every_candidate_alike():
    class Matches:
        def matches_in(self, text):
            return [("만들", ("Make",)), ("오브젝트", ("Object", "Objects")), ("회전", ("Rotate", "Rotation")),
                    ("A", ("A",)), ("오브젝트", ("Object", "Objects")), ("버텍스", ("Vertices", "Vertex"))]

    assert NarrowNames(Matches()).english_in("아무 글") == ("Object", "Objects", "Vertices", "Vertex")


def test_scope_drops_chunks_from_meaning_and_bm25_before_ranking(tmp_path):
    """거른 청크는 뜻 검색 1위였어도, BM25 낱말이 겹쳐도 결과에 없다."""
    keep = np.array([True, True, False, True])  # bevel을 뺀다
    searcher = Searcher(POOL, {"fake": build_index(POOL, "fake", FakeEmbedder(), tmp_path)}, scopes={Scope.BEGINNER: keep})
    vector = FakeEmbedder().embed(["bevel"], 0)[0]
    for bm25 in (Bm25.OFF, Bm25.ENGLISH):
        whole = searcher.search(Condition("fake", Text.ORIGINAL, bm25), "bevel", vector)
        kept = searcher.search(Condition("fake", Text.ORIGINAL, bm25, Scope.BEGINNER), "bevel", vector)
        assert whole.final[0] == "bevel.html#bevel/1"
        assert "bevel.html#bevel/1" not in kept.final and len(kept.final) == 3
    assert Condition("fake", Text.ORIGINAL, Bm25.OFF).name == "fake / 원문만 / BM25 끔"  # 범위 전체면 예전 이름 그대로


def test_question_areas_keep_only_asked_or_drop_excluded(tmp_path):
    searcher = Searcher(POOL, {"fake": build_index(POOL, "fake", FakeEmbedder(), tmp_path)})
    vector = FakeEmbedder().embed(["bevel"], 0)[0]
    picked = Picked(asked=("set", "merge"), excluded=("other",))
    asked = searcher.search(Condition("fake", Text.ORIGINAL, Bm25.OFF, Scope.ASKED), "bevel", vector, picked)
    others = searcher.search(Condition("fake", Text.ORIGINAL, Bm25.OFF, Scope.OTHERS), "bevel", vector, picked)
    assert sorted(asked.final) == ["merge.html#merge/1", "set.html#origin/1"]
    assert sorted(others.final) == ["bevel.html#bevel/1", "merge.html#merge/1", "set.html#origin/1"]


def test_area_splits_only_big_fields_one_level_deeper():
    assert area_of("modeling/modifiers/deform/lattice") == "modeling/modifiers"
    assert area_of("render/cycles/baking") == "render/cycles"
    assert area_of("physics/cloth/introduction") == "physics"
    assert area_of("index") == "index"


class FakeChat:
    """질문 바꾸기 모델 대신: 질문에 '오리진'이 있으면 Set Origin, 아니면 bevel. 분야는 목록 밖 이름 하나를 섞는다."""

    def __init__(self, answers=None):
        self.input_tokens = self.output_tokens = 0
        self.asked = []
        self.answers = answers

    def ask(self, messages):
        self.asked.append(messages)
        self.input_tokens += 100
        self.output_tokens += 10
        if self.answers:
            return self.answers.pop(0)
        if "오리진" in messages[-1]["content"]:
            return json.dumps({"query": "Set Origin", "areas": ["set", "없는 분야"], "exclude": ["other"]})
        return json.dumps({"query": "bevel edges", "areas": ["bevel"], "exclude": []})


def test_rewrite_asks_every_round_keeps_known_areas_and_stops_on_answer_without_query():
    chat = FakeChat()
    rows = rewrite(questions(), chat, ["bevel", "other", "set"], rounds=2, clock=Clock())
    assert [(row["회차"], row["질문"], row["검색어"]) for row in rows] == [
        (1, "Q1", "Set Origin"), (1, "Q2", "bevel edges"), (2, "Q1", "Set Origin"), (2, "Q2", "bevel edges")]
    assert rows[0]["분야"] == ["set"] and rows[0]["뺄 분야"] == ["other"] and rows[0]["목록 밖"] == ["없는 분야"]
    assert all(row["초"] == 1.0 for row in rows)
    assert "bevel\nother\nset" in chat.asked[0][0]["content"]  # 분야 목록을 지시에 넣는다
    with pytest.raises(ValueError, match="검색어가 없는"):
        rewrite(questions(), FakeChat([json.dumps({"query": ""})]), ["set"], rounds=1)


def test_rewrite_command_needs_yes_and_run_uses_its_queries_and_areas(tmp_path):
    write_data(tmp_path)
    (tmp_path / "scope.jsonl").write_text(json.dumps({"path": "set", "include": True}) + "\n"
                                          + json.dumps({"path": "bevel", "include": False}) + "\n", encoding="utf-8")
    base = ["--pool", str(tmp_path / "pool.jsonl"), "--chunks", str(tmp_path / "chunks.jsonl"),
            "--translations", str(tmp_path / "ko.jsonl"), "--questions", str(tmp_path / "q.jsonl"),
            "--results", str(tmp_path / "results"), "--rounds", "1", "--note", "시험"]
    chats = []

    def make_chat(model, effort):
        chats.append(FakeChat())
        return chats[-1]

    assert main(["rewrite", "--name", "바꿈", *base], make_chat=make_chat) == 2 and chats == []  # 유료라 --yes 없이는 멈춤
    assert main(["rewrite", "--name", "바꿈", "--yes", *base], now=datetime(2026, 10, 30, 10, 0), make_chat=make_chat) == 0
    rewrites = tmp_path / "results" / "20261030" / "100000_바꿈" / "검색어.jsonl"
    assert len(rewrites.read_text(encoding="utf-8").splitlines()) == 2

    embedder = FakeEmbedder()
    args = ["run", "--name", "t", "--models", "fake", "--db", str(tmp_path / "db"), *base, "--original-only", "--with-bm25",
            "--rewrites", str(rewrites), "--rewritten-query", "--scopes", "all", "asked", "others", "beginner",
            "--scope-file", str(tmp_path / "scope.jsonl")]
    assert main(args, now=datetime(2026, 10, 30, 10, 1), make_embedder=lambda _: embedder, load_names=lambda: FakeNames()) == 0
    folder = tmp_path / "results" / "20261030" / "100100_t"
    about = json.loads((folder / "설정.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (folder / "실행.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(about["조건"]) == 8  # BM25 끔·켬 × 범위 4
    assert {row["검색어"] for row in rows} == {"Set Origin", "bevel edges"}  # 메뉴 이름 대신 바꾼 검색어
    q1 = {row["조건"].split(" / ")[-1]: row for row in rows if row["질문"] == "Q1" and "BM25 끔" in row["조건"]}
    assert q1["질문 분야만"]["결과"] == ["set.html#origin/1"] and q1["질문 분야만"]["남은 청크"] == 1
    assert q1["질문 보고 뺀 나머지"]["남은 청크"] == 2 and q1["초보자 범위만"]["결과"] == ["set.html#origin/1"]
    without = ["run", "--name", "u", "--models", "fake", "--db", str(tmp_path / "db"), *base, "--original-only", "--scopes", "asked"]
    with pytest.raises(SystemExit):  # --rewrites 없이 질문 분야 범위는 못 씀
        main(without, make_embedder=lambda _: embedder, load_names=lambda: FakeNames())
