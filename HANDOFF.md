# 인수인계

마지막 갱신: 2026-11-03 · Claude Code(Opus 5.5) · 강의실 PC · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. 이어받을 때 PR #39가 병합됐는지 git으로 먼저 본다.

## 다음 할 일

1. **티켓 35 이어서: 고치기 전 기준 [E1b] 채점 확정 → 고치기 반복.** `docs/experiment.md`를 먼저 읽는다(체크리스트·[E1]·[E1b]).
   - [E1b] 채점이 "미완"이면: 새 하위 에이전트에게 `docs/experiment.md` 체크리스트대로 `results/20261103/172801_dev30_before_fixed_scenes/답.jsonl` 34차례를 채점시킨다(문항 `data/eval/dev30/questions.json`, 상태 `data/eval/dev30/states/`, 연습 과정 `courses/`, 청크 `data/chunks/manual_chunks.jsonl`). [E1] 오답노트는 주지 않는다(독립 채점). 결과를 [E1] 메인 채점과 견줘 다른 것만 사용자에게 보이고 판단을 받는다.
   - 그다음 고치기, 하나씩 고치고 다시 잰다(차례 34개 약 $0.022, 돌리기 전 확인). 권한 순서: ① D05 연습 과정 '모서리 깎기' 자주 막히는 곳에 "방향마다 다르게 깎이면 앞 단계 크기 확정을 안 한 것"(검·방패) ② N2·N5 연습 과정 권하기 지시문(`answer_engine.py` SIMILAR_NOTE와 INSTRUCTIONS의 "가장 가까운 내용" 줄이 부딪침) ③ D03 엔진: 쪽 안 공통 소제목(Common Options)을 함께 넘기기 ④ B2는 설명서에 순서가 있는지 먼저 확인.
   - 같은 문항을 다시 돌려도 결과가 흔들린다([E1] 적중 25 → [E1b] 27, N5는 권함이 바뀜). 고친 문항만 3번씩 돌리는 등 다루는 법을 사용자와 정한다.
   - 사용자가 직접 할 것: GPT 빈손 [E0], 도우미 창 시간 10문항(후보 D01·D06·D07·M1·B1·T2 + S2·S3 차례 4개). 안내 파일이 필요하면 만들어 준다고 말해 둠.
2. (집 PC, Claude 데스크톱 앱) 컴퓨터 유즈로 Blender·도우미 창 다뤄 보기. 지난 HANDOFF 1번 그대로(시나리오 ①-⑤는 HISTORY [157]·[158] 참고). 이번 세션은 CLI라 못 함. agent-desktop 실제 입력이 최근 조작 기록에 남는 것은 [158]에서 확인됨.
3. 티켓 37(홀드아웃). 45(화면 위치 표)는 35의 고치기 후보.
4. 낮은 우선순위: Win+E로 도우미 창이 튀어나옴(원인 미조사). 42(집 PC 로컬 트랙). pstack 실험(티켓을 모두 끝낸 뒤, [156]).

## 지금 상태와 검증

- 이번 PR: 기록 문서(`docs/experiment.md` 새로, HISTORY [158]·[159], 티켓 35 Comments, HANDOFF)만. 프로그램 코드는 바꾸지 않아 pytest·course_check는 다시 돌리지 않았다(직전 PR #36 기준 596 passed, 문제 0개).
- 유료 실행 두 번(사용자 확인 뒤): `evaluate run data/eval/dev30/questions.json --yes` → [E1] `results/20261103/171030_dev30_before`(답변 모델 $0.0124), [E1b] `results/20261103/172801_dev30_before_fixed_scenes`($0.0122). 질문 바꾸기·임베딩은 따로(어림 합계 각 약 $0.022).
- [E1]은 장면 실수(합친 검의 빈 재질 칸을 스크립트가 지움)가 있어 기준으로 쓰지 않는다. 장면 4개를 고쳐 [E1b]를 다시 쟀다.

## 모르면 실수할 것

- **개발 문항은 Git 밖**: `data/eval/dev30/`(문항·장면 `.blend`·상태 JSON/PNG·스크립트 `build_scenes.py`·`capture.py`·`make_questions.py`). 질문을 고치면 `문항초안.md`를 고치고 `make_questions.py`로 `questions.json`을 다시 만든다. 장면을 고치면 `build_scenes.py` → `capture.py`(장면마다 화면 있는 Blender가 떴다 꺼짐, 머티리얼 미리보기 장면은 `slow`).
- **장면은 연습 과정대로 실제와 같아야 한다**(체크리스트). 스크립트가 손으로는 안 생기는 정리를 하면 채점이 틀린다.
- **D01·T2 상태는 agent-desktop 실제 입력**으로 찍었다(`capture.py -- <이름> wait` 뒤 입력, `<이름>.go` 파일로 저장). 실제 입력 중에는 PC 마우스·키보드를 쓰면 안 된다.
- **홀드아웃 열지 않기**: `data/holdout/`·`data/holdout_work/`는 37에서 코드를 동결하기 전까지 열지 않는다(해시는 HISTORY [155]).
- **유료**: `evaluate run`은 `--yes` 없이 어림 비용만 보이고 멈춘다. 도우미 창 질문마다 약 $0.0006.
- API 키는 `data/.env`. 도우미는 켜질 때만 읽어, 바꾼 뒤 Blender를 모두 닫았다 켠다.
- 검토 결과는 한 항목씩 글로 보인다(AGENTS.md). 사용자가 방식을 바꾸면 그 말을 따른다.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

2026-11-03에 사용자가 `data/models/`·`data/hf_cache/`를 뺀 전부를 구글 드라이브 `개인 프로젝트/블렌더_RAG/data`·`results`에 올림(Claude가 대표 파일 크기로 대조, 하위 파일 수는 다 세지 않음). 다른 PC에서는 거기서 받아 같은 위치에 둔다.

| 자료 | 위치 | 비고 |
|---|---|---|
| API 키 | `data/.env` | 드라이브에도 있음 |
| 개발 30문항·장면·상태 | `data/eval/dev30/` | 티켓 35 |
| 홀드아웃 봉인 | `data/holdout/`(49파일), `data/holdout_work/` | 열지 않기 |
| 검·방패 검수 자료 | `data/review/`, `data/holdout_raw/`, `data/snapshots/` | |
| 설명서 벡터·연습 과정 벡터 | `data/vectors/` | 벡터는 `manual_vectors build --yes`(약 $0.13)로도 다시 만듦 |
| 메뉴 이름 사전 | `data/menu_names/menu_names.json` | 11-02 판 |
| 결과 원본 | `results/20261029/`-`20261103/` | 숫자는 HISTORY·`docs/experiment.md` |
| 로컬 임베딩 모델 | `data/models/`, `data/hf_cache/` | 드라이브에 없음, 지금 안 씀, 다시 내려받을 수 있음 |

## 추천 스킬과 참고

- 35 고치기는 고치기마다 `/implement`가 맞지만, 평가(유료)와 채점이 끼어 있어 티켓 35 Comments와 `docs/experiment.md`를 먼저 읽는다. 스킬 없이: 고치기 하나 → `evaluate run --name <이름>`(어림 보고 확인 뒤 `--yes`) → 하위 에이전트 채점 → `docs/experiment.md`에 [E번호].
- [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [티켓 37](.scratch/mvp-roundtrip/issues/37-유료-홀드아웃-실행.md), [실험 기록](docs/experiment.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [157]-[159]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
