"""진행 기록 폴더 고르기: 설정 폴더(APPDATA)에 쓸 수 없으면 사용자 폴더로."""

from blender_tutor.paths import progress_records


def test_설정_폴더에_쓸_수_있으면_그_아래(tmp_path):
    assert progress_records(tmp_path / "AppData", tmp_path / "home") == tmp_path / "AppData" / "blender_tutor" / "progress"


def test_설정_폴더가_없거나_쓸_수_없으면_사용자_폴더_아래(tmp_path):
    home = tmp_path / "home"
    assert progress_records(None, home) == home / "blender_tutor" / "progress"
    blocked = tmp_path / "AppData"
    blocked.write_text("", encoding="utf-8")  # 폴더 자리에 파일이 있어 그 아래 폴더를 못 만듦
    assert progress_records(blocked, home) == home / "blender_tutor" / "progress"


def test_둘_다_쓸_수_없으면_설정_폴더_쪽을_돌려준다(tmp_path):
    # 기록은 메모리에만 남고 진행은 계속된다(ProgressManager가 쓰기 실패를 받아 준다)
    blocked_app, blocked_home = tmp_path / "AppData", tmp_path / "home"
    blocked_app.write_text("", encoding="utf-8")
    blocked_home.write_text("", encoding="utf-8")
    assert progress_records(blocked_app, blocked_home) == blocked_app / "blender_tutor" / "progress"
