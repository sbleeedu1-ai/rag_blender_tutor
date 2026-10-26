"""시간 기록(티켓 28): 질문마다 F10 누름 → 받음 → 입력 가능 → 보냄 → 첫 글자 → 답 끝 시각과 그때의 엔진·설정을 기록 파일에 한 줄씩 남긴다.

시계는 가짜(정해 둔 시각을 차례로 내줌)로 바꿔 끼우고, 기록 파일에 쓰인 줄을 읽어 본다.
"""

import json

from blender_tutor.answer_engine import Done, Failure, Piece
from blender_tutor.timing import Stopwatch

DONE = Done((), ())
# 질문할 때의 엔진과 설정(평가 프로그램이 이것으로 줄을 가른다, 티켓 29)
ENGINE = {"name": "stand_in", "settings": {"top_k": 6, "timeout": 10.0, "use_bm25": True, "reasoning": "none", "recent_pairs": 3}}


class Clock:
    """부를 때마다 times를 앞에서부터 하나씩 내준다."""

    def __init__(self, *times: float):
        self._times = list(times)

    def __call__(self) -> float:
        return self._times.pop(0)


def lines(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_F10부터_답_끝까지_시각을_한_줄로_남긴다(tmp_path):
    path = tmp_path / "timings.jsonl"
    watch = Stopwatch(path, pc="강의실", clock=Clock(100.05, 100.30, 105.0, 106.5, 108.0))
    watch.summoned(pressed=100.0)  # 받음 100.05
    watch.ready()  # 입력 가능 100.30
    lap = watch.asked("칼끝은 어떻게 모아요?", ENGINE)  # 보냄 105.0
    for event in (Piece("먼저 "), Piece("버텍스를"), DONE):  # 첫 글자 106.5, 답 끝 108.0
        lap.saw(event)
    assert lines(path) == [
        {
            "pc": "강의실",
            "engine": "stand_in",
            "settings": {"top_k": 6, "timeout": 10.0, "use_bm25": True, "reasoning": "none", "recent_pairs": 3},
            "question": "칼끝은 어떻게 모아요?",
            "f10_pressed": 100.0,
            "f10_received": 100.05,
            "ready": 100.30,
            "sent": 105.0,
            "first_piece": 106.5,
            "done": 108.0,
            "outcome": "done",
        }
    ]


def test_F10_없이_이어_물은_질문은_F10_칸을_비운다(tmp_path):
    """F10 시각은 그 뒤 첫 질문에만 붙는다. 창이 떠 있는 채 다시 물으면 준비 시간이 없다."""
    path = tmp_path / "timings.jsonl"
    watch = Stopwatch(path, pc="집", clock=Clock(1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 11.0, 12.0))
    watch.summoned(pressed=0.5)
    watch.ready()
    for question in ("첫 질문", "이어 묻기"):
        lap = watch.asked(question, ENGINE)
        lap.saw(Piece("답"))
        lap.saw(DONE)
    second = lines(path)[1]
    assert (second["question"], second["f10_pressed"], second["f10_received"], second["ready"]) == ("이어 묻기", None, None, None)
    assert (second["sent"], second["first_piece"], second["done"]) == (10.0, 11.0, 12.0)


def test_실패로_끝난_답은_첫_글자_없이_실패로_남긴다(tmp_path):
    path = tmp_path / "timings.jsonl"
    watch = Stopwatch(path, pc="집", clock=Clock(1.0, 11.0))
    lap = watch.asked("질문", None)  # 엔진 준비 전이면 엔진·설정을 모른다
    lap.saw(Failure("도우미가 설명서를 읽는 중이에요."))
    [line] = lines(path)
    assert (line["engine"], line["settings"], line["first_piece"], line["done"], line["outcome"]) == (None, None, None, 11.0, "failure")


def test_기록_파일을_쓸_수_없어도_멈추지_않는다(tmp_path):
    """시간 기록은 재기 위한 덤이라, 못 써도 답은 그대로 나와야 한다."""
    watch = Stopwatch(tmp_path, pc="집", clock=Clock(1.0, 2.0))  # 폴더를 파일 자리에 줘서 쓰기가 실패한다
    lap = watch.asked("질문", ENGINE)
    lap.saw(DONE)  # 예외가 나지 않으면 통과


def test_F10_뒤_60초가_지나서_보낸_질문에는_F10_시각을_붙이지_않는다(tmp_path):
    """F10을 누르고 묻지 않은 채 Blender에서 작업하다 창을 눌러 물으면, 그 사이 시간이 준비 시간으로 잡히지 않게 한다.

    60초 안이면 다른 창에서 복사해 붙여 넣느라 오가도 그대로 붙는다.
    """
    path = tmp_path / "timings.jsonl"
    watch = Stopwatch(path, pc="집", clock=Clock(1.0, 2.0, 61.5, 70.0, 71.0, 72.0, 200.0, 201.0))
    watch.summoned(pressed=0.5)  # 받음 1.0
    watch.ready()  # 입력 가능 2.0
    lap = watch.asked("60초 안", ENGINE)  # 보냄 61.5: 입력 가능 뒤 59.5초
    lap.saw(DONE)  # 70.0
    watch.summoned(pressed=70.5)  # 받음 71.0
    watch.ready()  # 입력 가능 72.0
    lap = watch.asked("60초 넘음", ENGINE)  # 보냄 200.0: 입력 가능 뒤 128초
    lap.saw(DONE)  # 201.0
    within, over = lines(path)
    assert (within["f10_pressed"], within["ready"]) == (0.5, 2.0)
    assert (over["f10_pressed"], over["f10_received"], over["ready"], over["sent"]) == (None, None, None, 200.0)
