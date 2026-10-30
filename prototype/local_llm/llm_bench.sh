#!/usr/bin/env bash
# 로컬 생성 모델 속도 1-2단계: llama.cpp와 GGUF 모델을 받고 llama-bench로 잰다(HISTORY [122], 티켓 42).
# 강의실 PC(CPU)에서 쓴 그대로다. GPU PC에서는 ASSET을 CUDA판으로, 모델 목록을 큰 모델로 바꾼다.
set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
ROOT=data/models/llm
TAG=b11998
ASSET=${ASSET:-win-cpu-x64}  # GPU PC는 win-cuda-… 배포 파일 이름으로
mkdir -p "$ROOT"
OUT="results/$(date +%Y%m%d)/$(date +%H%M%S)_llm_bench"
mkdir -p "$OUT"
cp "$0" "$OUT/llm_bench.sh"

if [ ! -x "$ROOT/llama-$TAG/llama-bench.exe" ]; then
  curl -sSL -o "$ROOT/llama-$TAG.zip" "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/llama-$TAG-bin-$ASSET.zip"
  mkdir -p "$ROOT/llama-$TAG"
  unzip -q -o "$ROOT/llama-$TAG.zip" -d "$ROOT/llama-$TAG"
fi
BENCH=$(find "$ROOT/llama-$TAG" -name llama-bench.exe | head -1)
echo "llama.cpp $TAG: $BENCH" | tee "$OUT/log.txt"

.venv/Scripts/python - "$ROOT" <<'EOF' | tee -a "$OUT/log.txt"
import sys, time
from huggingface_hub import hf_hub_download
root = sys.argv[1]
for repo, rev, name in [
    ("ggml-org/Qwen3.5-0.8B-GGUF", "807dfd9a6f", "Qwen3.5-0.8B-Q4_0.gguf"),
    ("bartowski/Qwen_Qwen3.5-2B-GGUF", "7d26695454", "Qwen_Qwen3.5-2B-Q4_0.gguf"),
    ("google/gemma-4-E2B-it-qat-q4_0-gguf", "675cff42a7", "gemma-4-E2B_q4_0-it.gguf"),
]:
    start = time.perf_counter()
    path = hf_hub_download(repo, name, revision=rev, local_dir=f"{root}/{repo.replace('/', '__')}")
    print(f"받음 {repo}@{rev} {name} {time.perf_counter() - start:.0f}초 -> {path}", flush=True)
EOF

for model in $(find "$ROOT" -name "*.gguf" ! -name "*mmproj*" | sort); do
  base=$(basename "$model" .gguf)
  for threads in 4 8; do
    echo "잼 $base 스레드 $threads $(date +%H:%M:%S)" | tee -a "$OUT/log.txt"
    "$BENCH" -m "$model" -t "$threads" -p 64,512 -n 32 -r 5 -o json > "$OUT/${base}_t${threads}.json" 2>> "$OUT/stderr.txt" \
      || echo "실패 $base 스레드 $threads" | tee -a "$OUT/log.txt"
  done
done
echo "끝 $(date +%H:%M:%S) -> $OUT" | tee -a "$OUT/log.txt"
