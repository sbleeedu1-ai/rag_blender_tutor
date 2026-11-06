# 인수인계

마지막 갱신: 2026-11-07 레트로 판단 뒤 · Claude Code(Opus 5.5) · 집 PC(B783D5080) · 브랜치 `feat/35-dev-eval` · PR #39 병합 전에 씀. PR #40(`chore/tidy-menu-json`)도 병합 전. 이어받을 때 두 PR이 병합됐는지 git으로 먼저 본다.

## 지금 상태 한눈에

- **다음 할 일 한 줄: 목표 시험 "늘 바뀌는 값"의 가설과 기준을 실행 전에 사용자에게 보인다. 도구 고치기는 멈춘다.** 레트로 후보 판단은 끝났다(HISTORY [214]). 삭제 훅은 넓히지 않는다(사용자 "그럼 하지마", HISTORY [215]). 긴 시험 감시는 다음 긴 시험 때 함께 만들고, `rmtree`가 든 10개 중 다음 시험에 쓰는 것만 세션 스크래치패드에 만들도록 고친다. 시험 명령은 `docs/experiment.md` 마지막 절에 `- [x] 목표 검토:`나 `- [x] 도구의 동작:`이 없거나, 앞 시험의 실행 뒤 칸이 비었거나, 두 검토의 하위 에이전트 호출이 세션 기록에 없거나, `도구의 동작` 칸의 `bpy.` 이름을 `.claude/tools/api_doc.py`로 본 기록이 없으면 훅이 막는다. 호출 프롬프트에 절 제목과 칸 이름을 넣어야 찾는다. 강의실 PC는 `new-setup` main을 받아 `install.cmd -SkipMatt`와 `install-optional.cmd experiment-checklist`를 돌려야 한다. 종합 문서: `.scratch/mvp-roundtrip/research/2026-11-07-작업상태-종합.md`, 전수표: `results/20261107/031654_값_전수표/`.
- **판 상태: 돌아가는 시험 없음. 사용자가 8-5 "9판 통과"를 철회했고("철회", HISTORY [214]) 8-6은 판정 없음이라, 통과한 판은 7판까지다. 다음 시험에 어느 판을 쓸지는 아직 안 정했다. `data/eval/state_generic/op_walk.py`는 9판(보관본 `op_walk_v9_선택이름만.py`)이고, 8판 `op_walk_v8_주인더함.py`는 통과하지 못했으며, 7판은 `op_walk_v7_주소만.py`, 6판은 `op_walk_v6_먼저닿은길.py`다.** 공식 문서 대조 보고서는 `.scratch/mvp-roundtrip/research/2026-11-06-공식문서-대조-*.md`. 2026-11-06에 어제 판정을 다시 봐 **H1-2의 "미달" 결론을 철회했고**([188]-[191]), **측정 구멍을 고쳤다**([195], 가설 7, 통과). 앞의 시험 1·2, H1-1, H1-2 결과는 옛 도구로 잰 것이라 칸 목록을 그대로 쓰지 않는다.
- **목표(사용자 확인)**: "API 에서 찾아낸 값중 어떤것을 효율적으로 보내면 좋을까?". 세 묶음은 '늘 바뀌는 값' / '계산이 필요한 값' / '그 외 나머지'. 효율은 "정해진 줄 수 안에서, 필요한 값을 놓치지 않고 보내는 것". **줄 수 한도는 아직 없다**(90%·중앙 30줄은 근거가 약해 철회). 비용과 묻힘은 예상일 뿐 재지 않았다.
- 훅이 `.venv/Scripts/python.exe`로 돈다(PR #41 병합됨, [182]). `.venv`가 없는 곳에서는 터미널 명령이 막히니 직접 터미널을 열어 만든다. 강의실 PC는 `.venv`가 있고 명령이 정상으로 돈다.
- **방향이 바뀌었다(HISTORY [175]-[177]).** 칸을 상·중·하로 고르지 않는다(사용자 "애초에 이젠 등급을 빼기로 했으니"). 값이 움직이는 모양으로 나눈다: 늘 바뀌는 값·계산해야 아는 값은 매번(계산 값 보내는 규칙은 시험 뒤) / 일부러 바꿔야 바뀌는 값은 공장값과 다를 때만 / 그 외는 무엇이 있는지 파악. 범용으로 만들고 연습 과정 감지에도 쓴다. 사용자 "우리 범용적으로 쓸거 만드는거다".
- **사용자 판단 전에 하지 않는 것**: 칸 확정, 애드온·프로그램 코드 수정, 돈이 드는 호출, PR 병합, 사용자 설정 변경.

## 다음 할 일

1. **이 항목은 위 "지금 일" 뒤로 미룬다. 도구 문제는 "어떤 값을 보낼지 답이 달라지는가"만 따진다. 아래 "9판 통과"는 철회한 판정이다(`docs/experiment.md` 가설 8-5, HISTORY [214]). 입력 흉내 관련 문장은 HISTORY [209]로 바뀌었다(입력 흉내가 먹는다).** 8-5에서 넘긴 것: 포인터 글이 `name` 없는 구조(`ActionSlot`)를 못 가림(74번), 읽기만으로 Cycles 장치 2개가 생기는 것의 애드온 영향, 주소 대조 561과 이름·번호 이동의 값 대조, 일부만 만든 상태 18·16개, 66번 `has_objects()`(물체가 있어도 False, 소스 또는 조작으로), 창의 읽는 순서. 입력 흉내는 집 PC에서도 안 먹고 `agent-desktop`은 집 PC에 없어, 끌기 대조는 실제 마우스를 쓰는 동안 사용자가 PC를 안 건드려야 한다(가설 8-6, 언제 할지 답 대기, 강의실 PC에는 `agent-desktop`이 있다). 다음 순서: ① 스컬프트 `stroke`, 네모 선택 등을 호출과 `agent-desktop drag`로 대조, 끌기 도중 값 ② 넘어간 것 표, 실행 뒤 독립 검토(스킬 지시문 그대로), 판정 ③ 8-3에서 넘긴 것: 창 단계 6판 대조(약 39분), 옮겨진 구조의 값 직접 대조, `local_view_get`의 다른 `RuntimeError`, 71·72번 3번 되풀이 ④ 판정 뒤 애드온 안건을 **한 항목씩** 묻는다: 스레드, 쿼드 뷰·카메라 시점에서 시점 값 누락, `region_3d`가 `None`이면 그 회차 전체 실패, 사본 저장 경로, "REGISTER만 기록에 남는다" 주석·`STRUCTURE.md`, 키맵·`opened` 주석, `blender_manifest.toml`. 비용과 묻힘 측정, 줄 수 한도는 아직 안 정했다.
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
8. PR #39 → #40 병합(사용자 확인 뒤, 병합은 훅이 막음 → 사용자가 직접). HISTORY 끝에서 충돌 한 번([161]은 #40). 2026-11-06 저녁 `gh pr view`로 #39는 충돌 없음, #40은 `CONFLICTING`(어느 파일인지 안 봄).
9. 사용자가 직접 할 것: 새 셋으로 GPT 빈손 [E0]·도우미 창 시간 10문항. 집 PC `new-setup` 적용은 끝남(아래 검증).
10. 그 밖(뒤로): 컴퓨터 유즈 시나리오(HISTORY [157]·[158]), 티켓 37·45, Win+E로 도우미 창이 튀어나옴, 42, pstack, 연습 과정 글 고치기(HISTORY [164]). 수집 자료로 원인 횟수 세기는 보류(홀드아웃 글 번호를 읽어야 해 승인 필요, HISTORY [178]).

## 지금 상태와 검증


- 집 PC에서 확인한 것(2026-11-06 저녁, 강의실 커밋 27개를 받은 뒤): pytest 637 passed. `data/eval/state_generic/` 54개 790,661바이트, `results/20261106/` 1,633개 165,904,348바이트로 기록과 같음(내용까지는 안 봄), `op_walk.py` 18,912바이트에 `CUSTOM_OK`·`read_custom` 있음(6판). 대조에 쓸 폴더 7개와 안전 시험 입력 `results/20261105/142218_bpy_classify/funcs_classified.csv` 있음. 공식 문서를 받음: zip 99,938,764바이트, `txt` 2,191개로 강의실 판과 같음. 개인설정 설치본이 `new-setup` 원본과 해시까지 같고 `autoCompactWindow` 600000 있음(`/context` 표시는 안 봄). `experiment-checklist`, `session-search`를 `install-optional.cmd`로 설치함(Claude Code·Codex·안티그래비티 모두에 들어감). 그 뒤 기록만 바꿨다.
- 공식 문서 대조: `objects.inv`(5.2.4 RC)를 Claude가 따로 받아 조사 자료와 맞춤. 조작 2,497 전부 있음, 타입 1,789 전부 있음(RNA 밖 9개는 RNA 아닌 이름 목록), 타입 안 이름 17,237 중 없음 2개(`Context.texture_slot`, `Operator.bl_property`).
- 뒤집힌 면 세기 오류와 편집 모드의 낡은 `obj.data`는 Claude가 화면 없는 Blender로 재현함.
- 오늘 측정 비용(어림 포함): 가설 8 약 $0.075, 6 약 $0.04, 7 약 $0.02, 5 약 $0.02. 실행 전 잔액 $2.12(가설 8 전), 사용자 대조는 아직.

## 모르면 실수할 것

- **CPU 60% 제한(사용자, 이 PC에서 게임과 함께 쓸 때)**: "혹시나  CPU 사용률 치솟을 일 있으면 최대 60% 까지만 써야함". 집 PC는 16스레드, Blender 1개는 약 5.5%지만 다른 프로그램이 약 35%를 쓴다. 동시에 2개까지만 돌리고, 오래 걸리는 안전 시험은 시작 뒤 `crash_run.py` 프로세스에 스레드 2개와 낮은 우선순위를 준다(자식 Blender가 물려받음, 시험 쪽 상한 전체의 약 25%). 2개를 돌릴 때 전체 평균 48-51%, 순간 최대 65%였고 넘은 순간의 원인은 못 나눴다. 시간을 판정에 쓰는 시험은 제한을 걸지 말고 혼자 돌린다.
- **안전 시험 감시가 멈춘 Blender를 못 끈 적이 있다(2026-11-06, 원인 모름)**: `crash_run.py`의 120초 감시가 있어도 Blender가 약 52분 응답 없음으로 머물렀고 감시 python의 CPU도 늘지 않았다. 사용자가 물어서 알았다. 진행 표식이 비어 있어 값 읽기가 돌기 전에 멈췄다. 매핑 중 읽기는 막히지 않아, 감시가 어디에 머물렀는지는 모른다. 원인을 찾기 전에는 긴 시험을 돌릴 때 로그가 3분 넘게 안 늘면 알리는 바깥 감시를 함께 둔다. 예는 이번 스크래치패드 스크립트와 같은 모양: `WaitForExit(5000)` 반복, 로그 줄 수 비교. 멈춘 Blender를 손으로 끄면 다음 상태 준비가 `OSError 22`로 끝나므로 남은 상태를 `--only`로 이어 돌린다.
- **저장소를 받은 세션은 옛 규칙을 들고 있다**: 세션을 시작할 때 읽은 `AGENTS.md`는 `git pull` 뒤에도 그대로라, 규칙 파일이나 훅이 바뀌는 커밋을 받으면 새 세션을 연다(2026-11-06 저녁 실제로 옛 판과 달랐다, HISTORY [204]).
- **세션과 하위 에이전트**: 오래 걸리고 도중 상태가 궁금한 일은 부모 아래 들여써 보이는 세션, 금방 끝나고 결과만 필요한 일은 하위 에이전트, 판단 없이 프로그램만 도는 시험은 뒤에서 도는 명령. 이유와 확인 범위는 HISTORY [204]. 사용량 차이는 안 쟀다.
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

**2026-11-06 밤 집 PC에서 새로 생긴 것(드라이브에 안 올림, 강의실 PC에 없음)**: `data/eval/state_generic/`의 `op_walk.py`(9판), `op_walk_v9_선택이름만.py`, `op_walk_v8_주인더함.py`, `second_walk_check.py`, `flow_compare.py`, `h8_5_read.py`, `op_walk_v7_주소만.py`, `op_walk_v6_먼저닿은길.py`, `flow_walk.py`, `flow_run.py`, `case_walk.py`(21번 뒷정리, 71-76번), `order_check.py`(`share` 집계 추가), `safety_compare.py`, `dup_share_check.py`와 `results/20261106/`의 19시 37분 뒤 폴더, `h8_3_실행출력_*.log`, `h8_4_실행출력_*.log`, `results/20261107/` 전체. 올린 뒤 경로·크기로 맞춘다. 올리기 전에 강의실 PC에서 시험을 이어 가면 7판과 8판이 없다.


**그 전 17시 강의실 PC 점검**(`data_manifest`로 목록 다시 만듦, 10,952줄): 드라이브에서 만든 시각 `2026-11-05T16:20Z`(11-06 01:20 KST) 뒤 파일 없음, 그때까지의 최근 업로드는 `2026-11-05T16:16Z`. 그 뒤 로컬에서 바뀐 `data/`는 `eval/state_generic` 53개 0.79MB(`__pycache__` 포함), `blender_api_5.2` 2,192개 110.8MB뿐이다(**드라이브에 안 올림, 집 PC에서 받는다**, 사용자 "3번은 handoff 에 남겨줘 집에서 받으라고"). `results/20261106/`은 1,633개 165.9MB로 통째로 안 올라갔다. 드라이브의 `state_generic/op_walk.py`는 12,583바이트 옛 판이고 로컬은 18,912바이트라, 올린 뒤 **크기로 새 판인지 확인한다**(같은 이름 폴더를 올리면 둘로 생길 수 있음, 추측). 전체 파일 단위 대조는 이번에도 안 했다(아래 11-05 항목이 그대로 남음). **2026-11-09(월) 강의실 PC에서 한다**(사용자 "다음주 월요일에는 대신 하긴 해야할듯?"). 그 PC의 `data_manifest` 목록과 드라이브 목록을 경로·크기로 맞추며 어림 15-20분(약 5,700개, 안 재 봄)이고 집 PC 목록은 필요 없다. `MANIFEST.tsv`에는 `results/`가 파일별로 안 들어 있어(파일 수 합 11,279가 `data/`와 같음) `results/`는 따로 세어 맞춘다. 집과 강의실을 서로 견주려면 양쪽 목록을 만들어 `--compare`한다.

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
| 공식 파이썬 문서 | 강의실, 집 (드라이브 없음) | `data/blender_api_5.2/` | 받는 법: `mkdir data\blender_api_5.2`, `curl -L -o data\blender_api_5.2\api.zip https://docs.blender.org/api/5.2/blender_python_reference_5_2.zip`, `.venv\Scripts\python data\eval\state_generic\api_to_text.py` |
| 시험 스크립트 11-06 (집 PC 1번에 꼭 필요) | 강의실, 집, 드라이브 | `data/eval/state_generic/` | **폴더 전체**(896KB). 11-06 오전 것과 오후에 고친 `op_walk.py`(6판), `op_walk_v5_커스텀없음.py`, `case_walk.py`, `crash_walk.py`, `flow_walk.py`, `doc_walk.py`, `doc_run.py`, `input_*`, `sim_cause*` 포함. `api_to_text.py`(공식 문서 본문 뽑기)도 들어 있음 |
| 시험 결과 11-06 | 강의실, 집, 드라이브 | `results/20261106/` | 폴더째(162MB, `165659_h8_2_safety_bg` 36MB는 멈춘 실행이라 빼도 됨). 8-2 대조에 `113739_h7_safety_bg`, `122610_h7_safety_window`, `144527_h8_safety_bg`, `144550_h8_safety_window`, `163538_h7_cases`, `165659_flow_walk`가 필요 |
| 시험 결과 11-05 밤 (드라이브에 있음, 강의실 PC에도 받음) | 집, 강의실, 드라이브 | `results/20261105/` | 기록에 숫자로 쓴 것: 191121_crash_walk2, 191735_crash_walk_window, 193217_crash_walk_wide, 193426_crash_walk_wide_line, 193446_crash_walk_wide_bg, 194118_crash_walk_reopen_bg, 194616_crash_walk_reopen_window, 200541_reach_table, 212340_op_walk3_bg, 215835_op_walk3_window, 225533_flow_walk, 225752_flow_walk. 비교용 앞 판: 201233_op_walk, 205827_op_walk2, 214347_op_walk3_window_try, 225247_flow_walk. 안 옮겨도 됨: 190443, 190510, 191518, 200732, 205253, 211823, 214219 |
| 프로토타입 개발셋 | 강의실 | `data/eval/dev30/` | 기록은 `archive/experiment_prototype.md` |
| API 키·벡터·모델 | PC마다 따로 | `data/.env`, `data/vectors/`, `data/models/` | 앞과 같음 |
| 사람 조작 기록 `streams` | **강의실만**(집 PC에 없음) | `%APPDATA%\blender_tutor\streams\` | 183파일 2.8MB, Git·드라이브 밖 |

## 참고

- [실험 기록·체크리스트](docs/experiment.md)(목차), [`bpy` 전체 분석](.scratch/mvp-roundtrip/research/2026-11-05-bpy-전체-분석.md), [`bpy` 작업 상태 지도](.scratch/mvp-roundtrip/research/2026-11-05-bpy-작업상태-지도.md), [범용 시험 계획](.scratch/mvp-roundtrip/research/2026-11-05-작업상태-범용-시험-계획.md), [칸 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류.md), [RNA 밖 이름·계산 값 분류](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-분류-2.md), [칸 후보 초안(낡음)](.scratch/mvp-roundtrip/research/2026-11-05-bpy-칸-후보-초안.md), [개발셋 작업표](.scratch/mvp-roundtrip/dev50-작업표.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [질문 종류 조사](.scratch/mvp-roundtrip/research/2026-11-04-블렌더-질문-종류.md), [경과 [168]-[204]](HISTORY.md), [구조](STRUCTURE.md).
- 검색 흐름 코드: `blender_tutor/answer_engine.py`(`REWRITE_PROMPT`, `answer`, `_rewritten`, `search`, `_widened`), `engine_setup.py`. 공식 API 문서: `https://docs.blender.org/api/5.2/`.
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해. 시험 전에 experiment-checklist 스킬로 체크리스트부터 채워.`
