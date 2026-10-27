# 인수인계

마지막 갱신: 2026-10-27 저녁 · Claude · DESKTOP-J9LV5HK(강의실 PC) · 브랜치 `feat/31-translate-embed`(원격에 올림, PR 아직 없음). 다음은 집 PC에서 이어 감

## 다음 할 일

티켓 순서(HISTORY [62]): 30(끝남) → **31(진행 중)** → 34 → 33 → 32 → 35 → 36·37. 38은 needs-triage.

1. **티켓 31 2단계 번역**(유료, luna): 먼저 50청크로 생각 수준 none/medium을 견주는 **비용을 계산해 보이고 확인받은 뒤** 실행. 번역은 따로 둔 원본에서 청크 안으로 합친다
   - 메뉴 이름은 사전의 고정 짝 글자를 따른다. **짝이 없는 여러 번역 이름(Smart UV Project)은 영어 그대로인지 시험을 넣는다**(HISTORY [67] P1)
   - 번역 스크립트는 아직 없다. `/tdd`로 시험부터
2. 3단계 번역 검수(코드 + 사용자 50개) → 4단계 임베딩(유료, large 한 벡터/두 벡터 + bge-m3 한 번 비교, 개발용 한국어 질문 20개)
3. 티켓 34는 사용자가 집에서(HISTORY [62], 34 Comments)

- 검토 결과는 **하나도 빼지 말고 한 항목씩** 사용자 판단을 받는다(`AGENTS.md` "지킬 것").

## 지금 상태

- 테스트 **454개 통과**(main은 435개). 브랜치 커밋 5개, 마지막 `7649e11`
- 티켓 31 **1단계(메뉴 이름 검수) 끝**: 화면 검수 197줄(HISTORY [66]), 코드 검토 9개 판단(HISTORY [67])
  - 저장소: `menu_choices.json`(고정 짝 112 + 경로 열쇠 6), `menu_titles.json`(통과 제목 80), `menu_aliases.json`(철자 3). 모양은 `STRUCTURE.md`, 용어는 `CONTEXT.md`
  - `data/menu_names/`: 검수 기록 `remaining_review.json`, 한 번 돌린 합치기 `merge_menu_review.py`, 사전 `menu_names.json`(이전 것 `_v1`·`_v2`)
- **개발 평가 숫자가 지난번과 달라질 수 있다**: 평가도 같은 엔진이라 이제 통과 제목이 검색어에 붙는다
- 쉬운 말 풀이는 잠시 뺌(사용자). 모델 조사 `.scratch/mvp-roundtrip/research/31-번역-모델-조사.md`

## 사용자가 정해야 할 것

- 번역 생각 수준(50청크 none/medium 결과를 보고), 번역·임베딩 비용
- 강사님 중간 확인 때 물을 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지

## 모르면 실수할 것

**메뉴 이름·번역**
- ko.po는 같은 영어도 문맥(msgctxt)마다 따로 번역하고, 어느 메뉴가 어느 문맥을 쓰는지는 Blender 코드에만 있다. 빠진 문맥은 fr.po(번역률 100%)와 대조해 찾는다(HISTORY [34])
- Blender에서 뽑은 화면 글자에는 빈틈이 있다(C 코드가 그리는 글자). 같은 메뉴 안에서도 공식 번역이 갈린다(Single: 싱글·단일). 이름 줄 글자를 따른다
- 청크 단위는 소제목이고, 옵션은 메타데이터 칸이자 긴 소제목을 나눌 경계다(HISTORY [33])
- BM25는 한국어 질문에 거의 일하지 않아 영어 메뉴 이름·소제목 경로를 검색어에 붙인다. 실제 도움은 개발 평가에서 `Settings.use_bm25` 켬/끔으로 견준다
- 하위 에이전트는 띄울 때마다 토큰이 크다(조사 하나 약 19만, 코드 검토 둘 약 15만). 번역처럼 큰 일은 API 스크립트로

**사용자와 일할 때**
- Blender 위치는 일상 말이 아니라 화면 글자로(에디트 모드, 페이스). 길이 확실하지 않으면 설명서를 먼저 찾아 근거와 함께. 스크린숏의 작은 한글은 잘못 읽을 수 있다(셰인함 → 세인함)
- `!` 명령은 Git Bash라 경로를 `/`로 쓴다. 사용자가 입력하면 진행 중인 작업이 끊기니 사용자 확인 작업은 순서를 나눈다
- Blender 조작 기록에는 사람이 키보드·메뉴로 한 것만 남는다. 그런 확인은 순서를 알려 주고 직접 해 달라고 한다

**코드·파일**
- 셸(heredoc)로 `\n`·`\b` 같은 글을 파일에 쓰면 실제 글자로 바뀐다(2026-10-22 두 번, 2026-10-27 HANDOFF에서 한 번). 파일 글은 Edit·Write 도구로
- 파일 쓰기 도구가 `\ue000` 같은 표기를 보이지 않는 글자로 바꿔 넣을 수 있다. `tests/test_manual_chunks.py`가 잡는다
- 애드온은 Blender 폴더에 복사된 것이 돈다. 고치면 `.venv\Scripts\python -m blender_tutor.install_addon` 후 Blender 다시 켜기(새 PC는 환경 설정 > 애드온에서 "Blender 첫걸음 도우미" 켜기)
- 흐름 기록은 늘 켜져 있다(`helper.py`의 `RECORD_STREAM = True`). 코드 동결 전에 False로(티켓 37)
- Qt 신호에 메서드를 이을 때는 그 객체를 `self.`로 붙잡아 둔다(티켓 39 검토 S1)
- `CourseDesk`에 버튼 함수를 더하면 `RecordingDesk`와 `replay`에도 더한다(`tests/test_state_stream.py`가 잡음)
- 조건 값 꼴: 모드는 `context.mode`(`EDIT_MESH`), 방금 조작은 `object.join`(애드온이 `OBJECT_OT_join`에서 바꿈), 방향은 `Z`나 `[Y, Z]`, 화면은 `돌림`·`확대`·`축소`·`옮김`·`전체`
- 화면 돌리기·확대·옮기기·Home은 조작 기록에 남지 않아(REGISTER 없음) 3D 화면 시점 값으로 알아챈다. 파일 열기·저장은 경로가 아니라 `load_post`·`save_post` 사건으로 받는다
- 이 PC의 Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`(5.2.2)

## 다른 PC에서 data/ 만들기

`data/`는 커밋하지 않는다. 드라이브의 `블렌더_RAG\data`에서 받아 나머지를 만든다(약 2분).

1. `git pull` 뒤 (처음이면) `python -m venv .venv`, `.venv\Scripts\python -m pip install -e ".[dev]"`(부품이 늘었으면 다시)
2. 드라이브에서 받아 이 자리에 둔다
   - `data\manual_en_5.2\blender_manual_html.zip`: 드라이브에는 `data` 바로 아래에 있으니 `manual_en_5.2` 폴더를 만들어 넣는다
   - `data\ui_ko_5.2\ko.po`, `fr.po`
   - **다시 만들 수 없는 것**: `data\beginner_scope\`(번역할 218쪽, luna 분류), `data\menu_names\`(검수 기록·Haiku 판단), `data\강사님의 기준.txt`
3. 프로젝트 폴더에서 차례로
   - `.venv\Scripts\python -m zipfile -e data\manual_en_5.2\blender_manual_html.zip data\manual_en_5.2\html`
   - `.venv\Scripts\python -m blender_tutor.manual_chunks data\manual_en_5.2\html\blender_manual_v520_en.html data\chunks\manual_chunks.jsonl`
   - `.venv\Scripts\python -m blender_tutor.menu_names data\manual_en_5.2\html\blender_manual_v520_en.html data\ui_ko_5.2\ko.po data\ui_ko_5.2\fr.po data\menu_names`
4. 확인: `.venv\Scripts\python -m blender_tutor.course_check courses` → "문제 0개", `.venv\Scripts\python -m pytest` → 건너뜀 없이 모두 통과

- 폴더 경로가 길면 설명서 풀기가 Windows 260자 제한에 걸린다. `C:\WORK\rag_blender_tutor`처럼 짧은 곳에

## 추천 스킬과 첫 문장

- `/implement .scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md` → `/tdd`로 구현, `/code-review`로 검토. 스킬 없이: 위 "다음 할 일" 1-2번 차례대로
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`

## 참고 문서

- 티켓 `.scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md`, 명세 `.scratch/mvp-roundtrip/spec.md`("답 엔진", "자료 준비")
- 구조 `STRUCTURE.md`, 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`(티켓 31은 [65]-[67])
- Codex 전체 점검 프롬프트 4개(2026-10-26에 씀, 끝남): `git show 7649e11:HANDOFF.md`의 맨 아래 "Codex에 붙여 넣을 프롬프트"
