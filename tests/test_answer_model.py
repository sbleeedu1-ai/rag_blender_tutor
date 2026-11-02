"""진짜 답변 모델 연결(티켓 33): 내 PC에 띄운 가짜 OpenAI 서버로 흘려 받기·시간 한도·끊김을 본다(돈이 들지 않음)."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from blender_tutor.answer_model import FirstOf, OpenAIAnswerModel
from blender_tutor.beginner_scope import OpenAIModel

USAGE = {"prompt_tokens": 6000, "completion_tokens": 400, "completion_tokens_details": {"reasoning_tokens": 100}}


def piece(text):
    return {"choices": [{"index": 0, "delta": {"content": text}}]}


@pytest.fixture
def server():
    """보낼 줄 목록(dict는 data: JSON, 글은 그대로, 숫자는 그만큼 쉼)을 정하면 그대로 흘려 주는 서버. 받은 요청 본문을 모은다."""
    plan = {"lines": [], "bodies": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            plan["bodies"].append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for line in plan["lines"]:
                if isinstance(line, float):
                    time.sleep(line)
                    continue
                text = f"data: {json.dumps(line)}" if isinstance(line, dict) else line
                self.wfile.write(f"{text}\n\n".encode("utf-8"))
                self.wfile.flush()

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    plan["url"] = f"http://127.0.0.1:{httpd.server_port}/v1/chat/completions"
    yield plan
    httpd.shutdown()


def model_for(server, effort="low"):
    model = OpenAIAnswerModel("gpt-6-luna", "fake-key", effort)
    model.URL = server["url"]
    return model


def test_답_조각을_오는_대로_돌려주고_토큰과_요금을_센다(server):
    server["lines"] = [piece("베벨은 "), {"choices": [{"index": 0, "delta": {}}]}, piece("모서리를 깎아요."),
                       {"choices": [], "usage": USAGE}, "data: [DONE]"]
    model = model_for(server)
    assert list(model.stream([{"role": "user", "content": "베벨?"}], timeout=5)) == ["베벨은 ", "모서리를 깎아요."]
    body = server["bodies"][0]
    assert (body["model"], body["reasoning_effort"], body["stream"]) == ("gpt-6-luna", "low", True)
    assert body["stream_options"] == {"include_usage": True}
    assert (model.input_tokens, model.output_tokens, model.reasoning_tokens, model.requests) == (6000, 400, 100, 1)
    assert model.dollars() == pytest.approx((6000 * 0.10 + 400 * 0.50) / 1_000_000)


def test_다음_조각이_한도_안에_오지_않으면_TimeoutError(server):
    server["lines"] = [piece("베벨은 "), 1.0, piece("늦은 조각"), "data: [DONE]"]
    pieces = []
    with pytest.raises(TimeoutError):
        for text in model_for(server).stream([], timeout=0.3):
            pieces.append(text)
    assert pieces == ["베벨은 "]


def test_조각_사이가_한도보다_짧으면_전체가_한도보다_길어도_끝까지_받는다(server):
    server["lines"] = [piece("하나"), 0.2, piece("둘"), 0.2, piece("셋"), "data: [DONE]"]
    assert list(model_for(server).stream([], timeout=0.35)) == ["하나", "둘", "셋"]  # 전체는 약 0.4초


def test_끝_표시_없이_흐름이_끊기면_오류(server):
    server["lines"] = [piece("베벨은 ")]
    with pytest.raises(ValueError, match="DONE"):
        list(model_for(server).stream([], timeout=5))


def test_연결_단계에서_늦어도_TimeoutError(monkeypatch):
    # 연결 단계의 시간 초과는 URLError에 싸여 온다(읽기 단계는 위 시험처럼 TimeoutError 그대로)
    def slow(request, timeout):
        raise urllib.error.URLError(socket.timeout("timed out"))

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(TimeoutError):
        list(OpenAIAnswerModel("gpt-6-luna", "fake-key", "none").stream([], timeout=0.3))


def test_흐름_도중_오류_조각이_오면_그_메시지로_오류(server):
    # 공식 라이브러리(openai-python _streaming.py)가 오류로 바꾸는 모양. 버리면 빈 답이 성공처럼 끝난다
    server["lines"] = [piece("베벨은 "), {"error": {"message": "server overloaded"}}, "data: [DONE]"]
    pieces = []
    with pytest.raises(RuntimeError, match="server overloaded"):
        for text in model_for(server).stream([], timeout=5):
            pieces.append(text)
    assert pieces == ["베벨은 "]


# 질문 바꾸기 흘려 받기(티켓 44): beginner_scope.OpenAIModel.stream도 같은 흐름 읽기를 쓴다


def test_질문_바꾸기를_JSON_모드로_흘려_받고_마지막_조각에서_토큰을_센다(server):
    server["lines"] = [piece('{"query": '), piece('"bevel"}'), {"choices": [], "usage": USAGE, "service_tier": "default"},
                       "data: [DONE]"]
    rewriter = OpenAIModel("gpt-6-luna", "fake-key", "none", timeout=5, url=server["url"])
    assert list(rewriter.stream([{"role": "user", "content": "베벨"}])) == ['{"query": ', '"bevel"}']
    body = server["bodies"][0]
    assert (body["stream"], body["response_format"], body["reasoning_effort"]) == (True, {"type": "json_object"}, "none")
    assert (rewriter.input_tokens, rewriter.output_tokens, rewriter.reasoning_tokens, rewriter.requests) == (6000, 400, 100, 1)
    assert rewriter.tiers == {"default": 1}


def test_질문_바꾸기_흐름이_끝_표시_없이_끊기면_오류(server):
    server["lines"] = [piece('{"query": "bevel"}')]
    with pytest.raises(ValueError, match="질문 바꾸기"):
        list(OpenAIModel("gpt-6-luna", "fake-key", timeout=5, url=server["url"]).stream([]))


# 답변 모델 2개 동시(티켓 44)


class Paced:
    """답변 모델 대신: wait초 쉰 뒤 pieces를 차례로 흘려 준다(error면 첫 조각 전에 그 오류). 끝까지 읽혔으면 finished가 열린다."""

    def __init__(self, pieces=(), wait=0.0, error=None, tail=None):
        self.model, self.pieces, self.wait, self.error, self.tail = "luna", pieces, wait, error, tail
        self.reasoning_tokens = 3
        self.finished = threading.Event()

    def stream(self, messages, timeout):
        time.sleep(self.wait)
        if self.error:
            raise self.error
        for text in self.pieces:
            yield text
        if self.tail:
            raise self.tail
        self.finished.set()

    def dollars(self):
        return 0.001


def test_첫_조각이_먼저_온_흐름만_돌려주고_늦은_흐름도_끝까지_읽는다():
    slow = Paced(["늦은 답"], wait=0.2)
    hedged = FirstOf([slow, Paced(["빠른 ", "답"])])
    assert list(hedged.stream([], timeout=5)) == ["빠른 ", "답"]
    assert slow.finished.wait(5)  # 요금을 세려고 늦은 흐름도 끝까지 읽는다
    assert hedged.model == "luna×2" and hedged.dollars() == pytest.approx(0.002) and hedged.reasoning_tokens == 6


def test_조각_없이_먼저_끝난_흐름은_고르지_않고_모두_비면_빈_답():
    assert list(FirstOf([Paced([]), Paced(["답"], wait=0.1)]).stream([], timeout=5)) == ["답"]
    assert list(FirstOf([Paced([]), Paced(error=OSError("끊김"), wait=0.1)]).stream([], timeout=5)) == []


def test_첫_조각_전에_실패한_흐름은_건너뛰고_모두_실패하면_첫_오류():
    assert list(FirstOf([Paced(error=OSError("끊김")), Paced(["답"], wait=0.1)]).stream([], timeout=5)) == ["답"]
    with pytest.raises(OSError, match="첫"):
        list(FirstOf([Paced(error=OSError("첫")), Paced(error=TimeoutError("둘째"), wait=0.1)]).stream([], timeout=5))


def test_고른_흐름이_도중에_실패하면_다른_흐름으로_바꾸지_않고_그_오류를_낸다():
    pieces = []
    with pytest.raises(RuntimeError, match="도중"):
        for text in FirstOf([Paced(["먼저 "], tail=RuntimeError("도중")), Paced(["늦은 답"], wait=0.2)]).stream([], timeout=5):
            pieces.append(text)
    assert pieces == ["먼저 "]  # 이미 보인 글에 다른 답을 이어 붙이지 않는다
