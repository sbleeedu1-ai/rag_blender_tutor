# 인수인계

마지막 갱신: 2026-11-03 · Claude Code(Opus 5.5) · 강의실 PC · 브랜치 `feat/34-holdout` · PR #37 병합 전에 씀. 이어받을 때 PR #37이 병합됐는지 git으로 먼저 본다.

## 다음 할 일

1. PR #37 병합(사용자 확인 뒤). `gh pr checks 37 --watch`로 CI를 기다리고, MERGED를 확인한 뒤에 로컬·원격 브랜치를 지운다(한 단계씩).
2. agent-desktop 시험(사용자 "다 끝나면 한번 테스트 해볼만한 가치는 있어보여서", HISTORY [156]). `npm install -g agent-desktop`은 실행 전에 확인받는다. Blender를 띄우고 `agent-desktop snapshot`으로 Blender 버튼이 접근성 트리에 잡히는지 → 안 잡히면 `--headed`로 키 하나를 눌러 최근 조작(`window_manager.operators`)이 채워지는지 본다. 프로젝트 코드는 바꾸지 않고 결과만 HISTORY에.
3. 티켓 35(개발 30문항, GPT 빈손, 고치기 전 측정 → 고치기 반복) → 37. 45(화면 위치 표)는 35의 고치기 후보.
4. 다음에 도우미를 켤 때 화면으로 볼 것: 방패 [153] 참고값(장식 S 0.15, 손잡이 S 0.12·G Z -0.13), 안내 말 줄바꿈·문단, 1단계 "'단계 ▼'에서 2단계를 골라" 안내, 검 7단계 `위치 바뀜: Z` 감지.
5. 낮은 우선순위: Win+E(파일 탐색기)를 누르면 도우미 창이 튀어나옴(원인 미조사). 42(집 PC 로컬 트랙)는 나중에. 채팅창 그림 띄우기·스크린샷 올리기는 명세 범위 밖([151]-9).
6. 티켓을 모두 끝낸 뒤(사용자 계획, [156]): 이 저장소를 비공개로 복사해 pstack(원본 `cursor/plugins`)으로 에이전트만 돌리고 되돌릴 수 없는 결정만 내려 보기. 준비할 것: `data/`·`.env`는 복사로 안 따라감(벡터 다시 만들면 약 $0.13), 실험용 OpenAI 키와 사용 한도, 확인 훅·AGENTS.md 검토 규칙과 pstack "never-block-on-the-human"이 부딪침, `data/holdout/`·`holdout_work/`는 옮기지 않음.

## 지금 상태와 검증

- 티켓 34 닫음(resolved). 홀드아웃 20문항이 `data/holdout/`에 봉인됨(2026-11-03, 파일 49개, 전체 해시 `b032f169…ca23a8f55`, 다시 계산하는 명령은 HISTORY [155]). 메인 세션은 내용을 보지 않았다.
- 확인(2026-11-03, 강의실 PC): `evaluate run data/holdout/questions.json --name holdout_check`(`--yes` 없이)가 "차례 23개 × 약 $0.00064 = 약 $0.01472(어림)"에서 멈춤 = 형식 통과, 비용 없음. 해시를 따로 다시 계산해 하위 에이전트 보고와 같음. 이번 PR은 기록 문서만 바꿔 pytest·course_check는 다시 돌리지 않았다(직전 PR #36 기준 596 passed, 문제 0개).

## 모르면 실수할 것

- **홀드아웃 열지 않기**: `data/holdout/`·`data/holdout_work/`는 37에서 코드를 동결하기 전까지 열지 않는다(Claude·Codex·사용자 모두). 35에서 고칠 때 보면 홀드아웃의 뜻이 없어진다. 37에서 열기 전에 해시가 같은지 본다. 출처 쏠림·실행 확인 절반은 37에서 열어 보고 아쉬우면 다시 짠다(사용자).
- **스크립트로 한 Blender 조작은 최근 조작 기록에 안 남는다**(창을 띄워도, `event_simulate`도 반응 없음). 그래서 홀드아웃 3문항은 그 칸을 손으로 채웠다.
- **유료**: 도우미 창 질문마다 약 $0.0006([135]). `evaluate run`·`speed_trial`은 `--yes` 없이 멈추고 어림 비용만 보인다.
- **API 키**: 만료되면 401 `expired_secret_key`. 도우미는 켜질 때만 키를 읽어, `data/.env`를 바꾼 뒤 Blender를 **모두** 닫았다 켠다. 키 확인은 무료 `GET /v1/models`.
- 도우미는 Blender를 다시 켜야 새 코드·새 연습 과정 글로 뜬다. 메뉴 이름 사전(`data/menu_names/menu_names.json`)이 없으면 안내 말이 영어로만 나온다.
- **연습 과정 YAML 고치기**: 목록 줄이 `[[`로 시작하면 문법 오류. 안내 말 문단 나눔 `\n\n`은 Git Bash 히어독이나 `python -c`로 넣으면 실제 줄바꿈이 되니 Edit 도구나 Write로 만든 스크립트로 넣는다.
- 방패 안내 숫자는 한 묶음(판 0.07 → 장식 0.15·0.5·0.04 → 손잡이 0.12·-0.13). 앞 숫자를 바꾸면 화면 없는 Blender로 높이를 다시 본다(`shield.yaml` 머리 주석).
- 검토 결과는 원래 한 항목씩 글로 보인다(AGENTS.md). 사용자가 방식을 바꾸면 그 말을 따른다.
- 답이 나오는 도중 도우미를 끄면 `RuntimeError: Signal source has been deleted`(알려진 것, [130]).

## Git 제외 자료 (`data/`·`results/`, 커밋 안 함)

| 자료 | 위치 | 다른 PC에서 |
|---|---|---|
| API 키 | `data/.env` | 옮기지 말고 그 PC에서 새로 넣는다 |
| **홀드아웃 봉인** | `data/holdout/`(49파일) + 작업 자료 `data/holdout_work/` | 백업 안 함. 37을 다른 PC에서 하면 통째로 옮기고 해시를 본다. 잃으면 다시 써야 한다 |
| 검·방패 검수 자료 | `data/review/20261102_검/`·`20261103_방패/` | 백업 안 함. 35 문항 만들 때 필요 |
| 검 검수 기록·막힌 곳 메모 | `data/holdout_raw/`(이제 개발용, 35), 스냅샷 `data/snapshots/20261102-115913.*` | 백업 안 함 |
| 설명서 벡터(115MB) | `data/vectors/manual_text-embedding-3-large.npz` + `.json` | 옮기거나 `manual_vectors build --yes`(약 $0.13) |
| 메뉴 이름 사전 | `data/menu_names/menu_names.json` | 옮기거나 `menu_names`로 다시 만듦(무료) |
| 검색 비교 질문 | `data/search_compare/questions/` | 손으로 만든 것이라 꼭 옮긴다 |
| 결과 원본 | `results/20261029/`·`20261030/`·`20261102/` | 백업 확인 안 함. 숫자는 HISTORY [113]-[135] |

## 추천 스킬과 참고

- 35는 `/implement`가 아니라 평가 문항 만들기 + 유료 측정이라, 티켓 35 Comments와 명세 "평가" 절을 먼저 읽는다. 스킬 없이: 개발 30문항을 만들고, 어림 비용을 보여 확인받은 뒤 `evaluate run --yes`로 고치기 전을 잰다.
- [티켓 34](.scratch/mvp-roundtrip/issues/34-홀드아웃-10문항-쓰고-봉인.md), [티켓 35](.scratch/mvp-roundtrip/issues/35-유료-개발-평가와-GPT-빈손.md), [티켓 37](.scratch/mvp-roundtrip/issues/37-유료-홀드아웃-실행.md), [티켓 45](.scratch/mvp-roundtrip/issues/45-화면-위치-표.md), [명세](.scratch/mvp-roundtrip/spec.md), [구조](STRUCTURE.md), [경과 [155]-[156]](HISTORY.md).
- 새 세션 첫 문장: `AGENTS.md와 HANDOFF.md를 읽고 '다음 할 일' 1번부터 이어서 해.`
