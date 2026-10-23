"""이 프로젝트의 폴더 위치. 여러 파일이 함께 쓰는 경로는 여기 한 곳에 둔다."""

import os
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
COURSES = PROJECT / "courses"
# 진행 기록(파일마다 작은 JSON, 지우지 않음)은 저장소 밖 사용자 설정 폴더에 둔다(명세 "진행 기록", 티켓 18·27)
PROGRESS_RECORDS = Path(os.environ.get("APPDATA") or Path.home()) / "blender_tutor" / "progress"
