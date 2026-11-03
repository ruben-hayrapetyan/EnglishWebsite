"""The generated pages follow the site's rules and the add-ons' contracts.

These run on the sample site built from PDF, Word and Markdown sources, so
every rule is checked on real converter output, not on hand-written HTML.
"""

import re
import unicodedata

import pytest
from lxml import html as lxml_html

from book_helpers import ROOT
from tools.textbook.render import GENERATOR_NOTE

PAGES = ["textbook.html", "chapter-from-pdf.html", "chapter-from-word.html", "chapter-from-markdown.html"]


@pytest.fixture
def pages(sample_site):
    return {name: (sample_site / name).read_text() for name in PAGES}


def doc(text):
    return lxml_html.fromstring(text.encode())


def test_generated_marker_after_doctype(pages):
    for name, text in pages.items():
        assert text.split("\n")[:2] == ["<!doctype html>", GENERATOR_NOTE], name


def test_head_and_chrome_match_the_template(pages):
    template = (ROOT / "_template.html").read_text()
    for text in pages.values():
        for needle in ('<link rel="stylesheet" href="assets/css/main.css">',
                       '<script src="assets/js/site.js" defer></script>',
                       '<a class="skip-link" href="#main">Skip to content</a>',
                       '<header class="site-header" data-site-header></header>',
                       '<footer class="site-footer" data-site-footer></footer>'):
            assert needle in template and needle in text


def test_one_h1_and_headings_in_order(pages):
    for name, text in pages.items():
        levels = [int(h.tag[1]) for h in doc(text).iter("h1", "h2", "h3", "h4", "h5", "h6")]
        assert levels.count(1) == 1 and levels[0] == 1, name
        assert all(b <= a + 1 for a, b in zip(levels, levels[1:])), (name, levels)


def test_ids_unique_and_contents_links_resolve(pages):
    for name, text in pages.items():
        d = doc(text)
        ids = d.xpath("//@id")
        assert len(ids) == len(set(ids)), name
        for href in d.xpath("//a/@href"):
            if href.startswith("#"):
                assert href[1:] in ids, (name, href)


def test_images_have_alt_and_exist(pages, sample_site):
    for name, text in pages.items():
        for img in doc(text).iter("img"):
            assert img.get("alt"), (name, img.get("src"))
            assert (sample_site / img.get("src")).is_file()


def test_alt_text_falls_back_to_the_manifest_then_source(pages):
    alts = {n: [i.get("alt") for i in doc(t).iter("img")] for n, t in pages.items()}
    assert alts["chapter-from-pdf.html"] == ["Black bars on white, evenly spaced"]   # from textbook.json
    assert alts["chapter-from-word.html"] == ["Black bars on white, evenly spaced"]  # from the .docx


def test_page_header_and_article_are_read_aloud_scopes(pages):
    for name in PAGES[1:]:
        d = doc(pages[name])
        assert d.xpath("//header[contains(@class,'page-header')][@data-read-aloud]")
        assert d.xpath("//article[contains(@class,'prose')][@data-read-aloud]")
        assert d.xpath("//nav[contains(@class,'chapter-nav')][not(contains(@class,'pager'))][@data-read-aloud-skip]")


def test_paragraph_text_is_stable_for_notes(pages):
    """Notes find a highlight again by its exact text, so text must be normalized:
    one line per paragraph, single spaces, NFC, no soft hyphens or ligatures."""
    for name in PAGES[1:]:
        for line in pages[name].splitlines():
            if not line.strip().startswith(("<p>", "<li>")):
                continue
            assert line.rstrip().endswith(("</p>", "</li>")), (name, line)
            text = re.sub(r"<[^>]+>", "", line).strip()
            assert "  " not in text and "­" not in text
            assert not re.search("[ﬀ-ﬆ]", text)
            assert unicodedata.normalize("NFC", text) == text


def test_pager_links_chapters_in_order(pages):
    def steps(name):
        return [(a.get("rel"), a.get("href")) for a in doc(pages[name]).xpath("//a[@class and contains(@class,'chapter-nav__step')]")]

    assert steps("chapter-from-pdf.html") == [("next", "chapter-from-word.html")]
    assert steps("chapter-from-word.html") == [("prev", "chapter-from-pdf.html"), ("next", "chapter-from-markdown.html")]
    assert steps("chapter-from-markdown.html") == [("prev", "chapter-from-word.html")]


def test_contents_page_lists_every_chapter_and_marks_missing_ones(pages):
    d = doc(pages["textbook.html"])
    cards = d.xpath("//article[contains(@class,'card')]")
    assert [c.get("id") for c in cards] == ["from-pdf", "from-word", "from-markdown", "not-written"]
    assert [c.xpath("string(.//p[@class='card__meta'])") for c in cards] == [f"Chapter {n}" for n in range(1, 5)]
    linked = [c.xpath("string(.//h3/a/@href)") for c in cards]
    assert linked == ["chapter-from-pdf.html", "chapter-from-word.html", "chapter-from-markdown.html", ""]
    assert cards[3].xpath("string(.//span[@class='tag'])") == "Coming soon"
    assert len(d.xpath("//mark")) == 1


def test_ai_credit_names_the_tool_and_the_authors_statement(pages):
    def credit(name):
        return doc(pages[name]).xpath("string(//aside[@class='ai-credit'])").strip()

    for name in PAGES:
        assert credit(name).startswith("Generative AI: Claude Opus 5.5 (Anthropic)")
    assert "have not yet stated" in credit("chapter-from-pdf.html")
    assert credit("chapter-from-markdown.html").endswith("The authors used no generative AI.")


def test_byline_and_meta(pages):
    d = doc(pages["chapter-from-markdown.html"])
    assert d.xpath("string(//p[@class='page-header__meta'])") == "Chapter 3 · Second unit"
    assert d.xpath("string(//header//p[starts-with(., 'By ')])") == "By Ada Example, Ben Example and Cy Example"
    lede = doc(pages["chapter-from-word.html"]).xpath("string(//p[@class='page-header__lede'])")
    assert lede == "The sample chapter, written in Word."
