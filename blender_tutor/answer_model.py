"""진짜 답변 모델(티켓 33): OpenAI Chat Completions에 대화 글을 보내고 답 글 조각을 오는 대로 돌려준다(돈이 든다).

답 엔진(answer_engine)의 AnswerModel 약속을 지킨다: timeout초 동안 다음 조각이 오지 않으면 TimeoutError.
연결은 소켓 한도로 지킨다. 소켓 한도는 '읽기 한 번'에 걸리므로 답 전체 시간이 아니라 조각 사이 시간 한도가 된다.
"""

import json
import queue
import threading
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator, Sequence
from http.client import HTTPResponse
from typing import Protocol

MODEL = "gpt-6-luna"  # 명세 기본 답변 모델
COPIES = 2  # 같은 질문을 동시에 보내는 답변 모델 수. 첫 조각이 먼저 온 쪽을 쓴다(티켓 44)
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
            for piece in events(response, "답변 모델"):
                if usage := piece.get("usage"):
                    self._count(usage)
                for choice in piece.get("choices", []):
                    if text := choice.get("delta", {}).get("content"):
                        yield text

    def _count(self, usage: dict) -> None:
        self.input_tokens += usage["prompt_tokens"]
        self.output_tokens += usage["completion_tokens"]  # 생각 토큰을 포함한 출력(이것으로 요금을 매긴다)
        self.reasoning_tokens += (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)

    def dollars(self) -> float:
        input_price, output_price = PRICE[self.model]
        return round((self.input_tokens * input_price + self.output_tokens * output_price) / 1_000_000, 6)


def events(response: HTTPResponse, label: str) -> Iterator[dict]:
    """흘려 받는 응답(줄마다 "data: {조각 JSON}" … "data: [DONE]", 사이사이 빈 줄)의 조각 JSON을 차례로 돌려준다.
    흐름 도중 오류 조각이면 RuntimeError(공식 라이브러리 openai-python _streaming.py와 같은 규칙, 버리면 빈 답이 성공처럼 끝남),
    끝 표시 없이 끊기면 ValueError. label은 오류 글에 붙일 이름(답변 모델·질문 바꾸기)."""
    for line in response:
        data = line.decode("utf-8").strip().removeprefix("data:").strip()
        if not data:
            continue
        if data == "[DONE]":
            return
        piece = json.loads(data)
        if error := piece.get("error"):
            message = error.get("message") if isinstance(error, dict) else None
            raise RuntimeError(f"{label} 흐름 도중 오류: {message or '알 수 없는 오류'}")
        yield piece
    raise ValueError(f"{label}의 흐름이 끝 표시([DONE]) 없이 끊김")


class Streaming(Protocol):
    """FirstOf에 끼울 답변 모델: 답 조각을 흘려 주고(조각 사이 timeout초 한도), 이름·쌓인 생각 토큰·요금을 안다."""

    model: str
    reasoning_tokens: int

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterable[str]: ...

    def dollars(self) -> float: ...


class FirstOf:
    """같은 대화를 답변 모델 여러 개에 동시에 보내, 첫 조각이 가장 먼저 온 흐름만 돌려준다(티켓 44, 헤지 요청).

    나머지 흐름도 뒤에서 끝까지 읽는다(마지막 조각의 토큰 수로 요금을 세려고). 조각 사이 시간 한도는 각 모델이 지킨다.
    조각 없이 끝나거나 첫 조각 전에 실패한 흐름은 건너뛴다. 모두 그렇게 끝나면 빈 답으로 끝내고(하나라도 정상으로 끝났을 때),
    모두 실패했으면 첫 오류를 낸다. 고른 흐름이 도중에 실패하면 다른 흐름으로 바꾸지 않고 그 오류를 낸다(이미 보인 글에 다른 답을 잇지 않게).
    요금·생각 토큰은 나머지 흐름이 아직 읽히는 중이면 그만큼 덜 세진다(평가가 끝에 한 번 읽을 때 마지막 질문 몫).
    """

    def __init__(self, models: Sequence[Streaming]):
        self.models = list(models)
        self.model = f"{self.models[0].model}×{len(self.models)}"  # 엔진 이름·결과 기록에 남는 이름

    def stream(self, messages: list[dict[str, str]], timeout: float) -> Iterator[str]:
        arrived: queue.Queue = queue.Queue()  # (몇째 모델, "조각"·"끝"·"오류", 값)
        for index, model in enumerate(self.models):
            threading.Thread(target=_pump, args=(model, messages, timeout, index, arrived), daemon=True).start()
        chosen, errors, empty = None, [], 0
        while True:
            index, kind, value = arrived.get()  # 각 모델이 시간 한도를 지키므로 언젠가 반드시 온다
            if chosen is None:
                if kind == "조각":
                    chosen = index
                else:
                    errors += [value] if kind == "오류" else []
                    empty += kind == "끝"
                    if len(errors) + empty == len(self.models):
                        if empty:
                            return
                        raise errors[0]
                    continue
            if index != chosen:
                continue
            if kind == "끝":
                return
            if kind == "오류":
                raise value
            yield value

    @property
    def reasoning_tokens(self) -> int:
        return sum(model.reasoning_tokens for model in self.models)

    def dollars(self) -> float:
        return round(sum(model.dollars() for model in self.models), 6)


def _pump(model: Streaming, messages: list[dict[str, str]], timeout: float, index: int, arrived: queue.Queue) -> None:
    """모델 하나의 흐름을 끝까지 읽어 조각·끝·오류를 arrived에 넣는다(뒤에서 도는 일)."""
    try:
        for text in model.stream(messages, timeout):
            arrived.put((index, "조각", text))
    except Exception as error:
        arrived.put((index, "오류", error))
        return
    arrived.put((index, "끝", None))
