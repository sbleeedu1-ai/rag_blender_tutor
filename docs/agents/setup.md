# 준비와 실행 명령

AGENTS.md에서 옮긴 줄이다(2026-11-16, HISTORY [367]). 글은 옮기기 전 그대로다. 명령은 Windows 모양이니 Mac에서는 AGENTS.md의 두 PC 표대로 바꿔 쓴다.

- 준비: Windows `python -m venv .venv` 뒤 `.venv\Scripts\python -m pip install -e ".[dev]"`. Mac은 Blender 안 파이썬으로 `/Volumes/mac_ssd/Applications/Blender.app/Contents/Resources/5.2/python/bin/python3.13 -m venv .venv` 뒤 `.venv/bin/python -m pip install -e ".[dev]"`, 이어서 `mkdir -p .venv/Scripts && ln -s ../bin/python .venv/Scripts/python.exe`(훅이 두 PC 모두 `.venv/Scripts/python.exe`를 부르므로 그 이름의 바로가기를 둔다. 없으면 터미널 명령이 모두 막힌다, HISTORY [182]·[307])
- 실행: 도우미 창은 Blender를 켜면 애드온이 함께 켠다(F10으로 부름, 손으로는 `.venv\Scripts\python -m blender_tutor.helper`, 환경 변수 `BLENDER_TUTOR_TOKEN` 필요). 애드온 설치 `.venv\Scripts\python -m blender_tutor.install_addon`(뒤에 Blender 환경 설정에서 애드온 켜기) · 애드온 자체 시험(Blender를 화면 없이 띄움, 기본 테스트 밖) `.venv\Scripts\python addon\selftest.py` · 연습 과정 파일 검사 `.venv\Scripts\python -m blender_tutor.course_check courses`
- 검사(2026-11-18, HISTORY [472]): 린트·코드 경계 `.venv\Scripts\python -m ruff check .`(자동 고침은 `--fix`), 타입 검사 `.venv\Scripts\python -m mypy`(설정은 `pyproject.toml`, 대상은 `blender_tutor/`). GitHub 검사가 pytest 앞에 둘 다 돌린다. 주석만 지웠는지는 `.venv\Scripts\python .claude\tools\same_ast.py`
