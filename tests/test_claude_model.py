"""Claude 모델 연결(HISTORY [270]). 공식 라이브러리 대신 가짜 client를 끼워 요청 모양과 응답 읽기만 본다(키·돈 없이 돈다)."""

import http.server
import json
import threading
import time
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from blender_tutor.claude_model import ClaudeModel, claude_messages, thinking_for

USAGE = SimpleNamespace(input_tokens=1000, output_tokens=200)


class FakeStream:
    def __init__(self, pieces, stop="end_turn", error=None):
        self.text_stream = self._pieces(pieces, error)
        self._final = SimpleNamespace(usage=USAGE, stop_reason=stop)

    @staticmethod
    def _pieces(pieces, error):
        yield from pieces
        if error:
            raise error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get_final_message(self):
        return self._final


class FakeClient:
    """with_options(timeout=…)와 messages.stream·create만 흉내 낸다. 받은 요청과 한도를 적어 둔다."""

    def __init__(self, pieces=("{\"query\": ", "\"bevel\"}"), text='{"분야": ["MO"]}', stop="end_turn", error=None):
        self.pieces, self.text, self.stop, self.error = pieces, text, stop, error
        self.bodies, self.timeouts = [], []
        self.messages = SimpleNamespace(stream=self._stream, create=self._create)

    def with_options(self, timeout):
        self.timeouts.append(timeout)
        return self

    def _stream(self, **body):
        self.bodies.append(body)
        return FakeStream(self.pieces, self.stop, self.error)

    def _create(self, **body):
        self.bodies.append(body)
        if self.error:
            raise self.error
        content = [SimpleNamespace(type="text", text=self.text)]
        return SimpleNamespace(content=content, usage=USAGE, stop_reason=self.stop)


MESSAGES = [{"role": "system", "content": "지시"}, {"role": "user", "content": "질문"}]


def timeout_error():
    return anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_생각_수준_none은_생각_끔_나머지는_adaptive와_effort():
    assert thinking_for("none") == {"thinking": {"type": "disabled"}}
    assert thinking_for("low") == {"thinking": {"type": "adaptive"}, "output_config": {"effort": "low"}}


def test_지시는_따로_떼고_대화는_사용자_글로_시작해야_한다():
    assert claude_messages(MESSAGES) == ("지시", [{"role": "user", "content": "질문"}])
    with pytest.raises(ValueError):
        claude_messages([{"role": "system", "content": "지시"}, {"role": "assistant", "content": "답"}])


def test_흘려_받기는_글_조각을_내고_토큰을_센다():
    client = FakeClient()
    model = ClaudeModel("claude-haiku-5-5", "k", "none", max_tokens=1024, schema={"type": "object"}, client=client)
    assert "".join(model.stream(MESSAGES, 3.0)) == '{"query": "bevel"}'
    body = client.bodies[0]
    assert body["system"] == "지시" and body["messages"] == [{"role": "user", "content": "질문"}] and body["max_tokens"] == 1024
    assert body["thinking"] == {"type": "disabled"} and body["output_config"]["format"] == {"type": "json_schema", "schema": {"type": "object"}}
    assert client.timeouts[0].read == 3.0 and (model.requests, model.input_tokens, model.output_tokens) == (1, 1000, 200)
    assert model.dollars() == round((1000 * 0.10 + 200 * 0.50) / 1_000_000, 6)


def test_조각_사이_시간_초과는_TimeoutError로_바꾼다():
    model = ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(error=timeout_error()))
    with pytest.raises(TimeoutError):
        list(model.stream(MESSAGES, 1.0))


def test_한도를_받지_않는_질문_바꾸기는_만들_때_정한_한도를_쓴다():
    client = FakeClient()
    list(ClaudeModel("claude-haiku-5-5", "k", timeout=5.0, client=client).stream(MESSAGES))
    assert client.timeouts[0].read == 5.0


def test_구조화된_출력은_dict로_받고_끝까지_못_쓰면_ValueError():
    client = FakeClient(text=json.dumps({"분야": ["MO"]}))
    model = ClaudeModel("claude-haiku-5-5", "k", "low", client=client)
    assert model.ask_json(MESSAGES, {"type": "object"}, 2.0) == {"분야": ["MO"]}
    assert client.bodies[0]["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    with pytest.raises(ValueError):
        ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(stop="max_tokens")).ask_json(MESSAGES, {"type": "object"})
    with pytest.raises(TimeoutError):
        ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(error=timeout_error())).ask_json(MESSAGES, {"type": "object"})


def test_답_도중_바이트가_한도보다_늦어_라이브러리_밖_시간_초과가_나도_TimeoutError로_바꾼다():
    # 흘려 받는 도중의 시간 초과는 anthropic이 감싸지 않은 httpx2.ReadTimeout으로 올라온다(05 medium Q22·Q23 3회, 1-1)
    model = ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=(), error=httpx2.ReadTimeout("The read operation timed out")))
    with pytest.raises(TimeoutError):
        list(model.stream(MESSAGES, 1.0))


@pytest.mark.parametrize("stop", ["max_tokens", "end_turn"])
def test_글이_0자인_채_끝난_답은_실패로_알리고_받은_토큰은_센다(stop):
    # 생각이 답 길이 한도를 다 쓰면 글 없이 끝난다. 빈 답을 끝난 답처럼 내지 않는다(1-1 버그 ②)
    model = ClaudeModel("claude-haiku-5-5", "k", "medium", client=FakeClient(pieces=(), stop=stop))
    with pytest.raises(ValueError, match=stop):
        list(model.stream(MESSAGES, 1.0))
    assert (model.requests, model.output_tokens) == (1, 200)


def test_글이_나오다_한도에서_잘린_답은_받은_데까지_내고_실패로_보지_않는다():
    model = ClaudeModel("claude-haiku-5-5", "k", client=FakeClient(pieces=("베벨 ", "모디"), stop="max_tokens"))
    assert "".join(model.stream(MESSAGES, 1.0)) == "베벨 모디"


class _SilentThinking(http.server.BaseHTTPRequestHandler):
    """내 PC에 띄우는 가짜 Claude 서버: 생각 블록을 연 뒤 server.pause초 아무것도 보내지 않고, server.text가 있으면 그 글로 끝난다."""

    def log_message(self, *_):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        usage = {"input_tokens": 1, "output_tokens": 1}
        self._send("message_start", {"type": "message_start", "message": {"id": "m", "type": "message", "role": "assistant", "model": "x", "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}})
        self._send("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
        time.sleep(self.server.pause)
        self._send("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "signature_delta", "signature": "s"}})
        self._send("content_block_stop", {"type": "content_block_stop", "index": 0})
        stop = "max_tokens"
        if self.server.text:
            stop = "end_turn"
            self._send("content_block_start", {"type": "content_block_start", "index": 1, "content_block": {"type": "text", "text": ""}})
            self._send("content_block_delta", {"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": self.server.text}})
            self._send("content_block_stop", {"type": "content_block_stop", "index": 1})
        self._send("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 4096}})
        self._send("message_stop", {"type": "message_stop"})

    def _send(self, event, data):
        self.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # 우리 쪽이 먼저 끊어 쓰기가 실패하는 것은 시험이 노린 일이다


@pytest.fixture
def silent_server():
    servers = []

    def start(pause, text=""):
        server = _QuietServer(("127.0.0.1", 0), _SilentThinking)
        server.pause, server.text = pause, text
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        client = anthropic.Anthropic(api_key="x", base_url=f"http://127.0.0.1:{server.server_port}", max_retries=0)
        return ClaudeModel("claude-haiku-5-5", "k", "medium", client=client)

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_진짜_라이브러리로_생각하는_동안_한도보다_오래_조용하면_TimeoutError(silent_server):
    with pytest.raises(TimeoutError):
        list(silent_server(pause=0.8).stream(MESSAGES, 0.3))


def test_진짜_라이브러리로_생각만_하고_글_없이_한도에서_끝나면_ValueError(silent_server):
    with pytest.raises(ValueError, match="max_tokens"):
        list(silent_server(pause=0.0).stream(MESSAGES, 2.0))


def test_진짜_라이브러리로_한도_안에_글이_오면_그대로_받는다(silent_server):
    assert "".join(silent_server(pause=0.1, text="베벨").stream(MESSAGES, 2.0)) == "베벨"
