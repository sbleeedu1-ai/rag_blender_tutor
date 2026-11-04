# 인수인계

마지막 갱신: 2026-11-04 수업 끝 · Claude Code(Opus 5.5) · PC DESKTOP-J9LV5HK(강의실) · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. PR #40(`chore/tidy-menu-json`)도 병합 전. 이어받을 때 두 PR이 병합됐는지 git으로 먼저 본다.

## 다음 할 일

1. **티켓 35 고치기 1번 "검색 보강": 검색 가설 4(기능 이름을 잘못 고름)를 마저 보고 가설 5(8개가 모자람)로 간다.** 가설 1·2·3은 끝났고 결론은 [`docs/experiment.md`](docs/experiment.md) 목차.
   - 가설 4 지금까지(비용 없이 기록만 봄, experiment.md에는 아직 안 씀, HISTORY [167]): 원인형이 아닌 7차례 Q16·Q17·Q19·Q29·Q30·Q43·Q44. 정답을 아는 검색어로는 5차례가 1-6위(Q29 30위·Q44 37위는 이름이 맞아도 낮음 → 따로 봄). luna는 세 벌 모두 같은 쪽으로 틀림: 방법이 여럿(Q16 Spin·Bevel, Q17 토폴로지·Knife, Q44 Geometry Nodes), 증상을 엉뚱한 곳 탓으로(Q19 기즈모, Q30 색 관리, Q43 변위 노드), 번역 함정(Q29 "칼날" → Knife).
   - Q16은 luna가 연습 과정 목록을 몰라서 "가장 가까운 과정의 다음 조작"을 못 찾은 경우로 봄(추정) → 고칠 후보: 질문 바꾸기에 연습 과정 목록을 넘기기.
   - 다음에 잴 것(Claude 권함, 사용자 확인 전): 남은 6차례를 더 큰 모델로 질문 바꾸기만 3번씩 → luna 힘 문제인지 지시문·맥락 문제인지 가름. 모델은 엔진 설정(`engine_setup.py`)을 보고 정한 뒤 비용 어림을 보이고 확인받는다.
   - 가설 5 자료: `results/20261104/160743_search_h1/기록.jsonl`의 '지금' 순위(50위까지). 하나도 못 받은 20차례 중 필요 청크가 9-50위인 차례 12개(Q03 12, Q04-1 12, Q07 10, Q09 10, Q18-2 10, Q29 12, Q30 22, Q31 9, Q37 9·42, Q43 41, Q44 30, Q45 26).
   - 가설을 하나씩: 세우기 → 무엇으로 확인하나 → 재기 → 확인한 것과 추정을 가른 요약 → 사용자와 결론 → `experiment.md`에 남기기. **한 번 잰 것을 결론처럼 말하지 않는다**, 가설을 묶지 않는다, **순서를 바꿀 때는 먼저 묻는다**(사용자 지적).
2. 검색 가설을 다 본 뒤 고칠 것을 한꺼번에 정한다. 지금까지의 후보: ① **작업 상태 칸 보강**(티켓 35 Comments 2026-11-04). 가설 3에서 원인이 드러나는 칸 이름·값이면 luna가 원인 검색어를 붙임(10 → 22 / 45). 회전 숫자는 해석 못 함 → 그런 칸은 코드 규칙(예: 회전이 0이 아니면 apply rotation)과 luna를 견줌. 칸 후보 값 읽기는 `data/eval/dev50/extra_state.py`. 원인과 상관없는 문항에서의 부작용은 아직 안 잼 ⑤ 질문 바꾸기에 연습 과정 목록 넘기기(가설 4 Q16) ② 완전히 같은 글 청크만 하나로 ③ 임베딩 글에 분야·묶음 이름 붙이기(벡터 다시 만들기 약 $0.13) ④ "설명서에 없어요" 사족 줄이기(지시문, [E2]에서 13차례). 고친 뒤에는 개발셋 전체를 **2-3번** 돌려 흔들림(1-2개)보다 큰지 본다.
3. 홀드아웃 "이겼다" 기준을 새 홀드아웃을 보기 전에 다시 적는다(옛 기준 HISTORY [155]).
4. PR #39 → #40 병합(사용자 확인 뒤, 병합은 훅이 막음 → 사용자가 직접). #40에 더하려던 `dev30` 이름 바꾸기·옛 홀드아웃 옮기기는 `data/` 안이라 Git 변경 없음(옛 홀드아웃은 이미 옮김). HISTORY 끝에서 충돌 한 번([161]은 #40).
5. 사용자가 직접 할 것: `data/research_raw/20261104_질문모음/`·`data/eval/dev50/`·새 `data/holdout/`·`data/holdout_work/`·`data/archive/`를 구글 드라이브에 올리기(아직 안 올림), 새 셋으로 GPT 빈손 [E0]·도우미 창 시간 10문항.
6. 그 밖(뒤로): 컴퓨터 유즈 시나리오(HISTORY [157]·[158]), 티켓 37·45, Win+E로 도우미 창이 튀어나옴, 42, pstack, 연습 과정 글 고치기(합치면 배율이 고르게 남아 "크기 확정 안 하면 방향마다 다르게 깎임"이 실제와 다름, HISTORY [164]).

## 지금 상태와 검증

- 오늘 한 것(모두 PR #39 브랜치, 원격과 같음): 새 개발 50문항·54차례와 장면 38개(HISTORY [164]), 새 홀드아웃 22문항 봉인(해시 `f92eea7d…56a2`, [165]), 고치기 전 [E2] 측정(맞음 19 / 부분 19 / 틀림 16, 엄격한 검색 적중 24 / 49, 약 $0.033), 검색 가설 1·2 실험(합쳐 약 $0.05), 가설 3 실험(약 $0.015), Q16 문항 고침(질문 "둥근 판", 핵심에 가장자리 얇게·Spin 대안, `questions.json` 다시 만듦·바뀐 문항 Q16 하나, HISTORY [167]). 프로그램 코드는 바꾸지 않아 pytest를 다시 돌리지 않았다(PR #36 기준 596 passed).
- `questions.json`은 `evaluate run`을 `--yes` 없이 돌려 어림 $0.03456에서 멈추는 것까지 확인. 장면은 창 있는 Blender로 만들고 그림 38장을 눈으로 대조.

## 모르면 실수할 것

- **사용자 방식**: 체크리스트 같은 기준이 있는 검토 결과는 Claude가 기준대로 판단·반영하고 정말 중요한 것 2개 안팎만 보인다(메모리). 설명은 문단 단위로, "이해되세요?" 붙이지 않기.
- **검색어는 실행마다 달라진다**(지금 방식만 두 번 돌려도 받은 청크 41 ↔ 42). 측정 기록(`답.jsonl`)에는 검색어가 남지 않는다 → 가설 실험 스크립트(`data/eval/dev50/search_h1.py` 등)가 남긴 기록을 쓴다.
- **답 모델은 그림을 받지 않는다**(작업 상태 JSON만, `evaluate.py:303`). 작업 상태에 물체 회전 칸이 없다(`view.rotation`은 화면 시점). 최근 조작 칸에는 조작 이름만 남는다.
- **임베딩 글은 "쪽 제목 > 소제목 / 본문"뿐**이고 분야·묶음(경로)은 메타데이터로만 있다(`manual_vectors.py`가 `chunk.text`를 임베딩, 티켓 06 결정). 쪽 제목이 같은 짝은 임베딩이 못 가른다.
- **장면 만들기**: `data/eval/dev50/scenes.py`(창 있는 Blender, `--factory-startup --python … -- <장면>`) → `capture.py`(보통 설정으로 열어 애드온 save_snapshot). 선택은 `view3d.select_box`를 화면 좌표로(`box`·`box_world`). `transform.rotate` 값은 화면에서 치는 R X 90과 부호가 반대. 연습 과정대로 합치기는 A → Ctrl + J(활성은 마지막에 더한 부품). 렌더 보기는 파일을 열면 솔리드로 돌아와 `capture.py … rendered`로 찍는다. 스크립트 조작은 '최근 조작' 칸에 안 남는다(Q18-1 장면은 손으로 채우지 못함, 다음 전체 재기 때 고침).
- **창 있는 Blender를 끌 때마다 `%TEMP%\quit.blend`를 덮어쓴다.**
- 창 있는 Blender로 그림을 찍을 때 `--factory-startup`만 주면 시작 화면이 가운데를 가린다 → 장면 파일(예: `data/eval/dev50/scenes/base/untitled.blend`)을 함께 열어 시작한다. 실험 스크립트(`search_h1b.py` 등)는 맨 끝에서 바로 실행되므로 다른 스크립트에서 불러 쓰지 말고 옮겨 적는다.
- **디시 댓글은 회색지대**: 원인·해결로 쓰지 않는다. 하위 에이전트 지시에 "우회 금지·rm 금지"를 넣는다.
- **홀드아웃 열지 않기**: 새 `data/holdout/`·`data/holdout_work/`, 옛 `data/archive/holdout_20261103/`, 질문 모음 `data/holdout_pool/`. 개발셋 하위 에이전트에도 열지 말라고 적는다.
- **유료**: `evaluate run`은 `--yes` 없이 어림만. 실험 스크립트도 `--yes`를 받아야 돈을 쓴다. API 키는 `data/.env`.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

11-03까지의 자료는 구글 드라이브 `개인 프로젝트/블렌더_RAG/data`·`results`에 있음. **11-04에 만든 아래 자료는 아직 안 올림.**

| 자료 | 위치 | 비고 |
|---|---|---|
| 새 개발셋 | `data/eval/dev50/` | 문항초안.md, questions.json, scenes/·states/, scenes.py·capture.py·make_questions.py, 확인결과.md, verify/, 검색 실험 스크립트 search_h1·h1b·h2·h2_pairs·h3.py, 상태 칸 후보 읽기 extra_state.py·extra/, Q16 비교 verify/q16_methods.py·q16_beginner.py·verify/q16/(그림), 후보_본문.md(남의 글 발췌) |
| 새 홀드아웃 봉인·작업 자료 | `data/holdout/`(57파일), `data/holdout_work/` | 열지 않기 |
| 옛 홀드아웃 | `data/archive/holdout_20261103/` | 열지 않기 |
| 홀드아웃용 질문 모음 | `data/holdout_pool/use_holdout.json` | 개발셋 글 51개를 뺀 1,115개 |
| 질문 조사 원자료 | `data/research_raw/20261104_질문모음/` | |
| 결과 | `results/20261104/145409_dev50_before/`(측정·채점), `160743_search_h1/`, `161724_search_h1b/`, `search_h2_log.txt`, `search_h2_pairs_log.txt`, `165335_search_h3/` | |
| 프로토타입 개발셋 | `data/eval/dev30/` | 기록은 `archive/experiment_prototype.md` |
| API 키·벡터·모델 | `data/.env`, `data/vectors/`, `data/models/` | 앞과 같음 |

## 참고

- [실험 기록·체크리스트](docs/experiment.md)(목차), [개발셋 작업표](.scratch/mvp-roundtrip/dev50-작업표.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [질문 종류 조사](.scratch/mvp-roundtrip/research/2026-11-04-블렌더-질문-종류.md), [프로토타입 기록](archive/experiment_prototype.md), [경과 [160]-[166]](HISTORY.md), [구조](STRUCTURE.md).
- 검색 흐름 코드: `blender_tutor/answer_engine.py`(`REWRITE_PROMPT`, `answer`, `search`, `_widened`), `engine_setup.py`.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
