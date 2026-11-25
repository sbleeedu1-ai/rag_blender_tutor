"""위 200 리랭킹의 판정기(Gemini Decision, HISTORY [626]). 진짜 서버는 부르지 않고 urllib를 가짜로 바꿔 보낸 요청과 받은 답만 본다."""

import io
import json
import socket
import urllib.error
import urllib.request

import pytest

from blender_tutor.decision_rerank import INSTRUCTION, DecisionReranker, rerank


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def serve(monkeypatch, answer: dict) -> list:
    """urlopen을 가짜로 바꿔 answer를 돌려주고, 받은 (요청, 시간 한도)를 모은다."""
    sent, contexts = [], []

    def fake(request, timeout, context=None):
        sent.append((request, timeout))
        contexts.append(context)
        return Reply(json.dumps(answer).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    serve.contexts = contexts  # type: ignore[attr-defined]
    return sent


def answers(*probs) -> dict:
    return {"answers": {f"c{i:02d}": {"noul": p} for i, p in enumerate(probs)},
            "usage": {"total_input_tokens": 1234, "total_output_tokens": 0}}


def test_요청은_차례_13번_시험과_같은_꼴로_보낸다(monkeypatch):
    # 시험 도구 rerank_trial.ask와 같은 몸통이어야 시험의 192가 제품에도 뜻을 가진다
    sent = serve(monkeypatch, answers(0.1, 0.9))
    DecisionReranker("가짜 키").judge("bevel width", ["Width sets the size.", "Array copies."], timeout=5.0)
    request, timeout = sent[0]
    body = json.loads(request.data)
    assert body == {
        "model": "gemini-decision-1", "input": "bevel width",
        "questions": {"c00": {"type": "noul", "instructions": INSTRUCTION + "Width sets the size."},
                      "c01": {"type": "noul", "instructions": INSTRUCTION + "Array copies."}},
    }
    assert request.full_url == "https://generativelanguage.googleapis.com/v1beta/decisions"
    assert request.get_header("X-goog-api-key") == "가짜 키" and timeout == 5.0


def test_지시_문구와_머리글은_시험_글자_그대로다(monkeypatch):
    # 같은 상수끼리 견주면 문구가 바뀌어도 통과하므로, 시험 도구(rerank_trial.INSTRUCTION)의 글자를 그대로 적어 둔다
    assert INSTRUCTION == (
        "The input is a search query written by someone learning Blender 5.2. "
        "Does the following passage from the Blender 5.2 manual contain information that helps answer that query?\n\nPassage:\n"
    )
    sent = serve(monkeypatch, answers(0.5))
    DecisionReranker("k").judge("q", ["a"], timeout=5.0)
    request = sent[0][0]
    assert request.get_method() == "POST" and request.get_header("Content-type") == "application/json"


def test_질문_이름은_100개를_넘어도_시험과_같다(monkeypatch):
    sent = serve(monkeypatch, answers(*[0.5] * 120))
    DecisionReranker("k").judge("q", ["t"] * 120, timeout=5.0)
    names = list(json.loads(sent[0][0].data)["questions"])
    assert names[:2] == ["c00", "c01"] and names[100] == "c100" and len(names) == 120


def test_확률은_보낸_글_차례로_돌려주고_입력_토큰과_요금을_쌓는다(monkeypatch):
    serve(monkeypatch, answers(0.2, 0.7, 0.4))
    judge = DecisionReranker("k")
    assert judge.judge("q", ["a", "b", "c"], timeout=5.0) == [0.2, 0.7, 0.4]
    judge.judge("q", ["a", "b", "c"], timeout=5.0)
    assert judge.input_tokens == 2468 and judge.dollars() == round(2468 / 1e6 * 0.10, 6)


def test_답에_빠진_질문이_있으면_ValueError(monkeypatch):
    serve(monkeypatch, {"answers": {"c00": {"noul": 0.3}}, "usage": {"total_input_tokens": 10}})
    with pytest.raises(ValueError, match="c01"):
        DecisionReranker("k").judge("q", ["a", "b"], timeout=5.0)


@pytest.mark.parametrize("error", [urllib.error.URLError(socket.timeout("timed out")), TimeoutError("timed out")])
def test_연결이든_읽기든_시간_초과면_TimeoutError(monkeypatch, error):
    def slow(request, timeout, context=None):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(TimeoutError):
        DecisionReranker("k").judge("q", ["a"], timeout=0.1)


def test_확률이_큰_순이고_같으면_원래_순위를_지킨다():
    assert rerank([7, 3, 9, 1], [0.2, 0.9, 0.9, 0.5]) == [3, 9, 1, 7]
    assert rerank([7, 3, 9], [0.5, 0.5, 0.5]) == [7, 3, 9]


@pytest.mark.parametrize("answer", [
    {"answers": {"c00": {"noul": None}}, "usage": {"total_input_tokens": 10}},  # 확률 칸이 null
    {"answers": {"c00": None}, "usage": {"total_input_tokens": 10}},  # 글 칸이 null
    {"answers": None, "usage": {"total_input_tokens": 10}},  # answers가 null
    ["뜻밖의 목록"],  # 몸통이 객체가 아님
])
def test_서버가_이상한_꼴로_답하면_ValueError라_엔진이_뜻_검색으로_답한다(monkeypatch, answer):
    # 엔진은 바깥 실패(OSError·ValueError)만 잡으므로, 서버 답 꼴 문제가 TypeError·AttributeError로 새면 답 전체가 죽는다
    serve(monkeypatch, answer)
    with pytest.raises(ValueError):
        DecisionReranker("k").judge("q", ["a"], timeout=5.0)


def test_읽다가_연결이_끊기면_OSError(monkeypatch):
    import http.client  # IncompleteRead는 OSError 아래가 아니라 그대로 두면 엔진이 잡지 못한다

    class Broken(Reply):
        def read(self, *args):
            raise http.client.IncompleteRead(b"{")

    monkeypatch.setattr(urllib.request, "urlopen", lambda request, timeout, context=None: Broken(b""))
    with pytest.raises(OSError):
        DecisionReranker("k").judge("q", ["a"], timeout=5.0)


def test_usage만_없으면_확률은_쓰고_토큰은_세지_못한다(monkeypatch):
    # 확률이 멀쩡한데 요금 칸 하나 때문에 리랭킹을 버리지 않는다. 대신 요금이 덜 잡힌다
    serve(monkeypatch, {"usage": None, "answers": {"c00": {"noul": 0.3}}})
    judge = DecisionReranker("k")
    assert judge.judge("q", ["a"], timeout=5.0) == [0.3] and judge.input_tokens == 0


def test_인증서는_운영체제_저장소로_확인한다(monkeypatch):
    # Mac의 python.org 파이썬은 기본 인증서 묶음이 없어 urllib 기본값으로는 모든 리랭킹이 SSL 오류로 실패했다(11-24 실제 키 확인).
    # anthropic이 쓰는 httpcore2(_ssl.py)처럼 truststore로 운영체제 인증서를 쓴다
    import truststore

    serve(monkeypatch, answers(0.5))
    DecisionReranker("k").judge("q", ["a"], timeout=5.0)
    assert isinstance(serve.contexts[0], truststore.SSLContext)
