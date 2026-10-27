# 인수인계

마지막 갱신: 2026-10-27 밤 · Claude · B783D5080(집 PC) · 브랜치 `feat/31-translate-embed`(원격에 올림, PR 아직 없음). 앞 세션이 세션 한도 때문에 문장 뜻 검수를 새 세션으로 넘김

## 다음 할 일

티켓 순서(HISTORY [62]): 30(끝남) → **31(진행 중)** → 34 → 33 → 32 → 35 → 36·37. 38은 needs-triage.

1. **티켓 31 3단계: 번역 문장 뜻 검수(표본, 무료)**. 이름 검수는 끝났다(HISTORY [72]-[75]). 이름이 아닌 문장의 뜻이 틀린 곳은 코드로 못 잡아서 Claude가 읽는다
   - **방법: Sonnet(노력치 medium)으로 나머지 전부**(HISTORY [76], 100개 시험에서 5시간 약 3%·주간 약 1%, 진짜 지적 4/8, 놓침 없음 5/5). 주간 한도는 2026-10-30 0시에 다시 참
     1. `data/translations/make_meaning_sample.py`를 고쳐 **청크마다 이름표(`translate.glossary(..., body)`)를 함께 적고**, 이미 본 100개(씨앗 2027)를 뺀 1,279개를 100개씩 파일 13개로 나눈다
     2. Sonnet 세션(Claude 데스크톱이면 새 세션, VS Code 터미널이면 `claude --model sonnet`)이 파일마다 읽고 `meaning_review_sonnet_<n>.md`에 적는다. 지시문은 [76] 시험 때와 같게 하되 "이름표의 글자는 공식 화면 글자라 지적하지 않는다"를 더한다
     3. Opus가 지적만 읽고 확인해 `apply_fixes_ko_none.py`에 더한다(긴 Opus 대화는 한 번 답할 때 5시간 한도 약 1%를 쓰니 새 세션에서)
   - **VS Code 터미널(CLI)에서 할 때**: 구독 한도는 데스크톱 앱과 같은 계정이라 함께 쓴다. 다른 점은 세션을 직접 열고, 끝난 알림이 없다는 것
     1. 터미널 1(Opus): `cd C:\WORK\rag_blender_tutor` → `claude` → "AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번의 1단계(표본 파일 13개 만들기)까지 해"
     2. 터미널 2(Sonnet): `cd C:\WORK\rag_blender_tutor` → `claude --model sonnet` → 노력치는 `/model` 메뉴에서 medium(정확한 방법은 `/help`로 확인) → 파일마다 "`data/translations/meaning_sample_<n>.md` 하나만 읽고 뜻을 검수해 `meaning_review_sonnet_<n>.md`에 써. 규칙은 HISTORY [76] 시험 지시문과 같고, 이름표의 글자는 지적하지 않는다. git·API·다른 파일 고치기는 하지 마"
     3. 사용량은 각 터미널에서 `/usage`. 한 파일이 끝날 때마다 늘어난 %를 보고, 주간 한도가 모자라 보이면 멈춘다
     4. 다 끝나면 터미널 1에 "meaning_review_sonnet_*.md 지적을 확인해 반영해"라고 알린다(자동 알림 없음)
   - 두 터미널이 같은 폴더를 쓰므로 Sonnet 쪽은 결과 파일 쓰기 외에 아무것도 하지 않게 한다
   - 번역은 `translation_check.reviewed(Path("data/translations/ko_none.jsonl"))`로 읽는다(모델 원본 위에 고친 줄을 덮음). 원문은 `translate._in_scope(...)`의 `Piece.chunk.text`. 원문과 번역은 줄 나눔이 같아 줄 번호로 맞댈 수 있다
   - 고칠 것은 `data/translations/apply_fixes_ko_none.py`의 `FIXES`에 더하고 그 스크립트를 다시 돌린다(바꿀 글자가 없으면 멈춤). 그다음 `.venv\Scripts\python -m blender_tutor.translation_check data\translations\ko_none.jsonl`로 다시 검사
   - 판단 기준: 원문과 화면이 **같은 것을 가리킬 때** 어색하거나 오타가 있어도 화면 글자를 따른다([66] 146 Unlink, [75]). LMB → 마우스 왼쪽 버튼처럼 풀어 쓴 것은 둔다([71])
   - 틀린 곳이 많으면 B안(번역 모델에 원문 + 번역을 주고 뜻이 다른 문장만 표시하게 함, 유료 약 $0.1-0.2 어림)을 **비용을 다시 계산해 보이고 확인받은 뒤**
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
