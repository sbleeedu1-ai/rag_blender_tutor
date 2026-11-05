# 인수인계

마지막 갱신: 2026-11-05 점심 전 · Claude Code(Opus 5.5) · PC DESKTOP-J9LV5HK(강의실) · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. PR #40(`chore/tidy-menu-json`)도 병합 전. 이어받을 때 두 PR이 병합됐는지 git으로 먼저 본다.

## 지금 돌아가는 일과 사용자 복귀 전 범위

- **사용자는 점심과 수업으로 2026-11-05 17시까지 자리에 없다. 크래시 창의 Close를 눌러 줄 수 없다.** 진행 중 하위 에이전트(같은 세션, Opus high)에 시간 제한과 자기 프로세스만 끄기, 같은 지점 3번 연속이면 건너뛰기를 지시함.
- 이 세션이 복귀 전까지 할 일(비용 없음): ① 3차 조사 결과 받기 → 개수 대조(14:20 끝남, 표 줄 수·칸 11,449개 일치. 앞에서 쓴 11,226개보다 많은 것은 번들 애드온을 켠 분) ② 새 Opus high 하위 에이전트로 전체 칸·읽기 함수·조작 1차 분류(14:25 시작, 결과 `results/20261105/<시각>_bpy_classify/`, `.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류.md`) ③ 표본 대조 ④ [E2] 실패 원인과 맞춘 후보 표 초안. ⑤ 결과를 문서로 남기고 커밋·푸시.
- 복귀 때 알릴 것: 3차 조사 중 `data/eval/dev50/scenes/base/`에 캐시 폴더 2개(`blendcache_untitled`, `cache_fluid_4b85f272`)가 생겼다(Git 밖, 삭제는 확인 뒤). 장면 파일 `untitled.blend`는 11-04 그대로다. 2차 조사가 도우미 프로그램을 2번 띄운 부작용도 있었다(11:59, 12:06, 기록상 질문 처리 없음).
- **복귀 전에 하지 않는 것**: 칸 확정, 애드온·프로그램 코드 수정, 돈이 드는 호출, PR 병합, 사용자 설정 변경. 판단이 필요한 것은 모아 두었다가 복귀 후 묻는다.
- 세부 판단은 [티켓 35 Comments 2026-11-05](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md)에 있다. 컴팩트 뒤 먼저 읽는다.

## 다음 할 일

1. **작업 상태 칸 보강을 위한 `bpy` 조사를 끝내고 칸을 고른다.** 순서(사용자와 정함):
   1. 전체 분석: 끝남. `.scratch/mvp-roundtrip/research/2026-11-05-bpy-전체-분석-2.md`, `results/20261105/135703_bpy_dump2/`. 화면 지도(패널·메뉴 → 칸·조작), 값 못 본 타입 채우기, 부모·자식 연결, 조작·함수의 읽기 쓰임.
   2. 칸 고르기: 전체 칸 11,449개와 읽기 함수·조작을 **실패 원인을 넘기지 않은 새 하위 에이전트**가 1차로 나누고 뺀 이유를 남긴다 → Claude가 표본 대조 → 메인 세션이 [E2] 실패 원인과 맞춰 후보 표 → 사용자가 고른다.
   3. 고른 칸만 실제 환경에서 확인: 마우스 위치별 F10, 여러 창·사분할·전체 화면, 사용자 설정(임시 설정 폴더), 큰 모델, 조각 직후. `event_simulate`로 상당수 자동 시험 가능.
   4. 구현: 애드온 `read_state`(확인한 칸 목록만 읽음), `work_state.py`(평소와 다를 때만 넘길지 판별), 질문 바꾸기로 넘기기. 티켓을 나눌지 정한다.
   5. 검색을 다시 재고 부작용을 본다.
2. 나머지 고칠 후보를 정한다. 표는 HISTORY [173] 앞의 설명과 `docs/experiment.md`. 권한 순서: 칸 보강 → 청크 쪽 한 번에(옵션 떼어 내기, 분야·묶음 이름, 같은 글 합치기, 벡터 다시 만들기 약 $0.13) → 지시문(사족 줄이기, 연습 과정 목록) → 마지막 조정(3개 합치기, 칸 12-16개). 뺀 것: 검색어 짧게(가설 6), 번역 합치기(가설 7). 보류: `low`(첫 글자 2초 목표를 바꿀 때만), 더 큰 모델(이름 선택, 안 잼).
3. 고친 뒤 개발셋을 2-3번 돌려 **약 5개 넘게** 나아지는지 본다(지금 방식 범위 38-46개, 1-2개라던 옛 기준은 틀림). 받은 청크 수는 같은 때 함께 돌린 값끼리 견주고 문항별 변화도 본다. 답까지 재는 측정은 다 고친 뒤.
4. 홀드아웃 "이겼다" 기준을 새 홀드아웃을 보기 전에 다시 적는다(옛 기준 HISTORY [155]).
5. PR #39 → #40 병합(사용자 확인 뒤, 병합은 훅이 막음 → 사용자가 직접). HISTORY 끝에서 충돌 한 번([161]은 #40).
6. 사용자가 직접 할 것: 아래 표의 11-04·11-05 자료를 구글 드라이브에 올리기(아직 안 올림), 새 셋으로 GPT 빈손 [E0]·도우미 창 시간 10문항.
7. 그 밖(뒤로): 컴퓨터 유즈 시나리오(HISTORY [157]·[158]), 티켓 37·45, Win+E로 도우미 창이 튀어나옴, 42, pstack, 연습 과정 글 고치기(HISTORY [164]).

## 지금 상태와 검증

- 오늘 한 것(모두 PR #39 브랜치): 검색 가설 4·5·6·7·8 측정과 결론(`docs/experiment.md`, HISTORY [168]-[172]), `experiment.md`의 "차례"를 문항·질문으로 고침, `bpy` 조사 두 번과 공식 문서 대조(HISTORY [173]). 프로그램 코드는 바꾸지 않아 pytest를 다시 돌리지 않았다(PR #36 기준 596 passed).
- 공식 문서 대조: `objects.inv`(5.2.4 RC)를 Claude가 따로 받아 조사 자료와 맞춤. 조작 2,497 전부 있음, 타입 1,789 전부 있음(RNA 밖 9개는 RNA 아닌 이름 목록), 타입 안 이름 17,237 중 없음 2개(`Context.texture_slot`, `Operator.bl_property`).
- 뒤집힌 면 세기 오류와 편집 모드의 낡은 `obj.data`는 Claude가 화면 없는 Blender로 재현함.
- 오늘 측정 비용(어림 포함): 가설 8 약 $0.075, 6 약 $0.04, 7 약 $0.02, 5 약 $0.02. 실행 전 잔액 $2.12(가설 8 전), 사용자 대조는 아직.

## 모르면 실수할 것

- **사용자 방식**: 체크리스트 같은 기준이 있는 검토 결과는 Claude가 기준대로 판단·반영하고 정말 중요한 것 2개 안팎만 보인다(메모리). 설명은 문단 단위로, "이해되세요?" 붙이지 않기. **"차례"라고 쓰지 않고 문항·질문으로 말한다.** **조사 범위를 임의로 줄이지 않는다**("초보자 범위 밖"으로 빼지 않기, 줄이려면 먼저 묻기. 사용자 "너 멋대로 곡해한게 문제지"). 하위 에이전트 지시에 기대 결과를 넣지 않는다.
- **`bpy` 쓰임**: 애드온은 읽기만 한다. `bpy.ops`와 `new`·`remove`는 부르지 않는다. 값을 자동으로 전부 훑으면 Blender가 죽을 수 있다(`is_overridable`, 평가본 `NodeLink.is_hidden` 등) → 확인한 칸 목록만 읽는다. 편집 모드 메시는 `bmesh.from_edit_mesh`로 읽고, 뒤집힌 면 계산은 복사본에서 한다(원본에 하면 사용자 메시가 고쳐짐). 뒤집힌 면 세기는 평평한 메시에서 틀린다. 공식 문서(`docs.blender.org/api/5.2`)는 도우미 검색 자료가 아니라 개발 참고용이다(명세가 뺌).
- **검색어는 실행마다 크게 달라진다**(같은 질문이 1위 ↔ 50위 밖). 합계만 보면 늘고 준 것이 상쇄되어 숨는다. 측정 기록(`답.jsonl`)에는 검색어가 남지 않는다 → 가설 실험 스크립트(`data/eval/dev50/search_h*.py`)가 남긴 기록을 쓴다. 정답 아는 검색어가 최선이라는 보장은 없다(Q29).
- **답 모델은 그림을 받지 않는다**(작업 상태 JSON만, `evaluate.py:303`). luna는 작업 상태를 받지 않는다. 작업 상태에 물체 회전 칸이 없다(`view.rotation`은 화면 시점). 최근 조작 칸에는 조작 이름만 남는다.
- **임베딩 글은 "쪽 제목 > 소제목 / 본문"뿐**이고 분야·묶음(경로)은 메타데이터로만 있다(`manual_vectors.py`가 `chunk.text`를 임베딩, 티켓 06 결정).
- **장면 만들기**: `data/eval/dev50/scenes.py`(창 있는 Blender, `--factory-startup --python … -- <장면>`) → `capture.py`(보통 설정으로 열어 애드온 save_snapshot). 선택은 `view3d.select_box`를 화면 좌표로(`box`·`box_world`). 스크립트 조작은 '최근 조작' 칸에 안 남는다(Q18-1 장면은 손으로 채우지 못함, `event_simulate`로 풀릴 수 있음, 안 해 봄).
- **창 있는 Blender를 끌 때마다 `%TEMP%\quit.blend`를 덮어쓴다.** 창 있는 Blender로 그림을 찍을 때 `--factory-startup`만 주면 시작 화면이 가운데를 가린다 → 장면 파일을 함께 연다. Blender 크래시 창이 뜨면 Restart 말고 Close(새 창이 쌓임).
- **디시 댓글은 회색지대**: 원인·해결로 쓰지 않는다. 하위 에이전트 지시에 "우회 금지·rm 금지"를 넣는다.
- **홀드아웃 열지 않기**: 새 `data/holdout/`·`data/holdout_work/`, 옛 `data/archive/holdout_20261103/`, 질문 모음 `data/holdout_pool/`. 개발셋 하위 에이전트에도 열지 말라고 적는다.
- **유료**: `evaluate run`은 `--yes` 없이 어림만. 실험 스크립트도 `--yes`를 받아야 돈을 쓴다. API 키는 `data/.env`.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

11-03까지의 자료는 구글 드라이브 `개인 프로젝트/블렌더_RAG/data`·`results`에 있음. **11-04·11-05에 만든 아래 자료는 아직 안 올림. 다른 PC에서 이어 가려면 먼저 올린다.**

| 자료 | 위치 | 비고 |
|---|---|---|
| 새 개발셋 | `data/eval/dev50/` | 문항초안.md, questions.json, scenes/·states/, 검색 실험 스크립트 search_h1·h1b·h2·h2_pairs·h3·h4_q19·h4_chunk·h5·h6·h7·h8.py, extra_state.py·extra/, verify/, 후보_본문.md(남의 글 발췌) |
| 새 홀드아웃 봉인·작업 자료 | `data/holdout/`(57파일), `data/holdout_work/` | 열지 않기 |
| 옛 홀드아웃 | `data/archive/holdout_20261103/` | 열지 않기 |
| 홀드아웃용 질문 모음 | `data/holdout_pool/use_holdout.json` | 개발셋 글 51개를 뺀 1,115개 |
| 질문 조사 원자료 | `data/research_raw/20261104_질문모음/` | |
| 결과 11-04 | `results/20261104/` | 145409_dev50_before, 160743_search_h1, 161724_search_h1b, search_h2_log.txt, search_h2_pairs_log.txt, 165335_search_h3 |
| 결과 11-05 | `results/20261105/` | 092459_search_h4_q19, 095146_search_h4_chunk, 100827_search_h5, 102254_search_h8, 103759_search_h6, 105605_search_h7, 120433_bpy_dump(약 155MB), 135703_bpy_dump2(약 430MB), `*_bpy_classify`(진행 중) |
| 프로토타입 개발셋 | `data/eval/dev30/` | 기록은 `archive/experiment_prototype.md` |
| API 키·벡터·모델 | `data/.env`, `data/vectors/`, `data/models/` | 앞과 같음 |

## 참고

- [실험 기록·체크리스트](docs/experiment.md)(목차), [`bpy` 전체 분석](.scratch/mvp-roundtrip/research/2026-11-05-bpy-전체-분석.md), [`bpy` 작업 상태 지도](.scratch/mvp-roundtrip/research/2026-11-05-bpy-작업상태-지도.md), [개발셋 작업표](.scratch/mvp-roundtrip/dev50-작업표.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [질문 종류 조사](.scratch/mvp-roundtrip/research/2026-11-04-블렌더-질문-종류.md), [경과 [168]-[173]](HISTORY.md), [구조](STRUCTURE.md).
- 검색 흐름 코드: `blender_tutor/answer_engine.py`(`REWRITE_PROMPT`, `answer`, `_rewritten`, `search`, `_widened`), `engine_setup.py`. 공식 API 문서: `https://docs.blender.org/api/5.2/`.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
