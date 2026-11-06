"""기록이 빠진 채 세션이 끝나면 다음 세션에 알리는 훅(SessionEnd, SessionStart). HISTORY [198].

- /clear와 세션 종료는 공식 문서상 막을 길이 없다. 그래서 끝날 때 빠진 기록과 대화 기록 파일 위치를 적어 두고,
  /clear 직후나 다음에 새로 열 때 Claude에게 넘긴다(일반 출력이 새 세션의 문맥이 된다).
- 적어 두는 곳은 커밋되지 않는 .git 안이다. 한 번 알리면 지운다.
"""

import json
import secrets
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_records_before_compact import _git, missing_records  # noqa: E402

NOTE = "session_end_missing.json"


def _top(cwd: Path) -> Path:
    return Path(_git(cwd, "rev-parse", "--show-toplevel").strip())


def _note(repo: Path) -> Path:
    return repo / _git(repo, "rev-parse", "--git-dir").strip() / NOTE


def save_note(cwd: Path, transcript: str, reason: str, now: datetime) -> None:
    """빠진 기록이 있으면 적어 두고, 없으면 지난번 알림을 치운다."""
    repo = _top(cwd)
    note = _note(repo)
    missing = missing_records(repo, now)
    if missing:
        note.write_text(json.dumps({"missing": missing, "transcript": transcript, "reason": reason, "time": now.isoformat(timespec="minutes")}, ensure_ascii=False), encoding="utf-8")
    elif note.exists():
        note.unlink()


def take_note(cwd: Path) -> str:
    """적어 둔 알림을 글로 돌려주고 지운다. 없으면 빈 글자."""
    note = _note(_top(cwd))
    if not note.exists():
        return ""
    data = json.loads(note.read_text(encoding="utf-8"))
    note.unlink()
    lines = "\n".join(f"- {item}" for item in data["missing"][:50])
    return f"[직전 세션 기록 확인] {data['time']}에 세션이 끝날 때({data['reason']}) 다음 기록이 빠져 있었다. 첫 답에서 사용자에게 알리고 채운다.\n{lines}\n대화 기록 파일: {data['transcript']}"


def unsaved_now(cwd: Path, now: datetime) -> str:
    """지금 커밋하지 않은 파일. 끝날 때 훅이 실패했어도 잡으려고 시작할 때 직접 본다.
    HANDOFF 날짜는 보지 않는다. 매일 첫 세션마다 울리면 습관처럼 넘기게 된다."""
    items = [item for item in missing_records(_top(cwd), now) if item.startswith("커밋하지 않은 파일")]
    if not items:
        return ""
    return "[지금 커밋하지 않은 파일] 첫 답에서 사용자에게 알린다.\n" + "\n".join(f"- {item}" for item in items[:50])


def start_notice(cwd: Path, now: datetime) -> str:
    """새 세션에 보낼 글. Claude의 문맥과 사용자 화면 양쪽에 보내, Claude가 말을 안 해도 사용자가 본다."""
    text = "\n\n".join(part for part in (take_note(cwd), unsaved_now(cwd, now)) if part)
    if not text:
        return ""
    # 훅만 아는 번호. Claude가 인용하면 파일을 스스로 찾은 것이 아니라 이 알림을 받았다는 증명이 된다
    number = f"알림 번호 {secrets.token_hex(3)}"
    order = (f"사용자의 첫 메시지가 무엇이든, 어떤 도구를 쓰기 전에 첫 답 맨 앞에 \"{number}\"와 아래 글을 그대로 인용한다. "
             "받지 못한 것처럼 넘어가지 않는다. 그다음 빠진 기록을 사용자와 함께 채운다.")
    return json.dumps({"systemMessage": f"{number}\n{text}", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": f"{order}\n\n{text}"}}, ensure_ascii=False)


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    cwd = Path(payload.get("cwd") or ".")
    if payload.get("hook_event_name") == "SessionEnd":
        save_note(cwd, payload.get("transcript_path", ""), payload.get("reason", ""), datetime.now())
    else:
        print(start_notice(cwd, datetime.now()), end="")


if __name__ == "__main__":
    main()
