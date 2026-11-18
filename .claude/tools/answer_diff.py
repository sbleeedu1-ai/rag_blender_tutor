"""답 바꾸기(제품 `_MenuMarks`)를 두 코드 판으로 저장된 답에 돌려, 바뀐 문장 전후를 모아 보인다. 돈 0.

왜: 화면 꼴이 바뀌는 일은 커밋·유료 시험 전에 실제 전후 문장을 먼저 보이기로 했다(HISTORY [370]·[371], 회고 3번).
지금까지는 시험마다 일회용 스크립트를 새로 썼다(`results/20261116/121347_티켓50_원문_대조/돌리기.py` 등).

쓰는 법(저장소 맨 위에서, Mac은 .venv/bin/python):
    .venv\\Scripts\\python .claude\\tools\\answer_diff.py                 # 전 = 마지막 커밋(HEAD), 후 = 지금 작업 폴더
    .venv\\Scripts\\python .claude\\tools\\answer_diff.py --전 main --후 HEAD
    ... --출력 results\\<날짜>\\<시각>_<이름>                              # 바뀐_자리.json·전후.md를 남김

자료: 지시문 시험 모델 원문 90개(모델이 낸 그대로)와 저장된 답 378개(천장 측정 3판·답 쪽 측정 4판, 이미 그때 제품을 거친 글).
저장된 답은 원문이 아니라서, 거기서 바뀐 자리는 "이미 바뀐 글에 다시 돌린 결과"로 읽는다.
한국어 화면인 문항만 이름을 바꾸는 것은 제품과 같다(`korean_screen`이 아니면 이름표 없이 돌린다).
자료 폴더(`results/`)는 Git 밖이라 다른 PC에 없으면 멈춘다.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import random
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = "data/eval/dev50/questions_20261114.json"

# (출처 이름, results/ 아래 경로, 글 칸)
SOURCES = [
    *[(f"원문:{d}_{i}", f"20261116/110745_지시문_시험/{d}_{i}/원문.jsonl", "원문") for d in ("지금", "예시", "앞으로") for i in (1, 2, 3)],
    *[(f"저장:{arm}", f"20261114/231756_천장측정/{arm}/답.jsonl", "답") for arm in ("바탕", "넣음", "정답만")],
    *[(f"저장:{arm}", f"20261115/011359_답쪽측정/{arm}/답.jsonl", "답") for arm in ("none1", "medium", "sonnet", "none2")],
]


def pieces(text: str, seed: int) -> list[str]:
    """도우미 창이 받는 것처럼 글을 1-12자 조각으로 나눈다(같은 씨앗이면 같게)."""
    rng, out, i = random.Random(seed), [], 0
    while i < len(text):
        k = rng.randint(1, 12)
        out.append(text[i : i + k])
        i += k
    return out


def stream_mismatch(text: str, run: Callable[[list[str]], str], seeds: Iterable[int] = (1, 2, 3)) -> int:
    """한 번에 넣은 결과와 조각으로 흘려 넣은 결과가 다른 씨앗 수."""
    whole = run([text])
    return sum(run(pieces(text, s)) != whole for s in seeds)


def spots(before: str, after: str, around: int = 15, join: int = 20) -> list[dict[str, str]]:
    """두 글에서 바뀐 자리마다 앞뒤 글(around자)을 붙여 뽑는다. 이름 하나가 글자 단위로 쪼개져 바뀌므로 join자 안의 바뀜은 한 자리로 본다."""
    sm = difflib.SequenceMatcher(None, before, after, autojunk=False)
    merged: list[list[int]] = []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op == "equal":
            continue
        if merged and a1 - merged[-1][1] <= join:
            merged[-1][1], merged[-1][3] = a2, b2
        else:
            merged.append([a1, a2, b1, b2])
    return [
        {
            "전": before[max(0, a1 - around) : a2 + around].replace("\n", " "),
            "후": after[max(0, b1 - around) : b2 + around].replace("\n", " "),
        }
        for a1, a2, b1, b2 in merged
    ]


def group(rows: list[dict]) -> list[dict]:
    """같은 전후는 하나로 묶고 몇 번, 어느 문항에서 나왔는지 센다. 많은 것부터."""
    seen: dict[tuple[str, str], dict] = {}
    for r in rows:
        g = seen.setdefault((r["전"], r["후"]), {"전": r["전"], "후": r["후"], "수": 0, "번호": []})
        g["수"] += 1
        if r["번호"] not in g["번호"]:
            g["번호"].append(r["번호"])
    return sorted(seen.values(), key=lambda g: -g["수"])


def read_sources(results: Path, sources=SOURCES) -> Iterator[tuple[str, str, str]]:
    for name, rel, field in sources:
        path = results / rel
        if not path.exists():
            raise FileNotFoundError(f"자료가 없습니다: {path} (results/는 Git 밖이라 다른 PC에는 없을 수 있음)")
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                yield name, r["번호"], r[field] or ""


def _emit(code: Path, out: Path) -> None:
    """`code` 폴더의 blender_tutor로 모든 자료를 바꿔 out에 적는다(다른 판은 따로 띄운 파이썬에서 부른다)."""
    sys.path.insert(0, str(code))
    from blender_tutor import evaluate
    from blender_tutor.answer_engine import _MenuMarks, _object_names
    from blender_tutor.menu_names import load_menu_names

    names = load_menu_names(ROOT / "data")
    courses = evaluate.load_courses(evaluate.COURSES)
    turns = {t.number: t for d in evaluate.load_questions(ROOT / QUESTIONS, courses) for t in d.turns}
    rows = []
    for src, num, text in read_sources(ROOT / "results"):
        t = turns[num]

        def run(parts: list[str], t=t) -> str:
            m = _MenuMarks(names if t.state.korean_screen else None, t.question, _object_names(t.state))
            return "".join(m.feed(p) for p in parts) + m.finish()

        rows.append({"출처": src, "번호": num, "글": run([text]), "흐름다름": stream_mismatch(text, run)})
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _side(ref: str | None, tmp: Path, label: str) -> list[dict]:
    """ref가 없으면 지금 작업 폴더, 있으면 그 커밋의 blender_tutor로 돌린다."""
    code = ROOT
    if ref is not None:
        code = tmp / f"code_{label}"
        code.mkdir()
        archive = tmp / f"{label}.tar"
        subprocess.run(["git", "-C", str(ROOT), "archive", "-o", str(archive), ref], check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(code, filter="data")
    out = tmp / f"{label}.json"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, __file__, "--내보내기", str(code), str(out)], check=True, env=env, cwd=ROOT)
    return json.loads(out.read_text(encoding="utf-8"))


def compare(before: list[dict], after: list[dict]) -> tuple[list[dict], dict]:
    if [(b["출처"], b["번호"]) for b in before] != [(a["출처"], a["번호"]) for a in after]:
        raise ValueError("두 판의 자료 순서가 다릅니다")
    rows = []
    for b, a in zip(before, after):
        for s in spots(b["글"], a["글"]):
            rows.append({"출처": a["출처"], "번호": a["번호"], **s})
    stats = {
        "자료": len(after),
        "바뀐 답": sum(b["글"] != a["글"] for b, a in zip(before, after)),
        "바뀐 자리": len(rows),
        "흐름 대조 다름(후, 씨앗 3개씩)": sum(a["흐름다름"] for a in after),
    }
    return rows, stats


def markdown(groups: list[dict], stats: dict, title: str) -> str:
    lines = [f"# {title}", "", *[f"- {k}: {v}" for k, v in stats.items()], f"- 서로 다른 전후: {len(groups)}", ""]
    lines += ["| 수 | 문항 | 전 | 후 |", "|---|---|---|---|"]
    for g in groups:
        cell = lambda s: s.replace("|", "\\|")
        lines.append(f"| {g['수']} | {', '.join(g['번호'][:5])}{' …' if len(g['번호']) > 5 else ''} | {cell(g['전'])} | {cell(g['후'])} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if argv[:1] == ["--내보내기"]:
        _emit(Path(argv[1]), Path(argv[2]))
        return 0
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--전", default="HEAD", help="바꾸기 전 코드의 커밋(기본 HEAD)")
    p.add_argument("--후", default=None, help="바꾼 뒤 코드의 커밋(기본: 지금 작업 폴더)")
    p.add_argument("--출력", default=None, help="결과를 남길 폴더(없으면 화면에만)")
    args = p.parse_args(argv)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        rows, stats = compare(_side(args.전, tmp, "before"), _side(args.후, tmp, "after"))
    groups = group(rows)
    text = markdown(groups, stats, f"바꾸기 전후: {args.전} → {args.후 or '작업 폴더'}")
    if args.출력:
        out = Path(args.출력)
        out.mkdir(parents=True, exist_ok=True)
        (out / "바뀐_자리.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "전후.md").write_text(text, encoding="utf-8")
    print(text if len(text) < 20000 else text[:20000] + "\n… (잘림, --출력 폴더의 전후.md를 볼 것)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
