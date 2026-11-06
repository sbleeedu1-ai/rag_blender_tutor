# 인수인계

마지막 갱신: 2026-11-06 오전 · Claude Code(Opus 5.5) · 강의실 PC(DESKTOP-J9LV5HK) · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. PR #40(`chore/tidy-menu-json`)도 병합 전. 이어받을 때 두 PR이 병합됐는지 git으로 먼저 본다.

## 지금 상태 한눈에

- **돌아가는 시험·하위 에이전트 없음.** 2026-11-06 오전에 어제 판정을 다시 봄([188]-[191], `docs/experiment.md` 작업 상태 가설 4-3·5·6). **H1-2의 "미달" 결론은 철회했다**: 기준 0.8은 닿을 수 없었고(상한 0.68), 같은 작업끼리 섞어도 0.47. **측정 구멍 발견**: 값 읽기가 모음 자체의 칸 91개(활성 물체 등)를 안 읽는다. 사용자가 "3단계는 기다려봐"로 고치기를 대기시켰다.
- **목표(사용자 확인)**: "API 에서 찾아낸 값중 어떤것을 효율적으로 보내면 좋을까?". 세 묶음은 '늘 바뀌는 값' / '계산이 필요한 값' / '그 외 나머지'. 효율은 "정해진 줄 수 안에서, 필요한 값을 놓치지 않고 보내는 것". **줄 수 한도는 아직 없다**(90%·중앙 30줄은 근거가 약해 철회). 비용과 묻힘은 예상일 뿐 재지 않았다.
- 훅이 `.venv/Scripts/python.exe`로 돈다(PR #41 병합됨, [182]). `.venv`가 없는 곳에서는 터미널 명령이 막히니 직접 터미널을 열어 만든다. 강의실 PC는 `.venv`가 있고 명령이 정상으로 돈다.
- **방향이 바뀌었다(HISTORY [175]-[177]).** 칸을 상·중·하로 고르지 않는다(사용자 "애초에 이젠 등급을 빼기로 했으니"). 값이 움직이는 모양으로 나눈다: 늘 바뀌는 값·계산해야 아는 값은 매번(계산 값 보내는 규칙은 시험 뒤) / 일부러 바꿔야 바뀌는 값은 공장값과 다를 때만 / 그 외는 무엇이 있는지 파악. 범용으로 만들고 연습 과정 감지에도 쓴다. 사용자 "우리 범용적으로 쓸거 만드는거다".
- **사용자 판단 전에 하지 않는 것**: 칸 확정, 애드온·프로그램 코드 수정, 돈이 드는 호출, PR 병합, 사용자 설정 변경.

## 다음 할 일

1. **회고 정리는 끝났다(HISTORY [193]).** 다음은 2번 측정 구멍 고치기이고, 사용자 "3단계는 기다려봐"에 따라 **사용자가 말하면 시작한다.** 줄 수 한도를 어떻게 정할지, 비용과 묻힘을 소액으로 먼저 잴지도 아직 안 정했다.
2. **측정 구멍 고치기 3단계**(대기): 91칸을 시험 7의 상태들에서 읽어 안 죽는지 확인 → 시험 도구(`data/`, 애드온 아님)가 모음 칸을 읽고 긴 모음은 전체로 비교, 새 물체 값은 따로 셈 → 정답을 아는 변화(활성 물체, 활성 수정자, 51번째 뒤 점, 작업 상태 14칸)가 전부 잡히는지 점검. 기준은 전부 잡힘.
3. **범용 시험을 이어 간다.** [계획](.scratch/mvp-roundtrip/research/2026-11-05-작업상태-범용-시험-계획.md)(0절이 진행 상황). 사용자 "진행해 ㄱㄱ"(전수 실행, 기준 숫자 제안값, 설정 복사본 승인).
   1. **진행 순서(사용자가 정함)**: 가설 → 결과 보기 전에 기준 적기 → 실험 → 결과 → 이 시험의 목적 다시 보기 → 통과하면 실험 자체 점검 → 다음. `experiment-checklist` 스킬의 체크리스트를 채운다. 실패했다고 원인을 안 재고 방법만 바꿔 고르게 하지 않는다(HISTORY [185]). 있는지 확인하지 않은 자료에 기대지 않는다.
   2. **늘 바뀌는 값 다음 시험(안)**: 가설은 "몇 가지 작업에서 모은 작은 목록이 목록을 만들 때 쓰지 않은 작업에서 자주 바뀌는 값도 대부분 잡는다". 성격이 다른 작업 6개, 지표는 덮는 비율과 크기. 사람 기록을 참고해 선택(좌표 지정)과 시점 돌리기를 넣고, 흐름은 목록을 모르는 Sonnet 하위 에이전트가 쓴다. 숫자 기준은 사용자와 정한다.
   3. 남은 순서: 공장값 나머지(3) → 긴 작업(4, 목록 경계를 옮기면 줄 수가 변하나도 봄) → 늘 보이는 칸(5) → 계산 값(6) → 언제 읽나(8, 타이머 안에서는 `bpy.context`에 창이 없어 `objects_in_mode`가 없음) → 감지(9, 입력 흉내 원인도 여기서) → 규칙 고정 → 개발 문항 점검(10). 걸린 시간(집 PC): 시험 7 약 37분, 시험 2 화면 없음 19분(10개 동시) · 창 51분(8개 동시, CPU 80%), 흐름 3개 약 2분 20초. **강의실 PC는 약 1.7배 느리고**(같은 흐름 237초), 모니터가 1대라 창이 화면을 가린다. 창 8개 동시 시험은 집 PC 권함. `flow_run.py`는 창 위치를 x=0으로 고쳤고, 나머지 스크립트는 아직 x=-1920이다(옆 모니터가 있는 집 PC 기준).
   4. 결과는 `docs/experiment.md`에 앞 가설들과 같은 모양으로 남기고 [칸 후보 초안](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-후보-초안.md)을 다시 쓴다.
4. 구현: 애드온 `read_state`(시험을 통과한 범위만 읽음), `work_state.py`(공장값과 다를 때만 넘길지 판별), 질문 바꾸기로 넘기기. 0.5초 타이머와 F10 없는 질문 길을 어떻게 할지 시험 8로 정한다. 티켓을 나눌지 정한다. 그 뒤 실제 환경 확인과 검색 재기.
5. 나머지 고칠 후보를 정한다. 표는 HISTORY [173] 앞의 설명과 `docs/experiment.md`. 권한 순서: 칸 보강 → 청크 쪽 한 번에(옵션 떼어 내기, 분야·묶음 이름, 같은 글 합치기, 벡터 다시 만들기 약 $0.13) → 지시문(사족 줄이기, 연습 과정 목록) → 마지막 조정(3개 합치기, 칸 12-16개). 뺀 것: 검색어 짧게(가설 6), 번역 합치기(가설 7). 보류: `low`(첫 글자 2초 목표를 바꿀 때만), 더 큰 모델(이름 선택, 안 잼).
6. 고친 뒤 개발셋을 2-3번 돌려 **약 5개 넘게** 나아지는지 본다(지금 방식 범위 38-46개, 1-2개라던 옛 기준은 틀림). 받은 청크 수는 같은 때 함께 돌린 값끼리 견주고 문항별 변화도 본다. 답까지 재는 측정은 다 고친 뒤.
7. 홀드아웃 "이겼다" 기준을 새 홀드아웃을 보기 전에 다시 적는다(옛 기준 HISTORY [155]).
8. PR #39 → #40 병합(사용자 확인 뒤, 병합은 훅이 막음 → 사용자가 직접). HISTORY 끝에서 충돌 한 번([161]은 #40).
9. 사용자가 직접 할 것: 아래 표의 2026-11-06 자료를 구글 드라이브에 올리기, **집 PC에서 `new-setup` 적용**(main을 받고 `install.cmd -SkipMatt`, `install-optional.cmd experiment-checklist`, `install-optional.cmd session-search`, new-setup HISTORY [27]), 새 셋으로 GPT 빈손 [E0]·도우미 창 시간 10문항.
10. 그 밖(뒤로): 컴퓨터 유즈 시나리오(HISTORY [157]·[158]), 티켓 37·45, Win+E로 도우미 창이 튀어나옴, 42, pstack, 연습 과정 글 고치기(HISTORY [164]). 수집 자료로 원인 횟수 세기는 보류(홀드아웃 글 번호를 읽어야 해 승인 필요, HISTORY [178]).

## 지금 상태와 검증

- 강의실 PC에서 한 것(2026-11-06 오전): 집 PC 커밋 7개를 받고 pytest 601 passed. 사용자가 드라이브에서 받은 스크립트·결과를 대조(폴더 12개, 크기 본 파일 17개 일치, 빈 파일 없음, `겹침.json`에서 0.51 재현. 나머지 파일은 하나씩 안 맞춤). 이 PC에서 `flow_run.py` 재실행으로 재현과 속도 확인. 입력 흉내 시험, 측정 구멍 조사. 그 뒤 프로그램 코드는 안 바꿈. 시험 전후 진짜 설정 파일 같음(`flow_run` 재실행은 뒤에 시각으로 확인, 그 밖에 `data/eval/state_generic/__pycache__` 2개 갱신).
- 집 PC에서 한 것(2026-11-05 밤): main의 훅 수정을 이 브랜치에 합침(pytest 601 passed, 그 뒤 문서·`data/` 스크립트만 바꿔 다시 안 돌림). 시험 7: 충돌 자리 2개 재현(평가본 `NodeLink.is_hidden`, 다시 연 파일의 `local_view` 안의 `local_view`), H7 기준 미달 → 허용 목록. 시험 1·2 결과는 `docs/experiment.md`. 시험 스크립트는 전후로 진짜 설정·`quit.blend`·`data/`·개발 장면 폴더가 같은 것을 비교했다.
- 강의실 PC에서 한 것(모두 PR #39 브랜치): 검색 가설 4·5·6·7·8 측정과 결론(`docs/experiment.md`, HISTORY [168]-[172]), `experiment.md`의 "차례"를 문항·질문으로 고침, `bpy` 조사 세 번과 공식 문서 대조(HISTORY [173]), 분류와 후보 표 초안(HISTORY [174]), 공장값 비교 시험(HISTORY [175]), 범용 시험 계획과 H2·H3(HISTORY [176]), 진짜 충돌과 메타볼 확인(HISTORY [177]), 숫자는 `docs/experiment.md` 작업 상태 가설 1·2. 프로그램 코드는 바꾸지 않아 pytest를 다시 돌리지 않았다(PR #36 기준 596 passed). 집 PC에서 위 스크립트를 돌린 적은 없다(Blender 경로 `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`를 스크립트에 고정함, 다르면 고칠 것).
- 공식 문서 대조: `objects.inv`(5.2.4 RC)를 Claude가 따로 받아 조사 자료와 맞춤. 조작 2,497 전부 있음, 타입 1,789 전부 있음(RNA 밖 9개는 RNA 아닌 이름 목록), 타입 안 이름 17,237 중 없음 2개(`Context.texture_slot`, `Operator.bl_property`).
- 뒤집힌 면 세기 오류와 편집 모드의 낡은 `obj.data`는 Claude가 화면 없는 Blender로 재현함.
- 오늘 측정 비용(어림 포함): 가설 8 약 $0.075, 6 약 $0.04, 7 약 $0.02, 5 약 $0.02. 실행 전 잔액 $2.12(가설 8 전), 사용자 대조는 아직.

## 모르면 실수할 것

- **규칙이 있는 곳(2026-11-06 옮김)**: 공통 규칙은 `new-setup`의 `개인설정.md`(설치된 `~/.claude/CLAUDE.md`를 직접 고치지 않는다), 프로젝트 규칙은 `AGENTS.md`와 `docs/agents/review.md`, 실험 절차는 `experiment-checklist` 스킬이다. Claude 메모리에는 규칙을 쌓지 않는다(옮긴 파일은 `C:\WORK\trash\20261106`). 직접 입력한 `/compact`는 기록이 빠지면 훅이 한 번 막고, 10분 안에 다시 입력하면 통과한다. 훅 설정은 새 세션부터 읽힐 수 있다.
- **측정 구멍(2026-11-06)**: 시험 1·2, H1-1, H1-2 결과와 칸 표에는 모음 자체의 칸 91개가 빠져 있고, 새 물체 값은 빈도에 안 들어가며, 긴 모음은 앞 50개만 읽는다. 사람 기록 비율을 칸 표에 그대로 곱하면 안 된다(`view3d.select`가 표에서는 입력이 없어 취소됨, 좌표를 주면 됨).
- **사람 기록**: `%APPDATA%\blender_tutor\streams\`는 강의실 PC에 있다(183파일 2.8MB, 집 PC에는 없음). 큰 파일 5개가 사용자의 검·방패 검수 기록이다. 한 사람, 우리 연습 과정, 물체·편집 모드뿐이라 범용 근거로 쓰지 않고 조작 비율 참고로만 쓴다.
- **`bpy` 쓰임**: 애드온은 읽기만 한다. `bpy.ops`와 `new`·`remove`는 부르지 않는다. 값을 자동으로 전부 훑으면 Blender가 죽을 수 있다(`is_overridable`, 평가본 `NodeLink.is_hidden` 등) → 확인한 칸 목록만 읽는다. 편집 모드 메시는 `bmesh.from_edit_mesh`로 읽고, 뒤집힌 면 계산은 복사본에서 한다(원본에 하면 사용자 메시가 고쳐짐). 뒤집힌 면 세기는 평평한 메시에서 틀린다. 공식 문서(`docs.blender.org/api/5.2`)는 도우미 검색 자료가 아니라 개발 참고용이다(명세가 뺌).
- **작업 상태 시험**: 제품 규칙은 범용으로 만들고 개발 문항·장면은 규칙을 고정한 뒤 점검으로만 쓴다. 판단 기준을 먼저 적고, 일부러 바꾼 값은 세지 않는다. 등급(상·중·하)은 모델 판단이라 근거로 쓰지 않는다. Blender는 `BLENDER_USER_CONFIG`·`SCRIPTS`·`DATAFILES`·`EXTENSIONS`·`TEMP`를 임시 폴더로 주고 `--factory-startup --console-crash-handler`로 띄운다(`data/eval/state_generic/base_check.py`). 이렇게 하면 우리 애드온이 안 켜지고 `quit.blend`도 안 건드린다. 충돌 시험은 `faulthandler._read_null`로 한다(`ctypes.string_at(0)`은 파이썬 예외로 잡혀 안 죽는다). 값을 일반 순회로 읽으면 죽을 수 있다: 로컬 뷰에서 `SpaceView3D.local_view` 안의 `local_view`. "죽는 값" 목록은 시도한 상태에서만 맞는다. 공장 큐브와 조작으로 만든 큐브는 값이 달라 기준은 종류별로 조작으로 만든다. 스크립트 조작은 조작 기록에 안 남아 기록을 보는 시험은 `--enable-event-simulate`.
- **검색어는 실행마다 크게 달라진다**(같은 질문이 1위 ↔ 50위 밖). 합계만 보면 늘고 준 것이 상쇄되어 숨는다. 측정 기록(`답.jsonl`)에는 검색어가 남지 않는다 → 가설 실험 스크립트(`data/eval/dev50/search_h*.py`)가 남긴 기록을 쓴다. 정답 아는 검색어가 최선이라는 보장은 없다(Q29).
- **답 모델은 그림을 받지 않는다**(작업 상태 JSON만, `evaluate.py:303`). luna는 작업 상태를 받지 않는다. 작업 상태에 물체 회전 칸이 없다(`view.rotation`은 화면 시점). 최근 조작 칸에는 조작 이름만 남는다.
- **임베딩 글은 "쪽 제목 > 소제목 / 본문"뿐**이고 분야·묶음(경로)은 메타데이터로만 있다(`manual_vectors.py`가 `chunk.text`를 임베딩, 티켓 06 결정).
- **장면 만들기**: `data/eval/dev50/scenes.py`(창 있는 Blender, `--factory-startup --python … -- <장면>`) → `capture.py`(보통 설정으로 열어 애드온 save_snapshot). 선택은 `view3d.select_box`를 화면 좌표로(`box`·`box_world`). 스크립트 조작은 '최근 조작' 칸에 안 남는다(Q18-1 장면은 손으로 채우지 못함, `event_simulate`로 풀릴 수 있음, 안 해 봄).
- **창 있는 Blender를 끌 때마다 `%TEMP%\quit.blend`를 덮어쓴다.** 창 있는 Blender로 그림을 찍을 때 `--factory-startup`만 주면 시작 화면이 가운데를 가린다 → 장면 파일을 함께 연다. Blender 크래시 창이 뜨면 Restart 말고 Close(새 창이 쌓임).
- **디시 댓글은 회색지대**: 원인·해결로 쓰지 않는다. 하위 에이전트 지시에 "우회 금지·rm 금지"를 넣는다.
- **홀드아웃 열지 않기**: 새 `data/holdout/`·`data/holdout_work/`, 옛 `data/archive/holdout_20261103/`, 질문 모음 `data/holdout_pool/`. 개발셋 하위 에이전트에도 열지 말라고 적는다.
- **유료**: `evaluate run`은 `--yes` 없이 어림만. 실험 스크립트도 `--yes`를 받아야 돈을 쓴다. API 키는 `data/.env`.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

**드라이브와 견주기**: 하루 마무리 때 `.venv\Scripts\python -m blender_tutor.data_manifest`로 **로컬 상태**를 `data/MANIFEST_요약.md`와 `data/MANIFEST.tsv`(파일별 크기·날짜)에 적는다(로컬 파악용, 드라이브에 안 올림). 드라이브 도구로 최근 올린 시각(`createdTime`)을 찾고, 로컬에서 그 뒤에 바뀐 파일만 추리면 올릴 것이 나온다. 드라이브의 `modifiedTime`은 원본 수정 시각을 그대로 유지하고 `createdTime`이 올린 시각이다(2026-11-05 확인). results는 날짜 폴더째 올린다.

**2026-11-05 저녁 상태**: 사용자가 `results/20261105/`, `data/holdout_work/`, 스크립트 12개를 올렸다고 함(드라이브에 폴더 3개 만들어진 것 확인, 08:35-08:37 UTC). **파일 단위 대조는 끝을 못 봤을 수 있어 2026-11-06 아침에 다시 한다**: 로컬 732개와 드라이브를 경로·크기·시각으로 맞춤. 스크래치 `drive_check/local.tsv`는 임시라 `data_manifest` 목록과 드라이브 도구로 다시 만든다. `data/manual_en_5.2/`는 드라이브에 zip으로만 있고 집 PC에는 폴더가 있다(사용자 말, zip은 이름 검색에 안 나와 확인 못 함). 나머지 약 3,000개는 하나씩 보지 않고 날짜로 잘랐다. 어제 업로드에서 빠진 파일은 못 잡으니, 지우기 전에는 그 폴더를 하나씩 대조한다. 전체 대조를 싸게 하려면 Google Drive 데스크톱 앱(`G:`)이 있는지 볼 것(안 물어봄).

| 자료 | 있는 곳 | 위치 | 비고 |
|---|---|---|---|
| 새 개발셋 | 강의실, 드라이브 | `data/eval/dev50/` | 문항초안.md, questions.json, scenes/·states/, 검색 실험 스크립트 search_h1·h1b·h2·h2_pairs·h3·h4_q19·h4_chunk·h5·h6·h7·h8.py, state_diff.py·state_diff_run.py, `data/eval/state_generic/`(probe.py·base_check.py·probe2.py·check2.py), extra_state.py·extra/, verify/, 후보_본문.md(남의 글 발췌) |
| 새 홀드아웃 봉인·작업 자료 | 강의실, 드라이브 | `data/holdout/`(57파일), `data/holdout_work/` | 열지 않기 |
| 옛 홀드아웃 | 강의실, 드라이브 | `data/archive/holdout_20261103/` | 열지 않기 |
| 홀드아웃용 질문 모음 | 강의실, 드라이브 | `data/holdout_pool/use_holdout.json` | 개발셋 글 51개를 뺀 1,115개 |
| 질문 조사 원자료 | 강의실, 드라이브 | `data/research_raw/20261104_질문모음/` | |
| 결과 11-04 | 강의실, 드라이브 | `results/20261104/` | 145409_dev50_before, 160743_search_h1, 161724_search_h1b, search_h2_log.txt, search_h2_pairs_log.txt, 165335_search_h3 |
| 결과 11-05 | 강의실, 드라이브 | `results/20261105/` | 092459_search_h4_q19, 095146_search_h4_chunk, 100827_search_h5, 102254_search_h8, 103759_search_h6, 105605_search_h7, 120433_bpy_dump(약 155MB), 135703_bpy_dump2(약 430MB), 142218_bpy_classify, 145831_bpy_classify2, 164329_state_diff, 164619_state_diff, 170618_state_base_check, 171644_state_safety_meta |
| 시험 스크립트 11-05 밤 (드라이브에 있음, 강의실 PC에도 받음) | 집, 강의실, 드라이브 | `data/eval/state_generic/` | crash_walk·crash_run, op_walk(3판)·op_run·op_table, flow_walk·flow_run, reach_table, type_bases, 앞 판 op_walk_v1·v2, op_table_v1 |
| **시험 스크립트 11-06 (강의실 PC에만, 드라이브에 올릴 것)** | **강의실만** | `data/eval/state_generic/` | sim_walk·sim_run·sim_min·sim_min_run, hole_probe·hole_run, flow_run(창 위치 x=0으로 고침) |
| **시험 결과 11-06 (강의실 PC에만, 드라이브에 올릴 것)** | **강의실만** | `results/20261106/` | 092251_flow_walk, 094230_event_sim, 094525_event_sim_focus, 094732_event_sim_min, 095840_hole_probe |
| 시험 결과 11-05 밤 (드라이브에 있음, 강의실 PC에도 받음) | 집, 강의실, 드라이브 | `results/20261105/` | 기록에 숫자로 쓴 것: 191121_crash_walk2, 191735_crash_walk_window, 193217_crash_walk_wide, 193426_crash_walk_wide_line, 193446_crash_walk_wide_bg, 194118_crash_walk_reopen_bg, 194616_crash_walk_reopen_window, 200541_reach_table, 212340_op_walk3_bg, 215835_op_walk3_window, 225533_flow_walk, 225752_flow_walk. 비교용 앞 판: 201233_op_walk, 205827_op_walk2, 214347_op_walk3_window_try, 225247_flow_walk. 안 옮겨도 됨: 190443, 190510, 191518, 200732, 205253, 211823, 214219 |
| 프로토타입 개발셋 | 강의실 | `data/eval/dev30/` | 기록은 `archive/experiment_prototype.md` |
| API 키·벡터·모델 | PC마다 따로 | `data/.env`, `data/vectors/`, `data/models/` | 앞과 같음 |
| 사람 조작 기록 `streams` | **강의실만**(집 PC에 없음) | `%APPDATA%\blender_tutor\streams\` | 183파일 2.8MB, Git·드라이브 밖 |

## 참고

- [실험 기록·체크리스트](docs/experiment.md)(목차), [`bpy` 전체 분석](.scratch/mvp-roundtrip/research/2026-11-05-bpy-전체-분석.md), [`bpy` 작업 상태 지도](.scratch/mvp-roundtrip/research/2026-11-05-bpy-작업상태-지도.md), [범용 시험 계획](.scratch/mvp-roundtrip/research/2026-11-05-작업상태-범용-시험-계획.md), [칸 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류.md), [RNA 밖 이름·계산 값 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류-2.md), [칸 후보 초안(낡음)](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-후보-초안.md), [개발셋 작업표](.scratch/mvp-roundtrip/dev50-작업표.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [질문 종류 조사](.scratch/mvp-roundtrip/research/2026-11-04-블렌더-질문-종류.md), [경과 [168]-[193]](HISTORY.md), [구조](STRUCTURE.md).
- 검색 흐름 코드: `blender_tutor/answer_engine.py`(`REWRITE_PROMPT`, `answer`, `_rewritten`, `search`, `_widened`), `engine_setup.py`. 공식 API 문서: `https://docs.blender.org/api/5.2/`.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
