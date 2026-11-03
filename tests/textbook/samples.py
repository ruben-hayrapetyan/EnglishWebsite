"""Sample chapter sources, generated in code at test time.

One sample chapter (SAMPLE) is written out as a PDF, a Word file and a
Markdown file. Because it's the same content, every format must convert to
the same outline: that's the cross-format black-box test. The PDF writer
places each line itself, so tests control exactly where lines break,
pages turn and running heads appear.

The text is test data about nothing in particular; it never ships on the site.
"""

from __future__ import annotations

import io
from pathlib import Path

TITLE = "Sample rhythms"

# Each paragraph is a list of visual lines, as a PDF would lay them out.
# The first paragraph splits "circadian" across a line ("circa-" / "dian")
# and keeps the real hyphen in "self-sustained".
PARA_1 = [
    "A rhythm is self-sustained when it keeps running without any outside cue. The",
    "circa-",
    "dian clock is the best known example, with a period close to one day.",
]
PARA_1_TEXT = (
    "A rhythm is self-sustained when it keeps running without any outside cue. "
    "The circadian clock is the best known example, with a period close to one day."
)
PARA_2 = ["Periods are measured from peak to peak, or between any two matching phases."]
BULLETS = ["Find two matching phases.", "Measure the time between them.", "Repeat over many cycles."]
CAPTION = "A square wave with a period of one day."
TABLE = [["Rhythm", "Period", "Example"], ["Ultradian", "Under a day", "Breathing"], ["Infradian", "Over a day", "Migration"]]
TABLE_CAPTION = "Periods of common rhythms."
STEPS = ["Record for several days.", "Plot the data."]
# Spans across a page break in the PDF.
PARA_3_LINES = [
    "This paragraph starts at the bottom of one page and",
    "continues at the top of the next one without a break.",
]
PARA_3_TEXT = "This paragraph starts at the bottom of one page and continues at the top of the next one without a break."
LINK_URL = "https://example.org/rhythms"
FORMATTED = ("A ", ("bold", "strong"), " claim, an ", ("italic", "em"), " aside and a ", ("link", "link"), ".")

SECTIONS = ["Measuring a period", "Figures and tables", "Summary"]


def png(width: int = 120, height: int = 60) -> bytes:
    """A small square-wave picture as PNG bytes."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for x in range(0, width, 40):
        draw.rectangle([x, 10, x + 19, height - 10], fill="black")
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


# ---- PDF ---------------------------------------------------------------------


class _Writer:
    """Places lines on an fpdf2 page with a fixed pitch."""

    def __init__(self, pdf, header: str | None):
        self.pdf = pdf
        self.header = header
        self.y = 0.0
        self.page_number = 0
        self.new_page()

    def new_page(self):
        pdf = self.pdf
        pdf.add_page()
        self.page_number += 1
        if self.header:
            pdf.set_font("helvetica", "", 8)
            pdf.text(20, 12, self.header)
            pdf.text(100, 287, str(self.page_number))
        self.y = 30

    def line(self, text: str, size: float = 11, style: str = "", x: float = 20, link: str | None = None):
        pdf = self.pdf
        pdf.set_font("helvetica", style, size)
        pdf.set_xy(x, self.y)
        pdf.cell(text=text, link=link or "")
        self.y += size * 0.5

    def gap(self, amount: float = 4):
        self.y += amount


def sample_pdf(path: Path, *, header: str | None = "Sample rhythms - class draft", title: bool = True) -> Path:
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"  # has the bullet character
    pdf.set_auto_page_break(False)
    w = _Writer(pdf, header)
    if title:
        w.line(TITLE, size=24, style="B")
        w.gap(6)
    w.line(SECTIONS[0], size=16, style="B")
    w.gap(2)
    for text in PARA_1:
        w.line(text)
    w.gap(3)
    for text in PARA_2:
        w.line(text)
    w.gap(3)
    for text in BULLETS:
        w.line(f"• {text}")
    w.gap(3)
    w.line(SECTIONS[1], size=16, style="B")
    w.gap(2)
    image_top = w.y
    pdf.image(io.BytesIO(png()), x=20, y=image_top, w=60, h=30)
    w.y = image_top + 33
    w.line(f"Figure 1. {CAPTION}", size=9)
    w.gap(4)
    w.line(f"Table 1. {TABLE_CAPTION}", size=9)
    w.gap(1)
    pdf.set_font("helvetica", "", 10)
    pdf.set_xy(20, w.y)
    with pdf.table(width=150, col_widths=(50, 50, 50), text_align="LEFT") as table:
        for row in TABLE:
            cells = table.row()
            for cell in row:
                cells.cell(cell)
    w.y = pdf.get_y() + 6
    w.line(SECTIONS[2], size=16, style="B")
    w.gap(2)
    for n, text in enumerate(STEPS, 1):
        w.line(f"{n}. {text}")
    w.gap(3)
    # A line with bold, italic and a link, built from pieces.
    pdf.set_xy(20, w.y)
    for part in FORMATTED:
        if isinstance(part, str):
            pdf.set_font("helvetica", "", 11)
            pdf.write(5, part)
        else:
            word, kind = part
            style = {"strong": "B", "em": "I", "link": ""}[kind]
            pdf.set_font("helvetica", style, 11)
            pdf.write(5, word, link=LINK_URL if kind == "link" else "")
    w.y += 5.5
    w.gap(3)
    # Push the next paragraph to the bottom of the page so it breaks across pages.
    w.y = 270
    w.line(PARA_3_LINES[0])
    w.new_page()
    w.line(PARA_3_LINES[1])
    pdf.output(str(path))
    return path


def scanned_pdf(path: Path) -> Path:
    """Two pages that are only pictures: what a scanner produces."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"  # has the bullet character
    for _ in range(2):
        pdf.add_page()
        pdf.image(io.BytesIO(png(400, 560)), x=0, y=0, w=210, h=297)
    pdf.output(str(path))
    return path


def two_column_pdf(path: Path) -> Path:
    """One page, two columns: left column must be read before the right one."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"  # has the bullet character
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.text(20, 20, "Two columns")
    pdf.set_font("helvetica", "", 10)
    left = [f"Left column line {n} of the first paragraph" for n in range(1, 9)]
    left[-1] += "."  # ends a sentence, so the right column starts a new paragraph
    right = [f"Right column line {n} of the next part" for n in range(1, 9)]
    for n, text in enumerate(left):
        pdf.text(15, 35 + n * 5, text)
    for n, text in enumerate(right):
        pdf.text(112, 35 + n * 5, text)
    pdf.output(str(path))
    return path


def vector_figure_pdf(path: Path) -> Path:
    """A figure drawn with lines (like a matplotlib PDF export), not an image."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"  # has the bullet character
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.text(20, 20, "Drawn figure")
    pdf.set_font("helvetica", "", 11)
    pdf.text(20, 30, "The figure below is drawn with vector paths.")
    pdf.set_line_width(0.6)
    for x in range(20, 120, 20):
        pdf.line(x, 70, x, 50)
        pdf.line(x, 50, x + 10, 50)
        pdf.line(x + 10, 50, x + 10, 70)
        pdf.line(x + 10, 70, x + 20, 70)
    pdf.set_font("helvetica", "", 9)
    pdf.text(20, 80, "Figure 2. A square wave drawn as paths.")
    pdf.output(str(path))
    return path


def book_pdf(path: Path) -> Path:
    """Two chapters in one PDF, one per page, for page-range and heading selection."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"  # has the bullet character
    for n, (title, body) in enumerate(
        [("First chapter", "Text that belongs to the first chapter."),
         ("Second chapter", "Text that belongs to the second chapter.")], 1):
        pdf.add_page()
        pdf.set_font("helvetica", "B", 20)
        pdf.text(20, 25, f"Chapter {n}: {title}")
        pdf.set_font("helvetica", "B", 14)
        pdf.text(20, 40, "Opening")
        pdf.set_font("helvetica", "", 11)
        pdf.text(20, 50, body)
        pdf.set_font("helvetica", "B", 14)
        pdf.text(20, 65, "Closing")
        pdf.set_font("helvetica", "", 11)
        pdf.text(20, 75, f"The end of chapter {n}.")
    pdf.output(str(path))
    return path


# ---- Word --------------------------------------------------------------------


def _add_hyperlink(paragraph, text: str, url: str):
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    rid = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def sample_docx(path: Path, *, alt: str | None = "Black bars on white, evenly spaced") -> Path:
    import docx

    d = docx.Document()
    d.add_heading(TITLE, level=0)  # "Title" style
    d.add_heading(SECTIONS[0], level=1)
    d.add_paragraph(PARA_1_TEXT)
    d.add_paragraph(" ".join(PARA_2))
    for text in BULLETS:
        d.add_paragraph(text, style="List Bullet")
    d.add_heading(SECTIONS[1], level=1)
    d.add_picture(io.BytesIO(png()))
    if alt is not None:
        doc_pr = d.inline_shapes[0]._inline.docPr
        doc_pr.set("descr", alt)
    d.add_paragraph(f"Figure 1. {CAPTION}", style="Caption")
    table = d.add_table(rows=len(TABLE), cols=3)
    for r, row in enumerate(TABLE):
        for c, cell in enumerate(row):
            table.cell(r, c).text = cell
    d.add_paragraph(f"Table 1. {TABLE_CAPTION}", style="Caption")
    d.add_heading(SECTIONS[2], level=1)
    for text in STEPS:
        d.add_paragraph(text, style="List Number")
    p = d.add_paragraph()
    for part in FORMATTED:
        if isinstance(part, str):
            p.add_run(part)
        else:
            word, kind = part
            if kind == "link":
                _add_hyperlink(p, word, LINK_URL)
            else:
                run = p.add_run(word)
                run.bold = kind == "strong"
                run.italic = kind == "em"
    d.add_paragraph(PARA_3_TEXT)
    d.save(str(path))
    return path


# ---- Markdown ----------------------------------------------------------------


def sample_markdown(path: Path) -> Path:
    image = path.with_name("sample-figure.png")
    image.write_bytes(png())
    bullets = "\n".join(f"- {t}" for t in BULLETS)
    steps = "\n".join(f"{n}. {t}" for n, t in enumerate(STEPS, 1))
    header = "| " + " | ".join(TABLE[0]) + " |\n|" + "---|" * 3
    rows = "\n".join("| " + " | ".join(r) + " |" for r in TABLE[1:])
    formatted = "".join(
        p if isinstance(p, str) else {"strong": f"**{p[0]}**", "em": f"*{p[0]}*", "link": f"[{p[0]}]({LINK_URL})"}[p[1]]
        for p in FORMATTED
    )
    path.write_text(
        f"""# {TITLE}

## {SECTIONS[0]}

{PARA_1_TEXT}

{" ".join(PARA_2)}

{bullets}

## {SECTIONS[1]}

![Black bars on white, evenly spaced]({image.name} "Figure 1. {CAPTION}")

{header}
{rows}

Table 1. {TABLE_CAPTION}

## {SECTIONS[2]}

{steps}

{formatted}

{PARA_3_TEXT}
""",
        encoding="utf-8",
    )
    return path


WRITERS = {"pdf": sample_pdf, "docx": sample_docx, "md": sample_markdown}


# ---- A PDF with the quirks real books have -------------------------------------
# Each quirk below was found converting real PDFs (a LibreOffice book, XeTeX and
# Google Docs exports). Real files can't be committed, so this rebuilds them.

REAL_WORLD_OUTLINE = [
    ("list", False, ("Bullet one", "Bullet two")),
    ("p", "Imagine a maze and we are able to stand in the middle of it."),
    ("figure", "Figure 1", "A picture of a maze."),
    ("list", True, ("First item that wraps onto a second line without any indent.",
                    "Second item that wraps under its words and keeps going here.",
                    "Third item that wraps as well and also keeps going here.")),
    ("h", 2, "2 Second section"),
    ("p", "Files live in /usr/bin on most systems."),
    ("code", "$ ls\nDesktop Music"),
    ("table", "Table 1", "Shortcuts", (("Shortcut", "Result"), ("cd", "Go home."),
                                       ("cd -", "Go back to the previous directory."))),
    ("p", "The end."),
]


def real_world_pdf(path: Path) -> Path:
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.core_fonts_encoding = "windows-1252"

    def page(number: int, head: str | None):
        pdf.add_page()
        left = 30 if number % 2 == 0 else 20  # left and right pages differ
        pdf.set_font("helvetica", "", 9)
        # Running heads sit below the top 8% (y = 28mm of 297); the folio
        # sits above the bottom 8%. Even pages: "<number>  <book title>".
        # Page 3: just a small copy of a heading, with no number.
        if head:
            pdf.text(left, 28, head)
        pdf.text(100, 266, str(number))
        return left

    def text(x, y, s, size=11, style="", family="helvetica"):
        pdf.set_font(family, style, size)
        pdf.text(x, y, s)

    left = page(1, None)
    text(left, 45, "Real world", size=18, style="B")
    # A bullet glyph drawn as its own text, a little lower than its words.
    for n, item in enumerate(["Bullet one", "Bullet two"]):
        text(left, 57.4 + n * 6, "-")
        text(left + 6, 57 + n * 6, item)
    # A figure placed in the middle of a sentence.
    text(left, 75, "Imagine a maze and we are able to")
    pdf.image(io.BytesIO(png(200, 100)), x=left, y=79, w=60, h=30)
    text(left, 115, "Figure 1: A picture of a maze.", size=9)
    text(left, 122, "stand in the middle of it.")
    # A numbered item whose wrapped line starts back at the marker.
    text(left, 134, "1. First item that wraps onto a second line")
    text(left, 140, "without any indent.")

    # The list goes on over the page, where most lines hang under the
    # item's words, so this page's text edge looks further right.
    left = page(2, "2   Real world")
    y = 45
    for n, first, rest in [(2, "Second item that wraps under its words", ["and keeps", "going here."]),
                           (3, "Third item that wraps as well", ["and also keeps", "going here."])]:
        text(left, y, f"{n}. {first}")
        for line in rest:
            y += 6
            text(left + 6, y, line)
        y += 6

    left = page(3, "Second section")
    # Section number and title written as separate texts on one baseline.
    text(left, 45, "2", size=16, style="B")
    text(left + 9, 45, "Second section", size=16, style="B")
    text(left, 57, "Files live in /usr/")
    text(left, 63, "bin on most systems.")
    text(left, 75, "$ ls", size=10, family="courier")  # code that runs over the page

    left = page(4, "4   Real world")
    text(left, 45, "Desktop Music", size=10, family="courier")
    # A table drawn without borders, with a wrapped cell.
    text(left, 60, "Table 1: Shortcuts", size=9)
    for n, (a, b) in enumerate([("Shortcut", "Result"), ("cd", "Go home."), ("cd -", "Go back to the previous")]):
        text(left, 68 + n * 6, a, style="B" if n == 0 else "")
        text(left + 40, 68 + n * 6, b, style="B" if n == 0 else "")
    text(left + 40, 86, "directory.")
    text(left, 100, "The end.")
    pdf.output(str(path))
    return path


def grid_paper_pdf(path: Path) -> Path:
    """Notes written on graph paper (like iPad handwriting exports): hundreds
    of ruling lines that are a background, not a table."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.add_page()
    pdf.set_draw_color(200, 220, 240)
    pdf.set_line_width(0.1)
    for x in range(0, 211):  # 1mm squares: about 500 ruling lines, like a real export
        pdf.line(x, 0, x, 297)
    for y in range(0, 298):
        pdf.line(0, y, 210, y)
    pdf.set_font("helvetica", "B", 16)
    pdf.text(20, 30, "Lecture notes")
    pdf.set_font("helvetica", "", 11)
    pdf.text(20, 45, "Check the syllabus and the grading policy.")
    pdf.text(20, 60, "Homework is due every Friday.")
    pdf.output(str(path))
    return path


# ---- A whole book compiled from several authors --------------------------------
# Rebuilds what a real class textbook (one Google Doc per author, merged) looked
# like: a contents page, chapters marked in different ways and set in different
# fonts, double spacing with one line per text block, captions above and below
# figures, and a chapter that isn't in the book yet.

COMPILED_CHAPTERS = [
    {"id": "first-topic", "title": "First topic", "unit": "first", "authors": ["ada"]},
    {"id": "second-topic", "title": "Second topic", "unit": "first", "authors": ["ben"]},
    {"id": "third-topic", "title": "Third topic", "unit": "second", "authors": ["cy"]},
    {"id": "fourth-topic", "title": "Fourth topic", "unit": "second", "authors": ["cy"]},
]


def compiled_book_pdf(path: Path) -> Path:
    from fpdf import FPDF

    pdf = FPDF(format="Letter", unit="pt")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_auto_page_break(False)

    def text(x, y, s, family="helvetica", style="", size=11):
        pdf.set_font(family, style, size)
        pdf.text(x, y, s)

    # Contents page: every chapter named, as bullets and as plain lines.
    pdf.add_page()
    text(72, 72, "Contents", style="B", size=16)
    for n, title in enumerate(["First topic", "Second topic", "Third topic", "Fourth topic"]):
        text(72, 110 + n * 20, f"• {title.upper()}")
        text(300, 110 + n * 20, title, style="B")

    # Chapter 1, by one author: Helvetica 11 labels, Times 12 body, double spaced.
    pdf.add_page()
    text(72, 72, "Chapter X: First topic", style="B")
    lines = ["The first paragraph of the first topic runs over three", "double spaced lines and is still one paragraph",
             "until it ends here."]
    for n, line in enumerate(lines):
        text(72, 110 + n * 25, line, family="times", size=12)
    text(72, 200, "A second paragraph follows after a larger gap.", family="times", size=12)
    text(72, 240, "Figure 1: A picture with its caption above it.", size=10)
    pdf.image(io.BytesIO(png()), x=72, y=250, w=200, h=100)
    text(72, 380, "The topic ends after the figure.", family="times", size=12)

    # Chapter 2, by another author: Times 12 bold label, and a heading that
    # mentions the chapter title again.
    pdf.add_page()
    text(72, 72, "Chapter 4: Second topic", family="times", style="B", size=12)
    text(72, 110, "Text that belongs to the second topic.", family="times", size=12)
    pdf.image(io.BytesIO(png()), x=72, y=130, w=200, h=100)
    text(72, 250, "A bold title for the figure", style="B")
    text(72, 268, "Figure 2. A caption below the figure and its title.", size=10)
    text(72, 310, "Second topic in practice", family="times", style="B", size=14)
    text(72, 340, "More text about the second topic.", family="times", size=12)

    # Chapter 3 shares its page with the end of chapter 2.
    text(72, 420, "UNIT AND CHAPTER: Third topic", style="B")
    text(72, 450, "Text that belongs to the third topic.")
    pdf.output(str(path))
    return path


def caption_quirks_pdf(path: Path) -> Path:
    """Captions as real books place them: a bulleted caption below an image, a
    caption at the foot of a page whose figure starts the next page, a table
    captioned as a figure, and a sentence that only looks like a caption."""
    from fpdf import FPDF

    pdf = FPDF(format="Letter", unit="pt")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_auto_page_break(False)

    def text(x, y, s, size=12, style=""):
        pdf.set_font("helvetica", style, size)
        pdf.text(x, y, s)

    pdf.add_page()
    text(72, 72, "Captions", size=18, style="B")
    pdf.image(io.BytesIO(png()), x=72, y=90, w=200, h=100)
    text(72, 210, "• Figure 1: A bulleted caption below its figure.")
    text(72, 250, "This sentence ends a paragraph, and the next line refers to a")
    text(72, 264, "Figure 1 presents nothing new and is not a caption.")
    text(72, 740, "Figure 2 - A caption at the foot of the page")
    pdf.add_page()
    pdf.image(io.BytesIO(png()), x=72, y=60, w=200, h=100)
    text(72, 200, "Figure 3 - A table the author called a figure")
    pdf.set_font("helvetica", "", 11)
    pdf.set_xy(72, 215)
    with pdf.table(width=300, col_widths=(150, 150), text_align="LEFT") as table:
        for row in (("Heart", "Rate"), ("Young", "Fast"), ("Old", "Slower")):
            cells = table.row()
            for cell in row:
                cells.cell(cell)
    pdf.output(str(path))
    return path


TEMPLATE_CHAPTERS = [
    {"id": "first-topic", "title": "First topic", "unit": "first", "authors": ["ada"]},
    {"id": "second-topic", "title": "Second topic", "unit": "first", "authors": ["ben", "cy"]},
]


def template_book_pdf(path: Path) -> Path:
    """A book written to the class's chapter template: each chapter opens with
    labelled front matter, has its written content (by one or two authors),
    then add-ins, a glossary and references."""
    from fpdf import FPDF

    pdf = FPDF(format="Letter", unit="pt")
    pdf.core_fonts_encoding = "windows-1252"
    pdf.set_auto_page_break(False)
    y = [0.0]

    def line(s, size=11, style=""):
        pdf.set_font("helvetica", style, size)
        pdf.text(72, y[0], s)
        y[0] += size * 1.9 + (12 if style == "B" else 0)  # labels have space after them

    def page():
        pdf.add_page()
        y[0] = 72

    def prose(words):
        for chunk in words:
            line(chunk)
        y[0] += 8

    page()
    line("Chapter 1: First topic", style="B")          # title above the opening block
    line("UNIT AND CHAPTER", style="B")
    line("CONTRIBUTORS", style="B")
    line("• Ada, subject matter expert")
    line("LEARNING OBJECTIVES", style="B")
    line("1. Explain the first topic")
    line("CHAPTER OUTLINE", style="B")
    line("• Section: Background")
    line("CHAPTER WRITTEN CONTENT", style="B")
    line("Background", size=15, style="B")
    prose(["The first topic is written content that readers should see on the site,",
           "and it runs over several lines that join into one paragraph."])
    line("CHAPTER ADD-INS", style="B")
    pdf.image(io.BytesIO(png()), x=72, y=y[0], w=150, h=75)
    y[0] += 90
    line("Figure 1: An add-in figure that is not part of the text", size=9)
    line("GLOSSARY", style="B")
    line("Rhythm: something that repeats")
    line("REFERENCES", style="B")
    line("Ada (2020). A reference.")

    page()
    line("UNIT AND CHAPTER", style="B")
    line("Unit: First unit")
    line("Chapter 2: Second topic", style="B")
    line("CONTRIBUTORS", style="B")
    line("• Ben and Cy")
    line("CHAPTER WRITTEN CONTENT (Ben)", style="B")
    line("Learning Objectives", style="B")
    line("1. Describe the second topic")
    line("Ben's part", size=15, style="B")
    prose(["Ben wrote this part of the second topic, and it belongs on the page",
           "together with the part his coauthor wrote afterwards."])
    line("Works Cited", size=12, style="B")
    line("Ben (2021). A source.")
    line("CHAPTER OUTLINE (Cy)", style="B")
    line("• Cy's plan")
    line("CHAPTER WRITTEN CONTENT (Cy)", style="B")
    line("Cy's part", size=15, style="B")
    prose(["Cy wrote the second part of the second topic, which also belongs on",
           "the page after Ben's part, in the same order as in the book."])
    line("REFERENCES", style="B")
    line("Cy (2022). Another source.")
    pdf.output(str(path))
    return path
