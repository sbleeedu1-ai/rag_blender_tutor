"""설정 값 읽기에 쓰는 표 만들기(HISTORY [270]): 애드온이 Blender 안에서 읽는 state_tables/rules.json·factory.json을 만든다.

- rules.json: 칸(타입.칸 이름) → 갈래(갈래 표 전부: 뺌·문맥도 있어야 애드온이 '표에 없음'과 가른다).
- factory.json: 공장값 표(규칙 12·13의 Baseline 모양: exact·loose·shaky) 가운데, 공장값과 견주는 칸(규칙 13에서 갈래 1·3·5·6과 표에 없는 칸)의 줄만.
입력은 가설 13의 갈래 표(여섯갈래_최종.csv)와 공장값 표(h12_view_run.py가 창 있는 Blender 두 번으로 만든 것).
둘 다 Blender에서 읽은 칸 이름·값이라 저장소에 커밋한다. 돈이 들지 않는다.

실행: .venv\\Scripts\\python -m blender_tutor.state_tables build --groups <여섯갈래_최종.csv> --factory <공장값표.json>
"""

import argparse
import csv
import json
import re
from pathlib import Path

from blender_tutor.paths import PROJECT

TABLES = PROJECT / "state_tables"
# 공장값과 다를 때만 보내는 갈래(h13_patch.rule13: 4·뺌·2·1-a·문맥이 아니면 견준다. 1은 세 덩어리 1번 칸 밖이면 견줌)
COMPARED = ("1", "3", "5", "6")
# 값에 표를 만든 PC의 사용자 폴더가 든 줄(파일 브라우저 책갈피·애셋 라이브러리·확장 폴더·임시 폴더 등)은 뺀다.
# 공개 저장소에 사용자 이름이 올라가지 않게 하고, 다른 PC에서는 어차피 맞지 않는 값이라서다. 빠진 칸은 공장값을 모르는 칸이라 늘 보낸다
PERSONAL = re.compile(r"[A-Za-z]:\\{1,4}Users\\{1,4}|/Users/|/home/", re.IGNORECASE)


def rules_from(rows: list[dict]) -> dict[str, str]:
    """갈래 표 줄(칸·갈래) → 칸의 갈래(전부)."""
    return {row["칸"]: row["갈래"] for row in rows}


def compared(site: str, groups: dict[str, str]) -> bool:
    """공장값과 견주는 칸인가: COMPARED 갈래, 또는 갈래 표에 없는 칸(규칙 13의 '표에 없음'도 공장값과 다를 때 보냈다)."""
    group = groups.get(site)
    return group is None or group in COMPARED


def factory_from(base: dict, groups: dict[str, str]) -> dict:
    """공장값 표에서 견주는 칸의 줄만. groups는 갈래 표 전체(뺌·문맥 포함)라야 '표에 없음'을 바로 가린다."""
    def keep(key: str, values=()) -> bool:
        return compared(key.rsplit("|", 1)[1], groups) and not any(PERSONAL.search(value) for value in values)

    return {
        "exact": {k: v for k, v in base["exact"].items() if keep(k, v)},
        "loose": {k: v for k, v in base["loose"].items() if keep(k, v)},
        "shaky": sorted(k for k in base["shaky"] if keep(k)),
    }


def build(groups_csv: Path, factory_json: Path, out: Path = TABLES) -> tuple[Path, Path]:
    """두 표를 out에 쓴다(덮어씀: 같은 입력이면 같은 결과). 쓴 경로를 돌려준다."""
    with groups_csv.open(encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    groups = {row["칸"]: row["갈래"] for row in rows}
    base = json.loads(factory_json.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    rules_path, factory_path = out / "rules.json", out / "factory.json"
    rules_path.write_text(json.dumps(rules_from(rows), ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8", newline="\n")
    factory_path.write_text(json.dumps(factory_from(base, groups), ensure_ascii=False, sort_keys=True), encoding="utf-8", newline="\n")
    return rules_path, factory_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="애드온이 설정 값을 읽을 때 쓰는 표(rules.json·factory.json)를 만듭니다.")
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build", help="갈래 표와 공장값 표로 state_tables/의 두 표를 만든다")
    make.add_argument("--groups", type=Path, required=True, help="여섯갈래_최종.csv")
    make.add_argument("--factory", type=Path, required=True, help="공장값표.json")
    make.add_argument("--out", type=Path, default=TABLES, help="쓸 폴더")
    args = parser.parse_args(argv)
    for path in build(args.groups, args.factory, args.out):
        print(f"{path}: {path.stat().st_size:,}바이트")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
