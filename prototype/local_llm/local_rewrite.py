"""로컬 생성 모델 초벌 시험: luna와 같은 바꾸기 지시로 W1·W2·W10을 바꾸고 시간을 잰다(무료, llama-server). HISTORY [122], 티켓 42."""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from blender_tutor.search_compare import REWRITE_PROMPT, area_of  # noqa: E402

LLM = ROOT / "data" / "models" / "llm"
SERVER = LLM / "llama-b11998" / "llama-server.exe"
MODELS = [
    ("Qwen3.5-0.8B", LLM / "ggml-org__Qwen3.5-0.8B-GGUF" / "Qwen3.5-0.8B-Q4_0.gguf"),
    ("Qwen3.5-2B", LLM / "bartowski__Qwen_Qwen3.5-2B-GGUF" / "Qwen_Qwen3.5-2B-Q4_0.gguf"),
    ("Gemma-4-E2B", LLM / "google__gemma-4-E2B-it-qat-q4_0-gguf" / "gemma-4-E2B_q4_0-it.gguf"),
]
QUESTIONS = ["W1", "W2", "W10"]
PORT = 8090

keys = [json.loads(line)["key"] for line in (ROOT / "data/search_compare/pool/pool_full.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
areas = sorted({area_of(key.split(".html")[0]) for key in keys})
prompt = REWRITE_PROMPT.format(areas="\n".join(areas))
questions = {}
for line in (ROOT / "data/search_compare/questions/web_questions.jsonl").read_text(encoding="utf-8").splitlines():
    row = json.loads(line)
    if row["id"] in QUESTIONS:
        questions[row["id"]] = row["question"]

now = datetime.now()
out = ROOT / "results" / f"{now:%Y%m%d}" / f"{now:%H%M%S}_local_rewrite_trial"
out.mkdir(parents=True)


def ask(question):
    body = json.dumps({
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": question}],
        "temperature": 0.2, "max_tokens": 200, "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False}, "cache_prompt": True,
    }).encode("utf-8")
    request = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", body, {"Content-Type": "application/json"})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        got = json.loads(response.read())
    return time.perf_counter() - start, got


LOAD_LIMIT = 120  # 초. 큰 모델도 이 안에 뜬다고 본다(강의실 PC E2B 3.1초)


def wait_ready(server: subprocess.Popen, log: Path) -> None:
    """서버가 /health에 답할 때까지 기다린다. 서버가 먼저 끝나거나 한도를 넘으면 로그 위치와 함께 멈춘다."""
    deadline = time.perf_counter() + LOAD_LIMIT
    while time.perf_counter() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"llama-server가 뜨지 못하고 끝났습니다(코드 {server.returncode}). {log}를 보세요.")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            return
        except OSError:  # 아직 모델을 읽는 중이면 연결이 거절되거나 503이 온다
            time.sleep(0.5)
    raise TimeoutError(f"llama-server가 {LOAD_LIMIT}초 안에 뜨지 않았습니다. {log}를 보세요.")


rows = []
for name, path in MODELS:
    if not path.exists():
        raise FileNotFoundError(f"모델 파일이 없습니다: {path} (llm_bench.sh로 먼저 받으세요)")
    load_start = time.perf_counter()
    log = out / f"{name}_server.log"
    with log.open("w", encoding="utf-8") as log_file:
        server = subprocess.Popen([str(SERVER), "-m", str(path), "-t", "4", "-c", "4096", "--port", str(PORT)],
                                  stdout=subprocess.DEVNULL, stderr=log_file)
    try:
        wait_ready(server, log)
        loaded = time.perf_counter() - load_start
        for order, qid in enumerate(QUESTIONS, start=1):
            seconds, got = ask(questions[qid])
            text = got["choices"][0]["message"]["content"]
            usage, timings = got.get("usage", {}), got.get("timings", {})
            row = {"모델": name, "질문": qid, "차례": order, "초": round(seconds, 2), "답": text,
                   "입력 토큰": usage.get("prompt_tokens"), "출력 토큰": usage.get("completion_tokens"),
                   "캐시된 입력": timings.get("cache_n"), "불러오기 초": round(loaded, 1)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        server.terminate()
        server.wait()

(out / "답.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
(out / "설정.json").write_text(json.dumps({
    "목적": "로컬 소형 모델이 luna 대신 질문 바꾸기를 할 수 있나 초벌 확인(W1·W2·W10, 1회)",
    "지시": prompt, "llama.cpp": "b11998 win-cpu-x64", "스레드": 4, "온도": 0.2, "생각": "끔",
    "모델": {name: str(path) for name, path in MODELS}, "시작 시각": now.isoformat(timespec="seconds"),
    "메모": "Claude 실행. 지시문 캐시: 같은 서버에서 첫 질문은 지시문을 새로 읽고 2·3번째는 캐시 재사용.",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"결과: {out}")
