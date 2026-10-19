# 시제품(버릴 코드): 고정된 답만 돌려주는 가짜 서버. 검색·답 생성은 하지 않는다.
# 받은 질문과 작업 상태를 그대로 화면에 찍어 무엇이 왔는지 보여 준다.
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DELAY = 2.0


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        t0 = time.perf_counter()
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        print("[가짜 서버] 받음:\n" + json.dumps(body, ensure_ascii=False, indent=2), flush=True)
        time.sleep(DELAY)  # 실제 서버가 답을 만드는 시간을 흉내
        state = body.get("state", {})
        answer = {
            "answer": (
                f"(가짜 답) 지금 {state.get('mode')} 모드이고 선택한 물체는 "
                f"{', '.join(state.get('selected_objects') or []) or '없음'}입니다. "
                f"화면 언어는 {state.get('locale')}입니다."
            ),
            "sources": [{"title": "Blender 5.2 설명서: 3D 뷰포트", "url": "https://docs.blender.org/manual/en/5.2/editors/3dview/index.html"}],
            "server_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
        data = json.dumps(answer, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def serve(port=8765, delay=2.0):
    global DELAY
    DELAY = delay
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"[가짜 서버] http://127.0.0.1:{port}/ask  (답 지연 {delay}초)", flush=True)
    return server


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--delay", type=float, default=2.0)
    serve(delay=p.parse_args().delay).serve_forever()
