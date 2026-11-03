# 인수인계

마지막 갱신: 2026-11-03 · Claude Code(Opus 5.5) · 강의실 PC · 브랜치 `chore/delete-confirm-ko`, PR #35 병합 전에 씀(새 세션 확인 끝, 병합만 남음). PR #34는 2026-11-02 병합됐고 브랜치도 지워짐.

## 다음 할 일

1. **PR #35 병합을 사용자에게 묻는다.** 새 세션 확인은 끝났다(HISTORY [146], 네 명령 모두 한국어 설명이 뜸). 병합 뒤 브랜치를 지울 때 브랜치 훅 창도 한 번 보인다.
2. 36(방패 연습 과정) → 34(홀드아웃 20문항, **모두 B 갈래**, HISTORY [138]) → 35 → 37. 순서는 HISTORY [136]. 45(화면 위치 표, 답 조사 겹침)는 35의 고치기 후보. 36은 main에서 새 브랜치로(이 브랜치가 병합되기 전이면 main 기준).
3. 낮은 우선순위: **Win+E(파일 탐색기)를 누르면 도우미 창이 튀어나옴**(원인 미조사, 사용자 "우선순위는 낮은편이라 일단은 핸드오프.md 에 남겨만 둬"). 검 1단계 숫자패드 `.` 감지와 7단계 `위치 바뀜: Z` 감지는 실제 조작으로 확인한 기록이 없음(방패 검수 때 검 1·7단계를 한 번씩 해 보면 됨). 42(집 PC 로컬 트랙)는 나중에.

## 지금 상태와 검증

- 브랜치 `chore/delete-confirm-ko`: 훅 `.claude/hooks/ask_file_delete.py`가 `rm`·`rmdir`·`Remove-Item`(대상마다 무엇인지·되살릴 수 있는지·위치), `git reset --hard`(버려지는 파일), `git clean`(지워질 것)을 묻는다. `.claude/settings.json`에는 이제 훅만 있고 권한 규칙(`permissions.ask`)은 없다. 브랜치 삭제·PR 병합은 브랜치 훅이 맡는다.
- pytest **590 passed**(2026-11-03, 강의실 PC). `git reset --hard`·`git clean` 처리를 빼면 새 시험 2개가 실패함을 돌려 봄.
- 실제 창: 새 세션에서 `rmdir`·`Remove-Item`·`git reset --hard`·`git clean -f` 모두 한국어 설명이 뜸(2026-11-03, 사용자 "ㅇㅇ 잘 뜸"). 끝의 `[settings] … settings.json to update hooks`는 Claude Code 고정 문구.

## 모르면 실수할 것

- **유료**: 도우미 창 질문마다 약 $0.0006([135]). `evaluate run`·`speed_trial`은 `--yes` 없이 멈추고 어림 비용만 보인다.
- **API 키**: 2026-11-02에 키가 만료돼(401 `expired_secret_key`) 사용자가 `data/.env`를 새 키로 바꿈. 도우미는 켜질 때만 키를 읽어, 바꾼 뒤 Blender를 **모두** 닫았다 켜야 한다. 키가 통하는지는 무료인 `GET /v1/models`로 본다.
- 도우미는 Blender를 다시 켜야 새 코드·새 연습 과정 글로 뜬다. 메뉴 이름 사전(`data/menu_names/menu_names.json`)이 없으면 안내 말이 영어로만 나온다. 사전은 이번에 다시 만들었다(무료, `python -m blender_tutor.menu_names …`, 사용법은 그 파일 `main`).
- 연습 과정 YAML에서 목록 줄이 `[[`로 시작하면 문법 오류(course_check가 잡음). `[[이름]]` 바로 뒤 조사는 "~ 칸이"·"~ 버튼을"처럼 피한다.
- 부품을 합치면(Ctrl+J) 재질 없던 부품 몫으로 **빈 재질 칸**이 생긴다(Blender로 확인, [141]). 방패(36)에서도 색을 입히면 같은 일이 생긴다.
- 시간 기록 `%APPDATA%\blender_tutor\timings.jsonl`에 이제 답 글도 남는다(그 전 줄에는 없음). 흐름 기록 `streams\`는 계속 쌓인다.
- 검토 결과는 원래 한 항목씩 글로 보인다(AGENTS.md). 사용자가 방식을 바꾸면 그 말을 따른다.
- 답이 나오는 도중 도우미를 끄면 `RuntimeError: Signal source has been deleted`(알려진 것, [130]). 오류 문구가 뜨면 `%TEMP%\blender_tutor_receiver.log`의 "바깥 서비스 오류" 줄.
- 청크 파일을 다시 만들면 `manual_vectors build --yes`(약 $0.13), 그 뒤 `search_compare full-pool`.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| API 키 | `data/.env` | 옮기지 말고 그 PC에서 새로 넣는다 |
| 검수 기록·막힌 곳 메모 | `data/holdout_raw/검수기록.txt`·`홀드아웃 메모.txt`(이제 개발용, 35), 스냅샷 `data/snapshots/20261102-115913.*` | 백업 안 함. 35를 집 PC에서 하면 옮긴다 |
| 검수 때 채팅 원문·그림 | 강의실 PC `다운로드\클로드 채팅 원문.md`·`클로드 채팅 원문 이미지\`·`1.png`·`2.png` | 저장소 밖. 35 문항 만들 때 필요 |
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 옮기거나 `manual_vectors build --yes`(약 $0.13) |
| 메뉴 이름 사전 | `data/menu_names/menu_names.json` | 옮기거나 `menu_names`로 다시 만듦(무료) |
| 검색 비교 질문 | `data/search_compare/questions/` | 드라이브 백업 확인 안 함. 손으로 만든 것이라 꼭 옮긴다 |
| 결과 원본 | `results/20261029/`·`20261030/`·`20261102/` | 백업 확인 안 함. 숫자는 HISTORY [113]-[135] |

## 추천 스킬과 참고

- 36은 `/implement`(티켓 하나 구현). 스킬 없이: 티켓 36을 읽고 `courses/sword.yaml`을 본보기로 방패 연습 과정 초안을 쓴 뒤 course_check와 pytest를 돌린다.
- [티켓 32](.scratch/mvp-roundtrip/issues/32-검-따라-하기-검수.md), [티켓 36](.scratch/mvp-roundtrip/issues/36-방패-연습-과정.md), [티켓 45](.scratch/mvp-roundtrip/issues/45-화면-위치-표.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [136]-[146]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
