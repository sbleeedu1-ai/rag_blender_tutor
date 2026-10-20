# 인수인계

마지막 갱신: 2026-10-20 · Claude · DESKTOP-J9LV5HK(강의실 PC)

## 다음 할 일

1. **티켓 19 PR 병합(사용자 확인 뒤)**: 브랜치 `tickets/19-manual-chunks`의 PR. CI "test"를 통과하고 사용자가 병합하라고 하면 병합 커밋으로 main에 합치고, 브랜치를 로컬·원격에서 지운다.
2. 사용자 답에 따라: "모드·메뉴·단축키" 상자 위치(아래 "사용자가 정해야 할 것"), 검토에서 나온 코드 모양 정리.
3. 그다음 시작할 수 있는 티켓: 19 병합 뒤 20(메뉴 이름 한국어-영어 짝)·21(답 엔진 첫 왕복)이 풀린다. 25(애드온), 34(홀드아웃 봉인)는 바로 가능.

## 지금 상태

- 티켓 19를 끝냈다(HISTORY [32]).
  - `blender_tutor/manual_chunks.py`: `chunk_page`(쪽 하나), `chunk_manual`(묶음 전체), 실행 `.venv\Scripts\python -m blender_tutor.manual_chunks data/manual_en_5.2/html/blender_manual_v520_en.html data/chunks/manual_chunks.jsonl`
  - 전체 실행: 청크 8,995개(쪽 2,085개), 13초. 결과는 `data/chunks/`(커밋 안 함). 다른 PC에서는 다시 돌려야 한다.
- 테스트: `.venv\Scripts\python -m pytest` 114개 통과. 새 의존성 `beautifulsoup4`가 있어 다른 PC에서는 `.venv\Scripts\python -m pip install -e ".[dev]"`를 다시 돌린다.
- 남은 다른 브랜치: `prototype/01-addon-roundtrip`, `prototype/02-helper-window-ui`(참고용 시제품, main에 합치지 않음).

## 모르면 실수할 것

- **진행 기록은 파일 단위다.** 진행 관리는 Blender 창 번호마다 하나씩 둔다(티켓 27 완료 조건, HISTORY [31]).
  - 다른 파일을 열면 지금 진행을 비운다. 앞 파일의 진행은 그 파일 기록에 남아 있다.
  - 기록을 쓰는 때는 사용자가 확인한 변화가 있을 때뿐이다: [네], 다음 단계·건너뛰기·뒤로, 연습 과정 고르기·바꾸기.
  - 끝낸 단계는 [네]와 "다음 단계" 버튼만 센다. 건너뛴 단계는 넣지 않는다.
- **파일 열기·저장은 사건으로 받는다.** 경로만으로는 "열기"와 "다른 이름 저장"을 가를 수 없기 때문이다. 애드온이 `load_post`·`save_post`로 알아채 보내야 한다(티켓 25 Comments). 사건 없이 경로만 바뀌면 진행 관리는 아무것도 하지 않는다.
- **푸시·PR은 확인 없이 해도 된다**(HISTORY [28], `AGENTS.md`).
  - main 병합만 확인받는다.
  - 푸시 전에 커밋할 파일 목록에 비밀 정보가 없는지 본다.
- **main은 보호되어 있다.**
  - CI "test"를 통과한 PR로만 합친다.
  - 기록(HANDOFF·HISTORY)은 병합 전에 같은 PR에 올린다.
- 끝난 조건 값 꼴:
  - 모드는 `context.mode` 꼴이다(`EDIT_MESH`).
  - 방금 조작은 `object.join` 꼴이다. 애드온이 `OBJECT_OT_join`에서 바꿔 보내야 한다(티켓 25).
- Blender 조작 기록에는 사람이 키보드·메뉴로 실행한 것만 남는다. 이런 확인은 사용자에게 순서를 알려 주고 직접 해 달라고 한다.
- 이 PC의 Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`(5.2.2).
- 사용자는 설명 없이 뜨는 선택 창을 불편해한다.
  - 고를 것이 있으면 먼저 글로 쉽게 풀어 설명한 다음 묻는다.
  - 코드 이름·전문 용어를 줄이고, 예시(파일 A·B처럼)로 설명하면 잘 통했다.
- 비용이 드는 작업(분류·번역·임베딩·생각 수준 실측·평가 실행)은 실행 전에 사용자 확인.

## 사용자가 정해야 할 것

- 티켓 19 PR 병합 여부.
- "모드·메뉴·단축키" 상자 위치: 명세는 "쪽 첫 청크"인데, 지금은 상자가 있던 소제목의 청크에 둔다(한 쪽에 도구가 여럿이면 상자도 여럿, 1,510개 중 1,047개가 쪽 첫 청크가 아님). Claude 권장: 지금대로.
- 강사님 중간 확인 때 물어볼 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지.

## 추천 스킬

- `/implement <티켓 경로>`: 티켓을 읽고 `/tdd`로 구현한 뒤 `/code-review`로 검토하고 커밋한다.

## 참고 문서

- 명세 `.scratch/mvp-roundtrip/spec.md`("자료 준비"), 티켓 `.scratch/mvp-roundtrip/issues/19-자료-준비-설명서-HTML을-청크로.md`
- 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`
