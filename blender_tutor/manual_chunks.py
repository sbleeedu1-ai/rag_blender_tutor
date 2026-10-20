"""자료 준비: 설명서 HTML 묶음을 소제목 단위 청크로 자른다(한 번 돌리는 프로그램, 비용 없음).

규칙은 .scratch/mvp-roundtrip/spec.md의 "자료 준비"와 티켓 06·07의 Answer를 따른다.
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

BASE_URL = "https://docs.blender.org/manual/en/5.2/"  # 근거 링크는 /en/5.2/<경로>.html#<앵커>로 고정(티켓 02)

_HEADING = re.compile(r"^h[1-6]$")


@dataclass(frozen=True)
class Chunk:
    """청크 하나. 위계는 분야 > 묶음 > 쪽 > 소제목(여러 겹)."""

    page_path: str  # 쪽 경로(.html 뺀 것, 예: modeling/modifiers/generate/bevel)
    anchor: str  # 소제목 앵커
    field: str  # 분야(경로 첫 폴더, 예: modeling)
    group: str  # 묶음(폴더 경로, 예: modeling/modifiers/generate)
    page_title: str  # 쪽 제목
    headings: tuple[str, ...]  # 쪽 제목 아래 소제목 경로. 쪽 첫머리 글이면 빈 묶음
    body: str  # 본문 글
    images: tuple[str, ...] = ()  # 글 속 그림 주소
    videos: tuple[str, ...] = ()  # 글 속 영상 주소

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.page_path}.html#{self.anchor}"

    @property
    def text(self) -> str:
        """검색·답변에 쓰는 글: 맨 앞에 '쪽 제목 > 소제목' 경로를 붙인다."""
        return " > ".join((self.page_title, *self.headings)) + "\n\n" + self.body


def chunk_page(html: str, page_path: str) -> list[Chunk]:
    """설명서 쪽 하나(HTML 전체)를 청크 목록으로 자른다."""
    article = BeautifulSoup(html, "html.parser").find("article")
    if article is None:
        return []
    top = article.find("section")
    if top is None:
        return []
    folders = page_path.split("/")[:-1]
    page = _Page(page_path, folders[0] if folders else "", "/".join(folders), _title(top))
    chunks: list[Chunk] = []
    _walk(top, (), page, chunks)
    return chunks


@dataclass(frozen=True)
class _Page:
    path: str
    field: str
    group: str
    title: str


def _walk(section: Tag, headings: tuple[str, ...], page: _Page, out: list[Chunk]) -> None:
    content = [child for child in section.children if not _is_section(child) and not _is_heading(child)]
    page_url = f"{BASE_URL}{page.path}.html"
    images, videos = _mark_media(content, page_url)
    # 그림을 글로 바꿔 끼웠으니 내용을 다시 모은다
    content = [child for child in section.children if not _is_section(child) and not _is_heading(child)]
    body = _text(content)
    if body:
        out.append(
            Chunk(page.path, section["id"], page.field, page.group, page.title, headings, body, images, videos)
        )
    for child in section.children:
        if _is_section(child):
            _walk(child, (*headings, _title(child)), page, out)


def _is_section(node) -> bool:
    return isinstance(node, Tag) and node.name == "section"


def _is_heading(node) -> bool:
    return isinstance(node, Tag) and bool(_HEADING.match(node.name))


def _title(section: Tag) -> str:
    heading = section.find(_HEADING)
    for link in heading.find_all("a", class_="headerlink"):
        link.decompose()
    return heading.get_text(" ", strip=True)


def _text(nodes) -> str:
    """블록 사이는 빈 줄, 블록 안 공백은 하나로."""
    raw = "\n\n".join(node.get_text(" ") if isinstance(node, Tag) else str(node) for node in nodes)
    blocks = (" ".join(block.split()) for block in re.split(r"\n\s*\n", raw))
    return "\n\n".join(block for block in blocks if block)


_PATH_ALT = re.compile(r"[\\/]|\.(png|jpe?g|gif|webp|svg)$", re.IGNORECASE)


def _mark_media(nodes, page_url: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """그림 자리를 [그림: 캡션]/[그림] 글로 바꾸고, 그림·영상 주소를 모아 돌려준다."""
    images: list[str] = []
    videos: list[str] = []
    for node in nodes:
        if not isinstance(node, Tag):
            continue
        for frame in node.find_all("iframe") + ([node] if node.name == "iframe" else []):
            videos.append(frame["src"])
            frame.decompose()
        for img in node.find_all("img") + ([node] if node.name == "img" else []):
            images.append(urljoin(page_url, img["src"]))
            holder = img.find_parent("figure") or img
            caption = holder.find("figcaption") if holder.name == "figure" else None
            if caption is not None:
                for link in caption.find_all("a", class_="headerlink"):
                    link.decompose()
                label = " ".join(caption.get_text().split())
            else:
                alt = (img.get("alt") or "").strip()
                label = "" if _PATH_ALT.search(alt) else alt
            holder.replace_with(NavigableString(f"\n\n[그림: {label}]\n\n" if label else "\n\n[그림]\n\n"))
    return tuple(images), tuple(videos)
