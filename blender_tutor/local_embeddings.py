"""가벼운 로컬 임베딩 비교: 내려받기와 실제 불러오기를 나눠 시간을 잰다.

모델은 data/models/ 아래에만 둔다. prepare는 파일만 내려받으며 모델을 불러오지 않는다.
검색 비교는 준비된 파일만 읽으므로, 모델 불러오기 시간에 네트워크 시간이 섞이지 않는다.
"""

import argparse
import json
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from blender_tutor.paths import PROJECT


MODELS = {
    "granite-embedding-97m-multilingual-r2": {
        "repo": "ibm-granite/granite-embedding-97m-multilingual-r2",
        "revision": "835ad14087e140460703cf0fae09f97d469d65c2",
        "query": "", "document": "",
    },
    "multilingual-e5-small": {
        "repo": "intfloat/multilingual-e5-small",
        "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
        "query": "query: ", "document": "passage: ",
    },
    "embeddinggemma-300m": {
        "repo": "google/embeddinggemma-300m",
        "revision": "57c266a740f537b4dc058e1b0cda161fd15afa75",
        "query": "task: search result | query: ", "document": "title: none | text: ",
    },
}
MODEL_ROOT = PROJECT / "data" / "models"


def model_path(name: str) -> Path:
    return MODEL_ROOT / name / MODELS[name]["revision"]


def prepare(name: str) -> dict:
    """고정한 버전의 모델에서 필요한 형식 하나와 설정만 내려받는다. 이미 받은 파일은 재사용한다."""
    from huggingface_hub import snapshot_download

    config = MODELS[name]
    target = model_path(name)
    start = time.perf_counter()
    snapshot_download(
        config["repo"], revision=config["revision"], local_dir=target,
        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "README.md", "LICENSE*", "NOTICE*"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )
    record_path = target / "download.json"
    if record_path.exists():
        return json.loads(record_path.read_text(encoding="utf-8"))
    record = {
        **config, "내려받은 시각": datetime.now().isoformat(timespec="seconds"),
        "내려받기 초": time.perf_counter() - start,
        "파일 바이트": sum(path.stat().st_size for path in target.rglob("*") if path.is_file() and ".cache" not in path.parts),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


class LocalEmbedder:
    """CPU·원래 정밀도(float32)로 비교한다. 질문과 문서의 접두어를 구분한다."""

    def __init__(self, name: str):
        config = MODELS[name]
        target = model_path(name)
        if not (target / "download.json").exists():
            raise FileNotFoundError(f"모델을 먼저 준비해 주세요: python -m blender_tutor.local_embeddings prepare --model {name}")
        start = time.perf_counter()
        from sentence_transformers import SentenceTransformer
        import torch

        imported = time.perf_counter()
        self._model = SentenceTransformer(
            str(target), device="cpu", local_files_only=True,
            model_kwargs={"dtype": torch.float32},
        )
        loaded = time.perf_counter()
        self.load_seconds = loaded - start
        self.metadata = {
            **config, "실행 방식": "PyTorch CPU float32", "배치 크기": 8,
            "최대 입력 토큰": self._model.max_seq_length, "CPU 스레드": torch.get_num_threads(),
            "라이브러리 불러오기 초": imported - start, "모델 파일 읽기 초": loaded - imported,
            "합계 초": self.load_seconds,
            "다운로드": json.loads((target / "download.json").read_text(encoding="utf-8")),
        }
        # 불러오기 시간 같은 실행마다 다른 값은 DB 열쇠에 넣지 않는다.
        self.cache_identity = {**config, "실행 방식": "PyTorch CPU float32"}
        self._query_prefix, self._document_prefix = config["query"], config["document"]

    def _encode(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        return self._model.encode(
            list(texts), prompt=prefix, batch_size=8, normalize_embeddings=True, show_progress_bar=False,
        ).tolist()

    def embed(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        """질문 임베딩. 로컬 계산이라 외부 서비스용 timeout은 쓰지 않는다."""
        return self._encode(texts, self._query_prefix)

    def embed_documents(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        return self._encode(texts, self._document_prefix)


def main() -> None:
    parser = argparse.ArgumentParser(description="비교용 로컬 모델의 파일만 내려받습니다(유료 호출 없음).")
    parser.add_argument("command", choices=["prepare"])
    parser.add_argument("--model", choices=list(MODELS), required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.model), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
