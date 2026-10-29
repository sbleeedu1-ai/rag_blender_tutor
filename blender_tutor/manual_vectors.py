"""설명서 검색용 벡터(티켓 31): 청크 영어 원문을 OpenAI 임베딩으로 한 번 바꿔 numpy 파일 하나에 저장하고, 도우미가 읽는다.

저장 방식(HISTORY [106]): `data/vectors/manual_<모델>.npz`에 vectors(청크 차례, 3,072차원 float32)·keys(청크 열쇠)·digests(청크 글의 해시).
같은 이름의 .json에 만든 모델·시각·실제 토큰·비용을 남긴다. 읽을 때 지금 청크 파일과 열쇠·글이 하나라도 다르면 멈춘다(옛 벡터로 검색하지 않게).

- estimate: 어림 토큰·비용을 보인다(돈 들지 않음).
- build: 벡터 파일을 만든다. 돈이 들어 --yes가 있어야 하고, 파일이 이미 있으면 멈춘다(덮어쓰지 않음).
예: python -m blender_tutor.manual_vectors build --yes
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import numpy as np

from blender_tutor.answer_engine import Embedder
from blender_tutor.beginner_scope import openai_key
from blender_tutor.manual_chunks import Chunk, load_chunks
from blender_tutor.paths import PROJECT
from blender_tutor.translate import _tokens, pieces

MODEL = "text-embedding-3-large"  # 티켓 40 결과로 고른 모델(HISTORY [102])
# 유료 모델의 요금(달러 / 100만 토큰, OpenAI 요금표 기준)
PRICE_PER_MILLION = {"text-embedding-3-large": 0.13}
BATCH = 128  # 한 번에 보내는 청크 수(가장 긴 청크 약 700토큰 × 128 < 한 요청 한도 30만 토큰)
BUILD_TIMEOUT = 60.0  # 만들 때 요청 하나의 응답 없음 한도(초)

DATA = PROJECT / "data"


class OpenAIEmbedder:
    """OpenAI 임베딩(돈이 든다). 받은 토큰·요청 수를 쌓아 둔다. 한도 안에 응답이 없으면 TimeoutError(답 엔진이 '너무 늦어져' 문구를 낸다)."""

    URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, model: str, key: str):
        self.model, self.key = model, key
        self.tokens = self.requests = 0

    def embed(self, texts: Sequence[str], timeout: float) -> list[list[float]]:
        body = {"model": self.model, "input": list(texts)}
        request = urllib.request.Request(
            self.URL, json.dumps(body).encode("utf-8"),
            {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                answer = json.loads(response.read())
        except urllib.error.URLError as error:  # 연결 단계의 시간 초과는 URLError에 싸여 온다. 읽기 단계는 TimeoutError 그대로
            if isinstance(error.reason, TimeoutError):
                raise TimeoutError(f"임베딩 응답이 {timeout}초 안에 오지 않음") from error
            raise
        self.requests += 1
        self.tokens += answer["usage"]["prompt_tokens"]
        return [row["embedding"] for row in sorted(answer["data"], key=lambda row: row["index"])]

    def dollars(self) -> float:
        return round(self.tokens / 1_000_000 * PRICE_PER_MILLION[self.model], 6)


def path_for(model: str, data_dir: Path = DATA) -> Path:
    return data_dir / "vectors" / f"manual_{model}.npz"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def estimate(chunks: Sequence[Chunk], model: str = MODEL) -> str:
    tokens = sum(_tokens(chunk.text) for chunk in chunks)
    dollars = tokens / 1_000_000 * PRICE_PER_MILLION[model]
    return f"{model}: 청크 {len(chunks):,}개, 약 {tokens:,}토큰 → 약 ${dollars:.4f} (요금 ${PRICE_PER_MILLION[model]}/100만 토큰)"


def build(chunks: Sequence[Chunk], embedder: Embedder, path: Path, model: str, batch: int = BATCH) -> dict:
    """청크 글을 batch개씩 임베딩해 path(.npz)와 같은 이름의 .json에 쓰고, 그 기록(.json 내용)을 돌려준다. path가 있으면 멈춘다."""
    if path.exists():
        raise FileExistsError(f"{path}가 이미 있어 멈춥니다(덮어쓰지 않음). 옛 파일을 archive/로 옮긴 뒤 다시 만드세요.")
    start = time.perf_counter()
    vectors: list[Sequence[float]] = []
    for begin in range(0, len(chunks), batch):
        vectors += embedder.embed([chunk.text for chunk in chunks[begin : begin + batch]], BUILD_TIMEOUT)
    if len(vectors) != len(chunks):
        raise ValueError(f"청크 {len(chunks)}개에 벡터 {len(vectors)}개")
    keys = [piece.key for piece in pieces(chunks)]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path, vectors=np.asarray(vectors, dtype=np.float32), keys=np.array(keys),
        digests=np.array([_digest(chunk.text) for chunk in chunks]),
    )
    record = {
        "모델": model, "청크 수": len(chunks), "만든 시각": datetime.now().isoformat(timespec="seconds"),
        "걸린 초": round(time.perf_counter() - start, 1),
    }
    if isinstance(embedder, OpenAIEmbedder):
        record |= {"토큰": embedder.tokens, "요청": embedder.requests, "달러": embedder.dollars()}
    path.with_suffix(".json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load(path: Path, chunks: Sequence[Chunk]) -> np.ndarray:
    """벡터 파일을 읽는다. 지금 청크와 열쇠·글이 다르면(청크 파일을 다시 만든 뒤 벡터를 안 만든 때) ValueError."""
    stored = np.load(path)
    keys = [piece.key for piece in pieces(chunks)]
    digests = [_digest(chunk.text) for chunk in chunks]
    if stored["keys"].tolist() != keys or stored["digests"].tolist() != digests:
        changed = sum(a != b for a, b in zip(stored["digests"].tolist(), digests)) + abs(len(stored["keys"]) - len(keys))
        raise ValueError(f"{path}: 지금 청크 파일과 다릅니다(청크 {len(keys)}개 중 약 {changed}개). 벡터 파일을 다시 만드세요.")
    return stored["vectors"]


def main(argv: Sequence[str] | None = None) -> int:
    """명령 줄 입구. 돌려주는 값은 종료 코드(0 성공, 2 --yes 없음)."""
    parser = argparse.ArgumentParser(description="설명서 청크의 검색용 벡터를 만듭니다(티켓 31).")
    parser.add_argument("command", choices=("estimate", "build"))
    parser.add_argument("--data", type=Path, default=DATA, help="data 폴더")
    parser.add_argument("--yes", action="store_true", help="어림 비용을 보고 확인받았다(build에 필요)")
    args = parser.parse_args(argv)

    chunks = load_chunks(args.data / "chunks" / "manual_chunks.jsonl")
    cost = estimate(chunks)
    print(cost)
    if args.command == "estimate":
        return 0
    if not args.yes:
        print("돈이 드는 실행이라 멈춥니다. 비용을 확인받은 뒤 --yes를 붙여 주세요.", file=sys.stderr)
        return 2
    record = build(chunks, OpenAIEmbedder(MODEL, openai_key()), path_for(MODEL, args.data), MODEL)
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
