"""평가 프로그램(티켓 29): 문항 파일 읽기, 답 엔진에 넣어 돌리기, 시간 통계, 명령 줄.

답 엔진은 진짜(AnswerEngine)에 가짜 임베딩·가짜 답변 모델을 끼우고, 지어낸 작은 청크 묶음(설명서 원문 아님)으로 돌린다.
문항·작업 상태·시간 기록 줄도 모두 지어낸 것이다.
"""

import json
from datetime import date

import pytest

from blender_tutor.answer_engine import AnswerEngine, Settings
from blender_tutor.evaluate import Dialogue, Spread, Turn, load_questions, main, run, timing_summary
from blender_tutor.manual_chunks import Chunk, save_chunks
from blender_tutor.progress import Course, Step
from blender_tutor.work_state import WorkState
from tests.examples import EDITING

BLADE = Step("blade-stretch", "정육면체를 늘려 칼날 모양 잡기", manual=("modeling/modifiers/generate/bevel.html#options",), guide="이름: 칼날")
TIP = Step("blade-tip", "칼끝 모으기")
SWORD = Course("sword", "단순한 검", (BLADE, TIP), "검을 만든다")


def write(folder, questions) -> object:
    """문항 파일과 그것이 가리키는 작업 상태 파일(states/편집.json)을 쓴다."""
    (folder / "states").mkdir(exist_ok=True)
    (folder / "states" / "편집.json").write_text(json.dumps(EDITING, ensure_ascii=False), encoding="utf-8")
    path = folder / "questions.json"
    path.write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    return path


SINGLE = {
    "번호": "D01", "분류": "연습 과정 단계", "질문": "칼끝은 어떻게 모아요?", "작업 상태": "states/편집.json",
    "스크린샷": "states/편집.png", "연습 과정": "sword", "단계": "blade-tip",
    "핵심": ["점을 골라 합친다"], "정답 위치": ["modeling/meshes/editing/vertex/merge.html#merge"],
}
OUTSIDE = {  # 연습 과정 밖, 문서에 없는 질문(정답 위치 없음)
    "번호": "D02", "분류": "문서에 없음", "질문": "게임 엔진에 바로 넣을 수 있어요?", "작업 상태": "states/편집.json",
    "핵심": ["설명서에 없다고 말한다"], "정답 위치": [],
}
SCENARIO = {
    "번호": "S1", "분류": "시나리오형", "연습 과정": "sword", "차례": [
        {"번호": "S1-1", "질문": "칼날을 길게 늘리려면요?", "작업 상태": "states/편집.json", "단계": "blade-stretch",
         "핵심": [], "정답 위치": []},  # 묻기만 하고 세지 않는 차례
        {"번호": "S1-2", "질문": "그거 반대로 하려면요?", "작업 상태": "states/편집.json", "단계": "blade-stretch",
         "핵심": ["Ctrl+Z"], "정답 위치": ["https://docs.blender.org/manual/en/5.2/files/blend/save.html"]},
    ],
}


def test_문항_하나는_차례_하나짜리_대화가_되고_단계와_작업_상태를_읽는다(tmp_path):
    [dialogue] = load_questions(write(tmp_path, [SINGLE]), [SWORD])
    assert (dialogue.number, dialogue.kind) == ("D01", "연습 과정 단계")
    [turn] = dialogue.turns
    assert turn.number == "D01" and turn.question == "칼끝은 어떻게 모아요?"
    assert turn.step == TIP
    assert turn.state.mode == "EDIT_MESH"
    assert turn.keys == ("점을 골라 합친다",) and turn.scored
    assert turn.locations == ("modeling/meshes/editing/vertex/merge.html#merge",)


def test_연습_과정_밖이면_단계가_없고_시나리오형은_차례를_파일_차례대로_읽는다(tmp_path):
    outside, scenario = load_questions(write(tmp_path, [OUTSIDE, SCENARIO]), [SWORD])
    assert outside.turns[0].step is None
    assert [turn.number for turn in scenario.turns] == ["S1-1", "S1-2"]
    assert [turn.scored for turn in scenario.turns] == [False, True]
    assert scenario.turns[0].step == BLADE
    # 링크를 그대로 붙여 넣어도 연습 과정 파일과 같은 꼴(경로.html#앵커)로 바꿔 든다
    assert scenario.turns[1].locations == ("files/blend/save.html",)


@pytest.mark.parametrize(
    "broken, words",
    [
        ({**SINGLE, "질문 ": "오타 칸"}, ["D01", "질문 "]),  # 모르는 칸
        ({key: value for key, value in SINGLE.items() if key != "핵심"}, ["D01", "핵심"]),  # 빠진 칸
        ({**SINGLE, "단계": "no-such-step"}, ["D01", "no-such-step"]),
        ({**SINGLE, "연습 과정": "shield"}, ["D01", "shield"]),
        ({**SINGLE, "연습 과정": None}, ["D01", "단계"]),  # 단계만 있고 연습 과정이 없음
        ({**SINGLE, "단계": None}, ["D01", "단계"]),  # 연습 과정만 있고 단계가 없음
        ({**SINGLE, "정답 위치": ["modeling/merge"]}, ["D01", "modeling/merge"]),  # .html이 없음
        ({**SINGLE, "작업 상태": "states/없음.json"}, ["D01", "없음.json"]),
        ({**SINGLE, "핵심": "점을 골라 합친다"}, ["D01", "핵심"]),  # 목록이 아님
    ],
)
def test_칸이_틀린_문항은_번호와_함께_알린다(tmp_path, broken, words):
    with pytest.raises(ValueError) as error:
        load_questions(write(tmp_path, [broken]), [SWORD])
    assert all(word in str(error.value) for word in words)


def test_번호가_겹치면_알린다(tmp_path):
    with pytest.raises(ValueError, match="D01"):
        load_questions(write(tmp_path, [SINGLE, {**OUTSIDE, "번호": "D01"}]), [SWORD])
    turn = {**SCENARIO["차례"][1], "번호": "D01"}  # 시나리오 차례 번호와 겹쳐도
    with pytest.raises(ValueError, match="D01"):
        load_questions(write(tmp_path, [SINGLE, {**SCENARIO, "차례": [turn]}]), [SWORD])


# ---- 돌리기: 진짜 답 엔진 + 가짜 임베딩·답변 모델

BEVEL = Chunk("modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate", "Bevel Modifier", ("Options",), "Width sets the size of the chamfer.")
ARRAY = Chunk("modeling/modifiers/generate/array", "introduction", "modeling", "modeling/modifiers/generate", "Array Modifier", ("Introduction",), "Array copies the object in a row.")
SAVE = Chunk("files/blend/save", "save", "files", "files/blend", "Saving", ("Save",), "Save writes the blend file.")
CHUNKS = [BEVEL, ARRAY, SAVE]
VECTORS = [[1.0, 0.0, 0.0], [0.5, 0.5, 0.0], [0.0, 0.0, 1.0]]  # 질문 벡터 [1, 0, 0]이면 BEVEL, ARRAY, SAVE 차례


class Embedder:
    def embed(self, texts, timeout):
        return [[1.0, 0.0, 0.0] for _ in texts]


class Model:
    """받은 대화 글을 적어 두고 '답n'을 흘린다. fail_on번째 부름이면 조각 하나 뒤 오류를 낸다."""

    def __init__(self, fail_on: int | None = None):
        self.calls: list[list[dict]] = []
        self.fail_on = fail_on

    def stream(self, messages, timeout):
        self.calls.append(messages)
        yield f"답{len(self.calls)}"
        if len(self.calls) == self.fail_on:
            raise TimeoutError


def engine(model, top_k=3) -> AnswerEngine:
    return AnswerEngine(CHUNKS, VECTORS, Embedder(), model, Settings(top_k=top_k, use_bm25=False))


def turn(number, question, locations=(), keys=("핵심",), step=None) -> Turn:
    return Turn(number, question, WorkState.from_json(EDITING), step, tuple(keys), tuple(locations))


def test_검색_결과에서_정답_위치가_몇_위인지_센다_소제목이나_쪽_전체로():
    dialogues = [
        Dialogue("D01", "정답형", (turn("D01", "베벨", ["modeling/modifiers/generate/bevel.html#options"]),)),
        Dialogue("D02", "정답형", (turn("D02", "배열", ["files/blend/save.html", "modeling/modifiers/generate/array.html"]),)),
        Dialogue("D03", "정답형", (turn("D03", "없음", ["modeling/modifiers/generate/array.html#other"]),)),
        Dialogue("D04", "문서에 없음", (turn("D04", "게임 엔진"),)),
    ]
    results = run(dialogues, engine(Model()))
    assert [result.hit for result in results] == [1, 2, None, None]
    assert results[0].answer == "답1" and results[0].failure is None
    assert results[0].results == (BEVEL, ARRAY, SAVE)
    assert [source.url for source in results[0].sources][0].endswith("bevel.html#options")


def test_시나리오형은_엔진이_낸_앞_답을_최근_대화로_넘기고_대화마다_새로_시작한다():
    model = Model()
    scenario = Dialogue("S1", "시나리오형", (turn("S1-1", "처음", keys=()), turn("S1-2", "그다음"), turn("S1-3", "또")))
    run([scenario, Dialogue("D01", "정답형", (turn("D01", "새 질문"),))], engine(model), recent_pairs=1)
    said = [[message["content"] for message in call[1:-1]] for call in model.calls]  # 지시·마지막 글 사이 = 최근 대화
    assert said == [[], ["처음", "답1"], ["그다음", "답2"], []]  # 1쌍만, 새 대화는 빈 채로


def test_지금_단계를_엔진에_넘긴다():
    model = Model()
    run([Dialogue("D01", "정답형", (turn("D01", "칼날", step=BLADE),))], engine(model))
    assert "# 지금 단계\n\n이름: 칼날" in model.calls[0][-1]["content"]


def test_실패한_답도_검색_결과와_적중은_남기고_최근_대화에는_넣지_않는다():
    model = Model(fail_on=1)
    scenario = Dialogue("S1", "시나리오형", (turn("S1-1", "처음", ["files/blend/save.html"]), turn("S1-2", "그다음")))
    first, second = run([scenario], engine(model))
    assert first.failure == "답이 너무 늦어져 멈췄어요. 잠시 뒤 다시 물어봐 주세요." and first.answer == "답1"
    assert first.hit == 3
    assert [message["content"] for message in model.calls[1][1:-1]] == []
    assert second.failure is None


# ---- 시간 통계: 도우미 창의 시간 기록 줄(지어낸 것)

NONE = {"top_k": 6, "timeout": 10.0, "use_bm25": True, "reasoning": "none", "recent_pairs": 3}
LOW = {**NONE, "reasoning": "low"}


def line(question, sent, first, done, f10=None, ready=None, engine="stand_in", settings=NONE, outcome="done"):
    return {
        "pc": "강의실", "engine": engine, "settings": settings, "question": question,
        "f10_pressed": f10, "f10_received": None if f10 is None else f10 + 0.05, "ready": ready,
        "sent": sent, "first_piece": first, "done": done, "outcome": outcome,
    }


QUESTIONS = [
    Dialogue("D01", "정답형", (turn("D01", "칼끝은 어떻게 모아요?"),)),
    Dialogue("D02", "정답형", (turn("D02", "저장은요?"),)),
    Dialogue("S1", "시나리오형", (turn("S1-1", "칼날을 늘리려면요?", keys=()), turn("S1-2", "반대로는요?"))),
]


def test_엔진과_설정이_같은_줄끼리_중앙값_최대값과_분모를_낸다():
    lines = [
        line("칼끝은 어떻게 모아요?", 100.0, 101.0, 104.0, f10=94.0, ready=94.2),
        line("저장은요?", 200.0, 202.0, 205.0, f10=195.0, ready=195.6),
        line("반대로는요?", 300.0, 303.0, 309.0),  # 창이 떠 있는 채 이어 물음: F10 칸 없음
        line("칼끝은 어떻게 모아요?", 400.0, 400.5, 401.0, settings=LOW),
    ]
    none, low = timing_summary(lines, QUESTIONS).groups
    assert (none.engine, none.settings, low.settings) == ("stand_in", NONE, LOW)
    assert none.numbers == ("D01", "D02", "S1-2")
    assert none.spreads["질문 준비(F10 → 입력 가능)"] == Spread(2, pytest.approx(0.4), pytest.approx(0.6))
    assert none.spreads["첫 글자(보냄 → 첫 글자)"] == Spread(3, 2.0, 3.0)
    assert none.spreads["답 끝(보냄 → 답 끝)"] == Spread(3, 5.0, 9.0)
    assert none.spreads["F10 → 답 끝"] == Spread(2, 10.0, 10.0)
    assert low.spreads["답 끝(보냄 → 답 끝)"] == Spread(1, 1.0, 1.0)
    assert low.spreads["질문 준비(F10 → 입력 가능)"] == Spread(0, None, None)


def test_앞뒤_공백을_무시해_맞추고_같은_문항은_마지막_줄을_쓰고_실패는_빼고_센다():
    lines = [
        line("칼끝은 어떻게 모아요?", 100.0, 101.0, 120.0),
        line("  칼끝은  어떻게\n모아요? ", 200.0, 201.0, 203.0),  # 붙여 넣다 붙은 공백·줄바꿈
        line("저장은요?", 300.0, None, 310.0, outcome="failure"),
        line("문항에 없는 질문", 400.0, 401.0, 402.0),
        line("칼끝은 어떻게 모아요?", 500.0, None, 501.0, engine=None, settings=None),  # 엔진 준비 전
    ]
    summary = timing_summary(lines, QUESTIONS)
    [group] = summary.groups
    assert group.numbers == ("D01",)
    assert group.spreads["답 끝(보냄 → 답 끝)"] == Spread(1, 3.0, 3.0)
    assert group.failures == ("D02",)
    assert (summary.unmatched, summary.not_ready) == (1, 1)


def test_질문_글이_같은_문항이_둘이면_줄을_가를_수_없어_알린다():
    twins = QUESTIONS + [Dialogue("D03", "정답형", (turn("D03", "저장은요? "),))]
    with pytest.raises(ValueError, match="D02.*D03"):
        timing_summary([], twins)


# ---- 명령 줄: 작은 청크 파일 + 임시 엔진(stand_in)으로 끝까지

def project(tmp_path):
    """청크 파일 하나인 data/, 빈 courses/, 연습 과정 밖 문항 둘인 문항 파일."""
    save_chunks(CHUNKS, tmp_path / "data" / "chunks" / "manual_chunks.jsonl")
    (tmp_path / "courses").mkdir(exist_ok=True)
    questions = [
        {**OUTSIDE, "번호": "D01", "질문": "save the blend file", "정답 위치": ["files/blend/save.html#save"]},
        {**OUTSIDE, "번호": "D02", "질문": "게임 엔진"},
    ]
    return write(tmp_path, questions)


def options(tmp_path, *more):
    return [str(project(tmp_path)), "--courses", str(tmp_path / "courses"), "--results", str(tmp_path / "results"), *more]


def run_options(tmp_path, *more):
    return options(tmp_path, "--data", str(tmp_path / "data"), *more)


def test_run은_날짜_이름_폴더에_설정과_차례별_답과_적중_요약을_쓴다(tmp_path):
    assert main(["run", *run_options(tmp_path, "--name", "기준", "--reasoning", "low", "--recent", "5", "--no-bm25")], today=date(2026, 10, 26)) == 0
    folder = tmp_path / "results" / "20261026_기준"
    settings = json.loads((folder / "설정.json").read_text(encoding="utf-8"))
    assert settings["engine"] == "stand_in" and settings["임베딩"] == "stand_in" and settings["리랭커"] == "끔"
    assert settings["settings"] == {"top_k": 6, "timeout": 10.0, "use_bm25": False, "reasoning": "low", "recent_pairs": 5}
    rows = [json.loads(text) for text in (folder / "답.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["번호"], row["적중 순위"]) for row in rows] == [("D01", 1), ("D02", None)]
    assert rows[0]["검색 결과"][0]["주소"] == "files/blend/save.html#save"
    assert rows[0]["답"].startswith("(임시 답)")
    assert "검색 적중: 1 / 1" in (folder / "요약.md").read_text(encoding="utf-8")


def test_같은_날_같은_이름으로_다시_돌리면_덮어쓰지_않고_멈춘다(tmp_path, capsys):
    arguments = ["run", *run_options(tmp_path, "--name", "기준")]
    main(arguments, today=date(2026, 10, 26))
    before = (tmp_path / "results" / "20261026_기준" / "답.jsonl").read_text(encoding="utf-8")
    assert main(arguments, today=date(2026, 10, 26)) == 1
    assert "20261026_기준" in capsys.readouterr().err
    assert (tmp_path / "results" / "20261026_기준" / "답.jsonl").read_text(encoding="utf-8") == before


def test_아직_없는_리랭커나_임베딩은_고를_수_없다(tmp_path):
    for more in (["--reranker", "켬"], ["--embedding", "bge-m3"]):
        with pytest.raises(SystemExit):
            main(["run", *run_options(tmp_path, "--name", "기준", *more)], today=date(2026, 10, 26))


def test_times는_시간_기록_파일에서_통계를_써_둔다(tmp_path):
    timings = tmp_path / "timings.jsonl"
    timings.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in [
        line("save the blend file", 100.0, 101.5, 104.0, f10=99.0, ready=99.3),
        line("게임 엔진", 200.0, 202.5, 206.0),
    ]) + "\n", encoding="utf-8")
    assert main(["times", *options(tmp_path, "--name", "시간", "--timings", str(timings))], today=date(2026, 10, 26)) == 0
    report = (tmp_path / "results" / "20261026_시간" / "시간.md").read_text(encoding="utf-8")
    assert "| 답 끝(보냄 → 답 끝) | 2 | 5.00 | 6.00 |" in report
    assert "| 질문 준비(F10 → 입력 가능) | 1 | 0.30 | 0.30 |" in report
