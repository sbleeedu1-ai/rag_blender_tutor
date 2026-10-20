"""자료 준비: 설명서에 나오는 블렌더 표기(메뉴 경로·버튼 이름·옵션 이름)를 Blender 화면 번역 사전 ko.po와 짝짓는다.

규칙은 .scratch/mvp-roundtrip/spec.md의 "자료 준비"와 티켓 12·20을 따른다.
ko.po는 번역된 문구만 담는다(티켓 12). 그래서 "번역 없음"은 어느 문맥(msgctxt)에도 번역이 없다는 뜻이다.
"""

import json
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from blender_tutor.manual_chunks import Chunk, chunk_manual

DEFAULT_CONTEXT = "*"  # 문맥 없는 일반 문구. Blender Python도 이렇게 적는다(bpy.app.translations.contexts.default)
_PATH_SEP = "‣"  # 설명서 메뉴 경로의 구분 글자(Add ‣ Mesh)
_TITLE_TAIL = re.compile(r" (Modifier|Node|Tool|Constraint)$")  # 쪽 제목 "Array Modifier"의 블렌더 표기는 "Array"


class Source(StrEnum):
    """블렌더 표기를 설명서 어디서 뽑았나."""

    UI = "화면 표시"  # 메뉴 경로(Add ‣ Mesh)·버튼 이름 표시
    OPTION = "옵션"  # 옵션 이름
    TITLE = "제목"  # 쪽 제목·소제목(ko.po에 있는 것만). 블렌더 표기가 아닌 흔한 낱말도 섞여 따로 검수한다


class Status(StrEnum):
    """번역 사전과 짝지은 결과."""

    NONE = "번역 없음"  # 한국어 화면에서도 영어로 보인다
    ONE = "하나"
    MANY = "여러 개"  # 문맥마다 번역이 달라 화면과 맞춰 골라야 한다(사용자 검수)


@dataclass(frozen=True)
class Translation:
    """한국어 화면 글자 하나와 그 글자가 나오는 문맥들."""

    korean: str
    contexts: tuple[str, ...]  # 이 번역이 나오는 문맥들


@dataclass(frozen=True)
class MenuName:
    """설명서에 나오는 블렌더 표기 하나(메뉴 경로의 한 단, 버튼 이름, 옵션 이름, ko.po에 있는 제목)."""

    english: str  # 설명서에 적힌 그대로
    translations: tuple[Translation, ...]  # 서로 다른 한국어만, 사전에 나온 차례로
    chunks: int  # 이 이름이 나온 청크 수
    example: str  # 처음 나온 청크 링크(검수 때 실제 쪽을 열어 본다)
    sources: tuple[Source, ...] = ()  # 어디서 뽑았나

    @property
    def status(self) -> Status:
        if not self.translations:
            return Status.NONE
        return Status.ONE if len(self.translations) == 1 else Status.MANY


class MenuNames:
    """메뉴 이름 사전: 영어 이름 → 번역들, 한국어 이름 → 영어 이름들."""

    def __init__(self, names: Iterable[MenuName]):
        self._by_english = {_english_key(name.english): name for name in names}
        self._by_korean: dict[str, dict[str, None]] = {}  # 차례를 지키며 겹친 영어는 한 번만
        for name in self._by_english.values():
            for translation in name.translations:
                self._by_korean.setdefault(_korean_key(translation.korean), {})[name.english] = None

    def __iter__(self):
        return iter(self._by_english.values())

    def get(self, english: str) -> MenuName | None:
        return self._by_english.get(_english_key(english))

    def english_for(self, korean: str) -> tuple[str, ...]:
        """한국어 블렌더 표기에 맞는 영어 이름들(질문 속 한국어 메뉴 이름으로 영어 설명서를 찾을 때, 티켓 22)."""
        return tuple(self._by_korean.get(_korean_key(korean), ()))

    def to_review(self) -> list[MenuName]:
        """번역이 여러 개인 이름을 많이 나온 차례로. 화면과 맞춰 하나로 고정하는 일은 사용자 검수 뒤에 한다."""
        return _by_count(name for name in self if name.status == Status.MANY)

    def title_only(self) -> list[MenuName]:
        """제목에서만 뽑은 이름을 많이 나온 차례로. 블렌더 표기가 아닌 흔한 낱말이 섞였는지 검수한다."""
        return _by_count(name for name in self if name.sources == (Source.TITLE,))

    def save(self, path: Path) -> None:
        rows = [asdict(name) for name in self._by_english.values()]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "MenuNames":
        rows = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            MenuName(
                english=row["english"],
                translations=tuple(Translation(t["korean"], tuple(t["contexts"])) for t in row["translations"]),
                chunks=row["chunks"],
                example=row["example"],
                sources=tuple(Source(source) for source in row["sources"]),
            )
            for row in rows
        )


def _by_count(names: Iterable[MenuName]) -> list[MenuName]:
    return sorted(names, key=lambda name: -name.chunks)


_Catalog = dict[str, dict[str, list[str]]]  # ko.po: 영어 → 한국어 → 문맥들


def build_menu_names(chunks: Iterable[Chunk], po_text: str, full_po_text: str = "") -> MenuNames:
    """청크들의 블렌더 표기를 ko.po 글과 짝지어 사전을 만든다.

    full_po_text는 번역률 100%인 다른 언어 사전(fr.po) 글이다. Blender가 쓰는 (문맥, 영어) 전체 목록으로 써서,
    한국어 번역이 빠진 문맥은 '영어 그대로'를 후보로 더한다. At Center는 Operator 문맥에만 "센터에서"가 있고
    병합 메뉴가 쓰는 Mesh 문맥에는 번역이 없어 화면에 영어로 보이기 때문이다(티켓 12·20).
    """
    catalog: _Catalog = {}
    for context, english, korean in read_po(po_text):
        catalog.setdefault(_english_key(english), {}).setdefault(korean, []).append(context)
    for context, english, _ in read_po(full_po_text):
        translations = catalog.get(_english_key(english))
        if translations and all(context not in contexts for contexts in translations.values()):
            translations.setdefault(english, []).append(context)
    seen: dict[str, _Seen] = {}
    for chunk in chunks:
        in_chunk: dict[str, set[Source]] = {}  # 한 청크에 같은 이름이 여러 번 나와도 한 번으로 센다
        for english, source in _screen_names(chunk, catalog):
            key = _english_key(english)
            in_chunk.setdefault(key, set()).add(source)
            seen.setdefault(key, _Seen(english, chunk.url))
        for key, sources in in_chunk.items():
            seen[key].chunks += 1
            seen[key].sources |= sources
    return MenuNames(
        MenuName(
            english=item.english,
            translations=tuple(
                Translation(korean, tuple(contexts)) for korean, contexts in catalog.get(key, {}).items()
            ),
            chunks=item.chunks,
            example=item.example,
            sources=tuple(source for source in Source if source in item.sources),
        )
        for key, item in seen.items()
    )


@dataclass
class _Seen:
    """사전을 만드는 동안 이름 하나에 대해 모으는 것."""

    english: str  # 처음 나온 모양 그대로
    example: str  # 처음 나온 청크 링크
    chunks: int = 0
    sources: set[Source] = field(default_factory=set)


def read_po(text: str) -> list[tuple[str, str, str]]:
    """ko.po 글을 (문맥, 영어, 한국어) 목록으로 읽는다. 머리말과 번역이 빈 항목은 뺀다."""
    entries: list[tuple[str, str, str]] = []
    fields: dict[str, str] = {}
    current = None  # 지금 이어 읽는 칸(msgctxt·msgid·msgstr)

    def finish() -> None:
        if fields.get("msgid") and fields.get("msgstr"):
            entries.append((fields.get("msgctxt", DEFAULT_CONTEXT), fields["msgid"], fields["msgstr"]))
        fields.clear()

    for line in text.splitlines():
        line = line.strip()
        match = re.match(r'(msgctxt|msgid|msgstr) "(.*)"$', line)
        if match:
            if match[1] != "msgstr" and "msgstr" in fields:
                finish()  # 새 항목이 시작됨
            current = match[1]
            fields[current] = _unquote(match[2])
        elif line.startswith('"') and current:
            fields[current] += _unquote(line[1:-1])  # 앞 칸에 이어지는 줄
        elif not line or line.startswith("#"):
            current = None
    finish()
    return entries


def _unquote(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m[1], m[1]), text)


def _screen_names(chunk: Chunk, catalog: _Catalog) -> list[tuple[str, Source]]:
    """청크의 블렌더 표기와 출처. 메뉴 경로는 한 단씩 나누고, 버튼 이름·옵션 이름은 그대로.

    쪽 제목·소제목은 ko.po에 있을 때만 블렌더 표기로 본다. 모디파이어·노드 이름(Array 등)은
    설명서가 메뉴 경로로 적지 않고 쪽 제목("Array Modifier")으로만 적기 때문이다(티켓 20).
    """
    names = [(part.strip(), Source.UI) for name in chunk.ui_names for part in name.split(_PATH_SEP)]
    names += [(option, Source.OPTION) for option in chunk.options]
    for title in (chunk.page_title, *chunk.headings):
        for candidate in dict.fromkeys((title, _TITLE_TAIL.sub("", title))):
            if _english_key(candidate) in catalog:
                names.append((candidate, Source.TITLE))
    return [(name, source) for name, source in names if name]


def _english_key(english: str) -> str:
    """설명서는 말줄임표를 '…' 한 글자로, ko.po는 '...'로 쓴다."""
    return english.replace("…", "...")


def _korean_key(korean: str) -> str:
    """사용자는 '배열(레거시)'처럼 띄어쓰기를 다르게 칠 수 있다."""
    return "".join(korean.split())


def _review_markdown(review: list[MenuName], title_only: list[MenuName]) -> str:
    """검수 목록: 번역이 여러 개인 이름, 제목에서만 뽑은 이름. 이름마다 후보·문맥·출처와 처음 나온 설명서 쪽 링크."""
    lines = [
        "# 메뉴 이름 검수",
        "",
        "문맥 `*`는 기본 문맥. 출처: 화면 표시(메뉴 경로·버튼 이름), 옵션, 제목(쪽 제목·소제목).",
        "",
        f"## 1. 번역이 여러 개인 이름 ({len(review)}개)",
        "",
        "화면에 실제로 보이는 글자와 맞춰 하나로 고정한다(번역 없이 영어로 보이면 영어).",
        "",
        *_review_table(review),
        "",
        f"## 2. 제목에서만 뽑은 이름 ({len(title_only)}개)",
        "",
        "쪽 제목·소제목 가운데 ko.po에 있는 것. 'Options'처럼 블렌더 표기가 아닌 낱말이 섞였는지 본다.",
        "",
        *_review_table(title_only),
    ]
    return "\n".join(lines) + "\n"


def _review_table(names: list[MenuName]) -> list[str]:
    rows = ["| 영어 | 나온 청크 | 후보(문맥) | 출처 | 처음 나온 곳 |", "|---|---|---|---|---|"]
    for name in names:
        options = " / ".join(f"{t.korean} ({', '.join(t.contexts)})" for t in name.translations)
        sources = ", ".join(name.sources)
        rows.append(f"| {name.english} | {name.chunks} | {options} | {sources} | [링크]({name.example}) |")
    return rows


def main(argv: list[str]) -> int:
    """사용법: python -m blender_tutor.menu_names <설명서 HTML 폴더> <ko.po> <fr.po> <출력 폴더>

    예: python -m blender_tutor.menu_names data/manual_en_5.2/html/blender_manual_v520_en.html data/ui_ko_5.2/ko.po data/ui_ko_5.2/fr.po data/menu_names
    ko.po·fr.po는 Blender 저장소 blender-v5.2-release 브랜치의 locale/po/에 있다(티켓 12).
    fr.po(번역률 100%)는 Blender가 쓰는 문맥 전체를 알려고 쓴다.

    출력 폴더에 사전 menu_names.json과 검수 목록 review.md를 쓴다. 결과는 data/에 두고 커밋하지 않는다.
    """
    if len(argv) != 4:
        print(main.__doc__)
        return 2
    root, po, full_po, out = Path(argv[0]), Path(argv[1]), Path(argv[2]), Path(argv[3])
    names = build_menu_names(chunk_manual(root), po.read_text(encoding="utf-8"), full_po.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    names.save(out / "menu_names.json")
    review = names.to_review()
    title_only = names.title_only()
    (out / "review.md").write_text(_review_markdown(review, title_only), encoding="utf-8")
    counts = {status: 0 for status in Status}
    for name in names:
        counts[name.status] += 1
    print(f"블렌더 표기 {sum(counts.values())}개 → {out}")
    print("  " + ", ".join(f"{status} {count}" for status, count in counts.items()))
    print(f"  검수 목록 → {out / 'review.md'}: 여러 개 {len(review)}개, 제목에서만 뽑은 이름 {len(title_only)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
