"""Glass-box tests for the PDF layout heuristics, one pass at a time.

These build Line/PageInfo objects by hand, so each heuristic is tested on
exactly the layout it's meant to handle, with no PDF involved.
"""

import pytest

from tools.textbook.readers import ReaderError
from tools.textbook.readers.pdf import (
    ImageItem,
    Line,
    PageInfo,
    Span,
    TableItem,
    _ranges,
    body_size,
    check_scanned,
    classify,
    heading_tiers,
    is_bold_heading,
    is_two_column,
    join_runs,
    margin_key,
    parse_page_spec,
    reading_order,
    remove_repeated_images,
    remove_running_heads,
    spans_to_runs,
    split_footnotes,
    starts_paragraph,
    strip_marker,
    typical_pitch,
)
from tools.textbook.model import Run

W, H = 600.0, 800.0


def line(text, x0=50, y0=100, x1=None, size=10, bold=False, page=0, block=0, block_lines=1, **span):
    x1 = x1 if x1 is not None else x0 + len(text) * size * 0.5
    return Line([Span(text, size, bold=bold, **span)], x0, y0, x1, y0 + size, page, block, block_lines)


def page_with(lines, images=(), tables=()):
    info = PageInfo(W, H)
    info.lines = list(lines)
    info.images = list(images)
    info.tables = list(tables)
    return info


# ---- page ranges -------------------------------------------------------------


def test_parse_page_spec():
    assert parse_page_spec(None, 3) == [0, 1, 2]
    assert parse_page_spec("2-3", 5) == [1, 2]
    assert parse_page_spec("1, 3-4", 5) == [0, 2, 3]


@pytest.mark.parametrize("spec", ["0", "4-2", "1-9", "abc", "1-"])
def test_parse_page_spec_rejects_bad_ranges(spec):
    with pytest.raises(ReaderError):
        parse_page_spec(spec, 5)


def test_ranges_formats_page_lists():
    assert _ranges([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8"


# ---- clean-up ----------------------------------------------------------------


def test_running_heads_and_page_numbers_are_removed():
    pages = []
    for n in range(4):
        pages.append(page_with([
            line("Sample book - draft", y0=20, page=n),         # running head
            line(f"Body text on page {n}", y0=300, page=n),
            line(str(n + 1), y0=770, page=n),                  # page number
            line(f"Chapter 2 - page {n + 1}", y0=775, x0=300, page=n),  # numbered footer
        ]))
    remove_running_heads(pages)
    assert [[l.text for l in p.lines] for p in pages] == [[f"Body text on page {n}"] for n in range(4)]


def test_text_in_the_margin_that_does_not_repeat_is_kept():
    pages = [page_with([line("A one-off note at the top", y0=20)]), page_with([line("Body", y0=300, page=1)])]
    remove_running_heads(pages)
    assert pages[0].lines[0].text == "A one-off note at the top"


def test_margin_key_ignores_numbers_and_case():
    assert margin_key("Page 3 of 10") == margin_key("PAGE 4 of 10")


def test_repeated_images_are_decorations():
    def img(digest, page):
        return ImageItem(b"x", "png", 0, 0, 50, 50, page, digest)

    pages = [page_with([], [img("logo", n), img(f"fig{n}", n)]) for n in range(3)]
    remove_repeated_images(pages)
    assert [[i.digest for i in p.images] for p in pages] == [["fig0"], ["fig1"], ["fig2"]]


def test_mostly_scanned_document_is_rejected():
    full = ImageItem(b"x", "png", 0, 0, W, H, 0)
    with pytest.raises(ReaderError, match="looks like a scan"):
        check_scanned([page_with([], [full]), page_with([], [full])], [0, 1], "scan.pdf")


def test_one_scanned_page_is_a_warning():
    full = ImageItem(b"x", "png", 0, 0, W, H, 2)
    pages = [page_with([line("text")]), page_with([line("text")]), page_with([], [full])]
    assert check_scanned(pages, [0, 1, 2], "x.pdf") == [
        "page 3: looks scanned (a picture of text) and was skipped; run OCR or re-export it"]


def test_body_size_is_the_most_used_size():
    pages = [page_with([line("A big title", size=20), line("body " * 30, size=10), line("more body " * 10, size=10)])]
    assert body_size(pages) == 10


def test_body_size_defaults_when_empty():
    assert body_size([page_with([])]) == 10.0


def test_footnotes_are_split_from_the_foot_of_the_page():
    info = page_with([
        line("Body text with a marker", y0=200),
        line("1 The first note.", y0=700, size=8),
        line("which wraps here.", y0=710, size=8),
        line("2 The second note.", y0=720, size=8),
    ])
    notes = split_footnotes([info], 10)
    assert [[l.text for l in n] for n in notes] == [["1 The first note.", "which wraps here."], ["2 The second note."]]
    assert [l.text for l in info.lines] == ["Body text with a marker"]


def test_small_text_without_a_marker_is_not_a_footnote():
    info = page_with([line("Body", y0=200), line("A small caption-like line", y0=700, size=8)])
    assert split_footnotes([info], 10) == []
    assert len(info.lines) == 2


# ---- reading order -----------------------------------------------------------


def two_columns():
    left = [line(f"left {n}", x0=40, x1=280, y0=100 + n * 12) for n in range(6)]
    right = [line(f"right {n}", x0=320, x1=560, y0=100 + n * 12) for n in range(6)]
    return left, right


def test_two_columns_are_detected():
    left, right = two_columns()
    assert is_two_column(left + right, W)
    single = [line(f"wide line {n}", x0=40, x1=560, y0=100 + n * 12) for n in range(12)]
    assert not is_two_column(single, W)
    assert not is_two_column(left[:3], W)  # too few lines to tell


def test_left_column_is_read_before_right_and_wide_items_split_bands():
    left, right = two_columns()
    title = line("A wide title", x0=40, x1=560, y0=60, size=16)
    figure = ImageItem(b"x", "png", 40, 200, 560, 300, 0)
    after_left = [line(f"after left {n}", x0=40, x1=280, y0=320 + n * 12) for n in range(2)]
    after_right = [line(f"after right {n}", x0=320, x1=560, y0=320 + n * 12) for n in range(2)]
    order = reading_order(page_with([title, *right, *left, *after_right, *after_left], [figure]))
    names = [getattr(it, "text", "FIGURE") for it in order]
    assert names == (["A wide title"] + [f"left {n}" for n in range(6)] + [f"right {n}" for n in range(6)]
                     + ["FIGURE"] + ["after left 0", "after left 1", "after right 0", "after right 1"])


def test_single_column_reads_top_to_bottom():
    a, b = line("second", y0=200), line("first", y0=100)
    table = TableItem([["a", "b"], ["c", "d"]], 40, 150, 560, 180, 0)
    assert [getattr(i, "text", "TABLE") for i in reading_order(page_with([a, b], tables=[table]))] == [
        "first", "TABLE", "second"]


# ---- classification ----------------------------------------------------------


def test_heading_tiers_rank_sizes_biggest_first():
    lines = [line("Title", size=24), line("Section", size=16), line("Sub", size=13), line("body", size=10)]
    assert heading_tiers(lines, 10) == {24: 1, 16: 2, 13: 3}


def test_bold_body_line_alone_is_a_minor_heading():
    assert is_bold_heading(line("Key ideas", bold=True), 10)
    assert not is_bold_heading(line("A bold sentence that ends.", bold=True), 10)
    assert not is_bold_heading(line("Key ideas", bold=True, block_lines=3), 10)
    assert not is_bold_heading(line("Key ideas"), 10)
    assert not is_bold_heading(line("1. Bold list item", bold=True), 10)


@pytest.mark.parametrize(
    "ln, expected",
    [
        (line("Figure 2. Waves", size=8), ("caption", 0)),
        (line("Section", size=16), ("heading", 1)),
        (line("Key ideas", bold=True), ("heading", 2)),
        (line("• a point"), ("item", 0)),
        (line("Just text."), ("body", 0)),
    ],
)
def test_classify(ln, expected):
    assert classify(ln, 10, {16: 1}) == expected


# ---- assembly ----------------------------------------------------------------

FRAME = {"left": 50, "right": 550, "width": 500}


def test_new_paragraph_after_a_large_gap():
    a = line("End of one paragraph", y0=100, x1=550)
    assert starts_paragraph(a, line("Next", y0=125), pitch=12, body=10, frame=FRAME)
    assert not starts_paragraph(a, line("same paragraph", y0=112), pitch=12, body=10, frame=FRAME)


def test_new_paragraph_at_a_first_line_indent():
    a = line("full width line ending.", x0=50, x1=550, y0=100)
    assert starts_paragraph(a, line("Indented start", x0=70, y0=112), pitch=12, body=10, frame=FRAME)


def test_new_paragraph_after_a_short_line_that_ends_a_sentence():
    short = line("Short last line.", x0=50, x1=200, y0=100)
    assert starts_paragraph(short, line("Next paragraph", y0=112), pitch=12, body=10, frame=FRAME)
    unfinished = line("short but unfinished", x0=50, x1=200, y0=100)
    assert not starts_paragraph(unfinished, line("continues", y0=112), pitch=12, body=10, frame=FRAME)


def test_paragraph_continues_across_a_page_break():
    end = line("a sentence that runs on", page=0, y0=760, x1=550)
    assert not starts_paragraph(end, line("to the next page.", page=1, y0=40), pitch=12, body=10, frame=FRAME)
    done = line("a finished sentence.", page=0, y0=760, x1=550)
    assert starts_paragraph(done, line("New paragraph", page=1, y0=40), pitch=12, body=10, frame=FRAME)
    assert not starts_paragraph(done, line("lowercase continuation", page=1, y0=40), pitch=12, body=10, frame=FRAME)


def test_typical_pitch_is_the_median_line_spacing():
    lines = [line("a", y0=100), line("b", y0=112), line("c", y0=124), line("d", y0=200, block=1)]
    assert typical_pitch(lines, 10) == 12
    assert typical_pitch([], 10) == 12.5


def test_join_runs_rejoins_split_words_and_keeps_formatting():
    lines = [[Run("the circa-")], [Run("dian", frozenset({"em"})), Run(" clock")]]
    assert join_runs(lines, frozenset()) == [Run("the circa"), Run("dian", frozenset({"em"})), Run(" clock")]


def test_spans_to_runs_maps_styles_to_marks():
    spans = [Span("b", 10, bold=True), Span("i", 10, italic=True), Span("c", 10, mono=True), Span("2", 6, sup=True)]
    assert [r.marks for r in spans_to_runs(spans)] == [{"strong"}, {"em"}, {"code"}, {"sup"}]


def test_strip_marker_removes_leading_characters_across_runs():
    assert strip_marker([Run("•"), Run(" item")], 2) == [Run("item")]
