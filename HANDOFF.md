# 인수인계

마지막 갱신: 2026-11-02 · Claude Code(Opus 5.5) · 강의실 PC · **PR #34 병합 전에 씀**(브랜치 `feat/32-sword-review`). 이어받을 때 `git fetch` 뒤 PR #34가 main에 병합됐는지 먼저 본다. 병합 안 됐으면 이 브랜치에서 이어 한다(32가 아직 열려 있음).

## 다음 할 일

1. 32 마무리: **사용자 결정 3개**(티켓 32 Comments 맨 아래 후보 A·B·C, 권하는 답 있음)를 받고, **사용자가 바뀐 단계(1-7·9·11)를 다시 검수**한다. 볼 것: 단계 끝 흐름이 자연스러운지(물음·'다음'·구분선), 1단계 숫자패드 .이 '다음' 없이 감지되는지, 11단계 Material Preview의 한국어 화면 글자, 10단계 "양(Amount)". 그 뒤 고칠 것을 고치고 티켓을 닫아 PR #34 병합(확인받고).
2. 36(방패 연습 과정) → 34(홀드아웃 20문항, **모두 B 갈래**, HISTORY [138]) → 35 → 37. 순서는 HISTORY [136].
3. 낮은 우선순위: **Win+E(파일 탐색기)를 누르면 도우미 창이 튀어나옴**(검수 때 사용자 발견, 원인 미조사, 사용자 "우선순위는 낮은편이라 일단은 핸드오프.md 에 남겨만 둬"). 42(집 PC 로컬 트랙)는 나중에.

## 지금 상태와 검증

- 브랜치 `feat/32-sword-review`, 커밋 3개(`5db76a9` 계획 메모, `0d9ee0f` 구현, `a07ecb1` 검토 반영) + 이 HANDOFF 커밋, 모두 원격에 올림. PR #34 열림, 병합 안 함.
- 바꾼 것: 안내 말의 `[[메뉴 이름]]` → 한국어 화면 글자(`course_desk`·`menu_names`), 단계 끝 흐름(`progress`), 구분선(`helper_window`), 새 감지 `위치 바뀜`(`conditions`), `courses/sword.yaml`·`_common.yaml`, 회귀 테스트 `tests/test_sword_review.py` + `tests/fixtures/`. 자세히는 HISTORY [138]·[139], 티켓 32 Comments.
- pytest **581 passed**, course_check 문제 0개(2026-11-02, 강의실 PC). 애드온은 바꾸지 않아 애드온 자체 시험은 돌리지 않았다. 실제 도우미 창으로는 아직 안 봤다(다시 검수 몫).
- 코드 검토 19개(규칙 10·명세 9)는 사용자 말("대부분 검수하고 처리하고 중요한 후보 3개만")대로 Claude가 처리, 처리·보류 이유는 티켓 32.

## 모르면 실수할 것

- **유료**: 도우미 창 질문마다 약 $0.0006([135]). 연습 과정 글이 바뀌어 도우미 첫 실행 때 연습 과정 임베딩을 한 번 새로 만든다(아주 작음). `evaluate run`·`speed_trial`은 `--yes` 없이 멈추고 어림 비용만 보인다.
- 도우미는 Blender를 다시 켜야 새 코드·새 연습 과정 글로 뜬다. 메뉴 이름 사전(`data/menu_names/menu_names.json`)이 없으면 안내 말이 영어로만 나온다.
- 연습 과정 글에서 `[[이름]]` 바로 뒤 조사는 바뀐 글이 영어로 끝나 영어 이름에 맞춘다. 한국어 이름에 "를"이 든 것(모디파이어를 추가)은 "~ 순서로"·"~ 칸을"처럼 쓴다. YAML 줄이 `[[`로 시작하거나 글 안에 `"`가 있으면 문법 오류가 난다(course_check가 잡음).
- 테스트 자료는 `tests/fixtures/`에 둔다. `.gitignore`의 `data/`가 `tests/data/`도 막는다.
- 흐름 기록 `%APPDATA%\blender_tutor\streams\`는 계속 쌓인다(검수 흐름은 `20261102-114759.jsonl`). 흐름 전체를 바뀐 연습 과정에 다시 넣으면 버튼 누름이 어긋난다(후보 B).
- 검토 결과는 원래 한 항목씩 글로 보인다(AGENTS.md). 이번처럼 사용자가 방식을 바꾸면 그 말을 따른다.
- 답이 나오는 도중 도우미를 끄면 `RuntimeError: Signal source has been deleted`(알려진 것, [130]). 오류 문구가 뜨면 `%TEMP%\blender_tutor_receiver.log`의 "바깥 서비스 오류" 줄.
- 청크 파일을 다시 만들면 `manual_vectors build --yes`(약 $0.13), 그 뒤 `search_compare full-pool`.

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| 검수 기록·막힌 곳 메모 | `data/holdout_raw/검수기록.txt`·`홀드아웃 메모.txt`(이제 개발용, 35), 스냅샷 `data/snapshots/20261102-115913.*` | 백업 안 함. 집 PC에서 32를 이을 거면 옮긴다 |
| 검수 때 채팅 원문·그림 | 강의실 PC `다운로드\클로드 채팅 원문.md`·`클로드 채팅 원문 이미지\`·`1.png`·`2.png` | 저장소 밖. 35 문항 만들 때 필요 |
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 옮기거나 `manual_vectors build --yes`(약 $0.13) |
| 메뉴 이름 사전 | `data/menu_names/menu_names.json` | 옮기거나 `menu_names`로 다시 만듦. 없으면 안내 말이 영어로만 |
| 검색 비교 질문 | `data/search_compare/questions/` | 드라이브 백업 확인 안 함. 손으로 만든 것이라 꼭 옮긴다 |
| 결과 원본 | `results/20261029/`·`20261030/`·`20261102/` | 백업 확인 안 함. 숫자는 HISTORY [113]-[135] |

## 추천 스킬과 참고

- 다시 검수는 사용자가 Blender에서 하는 일. Claude 몫은 후보 결정을 받고 지적을 받아 고치기(`/implement`는 새 티켓을 열 때). 스킬 없이: 티켓 32 Comments 맨 아래를 읽고 후보 A·B·C부터 묻는다.
- [티켓 32](.scratch/mvp-roundtrip/issues/32-검-따라-하기-검수.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [136]-[139]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
