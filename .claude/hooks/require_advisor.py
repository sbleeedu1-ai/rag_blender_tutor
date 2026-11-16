"""제품 코드·훅을 고치기 전에 advisor와 상의했는지 보는 훅(PreToolUse, Write·Edit). HISTORY [361] 회고 A.

- 대상: 저장소의 `blender_tutor/`, `addon/`, `.claude/hooks/` 아래 파일. 다른 파일은 보지 않는다.
- 규칙: 세션 기록(transcript_path)에서 마지막 사람 메시지(`origin.kind == "human"`, restore_after_compact.py와 같은 판별) 뒤에
  advisor 호출(`server_tool_use`, name "advisor")이 하나라도 있으면 통과. 결과가 성공이든 오류(overloaded 등)든, 결과 줄이
  안 적혔든 호출만 본다(2026-11-16 이 세션 기록: 호출 68 중 성공 54·오류 2·결과 줄 없음 12).
- 하위 에이전트(입력에 agent_id가 있음)는 advisor가 없어 보지 않는다.
- 지금은 기록만 한다: 막지 않고 판정을 `.claude/hooks/require_advisor.log`에 적는다(막는 방식으로 바꾸기 전에 시점 확인용).
- 못 잡는 것: Bash(sed·heredoc)로 고친 파일, 말로 한 제안. 2026-11-16 지난 기록 재생: 범위 안 쓰기 89개 중 Bash 약 80(어림).
- 하위 에이전트에서 agent_id 키가 실제로 오는지는 확인하지 않았다(재생에서 하위 에이전트의 범위 안 편집은 0건).
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPES = ("blender_tutor", "addon", ".claude/hooks")
LOG = Path(__file__).with_suffix(".log")
CHUNK = 1 << 20  # 끝에서 1MB씩 거슬러 읽는다


def in_scope(file_path: str) -> bool:
    if not file_path:
        return False
    try:
        rel = Path(file_path).resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return any(rel.as_posix() == s or rel.as_posix().startswith(s + "/") for s in SCOPES)


def _is_human(entry: dict) -> bool:
    return (
        entry.get("type") == "user"
        and (entry.get("origin") or {}).get("kind") == "human"
        and not (entry.get("isMeta") or entry.get("isCompactSummary") or entry.get("isSidechain"))
    )


def _has_advisor_call(entry: dict) -> bool:
    content = (entry.get("message") or {}).get("content")
    return isinstance(content, list) and any(
        b.get("type") == "server_tool_use" and b.get("name") == "advisor" for b in content
    )


def lines_from_end(path: Path):
    """기록 파일을 끝에서부터 한 줄씩(덜 적힌 마지막 줄 포함, 읽지 못하는 줄은 건너뜀)."""
    with path.open("rb") as f:
        f.seek(0, 2)
        pos, rest = f.tell(), b""
        while pos > 0:
            step = min(CHUNK, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + rest).split(b"\n")
            rest = parts.pop(0)
            yield from reversed(parts)
        yield rest


def _has_advisor_result(entry: dict) -> bool:
    content = (entry.get("message") or {}).get("content")
    return isinstance(content, list) and any(b.get("type") == "advisor_tool_result" for b in content)


def consulted(transcript: Path) -> dict:
    """마지막 사람 메시지 뒤의 advisor 호출·결과(성공·오류)가 보이는지. human=False면 사람 메시지를 못 찾음."""
    seen = {"call": False, "result": False, "human": False}
    for raw in lines_from_end(transcript):
        if b'"advisor' not in raw and b'"human"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        seen["call"] |= _has_advisor_call(entry)
        seen["result"] |= _has_advisor_result(entry)
        if _is_human(entry):
            seen["human"] = True
            return seen
    return seen


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    if not in_scope(file_path) or payload.get("agent_id"):
        return
    start = time.perf_counter()
    verdict = consulted(Path(payload["transcript_path"]))
    took = time.perf_counter() - start
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tool": payload.get("tool_name"),
            "file": file_path,
            "consulted": verdict,
            "seconds": round(took, 3),
            "keys": sorted(payload),
        }, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
