# 인수인계

마지막 갱신: 2026-10-30 · Claude Code(Opus 5.5) · 강의실 PC · PR #29 병합 전에 씀(브랜치 `feat/local-embedding-compare`). 사용자가 병합을 승인했다("ㄱㄱ", HISTORY [124]·[126]). [112]의 "병합하지 않고 보존"은 [124]에서 바뀌었다. 이어받을 때 PR #29가 main에 병합됐는지 git으로 먼저 본다.

## 다음 할 일

1. **티켓 43: 도우미 검색을 새 흐름으로 바꾸고 2초 안에 드는 방법을 찾는다.** [43번](.scratch/mvp-roundtrip/issues/43-도우미-검색을-새-흐름으로.md). main에서 새 브랜치로 시작한다.
   - 정한 흐름: 질문 → luna(none) 질문 바꾸기 3번 동시 → large 임베딩 → 설명서 전체 뜻 검색(BM25 끔) → RRF 합쳐 **상위 8개**. 메뉴 이름 덧붙이기는 뺀다.
   - 먼저 2초 안 후보(짧은 지시, 연결 다시 쓰기, 더 작은 모델)를 20문항으로 잰다. 지금 중앙 2.53초·최대 5.95초, 86%가 luna([122]).
2. 티켓 33: 실제 답변 모델을 붙이고 생각 수준 none/low 속도를 잰다. [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md) Comments 먼저.
3. 티켓 42(집 PC): 고사양 로컬 트랙 측정 계획. [42번](.scratch/mvp-roundtrip/issues/42-집-PC-고사양-로컬-트랙-측정.md). 집 PC에서만.
4. 이후 32 → 35 → 36·37. 34(홀드아웃)는 자유 질문 목표에 맞게 분야를 넓혀 쓴다([118]).

## 지금 상태와 검증

- 도우미는 아직 옛 흐름이다: 질문 + 메뉴 이름 덧붙이기 → large → 상위 6개. 가짜 답변(`text-embedding-3-large+stand_in`).
- 검색 결론(설명서 전체 8,997청크, 20문항): 한국어 그대로 상위 8개 22.5% → luna 번역만 47.5% → luna 질문 바꾸기 85% → 3번 합침 87.5%([121]·[122]). 범위·분야 거르기, BM25, 메뉴 이름 덧붙이기는 효과 없거나 손해([113]-[119]). 로컬 소형 생성 모델은 강의실 PC에서 느리고 기능 이름을 못 떠올림([122]).
- pytest **538 passed**(2026-10-30, 커밋 `264773e`, 강의실 PC). 코드 검토 21건은 사용자 판단을 받아 처리([125]). 연습 과정 검사는 이번에 돌리지 않았다(연습 과정 파일을 바꾸지 않음).
- `search_compare full-pool`로 설명서 전체 묶음·DB를 다시 만들 수 있음을 실제 자료로 확인(해시 같음).

## 모르면 실수할 것

- **유료**: `search_compare rewrite`·`flow`·`run`(large)·답변 모델은 `--yes` 없이 멈춘다. 어림 비용을 보이고 사용자 확인 뒤 붙인다. 오늘 쓴 유료는 약 $0.03. pytest는 무료(가짜).
- luna 응답 시간은 시간대마다 다르다(오전 중앙 1.50초, 오후 1.86초). 비교는 같은 실행 안에서 한다.
- 도우미 창은 OpenAI 키(`OPENAI_API_KEY` 또는 `data/.env`)가 있어야 답한다.
- 청크 파일을 다시 만들면 설명서 벡터가 안 맞아 도우미가 멈춘다 → `manual_vectors build --yes`(약 $0.13), 그 뒤 `search_compare full-pool`.
- 검토 결과는 한 항목씩 사용자 판단(AGENTS.md). 이전 HANDOFF에는 "하위 에이전트 검토는 사용량 때문에 쓰지 않기로 했다"가 있었는데, 이번에 사용자 "코드 검토부터 ㅇㅇ"에 Claude가 `code-review`(하위 에이전트 2개)를 썼다. 다음에는 쓸지 먼저 묻는다.
- 사용자는 Blender 기능을 깊이 모른다. 청크 정답 여부 같은 판단은 Claude가 근거와 권하는 답을 낸다.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 옮기거나 `manual_vectors build --yes`(약 $0.13) |
| 검색 비교 질문·묶음·DB | `data/search_compare/` | **드라이브 백업 전**. 질문 파일은 손으로 만든 것이라 꼭 옮긴다. 설명서 전체 묶음과 large DB는 `search_compare full-pool`로 다시 만든다. Gemma 전체 DB는 다시 만들면 약 34분 |
| 결과 원본 | `results/20261029/`, `results/20261030/`(실험 30여 개) | 백업 전. 숫자는 HISTORY [113]-[125]에 있다 |
| 로컬 임베딩 모델 | `data/models/<모델>/<버전>/`(약 2GB) | `local_embeddings prepare`로 다시 받음. EmbeddingGemma는 약관 동의한 계정 인증 |
| 로컬 생성 모델·llama.cpp | `data/models/llm/`(약 5.3GB) | `prototype/local_llm/llm_bench.sh`가 다시 받는다 |
| BGE-M3 | `C:\Users\201\.cache\huggingface\hub\models--BAAI--bge-m3` | 비교 프로그램에만 필요 |

## 추천 스킬과 참고

- 43번은 `implement` 스킬(계획 → 구현 → 검수). 스킬 없이: 43번 티켓의 "할 일" 1번(2초 안 후보 측정)부터, 유료면 어림 비용을 보이고 확인받는다.
- [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [113]-[126]](HISTORY.md), [리서치](.scratch/mvp-roundtrip/research/2026-10-30-질문-바꾸기·HyDE·doc2query·리랭커-조사.md), [PR #29](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/29).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
