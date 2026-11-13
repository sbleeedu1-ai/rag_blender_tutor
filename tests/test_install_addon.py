"""설치 명령: 임시 폴더를 Blender 애드온 폴더로 삼아 설치해 본다."""

import json
from pathlib import Path

from blender_tutor.install_addon import ADDON_NAME, SOURCE, default_addons_dir, install
from blender_tutor.receiver import PORT

PROJECT = Path(__file__).resolve().parent.parent
PYTHON = Path("C:/project/.venv/Scripts/pythonw.exe")


def config_of(addons_dir: Path) -> dict:
    return json.loads((addons_dir / ADDON_NAME / "config.json").read_text(encoding="utf-8"))


def test_애드온을_복사하고_도우미_프로그램_켜는_법을_적는다(tmp_path):
    install(tmp_path, PYTHON, platform="win32")
    assert (tmp_path / ADDON_NAME / "__init__.py").read_bytes() == (SOURCE / "__init__.py").read_bytes()
    config = config_of(tmp_path)
    assert config["command"] == [str(PYTHON), "-m", "blender_tutor.helper"]
    assert config["cwd"] == str(PROJECT)
    assert config["port"] == PORT
    assert len(config["token"]) >= 32


def test_비밀_글자는_설치마다_달라진다(tmp_path):
    install(tmp_path / "a", PYTHON, platform="win32")
    install(tmp_path / "b", PYTHON, platform="win32")
    assert config_of(tmp_path / "a")["token"] != config_of(tmp_path / "b")["token"]


def test_다시_설치하면_애드온을_덮어쓰고_비밀_글자는_그대로_둔다(tmp_path):
    install(tmp_path, PYTHON, platform="win32")
    token = config_of(tmp_path)["token"]
    (tmp_path / ADDON_NAME / "__init__.py").write_text("# 지난 판", encoding="utf-8")
    install(tmp_path, PYTHON, platform="win32")
    assert config_of(tmp_path)["token"] == token  # 이미 켜진 도우미 프로그램이 계속 받을 수 있게
    assert (tmp_path / ADDON_NAME / "__init__.py").read_bytes() == (SOURCE / "__init__.py").read_bytes()


def test_기본_설치_위치는_Blender_5_2_사용자_애드온_폴더(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_addons_dir("win32") == tmp_path / "Blender Foundation" / "Blender" / "5.2" / "scripts" / "addons"


def test_기본_애드온_폴더는_운영체제마다_Blender가_찾는_자리(tmp_path):
    windows = default_addons_dir("win32", {"APPDATA": str(tmp_path / "AppData")}, tmp_path)
    assert windows == tmp_path / "AppData" / "Blender Foundation" / "Blender" / "5.2" / "scripts" / "addons"
    mac = default_addons_dir("darwin", {}, tmp_path)
    assert mac == tmp_path / "Library" / "Application Support" / "Blender" / "5.2" / "scripts" / "addons"


def test_Mac은_도우미를_파이썬_복사본을_실행_파일로_둔_앱_묶음으로_만들고_open으로_켜게_적는다(tmp_path):
    import plistlib

    base = tmp_path / "blender_python"  # Blender에 딸린 파이썬(가상 환경이 가리키는 진짜 실행 파일)
    (base / "bin").mkdir(parents=True)
    (base / "bin" / "python3.13").write_bytes(b"binary")
    venv = tmp_path / "venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(base / "bin" / "python3.13")
    target = install(tmp_path / "addons", venv / "python", platform="darwin", sign=False)
    app = target / "BlenderTutorHelper.app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleDisplayName"] == "Blender 첫걸음 도우미" and info["LSUIElement"] is True
    # 셸 스크립트로 파이썬을 켜면 권한이 'python3.13' 실행 파일에 잡혔다(HISTORY [313]). 실행 파일 자체가 파이썬 복사본이어야
    # 권한이 이 앱에 잡힌다
    assert (app / "Contents" / "MacOS" / info["CFBundleExecutable"]).read_bytes() == b"binary"
    assert info["LSEnvironment"]["PYTHONHOME"] == str(base)
    command = config_of(tmp_path / "addons")["command"]
    assert command[:7] == ["open", "-n", "-g", "-a", str(app), "--args", "-c"]
    assert str(tmp_path / "venv" / "lib" / "python3.13" / "site-packages") in command[7]  # 가상 환경 꾸러미를 덧붙임
    assert command[8:] == ["--token-file", str(target / "config.json")]
