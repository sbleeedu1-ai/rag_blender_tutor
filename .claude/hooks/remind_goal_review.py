"""시험을 돌리기 전에 절차를 잊지 않게, 빠진 것이 있으면 사용자에게 묻지 않고 실행을 멈춰 Claude에게 상기시키는 훅
(PreToolUse, Bash·PowerShell). HISTORY [212]·[213].

- 시험을 띄우는 명령만 본다: `state_generic`의 `*_run.py`를 파이썬으로 실행하거나, `state_generic`의 스크립트를 Blender `--python`으로 넘기는 명령.
- `docs/experiment.md` 마지막 절: `- [x] 목표 검토:`가 있고 `- [x] 결과:`가 아직 없어야 한다. 결과가 적힌 절은 끝난 실험이라 새 절을 요구한다.
- `목표 검토` 칸이 있는 앞 절: 실행 뒤 칸을 모두 채웠어야 한다. 이 칸이 없는 옛 절은 보지 않는다.
- 세션 기록: 두 검토마다 프롬프트에 절 제목과 칸 이름이 든 하위 에이전트 호출이 있어야 한다. 이 PC의 최근 세션만 찾는다.
- `목표 검토` 칸에 "판정에 안 씀"이라고 적은 절은 칸만 보고 세션 기록과 실행 뒤 칸은 보지 않는다.
- 호출이 있었는지만 본다. 답의 내용이나 칸에 그대로 옮겼는지는 보지 못한다.
"""

import json
import re
import sys
from pathlib import Path

_PYTHON_RUN = re.compile(r"""python(?:\.exe)?["']?\s+(?:-\S+\s+)*["']?([^\s"';&|]+_run\.py)""", re.IGNORECASE)
_BLENDER_SCRIPT = re.compile(r"""(?:--python|-P)\s+["']?[^\s"']*state_generic""")
_GOAL = "목표 검토"
_AFTER_REVIEW = "실행 뒤 독립 검토"
_AFTER_CELLS = ("결과", "목적 다시 보기", "실험 점검", "결과를 본 뒤 바꾼 것", "넘어간 것", _AFTER_REVIEW)
_NOT_FOR_VERDICT = "판정에 안 씀"
_RECENT_SESSIONS = 10  # 세션 기록 하나가 10MB가 넘을 수 있어 훅 제한 시간 안에 읽을 만큼만 본다
_HOW_TO_GOAL = (
    "experiment-checklist 스킬대로 기대 결과를 모르는 하위 에이전트에게 최종 목표 원문을 주고 "
    "\"이 시험이 통과할 때와 실패할 때 최종 답이 각각 어떻게 달라지나\"를 물어 답을 그 칸에 적은 뒤 다시 실행하세요. "
    f"판정에 쓰지 않는 확인이면 그 칸에 \"{_NOT_FOR_VERDICT}\"이라고 적고 판정에 쓰지 않습니다."
)


def starts_experiment(command: str, cwd: str) -> bool:
    """명령이 시험을 띄우는지. 읽기·검색처럼 스크립트 이름만 나오는 명령은 해당하지 않는다."""
    if _BLENDER_SCRIPT.search(command):
        return True
    return any((Path(cwd) / found.replace("\\", "/")).parent.name == "state_generic" for found in _PYTHON_RUN.findall(command))


def _sections(record: str) -> list[list[str]]:
    lines = record.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("### [E")]
    return [lines[start:end] for start, end in zip(starts, starts[1:] + [len(lines)])]


def _cell(section: list[str], name: str) -> str | None:
    return next((line for line in section if line.startswith(f"- [x] {name}:")), None)


def _title(section: list[str]) -> str:
    return section[0].removeprefix("### ")


def _needs_after_cells(section: list[str]) -> bool:
    goal = _cell(section, _GOAL)
    return goal is not None and _NOT_FOR_VERDICT not in goal


def _unasked(section: list[str], cell: str, prompts: list[str]) -> str | None:
    if any(_title(section) in prompt and cell in prompt for prompt in prompts):
        return None
    return f"세션 기록에 `{_title(section)}`의 `{cell}` 하위 에이전트 호출이 없습니다. 프롬프트에 절 제목과 칸 이름을 넣어 불러 주세요(이 PC의 최근 {_RECENT_SESSIONS}개 세션만 찾습니다)."


def _unfinished(section: list[str], prompts: list[str]) -> str | None:
    """실행이 끝난 절에서 빠진 것."""
    if not _needs_after_cells(section):
        return None
    missing = [name for name in _AFTER_CELLS if _cell(section, name) is None]
    if missing:
        return f"앞 시험 `{_title(section)}`의 실행 뒤 칸이 비었습니다: {', '.join(missing)}. 그것부터 채우세요."
    return _unasked(section, _AFTER_REVIEW, prompts)


def missing_step(record: str, prompts: list[str]) -> str | None:
    """시험 전에 빠진 절차를 설명하는 글. 시험을 돌려도 되면 None."""
    sections = _sections(record)
    if not sections:
        return "docs/experiment.md에 실험 절이 없습니다."
    last = sections[-1]
    for section in sections[:-1]:
        if problem := _unfinished(section, prompts):
            return problem
    if _cell(last, "결과"):
        return _unfinished(last, prompts) or "마지막 실험 절은 결과까지 적혀 끝났습니다. 새 시험이면 새 절을 쓰고 체크리스트부터 채우세요."
    if _cell(last, _GOAL) is None:
        return f"마지막 실험 절에 `- [x] {_GOAL}:` 칸이 없습니다. {_HOW_TO_GOAL}"
    if _needs_after_cells(last):
        if problem := _unasked(last, _GOAL, prompts):
            return f"{problem} {_HOW_TO_GOAL}"
    return None


def agent_prompts(transcript_path: str) -> list[str]:
    """이 프로젝트의 최근 세션 기록에서 하위 에이전트에게 준 프롬프트를 모은다."""
    folder = Path(transcript_path).parent
    logs = sorted(folder.glob("*.jsonl"), key=lambda log: log.stat().st_mtime, reverse=True)[:_RECENT_SESSIONS]
    prompts = []
    for log in logs:
        # 지금 쓰이는 세션은 마지막 줄이 덜 적혀 있을 수 있어 완성된 줄만 읽는다
        complete = log.read_text(encoding="utf-8", errors="replace").rpartition("\n")[0]
        for line in complete.splitlines():
            if '"Agent"' not in line:
                continue
            content = (json.loads(line).get("message") or {}).get("content")
            if isinstance(content, list):
                prompts += [part["input"].get("prompt", "") for part in content if isinstance(part, dict) and part.get("type") == "tool_use" and part.get("name") == "Agent"]
    return prompts


def decide(command: str, cwd: str, record_path: Path, transcript_path: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    if not starts_experiment(command, cwd):
        return None
    problem = missing_step(record_path.read_text(encoding="utf-8"), agent_prompts(transcript_path))
    if problem is None:
        return None
    reason = f"[실험 절차 상기] 사용자가 내내 볼 수 없어 이 훅이 대신 멈췄습니다. {problem}"
    return {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    record = Path(__file__).resolve().parents[2] / "docs" / "experiment.md"
    answer = decide(command, payload.get("cwd") or ".", record, payload["transcript_path"])
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
