# 시제품(버릴 코드) 실행: python prototype/helper_window_ui/run.py [widgets|qml|both]
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
APPS = {"widgets": "widgets_app.py", "qml": "qml_app.py"}

which = sys.argv[1] if len(sys.argv) > 1 else "both"
names = list(APPS) if which == "both" else [which]
procs = [subprocess.Popen([sys.executable, str(HERE / APPS[n]), str(i)]) for i, n in enumerate(names)]
for p in procs:
    p.wait()
