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
    install(tmp_path, PYTHON)
    assert (tmp_path / ADDON_NAME / "__init__.py").read_bytes() == (SOURCE / "__init__.py").read_bytes()
    config = config_of(tmp_path)
    assert config["command"] == [str(PYTHON), "-m", "blender_tutor.receiver"]
    assert config["cwd"] == str(PROJECT)
    assert config["port"] == PORT
    assert len(config["token"]) >= 32


def test_비밀_글자는_설치마다_달라진다(tmp_path):
    install(tmp_path / "a", PYTHON)
    install(tmp_path / "b", PYTHON)
    assert config_of(tmp_path / "a")["token"] != config_of(tmp_path / "b")["token"]


def test_다시_설치하면_애드온을_덮어쓰고_비밀_글자는_그대로_둔다(tmp_path):
    install(tmp_path, PYTHON)
    token = config_of(tmp_path)["token"]
    (tmp_path / ADDON_NAME / "__init__.py").write_text("# 지난 판", encoding="utf-8")
    install(tmp_path, PYTHON)
    assert config_of(tmp_path)["token"] == token  # 이미 켜진 도우미 프로그램이 계속 받을 수 있게
    assert (tmp_path / ADDON_NAME / "__init__.py").read_bytes() == (SOURCE / "__init__.py").read_bytes()


def test_기본_설치_위치는_Blender_5_2_사용자_애드온_폴더(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert default_addons_dir() == tmp_path / "Blender Foundation" / "Blender" / "5.2" / "scripts" / "addons"
