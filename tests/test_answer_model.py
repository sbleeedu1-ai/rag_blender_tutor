"""진짜 답변 모델 연결(티켓 33): 내 PC에 띄운 가짜 OpenAI 서버로 흘려 받기·시간 한도·끊김을 본다(돈이 들지 않음)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from blender_tutor.answer_model import OpenAIAnswerModel

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
