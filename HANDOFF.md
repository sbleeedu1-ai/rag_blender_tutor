# 인수인계

마지막 갱신: 2026-11-13 오후(PR #46 병합 뒤) · Claude Code(Opus 5.5) · 집 Mac(`/Volumes/mac_ssd/proj/rag_blender_tutor`) · PR #43 병합 전에 씀

## 11-13 상태 (답 채점 끝)

- 답 시험 두 판 채점 완료([308], `docs/experiment.md` 맨 끝 "답 채점 설계·결과·판정·실행 뒤 점검"). 판정(advisor) **가를 수 없음**: 1차 D +3(구간 −3 - +10), 2차 +2, 채점자 불일치 15.7%. 원자료 `results/20261113/094504_답시험_채점/`.
- 사용자 범위: "채점까지만 해", 판정은 "advisor에게 판단을 맡겨". 제품 코드는 바꾸지 않았다.
- 실행 뒤 독립 검토(Sonnet) 끝, 판정 그대로, 처리 표는 `docs/experiment.md` 맨 끝. 눈여겨볼 것: D 전부가 `고른 분야`가 두 판에서 달라진 19문항에서 나왔다(나머지 35문항 D 0, 결과 본 뒤 설명).

## 11-13 오후: Mac에서 도우미·애드온 돌게 하기 (끝, PR #46 병합)

- [PR #46](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/46) main에 병합(cab5ba8), `feat/mac-support`는 로컬·원격 지움, 이 브랜치에 main을 당겨옴. 기록 HISTORY [312]-[316], 티켓 47(Windows 같은 깜빡임)·48(README에 권한과 보내는 자료 설명), 둘 다 needs-triage.
- 지금 Mac 동작: 창 동작은 ADR-0001 그대로. 도우미는 앱 묶음 `BlenderTutorHelper.app`(애드온 폴더 안)으로 `open`해 켜서 권한이 도우미에만 잡힌다. 손쉬운 사용 권한을 처음 한 번만 묻고(표시 파일 `~/Library/Application Support/blender_tutor/accessibility_asked`), 있으면 누름을 붙잡아 Blender로 돌아올 때 깜빡이지 않는다. 입력 모니터링·로컬 네트워크는 묻지 않는다. 프로젝트가 바깥 SSD라 '제거 가능한 볼륨'은 허용해야 도우미가 켜진다.
- 검증: Mac pytest 730, Windows CI 통과(d146408), 사용자 눈 확인(깜빡임 0/14, 권한 창). 강의실 Windows PC에서는 다시 확인하지 않음(receiver 서버 바꿈은 Windows에도 감).

## 다음 할 일

1. (끝남, [310]·[311]) 기준 빈곳: ① 곁가지 사실 오류는 틀림 유지 ② 한국어 화면에서 영어 이름만 쓰면 부분(`grading.md` 3절). 함께 나온 제품 변경 "질문에 영어로 쓴 메뉴 이름은 영어(한국어)"는 PR #45로 main 병합(7046091) 뒤 이 브랜치로 가져옴(6fbbc56, pytest 728 통과). 남은 것: 모델이 `[[ ]]`로 감싸지 않아 영어만 남는 답의 원인(안 잼).
2. 답 모델 개선(사용자 동의 [304], advisor도 이것을 먼저 권함): ① Haiku 답 모델 생각 수준 none → low·medium을 잰다(유료, 실행 전 사용자 확인). ② 모자라면 Sonnet 5.5 답 모델(요금 20배, 54문항 답 약 $0.1 → $1.9 어림). Sonnet 5.5는 thinking disabled가 400이라 끌 때 `between_tools`(claude_model.thinking_for는 아직 disabled만 보냄). 근거: 검색 적중이 새로 생긴 10문항에서도 맞음이 0 → 1로만 늘었다([308]).
3. 돈 안 드는 확인(판정에 안 씀, 하고 싶으면 사용자에게 묻고): ① 분야 고르기가 질문 바꾸기 결과를 쓰는지 코드로 본다(19문항 몰림의 원인) ② 갈린 17답 중 기존 판 13답의 이유 읽기 ③ `답.jsonl` 검색 결과로 원인 칸 세기 ④ Sonnet 채점자 폭을 [E2] 648답 재채점으로 재기(구독 사용량 큼).
4. **보류**: 새 질문 바꾸기 제품 반영(`answer_engine.py` `REWRITE_PROMPT` 2b예시없음, `engine_setup.py` `REWRITE_EFFORT` medium·`REWRITE_MAX_TOKENS` 2000). 답이 나아진 근거가 없고 첫 글자 +0.79초 비용은 확실하다. 2번 뒤 다시 볼지 정한다.
5. 남은 가설(사용자에게 물을 것): 순위 합치기가 소수 검색어의 맞는 조각을 지운다(Q09, [300]). Sonnet 질문 바꾸기는 Q09를 찾았다([303]). 그 뒤: 설명서 부재 안내·전체 비용과 시간. 드라이브 마지막 업로드는 아래 `Git 밖 자료·다른 PC`.

## 주의

- **채점 묶음의 `풀이.json`은 채점자가 쓰는 폴더(공유 스크래치패드 포함) 밖에 둔다.** 이번에 채점자 스크립트 자리에 옮겨 두어 둘이 이름을 봤다(읽은 호출 0, 작업 기록 전수 확인). 채점자 여럿이 스크래치패드를 같이 쓰면 임시 스크립트가 서로 덮이니 채점자마다 하위 폴더를 지시문에 정해 준다.
- Mac 경로: Blender `/Volumes/mac_ssd/Applications/Blender.app/Contents/MacOS/Blender`(5.2.4), 파이썬 `.venv/bin/python`. 두 PC 경로 짝은 `AGENTS.md`(PR #44, [307]). 이 Mac에는 `data/blender_api_5.2/`가 없다.
- 백그라운드 "완료" 알림을 믿지 말고 결과 파일을 직접 센다(이번엔 채점 파일마다 표 36줄 확인).

## Git·검증

- 브랜치 `exp/35-dev-bundle`, [PR #43](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/43) 초안·미병합. 11-13에 main(PR #44 a2716e1, PR #45 7046091)을 이 브랜치로 병합(4122458, 6fbbc56). main 병합은 사용자 확인 뒤.
- 11-13 채점: 묶음 `data/eval/dev50/answer_grade_pack.py`(Git 제외, 무료), 집계 `results/20261113/094504_답시험_채점/집계.py`(무료, 출력 `집계_출력.txt`). 가짜 판정으로 집계 무료 점검 뒤 실제 집계. 제품 pytest는 제품 코드를 안 바꿔 돌리지 않음(PR #44 세션이 Mac에서 717 통과 보고).
- 최종 자료 점검: `python -B -m pytest tests/test_data_manifest.py -q -p no:cacheprovider` 6개 통과. 처음 샌드박스 실행은 기존 임시 폴더 권한 때문에 준비 단계 4개가 실패했고, 같은 명령을 권한이 있는 환경에서 다시 실행해 통과했다. `data/manifests/`에 기록이 늘어도 자료 목록이 바뀌지 않는 것과 사용자 지정 원문 폴더의 업로드 제외를 확인했다. 전체 제품 시험은 제품 동작을 바꾸지 않아 추가 실행하지 않았다.
- 검증: 세 실행기 무료 점검(통신 차단, 가짜 자료로 5초/전부/먼저1개 분리·예시만 빠짐·조건 순서)을 통과한 뒤 유료 실행. 결과는 기록 줄 수 270/180/486과 `설정.json` 끝 시각·멈춤 없음을 확인했다. 실험 기록 검사 `pytest tests/test_experiment_record.py -q -p no:cacheprovider` 10개 통과. 제품 전체 pytest는 제품 코드를 안 바꿔 오늘 재실행하지 않았다.
- 비용(토큰 단가 계산): 2-a $0.264776, 2-b $0.159542, 본시험 $0.433688(+미확인 예약 $0.016, 오류 1호출). 사용자 "팍팍 여유있게 써라", 실행기 상한 $2.0. 계정 잔액·청구서는 안 봤다.
- 유료 명령(재실행 금지): `data/eval/dev50/search_prompt_2a_run.py --yes`, `search_prompt_2b_run.py --yes`, `search_prompt_main_run.py --yes`. 무료: 인수 없이 실행(점검만), `read_2a.py <폴더>`, `grade_main.py <폴더>`(저장 기록만 읽음).

## Git 밖 자료·다른 PC

- **마지막으로 올릴 자료(17:32-17:34 드라이브 전수 조회, 17:34:55 로컬 results 수집 기준)**: `results/20261112/` 전체 163파일·28,646,477바이트, `data/eval/dev50/`의 `answer_new_rewrite_run.py`·`search_prompt_34.py`·`search_prompt_34_run.py`·`sonnet_time_probe.py` 4파일·22,472바이트다. 이 마지막 업로드는 아직 확인하지 않았다. 전날까지 일반 자료는 확인된 범위에서 누락·크기 차이 0개이며, 같은 크기라도 내용은 대조하지 않았다. 기존 DC 질문 원문 폴더의 67파일은 조회 한도로 미확인이다.
- 로컬 자료 목록은 `data/MANIFEST.tsv`·`data/MANIFEST_요약.md`, 최신 드라이브·로컬 전체 목록과 올릴 파일의 전체 경로는 `data/manifests/20261112/173151_최종대조/요약.md`와 같은 폴더의 TSV에 있다. 원격 확인분 860폴더·최소 10,932파일, 로컬 원본 자료 19,127파일을 대조했다. 로컬 자료 목록에서 `data/manifests/` 자체는 제외한다. 목록을 드라이브에 올리지 않는 기존 결정은 HISTORY [180]을 참고한다.
- 앞서 `results/20261112/153458_드라이브목록대조/`·`160124_드라이브재점검/`에 있던 기록은 `data/manifests/archive/20261112/` 아래 동명 폴더로 옮겼다. 옛 HISTORY의 경로로 찾지 못하면 새 위치를 본다. 옮긴 목록·보고서 10파일의 크기를 이전 기록과 대조했고, 두 대조 스크립트는 새 위치에서도 저장소 루트를 찾게 고쳤다.
- 11-13 새 결과 `results/20261113/094504_답시험_채점/`(Git 제외, 드라이브 안 올림). 11-12 오후 새 결과(모두 `results/20261112/`): `144926_독립검토_대체근거/`(Codex 재판정·재채점), `152223_검색지시문2low/`, `160105_어려움분류/`, `164258_검색34번/`, `170115_답시험_기존/`, `170728_답시험_새질문바꾸기/`. 검색 시험 폴더에는 `최종파일목록.json`(크기·SHA256). 새 도구(Git 제외 `data/eval/dev50/`): `search_prompt_low_run.py`, `grade_low.py`, `search_prompt_34.py`·`search_prompt_34_run.py`, `answer_new_rewrite_run.py`, `sonnet_time_probe.py`(유료, 재실행 주의). 결과 `results/20261112/172226_sonnet시간3문항/`.
- 새 결과 `results/20261112/115859_검색지시문2a/`(10파일·1,184,772바이트), `122717_검색지시문2b/`(11파일·818,562바이트), `123921_검색지시문2본시험/`(17파일·2,897,240바이트). 여기 수·크기는 목록 파일 자신을 포함한 현재 폴더 전체다. 각 폴더 `최종파일목록.json`에는 목록 자신을 제외한 파일의 크기·SHA256이 있다. 본시험 폴더에 `추가기준.json`(새 조각 판정)·`읽을조각_판정영향.json`·`새조각.json`.
- 새 도구 `data/eval/dev50/`: `search_prompt_2a.py`·`search_prompt_2b.py`(지시문), `search_prompt_2a_run.py`·`search_prompt_2b_run.py`·`search_prompt_main_run.py`(실행기), `read_2a.py`·`grade_main.py`(집계·채점). 실행기와 지시문 복사본은 각 결과 폴더에도 있다. 앞선 1·2번 자료와 청크·벡터는 이전 인계대로 필요하다.
- 키는 `data/.env` 또는 환경 변수. 드라이브 업로드는 이번에 하지 않았다. 옮길 때 같은 경로로 두고 파일 수·크기까지 대조한다. 마지막 확인용 자료는 열지 않았다.
- Python 3.12.10·가상 환경 준비됨. 추천 스킬: 제품 반영이면 `tdd`, 기록이면 `handoff`, 추가 시험이면 `experiment-checklist`. 스킬 없이도: HISTORY [294]와 `docs/experiment.md` 맨 끝 절을 읽고 사용자에게 1번 판단부터 묻는다.

## 참고

- [실험 기록](docs/experiment.md)(맨 끝 2-a·2-b·본시험 절) · [결정 이력](HISTORY.md) [290]-[308] · [채점 기준](docs/agents/grading.md) · [검토 처리](docs/agents/review.md)
- [티켓35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md) · [명세](.scratch/mvp-roundtrip/spec.md) · [구조](STRUCTURE.md)
- 공식 가이드: [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) · [Prompting Claude Haiku 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5)

새 도구에 붙일 첫 문장: AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.
