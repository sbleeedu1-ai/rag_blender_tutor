"""자료 준비: 설명서에 나오는 블렌더 표기(메뉴 경로·버튼 이름·옵션 이름)를 Blender 화면 번역 사전 ko.po와 짝짓는다.

규칙은 .scratch/mvp-roundtrip/spec.md의 "자료 준비"와 티켓 12·20을 따른다.
ko.po는 번역된 문구만 담는다(티켓 12). 그래서 "번역 없음"은 어느 문맥(msgctxt)에도 번역이 없다는 뜻이다.
"""

import json
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path

from blender_tutor.manual_chunks import Chunk, chunk_manual

DEFAULT_CONTEXT = "*"  # 문맥 없는 일반 문구. Blender Python도 이렇게 적는다(bpy.app.translations.contexts.default)
_PATH_SEP = "‣"  # 설명서 메뉴 경로의 구분 글자(Add ‣ Mesh)
ALIASES = Path(__file__).resolve().parents[1] / "menu_aliases.json"  # 설명서 철자 → 화면 철자 표(티켓 31)
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

    def __init__(self, names: Iterable[MenuName], choices: Mapping[str, str] = {}, titles: Iterable[str] = ()):
        """choices는 번역이 여러 개인 이름에 고정한 짝: 영어 이름 → 화면이 쓰는 문맥(사용자 검수, 티켓 23).

        열쇠에 바로 앞 단을 붙이면("Add > Empty") 그 메뉴 아래서만 쓰는 짝이다. 같은 이름도 메뉴·패널마다
        문맥이 달라 글자가 다르게 보이기 때문이다(Empty: 추가 메뉴 "비어 있음", 속성 창 "엠프티", 티켓 31).

        titles는 제목에서만 뽑은 이름 가운데 검수를 통과한 영어 이름들이다(티켓 31). 이것만 질문 찾기에 쓴다.
        """
        self._by_english = {_english_key(name.english): name for name in names}
        self._choices: dict[tuple[str, str], str] = {}  # (앞 단, 이름) → 문맥. 앞 단이 ""이면 이름 하나의 짝
        for key, context in choices.items():  # 틀린 짝이 조용히 영어로 보이지 않게 바로 멈춘다(오타·사전 다시 만든 뒤 어긋남)
            *parents, english = [part.strip() for part in re.split(r"[>‣]", key)]
            if len(parents) > 1 or parents == [""]:
                raise ValueError(f"고정 짝 {key!r}: 열쇠는 '이름'이나 '앞 단 > 이름'")
            name = self.get(english)
            if name is None or name.status != Status.MANY:
                raise ValueError(f"고정 짝 {key!r}: 사전에 번역이 여러 개인 이름으로 없음")
            if not any(context in t.contexts for t in name.translations):
                raise ValueError(f"고정 짝 {key!r}: 문맥 {context!r}가 사전에 없음")
            self._choices[("".join(parents), _english_key(english))] = context
        self._by_korean: dict[str, dict[str, None]] = {}  # 차례를 지키며 겹친 영어는 한 번만
        for name in self._by_english.values():
            for translation in name.translations:
                self._by_korean.setdefault(_korean_key(translation.korean), {})[name.english] = None
        titles = tuple(titles)
        passed = {_english_key(english) for english in titles}
        for english in titles:  # 고정 짝처럼 틀린 이름은 바로 멈춘다(오타·사전 다시 만든 뒤 어긋남)
            name = self.get(english)
            if name is None or name.sources != (Source.TITLE,):
                raise ValueError(f"통과 제목 {english!r}: 사전에 제목에서만 뽑은 이름으로 없음")
        self._in_questions = _question_index(self._by_english.values(), passed)  # english_in이 쓰는 표

    def __iter__(self):
        return iter(self._by_english.values())

    def get(self, english: str) -> MenuName | None:
        return self._by_english.get(_english_key(english))

    def korean(self, english: str, parent: str = "") -> str | None:
        """한국어 화면에 보이는 글자. 영어 그대로 보이면 None.

        번역 없음·사전에 없음은 영어 그대로, 하나면 그 번역, 여러 개면 고정한 짝(고정 전이면 영어 그대로)이다.
        parent는 메뉴 경로에서 바로 앞 단의 영어다. 그 메뉴 아래 짝이 있으면 그것을, 없으면 이름 하나의 짝을 쓴다.
        """
        name = self.get(english)
        if name is None or name.status == Status.NONE:
            return None
        if name.status == Status.ONE:
            return name.translations[0].korean
        key = _english_key(english)
        context = self._choices.get((parent.strip(), key)) or self._choices.get(("", key))
        korean = next((t.korean for t in name.translations if context in t.contexts), None)
        return None if korean == name.english else korean  # 고른 문맥에 번역이 없으면 화면은 영어

    def english_for(self, korean: str) -> tuple[str, ...]:
        """한국어 블렌더 표기에 맞는 영어 이름들(질문 속 한국어 메뉴 이름으로 영어 설명서를 찾을 때, 티켓 22)."""
        return tuple(self._by_korean.get(_korean_key(korean), ()))

    def english_in(self, text: str) -> tuple[str, ...]:
        """글(사용자 질문) 속 한국어 블렌더 표기를 찾아 영어 이름들을 나온 차례로 돌려준다(티켓 22).

        띄어쓰기는 무시하고 왼쪽부터, 자리마다 가장 긴 이름 하나를 고른다(중심을 찾으면 그 안의 심은 보지 않는다).
        한 글자 이름(면·폭 등)은 낱말 시작이나 앞 이름 바로 뒤에서만 인정한다(하려면의 면을 거르려고).
        '기'로 끝나는 이름은 '기'를 뗀 꼴로도 찾는다(합치기 → 합치려면).
        제목에서만 뽑은 이름은 검수를 통과한 것(titles)만 쓴다(티켓 31).

        검색어 보조일 뿐이라 예외를 더 두지 않는다. 알려진 한계(지어낸 질문으로 확인, 티켓 22 Comments):
        - 모양이 바뀐 동사 꼴(합쳤는데·숨긴)은 못 찾는다
        - 화면과 다른 낱말(꼭짓점 ↔ 화면 '버텍스')은 못 찾는다
        - 엉뚱한 것이 붙기도 한다(바꾸고 → Replace, 실수 → Float, 되돌리려면 → Dolly)
        """
        return tuple(dict.fromkeys(english for _, names in self.matches_in(text) for english in names))

    def matches_in(self, text: str) -> list[tuple[str, tuple[str, ...]]]:
        """english_in과 같은 규칙으로 찾되, 걸린 한국어 조각(띄어쓰기 뺀 것)과 그 영어 이름들을 나온 차례로 돌려준다."""
        index = self._in_questions
        longest = max(map(len, index), default=0)
        letters, word_starts = [], set()
        for i, letter in enumerate(text):
            if letter.isspace():
                continue
            if i == 0 or text[i - 1].isspace():
                word_starts.add(len(letters))
            letters.append(letter)
        squashed = "".join(letters)
        found = []
        start, last_end = 0, 0
        while start < len(squashed):
            for size in range(min(longest, len(squashed) - start), 0, -1):
                piece = squashed[start : start + size]
                if piece in index and (size > 1 or start in word_starts or start == last_end):
                    found.append((piece, index[piece]))
                    start = last_end = start + size
                    break
            else:
                start += 1
        return found

    def to_review(self) -> list[MenuName]:
        """번역이 여러 개인 이름을 많이 나온 차례로. 화면과 맞춰 하나로 고정하는 일은 사용자 검수 뒤에 한다."""
        return _by_count(name for name in self if name.status == Status.MANY)

    def title_only(self) -> list[MenuName]:
        """제목에서만 뽑은 이름을 많이 나온 차례로. 블렌더 표기가 아닌 흔한 낱말이 섞였는지 검수한다."""
        return _by_count(name for name in self if name.sources == (Source.TITLE,))

    def save(self, path: Path) -> None:
        rows = [asdict(name) for name in self._by_english.values()]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def load_choices(path: Path) -> dict[str, str]:
        """고정 짝 파일(영어 이름 → 문맥 JSON). 번역 글자가 없어 저장소에 커밋한다(menu_choices.json)."""
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def load_aliases(path: Path) -> dict[str, str]:
        """철자 표 파일(설명서 철자 → 화면 철자 JSON). 번역 글자가 없어 저장소에 커밋한다(menu_aliases.json)."""
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def load_titles(path: Path) -> list[str]:
        """통과 제목 파일(영어 이름 목록 JSON). 번역 글자가 없어 저장소에 커밋한다(menu_titles.json)."""
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def load(cls, path: Path, choices: Mapping[str, str] = {}, titles: Iterable[str] = ()) -> "MenuNames":
        rows = json.loads(path.read_text(encoding="utf-8"))
        names = [
            MenuName(
                english=row["english"],
                translations=tuple(Translation(t["korean"], tuple(t["contexts"])) for t in row["translations"]),
                chunks=row["chunks"],
                example=row["example"],
                sources=tuple(Source(source) for source in row["sources"]),
            )
            for row in rows
        ]
        return cls(names, choices, titles)


def _question_index(names: Iterable[MenuName], passed: set[str]) -> dict[str, tuple[str, ...]]:
    """질문 찾기용 표: 한국어(띄어쓰기 뺀 것, '기'를 뗀 꼴 포함) → 영어 이름들.

    제목에서만 뽑은 이름은 통과 목록(passed, 영어 열쇠)에 있는 것만 넣는다.
    """
    index: dict[str, dict[str, None]] = {}
    for name in names:
        if name.sources == (Source.TITLE,) and _english_key(name.english) not in passed:
            continue
        for translation in name.translations:
            index.setdefault(_korean_key(translation.korean), {})[name.english] = None
    stems: dict[str, dict[str, None]] = {}
    for korean, english in index.items():
        if korean.endswith("기") and len(korean) >= 3 and korean[:-1] not in index:
            stems.setdefault(korean[:-1], {}).update(english)
    return {korean: tuple(english) for korean, english in {**stems, **index}.items()}


def _by_count(names: Iterable[MenuName]) -> list[MenuName]:
    return sorted(names, key=lambda name: -name.chunks)


_Catalog = dict[str, dict[str, list[str]]]  # ko.po: 영어 → 한국어 → 문맥들


def build_menu_names(
    chunks: Iterable[Chunk], po_text: str, full_po_text: str = "", aliases: Mapping[str, str] = {}
) -> MenuNames:
    """청크들의 블렌더 표기를 ko.po 글과 짝지어 사전을 만든다.

    full_po_text는 번역률 100%인 다른 언어 사전(fr.po) 글이다. Blender가 쓰는 (문맥, 영어) 전체 목록으로 써서,
    한국어 번역이 빠진 문맥은 '영어 그대로'를 후보로 더한다. At Center는 Operator 문맥에만 "센터에서"가 있고
    병합 메뉴가 쓰는 Mesh 문맥에는 번역이 없어 화면에 영어로 보이기 때문이다(티켓 12·20).

    aliases는 설명서 철자 → 화면 철자 표다(menu_aliases.json). 설명서는 "Icosphere", 화면 추가 메뉴는 "Ico Sphere"처럼
    철자가 달라 ko.po의 다른 줄과 짝지어지는 이름만 적는다. 이름은 설명서 철자로 두고 번역은 화면 철자로 찾는다(티켓 31).
    """
    catalog: _Catalog = {}
    for context, english, korean in read_po(po_text):
        catalog.setdefault(_english_key(english), {}).setdefault(korean, []).append(context)
    for context, english, _ in read_po(full_po_text):
        translations = catalog.get(_english_key(english))
        if translations and all(context not in contexts for contexts in translations.values()):
            translations.setdefault(english, []).append(context)
    for manual, screen in aliases.items():  # 설명서 철자의 번역 자리를 화면 철자의 것으로 바꾼다
        catalog[_english_key(manual)] = catalog.get(_english_key(screen), {})
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
    aliases = MenuNames.load_aliases(ALIASES)
    names = build_menu_names(
        chunk_manual(root), po.read_text(encoding="utf-8"), full_po.read_text(encoding="utf-8"), aliases
    )
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
