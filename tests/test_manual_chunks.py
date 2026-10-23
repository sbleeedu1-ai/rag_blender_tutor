"""자료 준비: 설명서 HTML → 청크(시험 경계 ④: .scratch/mvp-roundtrip/spec.md의 Testing Decisions 참고).

설명서 구조(Sphinx가 만든 쪽: article > section > h1-h6)를 흉내 내 직접 쓴 작은 HTML 조각을 넣고,
나온 청크의 경계·경로·앵커·위계 메타데이터·그림 표시를 본다. 설명서 원문은 쓰지 않는다.
"""

from pathlib import Path

from blender_tutor import manual_chunks
from blender_tutor.manual_chunks import Example, chunk_manual, chunk_page

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


def option(name: str, desc: str) -> str:
    return f"<dt>{name}</dt><dd><p>{desc}</p></dd>"


def test_글자_꾸밈_앞뒤에_빈칸을_넣지_않고_표는_칸을_세로줄로_나눈다():
    table = '<table class="docutils"><tbody><tr><td><p>Left</p></td><td><p>Right</p></td></tr></tbody></table>'
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            "<p>Press <kbd>Shift</kbd>-<kbd>W</kbd> to use the <em>Wand</em>.</p>"
            '<p><span class="menuselection">Object ‣ Wand</span>.</p>' + table,
        )
    )

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.body == "Press Shift-W to use the Wand.\n\nObject ‣ Wand.\n\nLeft | Right"


def test_400단어가_넘는_소제목은_옵션_경계에서_나누고_같은_경로_앵커를_쓴다():
    options = (
        "<dl>"
        + option("Alpha <kbd>Shift</kbd>-<kbd>A</kbd>", words(180, "a"))
        + option("Beta", words(180, "b"))
        + option("Gamma", words(180, "c"))
        + "</dl>"
    )
    html = page(headed("wand-tool", 1, "Wand Tool", headed("options", 2, "Options", options)))

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    # 182 + 181 + 181단어: [182 | 362]가 [363 | 181]보다 고르다
    assert [(c.anchor, c.headings, c.options) for c in chunks] == [
        ("options", ("Options",), ("Alpha",)),
        ("options", ("Options",), ("Beta", "Gamma")),
    ]
    assert chunks[0].body == f"Alpha Shift-A\n\n{words(180, 'a')}"
    assert chunks[1].text == f"Wand Tool > Options\n\nBeta\n\n{words(180, 'b')}\n\nGamma\n\n{words(180, 'c')}"


def test_나눌_때는_고르게_나눠_아주_작은_꼬리_조각을_만들지_않는다():
    paragraphs = f"<p>{words(200, 'a')}</p><p>{words(195, 'b')}</p><p>{words(15, 'c')}</p>"
    html = page(headed("wand-tool", 1, "Wand Tool", paragraphs))

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    # 앞에서 꽉 채우면 [395 | 15]가 되지만 고르게 나누면 [200 | 210]
    assert [c.body for c in chunks] == [words(200, "a"), f"{words(195, 'b')}\n\n{words(15, 'c')}"]


def test_옵션이_없는_긴_소제목은_문단_끝에서_나눈다():
    paragraphs = "".join(f"<p>{words(180, w)}</p>" for w in "abc")
    html = page(headed("wand-tool", 1, "Wand Tool", paragraphs))

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    assert [c.body for c in chunks] == [f"{words(180, 'a')}\n\n{words(180, 'b')}", words(180, "c")]
    assert all(c.anchor == "wand-tool" and c.options == () for c in chunks)


def test_값_목록은_옵션으로_세지_않는다():
    values = '<dl class="field-list simple"><dt>Fast<span class="colon">:</span></dt><dd><p>Quick.</p></dd></dl>'
    html = page(headed("wand-tool", 1, "Wand Tool", "<dl>" + option("Speed", "How fast." + values) + "</dl>"))

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.options == ("Speed",)


TOCTREE = '<div class="toctree-wrapper compound"><ul><li class="toctree-l1"><a href="a.html">Child Page</a></li></ul></div>'


def test_아래_소제목만_묶는_제목뿐인_소제목은_경로에만_남는다():
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            '<span id="index-0"></span>' + headed("tools", 2, "Tools", headed("spark", 3, "Spark", "<p>Sparks fly.</p>")),
        )
    )

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert (chunk.anchor, chunk.text) == ("spark", "Wand Tool > Tools > Spark\n\nSparks fly.")


def test_목차만_있는_소제목과_쪽은_버린다():
    toc_page = page(headed("wands", 1, "Wands", TOCTREE))
    toc_section = page(headed("wand-tool", 1, "Wand Tool", "<p>Intro.</p>" + headed("pages", 2, "Pages", TOCTREE)))

    assert chunk_page(toc_page, "modeling/wands/index") == []
    assert [c.anchor for c in chunk_page(toc_section, "modeling/wands/wand_tool")] == ["wand-tool"]


def test_영상만_그림만_있는_소제목은_같은_쪽_바로_앞_청크에_예시로_붙인다():
    video = '<div class="video"><iframe src="https://video.blender.org/videos/embed/abc"></iframe></div>'
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            "<p>Intro.</p>"
            + headed("usage", 2, "Usage", "<p>Hold it.</p>")
            + headed("demo", 2, "Demo", video)
            + headed("gallery", 2, "Gallery", figure("../../_images/wand_gallery.png"))
            + headed("result", 2, "Result", figure("../../_images/wand_result.png", caption="Many wands."))
            + headed("tips", 2, "Tips", "<p>Wave slowly.</p>"),
        )
    )

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    # 캡션은 찾을 수 있는 글이라 캡션 있는 그림만 있는 소제목은 청크로 둔다(티켓 06의 '그림만'은 0단어 소제목)
    assert [(c.anchor, c.body) for c in chunks] == [
        ("wand-tool", "Intro."),
        ("usage", "Hold it."),
        ("result", "[그림: Many wands.]"),
        ("tips", "Wave slowly."),
    ]
    assert chunks[1].examples == (
        Example("영상", "Demo", BASE + "modeling/wands/wand_tool.html#demo", ("https://video.blender.org/videos/embed/abc",)),
        Example("그림", "Gallery", BASE + "modeling/wands/wand_tool.html#gallery", (BASE + "_images/wand_gallery.png",)),
    )
    assert [c.examples for c in chunks if c.anchor != "usage"] == [(), (), ()]


def test_모드_메뉴_단축키_상자는_본문과_메타데이터에_둔다():
    refbox = (
        '<div class="refbox admonition"><p class="admonition-title">Reference</p><dl class="field-list simple">'
        '<dt class="field-odd">Mode<span class="colon">:</span></dt><dd class="field-odd"><p>Edit Mode</p></dd>'
        '<dt class="field-even">Menu<span class="colon">:</span></dt>'
        '<dd class="field-even"><p><span class="menuselection">Wand ‣ Wave</span></p></dd>'
        '<dt class="field-odd">Shortcut<span class="colon">:</span></dt>'
        '<dd class="field-odd"><p><kbd>Ctrl</kbd>-<kbd>W</kbd></p></dd></dl></div>'
    )
    html = page(headed("wand-tool", 1, "Wand Tool", refbox + "<p>The wand tool waves.</p>"))

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.reference == (("Mode", "Edit Mode"), ("Menu", "Wand ‣ Wave"), ("Shortcut", "Ctrl-W"))
    assert chunk.body == "Reference\n\nMode: Edit Mode\n\nMenu: Wand ‣ Wave\n\nShortcut: Ctrl-W\n\nThe wand tool waves."


def test_묶음_전체를_돌리되_기여자용_contribute_쪽과_색인_쪽은_뺀다(tmp_path):
    pages = [("modeling/wands/wand_tool.html", "Wand Tool"), ("contribute/manual/guide.html", "Guide"), ("genindex.html", "Index")]
    for path, title in pages:
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(page(headed("top", 1, title, "<p>Body.</p>")), encoding="utf-8")

    chunks = chunk_manual(tmp_path)

    assert [(c.page_path, c.page_title) for c in chunks] == [("modeling/wands/wand_tool", "Wand Tool")]


def test_옵션_하나가_400단어를_넘으면_그_옵션_안의_문단_끝에서_나누고_뒤_조각에_옵션_이름을_붙인다():
    big = "<dl><dt>Operation</dt><dd>" + "".join(f"<p>{words(180, w)}</p>" for w in "abc") + "</dd></dl>"
    html = page(headed("wand-tool", 1, "Wand Tool", big))

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    assert [(c.text, c.options) for c in chunks] == [
        (f"Wand Tool\n\nOperation\n\n{words(180, 'a')}", ("Operation",)),
        (f"Wand Tool > Operation\n\n{words(180, 'b')}\n\n{words(180, 'c')}", ("Operation",)),
    ]


def value(name: str, desc: str) -> str:
    """값 목록(field-list)의 한 줄: 값 이름 + 설명."""
    return f'<dt>{name}<span class="colon">:</span></dt><dd><p>{desc}</p></dd>'


def test_긴_옵션은_범주와_값_경계에서_나누고_값_이름과_설명은_떼지_않는다():
    # Math 노드의 Operation처럼: 옵션 > 범주(Functions, Trigonometric) > 값 이름 + 설명
    functions = "".join(value(name, words(50, "f")) for name in ("Add", "Subtract", "Multiply"))
    trig_names = ("Sine", "Cosine", "Tangent", "Arcsine", "Arccosine", "Arctangent", "Hsine", "Hcosine", "Htangent")
    trigonometric = "".join(value(name, words(50, "t")) for name in trig_names)
    operation = (
        "<dl><dt>Operation</dt><dd><p>The operator to use:</p><dl class='simple'>"
        f'<dt>Functions</dt><dd><dl class="field-list simple">{functions}</dl></dd>'
        f'<dt>Trigonometric</dt><dd><dl class="field-list simple">{trigonometric}</dl></dd>'
        "</dl></dd></dl>"
    )
    html = page(headed("wand-tool", 1, "Wand Tool", headed("properties", 2, "Properties", operation)))

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    assert len(chunks) == 2
    assert chunks[0].text.startswith("Wand Tool > Properties\n\nOperation\n\nThe operator to use:\n\nFunctions\n\nAdd:")
    assert chunks[1].text.startswith(f"Wand Tool > Properties > Operation > Trigonometric\n\nArcsine:\n\n{words(50, 't')}")
    assert [c.options for c in chunks] == [("Operation",), ("Operation",)]


def test_한_청크에_든_모드_메뉴_단축키_상자는_모두_메타데이터에_남는다():
    def refbox(mode: str) -> str:
        return (
            '<div class="refbox admonition"><p class="admonition-title">Reference</p><dl class="field-list simple">'
            f"<dt>Mode<span>:</span></dt><dd><p>{mode}</p></dd></dl></div>"
        )

    html = page(headed("wand-tool", 1, "Wand Tool", refbox("Edit Mode") + "<p>Two tools.</p>" + refbox("Object Mode")))

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    assert chunk.reference == (("Mode", "Edit Mode"), ("Mode", "Object Mode"))


def menu(path: str) -> str:
    return f'<span class="menuselection">{path}</span>'


def label(name: str) -> str:
    return f'<span class="guilabel">{name}</span>'


def test_메뉴_경로와_버튼_이름은_글은_그대로_두고_화면_이름_메타데이터에_차례로_모은다():
    refbox = (
        '<div class="refbox admonition"><p class="admonition-title">Reference</p><dl class="field-list simple">'
        f'<dt>Menu<span class="colon">:</span></dt><dd><p>{menu("Wand ‣ Wave")}</p></dd></dl></div>'
    )
    body = (
        refbox
        + f"<p>Open {menu('Add ‣ Wand')} in {label('Edit Mode')}, then {menu('Wand ‣ Wave')} again.</p>"
        + f"<dl><dt>Speed {label('Cycles Only')}</dt><dd><p>How fast.</p></dd></dl>"
    )
    html = page(headed("wand-tool", 1, f"Wand {label('Tool')}", body))

    [chunk] = chunk_page(html, "modeling/wands/wand_tool")

    # 같은 이름은 한 번만, 처음 나온 차례로
    assert chunk.ui_names == ("Wand ‣ Wave", "Add ‣ Wand", "Edit Mode", "Cycles Only")
    assert chunk.body == (
        "Reference\n\nMenu: Wand ‣ Wave\n\nOpen Add ‣ Wand in Edit Mode, then Wand ‣ Wave again.\n\n"
        "Speed Cycles Only\n\nHow fast."
    )
    assert chunk.reference == (("Menu", "Wand ‣ Wave"),)
    assert chunk.options == ("Speed Cycles Only",)
    assert chunk.page_title == "Wand Tool"


def test_긴_소제목을_나누면_화면_이름은_그_이름이_든_조각에만_둔다():
    html = page(
        headed(
            "wand-tool",
            1,
            "Wand Tool",
            f"<p>{words(300, 'a')} {menu('Add ‣ Wand')}</p><p>{words(300, 'b')} {label('Wave')}</p>",
        )
    )

    chunks = chunk_page(html, "modeling/wands/wand_tool")

    assert [c.ui_names for c in chunks] == [("Add ‣ Wand",), ("Wave",)]


def test_코드_파일에_보이지_않는_표식_글자가_그대로_들어가지_않는다():
    # 표식 글자는 ""처럼 번호로 적는다. 글자 그대로 넣으면 화면에 안 보여 편집 중에 지워지기 쉽다
    source = Path(manual_chunks.__file__).read_text(encoding="utf-8")

    assert [ch for ch in source if 0xE000 <= ord(ch) <= 0xF8FF] == []


def test_청크_파일에_쓰고_다시_읽으면_같은_청크가_나온다(tmp_path):
    # 칸을 모두 채운 청크(지어낸 값)와 기본값만 둔 청크
    full = manual_chunks.Chunk(
        "modeling/modifiers/generate/bevel", "options", "modeling", "modeling/modifiers/generate",
        "Bevel Modifier", ("Options", "Width"), "Width sets the size.",
        option_path=("Width Type",), options=("Width", "Segments"),
        images=("https://example.org/a.png",), videos=("https://example.org/a.mp4",),
        examples=(Example(manual_chunks.MediaKind.VIDEO, "Example", "https://example.org/x.html#example", ("https://example.org/b.mp4",)),),
        reference=(("Mode", "Edit Mode"), ("Menu", "Edge ‣ Bevel")), ui_names=("Edge ‣ Bevel",),
    )
    bare = manual_chunks.Chunk("files/blend/save", "save", "files", "files/blend", "Saving", (), "Save writes the file.")
    path = tmp_path / "chunks.jsonl"
    manual_chunks.save_chunks([full, bare], path)
    assert manual_chunks.load_chunks(path) == [full, bare]
