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
    (warning,) = check_scanned(pages, [0, 1, 2], "x.pdf")
    assert warning.startswith("page 3: is a picture with no text in it") and "kept as a figure" in warning


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


def test_join_runs_keeps_formatting_that_spans_the_line_break():
    lines = [[Run("as shown by a", frozenset({"em"}))], [Run("graphical file manager", frozenset({"em"}))]]
    assert join_runs(lines, frozenset()) == [Run("as shown by a graphical file manager", frozenset({"em"}))]


def test_join_runs_rejoins_split_words_and_keeps_formatting():
    lines = [[Run("the circa-")], [Run("dian", frozenset({"em"})), Run(" clock")]]
    assert join_runs(lines, frozenset()) == [Run("the circa"), Run("dian", frozenset({"em"})), Run(" clock")]


def test_spans_to_runs_maps_styles_to_marks():
    spans = [Span("b", 10, bold=True), Span("i", 10, italic=True), Span("c", 10, mono=True), Span("2", 6, sup=True)]
    assert [r.marks for r in spans_to_runs(spans)] == [{"strong"}, {"em"}, {"code"}, {"sup"}]


def test_strip_marker_removes_leading_characters_across_runs():
    assert strip_marker([Run("•"), Run(" item")], 2) == [Run("item")]


# ---- Quirks of real PDFs -------------------------------------------------------

from tools.textbook.readers.pdf import (  # noqa: E402
    find_text_tables,
    is_code,
    merge_fragments,
    remove_contents_pages,
)


def test_marker_fragment_joins_its_words_even_when_drawn_lower():
    marker = line("•", x0=50, x1=54, y0=101)          # sorts after the words
    words = line("Find two phases", x0=62, y0=100)
    number = line("2", x0=50, x1=56, y0=200, size=16)
    title = line("Convergence", x0=70, y0=200, size=16)
    far = line("-", x0=50, x1=54, y0=300)
    other = line("too far away", x0=400, y0=300)
    info = page_with([words, marker, number, title, far, other])
    merge_fragments(info)
    assert sorted(l.text for l in info.lines) == ["-", "2 Convergence", "too far away", "• Find two phases"]


def test_contents_pages_are_dropped():
    toc = page_with([line("Contents", size=16, y0=50)] +
                    [line(f"{n} – Chapter {n}" + "." * 20 + str(n * 7), y0=80 + n * 14) for n in range(1, 5)])
    body = page_with([line("Real text. . . and an ellipsis", page=1)])
    assert remove_contents_pages([toc, body]) == [1]
    assert toc.lines == [] and len(body.lines) == 1


def test_running_heads_beyond_the_fixed_margin():
    """Heads at 9% from the top and folios at 89%, as in real books."""
    pages = []
    for n in range(4):
        head = f"{n + 7}   Navigation" if n % 2 else f"Section {n}   {n + 7}"
        pages.append(page_with([
            line(head, y0=73, page=n),
            line(f"Body text on page {n}, long enough to be ordinary text.", y0=150, page=n),
            line(str(n + 7), y0=707, page=n),
        ]))
    remove_running_heads(pages)
    assert [[l.text for l in p.lines] for p in pages] == [
        [f"Body text on page {n}, long enough to be ordinary text."] for n in range(4)]


def test_a_small_copy_of_a_heading_at_the_top_is_a_running_head():
    pages = [
        page_with([line("Measuring a period", size=16, y0=200), line("Body.", y0=230)]),
        page_with([line("Measuring a period", y0=60, page=1), line("More body.", y0=150, page=1)]),
    ]
    remove_running_heads(pages)
    assert [l.text for l in pages[1].lines] == ["More body."]
    assert [l.text for l in pages[0].lines] == ["Measuring a period", "Body."]


def test_punctuation_alone_is_never_a_running_head():
    pages = [page_with([line("-", y0=60, page=n), line("Text", y0=200, page=n)]) for n in range(3)]
    remove_running_heads(pages)
    assert all(p.lines[0].text == "-" for p in pages)


def test_borderless_table_with_a_wrapped_cell():
    rows = [("Shortcut", "Result", 300), ("cd", "Go home.", 320), ("cd -", "Go back to the previous", 340)]
    lines = [line("Some text before the table.", y0=260, x0=50, x1=500)]
    for a, b, y in rows:
        lines += [line(a, x0=50, y0=y), line(b, x0=200, y0=y)]
    lines += [line("directory.", x0=200, y0=354), line("Text after the table, much later.", y0=420, x0=50, x1=500)]
    info = page_with(lines)
    find_text_tables(info)
    (table,) = info.tables
    assert table.rows == [["Shortcut", "Result"], ["cd", "Go home."], ["cd -", "Go back to the previous directory."]]
    assert [l.text for l in info.lines] == ["Some text before the table.", "Text after the table, much later."]


def test_side_by_side_math_is_not_a_table():
    lines = [line("x", x0=50, y0=100, math=True), line("(1)", x0=400, y0=100),
             line("y", x0=50, y0=120, math=True), line("(2)", x0=400, y0=120)]
    info = page_with(lines)
    find_text_tables(info)
    assert info.tables == [] and len(info.lines) == 4


def test_scattered_text_is_not_a_table():
    lines = [line("a", x0=50, y0=100), line("b", x0=500, y0=100),
             line("c", x0=150, y0=120), line("d", x0=300, y0=120),
             line("e", x0=400, y0=140), line("f", x0=250, y0=140)]
    info = page_with(lines)
    find_text_tables(info)
    assert info.tables == []


def test_code_lines_are_all_monospace():
    assert is_code(line("$ ls -l", mono=True))
    assert not is_code(line("Run ls to list files"))
    assert classify(line("$ ls -l", mono=True), 10, {}) == ("code", 0)


from tools.textbook.readers.pdf import is_real_table  # noqa: E402


def test_real_tables_are_mostly_filled():
    assert is_real_table([["Rhythm", "Period"], ["Circadian", "24 h"], ["Ultradian", ""]])
    grid = [[""] * 30 for _ in range(40)]
    grid[3][2] = "a stray word"
    assert not is_real_table(grid)                      # graph paper
    assert not is_real_table([["only one row", "x"]])   # one row is not a table
    assert not is_real_table([["a"], ["b"]])            # one column is not a table


from tools.textbook.readers.pdf import _without_bullet, is_caption  # noqa: E402


def test_captions_need_a_separator_or_small_type():
    assert is_caption(line("Figure 3: A wave."), 10)
    assert is_caption(line("Figure 3 - A wave"), 10)
    assert is_caption(line("Figure 3"), 10)
    assert is_caption(line("● Figure 2: Predator-prey graph"), 10)   # written as a bullet
    assert is_caption(line("Figure 3 shows a wave", size=8), 10)           # smaller type
    assert not is_caption(line("Figure 3). Thus, serotonin resets the clock"), 10)
    assert not is_caption(line("Figure 1 presents the dynamics of two species"), 10)
    assert _without_bullet("● Figure 2: x") == "Figure 2: x"
    assert _without_bullet("1. Figure 2: x") == "1. Figure 2: x"            # numbers are not bullets
