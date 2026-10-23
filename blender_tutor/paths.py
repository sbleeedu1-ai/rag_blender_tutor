"""이 프로젝트의 폴더 위치. 여러 파일이 함께 쓰는 경로는 여기 한 곳에 둔다."""

import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
COURSES = PROJECT / "courses"


def progress_records(app_data: Path | None, home: Path) -> Path:
    """진행 기록(파일마다 작은 JSON, 지우지 않음) 폴더. 저장소 밖 사용자 설정 폴더에 둔다(명세 "진행 기록", 티켓 18·27).

    Windows 설정 폴더(APPDATA) 아래에 폴더를 만들고 써 볼 수 없으면(값이 없음, 관리되는 PC에서 쓰기가 막힘 등)
    사용자 폴더 아래로. 둘 다 안 되면 설정 폴더 쪽을 돌려주고, 기록은 진행 관리가 메모리에만 둔다.
    맥을 붙일 때는 맥의 설정 폴더 자리(~/Library/Application Support)를 먼저 보게 바꾼다.
    """
    places = [base / "blender_tutor" / "progress" for base in (app_data, home) if base is not None]
    for place in places:
        try:
            place.mkdir(parents=True, exist_ok=True)
            probe = place / ".write-test"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
            return place
        except OSError:
            continue
    return places[0]


def default_progress_records() -> Path:
    """이 PC의 진행 기록 폴더(도우미를 켤 때 한 번 고른다)."""
    app_data = os.environ.get("APPDATA")
    return progress_records(Path(app_data) if app_data else None, Path.home())
