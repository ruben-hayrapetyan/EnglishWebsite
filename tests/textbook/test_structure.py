"""Glass-box tests for tools/textbook/structure.py."""

import pytest

from tools.textbook.model import Document, Heading, Paragraph, Run
from tools.textbook.readers import ReaderError
from tools.textbook.structure import chapter_body, drop_title, normalize_levels, select_section


def H(level, text):
    return Heading(level, [Run(text)])


def P(text):
    return Paragraph([Run(text)])


def outline(doc):
    return [(b.level, b.content[0].text) if isinstance(b, Heading) else b.content[0].text for b in doc.blocks]


BOOK = Document(
    [H(1, "Chapter 1: Clocks"), H(2, "Intro"), P("clock text"), H(1, "Chapter 2: Sleep"), H(2, "Intro"), P("sleep text")],
    "book.pdf",
)


def test_select_section_takes_one_chapter_out_of_a_book():
    assert outline(select_section(BOOK, "Sleep")) == [(1, "Chapter 2: Sleep"), (2, "Intro"), "sleep text"]
    assert outline(select_section(BOOK, "chapter 1 clocks")) == [(1, "Chapter 1: Clocks"), (2, "Intro"), "clock text"]


def test_select_section_lists_the_headings_it_found_when_nothing_matches():
    with pytest.raises(ReaderError, match=r"no heading matches \"Tides\".*'Chapter 2: Sleep'"):
        select_section(BOOK, "Tides")


def test_drop_title_removes_a_matching_title():
    doc = drop_title(Document([H(1, "Chronotypes"), H(2, "A"), P("x")], "s"), "Chronotypes")
    assert outline(doc) == [(2, "A"), "x"]
    assert doc.warnings == []


def test_drop_title_warns_when_the_source_title_differs():
    doc = drop_title(Document([H(1, "Chronotype stuff"), H(2, "A"), H(2, "B")], "s"), "Chronotypes")
    assert outline(doc) == [(2, "A"), (2, "B")]
    assert "the page uses textbook.json" in doc.warnings[0]


def test_drop_title_keeps_sections_when_there_is_no_title():
    doc = Document([H(2, "A"), P("x"), H(2, "B")], "s")
    assert outline(drop_title(doc, "Chronotypes")) == [(2, "A"), "x", (2, "B")]


def test_drop_title_without_headings_is_a_no_op():
    doc = Document([P("only text")], "s")
    assert drop_title(doc, "x") is doc


@pytest.mark.parametrize(
    "levels, expected",
    [
        ([3, 4, 4, 3], [2, 3, 3, 2]),   # shift so the top level is h2
        ([1, 3, 5], [2, 3, 4]),         # no skipped levels
        ([2, 2], [2, 2]),
        ([2, 3, 4, 5, 6, 7, 8], [2, 3, 4, 5, 6, 6, 6]),  # never past h6
    ],
)
def test_normalize_levels(levels, expected):
    doc = normalize_levels(Document([H(l, str(i)) for i, l in enumerate(levels)], "s"))
    assert [b.level for b in doc.blocks] == expected


def test_chapter_body_combines_the_steps():
    doc = chapter_body(BOOK, "Sleep", heading="Chapter 2: Sleep")
    assert outline(doc) == [(2, "Intro"), "sleep text"]
