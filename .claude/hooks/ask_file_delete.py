"""되살리기 어려운 지우기 명령을 실행하기 전에, 무엇이 사라지고 되살릴 수 있는지 쉬운 말로 묻는 훅
(PreToolUse, Bash·PowerShell). HISTORY [144]·[145].

- rm·rmdir·Remove-Item: 지울 대상마다 파일·폴더인지, git으로 되살릴 수 있는지, 어디에 있는지.
- git reset --hard: 버려지는 고친 내용(파일 목록).
- git clean: 지워지는 git 밖 파일(git clean -n으로 미리 본 목록).
설정의 "ask" 규칙 없이 이 훅만으로 확인 창을 띄운다. 거부는 하지 않는다.
해당 명령이 없으면 아무것도 하지 않는다(출력 없음 = 평소 권한 규칙대로).
"""

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ask_branch_delete import pieces

DELETE_COMMANDS = {"rm", "rmdir", "remove-item"}
# Remove-Item에서 값을 받는 옵션(그 값은 지울 대상이 아니다). -Path·-LiteralPath 뒤 값은 대상이다.
_VALUE_OPTIONS = {"-filter", "-include", "-exclude", "-credential", "-stream"}
SHOWN_AT_MOST = 10
CANNOT = "되살릴 수 없음 (git 기록 없음)"


def targets(words: list[str]) -> list[str] | None:
    """조각 하나가 파일 지우기면 지울 대상 목록, 아니면 None."""
    if not words or words[0].lower() not in DELETE_COMMANDS:
        return None
    found, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif word.startswith("-"):
            skip = word.lower() in _VALUE_OPTIONS
        else:
            found.extend(part for part in word.split(",") if part)  # PowerShell은 a,b로 여러 개를 준다
    return found


def _local_path(text: str, cwd: str) -> Path:
    """Git Bash 모양(/c/WORK/…)·~ 를 이 PC 경로로."""
    text = re.sub(r"^/([a-zA-Z])/", r"\1:/", text)
    path = Path(os.path.expanduser(text))
    return path if path.is_absolute() else Path(cwd) / path


def _git_lines(cwd: Path | str, *args: str) -> list[str] | None:
    """git 명령의 출력 줄들. git 저장소 밖이거나 실패하면 None."""
    done = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=10)
    return done.stdout.splitlines() if done.returncode == 0 else None


def _changed(cwd: Path | str, spec: str) -> list[str]:
    """git에 저장된 뒤 고친 파일들(git에 없는 새 파일은 뺌)."""
    lines = _git_lines(cwd, "status", "--porcelain", "--", spec) or []
    return [line[3:] for line in lines if not line.startswith("??")]


def describe(path: Path) -> tuple[str, str]:
    """대상 하나: (무엇인지, 되살릴 수 있나). path는 있는 것."""
    where, spec = (path, ".") if path.is_dir() else (path.parent, path.name)
    if path.is_dir():
        total = sum(len(files) for _, _, files in os.walk(path))
        kind = f"폴더, 파일 {total}개"
    else:
        kind, total = "파일", 1
    saved = len(_git_lines(where, "ls-files", "--", spec) or [])
    if saved == 0:
        return kind, CANNOT
    changed = len(_changed(where, spec))
    lost = ""
    if changed:
        lost = "마지막 커밋 뒤 고친 내용은 사라짐" if path.is_file() else f"{changed}개 파일은 마지막 커밋 뒤 고친 내용이 사라짐"
    if saved >= total:
        return kind, f"되살릴 수 있음, 단 {lost}" if lost else "되살릴 수 있음 (git에 저장됨)"
    verdict = f"{saved}개만 되살릴 수 있음, {total - saved}개는 git 기록 없음"
    return kind, f"{verdict}; {lost}" if lost else verdict


def removal(names: list[str], cwd: str) -> str:
    """rm·rmdir·Remove-Item 한 조각의 설명."""
    lines = []
    if not names:
        lines.append("- 지울 대상을 명령에서 찾지 못했습니다.")
    expanded = []
    for name in names:
        if re.search(r"[$`]", name):
            expanded.append((name, None))
        elif matches := (glob.glob(str(_local_path(name, cwd))) if any(c in name for c in "*?[") else []):
            expanded.extend((m, Path(m)) for m in matches)  # 와일드카드는 맞는 것마다 따로 설명
        else:
            expanded.append((name, _local_path(name, cwd)))
    for name, path in expanded[:SHOWN_AT_MOST]:
        if path is None:
            lines.append(f"- {name}: 미리 알 수 없음 (경로에 변수가 있음)")
        elif not path.exists():
            lines.append(f"- {name}: 지금 없음 (지워질 것 없음)")
        else:
            kind, verdict = describe(path)
            lines.append(f"- {path.name} ({kind}): {verdict}\n위치: {path.resolve().parent.as_posix()}")
    if len(expanded) > SHOWN_AT_MOST:
        lines.append(f"- 그 밖에 {len(expanded) - SHOWN_AT_MOST}개")
    return "[영구 삭제] 지우면 휴지통에 남지 않습니다.\n" + "\n".join(lines)


def _listed(label: str, names: list[str]) -> str:
    shown = ", ".join(names[:SHOWN_AT_MOST])
    more = f" 외 {len(names) - SHOWN_AT_MOST}개" if len(names) > SHOWN_AT_MOST else ""
    return f"- {label} {len(names)}개: {shown}{more}"


def reset(words: list[str], cwd: str) -> str:
    """git reset --hard 한 조각의 설명."""
    changed = _changed(cwd, ".")
    lines = [_listed("버려지는 파일", changed) if changed else "- 지금 고친 내용이 없어 버려지는 것은 없습니다."]
    lines.append("- git에 없는 새 파일은 그대로 남습니다.")
    target = next((w for w in words[2:] if not w.startswith("-") and w != "HEAD"), None)
    if target:
        lines.append(f"- 지금 브랜치를 {target} 커밋으로 옮깁니다. 그 뒤 커밋은 브랜치에서 안 보이게 됩니다(git reflog로 되찾을 수 있음).")
    return "[고친 내용 버리기] 커밋하지 않은 고친 내용을 되살릴 수 없게 버립니다.\n" + "\n".join(lines)


def clean(words: list[str], cwd: str) -> str:
    """git clean 한 조각의 설명. 같은 범위를 git clean -n으로 미리 본다."""
    options = sorted({c for w in words[2:] if re.fullmatch(r"-[a-zA-Z]+", w) for c in w[1:] if c in "dxX"})
    paths = [w for w in words[2:] if not w.startswith("-")]
    preview = _git_lines(cwd, "clean", "-n", *(f"-{c}" for c in options), "--", *paths)
    if preview is None:
        body = "- 미리 알 수 없음 (git clean -n이 실패함)"
    else:
        gone = [line.removeprefix("Would remove ") for line in preview if line.startswith("Would remove ")]
        body = _listed("지워지는 것", gone) if gone else "- 지워질 것이 없습니다."
    return "[git 밖 파일 지우기] git에 없는 파일을 휴지통 없이 지웁니다. 되살릴 수 없습니다.\n" + body


def section(words: list[str], cwd: str) -> str | None:
    """조각 하나가 이 훅이 묻는 명령이면 그 설명, 아니면 None."""
    if (names := targets(words)) is not None:
        return removal(names, cwd)
    if words[:2] == ["git", "reset"] and "--hard" in words:
        return reset(words, cwd)
    if words[:2] == ["git", "clean"] and not {"-n", "--dry-run"} & set(words):
        return clean(words, cwd)
    return None


def decide(command: str, cwd: str) -> dict | None:
    """훅의 답(hookSpecificOutput) 또는 None(관여하지 않음)."""
    # 나누는 함수는 \ 를 이스케이프로 읽어 C:\WORK 가 C:WORK 가 된다. Windows 경로는 / 로 써도 같은 곳이다.
    parts = pieces(command.replace("\\", "/"))
    sections = [s for p in parts if (s := section(p, cwd))]
    if not sections:
        return None
    others = len(parts) - len(sections)
    if others:
        sections.append(f"(이 줄에는 다른 명령 {others}개도 함께 있습니다.)")
    return {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "\n".join(sections)}


def main() -> None:
    # Windows 기본 글자판(cp949)이 아니라 UTF-8로 주고받는다(한글 경로·이유가 깨지지 않게)
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    command = (payload.get("tool_input") or {}).get("command") or ""
    answer = decide(command, payload.get("cwd") or ".")
    if answer:
        print(json.dumps({"hookSpecificOutput": answer}, ensure_ascii=False))


if __name__ == "__main__":
    main()
