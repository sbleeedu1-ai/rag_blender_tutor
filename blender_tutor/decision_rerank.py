"""위 200 리랭킹(HISTORY [626]): 뜻 검색 위 200개 청크를 Gemini Decision API에 예/아니오(noul)로 묻고, 확률 순으로 다시 세운다.

차례 13번 시험(`data/eval/dev50/rerank_trial.py`·`full200_trial.py`, 474실행 중 정답 청크 묶음이 모두 8위 안 192, 기준 182)과
같은 요청 꼴을 쓴다. 지시 문구·질문 이름·꼴을 바꾸면 그 숫자는 이 제품에 대한 근거가 되지 못한다(실험 기록 "차례 13번").
noul 값이 클수록 "예"라는 방향은 시험 때 방향 시험으로 확인했다(맞는 조각 > 무관한 조각).
돈이 든다(검색 한 번 약 4.3만 입력 토큰, 시험 기록의 중앙값).
"""

import json
import urllib.error
import urllib.request
from collections.abc import Sequence

from blender_tutor.beginner_scope import api_key

URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
MODEL = "gemini-decision-1"
PRICE_PER_MILLION = 0.10  # 입력 100만 토큰당 달러(요금 쪽 요약으로 읽은 값, 11-23. 출력 토큰은 0으로 옴)
INSTRUCTION = (
    "The input is a search query written by someone learning Blender 5.2. "
    "Does the following passage from the Blender 5.2 manual contain information that helps answer that query?\n\nPassage:\n"
)


def gemini_key() -> str:
    """환경 변수 GEMINI_API_KEY, 없으면 data/.env의 같은 이름 줄. 없으면 SystemExit."""
    return api_key("GEMINI_API_KEY", "Gemini")


class DecisionReranker:
    """Gemini Decision 판정기. 글마다 "검색어에 답하는 데 도움이 되나"의 예 확률을 돌려준다. 받은 입력 토큰·요청 수를 쌓는다."""

    def __init__(self, key: str, model: str = MODEL):
        self.key, self.model = key, model
        self.input_tokens = self.requests = 0

    def judge(self, query: str, passages: Sequence[str], timeout: float) -> list[float]:
        """passages 차례대로 예 확률. timeout초 안에 응답이 없으면 TimeoutError, 답에 빠진 글이 있으면 ValueError."""
        names = [f"c{i:02d}" for i in range(len(passages))]  # 시험과 같은 이름(c00-c199)
        body = {"model": self.model, "input": query,
                "questions": {name: {"type": "noul", "instructions": INSTRUCTION + text} for name, text in zip(names, passages)}}
        request = urllib.request.Request(URL, json.dumps(body).encode("utf-8"),
                                         {"Content-Type": "application/json", "x-goog-api-key": self.key}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                answer = json.loads(response.read())
        except urllib.error.URLError as error:  # 연결 단계의 시간 초과는 URLError에 싸여 온다. 읽기 단계는 TimeoutError 그대로
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(f"리랭킹 응답이 {timeout}초 안에 오지 않음") from error
            raise
        self.requests += 1
        self.input_tokens += answer.get("usage", {}).get("total_input_tokens", 0)  # 빠진 답이 있어도 받은 요청의 값은 센다
        answers = answer.get("answers", {})
        if missing := [name for name in names if "noul" not in answers.get(name, {})]:
            raise ValueError(f"리랭킹 답에 빠진 글 {len(missing)}개: {', '.join(missing[:5])}")
        return [float(answers[name]["noul"]) for name in names]

    def dollars(self) -> float:
        return round(self.input_tokens / 1_000_000 * PRICE_PER_MILLION, 6)


def rerank(order: Sequence[int], probs: Sequence[float]) -> list[int]:
    """확률이 큰 순, 같은 확률은 원래 순위 순(시험 도구 rerank_trial.rerank와 같음)."""
    return [item for _, _, item in sorted((-p, i, item) for i, (p, item) in enumerate(zip(probs, order)))]
