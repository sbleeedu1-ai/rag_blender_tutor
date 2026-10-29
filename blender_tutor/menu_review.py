"""메뉴 이름 검수 초안(티켓 31): 초보자 범위 안에서 번역이 여러 개인 이름의 고정 짝을 Blender가 실제로 쓰는 문맥으로 미리 고른다.

Blender 화면 글자는 "영어 + 문맥"을 번역 사전에 넣어 뽑는다. 그래서 화면 없이 띄운 Blender에서
조작·속성·고르는 값·메뉴·패널 이름과 화면 파이썬 코드의 text=가 쓰는 문맥을 모두 뽑아(blender_ui_labels.py),
설명서 이름마다 그 문맥들이 어느 한국어로 보이는지 센다.
- 한 가지 한국어로만 보이면 자동으로 고른다(쓰는 곳이 가장 많은 문맥)
- 쓰는 곳마다 갈리거나 사전 후보에 없는 문맥이 섞이면 판단에 넘긴다(AI 초안 → 사용자 검수)
- Blender에서 못 찾은 이름(C 코드에서만 그리는 글자 등)도 판단에 넘긴다

Blender 안쪽 C 코드에서 그리는 글자는 뽑히지 않는다. 그래서 자동으로 고른 것도 사용자가 화면과 몇 개 맞춰 본다.
"""

import json
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from blender_tutor.manual_chunks import load_chunks
from blender_tutor.menu_names import ALIASES, MenuName, MenuNames, Source, Status, _english_key, build_menu_names

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
LABELS_SCRIPT = Path(__file__).with_name("blender_ui_labels.py")

UiLabels = Mapping[str, Mapping[str, Mapping]]  # 영어 → 문맥 → {"count": 쓰는 곳 수, "where": 쓰는 곳 몇 개}


class Kind(StrEnum):
    AUTO = "자동"  # 화면이 한 가지 한국어로만 쓴다
    SPLIT = "갈림"  # 쓰는 곳마다 한국어가 다르거나 사전에 없는 문맥이 섞임
    UNSEEN = "못 찾음"  # Blender에서 뽑은 글자에 없음


@dataclass(frozen=True)
class ChoiceDraft:
    """번역이 여러 개인 이름 하나의 초안."""

    english: str
    kind: Kind
    context: str | None  # 자동으로 고른 문맥(menu_choices.json에 적을 값). 판단이 필요하면 None
    screen: dict[str, int]  # 화면에 보이는 한국어 → 그렇게 쓰는 곳 수. 사전에 없는 문맥은 "?(문맥)"
    where: dict[str, list[str]]  # 문맥 → Blender에서 쓰는 곳 몇 개(판단 근거)


@dataclass(frozen=True)
class TitleDraft:
    """제목에서만 뽑은 이름 하나의 초안."""

    english: str
    in_blender: int  # Blender가 이 글자를 쓰는 곳 수(0이면 화면 글자가 아닐 수 있음)
    where: dict[str, list[str]]


def draft_choices(names: Iterable[MenuName], ui: UiLabels) -> list[ChoiceDraft]:
    drafts = []
    for name in names:
        used = ui.get(_english_key(name.english), {})
        korean_of = {context: t.korean for t in name.translations for context in t.contexts}
        screen: dict[str, int] = {}
        for context, use in used.items():
            korean = korean_of.get(context, f"?({context})")
            screen[korean] = screen.get(korean, 0) + use["count"]
        if not used:
            kind = Kind.UNSEEN
        elif len(screen) == 1 and not next(iter(screen)).startswith("?("):
            kind = Kind.AUTO
        else:
            kind = Kind.SPLIT
        context = max(used, key=lambda c: used[c]["count"]) if kind == Kind.AUTO else None
        drafts.append(ChoiceDraft(name.english, kind, context, screen, {c: list(u["where"]) for c, u in used.items()}))
    return drafts


def draft_titles(names: Iterable[MenuName], ui: UiLabels) -> list[TitleDraft]:
    drafts = []
    for name in names:
        used = ui.get(_english_key(name.english), {})
        count = sum(use["count"] for use in used.values())
        drafts.append(TitleDraft(name.english, count, {c: list(u["where"]) for c, u in used.items()}))
    return drafts


def scope_names(chunks_path: Path, scope_path: Path, po: Path, full_po: Path, names_path: Path) -> tuple[list[MenuName], list[MenuName]]:
    """초보자 범위 청크에 나오는 이름 가운데 (번역이 여러 개인 것, 제목에서만 뽑은 것). 많이 나온 차례로.

    여러 개·제목에서만은 설명서 전체로 만든 사전 기준이다(범위 안에서만 제목으로 나와도 다른 곳에서 화면 표시면 검수할 것이 없다).
    """
    include = set()
    with scope_path.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            if row["include"]:
                include.add(row["path"])
    chunks = [chunk for chunk in load_chunks(chunks_path) if chunk.page_path in include]
    in_scope = build_menu_names(
        chunks, po.read_text(encoding="utf-8"), full_po.read_text(encoding="utf-8"), MenuNames.load_aliases(ALIASES)
    )
    whole = MenuNames.load(names_path)
    many, titles = [], []
    for local in sorted(in_scope, key=lambda name: -name.chunks):
        name = whole.get(local.english)
        if name.status == Status.MANY:
            many.append(name)
        elif name.sources == (Source.TITLE,):
            titles.append(name)
    return many, titles


def dump_labels(out: Path, blender: str) -> None:
    """화면 없이 띄운 Blender에서 화면 글자와 문맥을 뽑아 out(JSON)에 쓴다."""
    subprocess.run(
        [blender, "-b", "--factory-startup", "--python", str(LABELS_SCRIPT), "--", str(out)],
        check=True, capture_output=True,
    )


def main(argv: list[str]) -> int:
    """사용법: python -m blender_tutor.menu_review <data 폴더>

    data/menu_names/ui_labels.json(Blender에서 뽑은 화면 글자, 없으면 Blender를 띄워 만듦)과
    data/menu_names/scope_review.json(초안: 여러 개 이름·제목에서만 뽑은 이름)을 쓴다. 이미 있는 초안은 덮어쓰지 않는다.
    Blender 위치가 다르면 환경 변수 BLENDER로 알려 준다.
    """
    if len(argv) != 1:
        print(main.__doc__)
        return 2
    data = Path(argv[0])
    out = data / "menu_names" / "scope_review.json"
    if out.exists():
        print(f"이미 있음: {out} (지우거나 옮긴 뒤 다시)")
        return 1
    labels = data / "menu_names" / "ui_labels.json"
    if not labels.exists():
        dump_labels(labels, os.environ.get("BLENDER", BLENDER))
    ui = json.loads(labels.read_text(encoding="utf-8"))
    many, titles = scope_names(
        data / "chunks" / "manual_chunks.jsonl", data / "beginner_scope" / "scope.jsonl",
        data / "ui_ko_5.2" / "ko.po", data / "ui_ko_5.2" / "fr.po", data / "menu_names" / "menu_names.json",
    )
    choices, title_drafts = draft_choices(many, ui), draft_titles(titles, ui)
    candidates = {name.english: {t.korean: list(t.contexts) for t in name.translations} for name in [*many, *titles]}
    rows = {
        "choices": [{**asdict(d), "candidates": candidates[d.english]} for d in choices],
        "titles": [{**asdict(d), "candidates": candidates[d.english]} for d in title_drafts],
    }
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    counts = {kind: sum(1 for d in choices if d.kind == kind) for kind in Kind}
    print(f"초안 → {out}")
    print(f"  번역이 여러 개 {len(choices)}개: " + ", ".join(f"{kind} {count}" for kind, count in counts.items()))
    print(f"  제목에서만 {len(title_drafts)}개: Blender가 쓰는 글자 {sum(1 for d in title_drafts if d.in_blender)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
