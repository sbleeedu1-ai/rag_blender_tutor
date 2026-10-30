# 인수인계

마지막 갱신: 2026-10-30 · Claude Code(Opus 5.5) · 강의실 PC · **PR #30 병합 전에 씀**(브랜치 `feat/rewrite-flow`, 사용자가 자동 검사 통과 뒤 병합을 승인). 이어받을 때 `git fetch` 뒤 PR #30이 main에 병합됐는지 먼저 본다. 병합됐으면 main에서 새 브랜치로.

## 다음 할 일

1. 티켓 43은 끝났다(코드 검토 [129], 도우미 창 실측 [130], 티켓 `Status: resolved`), PR #30.
2. 그다음 티켓 33(실제 답변 모델, [33번](.scratch/mvp-roundtrip/issues/33-유료-생각-수준-실측.md) Comments 먼저) → 42(집 PC) → 32 → 35 → 36·37.

## 지금 상태와 검증

- 도우미 검색(커밋 `2f09cea`): 질문(+직전 질문·단계 이름·방금 조작을 참고 줄로) → luna(none, 긴 지시) 3번 동시 → 먼저 온 1개의 영어 검색어 → large 임베딩 → 뜻 검색 상위 8개. 5초 안에 하나도 안 오거나 모두 실패하면 오류 표시로 멈춤. 예열은 `BLENDER_TUTOR_WARM_UP=1`일 때만. 답변은 아직 가짜.
- 정한 근거([127]): 긴 지시 3개 합침 86.7%·중앙 2.04초·2초 넘음 58% / 먼저 온 1개 85.3%·1.71초·3% / 짧은 지시 77.3% / fast는 약 10%만 빨라 안 씀.
- pytest **546 passed**(2026-10-30, 커밋 `1baeccf`, 강의실 PC). 이후 커밋은 문서만 바꿨다. 연습 과정 검사는 돌리지 않았다(연습 과정 파일을 바꾸지 않음).
- 진짜 luna 3문항(도우미 창 없이 엔진만, [128]): 셋 다 정답 쪽 1위, 끝까지 4.20·2.16·1.66초.

## 모르면 실수할 것

- **유료**: 이제 진짜 임베딩 엔진은 질문마다 luna 3번을 부른다(질문당 약 $0.00025). 도우미 창과 `evaluate run --embedding text-embedding-3-large`가 해당된다. `search_compare rewrite`·`flow`·`run`(large)은 `--yes` 없이 멈춘다. 오늘 쓴 유료는 약 $0.056(오전 $0.03 + 측정 $0.023 + 3문항 $0.0008 + 도우미 창 실측 약 $0.002).
- 첫 요청이 느리다: 측정·3문항 모두 맨 첫 요청에서 luna 3.5-4.4초, 임베딩 1.9-2.0초가 나왔다. 도우미 창 실측([130])도 첫 질문 2.7-3.0초, 이후 약 1.9초. 원인 미확인. 예열이 이것을 줄이는지는 재지 않았다(사용자가 지금 수치를 받아들임).
- 답이 나오는 도중 도우미를 끄면 기록에 `RuntimeError: Signal source has been deleted`(`helper.py`의 `_QtWindowSide.show`)가 남고 그 질문의 시간 기록 줄이 빠진다. 알려진 것이고 해롭지 않아 고치지 않았다([130]). 끄는 순간이 아닌데 이 오류가 나면 다른 문제다.
- "잠시 뒤 다시"가 뜨면 `%TEMP%\blender_tutor_receiver.log`의 "바깥 서비스 오류" 줄로 원인(시간 초과·키·이상한 답)을 본다([129] 3번).
- 무료 모드(stand_in 낱말 세기)는 메뉴 이름 덧붙이기가 빠져 근거 목록이 엉뚱하게 나온다. 창 동작 확인용으로만 본다.
- Git Bash 헤어독(`<<'EOF'`)으로 파이썬 코드를 넘기면 문자열 속 `\\n`이 실제 줄바꿈으로 들어가 문법 오류가 났다(오늘 세 번). 코드 수정은 Edit 도구를 쓴다.
- luna 응답 시간은 시간대마다 다르다. 비교는 같은 실행 안에서 한다.
- 도우미 창은 OpenAI 키(`OPENAI_API_KEY` 또는 `data/.env`)가 있어야 답한다. Anthropic 키는 없다.
- 청크 파일을 다시 만들면 설명서 벡터가 안 맞아 도우미가 멈춘다 → `manual_vectors build --yes`(약 $0.13), 그 뒤 `search_compare full-pool`.
- 검토 결과는 한 항목씩 사용자 판단(AGENTS.md). 사용자는 Blender 기능을 깊이 모른다. 청크 정답 여부 같은 판단은 Claude가 근거와 권하는 답을 낸다.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 옮기거나 `manual_vectors build --yes`(약 $0.13) |
| 검색 비교 질문·묶음·DB | `data/search_compare/` | **드라이브 백업 전**. 질문 파일은 손으로 만든 것이라 꼭 옮긴다. 설명서 전체 묶음과 large DB는 `search_compare full-pool`로 다시 만든다 |
| 결과 원본 | `results/20261029/`, `results/20261030/`(오늘 `124302_flow_short_vs_long`·`124708_flow_fast_small` 추가) | 백업 전. 숫자는 HISTORY [113]-[128]에 있다 |
| 로컬 임베딩·생성 모델 | `data/models/` | `local_embeddings prepare`, `prototype/local_llm/llm_bench.sh`로 다시 받음 |

## 추천 스킬과 참고

- 1번은 사용자가 고른 방식대로(`code-review` 스킬 또는 직접). 스킬 없이: `git diff main..feat/rewrite-flow`를 AGENTS.md "코드 작성"과 티켓 43 완료 조건에 대어 보고, 항목마다 근거·지금 동작·권하는 답을 낸다.
- [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [122]-[128]](HISTORY.md), [티켓 43](.scratch/mvp-roundtrip/issues/43-도우미-검색을-새-흐름으로.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
