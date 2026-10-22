# 인수인계

마지막 갱신: 2026-10-22(티켓 23) · Claude · DESKTOP-J9LV5HK(강의실 PC)

## 다음 할 일

1. 티켓 23(메뉴 이름 한국어 표기)은 브랜치 `tickets/23-menu-name-display`에서 끝내고 PR을 올림. main 병합은 사용자 확인 뒤
2. 시작할 수 있는 티켓: 29(평가 프로그램)·25(애드온), 34(홀드아웃 봉인, 사람), 30(유료 초보자 범위 분류). 새 티켓 38(메뉴 이름 비슷한 말 표)은 needs-triage, 30 뒤.

## 지금 상태

- 답 엔진(`blender_tutor/answer_engine.py`): 티켓 21에서 질문 → 임베딩 1번 → 뜻 + 낱말(BM25) 검색 RRF 상위 6개 → 답변 모델 1번 → 답 조각 + 근거 목록(HISTORY [37]).
  - 티켓 22에서 검색어와 넘기는 글을 보탰다(PR #13 main 병합, HISTORY [38]-[41]). 호출은 그대로 2번.
    - 검색어 = 질문(+ 질문 속 한국어 메뉴 이름의 영어) + 직전 질문 + 단계 이름 + 먼저 볼 소제목 경로 + 방금 조작
    - 모델에: 먼저 볼 소제목(검색 상위 위에 덧붙임, 넓히지 않음), 50단어 미만 청크는 아래 소제목(없으면 형제)을 400단어까지(쪽 첫머리 글이면 그 쪽 앞 소제목들, 사용자 확인), 연습 과정 밖이면 비슷한 연습 과정 3개, 진행 중이면 지금 단계 내용만
    - 임베딩은 글 목록 → 벡터 목록. 연습 과정 밖이면 같은 호출에 질문만을 하나 더 실어 비슷한 연습 과정을 고른다(비용은 티켓 31에서 잼)
    - 메뉴 이름 찾기(`MenuNames.english_in`)는 검색 보조라 예외를 더 두지 않았다. 알려진 한계는 티켓 22 Comments
    - 용어집 `CONTEXT.md`에 설명서 갈래(분야·묶음·쪽·소제목·옵션·청크)를 넣었다. 사용자가 헷갈리면 말하기로 함
  - 티켓 23에서 메뉴 이름 표기를 더했다(HISTORY [42]). 답변 모델은 `[[Add > Mesh]]`처럼 영어로 표시해 쓰고, 엔진이 답이 흐르는 동안 한국어 화면 + 번역 켜짐이면 "추가(Add) > 메시(Mesh)", 아니면 영어만으로 바꾼다.
    - 여러 번역의 고정 짝은 저장소 `menu_choices.json`(영어 이름 → 문맥). 지금은 비어 있어 Edit Mode·Modifiers·Cube 같은 이름은 영어로 보인다(검수는 티켓 30 뒤)
    - 작업 상태 칸은 시제품 이름 `language`·`translate_interface`를 임시로 쓴다(티켓 25에서 확정)
    - 답 엔진 파일 나누기(HISTORY [41]에서 "티켓 23에서 같이 봄")는 사용자에게 물어봄
  - 아직 가짜 모델만 끼운다. 실제 OpenAI 연결은 유료 티켓 31(임베딩)·33(답변)에서.
  - 넘긴 것: 작업 상태 12칸 모양(25), 창의 오류 받기·엔진에 단계 넘기기(26·27), 번역을 BM25에도 넣을지·연습 과정 벡터(31), 검 파일 용어를 화면 글자로(32), 제목에서만 뽑은 이름 검수 뒤 더하기(30). 각 티켓 Comments.
- 테스트: `.venv\Scripts\python -m pytest` 210개 통과(`data/`가 없으면 1개 건너뜀).
- 남은 다른 브랜치: `prototype/01-addon-roundtrip`, `prototype/02-helper-window-ui`(참고용 시제품, main에 합치지 않음).

## 다른 PC에서 data/ 다시 만들기

`data/`는 커밋하지 않는다. 다른 PC에서 실제 자료 검사·테스트를 돌리려면, 구글 드라이브에 둔 두 가지만 가져와 나머지를 만든다(2026-10-20 빈 폴더에서 해 보니 지금 것과 똑같이 나옴, 약 2분).

1. `git pull` 뒤 (처음이면) `python -m venv .venv`, `.venv\Scripts\python -m pip install -e ".[dev]"`
2. 드라이브에서 가져와 이 자리에 둔다
   - `data\manual_en_5.2\blender_manual_html.zip` (설명서)
   - `data\ui_ko_5.2\ko.po`, `data\ui_ko_5.2\fr.po` (Blender 화면 번역)
3. 프로젝트 폴더에서 차례로 실행
   - 설명서 풀기: `.venv\Scripts\python -m zipfile -e data\manual_en_5.2\blender_manual_html.zip data\manual_en_5.2\html`
   - 청크 만들기: `.venv\Scripts\python -m blender_tutor.manual_chunks data\manual_en_5.2\html\blender_manual_v520_en.html data\chunks\manual_chunks.jsonl`
   - 메뉴 이름 사전: `.venv\Scripts\python -m blender_tutor.menu_names data\manual_en_5.2\html\blender_manual_v520_en.html data\ui_ko_5.2\ko.po data\ui_ko_5.2\fr.po data\menu_names`
4. 확인: `.venv\Scripts\python -m blender_tutor.course_check courses` → "문제 0개"(건너뛴다는 줄이 없어야 함), `.venv\Scripts\python -m pytest` → 건너뜀 없이 모두 통과

- 프로젝트 폴더 경로가 길면(예: 바탕화면 깊은 곳) 설명서 풀기가 Windows 경로 길이 제한(260자)에 걸려 멈춘다. `C:\sample\rag_blender_tutor`처럼 짧은 곳에 둔다.
- `data\강사님의 기준.txt`는 다시 만들 수 없으니 드라이브에도 따로 둔다.

## 모르면 실수할 것

- **부품이 늘었다(numpy, rank-bm25).** 다른 PC에서 `git pull` 뒤 `.venv\Scripts\python -m pip install -e ".[dev]"`를 다시 돌려야 답 엔진 테스트가 돈다.
- **BM25는 한국어 질문에 거의 일하지 않는다.** 영어 설명서와 겹치는 낱말이 없어서다. 그래서 티켓 22에서 영어 메뉴 이름·소제목 경로·조작 이름을 검색어에 붙였다. 실제 도움은 개발 평가에서 켬/끔(`Settings.use_bm25`)으로 견준다.
- **`\n`이 든 글을 셸(heredoc)로 파일에 쓰면 실제 줄바꿈으로 바뀌어 문법 오류가 난다**(2026-10-22 두 번 겪음). 파이썬 코드의 `\n`은 Edit 도구로 넣는다.

- **ko.po는 같은 영어도 문맥(msgctxt, 꼬리표)마다 따로 번역한다.** 어느 메뉴가 어느 문맥을 쓰는지는 Blender 코드에만 있다. 번역이 빠진 문맥은 fr.po(번역률 100%)와 대조해 찾는다(At Center: Operator "센터에서", 병합 메뉴의 Mesh는 번역 없음 → 화면은 영어). HISTORY [34]
- **용어 "블렌더 표기"**: Blender 화면에 보이는 메뉴·버튼·옵션 이름. "화면 이름"은 쓰지 않는다(사용자가 어색하다고 함).
- **청크 단위는 소제목이다.** 옵션은 청크 단위가 아니라 메타데이터 칸이자 긴 소제목을 나눌 경계다(티켓 06, HISTORY [33]).
- **파일 쓰기 도구가 `\ue000` 같은 표기를 실제 보이지 않는 글자로 바꿔 넣을 수 있다.** `tests/test_manual_chunks.py`의 지킴 테스트가 잡는다. 걸리면 글자 번호로 찾아 바꾼다.
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

- 메뉴 이름 검수(여러 개 291, 제목에서만 1,055): 초보자 범위 분류(티켓 30) 뒤 범위 안 것만. 고른 짝은 `menu_choices.json`에 영어 이름 → 문맥으로 적는다(티켓 23).
- 강사님 중간 확인 때 물어볼 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지.

## 추천 스킬

- `/implement <티켓 경로>`: 티켓을 읽고 `/tdd`로 구현한 뒤 `/code-review`로 검토하고 커밋한다.

## 참고 문서

- 명세 `.scratch/mvp-roundtrip/spec.md`("답 엔진", "자료 준비"), 티켓 `.scratch/mvp-roundtrip/issues/21-답-엔진-첫-왕복.md`·`22-답-엔진-검색어-만들기와-덧붙이기.md`, 조사 `git show 734adb5:".scratch/mvp-roundtrip/research/12-화면-한국어-번역-조사.md"`
- 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`
