"""Black-box tests: real source files in, Document out.

Each test writes a source file (PDF, Word or Markdown), reads it with the
public `read()` entry point, and checks only what came out.
"""

import pytest

from book_helpers import samples
from tools.textbook.model import Code, Figure, Heading, ListBlock, Paragraph, Quote, Table, plain_text
from tools.textbook.readers import ReaderError, read
from tools.textbook.structure import chapter_body


def texts(doc, kind):
    return [plain_text(b.content) for b in doc.blocks if isinstance(b, kind)]


# ---- PDF -----------------------------------------------------------------------


@pytest.fixture
def pdf_doc(tmp_path):
    return read(samples.sample_pdf(tmp_path / "s.pdf"))


def test_pdf_finds_title_and_sections_by_font_size(pdf_doc):
    assert [(b.level, plain_text(b.content)) for b in pdf_doc.blocks if isinstance(b, Heading)] == [
        (1, samples.TITLE), *[(2, s) for s in samples.SECTIONS]]


def test_pdf_drops_running_heads_and_page_numbers(pdf_doc):
    everything = " ".join(texts(pdf_doc, Paragraph))
    assert "class draft" not in everything
    assert not any(t.strip().isdigit() for t in texts(pdf_doc, Paragraph))


def test_pdf_rejoins_hyphenated_words_but_keeps_real_hyphens(pdf_doc):
    assert texts(pdf_doc, Paragraph)[0] == samples.PARA_1_TEXT


def test_pdf_joins_a_paragraph_across_a_page_break(pdf_doc):
    assert texts(pdf_doc, Paragraph)[-1] == samples.PARA_3_TEXT


def test_pdf_lists(pdf_doc):
    lists = [b for b in pdf_doc.blocks if isinstance(b, ListBlock)]
    assert [(l.ordered, [plain_text(i.content) for i in l.items]) for l in lists] == [
        (False, samples.BULLETS), (True, samples.STEPS)]


def test_pdf_figure_with_caption(pdf_doc):
    (figure,) = [b for b in pdf_doc.blocks if isinstance(b, Figure)]
    assert figure.label == "Figure 1"
    assert plain_text(figure.caption) == samples.CAPTION
    assert figure.image.data.startswith(b"\x89PNG") and figure.alt == ""


def test_pdf_table_with_caption_above(pdf_doc):
    (table,) = [b for b in pdf_doc.blocks if isinstance(b, Table)]
    assert [[plain_text(c) for c in row] for row in table.rows] == samples.TABLE
    assert (table.label, plain_text(table.caption)) == ("Table 1", samples.TABLE_CAPTION)
    assert not any("Ultradian" in t for t in texts(pdf_doc, Paragraph))  # table text isn't repeated


def test_pdf_inline_bold_italic_and_partial_link(pdf_doc):
    para = next(b for b in pdf_doc.blocks if isinstance(b, Paragraph) and "claim" in plain_text(b.content))
    marked = {r.text: (r.marks, r.href) for r in para.content}
    assert marked["bold"][0] == {"strong"}
    assert marked["italic"][0] == {"em"}
    assert marked["link"][1] == samples.LINK_URL


def test_pdf_page_range_selects_pages(tmp_path):
    book = samples.book_pdf(tmp_path / "book.pdf")
    doc = read(book, "2")
    assert texts(doc, Paragraph) == ["Text that belongs to the second chapter.", "The end of chapter 2."]


def test_pdf_combined_book_split_by_heading(tmp_path):
    book = samples.book_pdf(tmp_path / "book.pdf")
    doc = chapter_body(read(book), "First chapter", heading="Chapter 1: First chapter")
    assert texts(doc, Heading) == ["Opening", "Closing"]
    assert texts(doc, Paragraph) == ["Text that belongs to the first chapter.", "The end of chapter 1."]


def test_pdf_two_columns_read_left_then_right(tmp_path):
    doc = read(samples.two_column_pdf(tmp_path / "two.pdf"))
    paras = texts(doc, Paragraph)
    assert len(paras) == 2
    assert paras[0].startswith("Left column line 1") and paras[0].endswith("line 8 of the first paragraph.")
    assert paras[1].startswith("Right column line 1")


def test_pdf_vector_figure_is_rasterized(tmp_path):
    doc = read(samples.vector_figure_pdf(tmp_path / "v.pdf"))
    (figure,) = [b for b in doc.blocks if isinstance(b, Figure)]
    assert figure.label == "Figure 2" and figure.image.data.startswith(b"\x89PNG")


def test_scanned_pdf_is_rejected_with_advice(tmp_path):
    with pytest.raises(ReaderError, match="looks like a scan.*OCR"):
        read(samples.scanned_pdf(tmp_path / "scan.pdf"))


def test_broken_pdf_is_rejected(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(ReaderError, match="could not be opened"):
        read(bad)


def test_bad_page_range_is_rejected(tmp_path):
    with pytest.raises(ReaderError, match="outside this PDF"):
        read(samples.book_pdf(tmp_path / "b.pdf"), "3-9")


# ---- Word ----------------------------------------------------------------------


@pytest.fixture
def docx_doc(tmp_path):
    return read(samples.sample_docx(tmp_path / "s.docx"))


def test_docx_headings_from_styles(docx_doc):
    assert [(b.level, plain_text(b.content)) for b in docx_doc.blocks if isinstance(b, Heading)] == [
        (1, samples.TITLE), *[(2, s) for s in samples.SECTIONS]]


def test_docx_alt_text_comes_from_the_image(docx_doc):
    (figure,) = [b for b in docx_doc.blocks if isinstance(b, Figure)]
    assert figure.alt == "Black bars on white, evenly spaced"
    assert (figure.label, plain_text(figure.caption)) == ("Figure 1", samples.CAPTION)


def test_docx_lists_tables_and_links(docx_doc):
    lists = [b for b in docx_doc.blocks if isinstance(b, ListBlock)]
    assert [(l.ordered, len(l.items)) for l in lists] == [(False, 3), (True, 2)]
    (table,) = [b for b in docx_doc.blocks if isinstance(b, Table)]
    assert table.label == "Table 1"
    para = next(b for b in docx_doc.blocks if isinstance(b, Paragraph) and "claim" in plain_text(b.content))
    assert any(r.href == samples.LINK_URL for r in para.content)


def test_docx_nested_lists_quotes_and_code(tmp_path):
    import docx

    d = docx.Document()
    d.add_paragraph("Outer one", style="List Bullet")
    d.add_paragraph("Inner one", style="List Bullet 2")
    d.add_paragraph("Inner two", style="List Bullet 2")
    d.add_paragraph("Outer two", style="List Bullet")
    d.add_paragraph("A quoted line.", style="Quote")
    d.add_paragraph("Another quoted line.", style="Quote")
    p = d.add_paragraph()
    run = p.add_run("print('hi')")
    run.font.name = "Courier New"
    sup = d.add_paragraph().add_run("x")
    sup.font.superscript = True
    path = tmp_path / "n.docx"
    d.save(path)
    doc = read(path)
    (lst, quote, code, sup_para) = doc.blocks
    assert [plain_text(i.content) for i in lst.items] == ["Outer one", "Outer two"]
    assert [plain_text(i.content) for i in lst.items[0].children[0].items] == ["Inner one", "Inner two"]
    assert isinstance(quote, Quote) and len(quote.content) == 2
    assert isinstance(code, Code) and code.text == "print('hi')"
    assert sup_para.content[0].marks == {"sup"}


def test_docx_missing_alt_text_is_empty(tmp_path):
    doc = read(samples.sample_docx(tmp_path / "s.docx", alt=None))
    (figure,) = [b for b in doc.blocks if isinstance(b, Figure)]
    assert figure.alt == ""


def test_broken_docx_is_rejected(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"not a zip")
    with pytest.raises(ReaderError, match="could not be opened as a Word document"):
        read(bad)


# ---- Markdown ------------------------------------------------------------------


def md(tmp_path, text, name="c.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return read(path)


def test_markdown_sample(tmp_path):
    doc = read(samples.sample_markdown(tmp_path / "s.md"))
    (figure,) = [b for b in doc.blocks if isinstance(b, Figure)]
    assert figure.alt == "Black bars on white, evenly spaced" and figure.label == "Figure 1"
    (table,) = [b for b in doc.blocks if isinstance(b, Table)]
    assert table.label == "Table 1"


def test_markdown_never_passes_raw_html_through(tmp_path):
    doc = md(tmp_path, "<div onclick=\"x()\">block</div>\n\nText <span>inline</span> and <sup>2</sup>.\n")
    assert len(doc.warnings) == 3  # the block, <span> and </span>
    (para,) = doc.blocks
    assert plain_text(para.content) == "Text inline and 2."
    assert [r.marks for r in para.content if r.text == "2"] == [{"sup"}]


def test_markdown_nested_lists_quotes_code_and_start_numbers(tmp_path):
    doc = md(tmp_path, "3. three\n4. four\n   - nested\n\n> quoted\n\n```\ncode here\n```\n")
    lst, quote, code = doc.blocks
    assert lst.ordered and lst.start == 3
    assert plain_text(lst.items[1].children[0].items[0].content) == "nested"
    assert plain_text(quote.content[0]) == "quoted"
    assert code.text == "code here"


def test_markdown_figure_caption_from_following_paragraph(tmp_path):
    (tmp_path / "f.png").write_bytes(samples.png())
    doc = md(tmp_path, "![Bars](f.png)\n\nFigure 4. Bars in a row.\n")
    (figure,) = doc.blocks
    assert (figure.label, plain_text(figure.caption)) == ("Figure 4", "Bars in a row.")


@pytest.mark.parametrize(
    "text, message",
    [
        ("![x](https://example.org/a.png)\n", "is on the web"),
        ("![x](missing.png)\n", "was not found"),
        ("![x](f.gif)\n", "must be PNG or JPEG"),
    ],
)
def test_markdown_image_problems(tmp_path, text, message):
    (tmp_path / "f.gif").write_bytes(b"GIF89a")
    with pytest.raises(ReaderError, match=message):
        md(tmp_path, text)


def test_markdown_must_be_utf8(tmp_path):
    path = tmp_path / "latin.md"
    path.write_bytes("café".encode("latin-1"))
    with pytest.raises(ReaderError, match="UTF-8"):
        read(path)


# ---- Format selection --------------------------------------------------------


@pytest.mark.parametrize(
    "name, advice",
    [("c.doc", "Save it as .docx"), ("c.gdoc", "Download it from Google Docs"), ("c.tex", "Compile it to PDF"),
     ("c.xyz", "Convert it to one of those formats")],
)
def test_unsupported_formats_say_how_to_convert(tmp_path, name, advice):
    path = tmp_path / name
    path.write_text("x")
    with pytest.raises(ReaderError, match=advice):
        read(path)


def test_missing_file_and_pages_on_non_pdf(tmp_path):
    with pytest.raises(ReaderError, match="does not exist"):
        read(tmp_path / "nope.pdf")
    path = tmp_path / "c.md"
    path.write_text("# x\n")
    with pytest.raises(ReaderError, match='"pages" only works for PDFs'):
        read(path, "1-2")


def test_pdf_with_real_book_quirks(tmp_path):
    """Patterns found converting real PDFs (a LibreOffice book, XeTeX and Google
    Docs exports), rebuilt in samples.real_world_pdf because real files can't
    be committed. See that function for each quirk."""
    from test_cross_format import outline

    doc = chapter_body(read(samples.real_world_pdf(tmp_path / "rw.pdf")), "Real world")
    got = []
    for block in doc.blocks:
        if isinstance(block, Code):
            got.append(("code", block.text))
        else:
            got.extend(outline(type("Doc", (), {"blocks": [block]})))
    assert got == samples.REAL_WORLD_OUTLINE
    assert doc.warnings == []
