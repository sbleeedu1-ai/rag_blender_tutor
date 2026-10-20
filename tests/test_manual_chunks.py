"""자료 준비: 설명서 HTML → 청크(시험 경계 ④: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

설명서 구조(Sphinx가 만든 쪽: article > section > h1-h6)를 흉내 내 직접 쓴 작은 HTML 조각을 넣고,
나온 청크의 경계·경로·앵커·위계 메타데이터·그림 표시를 본다. 설명서 원문은 쓰지 않는다.
"""

from blender_tutor.manual_chunks import chunk_page

BASE = "https://docs.blender.org/manual/en/5.2/"


def page(body: str) -> str:
    """설명서 쪽처럼 옆 목차(sidebar)와 본문(article)을 두른다. 옆 목차 글은 청크에 들어가면 안 된다."""
    return f"""<html><body>
<div class="sidebar-tree"><ul><li><a href="#">Sidebar Link Should Not Appear</a></li></ul></div>
<article role="main" id="furo-main-content">{body}</article>
<footer>Footer Should Not Appear</footer>
</body></html>"""


def headed(id_: str, level: int, title: str, inner: str) -> str:
    """소제목 하나(제목 + ¶ 링크 + 내용)."""
    return (
        f'<section id="{id_}"><h{level}>{title}<a class="headerlink" href="#{id_}" title="Link to this heading">¶</a>'
        f"</h{level}>{inner}</section>"
    )


def words(n: int, word: str = "lorem") -> str:
    return " ".join([word] * n)


def test_소제목_하나가_청크_하나이고_경로_앵커_위계를_붙인다():
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            "<p>The wand tool waves.</p>"
            + headed("usage", 2, "Usage", "<p>Hold the wand.</p>" + headed("tips", 3, "Tips", "<p>Wave slowly.</p>")),
        )
    )

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    assert [(c.anchor, c.headings, c.body) for c in chunks] == [
        ("wand-tool", (), "The wand tool waves."),
        ("usage", ("Usage",), "Hold the wand."),
        ("tips", ("Usage", "Tips"), "Wave slowly."),
    ]
    tips = chunks[2]
    assert tips.url == BASE + "modeling/wands/wand_tool.html#tips"
    assert (tips.field, tips.group, tips.page_title) == ("modeling", "modeling/wands", "Wand Tool")
    assert tips.text == "Wand Tool > Usage > Tips\n\nWave slowly."
    assert chunks[0].text == "Wand Tool\n\nThe wand tool waves."


def figure(src: str, caption: str | None = None, alt: str | None = None) -> str:
    """설명서의 그림 꼴. alt는 따로 주지 않으면 설명서처럼 파일 경로다."""
    cap = (
        f'<figcaption><p><span class="caption-text">{caption}</span>'
        f'<a class="headerlink" href="#id1" title="Link to this image">¶</a></p></figcaption>'
        if caption
        else ""
    )
    return f'<figure class="align-default"><img alt="{alt or src}" src="{src}" />{cap}</figure>'


def test_그림_자리에_캡션을_남기고_경로뿐인_alt는_버리고_주소는_메타데이터에_둔다():
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            "<p>Before.</p>"
            + figure("../../_images/wand_wave.png", caption="Waving the <em>wand</em>.")
            + figure("../../_images/wand_side.png")
            + figure("../../_images/wand_top.png", alt="Wand seen from above")
            + "<p>After.</p>",
        )
    )

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.body == "Before.\n\n[그림: Waving the wand.]\n\n[그림]\n\n[그림: Wand seen from above]\n\nAfter."
    assert chunk.images == (
        BASE + "_images/wand_wave.png",
        BASE + "_images/wand_side.png",
        BASE + "_images/wand_top.png",
    )
    assert chunk.videos == ()


def test_글_속_영상은_그_청크_메타데이터에_영상_주소로_둔다():
    video = '<div class="video"><iframe allowfullscreen="true" src="https://video.blender.org/videos/embed/abc"></iframe></div>'
    html = page(headed("wand-tool", 1, "Wand Tool", "<p>Watch this.</p>" + video))

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.body == "Watch this."
    assert chunk.videos == ("https://video.blender.org/videos/embed/abc",)
