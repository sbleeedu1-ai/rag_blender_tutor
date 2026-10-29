# 인수인계

마지막 갱신: 2026-10-29 · Claude · 강의실 PC · PR #28 병합 전에 씀(브랜치 `feat/31-translate-embed` → main). 이어받을 때 PR #28이 병합됐는지 git으로 먼저 본다.

## 다음 할 일

1. **티켓 33: 실제 답변 모델을 붙이고 생각 수준 none/low 속도를 잰다.** [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md) Comments의 넘겨받은 일을 먼저 읽는다.
   - 새 브랜치에서 시작한다(main 최신에서).
   - 답변 모델(명세 기본 `gpt-6-luna`) 연결 코드 → 가짜로 시험 → **어림 비용을 보이고 사용자 확인** → 강의실 PC 도우미 창에서 질문 준비 0.5초 / 첫 글자 2초 / 답 끝 6초를 잰다.
   - 함께 볼 것(HISTORY [107]·[109]): 첫 질문 검색 0.54초(목표 0.5초 근처), 도우미 창을 실제로 띄워 진짜 임베딩 근거가 나오는지, 용어표를 실제 모델이 지키는지([105]), 원문만 넘겨도 한국어 답이 괜찮은지([104]).
   - 답변 모델이 진짜가 되면 엔진 만들기를 `stand_in.py` 밖으로 옮기고 `stand_in.py`는 `archive/`로(파일 첫머리 주석).
2. 로컬 임베딩 후보 3개(granite-embedding-97m-multilingual-r2 / multilingual-e5-small / embeddinggemma-300m) 측정. **사용자가 시작하라고 할 때만.** 처음 불러오기는 처음 설치(내려받은) 직후 한 번 재서 기록([103]). 비교 프로그램에 모델을 더하는 코드가 필요하다. 조사: [로컬 후보](.scratch/mvp-roundtrip/research/2026-10-29-가벼운-로컬-임베딩-후보.md).
3. 이후 32(검 따라 하기 검수) → 35 → 36·37. 34(홀드아웃)는 나중에 해도 된다([103]).

## 지금 상태와 검증

- 티켓 31·40 닫음(`Status: resolved`). 검색 방식: text-embedding-3-large · 원문만 · BM25 끔 · 상위 6개([102]).
- 도우미 창은 진짜 임베딩 + 가짜 답변(엔진 이름 `text-embedding-3-large+stand_in`).
- pytest **516 passed**(2026-10-29, 이 브랜치 마지막 코드 커밋 `99fe35b` 기준, 강의실 PC). 연습 과정 검사 `courses: 문제 0개`.
- 실제 확인: 엔진 준비 2.7초, "베벨 어떻게 해요?" 검색 0.20초, "의자 오리진을 바닥으로 내리는 법?" 0.54초(Set Origin 쪽을 못 찾음, 티켓 40 W1과 같은 약점). 도우미 창을 직접 띄워 보지는 않았다(코드로 엔진을 불러 확인).

## 모르면 실수할 것

- **유료**: 도우미 창 질문마다 임베딩 약 $0.000005. `manual_vectors build`(약 $0.13), 검색 비교 `run`, 답변 모델은 돌리기 전 어림 비용을 보이고 확인받는다. pytest는 무료(가짜).
- 도우미 창은 OpenAI 키(환경 변수 `OPENAI_API_KEY` 또는 `data/.env`)가 있어야 답한다. 없으면 키 없음 문구.
- 청크 파일(`data/chunks/manual_chunks.jsonl`)을 다시 만들면 설명서 벡터가 맞지 않아 도우미가 멈춘다 → `manual_vectors build --yes`로 다시 만든다(옛 파일은 `archive/`로 옮긴 뒤, 있으면 멈춤).
- 평가 프로그램은 `--no-bm25`가 없어지고 `--bm25`(켤 때만)로 바뀌었다. 진짜 임베딩은 `--embedding text-embedding-3-large`.
- 검토 결과는 한 항목씩 사용자 판단(AGENTS.md). 하위 에이전트 검토(`code-review`)·Codex 검토는 사용량 때문에 쓰지 않기로 했다 — Claude가 직접 보고 판단을 받는다.
- 사용자는 Blender 기능을 깊이 모른다. 청크 정답 여부 같은 판단은 Claude가 근거와 권하는 답을 낸다.
- 강사님에게 물을 것: GPT 비교에서 연습 과정 정보를 GPT에 주지 않는 조건이 괜찮은지.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 드라이브로 옮기거나 `python -m blender_tutor.manual_vectors build --yes`(약 $0.13, 1분) |
| 연습 과정 벡터 | `data/vectors/courses_text-embedding-3-large.npz` | 없으면 도우미가 켤 때 자동으로 만든다 |
| 검색 비교 질문·묶음·DB | `data/search_compare/` | **아직 드라이브 백업 전**. 다른 PC로 가기 전에 백업 |
| 검색 비교 결과 | `results/20261029_search_compare/` (요약표는 `docs/실험결과/`에 커밋) | 원본은 백업 대상 |
| BGE-M3 모델 | `C:\Users\201\.cache\huggingface\hub\models--BAAI--bge-m3` | 비교 프로그램에만 필요(`pip install -e ".[dev,compare]"`) |

## 추천 스킬과 참고

- 33번은 `implement` 스킬(계획 → 구현 → 검수). 스킬 없이: 33번 티켓 Comments를 읽고 답변 모델 연결 코드를 가짜로 시험한 뒤, 어림 비용을 보이고 확인받아 실측한다.
- [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md), [31번](.scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md), [40번](.scratch/mvp-roundtrip/issues/40-소규모-검색-비교.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [102]-[109]](HISTORY.md), PR #28.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
