# 인수인계

마지막 갱신: 2026-10-29 · Claude · 강의실 PC · 브랜치 `feat/31-translate-embed` · PR 없음. 사용자 지시로 PR 생성 금지.

## 다음 할 일

1. [40번 소규모 검색 비교](.scratch/mvp-roundtrip/issues/40-소규모-검색-비교.md)의 **약 200청크 검색 묶음**부터 한다. 질문 20개(웹 10 + AI 10)와 정답 청크는 확정했다(HISTORY [94]-[97]). 정답 청크에 헷갈릴 청크와 다른 분야 청크를 더해 200개를 목표로 한다. 필요한 정답·경쟁 후보를 빼서 개수를 맞추지 않는다.
2. 그다음 비교 프로그램(18개 조합, 상위 4·6·8개, 시간 측정)을 만든다. 자동 시험은 가짜 임베딩으로. 유료 실행 전 추정 비용을 보여 주고 확인받는다(조각 약 200개 임베딩 + 질문 처리 1,080회 중 large 540회).
3. 40번 결과로 31번 검색 방식 선택을 이어 간다. 이후 34 → 33 → 32 → 35 → 36·37(HISTORY [62]).

## 지금 상태와 검증

- 이번 세션 커밋: HISTORY [94]-[97](`4044bbe`·`852d9d0`·`1f2577a`·`d1db53f`), 모두 푸시. 코드는 바꾸지 않았다.
- 강의실 PC .venv에 PyTorch 2.15.0 CPU판·sentence-transformers·openai를 설치하고 BGE-M3를 받았다(`C:\Users\201\.cache\huggingface\hub\models--BAAI--bge-m3`, 4.3GB). 첫 불러오기 24.5초, 문장 2개 0.39초. 그래픽카드 GTX 950(2GB)은 쓰지 않음. **pyproject.toml에는 아직 안 적음**(40번 구현 때 별도 설치 묶음으로, 티켓 Comments에 남김).
- 마지막 pytest는 어제 490개 통과. 오늘은 코드 변경이 없어 다시 돌리지 않았다.

## 질문 자료 (모두 data/, 커밋 안 함)

- `data/search_compare/questions/web_questions.jsonl`: 웹 질문 W1-W10. 원문 말투, 만든 방식(`written_from`)·확인한 것(`checked`)·근거 글 주소·조회수·정답 묶음(`answer_groups`: 묶음 안은 서로 대신, 묶음이 둘이면 둘 다 필요).
- `data/search_compare/questions/ai_questions.jsonl`: AI 질문 A1-A7·A9-A11(A8·A12는 뺀 이유와 함께 기록).
- `data/search_compare/web_questions/v1_대조용_2026-10-29/`(1판, 대조용)·`v2_사이트별_2026-10-29/`(SE·BA·DC·인프런 원자료 raw/와 README.md).
- `data/search_compare/scripts/`: 위 두 질문 파일을 만드는 프로그램과 정답 후보 찾기 프로그램. 다시 만들 때 `.venv\Scripts\python -I data\search_compare\scripts\build_web_questions.py` 뒤 `build_ai_questions.py`(겹침 검사 포함).
- **data/search_compare/(약 7.8MB)는 아직 드라이브 백업 전**이다. 다른 PC로 가기 전에 백업한다.

## 모르면 실수할 것

- PR은 만들지 않는다. 검토 결과는 빠짐없이 한 항목씩 사용자 판단을 받는다. 질문·채점 차례·시간 표본을 구현 편의로 빼지 않는다.
- "번역 없음" 질문은 대신할 정답까지 포함해 정답 청크 어느 것에도 번역이 없어야 한다(HISTORY [95]). 툴바·상단 메뉴 같은 번역된 목록 청크도 정답이 될 수 있어 확인한다.
- 웹 질문은 원문 말투를 살린다. 제목만 보고 상황을 짐작하지 말고 본문·답글로 확인한다(오늘 짐작 5개 중 1개만 맞았다, HISTORY [97]). W1·W6은 아직 본문을 안 읽었다. W4 정답(Clamp Overlap)은 SE 답변 근거의 추정이다.
- 청크 열쇠는 `쪽주소.html#소제목/차례`(번역 파일 열쇠와 같은 규칙, 1,379개 일치 확인).
- 원문만 / 원문+번역 합침 / 분리 검색은 독립 조건이다. 분리 검색 안에서만 같은 청크의 높은 점수 하나를 쓰되 개별 결과는 모두 남긴다.
- 자동 모드는 사이트 내부 목록 주소를 터미널에서 부르는 것과 레딧 미러를 막았다. 브라우저 확장(Claude in Chrome)은 `claude --chrome`으로 시작해야 연결되고, 레딧·네이버 지식iN은 확장이 막는다.
- 강사님에게 물을 것: GPT 비교에서 연습 과정 정보를 GPT에 주지 않는 조건이 괜찮은지.

## 추천 스킬과 참고

- `/implement .scratch/mvp-roundtrip/issues/40-소규모-검색-비교.md`. 유료 실행 승인은 별도로 받는다.
- [31번](.scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [용어집](CONTEXT.md), [경과 [93]-[97]](HISTORY.md), [결정](docs/adr/).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 40번 소규모 검색 비교의 200청크 묶음부터 이어서 해. PR은 만들지 마.`
