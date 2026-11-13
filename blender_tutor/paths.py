"""이 프로젝트의 폴더 위치. 여러 파일이 함께 쓰는 경로는 여기 한 곳에 둔다."""

import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
COURSES = PROJECT / "courses"
# 메뉴 이름 검수로 정한 표(번역 글자가 없어 저장소에 커밋한다, 티켓 23·31)
MENU_ALIASES = PROJECT / "menu_tables" / "menu_aliases.json"  # 설명서 철자 → 화면 철자
MENU_CHOICES = PROJECT / "menu_tables" / "menu_choices.json"  # 번역이 여러 개인 이름의 고정 짝(영어 이름 → 문맥)
MENU_TITLES = PROJECT / "menu_tables" / "menu_titles.json"  # 제목에서만 뽑은 이름 중 검수를 통과한 것
# 답 모델에 보낼 설정 값의 표(Blender에서 읽은 칸 이름·공장값이라 저장소에 커밋한다, HISTORY [270])
FIELDS = PROJECT / "state_tables" / "fields.json"  # 분야 코드 → 쉬운 설명(32종)
BUNDLES = PROJECT / "state_tables" / "bundles.json"  # 분야 코드 → 묶음 칸(갈아 끼우는 파일)


def progress_records(app_data: Path | None, home: Path) -> Path:
    """진행 기록(파일마다 작은 JSON, 지우지 않음) 폴더. 저장소 밖 사용자 설정 폴더에 둔다(명세 "진행 기록", 티켓 18·27).

    Windows 설정 폴더(APPDATA) 아래에 폴더를 만들고 써 볼 수 없으면(값이 없음, 관리되는 PC에서 쓰기가 막힘 등)
    사용자 폴더 아래로. 둘 다 안 되면 설정 폴더 쪽을 돌려주고, 기록은 진행 관리가 메모리에만 둔다.
    app_data는 운영체제의 설정 폴더(settings_base: Windows APPDATA, Mac ~/Library/Application Support).
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


def settings_base(platform: str, environ: Mapping[str, str], home: Path) -> Path | None:
    """프로그램 설정을 두는 사용자 폴더. APPDATA가 있으면 그것(Windows 기본, 자체 시험이 임시 폴더로 바꿀 때 Mac도),
    없으면 Mac은 ~/Library/Application Support, Windows는 None."""
    if app_data := environ.get("APPDATA"):
        return Path(app_data)
    return home / "Library" / "Application Support" if platform == "darwin" else None


def default_progress_records() -> Path:
    """이 PC의 진행 기록 폴더(도우미를 켤 때 한 번 고른다)."""
    return progress_records(settings_base(sys.platform, os.environ, Path.home()), Path.home())


WINDOWS_BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"


def mac_blender_apps(home: Path) -> list[Path]:
    """Mac에서 Blender.app을 찾아볼 자리: 응용 프로그램 폴더, 사용자 응용 프로그램 폴더, 바깥 저장소의 응용 프로그램 폴더."""
    return [Path("/Applications/Blender.app"), home / "Applications" / "Blender.app", *sorted(Path("/Volumes").glob("*/Applications/Blender.app"))]


def blender_executable(platform: str, environ: Mapping[str, str], mac_apps: Iterable[Path]) -> str:
    """자체 시험·메뉴 검수가 띄울 Blender 실행 파일. 환경 변수 BLENDER가 먼저다.

    Mac은 앱 묶음(Blender.app) 안의 Contents/MacOS/Blender를 mac_apps 차례로 찾고, 없으면 첫 자리를 돌려준다(실행이 실패해 알린다).
    """
    if "BLENDER" in environ:
        return environ["BLENDER"]
    if platform != "darwin":
        return WINDOWS_BLENDER
    candidates = [app / "Contents" / "MacOS" / "Blender" for app in mac_apps]
    return str(next((path for path in candidates if path.exists()), candidates[0] if candidates else Path("Blender")))


def default_blender() -> str:
    """이 PC의 Blender 실행 파일(blender_executable을 지금 운영체제로)."""
    return blender_executable(sys.platform, os.environ, mac_blender_apps(Path.home()))
