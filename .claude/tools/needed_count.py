"""답 모델에 '답에 꼭 필요한 설명서 조각'이 넘어갔는지 센다(04 지표 2, docs/plan/04 2·3절). 돈 안 듦, 모델 호출 없음.

필요 내용 목록(data/eval/dev50/needed_<날짜>.json, 01 B): 차례마다 묶음 목록, 묶음 = 대안 주소(하나만 와도 됨), 묶음은 모두 필요.
빈 목록인 차례(설명서 조각이 필요 없음)는 세지 않는다.

넘어갔나: 주소의 조각 글(같은 주소를 나눈 조각이면 그중 하나) 전체가 답 모델에 보낸 글 안에 그대로 있으면 그 주소가 넘어간 것이다.
엔진은 조각 글을 고치지 않고 이어 붙여 보낸다(answer_engine._messages, `소스 코드`). 그래서 검색 8개뿐 아니라 먼저 볼 소제목·
짧은 조각에 붙인 형제 소제목도 센다.

명령:
  check <원자료 jsonl> <문항 파일>   저장된 '검색 결과' 칸(검색 8개의 주소)으로, 등록된 정답 위치가 전부/일부/하나도 안 들어온 답 수를
                                      판정별로 낸다(이전 결론 1_문제정의_계획.md의 34·57·56 표와 맞대어 세는 법을 확인).
  stored <원자료 jsonl> <필요 목록>  같은 '검색 결과' 칸으로 필요 내용이 넘어간 차례 수(검색 8개만 보므로 아래 run보다 적게 나온다).
  run <필요 목록> <조각 파일> <판 폴더>...   evaluate 결과 폴더(호출.jsonl의 보낸 글 전문)마다 차례별 넘어감을 JSON으로 찍는다.
실행: .venv/bin/python -I .claude/tools/needed_count.py <명령> ...
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_needed(path: Path) -> dict[str, list[list[str]]]:
    return {number: item["필요"] for number, item in json.loads(path.read_text(encoding="utf-8"))["차례"].items()}


def load_texts(chunks: Path) -> dict[str, list[str]]:
    """주소(경로.html#앵커) → 그 주소의 조각 글들."""
    texts: dict[str, list[str]] = defaultdict(list)
    for line in chunks.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunk = json.loads(line)
            texts[f"{chunk['page_path']}.html#{chunk['anchor']}"].append(chunk["text"])
    return texts


def present(sent: str, addresses: set[str], texts: dict[str, list[str]]) -> set[str]:
    """addresses 가운데 조각 글이 보낸 글에 그대로 있는 주소."""
    return {address for address in addresses if any(text in sent for text in texts[address])}


def passed(groups: list[list[str]], got: set[str]) -> tuple[bool, int]:
    """(묶음이 모두 채워졌나, 채워진 묶음 수)."""
    filled = sum(any(address in got for address in group) for group in groups)
    return filled == len(groups), filled


def _stored(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        row["_주소"] = {result.split(" | ")[0] if isinstance(result, str) else result["주소"] for result in row["검색 결과"]}
    return rows


def _hits(location: str, addresses: set[str]) -> bool:
    """정답 위치(경로.html#앵커 또는 쪽 전체 경로.html)가 주소 묶음에 들었나(evaluate.hit와 같은 규칙)."""
    return location in addresses or ("#" not in location and any(address.split("#")[0] == location for address in addresses))


def check(stored: Path) -> dict:
    table: dict[str, Counter] = defaultdict(Counter)
    for row in _stored(stored):
        locations = row["정답 위치"]
        if not locations:
            continue
        count = sum(_hits(location, row["_주소"]) for location in locations)
        kind = "전부 들어옴" if count == len(locations) else "일부만" if count else "하나도 없음"
        table[kind][row["판정"]] += 1
    return {kind: dict(counter) | {"합": sum(counter.values())} for kind, counter in table.items()}


def stored_count(stored: Path, needed: dict[str, list[list[str]]]) -> dict:
    counted = [row for row in _stored(stored) if needed[row["번호"]]]
    ok = [row for row in counted if passed(needed[row["번호"]], row["_주소"])[0]]
    return {"센 답": len(counted), "필요 내용이 다 넘어감": len(ok), "판정별": dict(Counter(row["판정"] for row in ok))}


def run_count(needed: dict[str, list[list[str]]], texts: dict[str, list[str]], folder: Path) -> list[dict]:
    """판 폴더 하나의 차례별 결과. 보낸 글이 없는 차례(답 모델을 부르기 전에 실패)는 '보낸 글 없음'."""
    found = []
    for line in (folder / "호출.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        groups = needed[row["번호"]]
        if not groups:
            continue
        if not row["보낸 글"]:
            found.append({"번호": row["번호"], "보낸 글 없음": True})
            continue
        sent = "\n".join(message["content"] for message in row["보낸 글"])
        got = present(sent, {address for group in groups for address in group}, texts)
        whole, filled = passed(groups, got)
        found.append({"번호": row["번호"], "다 넘어감": whole, "채운 묶음": filled, "묶음": len(groups), "넘어간 주소": sorted(got)})
    return found


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "check":
        print(json.dumps(check(Path(args[0])), ensure_ascii=False, indent=1))
    elif command == "stored":
        print(json.dumps(stored_count(Path(args[0]), load_needed(Path(args[1]))), ensure_ascii=False, indent=1))
    elif command == "run":
        needed, texts = load_needed(Path(args[0])), load_texts(Path(args[1]))
        print(json.dumps({folder: run_count(needed, texts, Path(folder)) for folder in args[2:]}, ensure_ascii=False, indent=1))
    else:
        sys.exit(f"모르는 명령 {command}")
