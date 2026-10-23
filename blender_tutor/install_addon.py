"""애드온 설치 명령(개발용, 사용자 결정 2026-10-22).

애드온을 Blender 5.2 사용자 애드온 폴더에 복사하고, 애드온이 도우미 프로그램을 켤 방법(이 프로젝트 .venv 파이썬)과
비밀 글자를 그 옆 config.json에 적는다. 프로젝트 폴더를 옮기면 다시 실행한다.
실제 배포 때는 도우미 프로그램을 .exe로 묶어 애드온 안에 넣고, config.json 대신 '내 옆의 .exe'를 켜게 바꾼다.

실행: .venv\\Scripts\\python -m blender_tutor.install_addon
"""

import argparse
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

from blender_tutor.paths import PROJECT
from blender_tutor.receiver import PORT

ADDON_NAME = "blender_tutor_addon"
SOURCE = PROJECT / "addon" / ADDON_NAME


def default_addons_dir() -> Path:
    """Blender 5.2가 사용자 애드온을 찾는 폴더(Windows)."""
    return Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender" / "5.2" / "scripts" / "addons"


def install(addons_dir: Path, python: Path) -> Path:
    """애드온을 addons_dir에 복사(덮어쓰기)하고 config.json을 적는다. 설치한 폴더를 돌려준다.

    다시 설치해도 비밀 글자는 그대로 둔다. 이미 켜진 도우미 프로그램이 지난 비밀 글자로 받고 있을 수 있어서다.
    """
    target = addons_dir / ADDON_NAME
    config_path = target / "config.json"
    token = json.loads(config_path.read_text(encoding="utf-8"))["token"] if config_path.exists() else secrets.token_hex(32)
    shutil.copytree(SOURCE, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "config.json"))
    config = {
        "command": [str(python), "-m", "blender_tutor.helper"],
        "cwd": str(PROJECT),
        "port": PORT,
        "token": token,
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Blender 5.2에 도우미 애드온을 설치합니다.")
    parser.add_argument("--addons-dir", type=Path, default=None, help="애드온 폴더(기본: Blender 5.2 사용자 애드온 폴더)")
    args = parser.parse_args()
    # 검은 명령 창이 뜨지 않게 pythonw를 쓴다(.venv\Scripts에 python과 함께 있음)
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = install(args.addons_dir or default_addons_dir(), pythonw if pythonw.exists() else Path(sys.executable))
    print(f"설치했습니다: {target}")
    print("Blender 5.2를 켜고 편집 > 환경 설정 > 애드온에서 'Blender 첫걸음 도우미'를 켜 주세요(처음 한 번만).")
    # Windows 11은 새 트레이 아이콘을 숨김 영역(^)에 넣는다(조사 문서)
    print("도우미 아이콘(파란 동그라미)은 작업 표시줄 오른쪽 ^를 누르면 보여요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
