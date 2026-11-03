"""Glass-box tests for tools/textbook/render.py."""

import io
import struct

import pytest

from book_helpers import ROOT, samples
from tools.textbook.manifest import Chapter
from tools.textbook.model import Code, Heading, ListBlock, ListItem, Quote, Run, Table
from tools.textbook.render import (
    BodyRenderer,
    TemplateError,
    esc,
    image_size,
    inline,
    load_template,
    safe_href,
    title_html,
)


def test_escaping_stops_markup_in_source_text():
    assert esc('<script>alert("x")</script> & it\'s') == "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; it's"
    assert inline([Run("<b>not bold</b>")]) == "&lt;b&gt;not bold&lt;/b&gt;"


@pytest.mark.parametrize(
    "href, safe",
    [
        ("https://example.org", "https://example.org"),
        ("mailto:a@example.org", "mailto:a@example.org"),
        ("chapter-x.html#y", "chapter-x.html#y"),
        ("javascript:alert(1)", None),
        (" JavaScript:alert(1)", None),
        ("data:text/html,x", None),
        ("", None),
        (None, None),
    ],
)
def test_only_safe_links_survive(href, safe):
    assert safe_href(href) == safe


def test_inline_nests_marks_minimally():
    runs = [Run("a "), Run("b", frozenset({"strong"})), Run("c", frozenset({"strong", "em"})), Run(" d")]
    assert inline(runs) == "a <strong>b<em>c</em></strong> d"


def test_inline_wraps_links_outermost_and_drops_unsafe_ones():
    runs = [Run("go ", href="https://x.org"), Run("now", frozenset({"em"}), href="https://x.org"),
            Run(" bad", href="javascript:x")]
    assert inline(runs) == '<a href="https://x.org">go <em>now</em></a> bad'


def test_inline_closes_everything():
    assert inline([Run("x", frozenset({"sup", "code"}))]) == "<code><sup>x</sup></code>"


def test_image_size_reads_png_and_jpeg_headers():
    assert image_size(samples.png(120, 60), "png") == (120, 60)
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (33, 17)).save(buf, "JPEG")
    assert image_size(buf.getvalue(), "jpg") == (33, 17)
    assert image_size(b"not an image", "png") is None
    assert image_size(b"\xff\xd8" + b"\x00" * 20, "jpg") is None


def test_image_size_skips_jpeg_segments_before_the_frame():
    app0 = b"\xff\xe0" + struct.pack(">H", 6) + b"JFIF"
    sof = b"\xff\xc0" + struct.pack(">HBHH", 11, 8, 40, 30) + b"\x03"
    assert image_size(b"\xff\xd8" + app0 + sof + b"\x00" * 10, "jpg") == (30, 40)


def test_title_html_marks_the_highlight_once():
    assert title_html("Sleep & jet lag", "jet lag") == 'Sleep &amp; <mark class="highlight--draw">jet lag</mark>'
    assert title_html("Sleep", None) == "Sleep"
    assert title_html("Sleep", "nope") == "Sleep"


def test_template_head_is_copied_with_slots(tmp_path):
    tpl = load_template(ROOT / "_template.html")
    assert "{title}" in tpl.head and "{description}" in tpl.head
    assert "<!--" not in tpl.head  # template-only comments are dropped
    assert 'href="assets/css/main.css"' in tpl.head
    assert "data-site-header" in tpl.body_start and "skip-link" in tpl.body_start
    assert "data-site-footer" in tpl.body_end_footer


def test_a_reshaped_template_fails_loudly(tmp_path):
    bad = tmp_path / "_template.html"
    bad.write_text("<html><body>nothing here</body></html>")
    with pytest.raises(TemplateError, match="no longer has the shape"):
        load_template(bad)
    bad.write_text("<head>\n<meta>\n</head>\n<body>\n<a></a><header data-site-header></header>\n"
                   "\n<footer data-site-footer></footer>\n")
    with pytest.raises(TemplateError, match="needs a <title>"):
        load_template(bad)


def test_body_renders_every_block_type():
    chapter = Chapter(id="c", title="C", unit="u", authors=["a"], number=1)
    blocks = [
        Heading(2, [Run("Main")]),
        Heading(2, [Run("Main")]),
        Heading(3, [Run("Sub")]),
        ListBlock(True, [ListItem([Run("one")], [ListBlock(False, [ListItem([Run("inner")])])]),
                         ListItem([Run("two")])], start=4),
        Quote([[Run("first")], [Run("second")]]),
        Code("x < 1 && y"),
        Table([[[Run("only header")]]]),
    ]
    body = BodyRenderer(chapter)
    out = "\n".join(body.blocks(blocks, ""))
    assert out == "\n".join([
        '<h2 id="main-2">Main</h2>',          # "main" is reserved for <main id="main">
        '<h2 id="main-3">Main</h2>',
        '<h3 id="sub">Sub</h3>',
        '<ol start="4">',
        "  <li>one",
        "    <ul>",
        "      <li>inner</li>",
        "    </ul>",
        "  </li>",
        "  <li>two</li>",
        "</ol>",
        "<blockquote>",
        "  <p>first</p>",
        "  <p>second</p>",
        "</blockquote>",
        "<pre><code>x &lt; 1 &amp;&amp; y</code></pre>",
        '<table id="table-1" tabindex="0">',
        "  <thead>",
        '    <tr><th scope="col">only header</th></tr>',
        "  </thead>",
        "</table>",
    ])
    assert body.sections == [("main-2", "Main"), ("main-3", "Main")]


def test_links_over_only_whitespace_become_plain_text():
    runs = [Run("Nature."), Run(" ", href="https://x.org/a"), Run("doi", href="https://x.org/b")]
    assert inline(runs) == 'Nature. <a href="https://x.org/b">doi</a>'
    assert inline([Run("  ", frozenset({"em"}), href="https://x.org")]) == "<em>  </em>"
