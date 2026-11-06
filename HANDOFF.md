# 인수인계

마지막 갱신: 2026-11-06 오후 · Claude Code(Opus 5.5) · 강의실 PC(DESKTOP-J9LV5HK) · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. PR #40(`chore/tidy-menu-json`)도 병합 전. 이어받을 때 두 PR이 병합됐는지 git으로 먼저 본다.

## 지금 상태 한눈에

- **돌아가는 시험 없음. 가설 8-2에서 멈췄다: 값 읽기 7판을 만들기로 정했고 코드는 안 고쳤다(`op_walk.py`는 6판). 계획은 `docs/experiment.md` 맨 끝. 공식 문서 대조 하위 에이전트 4개는 끝났고 보고서는 `.scratch/mvp-roundtrip/research/2026-11-06-공식문서-대조-*.md`.** 2026-11-06에 어제 판정을 다시 봐 **H1-2의 "미달" 결론을 철회했고**([188]-[191]), **측정 구멍을 고쳤다**([195], `docs/experiment.md` 가설 7, 통과). 앞의 시험 1·2, H1-1, H1-2 결과는 옛 도구로 잰 것이라 칸 목록을 그대로 쓰지 않는다.
- **목표(사용자 확인)**: "API 에서 찾아낸 값중 어떤것을 효율적으로 보내면 좋을까?". 세 묶음은 '늘 바뀌는 값' / '계산이 필요한 값' / '그 외 나머지'. 효율은 "정해진 줄 수 안에서, 필요한 값을 놓치지 않고 보내는 것". **줄 수 한도는 아직 없다**(90%·중앙 30줄은 근거가 약해 철회). 비용과 묻힘은 예상일 뿐 재지 않았다.
- 훅이 `.venv/Scripts/python.exe`로 돈다(PR #41 병합됨, [182]). `.venv`가 없는 곳에서는 터미널 명령이 막히니 직접 터미널을 열어 만든다. 강의실 PC는 `.venv`가 있고 명령이 정상으로 돈다.
- **방향이 바뀌었다(HISTORY [175]-[177]).** 칸을 상·중·하로 고르지 않는다(사용자 "애초에 이젠 등급을 빼기로 했으니"). 값이 움직이는 모양으로 나눈다: 늘 바뀌는 값·계산해야 아는 값은 매번(계산 값 보내는 규칙은 시험 뒤) / 일부러 바꿔야 바뀌는 값은 공장값과 다를 때만 / 그 외는 무엇이 있는지 파악. 범용으로 만들고 연습 과정 감지에도 쓴다. 사용자 "우리 범용적으로 쓸거 만드는거다".
- **사용자 판단 전에 하지 않는 것**: 칸 확정, 애드온·프로그램 코드 수정, 돈이 드는 호출, PR 병합, 사용자 설정 변경.

## 다음 할 일

1. **값 읽기 7판을 만들고 다시 잰다(집 PC).** 사용자 "원인을 알고 고칠 방법을 아는데 고치긴하는게 맞아보임". 공식 문서(`data/blender_api_5.2/`)가 집 PC에 없으니 먼저 받는다: `mkdir data\blender_api_5.2`, `curl -L -o data\blender_api_5.2\api.zip https://docs.blender.org/api/5.2/blender_python_reference_5_2.zip`, `.venv\Scripts\python data\eval\state_generic\api_to_text.py`. 강의실 판은 zip 99,938,764바이트, `txt` 2,191개다(공식 문서가 갱신됐으면 다를 수 있어 숫자를 견줘 알린다). 드라이브에서 아래 표의 스크립트를 받아 `data/eval/state_generic/`이 강의실 판인지 본다(`op_walk.py`에 `CUSTOM_OK`와 `read_custom`이 있어야 6판, 18,912바이트). 할 일과 기준은 `docs/experiment.md` 가설 8-2 맨 끝 "7판 계획" 1-5번. 약 1시간 20분(강의실 기준, 돈 안 듦). 시험을 돌리는 동안 `op_walk.py`를 고치지 않는다.
   그 뒤 가설 8을 마친다: ① 스컬프트 `stroke`, 네모 선택 등을 호출과 `agent-desktop drag`로 대조, 끌기 도중 값 ② 넘어간 것 표, 실행 뒤 독립 검토(스킬 지시문 그대로), 판정 ③ 판정 뒤 애드온 안건을 **한 항목씩** 묻는다: 스레드, 쿼드 뷰·카메라 시점에서 시점 값 누락, `region_3d`가 `None`이면 그 회차 전체 실패, 사본 저장 경로, "REGISTER만 기록에 남는다" 주석·`STRUCTURE.md`, 키맵·`opened` 주석, `blender_manifest.toml`. 비용과 묻힘 측정, 줄 수 한도는 아직 안 정했다.
2. **있는 조작을 다 써 보는 시험을 만든다**(사용자 "있는건 다 써보는 테스트 만들어야 하지 않을까?"). 11-05 시험 2는 옛 도구·기본 입력이고 2,605개 중 1,552개만 실행됐다. 고친 도구와 `undo=True`로 다시 돌리고, 못 돈 조작은 조작마다 까닭을 적고, 입력 칸(`ops.json`, 공식 문서)으로 끌기 조작도 채운다. 그 뒤 '늘 바뀌는 값' 시험(아래 3-2)을 체크리스트대로 다시 잰다.
3. **범용 시험을 이어 간다.** [계획](.scratch/mvp-roundtrip/research/2026-11-05-작업상태-범용-시험-계획.md)(0절이 진행 상황). 사용자 "진행해 ㄱㄱ"(전수 실행, 기준 숫자 제안값, 설정 복사본 승인).
   1. **진행 순서(사용자가 정함)**: 가설 → 결과 보기 전에 기준 적기 → 실험 → 결과 → 이 시험의 목적 다시 보기 → 통과하면 실험 자체 점검 → 다음. `experiment-checklist` 스킬의 체크리스트를 채운다. 실패했다고 원인을 안 재고 방법만 바꿔 고르게 하지 않는다(HISTORY [185]). 있는지 확인하지 않은 자료에 기대지 않는다.
   2. **늘 바뀌는 값 다음 시험(안)**: 가설은 "몇 가지 작업에서 모은 작은 목록이 목록을 만들 때 쓰지 않은 작업에서 자주 바뀌는 값도 대부분 잡는다". 성격이 다른 작업 6개, 지표는 덮는 비율과 크기. 사람 기록을 참고해 선택(좌표 지정)과 시점 돌리기를 넣고, 흐름은 목록을 모르는 Sonnet 하위 에이전트가 쓴다. 숫자 기준은 사용자와 정한다.
   3. 남은 순서: 공장값 나머지(3) → 긴 작업(4, 목록 경계를 옮기면 줄 수가 변하나도 봄) → 늘 보이는 칸(5) → 계산 값(6) → 언제 읽나(8, 타이머 안에서는 `bpy.context`에 창이 없어 `objects_in_mode`가 없음) → 감지(9, 입력 흉내 원인도 여기서) → 규칙 고정 → 개발 문항 점검(10). 걸린 시간(집 PC): 시험 7 약 37분, 시험 2 화면 없음 19분(10개 동시) · 창 51분(8개 동시, CPU 80%), 흐름 3개 약 2분 20초. **강의실 PC는 약 1.7배 느리고**(같은 흐름 237초), 모니터가 1대라 창이 화면을 가린다. 창 8개 동시 시험은 집 PC 권함. `flow_run.py`, `crash_run.py`, `case_run.py`는 환경 변수 `STATE_WINDOW_X`로 창 위치를 정한다(기본 0, -1920이면 강의실 PC에서도 화면을 안 덮고 결과가 같음). `op_run.py`는 아직 x=-1920 고정이다. 입력 흉내 원인은 집 PC에서 `sim_cause_run.py`를 돌려 가린다. 값 읽기는 전체 읽기가 창에서 약 2초(값 21만 개, 91.5%가 키맵), `snapshot(full=False)`는 약 0.36초다. `op_walk.py`의 조작 시험은 아직 전체 읽기를 쓰므로 시험 2를 다시 돌리기 전에 정한다.
   4. 결과는 `docs/experiment.md`에 앞 가설들과 같은 모양으로 남기고 [칸 후보 초안](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-후보-초안.md)을 다시 쓴다.
4. 구현: 애드온 `read_state`(시험을 통과한 범위만 읽음), `work_state.py`(공장값과 다를 때만 넘길지 판별), 질문 바꾸기로 넘기기. 0.5초 타이머와 F10 없는 질문 길을 어떻게 할지 시험 8로 정한다. 티켓을 나눌지 정한다. 그 뒤 실제 환경 확인과 검색 재기.
5. 나머지 고칠 후보를 정한다. 표는 HISTORY [173] 앞의 설명과 `docs/experiment.md`. 권한 순서: 칸 보강 → 청크 쪽 한 번에(옵션 떼어 내기, 분야·묶음 이름, 같은 글 합치기, 벡터 다시 만들기 약 $0.13) → 지시문(사족 줄이기, 연습 과정 목록) → 마지막 조정(3개 합치기, 칸 12-16개). 뺀 것: 검색어 짧게(가설 6), 번역 합치기(가설 7). 보류: `low`(첫 글자 2초 목표를 바꿀 때만), 더 큰 모델(이름 선택, 안 잼).
6. 고친 뒤 개발셋을 2-3번 돌려 **약 5개 넘게** 나아지는지 본다(지금 방식 범위 38-46개, 1-2개라던 옛 기준은 틀림). 받은 청크 수는 같은 때 함께 돌린 값끼리 견주고 문항별 변화도 본다. 답까지 재는 측정은 다 고친 뒤.
7. 홀드아웃 "이겼다" 기준을 새 홀드아웃을 보기 전에 다시 적는다(옛 기준 HISTORY [155]).
8. PR #39 → #40 병합(사용자 확인 뒤, 병합은 훅이 막음 → 사용자가 직접). HISTORY 끝에서 충돌 한 번([161]은 #40).
9. 사용자가 직접 할 것: 아래 표의 2026-11-06 자료를 구글 드라이브에 올리기, **집 PC에서 `new-setup` 적용**(main을 받고 `install.cmd -SkipMatt`, 자동 압축 600k도 이때 들어가고 켜 둔 세션은 `/exit` 뒤 `claude --continue`로 반영, `install-optional.cmd experiment-checklist`, `install-optional.cmd session-search`, new-setup HISTORY [27]), 새 셋으로 GPT 빈손 [E0]·도우미 창 시간 10문항.
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
- **`bpy` 쓰임**: 애드온은 Blender 데이터를 바꾸지 않는다(스크린샷 조작, 키맵 항목 `new`·`remove`, 등록, 상태 줄 글은 쓴다). 값을 자동으로 전부 훑으면 Blender가 죽을 수 있다(`is_overridable`, 평가본 `NodeLink.is_hidden` 등) → 확인한 칸 목록만 읽는다. 애드온의 편집 모드 선택 수는 `mesh.total_*_sel`로 읽는다. 뒤집힌 면 계산 쪽은 `bmesh.from_edit_mesh`로 읽고 복사본에서 한다(원본에 하면 사용자 메시가 고쳐짐). 뒤집힌 면 세기는 평평한 메시에서 틀린다. 공식 문서(`docs.blender.org/api/5.2`)는 도우미 검색 자료가 아니라 개발 참고용이다(명세가 뺌).
- **작업 상태 시험**: 제품 규칙은 범용으로 만들고 개발 문항·장면은 규칙을 고정한 뒤 점검으로만 쓴다. 판단 기준을 먼저 적고, 일부러 바꾼 값은 세지 않는다. 등급(상·중·하)은 모델 판단이라 근거로 쓰지 않는다. Blender는 `BLENDER_USER_CONFIG`·`SCRIPTS`·`DATAFILES`·`EXTENSIONS`·`TEMP`를 임시 폴더로 주고 `--factory-startup --console-crash-handler`로 띄운다(`data/eval/state_generic/base_check.py`). 이렇게 하면 우리 애드온이 안 켜지고 `quit.blend`도 안 건드린다. 충돌 시험은 `faulthandler._read_null`로 한다(`ctypes.string_at(0)`은 파이썬 예외로 잡혀 안 죽는다). 값을 일반 순회로 읽으면 죽을 수 있다: 로컬 뷰에서 `SpaceView3D.local_view` 안의 `local_view`. "죽는 값" 목록은 시도한 상태에서만 맞는다. 공장 큐브와 조작으로 만든 큐브는 값이 달라 기준은 종류별로 조작으로 만든다. 스크립트 조작은 `undo=True`로 불러야 조작 기록에 남는다(가설 8-1, REGISTER나 UNDO 표시가 있는 조작. 표본 11개).
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

**2026-11-06 17시 강의실 PC 점검**(`data_manifest`로 목록 다시 만듦, 10,952줄): 드라이브에서 만든 시각 `2026-11-05T16:20Z`(11-06 01:20 KST) 뒤 파일 없음, 그때까지의 최근 업로드는 `2026-11-05T16:16Z`. 그 뒤 로컬에서 바뀐 `data/`는 `eval/state_generic` 53개 0.79MB(`__pycache__` 포함), `blender_api_5.2` 2,192개 110.8MB뿐이다(**드라이브에 안 올림, 집 PC에서 받는다**, 사용자 "3번은 handoff 에 남겨줘 집에서 받으라고"). `results/20261106/`은 1,633개 165.9MB로 통째로 안 올라갔다. 드라이브의 `state_generic/op_walk.py`는 12,583바이트 옛 판이고 로컬은 18,912바이트라, 올린 뒤 **크기로 새 판인지 확인한다**(같은 이름 폴더를 올리면 둘로 생길 수 있음, 추측). 전체 파일 단위 대조는 이번에도 안 했다(아래 11-05 항목이 그대로 남음). **2026-11-09(월) 강의실 PC에서 한다**(사용자 "다음주 월요일에는 대신 하긴 해야할듯?"). 그 PC의 `data_manifest` 목록과 드라이브 목록을 경로·크기로 맞추며 어림 15-20분(약 5,700개, 안 재 봄)이고 집 PC 목록은 필요 없다. `MANIFEST.tsv`에는 `results/`가 파일별로 안 들어 있어(파일 수 합 11,279가 `data/`와 같음) `results/`는 따로 세어 맞춘다. 집과 강의실을 서로 견주려면 양쪽 목록을 만들어 `--compare`한다.

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
| **시험 스크립트 11-06 (강의실 PC에만, 드라이브에 올릴 것, 집 PC 1번에 꼭 필요)** | **강의실만** | `data/eval/state_generic/` | **폴더 전체**(896KB). 11-06 오전 것과 오후에 고친 `op_walk.py`(6판), `op_walk_v5_커스텀없음.py`, `case_walk.py`, `crash_walk.py`, `flow_walk.py`, `doc_walk.py`, `doc_run.py`, `input_*`, `sim_cause*` 포함. 2026-11-06 17시쯤 드라이브 검색에 `doc_walk`, `op_walk_v5` 없음 |
| **시험 결과 11-06 (강의실 PC에만, 드라이브에 올릴 것)** | **강의실만** | `results/20261106/` | 폴더째(162MB, `165659_h8_2_safety_bg` 36MB는 멈춘 실행이라 빼도 됨). 8-2 대조에 `113739_h7_safety_bg`, `122610_h7_safety_window`, `144527_h8_safety_bg`, `144550_h8_safety_window`, `163538_h7_cases`, `165659_flow_walk`가 필요 |
| 시험 결과 11-05 밤 (드라이브에 있음, 강의실 PC에도 받음) | 집, 강의실, 드라이브 | `results/20261105/` | 기록에 숫자로 쓴 것: 191121_crash_walk2, 191735_crash_walk_window, 193217_crash_walk_wide, 193426_crash_walk_wide_line, 193446_crash_walk_wide_bg, 194118_crash_walk_reopen_bg, 194616_crash_walk_reopen_window, 200541_reach_table, 212340_op_walk3_bg, 215835_op_walk3_window, 225533_flow_walk, 225752_flow_walk. 비교용 앞 판: 201233_op_walk, 205827_op_walk2, 214347_op_walk3_window_try, 225247_flow_walk. 안 옮겨도 됨: 190443, 190510, 191518, 200732, 205253, 211823, 214219 |
| 프로토타입 개발셋 | 강의실 | `data/eval/dev30/` | 기록은 `archive/experiment_prototype.md` |
| API 키·벡터·모델 | PC마다 따로 | `data/.env`, `data/vectors/`, `data/models/` | 앞과 같음 |
| 사람 조작 기록 `streams` | **강의실만**(집 PC에 없음) | `%APPDATA%\blender_tutor\streams\` | 183파일 2.8MB, Git·드라이브 밖 |

## 참고

- [실험 기록·체크리스트](docs/experiment.md)(목차), [`bpy` 전체 분석](.scratch/mvp-roundtrip/research/2026-11-05-bpy-전체-분석.md), [`bpy` 작업 상태 지도](.scratch/mvp-roundtrip/research/2026-11-05-bpy-작업상태-지도.md), [범용 시험 계획](.scratch/mvp-roundtrip/research/2026-11-05-작업상태-범용-시험-계획.md), [칸 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류.md), [RNA 밖 이름·계산 값 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류-2.md), [칸 후보 초안(낡음)](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-후보-초안.md), [개발셋 작업표](.scratch/mvp-roundtrip/dev50-작업표.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [질문 종류 조사](.scratch/mvp-roundtrip/research/2026-11-04-블렌더-질문-종류.md), [경과 [168]-[198]](HISTORY.md), [구조](STRUCTURE.md).
- 검색 흐름 코드: `blender_tutor/answer_engine.py`(`REWRITE_PROMPT`, `answer`, `_rewritten`, `search`, `_widened`), `engine_setup.py`. 공식 API 문서: `https://docs.blender.org/api/5.2/`.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
