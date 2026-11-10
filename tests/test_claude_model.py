"""Claude 모델 연결(HISTORY [270]). 공식 라이브러리 대신 가짜 client를 끼워 요청 모양과 응답 읽기만 본다(키·돈 없이 돈다)."""

import json
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
