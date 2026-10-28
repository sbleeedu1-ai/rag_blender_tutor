# 인수인계

마지막 갱신: 2026-10-28 · Claude · 강의실 PC · 브랜치 `feat/31-translate-embed`(원격에 올림, PR 아직 없음). 번역 뜻 검수를 모두 끝내고 5시간 한도 때문에 멈춤

## 다음 할 일

티켓 순서(HISTORY [62]): 30(끝남) → **31(진행 중)** → 34 → 33 → 32 → 35 → 36·37. 38은 needs-triage.

1. **티켓 31 3단계 뜻 검수: 끝남**(HISTORY [76]-[92]). 1,379청크 모두 Sonnet이 지금 지시문으로 봤고, 지적은 Opus가 원문·ko.po·코드 후보와 맞대어 확인한 뒤 사용자 판단을 받아 반영했다
   - 고침은 모두 `data/translations/apply_fixes_ko_none.py` 한 곳: `FIXES`(한 곳 고침 175건) + 아래쪽 낱말 맞추기 규칙(정점→버텍스, 모서리→에지, 면→페이스(줄 목록), 본→뼈대, 재질→머티리얼, 연산자→작업자, 압축→포장, 편집 모드→에디트 모드, 법선→노멀, 빈 오브젝트→엠프티, 메쉬→메시, 커스텀 노멀, 셰인함, 지오메트리, 수정자→모디파이어, 초점의 길이 등, 영어 괄호 규칙 [83], 같은 원문 줄 하나로 `SAME_SOURCE`). 다시 돌리면 `ko_none_fixes.jsonl`을 새로 씀
   - 규칙: 원문 같은 줄에 그 영어가 있을 때만 바꾸고, 청크 이름표의 화면 이름은 지킨다(ko.po 오타 "슬롯를"도 따름). 바꾼 뒤 늘 `translation_check`로 걸린 곳 수를 본다(지금 94, 늘면 원인부터)
   - 결과: 고친 청크 481개, 번역 검사 94곳(모두 일부러 둔 것). 표본·Sonnet 결과는 `data/translations/meaning_sample_*.md`·`meaning_review_sonnet_*.md`, 옛 판은 `archive/`
   - 티켓 31을 닫을 때 Comments에: 청크 옵션 이름이 붙어 뽑힘(Clamp or, Boundary Complex Mode 등), 그림 경로를 청크에 안 남김([77] 사용자 결정), 남은 번역투(어색함)는 4단계 평가 때 보기로 함
2. PR 전에 `STRUCTURE.md`에 `blender_tutor/translate.py`·`translation_check.py`와 `data/translations/` 파일 모양을 넣는다
3. 마지막 사용자 검수 목록: 무작위 50개 + ko.po에서 온 소문자 섞인 이름(설명 글 같은 것)이 든 청크([71])
4. 4단계 임베딩(유료, large 한 벡터/두 벡터 + bge-m3 한 번 비교, 개발용 한국어 질문 20개). 번역을 청크 파일 안으로 합치는 것도 이때(C3: 저장 형식을 읽는 규칙을 한곳에)
5. 티켓 34는 사용자가 집에서(HISTORY [62], 34 Comments)

- 검토 결과는 **하나도 빼지 말고 한 항목씩** 사용자 판단을 받는다(`AGENTS.md` "지킬 것").

## 지금 상태

- 테스트 **490개 통과**(main은 435개). 브랜치 원격에 모두 올림
- 티켓 31 1단계(메뉴 이름 검수) 끝([66]·[67])
- 2단계 번역 끝([68]-[71]): `blender_tutor/translate.py`. gpt-6-luna, 생각 수준 none, 5청크씩, 이름표 = 사전 표시 이름 + 본문 속 사전 이름(A) + ko.po 번역 하나뿐인 이름(B). 전체 1,379청크 약 $0.18(시험 포함 약 $0.20)
- 3단계 이름 검수 끝([72]-[75]), 뜻 검수 100개 시험 끝([76]): `blender_tutor/translation_check.py`. 고침 76건 / 청크 67개, 다시 검사 걸린 곳 90개는 모두 일부러 둔 것([72]에 종류)
- `data/translations/`(커밋 안 함): `ko_none.jsonl`(모델 원본, 덮어쓰지 않음), `ko_none_fixes.jsonl`(고친 줄·까닭), `apply_fixes_ko_none.py`(고침 목록), `check_ko_none.md`(검사 결과), `make_meaning_sample.py`·`meaning_sample100.md`·`meaning_review_sonnet100.md`(뜻 검수 시험), `trial50_*.jsonl`(50청크 시험 셋). 다른 PC에서 이어 하려면 이 폴더를 드라이브에 올린다
- 발견: 옵션 이름이 이어 붙은 청크(Absolute Increment Snap Increment 등). 티켓 31을 닫을 때 Comments에

## 사용자가 정해야 할 것

- 표본 검수 결과를 보고 B안(유료)을 할지
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
   - **다시 만들 수 없는 것**: `data\beginner_scope\`(번역할 218쪽, luna 분류), `data\menu_names\`(검수 기록·Haiku 판단, `menu_names.json`도 다시 만들면 검수 전 판으로 바뀜), `data\translations\`(유료 번역과 Claude 검수), `data\강사님의 기준.txt`
   - 드라이브에서 받을 때 `data\.env`가 `data\env`로 점이 빠질 수 있다. 이름을 `.env`로 바꾼다
   - **이미 있는 파일은 다시 만들지 않는다**: 아래 3번은 `data\chunks\`·`data\menu_names\`가 없을 때만. 있는 채로 돌리면 덮어쓴다(2026-10-27 집 PC에서 한 번 덮어써 드라이브에서 되살림)
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
