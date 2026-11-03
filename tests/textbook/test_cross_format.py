"""Black-box, cross-format: the same chapter written as a PDF, a Word file and
a Markdown file must convert to the same outline and the same text.

This is the main guarantee behind "accept many forms of the textbook": an
author can hand in any supported format and readers get the same page.
"""

import pytest

from book_helpers import samples
from tools.textbook.model import Figure, Heading, ListBlock, Paragraph, Table, plain_text
from tools.textbook.readers import read
from tools.textbook.structure import chapter_body


def outline(doc):
    out = []
    for b in doc.blocks:
        if isinstance(b, Heading):
            out.append(("h", b.level, plain_text(b.content)))
        elif isinstance(b, Paragraph):
            out.append(("p", plain_text(b.content)))
        elif isinstance(b, ListBlock):
            out.append(("list", b.ordered, tuple(plain_text(i.content) for i in b.items)))
        elif isinstance(b, Figure):
            out.append(("figure", b.label, plain_text(b.caption)))
        elif isinstance(b, Table):
            out.append(("table", b.label, plain_text(b.caption),
                        tuple(tuple(plain_text(c) for c in row) for row in b.rows)))
    return out


def marks(doc):
    """Formatting and links, independent of how runs happen to be split."""
    return sorted(
        (r.text.strip(), tuple(sorted(r.marks)), r.href)
        for b in doc.blocks if isinstance(b, Paragraph)
        for r in b.content if r.marks or r.href
    )


@pytest.fixture(scope="module")
def converted(tmp_path_factory):
    folder = tmp_path_factory.mktemp("formats")
    return {kind: chapter_body(read(write(folder / f"sample.{kind}")), samples.TITLE)
            for kind, write in samples.WRITERS.items()}


@pytest.mark.parametrize("kind", ["docx", "md"])
def test_outline_matches_the_pdf(converted, kind):
    assert outline(converted[kind]) == outline(converted["pdf"])


@pytest.mark.parametrize("kind", ["docx", "md"])
def test_formatting_and_links_match_the_pdf(converted, kind):
    assert marks(converted[kind]) == marks(converted["pdf"])


def test_expected_outline(converted):
    """Pin the shared outline itself, so all three can't drift together."""
    assert outline(converted["md"]) == [
        ("h", 2, "Measuring a period"),
        ("p", samples.PARA_1_TEXT),
        ("p", samples.PARA_2[0]),
        ("list", False, tuple(samples.BULLETS)),
        ("h", 2, "Figures and tables"),
        ("figure", "Figure 1", samples.CAPTION),
        ("table", "Table 1", samples.TABLE_CAPTION, tuple(tuple(r) for r in samples.TABLE)),
        ("h", 2, "Summary"),
        ("list", True, tuple(samples.STEPS)),
        ("p", "A bold claim, an italic aside and a link."),
        ("p", samples.PARA_3_TEXT),
    ]
