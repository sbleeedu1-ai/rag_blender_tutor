"""호출 기록(docs/plan/01 A): 답 시험이 차례마다 바깥 호출의 시각·토큰·주고받은 글을 남기는 겉.

진짜 ClaudeModel에 가짜 client(키·돈 없음)를 끼워, 토큰 칸이 실제 모델의 셈에서 오는지까지 본다. 글은 모두 지어낸 것이다.
"""

import threading

import pytest

from blender_tutor.call_log import CallLog
from blender_tutor.claude_model import ClaudeModel
from tests.test_claude_model import FakeClient

MESSAGES = [{"role": "system", "content": "지시"}, {"role": "user", "content": "질문"}]


def ticking():
    """부를 때마다 1초씩 가는 시계."""
    now = iter(range(1000))
    return lambda: float(next(now))


def test_답변은_보낸_글_원문_시각_토큰을_남기고_엔진에는_조각을_그대로_준다():
    log = CallLog(clock=ticking())
    model = log.wrap("답변", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=("[[Add]] ", "눌러요"))))
    log.start()  # 0초
    assert list(model.stream(MESSAGES, 10.0)) == ["[[Add]] ", "눌러요"]
    [record] = log.take()
    assert record["종류"] == "답변" and record["몇째"] == 0
    assert record["보낸 글"] == MESSAGES and record["글"] == "[[Add]] 눌러요"
    assert (record["보냄"], record["첫 조각"], record["끝"]) == (1.0, 2.0, 3.0)
    assert (record["입력"], record["출력"], record["생각"]) == (1000, 200, 0)  # 가짜 client의 usage 그대로


def test_같은_모델을_두_번_부르면_토큰은_그_호출의_몫만():
    log = CallLog()
    model = log.wrap("답변", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=("답",))))
    for _ in range(2):
        log.start()
        list(model.stream(MESSAGES, 10.0))
        [record] = log.take()
        assert record["입력"] == 1000  # 쌓인 2000이 아니라
    assert model.dollars() == pytest.approx(2 * (1000 * 0.10 + 200 * 0.50) / 1_000_000)  # 겉 밖의 이름은 속 모델로 넘긴다


def test_질문_바꾸기는_검색어가_닫힌_시각을_따로_남긴다():
    log = CallLog(clock=ticking())
    pieces = ('{"query": "be', 'vel"', ', "areas": []}')
    rewriter = log.wrap("질문 바꾸기", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=pieces), schema={}))
    log.start()
    assert "".join(rewriter.stream(MESSAGES)) == "".join(pieces)
    [record] = log.take()
    assert (record["보냄"], record["첫 조각"], record["검색어 닫힘"], record["끝"]) == (1.0, 2.0, 3.0, 4.0)
    assert "보낸 글" not in record  # 지시(분야 목록)는 차례마다 같아 남기지 않는다


def test_분야_고르기와_임베딩도_시각과_토큰을_남긴다():
    class Embedder:
        tokens = 0

        def embed(self, texts, timeout):
            self.tokens += 7
            return [[1.0] for _ in texts]

    log = CallLog()
    fields = log.wrap("분야 고르기", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(text='{"분야": ["MO"]}')))
    embedder = log.wrap("임베딩", Embedder())
    log.start()
    assert fields.ask_json(MESSAGES, {"type": "object"}, 5.0) == {"분야": ["MO"]}
    assert embedder.embed(["a", "b"], 5.0) == [[1.0], [1.0]]
    chosen, embedded = log.take()
    assert chosen["종류"] == "분야 고르기" and chosen["글"] == '{"분야": ["MO"]}' and chosen["입력"] == 1000
    assert embedded["종류"] == "임베딩" and embedded["글 수"] == 2 and embedded["입력"] == 7 and "출력" not in embedded


def test_실패한_호출은_오류를_적고_오류를_그대로_올린다():
    class Broken:
        def stream(self, messages, timeout, first_timeout=None):
            yield "반"
            raise TimeoutError("늦음")

    log = CallLog()
    model = log.wrap("답변", Broken())
    log.start()
    with pytest.raises(TimeoutError):
        list(model.stream(MESSAGES, 1.0))
    [record] = log.take()
    assert record["글"] == "반" and "늦음" in record["오류"] and "끝" in record
    assert "입력" not in record  # 토큰을 세지 않는 부품은 칸을 비운다(0으로 지어내지 않음)


def test_끝까지_받지_못한_호출은_토큰을_0으로_적지_않는다():
    log = CallLog()
    model = log.wrap("답변", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=("가", "나"))))
    log.start()
    stream = model.stream(MESSAGES, 10.0)
    next(stream)
    stream.close()  # 읽는 쪽이 중간에 놓음: 모델은 마지막 셈을 하지 못한다
    [record] = log.take()
    assert record["다 받음"] is False and "입력" not in record and "끝" in record
    broken = log.wrap("분야 고르기", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(stop="max_tokens")))
    log.start()
    with pytest.raises(ValueError):
        broken.ask_json(MESSAGES, {"type": "object"})
    assert "입력" not in log.take()[0]  # 오류로 끝난 호출은 셈이 그 호출 몫인지 알 수 없어 비운다


def test_같은_종류는_만든_차례로_몇째를_매기고_종류별_요금을_합친다():
    log = CallLog()
    first = log.wrap("질문 바꾸기", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(), schema={}))
    second = log.wrap("질문 바꾸기", ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(), schema={}))
    log.wrap("임베딩", object())  # 요금을 셀 수 없는 부품
    log.start()
    list(second.stream(MESSAGES))
    assert log.take()[0]["몇째"] == 1
    list(first.stream(MESSAGES))
    assert log.dollars() == {"질문 바꾸기": pytest.approx(2 * 0.0002), "임베딩": None}


def test_뒤에서_도는_호출이_끝나기를_기다린다():
    log = CallLog()
    release = threading.Event()

    class Slow:
        def stream(self, messages):
            yield '{"query": "a"}'
            release.wait()

    rewriter = log.wrap("질문 바꾸기", Slow())
    log.start()
    stream = rewriter.stream(MESSAGES)
    next(stream)  # 엔진처럼 검색어만 받고 나머지는 뒤에서 읽힌다
    worker = threading.Thread(target=lambda: list(stream))
    worker.start()
    assert log.wait_idle(timeout=0.05) is False  # 넘기면 알리고 멈추지 않는다(앞 차례 결과를 버리지 않게)
    release.set()
    assert log.wait_idle(timeout=5.0) is True
    worker.join()
    assert "끝" in log.take()[0]
