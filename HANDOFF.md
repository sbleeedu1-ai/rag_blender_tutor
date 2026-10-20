# 인수인계

마지막 갱신: 2026-10-20 · Claude · DESKTOP-J9LV5HK(강의실 PC)

## 다음 할 일

1. **티켓 16: 검 연습 과정 파일 초안** `/implement .scratch/mvp-roundtrip/issues/16-검-연습-과정-파일-초안.md`
   - 새 브랜치에서 한다(예: `tickets/16-sword-course`).
   - `courses/sword.yaml`을 쓰고 `.venv\Scripts\python -m blender_tutor.course_check courses`로 문제 0개를 만든다.
   - 칸 이름과 모양은 `courses/_common.yaml`과 `tests/test_course_check.py`의 `COURSE` 예시를 그대로 따른다(결정은 HISTORY [19]-[21]).
2. 그다음 바로 시작할 수 있는 티켓: 17(진행 관리, 16과 함께 15만 기다림), 19(자료 준비), 34(홀드아웃 봉인).

## 지금 상태

- 티켓 15를 끝냈다. PR #3을 main에 병합했고, 브랜치 `tickets/15-course-check`는 로컬과 원격에서 지웠다.
- 테스트: `.venv\Scripts\python -m pytest` 37개 통과(API 키·Blender·화면 없이).
- 남은 다른 브랜치: `prototype/01-addon-roundtrip`, `prototype/02-helper-window-ui`(참고용 시제품, main에 합치지 않음).

## 모르면 실수할 것

- 다른 PC에서는 먼저 `python -m venv .venv` 다음 `.venv\Scripts\python -m pip install -e ".[dev]"`를 한다(`AGENTS.md`의 "준비").
- 연습 과정 파일에서 조작은 설명·메뉴·단축키 셋 다 꼭 적는다. 없으면 `없음`이라고 적는다. 메뉴 경로·이름표·Blender 조작 이름은 영어로 적는다.
- 따옴표 없는 `no`·`on`·`1.10`·`22:30`은 YAML이 글이 아닌 것으로 읽는다. 검사가 `yaml-trap`으로 잡으면 따옴표로 감싼다.
- 끝난 조건은 종류만 검사하고 값의 꼴은 아직 안 본다(티켓 17에서 함께 넣기로 함, 17번 Comments).
- 설명서 문장을 옮기지 않는다. 먼저 볼 소제목은 `경로.html#앵커` 꼴이다. 내려받은 설명서가 `data/manual_en_5.2/html/blender_manual_v520_en.html/`에 있어 앵커가 실제로 있는지 볼 수 있다(다른 PC에는 없을 수 있음).
- 티켓을 닫을 때 완료 조건 밖에 더한 것은 그 티켓 맨 아래 Comments에 이유와 함께 적는다(사용자 요청, HISTORY [21]).
- 비용이 드는 작업(분류·번역·임베딩·생각 수준 실측·평가 실행)은 실행 전에 사용자 확인.

## 사용자가 정해야 할 것

- 강사님 중간 확인 때 물어볼 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지.

## 추천 스킬

- `/implement <티켓 경로>`: 티켓을 읽고 `/tdd`로 구현한 뒤 `/code-review`로 검토하고 커밋한다. 스킬이 없으면 티켓 완료 조건을 하나씩 채우고, 검사 명령과 테스트를 돌린다.

## 참고 문서

- 명세 `.scratch/mvp-roundtrip/spec.md`, 티켓 `.scratch/mvp-roundtrip/issues/`
- 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`
- 검 단계 초안(조사) `archive/research/03-강좌-설명서-대조.md`의 "후보 A. 단순한 검"
