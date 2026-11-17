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

from blender_tutor.korean_particles import PARTICLE, fit_particle
from blender_tutor.manual_chunks import Chunk, chunk_manual
from blender_tutor.paths import MENU_ALIASES, MENU_CHOICES, MENU_COMMON, MENU_TITLES

DEFAULT_CONTEXT = "*"  # 문맥 없는 일반 문구. Blender Python도 이렇게 적는다(bpy.app.translations.contexts.default)
_PATH_SEP = "‣"  # 설명서 메뉴 경로의 구분 글자(Add ‣ Mesh)
_TITLE_TAIL = re.compile(r" (Modifier|Node|Tool|Constraint)$")  # 쪽 제목 "Array Modifier"의 블렌더 표기는 "Array"
# 메뉴 이름 표시. 답변 모델의 답(티켓 23)과 연습 과정 안내 말(티켓 32)이 메뉴 이름을 감싸고, 화면 언어에 맞게 바꾼다
MARK_OPEN, MARK_CLOSE = "[[", "]]"
_MARK = re.compile(r"\[\[(.+?)\]\]")
ARTICLES = {"The", "A", "An", "This", "These", "That", "Those", "Each", "Its", "Your"}  # 문장 첫머리 관사·지시어
# 키보드 키 이름. ko.po에는 'Space → 공간'처럼 다른 뜻으로 들어 있어 넓힌 목록에서 빼고, 답 글에서도 바꾸지 않는다(티켓 49)
KEY_NAMES = {"Space", "Delete", "Backspace", "Tab", "Enter", "Return", "Esc", "Escape", "Home", "End", "Insert",
             "Shift", "Ctrl", "Alt", "Cmd", "Option", "Fn", "Page Up", "Page Down", "Numpad", "Spacebar"}
MODIFIER_KEYS = {"Shift", "Ctrl", "Alt", "Cmd", "Option", "Fn"}
PROGRAM_NAMES = {"Blender"}  # 화면 메뉴 이름이 아니라 프로그램 이름
# Blender가 새 물체에 붙이는 기본 이름. 답 글에서는 고르지 않은 물체 이름(불리언 대상 Cube 등)일 수 있어, 메뉴 경로(> 뒤)가 아니면
# 바꾸지 않는다(2026-11-16 저장된 답 Q11 "대상은 Cube"로 확인)
OBJECT_DEFAULTS = {"Cube", "Plane", "Circle", "Cylinder", "Cone", "Torus", "Grid", "Sphere", "UV Sphere", "Ico Sphere",
                   "Icosphere", "Suzanne", "Monkey", "Camera", "Light", "Empty", "Armature", "Text", "Curve"}
# 자리마다 화면 글자가 다른 것을 확인한 이름: 버튼은 엣지, 메뉴·글은 에지(HISTORY [80]). 메뉴마다 짝을 따로 둔 이름도 같이 본다
PLACE_DEPENDENT = {"Edge"}
# 속성 창 탭 이름(Blender 5.2 RNA `SpaceProperties.context`의 고르는 값, 실행으로 확인). 탭은 `ID` 문맥 글자로 보인다:
# 렌치 탭에 마우스를 대면 "수정자"(메뉴·패널은 "모디파이어", 사용자 스크린숏 [353]). 답에서 이름 바로 뒤나 괄호 바로 앞이 "탭"이면
# 이 글자를 쓴다(사용자 "화면대로가 원칙인데", HISTORY [397]). 한국어 글자는 사전에서 찾는다(번역 글자를 저장소에 두지 않음)
PROPERTIES_TABS = ("Tool", "Scene", "Render", "Output", "View Layer", "World", "Collection", "Object", "Constraints", "Modifiers",
                   "Data", "Bone", "Bone Constraints", "Material", "Texture", "Particles", "Physics", "Effects", "Strip",
                   "Strip Modifiers")
TAB_CONTEXT = "ID"
_TAB_RUN = re.compile(r"\S*(?<![A-Za-z])(?:" + "|".join(re.escape(t) for t in sorted(PROPERTIES_TABS, key=len, reverse=True))
                      + r")[)\]'\"’”*]*\s*$")


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

    def __init__(
        self, names: Iterable[MenuName], choices: Mapping[str, str] = {}, titles: Iterable[str] = (), extra: Mapping[str, str] = {},
        common: Mapping[str, Iterable[str]] = {},
    ):
        """choices는 번역이 여러 개인 이름에 고정한 짝: 영어 이름 → 화면이 쓰는 문맥(사용자 검수, 티켓 23).

        열쇠에 바로 앞 단을 붙이면("Add > Empty") 그 메뉴 아래서만 쓰는 짝이다. 같은 이름도 메뉴·패널마다
        문맥이 달라 글자가 다르게 보이기 때문이다(Empty: 추가 메뉴 "비어 있음", 속성 창 "엠프티", 티켓 31).

        titles는 제목에서만 뽑은 이름 가운데 검수를 통과한 영어 이름들이다(티켓 31). 이것만 질문 찾기에 쓴다.

        extra는 넓힌 목록: 사전에 없는 화면 이름 → 한국어 화면 글자(extra_names, 티켓 49). 화면 글자로 바꿀 때만 쓰고
        질문 찾기에는 넣지 않는다(검색어가 달라지지 않게).

        common은 흔히 옮기는 말 목록: 영어 이름 → 모델이 그 이름을 한국어로 옮길 때 흔히 쓰는 말들(티켓 50 가, HISTORY [358]-[360]).
        "직교 투영(Orthographic)"처럼 모델이 스스로 옮긴 앞말을 화면 글자로 통째로 바꿀 때만 쓴다. 종류 낱말(모드·창 등)은 뺀다.
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
        self._passed = passed
        self._extra = {_english_key(english): korean for english, korean in extra.items()}
        # 화면 글자에 쓰인 낱말 모음: 앞말 끝 낱말이 여기 있으면 '-어'로 끝나도 이어 주는 꼴로 보지 않는다("모디파이어", [393])
        self.glyph_words = frozenset(w for name in self._by_english.values() for t in name.translations for w in t.korean.split())
        kinds = {_squash(tail) for tail in COMMON_TAILS}
        self._common = {
            _english_key(english): tuple(sorted({" ".join(v.split()) for v in variants if v.strip() and _squash(v) not in kinds},
                                                key=len, reverse=True))
            for english, variants in common.items()
        }
        # 흐름 붙잡기용: 뒤에 낱말이 더 이어지면 목록 말(+꼬리)이 될 수 있는 낱말 줄("직교 투영"의 "직교", 꼬리가 붙을 "면",
        # "면 선택 모드"의 "면 선택"). 꼬리 가운데 여러 낱말은 "선택 모드"뿐이다
        self.common_prefixes: set[str] = set()
        for english, variants in self._common.items():
            glyph = self.korean(english)  # 화면 글자 + 꼬리도 꼬리를 괄호 뒤로 옮기므로 함께
            for v in (*variants, *([" ".join(glyph.split())] if glyph and _HANGUL.search(glyph) else [])):
                words = v.split()
                self.common_prefixes.update(" ".join(words[:k]) for k in range(1, len(words) + 1))
                self.common_prefixes.add(f"{v} 선택")

    def __iter__(self):
        return iter(self._by_english.values())

    def common(self, english: str) -> tuple[str, ...]:
        """흔히 옮기는 말들(긴 것부터). 목록에 없으면 빈 묶음."""
        return self._common.get(_english_key(english), ())

    def tab_glyph(self, english: str) -> str | None:
        """속성 창 탭 이름이면 탭에 보이는 한국어(`ID` 문맥). 탭 이름이 아니거나 그 문맥에 번역이 없으면 None."""
        if english not in PROPERTIES_TABS:
            return None
        name = self.get(english)
        korean = next((t.korean for t in name.translations if TAB_CONTEXT in t.contexts), None) if name else None
        return None if korean == english else korean

    def glyphs(self, english: str) -> tuple[str, ...]:
        """이 이름의 모든 화면 글자(문맥마다 다른 번역)."""
        name = self.get(english)
        return tuple(t.korean for t in name.translations) if name else ()

    def get(self, english: str) -> MenuName | None:
        return self._by_english.get(_english_key(english))

    def korean(self, english: str, parent: str = "") -> str | None:
        """한국어 화면에 보이는 글자. 영어 그대로 보이면 None.

        번역 없음·사전에 없음은 영어 그대로, 하나면 그 번역, 여러 개면 고정한 짝(고정 전이면 영어 그대로)이다.
        parent는 메뉴 경로에서 바로 앞 단의 영어다. 그 메뉴 아래 짝이 있으면 그것을, 없으면 이름 하나의 짝을 쓴다.
        """
        name = self.get(english)
        if name is None:
            return self._extra.get(_english_key(english))
        if name.status == Status.NONE:
            return None
        if name.status == Status.ONE:
            return name.translations[0].korean
        key = _english_key(english)
        context = self._choices.get((parent.strip(), key)) or self._choices.get(("", key))
        korean = next((t.korean for t in name.translations if context in t.contexts), None)
        return None if korean == name.english else korean  # 고른 문맥에 번역이 없으면 화면은 영어

    def screen(self, english: str, parent: str = "") -> tuple[bool, str | None]:
        """화면 글로 바꿀 때 찾기: (사전이나 넓힌 목록에 있나, 한국어 화면 글자). 있는데 화면이 영어면 (True, None).

        설명서·답은 "Zoom Region…"의 말줄임표를 떼고 쓰기도 해서, 그대로 없으면 붙인 꼴·뗀 꼴도 찾는다.
        """
        key = _english_key(english)
        for candidate in dict.fromkeys((key, key + "...", key.removesuffix("..."))):
            if self.get(candidate) is not None or candidate in self._extra:
                return True, self.korean(candidate, parent)
        return False, None

    def in_prose(self, english: str) -> tuple[bool, str | None]:
        """감싸지 않은 답 글 속 이름 찾기. screen과 같되 둘을 더 가린다.

        - 제목에서만 뽑은 이름은 검수를 통과한 것만(일상 낱말이 섞여서, 티켓 31)
        - 번역이 여러 개인 이름은 고정 짝의 글자가 기본 문맥(`*`)의 글자와 같을 때만 바꾼다. 짝은 검수한 한 자리의 글자인데,
          감싸지 않은 글에는 어느 메뉴 아래인지가 없다. 기본 문맥과 다르면 자리마다 글자가 갈린다(예: Strength 고정 짝 '힘',
          월드 배경 노드 칸은 기본 문맥 '강도', 2026-11-16 실행으로 확인)
        """
        name = self.get(english) or self.get(english + "...")
        if name is not None and name.sources == (Source.TITLE,) and _english_key(name.english) not in self._passed:
            return False, None
        if name is not None and (name.english in PLACE_DEPENDENT or any(parent and key == _english_key(name.english) for parent, key in self._choices)):
            return True, None  # 메뉴마다 글자가 다른 이름(Bisect·Normal 등 경로 열쇠가 있는 것)은 어느 메뉴인지 알 때만
        if name is not None and name.status == Status.MANY:
            korean = self.korean(name.english)
            default = next((t.korean for t in name.translations if DEFAULT_CONTEXT in t.contexts), None)
            return True, korean if korean is not None and korean == default else None
        return self.screen(english)

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
    def load(cls, path: Path, choices: Mapping[str, str] = {}, titles: Iterable[str] = (), extra: Mapping[str, str] = {},
             common: Mapping[str, Iterable[str]] = {}) -> "MenuNames":
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
        return cls(names, choices, titles, extra, common)


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


def screen_path(path: str, names: "MenuNames | None", asked: str = "", seen: set | None = None, tab: bool = False) -> str:
    """메뉴 이름 표시 하나의 속(Add > Mesh)을 화면 글로 바꾼다.

    names가 있으면(한국어 화면에 번역 켜짐) 단마다 "추가(Add)"처럼 한국어(영어)로, 영어로 보이는 단과 화면 글자가 영어와
    같은 단(X-Ray)은 영어 하나로. names가 없으면 영어 그대로.
    asked(사용자 질문)에 영어로 쓴 단은 "Add(추가)"처럼 영어(한국어)로 둔다. 사용자가 부른 이름을 앞에 두어 같은 것임을 알게
    한다(HISTORY [311]). 대소문자는 가리지 않고, 더 긴 영어 낱말 속 글자(Addon의 Add)는 물은 것으로 치지 않는다.
    seen을 주면(답 하나 동안 이미 보인 (영어, 화면 글자) 짝) 되풀이되는 단은 괄호 없이 하나만 보인다(티켓 50, 처음 한 번만).
    tab이면(표시 바로 뒤가 "탭") 한 단짜리 속성 창 탭 이름은 탭 글자로(tab_place).
    """
    parts = [part.strip() for part in re.split(r"[>‣]", path)]
    if names:
        parents = ["", *parts[:-1]]  # 단마다 바로 앞 단(같은 이름도 메뉴마다 글자가 달라서, 티켓 31)
        tab_glyph = names.tab_glyph(parts[0]) if tab and len(parts) == 1 else None
        parts = [_shown_part(part, tab_glyph or names.screen(part, parent)[1], asked, seen) for part, parent in zip(parts, parents)]
    return " > ".join(parts)


def _shown_part(part: str, korean: str | None, asked: str, seen: set | None = None) -> str:
    if not korean or korean == part:
        return part
    first = re.search(rf"(?<![A-Za-z]){re.escape(part)}(?![A-Za-z])", asked, re.IGNORECASE)  # 사용자가 부른 이름을 앞에
    if seen is not None:
        if (part, korean) in seen:
            return part if first else korean
        seen.add((part, korean))
    return f"{part}({korean})" if first else f"{korean}({part})"


def tab_place(before: str, after: str) -> bool:
    """이름이 속성 창 탭을 가리키는 자리인가: 이름(과 닫는 괄호·따옴표·굵은 글씨) 바로 뒤나 여는 괄호 바로 앞이 "탭"이고,
    이름 바로 앞이 "메뉴에서·메뉴의"가 아니다("상단 메뉴에서 [[Render]] 탭"은 맨 위 메뉴를 잘못 부른 것이라 메뉴 글자로 둔다)."""
    if not (re.match(r"[)\]'\"’”*]*\s*탭", after) or re.search(r"탭\s*\($", before.rstrip())):
        return False
    return not re.search(r"메뉴(?:에서|의|에)?\s+[*'\"‘“]*(?:[^\s()]+\s*\()?$", before)


def last_korean(shown: str) -> str:
    """바꾼 이름에서 조사가 붙는 한국어: 마지막 단의 괄호 앞 글("추가(Add)" → "추가"). 한글로 끝나지 않으면 빈 글(조사 안 고침)."""
    head = re.split(r"[>‣]", shown)[-1].split("(")[0].strip()
    return head if re.search(r"[가-힣]$", head) else ""


# 뒤에 조사가 바로 붙으면 "앞으로로"·"추가를 누르기를"처럼 읽히는 화면 글자: 조사·어미로 끝나거나(앞으로, 거리에 의해, 선택되지
# 않은) 목적어 조사가 든 명령 구절(리프 뼈대를 무시). 끝 글자만 보므로 "무게"처럼 멀쩡한 낱말도 걸리지만 고친 꼴이
# "'무게' 항목을"이라 해가 작다(티켓 50, HISTORY [355]·[356])
_AWKWARD_END = re.compile(r"(으로|에서|의해|에|게|않은|없는|있는|[은는한운된른])$")
_AWKWARD_MID = re.compile(r"[가-힣](을|를|으로|에서) ")


def _awkward(head: str) -> bool:
    return bool(_AWKWARD_END.search(head) or _AWKWARD_MID.search(head))


def with_particle(shown: str, text: str) -> tuple[str, str]:
    """바꾼 이름 shown과 그 뒤 글 text: 맨 앞 조사를 화면 글자에 맞춘다. 어색한 화면 글자면 따옴표로 묶고 '항목'을 넣어
    "'앞으로'(Forward) 항목으로"처럼 조사를 '항목'에 붙인다. 조사가 없거나 화면 글자가 한글이 아니면 그대로."""
    particle = PARTICLE.match(text)
    head = last_korean(shown)
    if not particle or not head:
        return shown, text
    if _awkward(head):
        at = shown.rfind(head)
        return f"{shown[:at]}'{head}'{shown[at + len(head):]} 항목", fit_particle("항목", text)
    return shown, fit_particle(head, text)


def looks_like_name(english: str) -> bool:
    """ko.po 문구 가운데 화면 이름 같은 것: 대문자로 시작하는 다섯 낱말 이하, 관사로 시작하지 않고 문장 부호·자리표시가 없음."""
    words = english.split()
    return (0 < len(words) <= 5 and english[0].isupper() and words[0] not in ARTICLES
            and not re.search(r'[%{}.:;!?"\\]', english))


def extra_names(names: "MenuNames", po_text: str, full_po_text: str) -> dict[str, str]:
    """넓힌 목록: 사전에 없는 화면 이름 → 한국어 화면 글자(티켓 49).

    10-27 번역 이름표 규칙 B(HISTORY [68], translate.screen_words)와 같이 ko.po에서 번역이 하나뿐인 이름 꼴의 문구를 담되,
    사전 만들기처럼 fr.po(번역률 100%)로 한국어 번역이 빠진 문맥(화면이 영어)이 있는 문구는 뺀다. 키 이름도 뺀다.
    사전에 있는 이름(제목 검수에서 떨어진 이름 포함)은 사전이 정한다.
    """
    found: dict[str, dict[str, set[str]]] = {}
    for context, english, korean in read_po(po_text):
        found.setdefault(english, {}).setdefault(korean, set()).add(context)
    used = {}
    for context, english, _ in read_po(full_po_text):
        used.setdefault(english, set()).add(context)
    extra = {}
    for english, koreans in found.items():
        if (english in KEY_NAMES or names.get(english) is not None
                or not looks_like_name(english) or len(koreans) != 1):
            continue
        korean, contexts = next(iter(koreans.items()))
        if korean != english and not used.get(english, set()) - contexts:
            extra[english] = korean
    return extra


_HANGUL = re.compile(r"[가-힣]")
# 영어 덩이: 대문자로 시작하는 낱말을 빈칸 하나로 이은 것. 앞이 영어·숫자·코드 글자면 다른 낱말의 일부라 보지 않는다
_RUN = re.compile(r"(?<![A-Za-z0-9_.`/\\-])[A-Z][A-Za-z0-9'\-]*(?:\.\.\.|…)?(?: [A-Za-z0-9][A-Za-z0-9'\-]*(?:\.\.\.|…)?)*")
_QUOTE_BEFORE = re.compile(r"설명서(?:의|에서|에는|에)\s*[\"“'‘]?\s*$")
_MAX_WORDS = 6
_HOLD_COMMON_WORDS = 6  # 흔히 옮기는 말(+꼬리) 앞부분으로 더 붙잡는 낱말 수 한도(목록 말은 대부분 4낱말 이하)
_HOLD_WORDS = 30  # 답이 흐르는 동안 붙잡는 영어 덩이의 낱말 수 한도(이보다 긴 덩이는 이름 하나로 맞을 일이 없다)


def _squash(text: str) -> str:
    return "".join(text.split())


# 이름 뒤에 모델이 붙이는 종류 낱말(꼬리). "면 선택 모드(Face)" → "페이스(Face) 선택 모드"(㉠, HISTORY [360]).
# 목록 시험의 맞추기 코드(124619_흔히옮기는말_견주기/자리.py TAILS)와 같다
COMMON_TAILS = ("선택 모드", "모드", "도구", "창", "값", "방식", "브러시", "물체", "버튼", "옵션", "메뉴", "패널", "탭", "항목", "칸", "설정", "기능",
                "노드")  # '노드'는 11-16 밤에 더함(화면 종류 낱말, "이미지 텍스처 노드(이미지 텍스처, Image Texture)"가 남아서, [373])
_TAIL_RE = "|".join(re.escape(t).replace(r"\ ", r"\s*") for t in sorted(COMMON_TAILS, key=len, reverse=True))


def _common_span(head: str, variants: Iterable[str]) -> tuple[int, str] | None:
    """괄호 바로 앞 글 head의 끝이 '흔히 옮기는 말 + (꼬리)'이면 (그 말이 시작하는 자리, 꼬리 글)을 돌려준다.
    빈칸은 무시하고 맞추고("루프 컷"/"루프컷"), 말 앞이 한글·영숫자면 다른 낱말의 일부라 보지 않는다("옆면"의 "면")."""
    text = head.rstrip()
    for v in variants:
        body = r"\s*".join(re.escape(ch) for ch in _squash(v))
        m = re.search(rf"({body})(\s*(?:{_TAIL_RE}))?$", text)
        if m and not re.search(r"[가-힣A-Za-z0-9]$", text[: m.start(1)]):
            return m.start(1), (m.group(2) or "").strip()
    return None


def _run_parts(words: list[str], names: "MenuNames", keep: set[str], in_path: bool) -> list[tuple[str, str | None]] | None:
    """덩이를 긴 이름부터 맞춘 (영어, 한국어 화면 글자) 목록. 못 맞춘 낱말이 남거나, 여러 낱말 덩이가 이름 하나로 맞지 않으면
    None(통째로 둔다). "Follow Path"처럼 사전에 없는 긴 이름을 낱말마다 쪼개 바꾸면 화면에 없는 글이 된다(2026-11-16 저장된 답으로 확인)."""
    parts, i = [], 0
    while i < len(words):
        for size in range(min(_MAX_WORDS, len(words) - i), 0, -1):
            english = " ".join(words[i : i + size])
            if english in keep or english in PROGRAM_NAMES or (english in OBJECT_DEFAULTS and not in_path):
                parts.append((english, None))
                break
            if english.isupper() or english in KEY_NAMES:
                continue  # 대문자 값(SCULPT)·한 글자(S 키, W 단위)·키 이름은 이름으로 치지 않는다
            found, korean = names.in_prose(english)
            if found:
                parts.append((english, korean))
                break
        else:
            return None
        i += size
    if len(parts) > 1 and any(korean is not None for _, korean in parts):
        return None
    return parts


def screen_prose(
    text: str, names: "MenuNames", asked: str = "", keep: Iterable[str] = (), start: int = 0, changed: list | None = None,
    seen: set | None = None,
) -> str:
    """[[ ]]로 감싸지 않은 답 글 속 블렌더 이름을 화면 글로 바꾼다(한국어 화면일 때만 부른다, 티켓 49).

    - 맨 영어 "Bevel 모디파이어" → "베벨(Bevel) 모디파이어"(질문에 영어로 쓴 이름은 "Bevel(베벨)", [311])
    - 화면과 다른 한국어를 붙인 "면(Face)" → 앞말 뒤에 따옴표 친 화면 글자 "면 '페이스'(Face)"(Fable 꼴, 시험 중 [393])
    - 화면과 다른 한국어 풀이가 뒤에 붙은 "Scale(크기 조절)" → 풀이 괄호를 지운 "스케일(Scale)"([349]·[353])
    그대로 두는 것: 코드(백틱 속·밑줄·점으로 이은 이름), 단축키(뒤에 '키', +로 이음), "설명서의 …" 인용, keep(작업 상태의
    물체 이름), 프로그램 이름, 대문자 값, 사전·넓힌 목록에 없는 낱말이 섞인 덩이, 화면도 영어인 이름.
    start 앞 글은 앞뒤를 보는 데만 쓰고 바꾸지 않는다(답이 흐르는 동안 이미 내보낸 글).
    changed를 주면 바꾼 자리마다 (원래 글, 바뀐 글)을 덧붙인다(저장된 답으로 검증할 때 쓴다).
    seen은 screen_path와 같다(답 하나 동안 이미 보인 짝은 괄호 없이, 괄호 꼴로 보인 짝은 여기에 더함).
    """
    keep = set(keep)
    edits: list[tuple[int, int, str]] = []
    for match in _RUN.finditer(text):
        s, e = match.span()
        if s < max(start, edits[-1][1] if edits else 0):
            continue  # 이미 내보낸 글이거나, 앞에서 고친 범위 안("Edge Weight(또는 Vertex Group)"의 Vertex Group)
        before, after = text[:s], text[e:]
        words = match.group().split(" ")
        if (before.count("`") % 2 or _QUOTE_BEFORE.search(before) or re.match(r"\s*키", after)
                or re.search(r"\+\s*$", before) or re.match(r"\s*\+", after) or re.match(r"[_.][A-Za-z0-9]", after)
                or re.search(r"[A-Za-z]/$", before) or re.match(r"/[A-Za-z]", after)
                or MODIFIER_KEYS & set(words)):
            continue
        parts = _run_parts(words, names, keep, bool(re.search(r"[>‣▸]\s*$", before)))
        if parts is None:
            continue
        others: tuple[str, ...] = ()  # 탭 자리면 같은 이름의 다른 글자("렌더(Render) 탭"의 렌더)도 앞말로 통째로 바꾼다
        if len(parts) == 1 and tab_place(before, after) and (tab := names.tab_glyph(parts[0][0])):
            parts, others = [(parts[0][0], tab)], names.glyphs(parts[0][0])
        whole = len(parts) == 1 and parts[0][1] not in (None, parts[0][0]) and parts[0][0] not in keep
        glossed = re.search(r"([가-힣]+)\s*\($", before)
        if before.rstrip().endswith("("):
            # 모델이 스스로 옮긴 말이 흔히 옮기는 말이면 앞말을 통째로 화면 글자로(티켓 50 가). 괄호 뒤가 '하다' 꼴이면
            # 앞말은 동사의 일부라("화면이 회전(Orbit)합니다") 바꾸지 않는다
            head = before.rstrip()[:-1]
            span = (_common_span(head, (*names.common(parts[0][0]), parts[0][1], *others))  # 화면 글자 자신 + 꼬리도 ㉠으로
                    if whole and after.startswith(")") and not re.match(r"\)(하(?!나)|합|했|해|함|한|할)", after) else None)
            floor = max(start, edits[-1][1] if edits else 0)
            if span and span[0] >= floor:
                at, tail = span
                core = _squash(head).removesuffix(_squash(tail))
                # 앞말이 이미 화면 글자로 끝나면 둔다("에지를 베벨(Bevel Edges)"). 화면 글자 + 꼬리면 꼬리만 괄호 뒤로
                if not core.endswith(_squash(parts[0][1])) or (tail and _squash(head[at:]).removesuffix(_squash(tail)) == _squash(parts[0][1])):
                    new = _shown_part(parts[0][0], parts[0][1], asked, seen)
                    end = e + 1
                    if tail and _squash(parts[0][1]).endswith(_squash(tail)):
                        tail = ""  # 화면 글자가 꼬리 낱말로 끝나면("값") 꼬리를 또 붙이지 않는다("값(Value) 값" 막기)
                    if tail:
                        new += " " + tail
                    else:
                        marks = re.match(r"(?:\*\*|['\"”’])*", after[1:]).group()  # 닫는 따옴표·굵은 글씨 뒤 조사도 맞춘다
                        particle = PARTICLE.match(after[1 + len(marks):])
                        if particle and marks:
                            new += marks + fit_particle(last_korean(new), particle.group())
                            end += len(marks) + particle.end()
                        elif particle:
                            new = "".join(with_particle(new, particle.group()))
                            end += particle.end()
                    edits.append((at, end, new))
                    continue
            # 한국어(영어) 꼴(Fable 꼴, HISTORY [393]): 괄호 속이 이 이름 하나이고 괄호 앞 한국어가 화면 글자와 다르면,
            # 앞말은 두고 그 뒤에 따옴표 친 화면 글자를 붙인다("세계 배경(World)이" → "세계 배경 '월드'(World)가").
            # 앞말은 설명("옵션(Only Selected)")이나 동사일 때가 많아 지우지 않는다. 거부된 "면(페이스, Face)"를 대신한다([349])
            if glossed and whole and after.startswith(")"):
                korean = parts[0][1]
                if not _squash(before[: glossed.end()].rstrip()[:-1]).endswith(_squash(korean)):
                    edit = _fable_form(before, after, parts[0][0], korean, names, max(start, edits[-1][1] if edits else 0))
                    if edit:
                        edits.append((edit[0], e + edit[1], edit[2]))
                    else:
                        continue  # 모델 꼴 그대로면 화면 글자를 아직 안 보였으니 '보인 짝'에 넣지 않는다("회전(Orbit)합니다" 뒤 [[Orbit]])
                if seen is not None:
                    seen.add(parts[0])  # 모델이 직접 쓴 "에디트 모드(Edit Mode)"도 보인 것으로
            continue
        explained = re.match(r"\s*\(\s*([^()\n]*)\)", after)
        if explained and _HANGUL.match(explained.group(1)):
            # 영어(한국어) 꼴: 모델이 이름 뒤에 붙인 풀이 괄호는 지우고 보통 꼴로 낸다("Union(합집합)" → "결합(Union)").
            # 풀이를 괄호 속에 남긴 "결합(Union, 합집합)"은 거부된 꼴이고([349]), 덧붙인 괄호는 지우기로 했다([353]·[354]).
            # 괄호 속이 화면 글자로 시작하면 영어(화면 글자) 그대로 두되 뒤에 덧붙인 것만 지운다("Focal Length(초점의 길이, Focal Length)")
            if whole:
                gloss = _squash(explained.group(1))
                if gloss.startswith(_squash(parts[0][1])):
                    # 화면 글자 뒤에 쉼표로 덧붙인 것만 지운다("Active(활성 물체)"처럼 화면 글자로 시작하는 풀이는 둔다)
                    if re.match(rf"\s*{re.escape(parts[0][1])}\s*,", explained.group(1)):
                        edits.append((s, e + explained.end(), f"{match.group()}({parts[0][1]})"))
                    if seen is not None:
                        seen.add(parts[0])
                    continue
                new = _shown_part(parts[0][0], parts[0][1], asked, seen)
                taken, tail = _after_name(after[explained.end() :], last_korean(new), new)
                edits.append((s, e + explained.end() + taken, tail))
            continue
        shown = " ".join(english if english in keep else _shown_part(english, korean, asked, seen) for english, korean in parts)
        if shown != match.group():
            particle = PARTICLE.match(after)  # 모델이 영어 이름에 맞춰 쓴 조사를 화면 글자에 맞춘다(티켓 50)
            if particle:
                edits.append((s, particle.end() + e, "".join(with_particle(shown, particle.group()))))
            else:
                edits.append((s, e, shown))
    for a, b, new in sorted(edits, reverse=True):
        if changed is not None:
            changed.append((text[a:b], new))
        text = text[:a] + new + text[b:]
    return text


_HADA_AFTER = re.compile(r"\)(하(?!나)|합|했|해|함|한|할)")  # 괄호에 바로 붙은 '하다' 꼴("회전(Orbit)합니다")
_CONNECT = re.compile(r"(고|거나|며|면서|여|어|아|해|서|게|채|지)$")  # 이어 주는 꼴로 끝난 앞말("녹여", "펼치고")
_PAIRS = {"'": "'‘", '"': '"“', "’": "‘'", "”": "“\""}  # 닫는 따옴표 → 그 짝이 될 여는 따옴표
# 앞말을 연 따옴표: 줄 첫머리·빈칸·여는 괄호 뒤에서 열고, 괄호까지 다른 따옴표·줄바꿈이 없다(짧은 앞말만, prose_cut과 같은 길이)
_QUOTE_HOLD = 30
_OPENER = re.compile(rf"(?:^|(?<=[\s(]))(['\"‘“])(?=[^\s'\"‘“’”])[^'\"‘“’”\n]{{1,{_QUOTE_HOLD}}}$")
_DROP_PREV = re.compile(r"([.,:)\]]|의|에서|에|은|는|을|를)$")


def _after_name(rest: str, korean: str, new: str, awkward: bool = True) -> tuple[int, str]:
    """바꾼 이름 new 바로 뒤 글 rest의 조사를 화면 글자 korean에 맞춘다: (rest에서 먹은 길이, new + 맞춘 뒤 글).

    굵은 글씨 표시(`**`)를 건너 조사를 찾는다("**차집합 '차이'(Difference)**으로" → "…**로", [374]와 같게).
    조사가 없으면 아무것도 먹지 않는다(표시는 rest에 그대로 남는다). awkward면 어색한 화면 글자에 '항목'을 넣는다(with_particle)."""
    marks = re.match(r"(?:\*\*)*", rest).group()
    particle = PARTICLE.match(rest[len(marks):])
    if not particle:
        return 0, new
    if marks or not korean or not awkward:
        return len(marks) + particle.end(), new + marks + (fit_particle(korean, particle.group()) if korean else particle.group())
    if new.endswith(")") and f"'{korean}'(" in new:  # Fable 꼴: 화면 글자가 이미 따옴표 안이라 '항목'만 넣는다
        return particle.end(), new + (f" 항목{fit_particle('항목', particle.group())}" if _awkward(korean) else fit_particle(korean, particle.group()))
    shown, text = with_particle(new, particle.group())
    return particle.end(), shown + text


def _stem(word: str) -> str:
    return re.sub(r"(을|를|에|의|으로|로|이|가|은|는)$", "", word) if len(word) > 2 else word


def _fable_form(before: str, after: str, english: str, korean: str, names: "MenuNames", floor: int) -> tuple[int, int, str] | None:
    """한국어(영어) 자리를 Fable 꼴로 바꿀 (시작, 괄호 뒤로 더 먹는 길이, 새 글). 바꾸지 않으면 None.

    Fable 재검토(`results/20261116/214634_72자리_fable검토/02_꼴_만들기.py`)의 고른 조합: 괄호 뒤 '하다' 꼴과 이어 주는 꼴은 모델 꼴 그대로,
    앞말이 화면 글자의 낱말뿐이면 앞말을 지우고 이름만, 괄호 뒤가 닫는 따옴표면 따옴표를 앞말 뒤로, 나머지는 앞말 뒤에 '화면 글자'(영어)."""
    if _HADA_AFTER.match(after):
        return None
    head = before.rstrip()[:-1]  # 괄호 앞 글
    words = head.split(" ")
    last = words[-1].strip("*'\"“‘")
    if _CONNECT.search(last) and last not in names.glyph_words:
        return None
    paren = len(before.rstrip()) - 1
    rest = after[1:]
    named = f"'{korean}'({english})"
    glyph = {_stem(w) for w in korean.split()}
    k = 0
    # 모델이 붙인 굵은 글씨 표시는 낱말 비교에서 건너고 글에는 남긴다("**병합(Merge by Distance)**" → "**'거리로 병합'(…)**")
    while k < len(words) and words[-1 - k].lstrip("*") and _stem(words[-1 - k].lstrip("*")) in glyph:
        k += 1
    if k:
        prev = words[-1 - k] if k < len(words) else ""
        if prev == "" or _DROP_PREV.search(prev):
            at = len(" ".join(words[: len(words) - k])) + (1 if k < len(words) else 0)
            if at >= floor:
                bold = re.search(r"\*+", head[at:])  # 지우는 앞말 속 여는 굵은 글씨 표시는 이름 앞에 남긴다("거리로 **병합(" 도)
                taken, new = _after_name(rest, korean, named, awkward=True)
                return at, 1 + taken, (bold.group() if bold else "") + new
    if paren < floor:
        return None
    quote = re.match(r"['\"”’]", rest)
    if quote:
        # 앞말을 감싼 모델 따옴표("'정투영(Orthographic)'")는 떼고 화면 글자에만 따옴표를 둔다("정투영 '정사법'(Orthographic)").
        # 여는 따옴표를 이미 내보냈으면(floor 앞) 따옴표를 앞말 뒤로 옮기는 꼴로 둔다. 흐름에서는 prose_cut이 여는 따옴표부터 붙잡는다
        opener = _OPENER.search(before[:paren])
        if opener and opener.group(1) in _PAIRS[quote.group()] and opener.start(1) >= floor:
            inner = before[opener.end(1) : paren].rstrip()
            taken, new = _after_name(rest[1:], korean, f"{inner} {named}")
            return opener.start(1), 2 + taken, new
        taken, new = _after_name(rest[1:], korean, quote.group() + " " + named, awkward=True)
        return paren, 2 + taken, new
    taken, new = _after_name(rest, korean, " " + named, awkward=True)
    return paren, 1 + taken, new


def prose_cut(text: str, hold: set[str] | frozenset = frozenset(), tabs: bool = False) -> int:
    """답이 흐르는 동안 지금 바꿔 내보내도 되는 글의 끝(그 뒤는 다음 조각과 이어질 수 있어 붙잡는다).

    마지막 낱말, 그 앞에 빈칸 하나로 이어진 영어 낱말들, 자를 자리를 품은 닫히지 않은 괄호(와 그 앞 낱말·영어 덩이),
    닫히지 않은 백틱 뒤를 붙잡는다. hold(흔히 옮기는 말의 앞부분 낱말 줄, MenuNames.common_prefixes)를 주면
    붙잡은 끝 낱말과 이어 그 줄이 되는 앞 낱말들도 붙잡는다("직교 투영(" 앞의 "직교", 티켓 50 가).
    tabs면 속성 창 탭 이름으로 끝나는 낱말도 다음 낱말("탭"인지)이 올 때까지 붙잡는다(tab_place).
    닫히지 않은 짧은 따옴표(_QUOTE_HOLD자 이하)는 여는 따옴표부터 붙잡는다(_fable_form이 앞말을 감싼 따옴표를 뗀다).
    """
    cut = len(text)
    tick = text.rfind("`")
    if text.count("`") % 2 and len(text) - tick <= 200:
        cut = tick
    cut = min(cut, re.search(r"\S*$", text[: len(text.rstrip(" "))]).start())
    joined = 0  # 앞으로 이어 붙인 영어 낱말 수. 한도가 없으면 긴 영어 글에서 조각마다 처음부터 다시 돌아 매우 느려진다(검토 지적)
    tabbed = not tabs
    quoted = False
    while True:
        moved = cut
        paren = text.rfind("(", 0, cut)
        if paren > text.rfind(")", 0, cut) and cut - paren <= 80:
            moved = re.search(r"\S*\s*$", text[:paren]).start()
        if joined < _HOLD_WORDS and moved >= 2 and text[moved - 1] == " " and re.search(r"[A-Za-z0-9.…]$", text[: moved - 1]) and (
                moved == len(text) or re.match(r"[A-Za-z0-9]", text[moved:])):
            moved = re.search(r"\S*$", text[: moved - 1]).start()  # 빈칸 하나로 이어진 앞 영어 낱말
            joined += 1
        if moved == cut:
            cut = _hold_common(text, cut, hold) if hold else cut
            opener = None if quoted else _OPENER.search(text[:cut])
            if opener and opener.start(1) < cut:
                # 따옴표 속 앞말이 괄호로 이어질 수 있어 여는 따옴표부터 붙잡는다(_fable_form이 따옴표를 뗀다). 길이 한도로 닫는
                # 따옴표를 여는 것으로 잘못 봐도 잠깐만 붙잡는다
                quoted, cut = True, opener.start(1)
                continue
            tab = None if tabbed else _TAB_RUN.search(text[:cut])
            if not tab or tab.start() >= cut:
                return cut
            # 탭 이름에서 한 번 더 자르고, 그 앞 영어 덩이·열린 괄호도 위 규칙으로 함께 붙잡는다("Image Texture", "(Apply Modifiers)")
            tabbed, moved = True, tab.start()
        cut = moved


def _hold_common(text: str, cut: int, hold: set[str] | frozenset) -> int:
    """cut 바로 앞 낱말 1-3개가 hold의 줄이면(뒤에 붙잡은 낱말과 이어 목록 말이 될 수 있으면) 가장 긴 줄의 시작까지 붙잡는다."""
    for k in range(_HOLD_COMMON_WORDS, 0, -1):
        m = re.search(rf"(?<!\S)((?:[^\s()]+ ){{{k}}})$", text[:cut])
        if not m or m.group(1).strip().lstrip("*_'\"“‘`") not in hold:
            continue
        if re.match(r"[A-Za-z0-9]", m.group(1)) and re.search(r"[A-Za-z0-9.…] $", text[: m.start(1)]):
            continue  # 영어 덩이 가운데서 자르지 않게("Separate RGB"의 RGB부터 붙잡으면 Separate만 따로 바뀐다)
        return m.start(1)
    return cut


def screen_marks(text: str, names: "MenuNames | None") -> str:
    """글 속 [[메뉴 이름]] 표시를 모두 화면 글로 바꾼다(한 번에 다 있는 글, 예: 연습 과정 안내 말)."""
    return _MARK.sub(lambda match: screen_path(match.group(1), names), text)


EXTRA_FILE = "screen_extra.json"  # 넓힌 목록(extra_names). data/에 두고 커밋하지 않는다(번역 글자가 들어 있음)


def load_menu_names(
    data_dir: Path, menu_choices: Path = MENU_CHOICES, menu_titles: Path = MENU_TITLES, menu_common: Path = MENU_COMMON
) -> MenuNames | None:
    """메뉴 이름 사전(data_dir/menu_names/menu_names.json과 저장소의 고정 짝·통과 제목). 사전 파일이 없으면 None(영어 그대로 보임)."""
    names_path = data_dir / "menu_names" / "menu_names.json"
    if not names_path.exists():
        return None
    extra_path = data_dir / "menu_names" / EXTRA_FILE
    extra = json.loads(extra_path.read_text(encoding="utf-8")) if extra_path.exists() else {}
    if not isinstance(extra, dict) or not all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in extra.items()):
        raise ValueError(f"넓힌 목록 {extra_path}: '영어 이름': '한국어 화면 글자' 모양이어야 함(menu_names extra로 다시 만든다)")
    # 흔히 옮기는 말 목록(티켓 50 가, HISTORY [360]·[376]). Haiku가 만든 낱말이고 화면 글자와 같은 말은 빼서 저장소에 둔다
    common_path = menu_common
    common = json.loads(common_path.read_text(encoding="utf-8"))["lists"]
    if not isinstance(common, dict) or not all(isinstance(k, str) and isinstance(v, list) and all(isinstance(x, str) for x in v)
                                               for k, v in common.items()):
        raise ValueError(f"흔히 옮기는 말 목록 {common_path}: {{'lists': {{'영어 이름': ['한국어 말', …]}}}} 모양이어야 함")
    return MenuNames.load(names_path, MenuNames.load_choices(menu_choices), MenuNames.load_titles(menu_titles), extra, common)


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
        title = title.removeprefix("– ")  # 화면 표시 방식 소제목은 "– Material Preview"처럼 줄표로 시작한다
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
    사전을 만든 뒤 넓힌 목록도 쓴다(screen_extra.json, 티켓 49).

    넓힌 목록만 다시: python -m blender_tutor.menu_names extra <ko.po> <fr.po> <사전 폴더>
    """
    if argv[:1] == ["extra"] and len(argv) == 4:
        return _main_extra(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    if len(argv) != 4:
        print(main.__doc__)
        return 2
    root, po, full_po, out = Path(argv[0]), Path(argv[1]), Path(argv[2]), Path(argv[3])
    aliases = MenuNames.load_aliases(MENU_ALIASES)
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
    return _main_extra(po, full_po, out)


def _main_extra(po: Path, full_po: Path, out: Path) -> int:
    """사전 폴더의 menu_names.json으로 넓힌 목록을 만들어 같은 폴더에 쓴다."""
    names = MenuNames.load(out / "menu_names.json", MenuNames.load_choices(MENU_CHOICES), MenuNames.load_titles(MENU_TITLES))
    extra = extra_names(names, po.read_text(encoding="utf-8"), full_po.read_text(encoding="utf-8"))
    (out / EXTRA_FILE).write_text(json.dumps(extra, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"넓힌 목록 {len(extra)}개 → {out / EXTRA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
