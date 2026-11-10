"""Claude(Haiku 5.5) 모델 연결(2026-11-10, HISTORY [270]): 질문 바꾸기·분야 고르기·답변을 모두 Haiku로 부른다(돈이 든다).

답 엔진의 약속을 지킨다.
- 질문 바꾸기(Rewriter): stream(messages) → 답 글 조각. 지시는 OpenAI 방식 대화 글(역할 system·user)로 받아 Claude 모양으로 옮긴다.
- 답변(AnswerModel): stream(messages, timeout) → 답 글 조각. timeout초 동안 다음 조각이 없으면 TimeoutError.
- 분야 고르기: ask_json(messages, schema) → 구조화된 출력(JSON 스키마)으로 받은 dict.

생각 수준(answer_engine.Reasoning): none이면 생각 끔(Haiku 5.5는 effort high 이하에서만 끌 수 있고 기본 effort는 medium),
low·medium이면 생각 켬(adaptive)과 그 effort(claude-api 스킬 Thinking & Effort 표). 공식 anthropic 파이썬 라이브러리로 부른다.
자동 재시도는 끈다(시간 한도를 우리가 재므로). 키는 data/.env 또는 환경 변수 ANTHROPIC_API_KEY.
"""

import json
import logging
from collections.abc import Iterator

import anthropic

from blender_tutor.beginner_scope import api_key

log = logging.getLogger(__name__)

MODEL = "claude-haiku-5-5"
PRICE = {MODEL: (0.10, 0.50)}  # 100만 토큰당 입력·출력 달러(질문 10만 토큰 이하, claude-api 스킬 모델 표 2026-11-03판)
CONNECT_TIMEOUT = 10.0  # 연결까지 기다리는 한도(초). 조각 사이 한도는 부를 때 받은 timeout


def anthropic_key() -> str:
    """환경 변수 ANTHROPIC_API_KEY, 없으면 data/.env의 같은 이름 줄. 없으면 SystemExit."""
    return api_key("ANTHROPIC_API_KEY", "Anthropic")


def thinking_for(reasoning: str) -> dict:
    """생각 수준 이름 → 요청 칸(thinking·output_config). none은 끔, 나머지는 adaptive + 그 effort."""
    if reasoning == "none":
        return {"thinking": {"type": "disabled"}}
    return {"thinking": {"type": "adaptive"}, "output_config": {"effort": reasoning}}


def claude_messages(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """OpenAI 방식 대화 글을 (지시, 나머지 대화)로 나눈다. Claude는 지시를 따로 받는다. 지시가 여럿이면 빈 줄로 잇는다."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    if not rest or rest[0]["role"] != "user":
        raise ValueError("Claude 대화는 사용자 글로 시작해야 함")
    return system, rest


class ClaudeModel:
    """Claude 모델 하나. 받은 토큰·요청 수를 쌓아 둔다(요금 계산용). 동시에 부를 것은 하나씩 따로 만든다."""

    def __init__(self, model: str, key: str, reasoning: str = "none", max_tokens: int = 4096,
                 timeout: float = 10.0, schema: dict | None = None, client=None):
        """schema를 주면 stream도 그 JSON 스키마로 답하게 한다(질문 바꾸기). timeout은 stream(messages)처럼 한도를 받지 않을 때 쓴다.
        client는 시험에서 가짜를 끼우는 자리(없으면 공식 라이브러리로 만든다)."""
        self.model, self.reasoning, self.max_tokens, self.timeout, self.schema = model, reasoning, max_tokens, timeout, schema
        self._client = client or anthropic.Anthropic(api_key=key, max_retries=0)
        self.input_tokens = self.output_tokens = self.reasoning_tokens = self.requests = 0

    def _body(self, messages: list[dict[str, str]], schema: dict | None) -> dict:
        system, rest = claude_messages(messages)
        body = {"model": self.model, "max_tokens": self.max_tokens, "messages": rest, **thinking_for(self.reasoning)}
        if system:
            body["system"] = system
        if schema:
            body.setdefault("output_config", {})["format"] = {"type": "json_schema", "schema": schema}
        return body

    def _client_for(self, timeout: float):
        return self._client.with_options(timeout=anthropic.Timeout(timeout, connect=CONNECT_TIMEOUT))

    def stream(self, messages: list[dict[str, str]], timeout: float | None = None) -> Iterator[str]:
        """답 글 조각을 오는 대로 돌려준다. timeout초 동안 다음 조각이 없으면 TimeoutError(라이브러리의 시간 초과를 바꿔 낸다).
        생각 블록은 글이 아니라서 내지 않는다. 답이 max_tokens에서 잘리면 기록만 남긴다(받은 데까지는 이미 보였다)."""
        limit = self.timeout if timeout is None else timeout
        try:
            with self._client_for(limit).messages.stream(**self._body(messages, self.schema)) as response:
                self.requests += 1
                yield from response.text_stream
                final = response.get_final_message()
        except anthropic.APITimeoutError as error:
            raise TimeoutError(f"{self.model}이 {limit}초 안에 다음 조각을 보내지 않음") from error
        self._count(final.usage)
        if final.stop_reason != "end_turn":
            log.warning("%s 답이 %s로 끝남", self.model, final.stop_reason)

    def ask_json(self, messages: list[dict[str, str]], schema: dict, timeout: float | None = None) -> dict:
        """구조화된 출력으로 한 번에 받아 dict로. 끝까지 쓰지 못했으면(max_tokens·거절) ValueError, 시간 초과면 TimeoutError."""
        limit = self.timeout if timeout is None else timeout
        try:
            answer = self._client_for(limit).messages.create(**self._body(messages, schema))
        except anthropic.APITimeoutError as error:
            raise TimeoutError(f"{self.model}이 {limit}초 안에 답하지 않음") from error
        self.requests += 1
        self._count(answer.usage)
        if answer.stop_reason != "end_turn":
            raise ValueError(f"{self.model} 답이 {answer.stop_reason}로 끝나 JSON을 다 받지 못함")
        return json.loads("".join(block.text for block in answer.content if block.type == "text"))

    def _count(self, usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens  # 생각 토큰을 포함한 출력(이것으로 요금을 매긴다)
        details = getattr(usage, "output_tokens_details", None)  # 생각 토큰 수(가설 16 응답에서 본 칸, 없으면 0)
        self.reasoning_tokens += getattr(details, "thinking_tokens", 0) or 0

    def dollars(self) -> float:
        input_price, output_price = PRICE[self.model]
        return round((self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000, 6)
