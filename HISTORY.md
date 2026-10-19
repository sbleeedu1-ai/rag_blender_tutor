# HISTORY

시간순 기록. 지난 항목은 고치지 않고 새 번호로 덧붙인다. 사용자가 고른 것은 말 그대로 인용하고, 자세한 내용은 링크로 대신한다.

### [1] 2026-10-19 · 저장소와 에이전트 스킬 설정

- 제안: Claude가 `/setup-matt-pocock-skills`로 이슈 위치(로컬 마크다운)·기본 분류 라벨·안내 파일(`AGENTS.md` + `@AGENTS.md`만 담은 `CLAUDE.md`)을 제안. 설치된 Matt 스킬은 용어집을 `GLOSSARY.md`로 부르지만 new-setup 템플릿은 `CONTEXT.md`라는 차이를 Claude가 지적
- 사용자 선택:
  - 이슈 위치 "로컬 마크다운", 라벨 "기본값 사용", 안내 파일 "내 github new-setup 을 참고해줘"
  - 용어집 이름 "CONTEXT.md", new-setup의 `.claude/settings.json`도 복사
  - `docs/agents/`를 지난 프로젝트(highschool_board_test)의 한글판에서 가져온 것: "그럼 그대로 두고"
  - "github 도 공개 저장소로 하나 만들자 readme.md 는 없이 만들고"
  - 제안서: "내부 참고용이라 안 올릴거야 gitignore 적어두자", `.gitignore`는 "최소안으로"
  - "다 했으면 push 하고 보호 켜자"
- 결과: 공개 저장소 `sbleeedu1-ai/rag_blender_tutor` 생성(README 없음), 커밋 이메일은 GitHub 비공개 주소(이 저장소만). `AGENTS.md`·`CLAUDE.md`·`.claude/settings.json`·`docs/agents/`·`.gitignore`(`.env`, `data/`, `docs/산출물/` 제외)·이 `HISTORY.md`를 첫 커밋으로 main에 푸시하고 main 브랜치 보호를 켬
- 남은 것: `AGENTS.md`의 `<...>` 칸(프로젝트 설명, 실행·테스트 명령, 프로젝트 규칙)
