# 시제품(버릴 코드): 가짜 서버를 켜고 Blender 5.2를 시제품 애드온과 함께 연다. 명령 하나로 끝.
#   python prototype/addon_roundtrip/run.py            (답 지연 2초)
#   python prototype/addon_roundtrip/run.py --delay 5  (멈춤 확인용으로 길게)
# Blender 위치가 다르면 환경 변수 BLENDER에 blender.exe 경로를 넣는다.
import argparse
import os
import subprocess
import threading
from pathlib import Path

from fake_server import serve

HERE = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")

p = argparse.ArgumentParser()
p.add_argument("--delay", type=float, default=2.0)
args = p.parse_args()

server = serve(delay=args.delay)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"[시제품] Blender 실행: {BLENDER}", flush=True)
subprocess.run([BLENDER, "--python", str(HERE / "tutor_proto_addon.py")])
server.shutdown()
