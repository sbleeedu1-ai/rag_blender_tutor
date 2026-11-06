"""직접 입력한 /compact 직전에 기록이 빠졌는지 보고, 빠졌으면 한 번 막는 훅(PreCompact). HISTORY [193].

- 오늘 만든 `results/<오늘>/` 폴더가 `docs/experiment.md`에 없음, 커밋하지 않은 파일, HANDOFF 날짜가 오늘이 아님을 본다.
- 하나라도 있으면 종료 코드 2로 막고 까닭을 보인다. 10분 안에 다시 입력하면 통과한다(막다른 길을 만들지 않는다).
- 자동 압축은 막지 않는다. 막으면 대화 한도를 복구하던 요청이 실패할 수 있다(공식 문서, 2026-11-06 확인).
- 이 PreCompact 훅은 경고만 보여 줄 길이 없다. 일반 출력은 디버그 로그로 가고, 막을 때의 stderr만 사용자에게 보인다.
"""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PASS_WINDOW = timedelta(minutes=10)


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    return done.stdout


def _unwritten_results(repo: Path, now: datetime) -> list[str]:
    folder = repo / "results" / now.strftime("%Y%m%d")
    if not folder.is_dir():
        return []
    record = repo / "docs" / "experiment.md"
    written = record.read_text(encoding="utf-8") if record.exists() else ""
    return [f"실험 기록에 없는 오늘 결과 폴더: results/{folder.name}/{item.name}" for item in sorted(folder.iterdir()) if item.is_dir() and item.name not in written]


def _stale_handoff(repo: Path, now: datetime) -> list[str]:
    handoff = repo / "HANDOFF.md"
    if not handoff.exists():
        return ["HANDOFF.md가 없습니다"]
    updated = next((line for line in handoff.read_text(encoding="utf-8").splitlines() if line.startswith("마지막 갱신:")), "")
    return [] if now.strftime("%Y-%m-%d") in updated else [f"HANDOFF 날짜가 오늘이 아닙니다: {updated[:40] or '갱신 줄 없음'}"]


def missing_records(repo: Path, now: datetime) -> list[str]:
    """빠진 기록을 사람이 읽을 문장 목록으로 돌려준다."""
    unsaved = [f"커밋하지 않은 파일: {line[3:]}" for line in _git(repo, "-c", "core.quotepath=false", "status", "--porcelain").splitlines()]
    return _unwritten_results(repo, now) + unsaved + _stale_handoff(repo, now)


def decide(cwd: Path, now: datetime) -> str | None:
    """막을 까닭 글, 통과면 None. Claude가 하위 폴더에 있어도 저장소 맨 위를 본다."""
    repo = Path(_git(cwd, "rev-parse", "--show-toplevel").strip())
    missing = missing_records(repo, now)
    # 저장소 밖으로 나가지 않고 커밋되지도 않는 자리에 "한 번 막았다"를 적는다
    marker = repo / _git(repo, "rev-parse", "--git-dir").strip() / "compact_check_asked"
    asked = datetime.fromisoformat(marker.read_text(encoding="utf-8")) if marker.exists() else None
    if asked is not None:
        marker.unlink()
    if not missing or (asked is not None and now - asked <= PASS_WINDOW):
        return None
    marker.write_text(now.isoformat(), encoding="utf-8")
    return "[컴팩트 전 기록 확인] 아래 기록이 빠져 한 번 막았습니다. 그대로 진행하려면 10분 안에 /compact를 다시 입력하세요.\n" + "\n".join(f"- {item}" for item in missing)


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    payload = json.load(sys.stdin)
    if payload.get("trigger") != "manual":
        return
    message = decide(Path(payload.get("cwd") or "."), datetime.now())
    if message:
        print(message, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
