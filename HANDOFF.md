# 인수인계

마지막 갱신: 2026-11-03 · Claude Code(Opus 5.5) · 강의실 PC · 브랜치 `chore/delete-confirm-ko`, PR 아직 안 만듦(확인 창 시험이 끝나면 만든다). PR #34는 2026-11-02 병합됐고 브랜치도 지워짐.

## 다음 할 일

1. **새 세션에서 `rm` 확인 창이 훅의 한국어 설명으로 뜨는지 본다**(HISTORY [144]). 임시 폴더에 버릴 파일을 하나 만들고 `rm`으로 지운다. 확인 창에 "[파일 지우기 확인] 휴지통으로 가지 않고 바로 지웁니다. …"가 보이면 성공. 사용자에게 화면을 물어본다(Claude는 창을 볼 수 없음).
   - 성공하면: 설정의 `Bash(rmdir *)`·`PowerShell(Remove-Item *)`도 빼고 다음 세션에서 같은 방법으로 본다(사용자 "일단 rm 부터 확인하자"). 그 뒤 훅의 임시 기록 줄(`ask_file_delete_debug.log`에 쓰는 세 줄, `main` 안 "임시 확인용")을 빼고 PR을 만든다.
   - 창이 아예 안 뜨면(확인 없이 지워짐): 바로 사용자에게 알리고 `Bash(rm *)` 규칙을 되돌린다.
   - 귀찮으면 뺀다(사용자 "너무 귀찮으면 빼게"): 설정의 훅 한 줄을 빼고 `Bash(rm *)`를 되돌린다.
2. 36(방패 연습 과정) → 34(홀드아웃 20문항, **모두 B 갈래**, HISTORY [138]) → 35 → 37. 순서는 HISTORY [136]. 45(화면 위치 표, 답 조사 겹침)는 35의 고치기 후보. 36은 main에서 새 브랜치로(이 브랜치가 병합되기 전이면 main 기준).
3. 낮은 우선순위: **Win+E(파일 탐색기)를 누르면 도우미 창이 튀어나옴**(원인 미조사, 사용자 "우선순위는 낮은편이라 일단은 핸드오프.md 에 남겨만 둬"). 검 1단계 숫자패드 `.` 감지와 7단계 `위치 바뀜: Z` 감지는 실제 조작으로 확인한 기록이 없음(방패 검수 때 검 1·7단계를 한 번씩 해 보면 됨). 42(집 PC 로컬 트랙)는 나중에.

## 지금 상태와 검증

- 브랜치 `chore/delete-confirm-ko`: 새 훅 `.claude/hooks/ask_file_delete.py`(`rm`·`rmdir`·`Remove-Item` 대상마다 파일/폴더, git으로 되살릴 수 있나를 붙여 묻는다), 시험 `tests/test_file_delete_hook.py` 5개, `.claude/settings.json`(훅 한 줄 더함, `Bash(rm *)` 규칙 뺌). `git reset --hard`·`git clean`은 "파일 지우기"가 아니라 넣지 않음.
- pytest **588 passed**(2026-11-03, 강의실 PC). Windows 경로 시험은 `\`를 `/`로 바꾸는 줄을 빼면 실패(1 failed)함을 돌려 봄.
- 이 세션에서 본 것: 설정 규칙과 훅이 함께 물으면 창에는 규칙 문구("Ask rule Bash(rm *) overrides auto mode…")만 보인다. 훅은 세션 중에 더해도 바로 돌았다(임시 기록으로 확인). 그런데 설정 파일에서 `Bash(rm *)`를 빼도 이 세션에서는 여전히 규칙 문구가 떴다. 다른 설정 파일 네 곳에는 그 규칙이 없고 사용자가 `/permissions`에서 아직 남아 있는 것을 확인 → 권한 규칙은 세션을 시작할 때만 읽는 것으로 본다.

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
- [티켓 32](.scratch/mvp-roundtrip/issues/32-검-따라-하기-검수.md), [티켓 36](.scratch/mvp-roundtrip/issues/36-방패-연습-과정.md), [티켓 45](.scratch/mvp-roundtrip/issues/45-화면-위치-표.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [136]-[143]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
