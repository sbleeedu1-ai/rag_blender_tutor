# 인수인계

마지막 갱신: 2026-10-29 · Codex · 강의실 PC · PR #29 병합 전에 씀(브랜치 `feat/local-embedding-compare` → main, 구현 커밋 `a056349`). PR #28은 main에 병합됨(`39f42d1`). PR #29는 작성했으며 아직 병합하지 않았다. 이어받을 때 PR #29 병합 여부를 먼저 확인한다.

## 다음 할 일

1. **티켓 33: 실제 답변 모델을 붙이고 생각 수준 none/low 속도를 잰다.** [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md) Comments의 넘겨받은 일을 먼저 읽는다.
   - PR #29 상태와 이 브랜치의 기록을 먼저 확인한다. #29를 병합했다면 최신 main에서 새 브랜치를 만든다. 병합은 사용자 확인 뒤에만 한다.
   - 답변 모델(명세 기본 `gpt-6-luna`) 연결 코드 → 가짜로 시험 → **어림 비용을 보이고 사용자 확인** → 강의실 PC 도우미 창에서 질문 준비 0.5초 / 첫 글자 2초 / 답 끝 6초를 잰다.
   - 함께 볼 것(HISTORY [107]·[109]): 첫 질문 검색 0.54초(목표 0.5초 근처), 도우미 창을 실제로 띄워 진짜 임베딩 근거가 나오는지, 용어표를 실제 모델이 지키는지([105]), 원문만 넘겨도 한국어 답이 괜찮은지([104]).
   - 답변 모델이 진짜가 되면 엔진 만들기를 `stand_in.py` 밖으로 옮기고 `stand_in.py`는 `archive/`로(파일 첫머리 주석).
2. 로컬 임베딩 후보 3개 측정은 끝났다(티켓 41, HISTORY [111]). 결과는 [요약](docs/실험결과/20261029_local_embedding_요약.md). Codex는 EmbeddingGemma를 다음 확인 후보로 권했으나 사용자 선택·도우미 연결은 아직이다. 상위 6개 적중률: granite 50%, e5 35%, EmbeddingGemma 70%, 기존 OpenAI 67.5%. 작은 평가 자료의 결과이며, 모델 교체를 확정하거나 같은 실험을 임의로 반복하지 않는다.
3. 이후 32(검 따라 하기 검수) → 35 → 36·37. 34(홀드아웃)는 나중에 해도 된다([103]).

## 지금 상태와 검증

- 티켓 31·40·41 닫음(`Status: resolved`). 도우미 검색 방식: text-embedding-3-large · 원문만 · BM25 끔 · 상위 6개([102]). 로컬 후보는 비교 프로그램에만 추가했다.
- 도우미 창은 진짜 임베딩 + 가짜 답변(엔진 이름 `text-embedding-3-large+stand_in`).
- pytest **522 passed**(2026-10-29, 구현 커밋 `a056349`의 코드, 강의실 PC). 연습 과정 검사 `courses: 문제 0개`. 검수에서 수정할 문제는 발견하지 못했다. 새 화면·Blender·Windows 모사 시험은 없으며 STRUCTURE에 새 파일·주고받는 형식을 반영했다.
- 실제 확인: 엔진 준비 2.7초, "베벨 어떻게 해요?" 검색 0.20초, "의자 오리진을 바닥으로 내리는 법?" 0.54초(Set Origin 쪽을 못 찾음, 티켓 40 W1과 같은 약점). 도우미 창을 직접 띄워 보지는 않았다(코드로 엔진을 불러 확인).
- 로컬 실측(Blender 기본 장면·조작/렌더링 없이 대기): 검색 중앙값 granite 0.037초·e5 0.032초·EmbeddingGemma 0.151초, 모델마다 60표본 전부 보존. 라이브러리 포함 불러오기 10.9-13.1초. granite 최초 실행은 사용자 조작이 겹쳐 모든 시간을 비교에서 제외하고 재측정했으므로, 유효한 설치 직후 첫 불러오기 값은 없다. e5는 문서 200개 중 9개에서 512토큰을 넘었다. 기존 기준선은 같은 PC의 별도 실행이며 BGE-M3 불러오기에는 라이브러리 import가 빠져 직접 비교하면 안 된다. ONNX·양자화·설명서 전체 검증은 미실행.

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
| 새 로컬 후보 3개 | `data/models/<모델>/<버전>/`(약 1.98GB, 버전·다운로드 기록 포함) | 백업 전. `python -m blender_tutor.local_embeddings prepare --model <이름>`으로 다시 받을 수 있다. EmbeddingGemma는 해당 PC에서 약관 동의한 계정으로 인증 필요. 인증 파일은 공유하지 않는다 |
| 로컬 측정 원본·통합 비교표 | `results/20261029_local_*` | 백업 전. 핵심 요약만 `docs/실험결과/20261029_local_embedding_요약.md`에 커밋. 원본 제외 사유·300행 자료 검증·코드 해시는 `results/20261029_local_embedding_report/` |

## 추천 스킬과 참고

- 33번은 `implement` 스킬(계획 → 구현 → 검수). 스킬 없이: 33번 티켓 Comments를 읽고 답변 모델 연결 코드를 가짜로 시험한 뒤, 어림 비용을 보이고 확인받아 실측한다.
- [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md), [31번](.scratch/mvp-roundtrip/issues/31-유료-번역과-임베딩.md), [40번](.scratch/mvp-roundtrip/issues/40-소규모-검색-비교.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [102]-[109]](HISTORY.md), PR #28.
- 로컬 비교: [41번](.scratch/mvp-roundtrip/issues/41-가벼운-로컬-임베딩-비교.md), [결과 요약](docs/실험결과/20261029_local_embedding_요약.md), HISTORY [111], [PR #29](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/29). 구현·결과·구조 문서를 작업 브랜치에 푸시했다. main 병합은 사용자 승인 전이다.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
