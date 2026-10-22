"""자료 준비: 설명서 HTML 묶음을 소제목 단위 청크로 자른다(한 번 돌리는 프로그램, 비용 없음).

규칙은 .scratch/mvp-roundtrip/spec.md의 "자료 준비"와 티켓 06·07·19를 따른다.
"""

import copy
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

BASE_URL = "https://docs.blender.org/manual/en/5.2/"  # 근거 링크는 /en/5.2/<경로>.html#<앵커>로 고정(티켓 02)
MAX_WORDS = 400  # 소제목 글이 이보다 길면 옵션 경계(없으면 문단 끝)에서 고르게 나눈다(티켓 06·19)

_HEADING = re.compile(r"^h[1-6]$")
# 앞뒤로 빈 줄을 두는 태그(나머지는 글 속에 이어 붙는다: em, kbd, a, span 등)
_BLOCK = {"p", "div", "dl", "dt", "dd", "ul", "ol", "li", "table", "tr", "pre", "figure", "blockquote", "caption"}
_PATH_ALT = re.compile(r"[\\/]|\.(png|jpe?g|gif|webp|svg)$", re.IGNORECASE)  # 파일 경로뿐인 alt
# 그림·영상 자리에 넣는 보이지 않는 표식. 글을 나눈 뒤 어느 조각에 어떤 주소가 들었는지 찾는 데 쓰고 지운다
_MARK_OPEN, _MARK_CLOSE = "\ue000", "\ue001"  # 유니코드 사용자 영역 글자라 설명서 글에는 나오지 않는다
_MEDIA_MARK = re.compile(_MARK_OPEN + r"(\d+)" + _MARK_CLOSE)
_KEY_MARK = "\ue002"  # 옵션 이름에서 단축키 키 하나를 잠시 바꿔 두는 글자
_SHORTCUT = re.compile(_KEY_MARK + r"(\s*[-+]\s*" + _KEY_MARK + ")*")
# 메뉴 경로·버튼 이름 앞뒤에 두는 표식. 글을 나눈 뒤 어느 조각에 어떤 블렌더 표기가 들었는지 찾는 데 쓰고 지운다
_UI_OPEN, _UI_CLOSE = "\ue003", "\ue004"
_UI_MARK = re.compile(_UI_OPEN + "([^" + _UI_CLOSE + "]*)" + _UI_CLOSE)
_UI_CLASSES = {"menuselection", "guilabel"}  # 설명서가 메뉴 경로(Add ‣ Mesh)와 버튼 이름에 붙이는 표시
# 검색에서 빼는 폴더: 기여자용 쪽(티켓 06), Sphinx가 만든 원문·그림·꾸밈 파일
_SKIP_FOLDERS = {"contribute", "_sources", "_images", "_static"}
_SKIP_PAGES = {"genindex", "search", "404"}  # 색인·검색·없는 쪽 안내(설명 글이 아님)


class MediaKind(StrEnum):
    """그림·영상 종류. 정해 둔 이름만 쓴다(오타를 내면 바로 오류가 난다)."""

    IMAGE = "그림"
    VIDEO = "영상"


@dataclass(frozen=True)
class Example:
    """영상만·그림만 있는 소제목. 청크로 만들지 않고 같은 쪽 바로 앞 청크에 붙인다(티켓 07)."""

    kind: MediaKind
    heading: str  # 그 소제목 제목
    url: str  # 그 소제목 링크
    media: tuple[str, ...]  # 영상·그림 주소


@dataclass(frozen=True)
class Chunk:
    """청크 하나. 위계는 분야 > 묶음 > 쪽 > 소제목(여러 겹) > 옵션."""

    page_path: str  # 쪽 경로(.html 뺀 것, 예: modeling/modifiers/generate/bevel)
    anchor: str  # 소제목 앵커. 긴 소제목을 나눈 청크도 같은 앵커
    field: str  # 분야(경로 첫 폴더, 예: modeling)
    group: str  # 묶음(폴더 경로, 예: modeling/modifiers/generate)
    page_title: str  # 쪽 제목
    headings: tuple[str, ...]  # 쪽 제목 아래 소제목 경로. 쪽 첫머리 글이면 빈 묶음
    body: str  # 본문 글
    option_path: tuple[str, ...] = ()  # 긴 옵션을 나눈 뒤 조각이면 그 옵션·범주 경로(예: Operation > Trigonometric)
    options: tuple[str, ...] = ()  # 이 청크에 든 옵션 이름(정의 목록의 항목 이름, 단축키 글자는 뗌)
    images: tuple[str, ...] = ()  # 글 속 그림 주소
    videos: tuple[str, ...] = ()  # 글 속 영상 주소
    examples: tuple[Example, ...] = ()  # 뒤따르는 영상만·그림만 있는 소제목
    reference: tuple[tuple[str, str], ...] = ()  # "모드·메뉴·단축키" 상자(예: ("Mode", "Edit Mode")), 여럿이면 차례로
    ui_names: tuple[str, ...] = ()  # 글 속 메뉴 경로(예: Add ‣ Mesh)·버튼 이름, 처음 나온 차례로 한 번씩(티켓 20)

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.page_path}.html#{self.anchor}"

    @property
    def address(self) -> str:
        """연습 과정 파일이 소제목을 가리키는 꼴(경로.html#앵커)."""
        return f"{self.page_path}.html#{self.anchor}"

    @property
    def path(self) -> str:
        """근거 목록에 보이는 '쪽 제목 > 소제목' 경로. 긴 소제목을 나눈 조각도 모두 같다."""
        return " > ".join((self.page_title, *self.headings))

    @property
    def has_image(self) -> bool:
        """그림 있음: 글 속 그림이나 뒤따르는 그림 예시."""
        return bool(self.images) or any(example.kind == MediaKind.IMAGE for example in self.examples)

    @property
    def video_links(self) -> tuple[str, ...]:
        """영상 링크: 글 속 영상, 그다음 뒤따르는 영상 예시의 영상."""
        examples = [media for example in self.examples if example.kind == MediaKind.VIDEO for media in example.media]
        return (*self.videos, *examples)

    @property
    def words(self) -> int:
        """본문 낱말 수(나눌 때와 같은 셈: 띄어쓰기로 자른 수)."""
        return len(self.body.split())

    @property
    def text(self) -> str:
        """검색·답변에 쓰는 글: 맨 앞에 '쪽 제목 > 소제목 (> 옵션 > 범주)' 경로를 붙인다."""
        return " > ".join((self.path, *self.option_path)) + "\n\n" + self.body


def chunk_manual(root: Path) -> list[Chunk]:
    """설명서 HTML 묶음 폴더 전체를 청크로 자른다. 기여자용 쪽, 색인·검색 쪽, Sphinx가 만든 보조 폴더는 뺀다."""
    chunks: list[Chunk] = []
    for file in sorted(root.rglob("*.html")):
        relative = file.relative_to(root)
        page_path = relative.with_suffix("").as_posix()
        if relative.parts[0] in _SKIP_FOLDERS or page_path in _SKIP_PAGES:
            continue
        chunks += chunk_page(file.read_text(encoding="utf-8"), page_path)
    return chunks


def chunk_page(html: str, page_path: str) -> list[Chunk]:
    """설명서 쪽 하나(HTML 전체)를 청크 목록으로 자른다."""
    # 옆 목차가 쪽마다 커서(수백 KB) 본문만 잘라 읽는다
    start, end = html.find("<article"), html.find("</article>")
    if start != -1 and end != -1:
        html = html[start : end + len("</article>")]
    article = BeautifulSoup(html, "html.parser").find("article")
    top = article.find("section") if article else None
    if top is None:
        return []
    folders = page_path.split("/")[:-1]
    page = _Page(page_path, folders[0] if folders else "", "/".join(folders), _title(top))
    chunks: list[Chunk] = []
    waiting: list[Example] = []  # 앞 청크가 없어 다음 청크에 붙일 예시
    for section, headings in _sections(top, ()):
        media = _mark_media(section, page.url)
        units = _units(_content(section))
        if not units and not media:
            continue  # 제목뿐(아래 소제목의 경로에만 남음)이거나 목차뿐
        # 글이 없고 영상이나 캡션 없는 그림만 있으면(0단어) 앞 청크의 예시로
        if all(unit.text == "[그림]" for unit in units):
            example = _example(section, headings, page, media)
            if chunks:
                chunks[-1] = replace(chunks[-1], examples=(*chunks[-1].examples, example))
            else:
                waiting.append(example)
            continue
        for in_chunk in _pack(units):
            chunks.append(_chunk(section, headings, page, in_chunk, media, tuple(waiting)))
            waiting = []
    return chunks


@dataclass(frozen=True)
class _Page:
    path: str
    field: str
    group: str
    title: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.path}.html"


@dataclass(frozen=True)
class _Media:
    kind: MediaKind
    urls: tuple[str, ...]


@dataclass
class _Unit:
    """나눌 때 쪼개지 않는 글 한 덩이: 문단 하나, 옵션 하나, 값 이름 + 설명 한 쌍 등."""

    text: str
    option: str | None = None  # 이 덩이가 속한 옵션 이름
    media: list[int] = field(default_factory=list)  # 이 덩이에 든 그림·영상 번호
    reference: tuple[tuple[str, str], ...] = ()  # "모드·메뉴·단축키" 상자면 그 칸들
    path: tuple[str, ...] = ()  # 긴 옵션을 나눈 덩이면 글에 이름이 빠진 옵션·범주 경로
    ui_names: tuple[str, ...] = ()  # 이 덩이에 든 메뉴 경로·버튼 이름

    @property
    def words(self) -> int:
        return len(self.text.split())


def _sections(section: Tag, headings: tuple[str, ...]):
    """소제목을 문서 순서로 (소제목, 쪽 제목 아래 경로) 짝으로 내놓는다."""
    yield section, headings
    for child in section.children:
        if _is_section(child):
            yield from _sections(child, (*headings, _title(child)))


def _chunk(
    section: Tag,
    headings: tuple[str, ...],
    page: _Page,
    units: list[_Unit],
    media: list[_Media],
    examples: tuple[Example, ...],
) -> Chunk:
    return Chunk(
        page_path=page.path,
        anchor=section["id"],
        field=page.field,
        group=page.group,
        page_title=page.title,
        headings=headings,
        body="\n\n".join(unit.text for unit in units),
        option_path=units[0].path,
        options=tuple(dict.fromkeys(unit.option for unit in units if unit.option)),  # 긴 옵션을 나눈 덩이는 이름이 같다
        images=_urls(units, media, MediaKind.IMAGE),
        videos=_urls(units, media, MediaKind.VIDEO),
        examples=examples,
        reference=tuple(item for unit in units for item in unit.reference),
        ui_names=tuple(dict.fromkeys(name for unit in units for name in unit.ui_names)),
    )


def _example(section: Tag, headings: tuple[str, ...], page: _Page, media: list[_Media]) -> Example:
    kind = MediaKind.VIDEO if any(item.kind == MediaKind.VIDEO for item in media) else MediaKind.IMAGE
    return Example(
        kind=kind,
        heading=headings[-1] if headings else page.title,
        url=f"{page.url}#{section['id']}",
        media=tuple(url for item in media for url in item.urls),
    )


def _units(nodes) -> list[_Unit]:
    """소제목 내용을 덩이로 나눈다. 옵션 목록(값 목록이 아닌 정의 목록)은 항목 하나가 한 덩이."""
    units: list[_Unit] = []
    for node in nodes:
        if isinstance(node, Tag) and "refbox" in node.get("class", []):
            units.append(_reference_unit(node))
        elif _is_option_list(node):
            for dt in node.find_all("dt", recursive=False):
                units += _option_units(dt, _option_name(dt), ())
        else:
            units += _paragraph_units(_render(node) if isinstance(node, Tag) else _string(node))
    return _drop_empty(units)


def _option_units(dt: Tag, option: str, path: tuple[str, ...]) -> list[_Unit]:
    """옵션(또는 그 안의 범주) 하나를 덩이로. MAX_WORDS 안이면 한 덩이로 두고,
    넘으면 안쪽 범주 → 값(이름 + 설명 한 쌍) → 문단 경계에서 나눈다(티켓 19, 예: Math 노드의 Operation).
    """
    dds = _following_dds(dt)
    whole = _text_unit("".join(_render(tag) for tag in (dt, *dds)), option, path)
    if whole.words <= MAX_WORDS:
        return [whole]
    inner = (*path, _option_name(dt))  # 안쪽 덩이에는 이 이름이 글에 없으니 경로로 붙인다
    units: list[_Unit] = []
    for child in (child for dd in dds for child in dd.children):
        if _is_option_list(child):
            for sub in child.find_all("dt", recursive=False):
                units += _option_units(sub, option, inner)
        elif _is_value_list(child):
            for sub in child.find_all("dt", recursive=False):
                units.append(_text_unit("".join(_render(tag) for tag in (sub, *_following_dds(sub))), option, inner))
        else:
            units += _paragraph_units(_render(child) if isinstance(child, Tag) else _string(child), option, inner)
    units = _drop_empty(units)
    if not units:
        return [whole]  # 안쪽에서 나눌 글을 못 찾으면 통째로 둔다
    # 이름(dt)은 첫 덩이 앞에 둔다. 첫 덩이 글에 이름이 있으니 경로는 바깥 것만
    header = _text_unit(_render(dt), option, path)
    first = units[0]
    units[0] = replace(
        first,
        text=f"{header.text}\n\n{first.text}",
        media=header.media + first.media,
        path=path,
        ui_names=header.ui_names + first.ui_names,
    )
    return units


def _drop_empty(units: list[_Unit]) -> list[_Unit]:
    """글 없이 표식만 남은 덩이(영상 자리 등)는 빼고, 그 그림·영상 번호는 이웃 덩이로 넘긴다."""
    kept: list[_Unit] = []
    orphan: list[int] = []
    for unit in units:
        if unit.text:
            unit.media = orphan + unit.media
            orphan = []
            kept.append(unit)
        elif kept:
            kept[-1].media += unit.media
        else:
            orphan += unit.media
    if orphan and kept:
        kept[-1].media += orphan
    return kept


def _paragraph_units(raw: str, option: str | None = None, path: tuple[str, ...] = ()) -> list[_Unit]:
    """빈 줄로 나뉜 글을 문단마다 한 덩이로."""
    return [_take_marks(block, option, path) for block in _squashed_blocks(raw)]


def _text_unit(raw: str, option: str | None = None, path: tuple[str, ...] = ()) -> _Unit:
    """문단이 여럿이어도 통째로 한 덩이로."""
    return _take_marks("\n\n".join(_squashed_blocks(raw)), option, path)


def _squashed_blocks(raw: str) -> list[str]:
    blocks = (_squash(block) for block in re.split(r"\n\s*\n", raw))
    return [block for block in blocks if block]


def _take_marks(text: str, option: str | None, path: tuple[str, ...]) -> _Unit:
    """글에서 그림·영상 표식과 블렌더 표기 표식을 떼어 번호·이름은 덩이에 적는다."""
    media = [int(n) for n in _MEDIA_MARK.findall(text)]
    ui_names = tuple(_UI_MARK.findall(text))
    return _Unit(_plain(_MEDIA_MARK.sub("", text)).strip(), option, media, path=path, ui_names=ui_names)


def _pack(units: list[_Unit]) -> list[list[_Unit]]:
    """덩이를 청크로 묶는다. MAX_WORDS 안에 들도록 가장 적은 수로 나누되, 조각 크기는 고르게.

    앞에서부터 꽉 채우면 꼬리가 아주 작아질 수 있어(400 + 10), 같은 조각 수가 나오는 가장 작은 한도를 찾아
    그 한도로 다시 채운다(205 + 205 쯤). 한 덩이가 한도를 넘으면 그 덩이만 따로 둔다.
    """
    count = len(_fill(units, MAX_WORDS))
    low, high = 1, MAX_WORDS
    while low < high:
        middle = (low + high) // 2
        if len(_fill(units, middle)) <= count:
            high = middle
        else:
            low = middle + 1
    return _fill(units, low)


def _fill(units: list[_Unit], limit: int) -> list[list[_Unit]]:
    """앞에서부터 limit 단어까지 채워 묶는다."""
    pieces: list[list[_Unit]] = []
    current: list[_Unit] = []
    total = 0
    for unit in units:
        if current and total + unit.words > limit:
            pieces.append(current)
            current, total = [], 0
        current.append(unit)
        total += unit.words
    if current:
        pieces.append(current)
    return pieces


def _reference_unit(box: Tag) -> _Unit:
    """"모드·메뉴·단축키" 상자를 'Mode: Edit Mode' 꼴 줄로 쓴 한 덩이로."""
    items = []  # 블렌더 표기 표식이 든 채로. 글의 표식은 _take_marks가 떼고, 메타데이터 칸에는 뗀 것을 둔다
    for dt in box.find_all("dt"):
        key = _squash(_render(dt)).rstrip(":").strip()
        value = _squash("".join(_render(dd) for dd in _following_dds(dt)))
        items.append((key, value))
    title = box.find(class_="admonition-title")
    lines = ([_squash(_render(title))] if title else []) + [f"{key}: {value}" for key, value in items]
    reference = tuple((_plain(key), _plain(value)) for key, value in items)
    return replace(_take_marks("\n\n".join(lines), None, ()), reference=reference)


def _following_dds(dt: Tag) -> list[Tag]:
    dds = []
    for sibling in dt.find_next_siblings():
        if sibling.name != "dd":
            break
        dds.append(sibling)
    return dds


def _option_name(dt: Tag) -> str:
    """옵션 이름에서 뒤에 붙은 단축키(Shift-A 등, 키를 잇는 -·+까지)를 뗀다."""
    name = copy.copy(dt)
    for kbd in name.find_all("kbd"):
        kbd.replace_with(NavigableString(_KEY_MARK))
    return _plain(_squash(_SHORTCUT.sub("", _render(name))))


def _is_option_list(node) -> bool:
    """옵션 목록: 정의 목록(dl) 가운데 값 목록이 아닌 것."""
    return isinstance(node, Tag) and node.name == "dl" and "field-list" not in node.get("class", [])


def _is_value_list(node) -> bool:
    """값 목록: 'Vertices: 설명'처럼 값 이름과 설명이 짝인 목록(field-list)."""
    return isinstance(node, Tag) and node.name == "dl" and "field-list" in node.get("class", [])


def _urls(units: list[_Unit], media: list[_Media], kind: MediaKind) -> tuple[str, ...]:
    return tuple(url for unit in units for n in unit.media if media[n].kind == kind for url in media[n].urls)


def _render(node: Tag) -> str:
    """태그 안 글. 블록 태그 앞뒤는 빈 줄, 표의 칸은 ' | '로 잇는다."""
    if "headerlink" in node.get("class", []) or "toctree-wrapper" in node.get("class", []):
        return ""
    if node.name == "tr":
        cells = node.find_all(["td", "th"], recursive=False)
        return "\n\n" + " | ".join(_squash(_render(cell)) for cell in cells) + "\n\n"
    inner = "".join(_render(child) if isinstance(child, Tag) else _string(child) for child in node.children)
    if node.name == "span" and _UI_CLASSES & set(node.get("class", [])):
        return f"{_UI_OPEN}{_squash(inner)}{_UI_CLOSE}"
    if node.name in _BLOCK or _HEADING.match(node.name):
        return f"\n\n{inner}\n\n"
    return inner


def _string(node) -> str:
    return "" if isinstance(node, Comment) else str(node)


def _squash(text: str) -> str:
    """줄바꿈·여러 빈칸을 빈칸 하나로."""
    return " ".join(text.split())


def _plain(text: str) -> str:
    """블렌더 표기 표식을 지운다(이름 글자는 남긴다)."""
    return text.replace(_UI_OPEN, "").replace(_UI_CLOSE, "")


def _mark_media(section: Tag, page_url: str) -> list[_Media]:
    """소제목 내용(아래 소제목 빼고)의 그림 자리를 [그림: 캡션]/[그림] 글로 바꾸고 그림·영상 자리에 표식을 넣는다.

    표식 번호 순서의 주소 목록을 돌려준다.
    """
    media: list[_Media] = []

    def mark(holder: Tag, item: _Media, label: str) -> None:
        holder.replace_with(NavigableString(f"\n\n{label}{_MARK_OPEN}{len(media)}{_MARK_CLOSE}\n\n"))
        media.append(item)

    # 단계마다 내용을 새로 찾는다: 앞 단계에서 떼어 낸 그림 상자 속 img를 다시 잡지 않도록
    for frame in _find_in_content(section, "iframe"):
        mark(frame, _Media(MediaKind.VIDEO, (frame["src"],)), "")
    for holder in _find_in_content(section, "figure"):
        urls = tuple(urljoin(page_url, img["src"]) for img in holder.find_all("img"))
        mark(holder, _Media(MediaKind.IMAGE, urls), _figure_label(holder.find("figcaption"), holder.find("img")))
    for img in _find_in_content(section, "img"):
        mark(img, _Media(MediaKind.IMAGE, (urljoin(page_url, img["src"]),)), _figure_label(None, img))
    return media


def _content(section: Tag) -> list:
    """소제목의 내용: 제목과 아래 소제목을 뺀 바로 아래 것들."""
    return [child for child in section.children if not _is_section(child) and not _is_heading(child)]


def _find_in_content(section: Tag, name: str) -> list[Tag]:
    """소제목 내용 안의 name 태그(아래 소제목 속 것은 빼고)."""
    tags = [node for node in _content(section) if isinstance(node, Tag)]
    return [found for tag in tags for found in ([tag] if tag.name == name else []) + tag.find_all(name)]


def _figure_label(caption: Tag | None, img: Tag | None) -> str:
    """캡션이 있으면 [그림: 캡션], 캡션이 없고 alt가 설명 글이면 [그림: alt], 둘 다 없으면 [그림]."""
    if caption is not None:
        label = _squash(_render(caption))
    else:
        alt = (img.get("alt") or "").strip() if img is not None else ""
        label = "" if _PATH_ALT.search(alt) else alt
    return f"[그림: {label}]" if label else "[그림]"


def _is_section(node) -> bool:
    return isinstance(node, Tag) and node.name == "section"


def _is_heading(node) -> bool:
    return isinstance(node, Tag) and bool(_HEADING.match(node.name))


def _title(section: Tag) -> str:
    return _plain(_squash(_render(section.find(_HEADING))))


def main(argv: list[str]) -> int:
    """사용법: python -m blender_tutor.manual_chunks <설명서 HTML 폴더> <청크 JSONL 파일>

    예: python -m blender_tutor.manual_chunks data/manual_en_5.2/html/blender_manual_v520_en.html data/chunks/manual_chunks.jsonl
    (설명서 HTML 폴더는 zip을 푼 폴더로, 이름이 .html로 끝나지만 폴더다)

    청크를 한 줄에 하나씩 JSON으로 쓰고 개수를 알린다(중간 점검용). 결과는 data/에 두고 커밋하지 않는다.
    """
    if len(argv) != 2:
        print(main.__doc__)
        return 2
    root, out = Path(argv[0]), Path(argv[1])
    chunks = chunk_manual(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as file:
        for chunk in chunks:
            row = {**asdict(chunk), "url": chunk.url, "text": chunk.text}
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    sizes = [len(chunk.body.split()) for chunk in chunks]
    pieces = {}  # 나눈 소제목(쪽 경로, 앵커) → 조각 단어 수들
    for chunk, size in zip(chunks, sizes):
        pieces.setdefault((chunk.page_path, chunk.anchor), []).append(size)
    split = [sizes for sizes in pieces.values() if len(sizes) > 1]
    print(f"청크 {len(chunks)}개 (쪽 {len({chunk.page_path for chunk in chunks})}개) → {out}")
    print(f"  나눈 소제목 {len(split)}개 → 조각 {sum(map(len, split))}개, 가장 작은 조각 {min(map(min, split), default=0)}단어")
    print(f"  단어 수: 50 미만 {sum(n < 50 for n in sizes)}, 50-400 {sum(50 <= n <= 400 for n in sizes)}, 400 넘음 {sum(n > 400 for n in sizes)}")
    print(f"  영상·그림 예시를 붙인 청크: {sum(bool(chunk.examples) for chunk in chunks)}개")
    print(f"  모드·메뉴·단축키 상자가 있는 청크: {sum(bool(chunk.reference) for chunk in chunks)}개")
    print(f"  메뉴 경로·버튼 이름이 있는 청크: {sum(bool(chunk.ui_names) for chunk in chunks)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
