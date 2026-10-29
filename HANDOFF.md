# 인수인계

마지막 갱신: 2026-10-29 · Claude · 강의실 PC · 브랜치 `feat/31-translate-embed` · PR 없음. 사용자 지시로 PR 생성 금지.

## 다음 할 일

1. **본 측정을 돌린다**(유료 승인 받음, 어림 $0.017. 사용자가 "시작"이라고 한 뒤에). 강의실 PC에서 Blender 5.2를 기본 파일로 열어 두고 손대지 않고, 도우미 창은 끄고, 설정·작업 관리자는 닫는다. 측정 중에는 PC·Codex를 쓰지 않는다.
   ```
   .venv\Scripts\python -m blender_tutor.search_compare run --name search_compare --yes --note "강의실 PC, Blender 5.2.2 LTS 기본 파일(저장 안 함) 열어 두고 조작 없음, 도우미 창 끔. 함께 켬: VS Code(Claude Code 실행 중, 터미널에 Codex 열어 둠, 측정 중 작업 없음), Chrome(Claude 탭 1개), 알림 영역 상주 프로그램(Copilot·NVIDIA 등)"
   ```
   - 메모는 그날 실제로 켠 것에 맞게 고친다. BGE-M3를 불러오는 데 약 25초, 이후 1,080회가 돈다. 백그라운드로 돌리고 끝 알림을 기다린다.
   - 결과: `results/20261029_search_compare/` (날짜가 바뀌면 그 날짜). 같은 이름이 있으면 멈춘다.
2. `요약.md`를 읽고 상위 4·6·8개 비교표로 후보(잠정 3개)를 근거와 함께 제안해 사용자 판단을 받는다. 결과를 HISTORY에 남기고, 티켓 40 `## Comments`에 완료 조건 밖에 더한 것을 적는다(아래 "더한 것").
3. 검토: 사용량을 아끼려고 하위 에이전트 검토(`code-review`)는 쓰지 않기로 했다. Codex에 `17c9dfd` diff 검토를 맡기는 것을 권했다. 검토 결과는 AGENTS.md 규칙대로 한 항목씩 사용자 판단을 받는다.
4. 40번 결과로 31번 검색 방식 선택을 이어 간다. 이후 34 → 33 → 32 → 35 → 36·37(HISTORY [62]).

## 지금 상태와 검증

- 비교 프로그램 `blender_tutor/search_compare.py`와 시험 `tests/test_search_compare.py`(12개)를 커밋했다(`17c9dfd`). pytest **502개 통과**(2026-10-29 세션 끝).
- 실제 자료로 확인: 청크 200(번역 90), 질문 20(번역 있음 10), 검색어에 사전 영어 이름이 붙음(W1 → "… Make Origin Floor Rotate …"). `estimate` 결과 large DB 약 104,265토큰 + 질문 541회 약 26,103토큰 → 약 $0.017.
- 검색용 DB 6개를 만들었다(`data/search_compare/db/`, 커밋 안 함). large는 약 9초, BGE-M3(CPU)는 약 14분. 같은 글이면 run이 다시 만들지 않고 읽는다.
- 이번 세션 결정은 HISTORY [100].

## 모르면 실수할 것

- PR은 만들지 않는다. 검토 결과는 빠짐없이 한 항목씩 사용자 판단을 받는다. 질문·채점 차례·시간 표본을 구현 편의로 빼지 않는다.
- 채점은 1회차 순위, 시간은 모든 회차. 3회차 순위는 모두 남기고 다르면 `요약.md`에 질문 번호로 표시한다(평균 내지 않음).
- `build-db`는 실제 사용 토큰을 파일에 남기지 않는다(run만 `설정.json`의 "유료"에 남김). large DB를 만든 실제 비용은 OpenAI 사용량 화면에서 본다.
- BGE-M3는 `pip install -e ".[dev,compare]"`가 필요하다(강의실 PC .venv엔 이미 설치, 모델은 `C:\Users\201\.cache\huggingface\hub\models--BAAI--bge-m3`). 다른 PC에서는 모델 내려받기(4.3GB)와 DB 다시 만들기(약 14분)가 든다.
- **data/search_compare/(질문·묶음·DB)는 아직 드라이브 백업 전**이다. 다른 PC로 가기 전에 백업한다.
- 묶음을 바꾸면 모든 조건에 같이 적용하고 새 결과로 다시 비교한다(`check_hidden_answers.py`도 다시 본다). "번역 없음" 질문은 대신할 정답까지 번역이 없어야 한다(HISTORY [95]).
- 사용자는 Blender 기능을 깊이 모른다. 청크 정답 여부 같은 판단은 Claude가 근거와 권하는 답을 낸다(HISTORY [98]).
- 강사님에게 물을 것: GPT 비교에서 연습 과정 정보를 GPT에 주지 않는 조건이 괜찮은지.

## 더한 것 (티켓을 닫을 때 Comments에 옮긴다)

- `estimate`·`build-db` 명령(유료 어림과 DB만 따로 만들기), 유료 모델은 `--yes` 없이 멈춤
- `pyproject.toml`의 설치 묶음 `compare`(sentence-transformers)
- 시작할 때 묶음·정답 검사(두 번 든 청크, 청크 파일에 없는 열쇠, 묶음 밖 정답)

## 추천 스킬과 참고

- 스킬 없이 위 1번 명령을 백그라운드로 돌리고, 끝나면 `요약.md`를 읽는다.
- [40번](.scratch/mvp-roundtrip/issues/40-소규모-검색-비교.md), [31번](.scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md), [구조 6절 "소규모 검색 비교"](STRUCTURE.md), [경과 [93]-[100]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해. 측정은 내가 시작하라고 하면 돌려. PR은 만들지 마.`
