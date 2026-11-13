"""애드온 설치 명령(개발용, 사용자 결정 2026-10-22).

애드온을 Blender 5.2 사용자 애드온 폴더에 복사하고, 애드온이 도우미 프로그램을 켤 방법(이 프로젝트 .venv 파이썬)과
비밀 글자를 그 옆 config.json에 적는다. 프로젝트 폴더를 옮기면 다시 실행한다.
실제 배포 때는 도우미 프로그램을 .exe로 묶어 애드온 안에 넣고, config.json 대신 '내 옆의 .exe'를 켜게 바꾼다.

실행: .venv\\Scripts\\python -m blender_tutor.install_addon (Mac: .venv/bin/python -m blender_tutor.install_addon)
"""

import argparse
import json
import os
import plistlib
import secrets
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from blender_tutor.paths import PROJECT
from blender_tutor.receiver import PORT

ADDON_NAME = "blender_tutor_addon"
SOURCE = PROJECT / "addon" / ADDON_NAME


def default_addons_dir(platform: str = sys.platform, environ: Mapping[str, str] = os.environ, home: Path = Path.home()) -> Path:
    """Blender 5.2가 사용자 애드온을 찾는 폴더(Windows: APPDATA/Blender Foundation/Blender, Mac: Application Support/Blender)."""
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Blender" / "5.2" / "scripts" / "addons"
    return Path(environ["APPDATA"]) / "Blender Foundation" / "Blender" / "5.2" / "scripts" / "addons"


MAC_APP = "BlenderTutorHelper.app"  # Mac: 도우미를 감싼 앱 묶음(애드온 폴더 안)


def install(addons_dir: Path, python: Path, platform: str = sys.platform, sign: bool = True) -> Path:
    """애드온을 addons_dir에 복사(덮어쓰기)하고 config.json을 적는다. 설치한 폴더를 돌려준다.

    다시 설치해도 비밀 글자는 그대로 둔다. 이미 켜진 도우미 프로그램이 지난 비밀 글자로 받고 있을 수 있어서다.
    Mac은 도우미를 자기 이름의 앱 묶음으로 감싸 open으로 켠다(mac_app, sign은 앱 묶음에 서명할지: 시험은 끈다).
    """
    target = addons_dir / ADDON_NAME
    config_path = target / "config.json"
    token = json.loads(config_path.read_text(encoding="utf-8"))["token"] if config_path.exists() else secrets.token_hex(32)
    shutil.copytree(SOURCE, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "config.json", MAC_APP))
    command = [str(python), "-m", "blender_tutor.helper"]
    if platform == "darwin":
        app, packages = mac_app(target / MAC_APP, python, sign)
        # 앱의 실행 파일은 맨 파이썬이라 가상 환경 꾸러미(.pth까지)를 덧붙이고 도우미를 __main__으로 돌린다
        start = (f"import site, sys, runpy; site.addsitedir({str(packages)!r}); sys.path.insert(0, {str(PROJECT)!r}); "
                 "sys.argv = ['blender_tutor.helper', *sys.argv[1:]]; runpy.run_module('blender_tutor.helper', run_name='__main__')")
        command = ["open", "-n", "-g", "-a", str(app), "--args", "-c", start, "--token-file", str(config_path)]
    config = {
        "command": command,
        "cwd": str(PROJECT),
        "port": PORT,
        "token": token,
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def mac_app(app: Path, python: Path, sign: bool) -> tuple[Path, Path]:
    """Mac: 도우미를 켜는 작은 앱 묶음을 새로 만든다. (앱, 가상 환경 꾸러미 폴더)를 돌려준다.

    Blender가 도우미를 직접 켜면 Mac은 Blender를 책임자로 보아 입력 모니터링 권한이 'Blender' 전체에 잡혔고, 앱 묶음의
    셸 스크립트로 파이썬을 켜면 'python3.13' 실행 파일에 잡혔다(그 파이썬으로 도는 모든 스크립트, HISTORY [313]).
    그래서 실행 파일 자리에 파이썬 복사본을 두고 서명해, Mac이 이 앱('Blender 첫걸음 도우미')을 주인으로 보게 한다.
    파이썬은 자기 표준 라이브러리를 실행 파일 자리로 찾으므로 원래 자리(PYTHONHOME)를 알려 준다.
    LSUIElement: Dock·Cmd+Tab에 나오지 않는다(메뉴 막대 아이콘만).
    """
    real = Path(os.path.realpath(python))  # 가상 환경 python → Blender에 딸린 python3.13
    packages = python.parent.parent / "lib" / real.name / "site-packages"
    shutil.rmtree(app, ignore_errors=True)  # 지난 판의 실행 파일·서명이 섞이지 않게
    executable = app / "Contents" / "MacOS" / "helper"
    executable.parent.mkdir(parents=True)
    shutil.copy2(real, executable)
    info = {
        "CFBundleIdentifier": "local.rag-blender-tutor.helper",
        "CFBundleName": "Blender Tutor Helper",
        "CFBundleDisplayName": "Blender 첫걸음 도우미",
        "CFBundleExecutable": executable.name,
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "0.1.0",
        "LSUIElement": True,
        "LSEnvironment": {"PYTHONHOME": str(real.parent.parent)},
    }
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    if sign:  # 인증서 없는 이 PC용 서명. 앱 이름·식별자로 권한을 묻게 한다
        subprocess.run(["codesign", "--force", "--sign", "-", str(app)], check=True, capture_output=True)
    return app, packages


def main() -> int:
    parser = argparse.ArgumentParser(description="Blender 5.2에 도우미 애드온을 설치합니다.")
    parser.add_argument("--addons-dir", type=Path, default=None, help="애드온 폴더(기본: Blender 5.2 사용자 애드온 폴더)")
    args = parser.parse_args()
    # Windows는 검은 명령 창이 뜨지 않게 pythonw를 쓴다(.venv\Scripts에 python과 함께 있음). Mac에는 없어 python 그대로
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = install(args.addons_dir or default_addons_dir(), pythonw if pythonw.exists() else Path(sys.executable))
    print(f"설치했습니다: {target}")
    print("Blender 5.2를 켜고 편집 > 환경 설정 > 애드온에서 'Blender 첫걸음 도우미'를 켜 주세요(처음 한 번만).")
    if sys.platform == "darwin":
        print("도우미 아이콘(파란 동그라미)은 화면 맨 위 메뉴 막대 오른쪽에 보여요.")
        print("처음 F10 때 '입력 모니터링' 허락을 물으면 'Blender 첫걸음 도우미'를 켜 주세요(시스템 설정 > 개인정보 보호 및 보안).")
        print("켠 뒤 Blender를 다시 켜야 적용돼요. 켜지 않아도 쓸 수 있고, Blender를 누를 때 도우미 창이 잠깐 깜빡이는 것만 남아요.")
    else:  # Windows 11은 새 트레이 아이콘을 숨김 영역(^)에 넣는다(조사 문서)
        print("도우미 아이콘(파란 동그라미)은 작업 표시줄 오른쪽 ^를 누르면 보여요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
