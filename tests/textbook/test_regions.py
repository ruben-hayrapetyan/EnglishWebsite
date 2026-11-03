"""Book-driven regions in hand-written pages (tools/textbook/regions.py).

The add-on pages (study hub, author pages, team page) must follow the book,
never a particular source file: they read textbook.json and the converted
chapters' headings, whatever format those chapters came from.
"""

import json

import pytest

from book_helpers import book_manifest, sample_chapters, write_manifest
from tools.textbook.build import build, outline_of, stale, write
from tools.textbook.manifest import Chapter, Manifest, OutlineNode, Unit
from tools.textbook.model import Document, Heading, Paragraph, Run
from tools.textbook.regions import Book, RegionError, fill, has_regions, outline_list


def tiny_book(tmp_path, **chapter) -> Book:
    ch = Chapter(id="one", title="One & only", unit="u", authors=["ada", "ben"], number=1,
                 outline=[OutlineNode("Intro"), OutlineNode("Deep", [OutlineNode("Deeper", [OutlineNode("Deepest")])])])
    for key, value in chapter.items():
        setattr(ch, key, value)
    manifest = Manifest(tmp_path / "t.json", "T", None, "L", "D", [Unit("u", "Unit U")],
                        {"ada": "Ada", "ben": "Ben <B>"}, [ch])
    return Book(manifest, tmp_path)


# ---- Glass box -----------------------------------------------------------------


def test_inline_region_is_replaced_in_place(tmp_path):
    text = "<p><!-- textbook:count chapters -->99<!-- /textbook --> chapters</p>"
    assert fill(text, tiny_book(tmp_path)) == "<p><!-- textbook:count chapters -->1<!-- /textbook --> chapters</p>"


def test_block_region_is_indented_like_its_marker_and_stable(tmp_path):
    text = "<div>\n    <!-- textbook:author-chapters ada -->\n    stale\n    <!-- /textbook -->\n</div>\n"
    once = fill(text, tiny_book(tmp_path))
    assert fill(once, tiny_book(tmp_path)) == once  # filling again changes nothing
    lines = once.splitlines()
    assert lines[1] == "    <!-- textbook:author-chapters ada -->"
    assert lines[2] == '    <article class="card author-chapter">'
    assert lines[-2] == "    <!-- /textbook -->"
    assert "stale" not in once


def test_author_chapters_escape_and_link_only_existing_pages(tmp_path):
    (tmp_path / "author-ben.html").write_text("x")
    out = fill("<!-- textbook:author-chapters ada -->\n<!-- /textbook -->", tiny_book(tmp_path))
    assert '<h3 class="card__title">One &amp; only</h3>' in out
    assert 'Coauthors: <a href="author-ben.html">Ben &lt;B&gt;</a>' in out
    assert "Textbook link to come." in out


def test_author_chapters_link_converted_chapters_and_use_their_headings(tmp_path):
    book = tiny_book(tmp_path)
    book.available = {"one"}
    book.outlines = {"one": [OutlineNode("Real heading")]}
    out = fill("<!-- textbook:author-chapters ada -->\n<!-- /textbook -->", book)
    assert '<a href="chapter-one.html">Read the chapter</a>' in out
    assert "Real heading" in out and "Intro" not in out


def test_outlines_nest_to_any_depth():
    nodes = [OutlineNode("A", [OutlineNode("B", [OutlineNode("C")])])]
    assert outline_list(nodes, "") == [
        "<ul>", "  <li>A", "    <ul>", "      <li>B", "        <ul>", "          <li>C</li>",
        "        </ul>", "      </li>", "    </ul>", "  </li>", "</ul>"]


@pytest.mark.parametrize(
    "text, message",
    [
        ("<!-- textbook:nonsense -->x<!-- /textbook -->", 'unknown region "textbook:nonsense"'),
        ("<!-- textbook:count pages -->x<!-- /textbook -->", 'needs one of authors, chapters, units'),
        ("<!-- textbook:study-cards nope -->\n<!-- /textbook -->", 'unit "nope" is not in textbook.json'),
        ("<!-- textbook:author-chapters zed -->\n<!-- /textbook -->", 'author "zed" is not in textbook.json'),
        ("<p><!-- textbook:author-chapters ada --><!-- /textbook --></p>", "needs its own line"),
    ],
)
def test_region_mistakes_are_reported(tmp_path, text, message):
    with pytest.raises(RegionError, match=message):
        fill(text, tiny_book(tmp_path))


def test_has_regions():
    assert has_regions("a <!-- textbook:count units -->4<!-- /textbook --> b")
    assert not has_regions("<!-- a normal comment -->")


def test_outline_of_builds_a_tree_from_headings():
    doc = Document([Heading(2, [Run("A")]), Paragraph([Run("text")]), Heading(3, [Run("A1")]),
                    Heading(4, [Run("A1a")]), Heading(2, [Run("B")])], "s")
    assert outline_of(doc) == [OutlineNode("A", [OutlineNode("A1", [OutlineNode("A1a")])]), OutlineNode("B")]


# ---- Black box: a sample site with add-on pages ---------------------------------

AUTHOR_PAGE = """<!doctype html>
<html lang="en"><body>
  <p>Hand-written introduction that must survive every build.</p>
  <div class="grid">
    <!-- textbook:author-chapters ada -->
    <!-- /textbook -->
  </div>
  <p><!-- textbook:count chapters -->0<!-- /textbook --> chapters</p>
</body></html>
"""

HUB_PAGE = """<!doctype html>
<html lang="en"><body>
  <div class="grid">
    <!-- textbook:study-cards first -->
    <!-- /textbook -->
  </div>
</body></html>
"""


@pytest.fixture
def addon_site(site):
    chapters = sample_chapters(site)
    chapters[3]["outline"] = ["Planned section", {"section": "Planned part", "subsections": ["Planned detail"]}]
    chapters[3]["authors"] = ["ada"]
    write_manifest(site, book_manifest(chapters))
    (site / "author-ada.html").write_text(AUTHOR_PAGE)
    (site / "study.html").write_text(HUB_PAGE)
    (site / "study-from-pdf.html").write_text(
        '<li class="deck__slide"></li><li class="deck__slide is-current"></li>' + '<li class="quiz__item"></li>' * 3)
    write(site, build(site))
    return site


def author_page(site):
    return (site / "author-ada.html").read_text()


def test_author_page_follows_the_converted_chapters(addon_site):
    page = author_page(addon_site)
    assert "Hand-written introduction that must survive every build." in page
    assert '<a href="chapter-from-pdf.html">Read the chapter</a>' in page
    for section in ("Measuring a period", "Figures and tables", "Summary"):  # the PDF's real headings
        assert f"<li>{section}</li>" in page
    assert "<li>Planned detail</li>" in page  # chapter with no source yet: outline from textbook.json
    assert "<!-- textbook:count chapters -->4<!-- /textbook --> chapters" in page


def test_study_hub_marks_kits_ready_and_counts_them(addon_site):
    hub = (addon_site / "study.html").read_text()
    assert '<a href="study-from-pdf.html">Sample rhythms</a>' in hub
    assert '<span class="tag">2 slides</span><span class="tag">3 questions</span>' in hub
    assert hub.count("Not ready yet") == 1  # from-word, the other chapter in the first unit


def test_add_on_pages_do_not_depend_on_the_source_format(addon_site):
    """Swap a chapter's PDF for the same chapter as Markdown: no add-on page changes."""
    before = author_page(addon_site), (addon_site / "study.html").read_text()
    data = json.loads((addon_site / "textbook/textbook.json").read_text())
    data["chapters"][0]["source"] = {"file": "sources/from-markdown.md", "heading": "Sample rhythms"}
    write_manifest(addon_site, data)
    write(addon_site, build(addon_site))
    assert (author_page(addon_site), (addon_site / "study.html").read_text()) == before


def test_adding_a_source_updates_the_author_page(addon_site):
    data = json.loads((addon_site / "textbook/textbook.json").read_text())
    data["chapters"][3]["source"] = "sources/from-word.docx"
    data["chapters"][3]["title"] = "Sample rhythms"
    data["chapters"][0]["title"] = "Sample rhythms, the PDF"
    write_manifest(addon_site, data)
    write(addon_site, build(addon_site))
    page = author_page(addon_site)
    assert '<a href="chapter-not-written.html">Read the chapter</a>' in page
    assert "<li>Planned detail</li>" not in page  # replaced by the real headings


def test_editing_inside_a_region_is_caught_and_the_page_is_never_deleted(addon_site):
    path = addon_site / "author-ada.html"
    path.write_text(path.read_text().replace("Read the chapter", "Read it"))
    result = build(addon_site)
    assert stale(addon_site, result) == ["author-ada.html"]
    write(addon_site, result)
    assert "Read the chapter" in path.read_text()
    assert "author-ada.html" not in (addon_site / "textbook/generated.txt").read_text()


def test_region_errors_name_the_page(addon_site):
    (addon_site / "author-zed.html").write_text("<!-- textbook:author-chapters zed -->\n<!-- /textbook -->\n")
    assert any(e.startswith("author-zed.html:") for e in build(addon_site).errors)
