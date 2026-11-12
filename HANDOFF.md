# 인수인계

마지막 갱신: 2026-11-12 최종 자료 점검 · Codex(GPT-6) · 강의실 PC(DESKTOP-J9LV5HK, `C:\WORK\rag_blender_tutor`) · PR #43 병합 전에 씀

## 다음 할 일

1. **답 채점: 오늘 돌린 답 시험 두 판(각 54차례, 1회)을 채점해 새 질문 바꾸기가 실제 답을 낫게 하는지 본다(티켓35, HISTORY [299]-[304]).** 기존 `results/20261112/170115_답시험_기존/`, 새 `results/20261112/170728_답시험_새질문바꾸기/`(2b예시없음 + medium). 프로그램 숫자는 검색 적중 31 → 38/49, 첫 글자 중앙 3.44 → 4.23초. 검색이 달라진 13문항만 메인 세션이 잠정 비교한 경향은 나아짐 4·나빠짐 2·비슷 7(순 +2, [302], 판정에 안 씀). 채점 기준은 `docs/agents/grading.md`. **채점 전에 판정 기준(예: 맞음 몇 개 이상 차이)을 사용자와 정한다.** 1회라 흔들림을 못 가른다는 한계를 함께 적는다. 하위 에이전트 금지([279])는 11-13 사용량 초기화로 풀리는지 사용자에게 먼저 확인한다.
2. 답 모델 개선 순서(사용자 동의 [304]): ① Haiku 답 모델 생각 수준 none → low·medium을 먼저 잰다(싼 쪽). ② 그래도 모자라면 답 모델을 Sonnet 5.5로 바꿔 비교한다(요금 20배, 54문항 답 약 $0.1 → $1.9 어림, 첫 글자 시간 미측정). 근거: 검색 +7이 답 +2로 줄었고 근거를 받고도 안 쓴 답(Q07·Q43)이 있었다. Sonnet 5.5는 thinking disabled가 400이라 끌 때 `between_tools`(claude_model.thinking_for는 아직 disabled만 보냄).
3. 채점 결과가 좋으면 제품 반영: `blender_tutor/answer_engine.py` `REWRITE_PROMPT`를 2b예시없음 글로, `blender_tutor/engine_setup.py` `REWRITE_EFFORT`를 "medium", `REWRITE_MAX_TOKENS`를 2000으로(medium 출력 토큰 99% 759·최대 901). 답 시험 실행기 `data/eval/dev50/answer_new_rewrite_run.py`가 같은 값을 쓴다. 테스트·STRUCTURE.md 갱신을 같은 PR에.
4. 남은 가설(사용자에게 물을 것): 순위 합치기가 소수 검색어의 맞는 조각을 지운다(Q09 상태 전용이 Apply Scale을 짚었지만 합치기에서 밀림, [300]). 질문 바꾸기를 Sonnet으로 바꾸면 Q09를 찾았다(3문항 탐색, [303]). 그 뒤: 설명서 부재 안내·전체 비용과 시간. 청구서·다른 PC 보유 여부는 미확인. 드라이브 최종 대조와 아직 올릴 자료는 아래 `Git 밖 자료·다른 PC`를 본다.

### 오늘 오후 결과 요약

- 본시험 Codex 독립 재판정([296]) +14·+15로 결론 유지. 2b low(예시 있음·없음)는 둘 다 미달, low는 생각을 거의 안 함([297]). medium 재현 +11.
- 결정 모델 길잡이(질문마다 none·medium 고르기): 무료 계산으로 미달([298]).
- 검색 3·4번(설정 참고·상태 전용 섞기): 둘 다 미달([300]).
- 답 시험 1회([301])·13문항 잠정 비교([302]): 위 1번. Sonnet 질문 바꾸기 3문항 시간([303]): 첫 닫힘 none 1.4-1.9초·medium 1.1-1.9초, Q09를 찾음.

## 오늘 한 일과 주의

- 2번 재분석([290]): 수정 지시문의 "해결법을 미리 넣지 않는다"가 정답 쪽 기능 이름을 빼서 덜 찾았다. "의도 유지" 채점은 질문 충실도를 잰 것이지 검색 쓸모가 아니었다.
- 2-a(10문항×9조건, [291]·[292]): 공식 가이드(이유·할 것·예시)를 따른 지시문. 예시가 검색어를 26-29낱말로 늘리고 30낱말 규칙을 자주 넘었다.
- 2-b(10문항×6조건, [293]): 이름 수를 질문 범위에 맞추게 하는 규칙 + 쏠림 이유 + 짧고 긴 예시 섞기. 2b예시있음/none·2b예시없음/medium이 길이와 적중을 함께 지켰다.
- 본시험(54문항×3회×3조건, [294]): 위 1번 결과. 2b예시있음/none은 10문항에선 후보였지만 54문항에선 +2로 미달.
- 채점은 2번 `본문기준.json` + 이번에 처음 나온 (문항, 조각) 126쌍을 메인 세션이 읽어 대체 근거 5개를 더한 것(세 조건 동일 적용). 더하기 전 +12, 더한 뒤 +14라 **낙관적일 수 있음**으로 표시했다.
- **하위 에이전트 금지 유지**(HISTORY [279], 금요일 사용량 초기화까지). 오늘 시험은 모두 독립 검토 없이 자기 검토다. 제품 코드는 바꾸지 않았다.
- 실행 중 백그라운드 "완료" 알림이 실제 파일 상태와 맞지 않은 적이 여러 번 있었다. 결과는 `기록.jsonl` 줄 수와 `설정.json`의 `끝`을 직접 보고 집계한다. 대기에는 Monitor를 쓰면 진행 알림이 맞게 왔다.
- 30낱말 규칙은 10-30 첫 지시문부터 있었고 이유 기록은 없다. 쏠림 근거는 `archive/experiment_E2.md` 검색 가설 1, 길이 시험은 가설 6([171], 효과 없음).

## Git·검증

- 브랜치 `exp/35-dev-bundle`. 이 인계·목록 도구 변경과 검증을 같은 작업 브랜치에 커밋·푸시한다. [PR #43](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/43)은 초안·열림·미병합(11-12 17:31 직접 조회). main 병합은 사용자 확인 뒤.
- 최종 자료 점검: `python -B -m pytest tests/test_data_manifest.py -q -p no:cacheprovider` 6개 통과. 처음 샌드박스 실행은 기존 임시 폴더 권한 때문에 준비 단계 4개가 실패했고, 같은 명령을 권한이 있는 환경에서 다시 실행해 통과했다. `data/manifests/`에 기록이 늘어도 자료 목록이 바뀌지 않는 것과 사용자 지정 원문 폴더의 업로드 제외를 확인했다. 전체 제품 시험은 제품 동작을 바꾸지 않아 추가 실행하지 않았다.
- 검증: 세 실행기 무료 점검(통신 차단, 가짜 자료로 5초/전부/먼저1개 분리·예시만 빠짐·조건 순서)을 통과한 뒤 유료 실행. 결과는 기록 줄 수 270/180/486과 `설정.json` 끝 시각·멈춤 없음을 확인했다. 실험 기록 검사 `pytest tests/test_experiment_record.py -q -p no:cacheprovider` 10개 통과. 제품 전체 pytest는 제품 코드를 안 바꿔 오늘 재실행하지 않았다.
- 비용(토큰 단가 계산): 2-a $0.264776, 2-b $0.159542, 본시험 $0.433688(+미확인 예약 $0.016, 오류 1호출). 사용자 "팍팍 여유있게 써라", 실행기 상한 $2.0. 계정 잔액·청구서는 안 봤다.
- 유료 명령(재실행 금지): `data/eval/dev50/search_prompt_2a_run.py --yes`, `search_prompt_2b_run.py --yes`, `search_prompt_main_run.py --yes`. 무료: 인수 없이 실행(점검만), `read_2a.py <폴더>`, `grade_main.py <폴더>`(저장 기록만 읽음).

## Git 밖 자료·다른 PC

- **마지막으로 올릴 자료(17:32-17:34 드라이브 전수 조회, 17:34:55 로컬 results 수집 기준)**: `results/20261112/` 전체 163파일·28,646,477바이트, `data/eval/dev50/`의 `answer_new_rewrite_run.py`·`search_prompt_34.py`·`search_prompt_34_run.py`·`sonnet_time_probe.py` 4파일·22,472바이트다. 이 마지막 업로드는 아직 확인하지 않았다. 전날까지 일반 자료는 확인된 범위에서 누락·크기 차이 0개이며, 같은 크기라도 내용은 대조하지 않았다. 기존 DC 질문 원문 폴더의 67파일은 조회 한도로 미확인이다.
- 로컬 자료 목록은 `data/MANIFEST.tsv`·`data/MANIFEST_요약.md`, 최신 드라이브·로컬 전체 목록과 올릴 파일의 전체 경로는 `data/manifests/20261112/173151_최종대조/요약.md`와 같은 폴더의 TSV에 있다. 원격 확인분 860폴더·최소 10,932파일, 로컬 원본 자료 19,127파일을 대조했다. 로컬 자료 목록에서 `data/manifests/` 자체는 제외한다. 목록을 드라이브에 올리지 않는 기존 결정은 HISTORY [180]을 참고한다.
- 앞서 `results/20261112/153458_드라이브목록대조/`·`160124_드라이브재점검/`에 있던 기록은 `data/manifests/archive/20261112/` 아래 동명 폴더로 옮겼다. 옛 HISTORY의 경로로 찾지 못하면 새 위치를 본다. 옮긴 목록·보고서 10파일의 크기를 이전 기록과 대조했고, 두 대조 스크립트는 새 위치에서도 저장소 루트를 찾게 고쳤다.
- 오후 새 결과(모두 `results/20261112/`): `144926_독립검토_대체근거/`(Codex 재판정·재채점), `152223_검색지시문2low/`, `160105_어려움분류/`, `164258_검색34번/`, `170115_답시험_기존/`, `170728_답시험_새질문바꾸기/`. 검색 시험 폴더에는 `최종파일목록.json`(크기·SHA256). 새 도구(Git 제외 `data/eval/dev50/`): `search_prompt_low_run.py`, `grade_low.py`, `search_prompt_34.py`·`search_prompt_34_run.py`, `answer_new_rewrite_run.py`, `sonnet_time_probe.py`(유료, 재실행 주의). 결과 `results/20261112/172226_sonnet시간3문항/`.
- 새 결과 `results/20261112/115859_검색지시문2a/`(10파일·1,184,772바이트), `122717_검색지시문2b/`(11파일·818,562바이트), `123921_검색지시문2본시험/`(17파일·2,897,240바이트). 여기 수·크기는 목록 파일 자신을 포함한 현재 폴더 전체다. 각 폴더 `최종파일목록.json`에는 목록 자신을 제외한 파일의 크기·SHA256이 있다. 본시험 폴더에 `추가기준.json`(새 조각 판정)·`읽을조각_판정영향.json`·`새조각.json`.
- 새 도구 `data/eval/dev50/`: `search_prompt_2a.py`·`search_prompt_2b.py`(지시문), `search_prompt_2a_run.py`·`search_prompt_2b_run.py`·`search_prompt_main_run.py`(실행기), `read_2a.py`·`grade_main.py`(집계·채점). 실행기와 지시문 복사본은 각 결과 폴더에도 있다. 앞선 1·2번 자료와 청크·벡터는 이전 인계대로 필요하다.
- 키는 `data/.env` 또는 환경 변수. 드라이브 업로드는 이번에 하지 않았다. 옮길 때 같은 경로로 두고 파일 수·크기까지 대조한다. 마지막 확인용 자료는 열지 않았다.
- Python 3.12.10·가상 환경 준비됨. 추천 스킬: 제품 반영이면 `tdd`, 기록이면 `handoff`, 추가 시험이면 `experiment-checklist`. 스킬 없이도: HISTORY [294]와 `docs/experiment.md` 맨 끝 절을 읽고 사용자에게 1번 판단부터 묻는다.

## 참고

- [실험 기록](docs/experiment.md)(맨 끝 2-a·2-b·본시험 절) · [결정 이력](HISTORY.md) [290]-[305] · [채점 기준](docs/agents/grading.md) · [검토 처리](docs/agents/review.md)
- [티켓35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md) · [명세](.scratch/mvp-roundtrip/spec.md) · [구조](STRUCTURE.md)
- 공식 가이드: [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) · [Prompting Claude Haiku 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5)

새 도구에 붙일 첫 문장: AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.
