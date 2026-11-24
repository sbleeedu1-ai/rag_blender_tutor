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
    sent = []

    def fake(request, timeout):
        sent.append((request, timeout))
        return Reply(json.dumps(answer).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
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
    def slow(request, timeout):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(TimeoutError):
        DecisionReranker("k").judge("q", ["a"], timeout=0.1)


def test_확률이_큰_순이고_같으면_원래_순위를_지킨다():
    assert rerank([7, 3, 9, 1], [0.2, 0.9, 0.9, 0.5]) == [3, 9, 1, 7]
    assert rerank([7, 3, 9], [0.5, 0.5, 0.5]) == [7, 3, 9]
