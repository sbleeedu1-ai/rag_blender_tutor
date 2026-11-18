"""호출 기록: 답 시험(evaluate run)이 차례마다 바깥 호출(질문 바꾸기·분야 고르기·임베딩·답변)의 시각·토큰·주고받은 글을 남긴다.

무엇이 효과였는지 채점 없이 가르려고 모델이 실제로 받은 글과 단계별 시간을 남긴다(docs/plan/01 A, HISTORY [459]).
부품을 겉으로 감쌀 뿐 주고받는 글은 그대로 넘기므로 답·검색 결과는 감싸기 전과 같다. 도우미 창은 쓰지 않는다.
speed_trial.Calls·TimedRewriter·TimedAnswer와 같은 방식이고, 그쪽은 OpenAI 판 엔진에 묶여 있어 따로 둔다.
"""

import json
import threading
import time
from collections.abc import Callable, Iterator

from blender_tutor.answer_engine import CLOSED_QUERY

IDLE_WAIT = 60.0  # 다음 차례 전에 뒤에서 도는 호출(질문 바꾸기의 남은 글 등)이 끝나기를 기다리는 한도(초)
SENT_KINDS = ("답변", "예비 답변")  # 보낸 글 전문을 남기는 종류(답 모델). 질문 바꾸기·분야 고르기 지시는 차례마다 거의 같아 뺀다


class CallLog:
    """차례 하나 동안의 호출 기록. 시각은 start()부터 잰 초. 감싼 부품은 종류별로 들고 있어 요금을 종류별로 합친다."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._records: list[dict] = []
        self._parts: dict[str, list] = {}  # 종류 → 감싼 속 부품들(만든 차례)
        self._open = 0
        self._idle = threading.Condition()
        self._start = clock()

    def wrap(self, kind: str, part):
        """부품을 기록 겉으로 감싼다. 같은 종류는 감싼 차례로 몇째(0부터)를 매긴다."""
        slot = len(self._parts.setdefault(kind, []))
        self._parts[kind].append(part)
        if kind == "임베딩":
            return _TimedEmbedder(part, self, kind, slot)
        return _TimedModel(part, self, kind, slot)

    def start(self) -> None:
        """새 차례: 기록을 비우고 시계를 0으로."""
        with self._idle:
            self._records = []
        self._start = self.clock()

    def now(self) -> float:
        return round(self.clock() - self._start, 4)

    def take(self) -> list[dict]:
        """이 차례의 기록(보낸 차례). 뒤에서 도는 호출이 있으면 먼저 wait_idle로 기다린다."""
        with self._idle:
            return list(self._records)

    def wait_idle(self, timeout: float = IDLE_WAIT) -> bool:
        """뒤에서 도는 호출이 모두 끝날 때까지 기다린다. 모두 끝났으면 True, timeout초를 넘기면 False.
        넘겨도 멈추지 않는다(유료 실행의 앞 차례 결과를 버리지 않게). 부르는 쪽이 그 차례에 표시해 셈이 섞였을 수 있음을 알린다."""
        with self._idle:
            return self._idle.wait_for(lambda: self._open == 0, timeout)

    def dollars(self) -> dict[str, float | None]:
        """종류 → 그 종류 부품들의 요금 합(달러). 요금을 셀 수 없는 부품(dollars가 없는 가짜)이 끼면 None."""
        found = {}
        for kind, parts in self._parts.items():
            prices = [part.dollars() for part in parts if hasattr(part, "dollars")]
            found[kind] = round(sum(prices), 6) if len(prices) == len(parts) else None
        return found

    def _begin(self, kind: str, slot: int) -> dict:
        record = {"종류": kind, "몇째": slot, "보냄": self.now()}
        with self._idle:
            self._open += 1
            self._records.append(record)
        return record

    def _end(self, record: dict, part, before: dict[str, int], counted: bool) -> None:
        """counted가 아니면(오류·중간에 놓음) 토큰 칸을 비운다. 속 모델은 끝까지 받아야 셈을 하므로 0이 '셌는데 0'과 섞이지 않게."""
        if counted:
            for name, value in _tokens(part).items():
                record[name] = value - before[name]
        record["끝"] = self.now()
        with self._idle:
            self._open -= 1
            self._idle.notify_all()


# 토큰 칸 이름 → 속 부품의 쌓인 셈 이름(ClaudeModel·OpenAI 모델은 앞의 셋, OpenAI 임베딩은 tokens)
_COUNTERS = {"입력": ("input_tokens", "tokens"), "출력": ("output_tokens",), "생각": ("reasoning_tokens",)}


def _tokens(part) -> dict[str, int]:
    """속 부품이 지금까지 센 토큰. 세지 않는 부품(가짜)은 그 칸을 뺀다(0으로 지어내지 않게)."""
    found = {}
    for name, attributes in _COUNTERS.items():
        for attribute in attributes:
            if isinstance(value := getattr(part, attribute, None), int):
                found[name] = value
                break
    return found


class _Timed:
    def __init__(self, inner, log: CallLog, kind: str, slot: int):
        self.inner, self._log, self._kind, self._slot = inner, log, kind, slot

    def __getattr__(self, name):  # model·dollars·reasoning_tokens 등은 속 부품의 것
        return getattr(self.inner, name)


class _TimedModel(_Timed):
    """질문 바꾸기(stream(messages))·답변(stream(messages, timeout))·분야 고르기(ask_json) 겉."""

    def stream(self, messages: list[dict[str, str]], *args) -> Iterator[str]:
        record, before, text, finished = self._log._begin(self._kind, self._slot), _tokens(self.inner), "", False
        if self._kind in SENT_KINDS:
            record["보낸 글"] = messages
        try:
            for piece in self.inner.stream(messages, *args):
                if "첫 조각" not in record:
                    record["첫 조각"] = self._log.now()
                text += piece
                if self._kind == "질문 바꾸기" and "검색어 닫힘" not in record and "빈 검색어" not in record \
                        and (match := CLOSED_QUERY.search(text)):
                    # 엔진(closed_query)처럼 빈 검색어는 쓸 수 없는 답이라 닫힘으로 치지 않는다
                    record["검색어 닫힘" if json.loads(match.group(1)).strip() else "빈 검색어"] = self._log.now()
                yield piece
            finished = True
        except Exception as error:
            record["오류"] = repr(error)
            raise
        finally:
            record["글"] = text
            if not finished and "오류" not in record:
                record["다 받음"] = False  # 읽는 쪽이 중간에 놓음
            self._log._end(record, self.inner, before, finished)

    def ask_json(self, messages: list[dict[str, str]], schema: dict, timeout: float | None = None) -> dict:
        record, before = self._log._begin(self._kind, self._slot), _tokens(self.inner)
        try:
            answer = self.inner.ask_json(messages, schema, timeout)
            record["글"] = json.dumps(answer, ensure_ascii=False)
            return answer
        except Exception as error:
            record["오류"] = repr(error)
            raise
        finally:
            self._log._end(record, self.inner, before, "오류" not in record)


class _TimedEmbedder(_Timed):
    def embed(self, texts, timeout: float):
        record, before = self._log._begin(self._kind, self._slot), _tokens(self.inner)
        record["글 수"] = len(texts)
        try:
            return self.inner.embed(texts, timeout)
        except Exception as error:
            record["오류"] = repr(error)
            raise
        finally:
            self._log._end(record, self.inner, before, "오류" not in record)

