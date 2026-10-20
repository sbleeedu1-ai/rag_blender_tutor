# 인수인계

마지막 갱신: 2026-10-20 · Claude · DESKTOP-J9LV5HK(강의실 PC)

## 다음 할 일

1. **PR #6 병합(사용자 확인 뒤)**: 티켓 17 작업이 PR #6(`tickets/17-progress`)에 있고 CI를 통과했다. 사용자가 병합하라고 하면 병합 커밋으로 main에 합치고, 브랜치를 로컬·원격에서 지운다.
2. **티켓 18: 진행 기록 저장과 이어 하기** `/implement .scratch/mvp-roundtrip/issues/18-진행-관리-진행-기록-저장과-이어-하기.md`
   - main에서 새 브랜치(`tickets/18-progress-record` 등)를 만들어 시작한다.
   - 티켓 17의 `blender_tutor/progress.py`(`Progress`)에 진행 기록을 붙이는 일이다. 지금 `Progress`는 아무것도 저장하지 않는다. 지금 단계, 거절한 단계, 단계 시작 때 물체 수는 메모리에만 있다.
3. 그다음 바로 시작할 수 있는 티켓: 19(자료 준비), 34(홀드아웃 봉인).

## 지금 상태

- 티켓 17을 끝냈다(HISTORY [26]-[28]). 진행 관리 `blender_tutor/progress.py`, 끝난 조건 표 `blender_tutor/conditions.py`, 값 꼴 검사(`condition-value`)를 더했다.
- 테스트: `.venv\Scripts\python -m pytest` 78개 통과. 연습 과정 검사 `.venv\Scripts\python -m blender_tutor.course_check courses` 문제 0개.
- 브랜치 `tickets/17-progress`는 원격에 푸시되어 있다(PR #6). 이 HANDOFF도 같은 PR에 들어 있다.
- 남은 다른 브랜치: `prototype/01-addon-roundtrip`, `prototype/02-helper-window-ui`(참고용 시제품, main에 합치지 않음).

## 모르면 실수할 것

- **푸시·PR은 확인 없이 해도 된다**(HISTORY [28], `AGENTS.md`). main 병합만 확인받는다. 푸시 전에 커밋할 파일 목록에 비밀 정보가 없는지 본다. 전역 `~/.claude/CLAUDE.md`에는 아직 "푸시·PR 확인"이 남아 있지만 이 프로젝트에서는 `AGENTS.md`를 따른다.
- **main은 보호되어 있다.** CI "test"를 통과한 PR로만 합친다. 기록(HANDOFF·HISTORY)은 병합 전에 같은 PR에 올리면 병합 뒤 기록용 커밋이 따로 생기지 않는다.
- **끝난 조건 값 꼴**: 모드는 Blender `context.mode` 꼴(`EDIT_MESH`, `OBJECT`)이다. `EDIT`는 검사에서 잡힌다. 방금 조작은 `object.join` 꼴이다(Blender 조작 기록에는 `OBJECT_OT_join` 꼴로 남아 애드온이 바꿔야 함, 티켓 25 Comments).
- **Blender 조작 기록은 사람이 키보드·메뉴로 실행한 것만 남는다.** 파이썬으로 부른 조작은 화면이 있든 없든 남지 않아 자동 시험으로 확인할 수 없다. 이런 확인은 사용자에게 순서를 알려 주고 직접 해 달라고 한다(사용자가 그 방식을 원함).
- glTF 내보내기는 조작 기록에 안 남는다. 애드온이 `glTF2_post_export_callback`으로 알아채야 한다(티켓 25, HISTORY [27]).
- 이 PC의 Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`(5.2.2). 다른 PC에는 없을 수 있다.
- 진행 관리 판정의 한계 두 가지는 일부러 그대로 두었다(티켓 17 Comments): 뒤로 간 단계에 같은 조작 이름이 남아 있으면 곧바로 다시 묻는다. [네]를 누르기 전에 미리 붙인 부품은 알아채지 않는다(티켓 32 검수에서 다시 봄).
- 사용자는 설명 없이 뜨는 선택 창(질문 창)을 불편해했다. 고를 것이 있으면 먼저 글로 쉽게 풀어 설명한 다음 묻는다.
- 비용이 드는 작업(분류·번역·임베딩·생각 수준 실측·평가 실행)은 실행 전에 사용자 확인.

## 사용자가 정해야 할 것

- PR #6 병합 여부.
- 강사님 중간 확인 때 물어볼 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지.

## 추천 스킬

- `/implement <티켓 경로>`: 티켓을 읽고 `/tdd`로 구현한 뒤 `/code-review`로 검토하고 커밋한다. 스킬이 없으면 티켓 완료 조건을 하나씩 테스트 먼저 쓰고 구현한 뒤, 검사 명령과 전체 테스트를 돌린다.

## 참고 문서

- 명세 `.scratch/mvp-roundtrip/spec.md`("진행 관리"), 티켓 `.scratch/mvp-roundtrip/issues/18-진행-관리-진행-기록-저장과-이어-하기.md`, 지난 결정 `.scratch/mvp-roundtrip/issues/09-대화-기억-범위.md`
- 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`
- PR #6: https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/6
