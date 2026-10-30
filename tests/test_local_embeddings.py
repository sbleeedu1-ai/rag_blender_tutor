"""모델을 받지 않고, 질문·문서 접두어와 로컬 파일만 읽는 연결을 확인한다."""

import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from blender_tutor import local_embeddings as local


@pytest.mark.parametrize("name,query,document", [
    ("granite-embedding-97m-multilingual-r2", "", ""),
    ("multilingual-e5-small", "query: ", "passage: "),
    ("embeddinggemma-300m", "task: search result | query: ", "title: none | text: "),
])
def test_encoder_uses_correct_prompt_for_questions_and_documents(tmp_path, monkeypatch, name, query, document):
    monkeypatch.setattr(local, "MODEL_ROOT", tmp_path)
    target = local.model_path(name)
    target.mkdir(parents=True)
    (target / "download.json").write_text(json.dumps({"내려받기 초": 1}), encoding="utf-8")
    calls, loaded = [], []

    class Model:
        max_seq_length = 512

        def __init__(self, path, **kwargs):
            loaded.append((path, kwargs))

        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return np.array([[1.0, 0.0] for _ in texts])

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=Model))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(float32="float32", get_num_threads=lambda: 4))
    embedder = local.LocalEmbedder(name)
    assert embedder.embed(["어떻게 해요?"], 1) == [[1.0, 0.0]]
    assert embedder.embed_documents(["Use the tool."], 1) == [[1.0, 0.0]]
    assert [kwargs["prompt"] for _, kwargs in calls] == [query, document]
    assert loaded[0][1] == {"device": "cpu", "local_files_only": True, "model_kwargs": {"dtype": "float32"}}
    assert embedder.cache_identity["revision"] == local.MODELS[name]["revision"]
    assert "합계 초" in embedder.metadata and "최대 입력 토큰" in embedder.metadata


def test_missing_download_stops_before_model_import(tmp_path, monkeypatch):
    monkeypatch.setattr(local, "MODEL_ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="prepare"):
        local.LocalEmbedder("multilingual-e5-small")
