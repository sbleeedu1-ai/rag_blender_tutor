"""자료 준비: 설명서 HTML 묶음을 소제목 단위 청크로 자른다(한 번 돌리는 프로그램, 비용 없음).

규칙은 .scratch/mvp-roundtrip/spec.md의 "자료 준비"와 티켓 06·07의 Answer를 따른다.
"""

import copy
import json
import re
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

BASE_URL = "https://docs.blender.org/manual/en/5.2/"  # 근거 링크는 /en/5.2/<경로>.html#<앵커>로 고정(티켓 02)
MAX_WORDS = 400  # 소제목 글이 이보다 길면 옵션 경계(없으면 문단 끝)에서 나눈다(티켓 06)

_HEADING = re.compile(r"^h[1-6]$")
# 앞뒤로 빈 줄을 두는 태그(나머지는 글 속에 이어 붙는다: em, kbd, a, span 등)
_BLOCK = {"p", "div", "dl", "dt", "dd", "ul", "ol", "li", "table", "tr", "pre", "figure", "blockquote", "caption"}
_PATH_ALT = re.compile(r"[\\/]|\.(png|jpe?g|gif|webp|svg)$", re.IGNORECASE)  # 파일 경로뿐인 alt
# 그림·영상 자리에 넣는 보이지 않는 표식. 글을 나눈 뒤 어느 조각에 어떤 주소가 들었는지 찾는 데 쓰고 지운다
_MEDIA_MARK = re.compile("(\\d+)")
_SHORTCUT = re.compile("(\\s*[-+]\\s*)*")  # 옵션 이름 속 단축키 자리(키 하나 = )
# 검색에서 빼는 폴더: 기여자용 쪽(티켓 06), Sphinx가 만든 원문·그림·꾸밈 파일
_SKIP_FOLDERS = {"contribute", "_sources", "_images", "_static"}
_SKIP_PAGES = {"genindex", "search", "404"}  # 색인·검색·없는 쪽 안내(설명 글이 아님)


@dataclass(frozen=True)
class Example:
    """영상만·그림만 있는 소제목. 청크로 만들지 않고 같은 쪽 바로 앞 청크에 붙인다(티켓 07)."""

    kind: str  # "영상" 또는 "그림"
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
    options: tuple[str, ...] = ()  # 이 청크에 든 옵션 이름(정의 목록의 항목 이름, 단축키 글자는 뗌)
    images: tuple[str, ...] = ()  # 글 속 그림 주소
    videos: tuple[str, ...] = ()  # 글 속 영상 주소
    examples: tuple[Example, ...] = ()  # 뒤따르는 영상만·그림만 있는 소제목
    reference: tuple[tuple[str, str], ...] = ()  # "모드·메뉴·단축키" 상자(예: ("Mode", "Edit Mode"))

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.page_path}.html#{self.anchor}"

    @property
    def text(self) -> str:
        """검색·답변에 쓰는 글: 맨 앞에 '쪽 제목 > 소제목' 경로를 붙인다."""
        return " > ".join((self.page_title, *self.headings)) + "\n\n" + self.body


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
    kind: str  # "그림" 또는 "영상"
    urls: tuple[str, ...]


@dataclass
class _Unit:
    """나눌 때 쪼개지 않는 글 한 덩이: 문단 하나 또는 옵션 하나."""

    text: str
    option: str | None = None
    media: list[int] = field(default_factory=list)  # 이 덩이에 든 그림·영상 번호
    reference: tuple[tuple[str, str], ...] = ()  # "모드·메뉴·단축키" 상자면 그 칸들

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
        page.path,
        section["id"],
        page.field,
        page.group,
        page.title,
        headings,
        "\n\n".join(unit.text for unit in units),
        tuple(unit.option for unit in units if unit.option),
        _urls(units, media, "그림"),
        _urls(units, media, "영상"),
        examples,
        next((unit.reference for unit in units if unit.reference), ()),
    )


def _example(section: Tag, headings: tuple[str, ...], page: _Page, media: list[_Media]) -> Example:
    kind = "영상" if any(item.kind == "영상" for item in media) else "그림"
    title = headings[-1] if headings else page.title
    return Example(kind, title, f"{page.url}#{section['id']}", tuple(url for item in media for url in item.urls))


def _units(nodes) -> list[_Unit]:
    """소제목 내용을 덩이로 나눈다. 옵션 목록(값 목록이 아닌 정의 목록)은 항목 하나가 한 덩이."""
    units: list[_Unit] = []
    for node in nodes:
        if isinstance(node, Tag) and "refbox" in node.get("class", []):
            units.append(_reference_unit(node))
        elif isinstance(node, Tag) and node.name == "dl" and "field-list" not in node.get("class", []):
            for dt in node.find_all("dt", recursive=False):
                parts = [dt, *_following_dds(dt)]
                units += _blocks("\n\n".join(_render(part) for part in parts), _option_name(dt))
        else:
            units += _blocks(_render(node) if isinstance(node, Tag) else _string(node))
    # 글 없이 표식만 남은 덩이(영상 자리 등)는 앞 덩이에 주소만 넘긴다
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


def _blocks(raw: str, option: str | None = None) -> list[_Unit]:
    """빈 줄로 나뉜 글을 덩이로. 옵션 하나는 문단이 여럿이어도 한 덩이로 둔다."""
    blocks = [" ".join(block.split()) for block in re.split(r"\n\s*\n", raw)]
    blocks = [block for block in blocks if block]
    if option is not None:
        blocks = ["\n\n".join(blocks)]
    units = []
    for block in blocks:
        media = [int(n) for n in _MEDIA_MARK.findall(block)]
        units.append(_Unit(_MEDIA_MARK.sub("", block).strip(), option, media))
    return units


def _pack(units: list[_Unit]) -> list[list[_Unit]]:
    """덩이를 앞에서부터 MAX_WORDS까지 채워 청크로 묶는다. 한 덩이가 넘치면 그 덩이만 따로 둔다."""
    pieces: list[list[_Unit]] = []
    current: list[_Unit] = []
    count = 0
    for unit in units:
        if current and count + unit.words > MAX_WORDS:
            pieces.append(current)
            current, count = [], 0
        current.append(unit)
        count += unit.words
    if current:
        pieces.append(current)
    return pieces


def _reference_unit(box: Tag) -> _Unit:
    """"모드·메뉴·단축키" 상자를 'Mode: Edit Mode' 꼴 줄로 쓴 한 덩이로."""
    items = []
    for dt in box.find_all("dt"):
        key = " ".join(_render(dt).split()).rstrip(":").strip()
        value = " ".join("".join(_render(dd) for dd in _following_dds(dt)).split())
        items.append((key, value))
    title = box.find(class_="admonition-title")
    lines = ([" ".join(_render(title).split())] if title else []) + [f"{key}: {value}" for key, value in items]
    raw = "\n\n".join(lines)
    return _Unit(_MEDIA_MARK.sub("", raw), media=[int(n) for n in _MEDIA_MARK.findall(raw)], reference=tuple(items))


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
        kbd.replace_with(NavigableString(""))
    text = _SHORTCUT.sub("", _render(name))
    return " ".join(text.split())


def _urls(units: list[_Unit], media: list[_Media], kind: str) -> tuple[str, ...]:
    return tuple(url for unit in units for n in unit.media if media[n].kind == kind for url in media[n].urls)


def _render(node: Tag) -> str:
    """태그 안 글. 블록 태그 앞뒤는 빈 줄, 표의 칸은 ' | '로 잇는다."""
    if "headerlink" in node.get("class", []) or "toctree-wrapper" in node.get("class", []):
        return ""
    if node.name == "tr":
        cells = node.find_all(["td", "th"], recursive=False)
        return "\n\n" + " | ".join(" ".join(_render(cell).split()) for cell in cells) + "\n\n"
    inner = "".join(_render(child) if isinstance(child, Tag) else _string(child) for child in node.children)
    if node.name in _BLOCK or _HEADING.match(node.name):
        return f"\n\n{inner}\n\n"
    return inner


def _string(node) -> str:
    return "" if isinstance(node, Comment) else str(node)


def _mark_media(section: Tag, page_url: str) -> list[_Media]:
    """소제목 내용(아래 소제목 빼고)의 그림 자리를 [그림: 캡션]/[그림] 글로 바꾸고 그림·영상 자리에 표식을 넣는다.

    표식 번호 순서의 주소 목록을 돌려준다.
    """
    media: list[_Media] = []

    def mark(holder: Tag, item: _Media, label: str) -> None:
        holder.replace_with(NavigableString(f"\n\n{label}{len(media)}\n\n"))
        media.append(item)

    # 단계마다 내용을 새로 찾는다: 앞 단계에서 떼어 낸 그림 상자 속 img를 다시 잡지 않도록
    for frame in _find(section, "iframe"):
        mark(frame, _Media("영상", (frame["src"],)), "")
    for holder in _find(section, "figure"):
        urls = tuple(urljoin(page_url, img["src"]) for img in holder.find_all("img"))
        mark(holder, _Media("그림", urls), _figure_label(holder.find("figcaption"), holder.find("img")))
    for img in _find(section, "img"):
        mark(img, _Media("그림", (urljoin(page_url, img["src"]),)), _figure_label(None, img))
    return media


def _content(section: Tag) -> list:
    """소제목의 내용: 제목과 아래 소제목을 뺀 바로 아래 것들."""
    return [child for child in section.children if not _is_section(child) and not _is_heading(child)]


def _find(section: Tag, name: str) -> list[Tag]:
    """소제목 내용 안의 name 태그(아래 소제목 속 것은 빼고)."""
    tags = [node for node in _content(section) if isinstance(node, Tag)]
    return [found for tag in tags for found in ([tag] if tag.name == name else []) + tag.find_all(name)]


def _figure_label(caption: Tag | None, img: Tag | None) -> str:
    """캡션이 있으면 [그림: 캡션], 캡션이 없고 alt가 설명 글이면 [그림: alt], 둘 다 없으면 [그림]."""
    if caption is not None:
        label = " ".join(_render(caption).split())
    else:
        alt = (img.get("alt") or "").strip() if img is not None else ""
        label = "" if _PATH_ALT.search(alt) else alt
    return f"[그림: {label}]" if label else "[그림]"


def _is_section(node) -> bool:
    return isinstance(node, Tag) and node.name == "section"


def _is_heading(node) -> bool:
    return isinstance(node, Tag) and bool(_HEADING.match(node.name))


def _title(section: Tag) -> str:
    heading = section.find(_HEADING)
    return " ".join(_render(heading).split())


def main(argv: list[str]) -> int:
    """사용법: python -m blender_tutor.manual_chunks <설명서 HTML 폴더> <청크 JSONL 파일>

    청크를 한 줄에 하나씩 JSON으로 쓰고 개수를 알린다. 결과는 data/에 두고 커밋하지 않는다.
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
    print(f"청크 {len(chunks)}개 (쪽 {len({chunk.page_path for chunk in chunks})}개) → {out}")
    print(f"  나눈 소제목에서 나온 청크: {len(chunks) - len({(c.page_path, c.anchor) for c in chunks})}개 더")
    print(f"  단어 수: 50 미만 {sum(n < 50 for n in sizes)}, 50-400 {sum(50 <= n <= 400 for n in sizes)}, 400 넘음 {sum(n > 400 for n in sizes)}")
    print(f"  영상·그림 예시를 붙인 청크: {sum(bool(chunk.examples) for chunk in chunks)}개")
    print(f"  모드·메뉴·단축키 상자가 있는 청크: {sum(bool(chunk.reference) for chunk in chunks)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
