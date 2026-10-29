"""설명서 검색용 벡터(티켓 31): 만들기·읽기·바뀐 청크 알아채기·유료 확인·시간 초과.

임베딩은 글 길이로 벡터를 만드는 가짜를 쓴다(API 키·유료 호출 없음). 청크는 지어낸 것이다(설명서 원문 아님).
"""

import socket
import urllib.error
import urllib.request

import numpy as np
import pytest

from blender_tutor.manual_chunks import Chunk, save_chunks
from blender_tutor.manual_vectors import OpenAIEmbedder, build, cached, load, main, path_for

BEVEL = Chunk("modeling/bevel", "options", "modeling", "modeling", "Bevel", ("Options",), "Width sets the size.")
ARRAY = Chunk("modeling/array", "intro", "modeling", "modeling", "Array", ("Introduction",), "Array copies the object.")
ARRAY_MORE = Chunk("modeling/array", "intro", "modeling", "modeling", "Array", ("Introduction",), "Count sets copies.")


class LengthEmbedder:
    """글마다 [글 길이, 1]을 돌려준다. 부를 때마다 받은 글 수를 적는다."""

    def __init__(self):
        self.calls: list[int] = []

    def embed(self, texts, timeout):
        self.calls.append(len(texts))
        return [[float(len(text)), 1.0] for text in texts]


def test_만든_벡터를_청크_차례대로_읽는다(tmp_path):
    chunks = [BEVEL, ARRAY, ARRAY_MORE]
    embedder = LengthEmbedder()
    path = tmp_path / "vectors" / "manual.npz"
    record = build(chunks, embedder, path, "fake", batch=2)
    assert embedder.calls == [2, 1]  # batch개씩 나눠 보낸다
    assert record["청크 수"] == 3 and path.with_suffix(".json").exists()
    vectors = load(path, chunks)
    assert vectors.dtype == np.float32
    assert vectors[:, 0].tolist() == [float(len(chunk.text)) for chunk in chunks]


def test_청크_글이나_차례가_바뀌면_읽지_않고_멈춘다(tmp_path):
    path = tmp_path / "manual.npz"
    build([BEVEL, ARRAY], LengthEmbedder(), path, "fake")
    with pytest.raises(ValueError, match="다시 만드세요"):
        load(path, [ARRAY, BEVEL])  # 차례가 바뀜
    edited = Chunk(*[getattr(BEVEL, name) for name in ("page_path", "anchor", "field", "group", "page_title", "headings")], "Width changed.")
    with pytest.raises(ValueError, match="다시 만드세요"):
        load(path, [edited, ARRAY])  # 같은 자리의 글이 바뀜
    with pytest.raises(ValueError, match="다시 만드세요"):
        load(path, [BEVEL, ARRAY, ARRAY_MORE])  # 청크가 늘어남


def test_벡터_파일이_있으면_덮어쓰지_않는다(tmp_path):
    path = tmp_path / "manual.npz"
    build([BEVEL], LengthEmbedder(), path, "fake")
    with pytest.raises(FileExistsError):
        build([BEVEL], LengthEmbedder(), path, "fake")


def test_build는_yes_없이_돈을_쓰지_않고_멈춘다(tmp_path, capsys):
    save_chunks([BEVEL, ARRAY], tmp_path / "chunks" / "manual_chunks.jsonl")
    assert main(["build", "--data", str(tmp_path)]) == 2
    assert not path_for("text-embedding-3-large", tmp_path).exists()
    assert "약 $" in capsys.readouterr().out  # 어림 비용은 먼저 보인다


@pytest.mark.parametrize("error", [urllib.error.URLError(socket.timeout("timed out")), TimeoutError("timed out")])
def test_OpenAI_임베딩은_연결이든_읽기든_시간_초과면_TimeoutError(monkeypatch, error):
    def slow(request, timeout):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", slow)
    with pytest.raises(TimeoutError):
        OpenAIEmbedder("text-embedding-3-large", "가짜 키").embed(["베벨"], timeout=0.1)


def test_연습_과정_벡터는_저장해_두고_새로_생기거나_바뀐_글만_임베딩한다(tmp_path):
    path = tmp_path / "vectors" / "courses.npz"
    embedder = LengthEmbedder()
    first = cached(["검", "방패"], embedder, path, timeout=1)
    assert embedder.calls == [2] and [vector[0] for vector in first] == [1.0, 2.0]
    cached(["검", "방패"], embedder, path, timeout=1)
    assert embedder.calls == [2]  # 그대로면 부르지 않는다
    again = cached(["검", "둥근 방패"], embedder, path, timeout=1)
    assert embedder.calls == [2, 1] and again[1][0] == 5.0  # 바뀐 글 하나만 부른다
    cached(["검"], embedder, path, timeout=1)
    assert np.load(path)["digests"].shape == (1,)  # 없어진 연습 과정의 벡터는 지운다


def test_연습_과정이_없으면_부르지_않는다(tmp_path):
    embedder = LengthEmbedder()
    assert cached([], embedder, tmp_path / "courses.npz", timeout=1) == [] and embedder.calls == []
