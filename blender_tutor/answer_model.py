"""진짜 답변 모델(티켓 33): OpenAI Chat Completions에 대화 글을 보내고 답 글 조각을 오는 대로 돌려준다(돈이 든다).

답 엔진(answer_engine)의 AnswerModel 약속을 지킨다: timeout초 동안 다음 조각이 오지 않으면 TimeoutError.
연결은 소켓 한도로 지킨다. 소켓 한도는 '읽기 한 번'에 걸리므로 답 전체 시간이 아니라 조각 사이 시간 한도가 된다.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator

MODEL = "gpt-6-luna"  # 명세 기본 답변 모델
PRICE = {"gpt-6-luna": (0.10, 0.50)}  # 100만 토큰당 입력·출력 달러(.scratch/.../31-번역-모델-조사.md, search_compare와 같은 값)


class OpenAIAnswerModel:
    """생각 수준(effort: none·low·medium)을 정해 답을 흘려 받는다. 받은 토큰·요청 수를 쌓아 둔다."""

    URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str, key: str, effort: str):
        self.model, self.key, self.effort = model, key, effort
        self.input_tokens = self.output_tokens = self.reasoning_tokens = self.requests = 0

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterator[str]:
        body = {
            "model": self.model, "messages": messages, "reasoning_effort": self.effort,
            "stream": True, "stream_options": {"include_usage": True},  # 마지막 조각에 토큰 수가 온다
        }
        request = urllib.request.Request(
            self.URL, json.dumps(body).encode("utf-8"),
            {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            response = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.URLError as error:  # 연결 단계의 시간 초과는 URLError에 싸여 온다. 읽기 단계는 TimeoutError 그대로
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(f"답변 모델이 {timeout}초 안에 연결되지 않음") from error
            raise
        with response:
            self.requests += 1
            for line in response:  # 서버가 보내는 줄: "data: {조각 JSON}" … "data: [DONE]", 사이사이 빈 줄
                data = line.decode("utf-8").strip().removeprefix("data:").strip()
                if not data:
                    continue
                if data == "[DONE]":
                    return
                piece = json.loads(data)
                # 흐름 도중 오류 조각. 공식 라이브러리(openai-python _streaming.py)와 같은 규칙으로 오류를 낸다(버리면 빈 답이 성공처럼 끝남)
                if error := piece.get("error"):
                    message = error.get("message") if isinstance(error, dict) else None
                    raise RuntimeError(f"답변 모델 흐름 도중 오류: {message or '알 수 없는 오류'}")
                if usage := piece.get("usage"):
                    self._count(usage)
                for choice in piece.get("choices", []):
                    if text := choice.get("delta", {}).get("content"):
                        yield text
        raise ValueError("답변 모델의 흐름이 끝 표시([DONE]) 없이 끊김")

    def _count(self, usage: dict) -> None:
        self.input_tokens += usage["prompt_tokens"]
        self.output_tokens += usage["completion_tokens"]  # 생각 토큰을 포함한 출력(이것으로 요금을 매긴다)
        self.reasoning_tokens += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)

    def dollars(self) -> float:
        input_price, output_price = PRICE[self.model]
        return round((self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000, 6)
