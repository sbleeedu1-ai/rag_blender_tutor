# 인수인계

마지막 갱신: 2026-10-19 · Claude · 강의실 PC

## 다음 할 일

1. **명세를 구현 티켓으로 쪼개기**: `/to-tickets .scratch/mvp-roundtrip/spec.md`
   - 티켓은 `.scratch/mvp-roundtrip/issues/`에 이어서 15번부터 만든다(01-14는 지도 티켓). 막힘은 `Blocked by:` 줄로 적는다.
   - 쪼개는 순서는 명세 맨 끝 "권하는 구현 순서"를 참고한다(연습 과정 파일 형식과 검사 → 진행 관리 → 자료 준비(무료) → 답 엔진(가짜 모델) → …).
2. 첫 구현 티켓부터 `/tdd`로 진행한다. 새 작업 브랜치에서 한다.

## 지금 상태

- 지도(`.scratch/mvp-roundtrip/map.md`)의 티켓 14개가 모두 닫혔고, 명세 `.scratch/mvp-roundtrip/spec.md`가 `ready-for-agent` 상태다.
- 브랜치: `wayfinder/mvp-map`을 main에 병합하고 원격에 푸시했다. 병합한 브랜치는 로컬과 원격에서 지웠다. `research/*` 브랜치 4개도 로컬과 원격에서 지웠다. 조사 문서 원본은 `archive/research/`에 있다.
- 남은 다른 브랜치: `prototype/01-addon-roundtrip`(애드온 왕복 시제품 코드, 본 구현 때 참고. main에 합치지 않음).
- 테스트: 아직 코드가 없어 테스트도 없다. `AGENTS.md`의 실행·테스트 명령은 자리표시로 남아 있고, 구현에서 정해지면 채운다.

## 모르면 실수할 것

- 티켓 안에 적힌 `research/...` 브랜치 경로는 이제 `archive/research/`의 같은 이름 파일로 읽는다.
- 비용이 드는 작업은 실행 전에 사용자 확인이 필요하다: 초보자 범위 분류, 번역, 임베딩, 생각 수준 실측, 평가 실행.
- `data/`(설명서 원문, 번역 사전, 강사님 기준, 홀드아웃)는 커밋하지 않는다. 다른 PC에는 이 폴더가 없을 수 있다.
- PyYAML이 이 PC에 없다. 연습 과정 파일 작업을 시작할 때 설치해야 한다.

## 사용자가 정해야 할 것

- 강사님 중간 확인 때 물어볼 것: GPT에게 연습 과정 정보를 주지 않는 조건이 괜찮은지.

## 추천 스킬

- `/to-tickets .scratch/mvp-roundtrip/spec.md`: 명세를 막힘 관계가 적힌 티켓 파일로 쪼갠다. 스킬이 없으면 명세의 구현 순서대로 티켓 파일을 하나씩 만들고 `Status: ready-for-agent`를 단다.
- 그다음 `/tdd`: 실패하는 테스트부터 쓰고 구현한다.

## 참고 문서

- 명세 `.scratch/mvp-roundtrip/spec.md`, 지도 `.scratch/mvp-roundtrip/map.md`, 티켓 `.scratch/mvp-roundtrip/issues/`
- 용어집 `CONTEXT.md`, 결정 `docs/adr/`, 경과 `HISTORY.md`
- 조사 원본 `archive/research/`
