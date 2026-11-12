# 인수인계

마지막 갱신: 2026-11-12 점심 전 마무리 · Claude Code(Opus 5.5) · 강의실 PC(DESKTOP-J9LV5HK, `C:\WORK\rag_blender_tutor`) · PR #43 병합 전에 씀

## 다음 할 일

1. **사용자 판단: 제품 질문 바꾸기를 2b예시없음 지시문 + 생각 medium으로 바꿀지(티켓35, HISTORY [294]·[295]).** 54문항 본시험에서 충분 59→73/147(+14, 개선15·악화1, 95% 구간 4-26)로 사용자 기준 +12를 넘었다. 제품 방식(먼저 닫힌 1개)으로는 56→75(+19). 대가는 검색어 첫 닫힘 중앙 0.78→1.85초, 90% 3.08초, 질문당 비용 약 1.9배(Haiku라 질문 1000개에 약 $0.37 어림). Claude 권고: 반영하되, 독립 검토가 가능해지는 금요일(11-13) 사용량 초기화 뒤 새 조각 대체 근거 5개 판정을 하위 에이전트로 다시 보고 반영하는 쪽이 더 안전하다. 사용자는 아직 고르지 않았다("잠시 일단 점심 시간이라 전부 마무리 기록해둬").
2. 반영을 고르면: `blender_tutor/answer_engine.py`의 `REWRITE_PROMPT`를 `data/eval/dev50/search_prompt_2b.py`의 `REWRITE_PROMPT_2B`에서 `<examples>` 묶음을 뺀 글로 바꾸고, `blender_tutor/engine_setup.py:26` `REWRITE_EFFORT`("none")와 `:29` `REWRITE_MAX_TOKENS`(600)를 함께 고친다. 생각 토큰이 출력 한도에 포함되어 600이면 잘릴 수 있다(시험은 8000). 한도 값은 본시험 기록의 출력 토큰 분포를 보고 정한다(아직 안 셈). 제품 시간 한도 `settings.rewrite_timeout`과 medium 90% 3.08초도 대조한다. 제품 코드 변경이라 테스트·STRUCTURE.md 갱신을 같은 PR에 넣는다.
3. 남은 문제: Q09(베벨로 쏠려 Apply Scale을 못 찾음)는 세 조건 모두 0/3으로 지시문으로 고쳐지지 않았다. Q45는 후보 나열로 Clear Mask가 빠졌고, 예시있음은 질문에 없는 원인을 지어 넣었다(Q13·Q45). 그 뒤 검색 실험 3·4번(기존2+설정 참고1, 상태 전용) 설계 여부는 이 결과를 반영한 새 기준으로 다시 정한다.
4. 더 뒤의 답 모델/제품 시험: 실제 답 품질·설명서 부재 안내·전체 비용과 시간. 청구서·드라이브 백업·다른 PC 보유 여부는 미확인.

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

- 브랜치 `exp/35-dev-bundle`. 오늘 기록 커밋 `c46eeb1`·`60fe3f7`·`6069fc2`·`3151bce`와 이 인계 커밋을 원격에 푸시한다. [PR #43](https://github.com/sbleeedu1-ai/rag_blender_tutor/pull/43)은 초안·열림·미병합(11-12 확인). main 병합은 사용자 확인 뒤.
- 검증: 세 실행기 무료 점검(통신 차단, 가짜 자료로 5초/전부/먼저1개 분리·예시만 빠짐·조건 순서)을 통과한 뒤 유료 실행. 결과는 기록 줄 수 270/180/486과 `설정.json` 끝 시각·멈춤 없음을 확인했다. 실험 기록 검사 `pytest tests/test_experiment_record.py -q -p no:cacheprovider` 10개 통과. 제품 전체 pytest는 제품 코드를 안 바꿔 오늘 재실행하지 않았다.
- 비용(토큰 단가 계산): 2-a $0.264776, 2-b $0.159542, 본시험 $0.433688(+미확인 예약 $0.016, 오류 1호출). 사용자 "팍팍 여유있게 써라", 실행기 상한 $2.0. 계정 잔액·청구서는 안 봤다.
- 유료 명령(재실행 금지): `data/eval/dev50/search_prompt_2a_run.py --yes`, `search_prompt_2b_run.py --yes`, `search_prompt_main_run.py --yes`. 무료: 인수 없이 실행(점검만), `read_2a.py <폴더>`, `grade_main.py <폴더>`(저장 기록만 읽음).

## Git 밖 자료·다른 PC

- 새 결과 `results/20261112/115859_검색지시문2a/`(9파일·1183601바이트), `122717_검색지시문2b/`(10파일·817260바이트), `123921_검색지시문2본시험/`(16파일·2895138바이트). 각 폴더 `최종파일목록.json`에 크기·SHA256(목록 파일 자신 제외). 본시험 폴더에 `추가기준.json`(새 조각 판정)·`읽을조각_판정영향.json`·`새조각.json`.
- 새 도구 `data/eval/dev50/`: `search_prompt_2a.py`·`search_prompt_2b.py`(지시문), `search_prompt_2a_run.py`·`search_prompt_2b_run.py`·`search_prompt_main_run.py`(실행기), `read_2a.py`·`grade_main.py`(집계·채점). 실행기와 지시문 복사본은 각 결과 폴더에도 있다. 앞선 1·2번 자료와 청크·벡터는 이전 인계대로 필요하다.
- 키는 `data/.env` 또는 환경 변수. 드라이브 업로드는 이번에 하지 않았다. 옮길 때 같은 경로로 두고 파일 수·크기까지 대조한다. 마지막 확인용 자료는 열지 않았다.
- Python 3.12.10·가상 환경 준비됨. 추천 스킬: 제품 반영이면 `tdd`, 기록이면 `handoff`, 추가 시험이면 `experiment-checklist`. 스킬 없이도: HISTORY [294]와 `docs/experiment.md` 맨 끝 절을 읽고 사용자에게 1번 판단부터 묻는다.

## 참고

- [실험 기록](docs/experiment.md)(맨 끝 2-a·2-b·본시험 절) · [결정 이력](HISTORY.md) [290]-[295] · [채점 기준](docs/agents/grading.md) · [검토 처리](docs/agents/review.md)
- [티켓35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md) · [명세](.scratch/mvp-roundtrip/spec.md) · [구조](STRUCTURE.md)
- 공식 가이드: [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) · [Prompting Claude Haiku 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-haiku-5-5)

새 도구에 붙일 첫 문장: AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.
