# 이슈 트래커: 로컬 마크다운

이 저장소의 이슈와 명세는 `.scratch/` 아래 마크다운 파일로 관리한다.

> GitHub 원격(`origin`)을 연결하더라도 코드 보관용이다. **GitHub Issues에는 이슈를 만들지 않는다.** `gh issue create`, `gh label create`를 쓰지 않는다.

## 규칙

- 기능 하나에 폴더 하나: `.scratch/<기능-slug>/`
- 명세는 `.scratch/<기능-slug>/spec.md`
- 구현 이슈는 티켓 하나에 파일 하나: `.scratch/<기능-slug>/issues/<NN>-<slug>.md`, `01`부터 번호를 매긴다. 여러 티켓을 한 파일에 몰아 쓰지 않는다.
- 분류 상태는 각 이슈 파일 위쪽의 `Status:` 줄에 적는다(값은 `triage-labels.md` 참고).
- 댓글과 논의 기록은 파일 맨 아래 `## Comments` 제목 밑에 이어 적는다.

## 스킬이 "이슈 트래커에 올려라"라고 할 때

`.scratch/<기능-slug>/` 아래에 새 파일을 만든다(폴더가 없으면 만든다).

## 스킬이 "관련 티켓을 가져와라"라고 할 때

지정된 경로의 파일을 읽는다. 보통 사용자가 경로나 이슈 번호를 직접 알려 준다.

## Wayfinding 작업

`/wayfinder`가 사용한다. **map**은 파일 하나이고, 티켓마다 **child** 파일이 하나씩 있다.

- **Map**: `.scratch/<effort>/map.md` (Notes / Decisions-so-far / Fog 본문)
- **Child 티켓**: `.scratch/<effort>/issues/NN-<slug>.md`, `01`부터 번호를 매기고 본문에 질문을 적는다. `Type:` 줄에 티켓 종류(`research`/`prototype`/`grilling`/`task`), `Status:` 줄에 `claimed`/`resolved`를 적는다.
- **막힘(Blocking)**: 위쪽에 `Blocked by: NN, NN` 줄을 둔다. 적힌 파일이 모두 `resolved`가 되면 풀린다.
- **Frontier**: `.scratch/<effort>/issues/`에서 열려 있고, 막히지 않았고, 아무도 맡지 않은 파일을 찾는다. 번호가 가장 앞선 것을 먼저 잡는다.
- **Claim**: 작업 전에 `Status: claimed`로 바꾸고 저장한다.
- **Resolve**: `## Answer` 제목 아래 답을 적고 `Status: resolved`로 바꾼 뒤, `map.md`의 Decisions-so-far에 요약과 링크를 덧붙인다.
