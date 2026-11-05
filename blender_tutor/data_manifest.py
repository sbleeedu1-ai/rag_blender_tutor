"""Git에 없는 data/·results/를 다른 PC·드라이브와 빠르게 견주기 위해, 파일 크기까지 적은 목록을 만들고 대조한다.

만들기: .venv\\Scripts\\python -m blender_tutor.data_manifest
대조:   .venv\\Scripts\\python -m blender_tutor.data_manifest --compare <다른 쪽 MANIFEST.tsv>

- data/MANIFEST_요약.md: 폴더별 파일 수·크기·가장 새 날짜, results/ 날짜별 수·크기. 먼저 이것만 본다.
- data/MANIFEST.tsv: 파일별 경로·크기·수정 시각. 요약이 다를 때 --compare로 대조한다.
크기와 시각만 본다(내용을 읽지 않는다). 크기가 같은 수정은 크기로 못 가른다.
홀드아웃 폴더는 파일 이름을 적지 않고 묶음 한 줄(수·크기)만 적는다.
"""

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_NAME = "MANIFEST_요약.md"
LIST_NAME = "MANIFEST.tsv"
SEALED = ("holdout", "holdout_work", "holdout_pool", "holdout_raw", "archive/holdout_20261103")  # 내용이 드러나지 않게 수·크기만
NOT_UPLOADED = ("models", "hf_cache")  # 다시 받을 수 있어 드라이브에 올리지 않는 폴더(HISTORY [159], 사용자가 이 둘을 뺀 나머지를 올림)


@dataclass(frozen=True)
class Entry:
    path: str  # data/ 기준, / 구분. 홀드아웃은 폴더 이름 + "/*"
    count: int
    size: int
    modified: str


def _sealed_of(relative: str) -> str | None:
    return next((name for name in SEALED if relative == name or relative.startswith(name + "/")), None)


def scan(data: Path) -> list[Entry]:
    """data/ 아래를 훑는다. 목록 파일 자신은 넣지 않는다."""
    entries: list[Entry] = []
    sealed: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for path in sorted(data.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(data).as_posix()
        if relative in (SUMMARY_NAME, LIST_NAME):
            continue
        stat = path.stat()
        group = _sealed_of(relative)
        if group is not None:
            sealed[group].append((stat.st_size, stat.st_mtime))
        else:
            entries.append(Entry(relative, 1, stat.st_size, _stamp(stat.st_mtime)))
    for group, files in sealed.items():
        entries.append(Entry(group + "/*", len(files), sum(s for s, _ in files), _stamp(max(t for _, t in files))))
    return sorted(entries, key=lambda e: e.path)


def _stamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d %H:%M")


def _megabytes(size: int) -> str:
    return f"{size / 1_000_000:,.1f} MB"


def summary_text(entries: list[Entry], results: Path) -> str:
    folders: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        folders[entry.path.split("/")[0] if "/" in entry.path else "(data 바로 아래)"].append(entry)
    lines = [f"# data·results 목록 요약 ({datetime.now():%Y-%m-%d %H:%M} 만듦)", "",
             "다른 쪽과 같은지 볼 때 이 표부터 견준다. 다르면 `python -m blender_tutor.data_manifest --compare <다른 쪽 MANIFEST.tsv>`.",
             "이 목록은 만든 때의 모습이다. 올릴 때는 자료를 다 올린 뒤 이 두 파일을 다시 만들어 마지막에 올린다.", "",
             "## data", "", "| 폴더 | 파일 수 | 크기 | 가장 새 날짜 | 비고 |", "|---|---:|---:|---|---|"]
    for name, items in sorted(folders.items()):
        note = "드라이브에 안 올림" if name in NOT_UPLOADED else ("이름 없이 수·크기만 포함" if any(e.path.endswith("/*") for e in items) else "")
        lines.append(f"| {name} | {sum(e.count for e in items):,} | {_megabytes(sum(e.size for e in items))} | {max(e.modified for e in items)} | {note} |")
    lines += ["", "## results(날짜 폴더째 올린다)", "", "| 날짜 | 파일 수 | 크기 |", "|---|---:|---:|"]
    if results.is_dir():
        for day in sorted(p for p in results.iterdir() if p.is_dir()):
            files = [p for p in day.rglob("*") if p.is_file()]
            lines.append(f"| {day.name} | {len(files):,} | {_megabytes(sum(p.stat().st_size for p in files))} |")
    return "\n".join(lines) + "\n"


def write_list(entries: list[Entry], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("경로\t파일 수\t크기\t수정 시각\n")
        for e in entries:
            f.write(f"{e.path}\t{e.count}\t{e.size}\t{e.modified}\n")


def read_list(path: Path) -> dict[str, Entry]:
    rows = path.read_text(encoding="utf-8").splitlines()[1:]
    parsed = (row.split("\t") for row in rows)
    return {p: Entry(p, int(c), int(s), m) for p, c, s, m in parsed}


def compare(mine: dict[str, Entry], other: dict[str, Entry]) -> dict[str, list[str]]:
    """크기·파일 수가 다른 것과 한쪽에만 있는 것. 다른 줄에는 어느 쪽이 새것인지 적는다."""
    uploaded = lambda path: path.split("/")[0] not in NOT_UPLOADED
    result = {"여기에만": [p for p in sorted(mine) if p not in other and uploaded(p)],
              "다른 쪽에만": [p for p in sorted(other) if p not in mine and uploaded(p)], "다름": []}
    for path in sorted(set(mine) & set(other)):
        a, b = mine[path], other[path]
        if (a.size, a.count) != (b.size, b.count):
            newer = "여기가 새것" if a.modified > b.modified else "다른 쪽이 새것" if b.modified > a.modified else "시각 같음"
            result["다름"].append(f"{path}: 여기 {a.count}개 {a.size} ({a.modified}) / 다른 쪽 {b.count}개 {b.size} ({b.modified}) → {newer}")
    return result


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description="data/·results/ 목록 만들기와 대조")
    parser.add_argument("--compare", type=Path, help="다른 쪽 MANIFEST.tsv")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    data = root / "data"
    entries = scan(data)
    if args.compare is not None:
        found = compare({e.path: e for e in entries}, read_list(args.compare))
        for title, rows in found.items():
            print(f"[{title}] {len(rows)}개")
            for row in rows:
                print(" ", row)
        return 0
    write_list(entries, data / LIST_NAME)
    (data / SUMMARY_NAME).write_text(summary_text(entries, root / "results"), encoding="utf-8")
    print(f"{data / SUMMARY_NAME}\n{data / LIST_NAME} ({len(entries):,}줄)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
