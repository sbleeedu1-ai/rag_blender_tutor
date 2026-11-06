"""시험을 돌리기 전에 목표 검토를 잊지 않게, 기록이 없으면 사용자에게 묻지 않고 실행을 멈춰 Claude에게 상기시키는 훅
(PreToolUse, Bash·PowerShell). HISTORY [212].

- 시험을 띄우는 명령만 본다: `state_generic`의 `*_run.py`를 파이썬으로 실행하거나, `state_generic`의 스크립트를 Blender `--python`으로 넘기는 명령.
- `docs/experiment.md` 마지막 실험 절에 `- [x] 목표 검토:`가 있고 아직 `- [x] 결과:`가 없으면 통과한다. 결과가 적힌 절은 끝난 실험이라 새 절을 요구한다.
- 칸이 채워졌는지만 본다. 답의 내용이나 하위 에이전트를 실제로 돌렸는지는 보지 못한다.
"""

import json
import re
import sys
from pathlib import Path

_PYTHON_RUN = re.compile(r"""python(?:\.exe)?["']?\s+(?:-\S+\s+)*["']?([^\s"';&|]+_run\.py)""", re.IGNORECASE)
_BLENDER_SCRIPT = re.compile(r"""(?:--python|-P)\s+["']?[^\s"']*state_generic""")
_REASON = (
    "[목표 검토 상기] 사용자가 내내 볼 수 없어 이 훅이 대신 멈췄습니다. {problem} "
    "experiment-checklist 스킬대로 기대 결과를 모르는 하위 에이전트에게 최종 목표 원문을 주고 "
    "\"이 시험이 통과할 때와 실패할 때 최종 답이 각각 어떻게 달라지나\"를 물어 답을 그 칸에 적은 뒤 다시 실행하세요. "
    "판정에 쓰지 않는 확인이면 그 칸에 \"판정에 안 씀\"이라고 적고 판정에 쓰지 않습니다."
)


def starts_experiment(command: str, cwd: str) -> bool:
    """명령이 시험을 띄우는지. 읽기·검색처럼 스크립트 이름만 나오는 명령은 해당하지 않는다."""
    if _BLENDER_SCRIPT.search(command):
        return True
    return any((Path(cwd) / found.replace("\\", "/")).parent.name == "state_generic" for found in _PYTHON_RUN.findall(command))


def missing_review(record: str) -> str | None:
    """마지막 실험 절에 빠진 것을 설명하는 글. 시험을 돌려도 되면 None."""
    lines = record.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("### [E")]
    if not starts:
        return "docs/experiment.md에 실험 절이 없습니다."
    section = lines[starts[-1]:]
    if any(line.startswith("- [x] 결과:") for line in section):
        return "마지막 실험 절은 결과까지 적혀 끝났습니다. 새 시험이면 새 절을 쓰고 체크리스트부터 채우세요."
    if not any(line.startswith("- [x] 목표 검토:") for line in section):
        return "마지막 실험 절에 `- [x] 목표 검토:` 칸이 없습니다."
    return None


def decide(command: str, cwd: str, record: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    if not starts_experiment(command, cwd):
        return None
    problem = missing_review(record)
    if problem is None:
        return None
    return {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": _REASON.format(problem=problem)}


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    record = Path(__file__).resolve().parents[2] / "docs" / "experiment.md"
    answer = decide(command, payload.get("cwd") or ".", record.read_text(encoding="utf-8"))
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
