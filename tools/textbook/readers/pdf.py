"""PDF reader.

A PDF has no structure, only positioned text, images and vector drawings.
This reader rebuilds the structure from layout, in passes:

1. extract    lines (with font size, weight, style, links), images and tables
2. clean      drop running heads, page numbers, repeated logos, footnotes
3. order      put each page's items in reading order (handles two columns)
4. classify   decide what each line is: heading, caption, list item, body
5. assemble   join lines into paragraphs and lists, attach captions

Each pass is a plain function over plain data, so the heuristics can be
tested one at a time without a PDF (see tests/textbook/test_pdf_layout.py).
Works for PDFs exported from Word, Google Docs, LaTeX and similar. Scanned
pages (pictures of text) are detected and rejected: they need OCR.
"""

from __future__ import annotations

import hashlib
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..model import (
    Code,
    Document,
    Figure,
    Heading,
    Image,
    Inlines,
    ListBlock,
    ListItem,
    Paragraph,
    Run,
    Table,
    plain_text,
)
from ..normalize import (
    strip_invisible,
    caption_label,
    comparable,
    clean_runs,
    clean_text,
    ends_sentence,
    hyphenated_vocabulary,
    line_joint,
    list_marker,
)
from . import ReaderError

# ---- 1. Extracted items ------------------------------------------------------

BOLD_FONT = re.compile(r"bold|black|heavy|semibold|demi", re.I)
ITALIC_FONT = re.compile(r"italic|oblique", re.I)
MONO_FONT = re.compile(r"mono|courier|code|consol", re.I)
MATH_FONT = re.compile(r"^(cmmi|cmsy|cmex|msam|msbm|stix.*math|cambria ?math|symbol|mt ?extra)", re.I)


@dataclass
class Span:
    text: str
    size: float
    bold: bool = False
    italic: bool = False
    mono: bool = False
    sup: bool = False
    href: str | None = None
    math: bool = False


@dataclass
class Line:
    spans: list[Span]
    x0: float
    y0: float
    x1: float
    y1: float
    page: int  # 0-based index into the document
    block: int  # PyMuPDF block number on its page
    block_lines: int = 1  # how many lines that block has

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def size(self) -> float:
        """Character-weighted most common font size, rounded to 0.5pt."""
        weights: Counter[float] = Counter()
        for span in self.spans:
            weights[round(span.size * 2) / 2] += len(span.text.strip()) or 0
        if not weights or not sum(weights.values()):
            return round(self.spans[0].size * 2) / 2 if self.spans else 0.0
        return max(weights.items(), key=lambda kv: (kv[1], kv[0]))[0]

    @property
    def bold(self) -> bool:
        visible = [s for s in self.spans if s.text.strip()]
        return bool(visible) and all(s.bold for s in visible)


@dataclass
class ImageItem:
    data: bytes
    ext: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    digest: str = ""


@dataclass
class TableItem:
    rows: list[list[str]]
    x0: float
    y0: float
    x1: float
    y1: float
    page: int


@dataclass
class PageInfo:
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    images: list[ImageItem] = field(default_factory=list)
    tables: list[TableItem] = field(default_factory=list)
    drawings: list[tuple[float, float, float, float]] = field(default_factory=list)
    doc: object = None  # the open PyMuPDF document, for rasterizing figures
    grid_paper: bool = False  # drawn as dense ruling (graph or lined paper)


GRID_DRAWINGS = 400  # more ruling lines than any real table on one page


def is_real_table(rows: list[list[str]]) -> bool:
    """A grid with text in most of its cells. Ruled backgrounds, form boxes
    and page borders also look like grids to the table finder, but they are
    mostly empty."""
    filled_rows = [row for row in rows if any(row)]
    if len(filled_rows) < 2 or max(len(r) for r in filled_rows) < 2:
        return False
    cells = [cell for row in rows for cell in row]
    return sum(1 for cell in cells if cell) >= 0.5 * len(cells)


def parse_page_spec(spec: str | None, page_count: int) -> list[int]:
    """'3-7,10' (1-based, inclusive) -> [2, 3, 4, 5, 6, 9]."""
    if not spec:
        return list(range(page_count))
    pages: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", part)
        if not m:
            raise ReaderError(f'Page range "{spec}" is not valid. Write it like "12-30" or "3-7,10".')
        start = int(m.group(1))
        end = int(m.group(2) or start)
        if start < 1 or end < start or end > page_count:
            raise ReaderError(
                f'Page range "{part}" is outside this PDF, which has {page_count} pages.'
            )
        pages.extend(range(start - 1, end))
    return pages


def _inside(x: float, y: float, box) -> bool:
    return box[0] - 1 <= x <= box[2] + 1 and box[1] - 1 <= y <= box[3] + 1


# Where a chapter starts and ends inside a whole-book PDF: content on the
# start page above start_y, and on the end page from end_y down, belongs to
# the neighbouring chapters. (start page, start y, end page or None, end y)
Clip = tuple[int, float, "int | None", float]


def clip_page(info: PageInfo, index: int, clip: Clip | None) -> None:
    if clip is None:
        return
    start_page, start_y, end_page, end_y = clip

    def keep(item) -> bool:
        if index == start_page and item.y0 < start_y:
            return False
        return not (index == end_page and item.y0 >= end_y)

    info.lines = [l for l in info.lines if keep(l)]
    info.images = [i for i in info.images if keep(i)]
    info.tables = [t for t in info.tables if keep(t)]


def extract(path: Path, pages: str | None = None, clip: Clip | None = None) -> tuple[list[PageInfo], list[int]]:
    import pymupdf  # imported here so the rest of the package loads without it

    pymupdf.no_recommend_layout()
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # corrupt file, wrong type, encrypted
        raise ReaderError(f"{path.name} could not be opened as a PDF ({exc}).") from exc
    if doc.needs_pass:
        raise ReaderError(f"{path.name} is password-protected. Export an unprotected copy.")
    indices = parse_page_spec(pages, doc.page_count)
    out: list[PageInfo] = []
    for index in indices:
        page = doc[index]
        info = PageInfo(page.rect.width, page.rect.height)
        links = [
            (link["from"], link["uri"])
            for link in page.get_links()
            if link.get("uri")
        ]
        drawings = page.get_cdrawings()  # C speed; same rectangles as get_drawings()
        tables = []
        if len(drawings) > GRID_DRAWINGS:
            # Graph or lined paper (handwritten notes): the ruling is not a table.
            info.grid_paper = True
        else:
            try:
                tables = page.find_tables().tables
            except Exception:  # table finder is best-effort
                tables = []
        table_boxes = []
        for table in tables:
            rows = [[clean_text(cell or "").strip() for cell in row] for row in table.extract()]
            if not is_real_table(rows):
                continue
            rows = [row for row in rows if any(row)]
            x0, y0, x1, y1 = table.bbox
            info.tables.append(TableItem(rows, x0, y0, x1, y1, index))
            table_boxes.append(table.bbox)

        raw = page.get_text("rawdict")
        for bno, block in enumerate(raw["blocks"]):
            if block["type"] == 1:
                x0, y0, x1, y1 = block["bbox"]
                if (x1 - x0) < 36 or (y1 - y0) < 36:
                    continue  # bullets, rules, tiny icons
                data, ext = _normalize_image(block["image"], block.get("ext", "png"), block.get("mask"))
                if data:
                    info.images.append(
                        ImageItem(data, ext, x0, y0, x1, y1, index, hashlib.sha1(data).hexdigest())
                    )
                continue
            lines = [l for l in block["lines"] if abs(l["dir"][1]) < 0.01 and l["dir"][0] > 0]
            for line in lines:
                spans = []
                for s in line["spans"]:
                    font = s.get("font", "")
                    flags = s.get("flags", 0)
                    style = dict(
                        size=s["size"],
                        bold=bool(flags & 16) or bool(BOLD_FONT.search(font)),
                        italic=bool(flags & 2) or bool(ITALIC_FONT.search(font)),
                        mono=bool(flags & 8) or bool(MONO_FONT.search(font)),
                        sup=bool(flags & 1),
                        math=bool(MATH_FONT.match(font.split("+")[-1])),
                    )
                    # Split the span where a link starts or ends: a link often
                    # covers only some words of a span.
                    for text, href in _split_by_links(s["chars"], links):
                        # Drop invisible characters now (Google Docs puts a zero-width
                        # space after every bullet), so markers and words are seen as they look.
                        text = strip_invisible(text)
                        if text:
                            spans.append(Span(text=text, href=href, **style))
                if not "".join(s.text for s in spans).strip():
                    continue
                x0, y0, x1, y1 = line["bbox"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                if any(_inside(cx, cy, box) for box in table_boxes):
                    continue
                info.lines.append(Line(spans, x0, y0, x1, y1, index, bno, len(lines)))
        info.doc = doc
        info.drawings = [tuple(d["rect"]) for d in drawings if d.get("rect")]
        clip_page(info, index, clip)
        out.append(info)
    return out, indices


def _split_by_links(chars, links) -> list[tuple[str, str | None]]:
    pieces: list[tuple[str, str | None]] = []
    for ch in chars:
        x0, y0, x1, y1 = ch["bbox"]
        href = next((uri for rect, uri in links if _inside((x0 + x1) / 2, (y0 + y1) / 2, rect)), None)
        if pieces and pieces[-1][1] == href:
            pieces[-1] = (pieces[-1][0] + ch["c"], href)
        else:
            pieces.append((ch["c"], href))
    return [(t, h) for t, h in pieces if t]


def _normalize_image(data: bytes, ext: str, mask: bytes | None = None) -> tuple[bytes, str]:
    """PNG or JPEG, with any transparency mask flattened onto white."""
    from ..images import flatten

    ext = ext.lower()
    if ext not in ("png", "jpg", "jpeg"):
        import pymupdf

        try:
            pix = pymupdf.Pixmap(data)
            if pix.colorspace and pix.colorspace.n > 3:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            data, ext = pix.tobytes("png"), "png"
        except Exception:
            return b"", ""
    return flatten(data, ext, mask)


def rasterize(info: PageInfo, page_index: int, box: tuple[float, float, float, float]) -> bytes:
    import pymupdf

    pix = info.doc[page_index].get_pixmap(clip=pymupdf.Rect(*box), dpi=150, alpha=False)
    return pix.tobytes("png")


# ---- 2. Clean-up -------------------------------------------------------------

PAGE_NUMBER = re.compile(r"^\s*(page\s*)?(\d{1,4}|[ivxlc]{1,7})(\s*(of|/)\s*\d{1,4})?\s*$", re.I)
MARGIN = 0.08  # top and bottom share of the page that always counts as margin
EDGE = 0.13    # running heads sit in the first or last line within this share
NUMBERED_HEAD = re.compile(r"^\s*(\d{1,4})\s+\S.{0,90}$|^.{0,90}\S\s+(\d{1,4})\s*$")


def margin_key(text: str) -> str:
    return re.sub(r"\d+", "#", clean_text(text).strip().casefold())


def in_margin(line: Line, info: PageInfo) -> bool:
    return line.y1 <= info.height * MARGIN or line.y0 >= info.height * (1 - MARGIN)


def edge_lines(info: PageInfo) -> list[Line]:
    """The top row and bottom row of text on a page, if they sit near an edge."""
    if not info.lines:
        return []
    top = min(l.y0 for l in info.lines)
    bottom = max(l.y1 for l in info.lines)
    edges = [l for l in info.lines if in_margin(l, info)]
    if top <= info.height * EDGE:
        edges += [l for l in info.lines if l.y0 <= top + 2]
    if bottom >= info.height * (1 - EDGE):
        edges += [l for l in info.lines if l.y1 >= bottom - 2]
    unique = {id(l): l for l in edges}
    return list(unique.values())


def _short(text: str) -> bool:
    return len(text.split()) <= 12


def remove_running_heads(pages: list[PageInfo]) -> None:
    """Drop page numbers, headers and footers.

    A line in the top or bottom row of a page is a running head when it is:
    a bare page number; text repeated on many pages; a short line whose
    number rises with the page (\"7  2 \u2013 Navigation\", \"8  Listing...\");
    or a small copy of a heading that appears elsewhere in the source.
    """
    edges = {info_index: edge_lines(info) for info_index, info in enumerate(pages)}
    edge_ids = {id(l) for lines in edges.values() for l in lines}

    counts: Counter[str] = Counter()
    for lines in edges.values():
        counts.update({margin_key(l.text) for l in lines})
    threshold = max(2, round(len(pages) * 0.25))

    offsets: Counter[int] = Counter()
    for index, lines in edges.items():
        for l in lines:
            m = NUMBERED_HEAD.match(l.text) if _short(l.text) else None
            if m:
                offsets[int(m.group(1) or m.group(2)) - index] += 1
    page_offset = next((off for off, n in offsets.most_common(1) if n >= 2), None)

    body = body_size(pages)
    headings = {
        comparable(l.text)
        for info in pages
        for l in info.lines
        if id(l) not in edge_ids and (l.size >= body * HEADING_RATIO or l.bold) and _short(l.text)
    }

    def running(l: Line, index: int) -> bool:
        if PAGE_NUMBER.match(l.text):
            return True
        repeated = len(pages) >= 2 and counts[margin_key(l.text)] >= threshold
        if repeated and _short(l.text) and re.search(r"[^\W_]", l.text):
            return True
        m = NUMBERED_HEAD.match(l.text) if _short(l.text) else None
        if m and page_offset is not None and int(m.group(1) or m.group(2)) - index == page_offset:
            return True
        return l.size < body * HEADING_RATIO and not l.bold and comparable(l.text) in headings

    for index, info in enumerate(pages):
        drop = {id(l) for l in edges[index] if running(l, index)}
        info.lines = [l for l in info.lines if id(l) not in drop]


def remove_repeated_images(pages: list[PageInfo]) -> None:
    """Logos and decorations repeat on many pages; figures don't."""
    seen: Counter[str] = Counter()
    for info in pages:
        seen.update({img.digest for img in info.images})
    for info in pages:
        info.images = [img for img in info.images if seen[img.digest] < 3]


def check_scanned(pages: list[PageInfo], indices: list[int], name: str) -> list[str]:
    scanned = []
    for info, index in zip(pages, indices):
        if info.lines:
            continue
        covered = sum((i.x1 - i.x0) * (i.y1 - i.y0) for i in info.images)
        if covered > 0.5 * info.width * info.height:
            scanned.append(index + 1)
    if scanned and len(scanned) >= max(1, len(pages) / 2):
        raise ReaderError(
            f"{name} looks like a scan: pages {_ranges(scanned)} are pictures of text, "
            "with no text the converter can read. Export the chapter from the program it "
            "was written in (Word, Google Docs, LaTeX), or run OCR on the PDF first."
        )
    return [
        f"page {p}: is a picture with no text in it (a scan or a photo of notes); it is kept as a figure, "
        "so describe it in the chapter's figures alt text, or run OCR on it if it should be text"
        for p in scanned
    ]


def _ranges(numbers: list[int]) -> str:
    out, start, prev = [], None, None
    for n in numbers + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    return ", ".join(out)


# A fragment that only holds a list marker or a section number. Some
# exporters (Google Docs, XeTeX) write it as separate text from the words
# after it on the same line: "-" | "Issues with RNNs", "2" | "Convergence".
FRAGMENT = re.compile(
    r"^\s*(\(?[0-9A-Za-z]{1,3}\)?(\.[0-9]{1,3})*[.)]?|[\u2022\u25e6\u25aa\u25cf\u2023\u2043\u2219\u00b7\u2013\u2014*\-\u25cb\u25a0\u25a1\u27a2\u27a4\u25ba\u2713])\s*$"
)


def merge_fragments(info: PageInfo) -> None:
    """Rejoin a marker or number fragment with the text that follows it on its line."""
    lines = sorted(info.lines, key=lambda l: (l.y0, l.x0))
    used: set[int] = set()
    merged: list[Line] = []
    for i, left in enumerate(lines):
        if i in used:
            continue
        if FRAGMENT.match(left.text):
            height = max(left.y1 - left.y0, 1)
            # The words may sort before the marker (a bullet drawn a little
            # lower than its text), so look at the whole row, nearest first.
            candidates = [
                (right.x0 - left.x1, j)
                for j, right in enumerate(lines)
                if j != i
                and j not in used
                and abs((right.y0 + right.y1) / 2 - (left.y0 + left.y1) / 2) < height * 0.6
                and 0 <= right.x0 - left.x1 < left.size * 5
                and not FRAGMENT.match(right.text)
            ]
            partner = min(candidates)[1] if candidates else None
            if partner is not None:
                right = lines[partner]
                used.add(partner)
                first = right.spans[0]
                joint = Span(" ", first.size, bold=first.bold, italic=first.italic)
                left = Line(left.spans + [joint] + right.spans, left.x0, min(left.y0, right.y0),
                            right.x1, max(left.y1, right.y1), left.page, right.block, right.block_lines)
        merged.append(left)
    info.lines = [l for k, l in enumerate(merged) if not _consumed(l, lines, used)]


def _consumed(line: Line, lines: list[Line], used: set[int]) -> bool:
    return any(line is lines[j] for j in used)


# A table-of-contents entry: text, a run of dot leaders, a page number.
TOC_ENTRY = re.compile(r"(\.\s?){4,}\s*([0-9]{1,4}|[ivxlc]{1,7})\s*$", re.I)
TOC_HEADING = re.compile(r"^\s*(table of )?contents\s*$", re.I)


def remove_contents_pages(pages: list[PageInfo]) -> list[int]:
    """Drop the source's own table of contents; the site builds its own."""
    dropped = []
    for info in pages:
        entries = [l for l in info.lines if TOC_ENTRY.search(l.text)]
        if len(entries) < 3:
            continue
        dropped.append(entries[0].page + 1)
        info.lines = [l for l in info.lines if not (TOC_ENTRY.search(l.text) or TOC_HEADING.match(l.text))]
    return dropped


def _rows(lines: list[Line]) -> list[list[Line]]:
    """Group lines that share a baseline into rows, top to bottom."""
    rows: list[list[Line]] = []
    for line in sorted(lines, key=lambda l: (l.y0, l.x0)):
        if rows:
            first = rows[-1][0]
            if abs((line.y0 + line.y1) / 2 - (first.y0 + first.y1) / 2) < max(first.y1 - first.y0, 1) * 0.6:
                rows[-1].append(line)
                continue
        rows.append([line])
    return [sorted(r, key=lambda l: l.x0) for r in rows]


def find_text_tables(info: PageInfo) -> None:
    """Find tables drawn without ruled borders.

    On a one-column page, ordinary text never has two lines side by side.
    Two or more rows of side-by-side lines, plus wrapped lines that continue
    a cell under its own column, make a table.
    """
    if not info.lines or is_two_column(info.lines, info.width):
        return
    rows = _rows(info.lines)
    i = 0
    while i < len(rows):
        if len(rows[i]) < 2:
            i += 1
            continue
        region = [rows[i]]
        starts = [l.x0 for l in rows[i]]
        j = i + 1
        while j < len(rows):
            row = rows[j]
            height = max(row[0].y1 - row[0].y0, 1)
            near = row[0].y0 - region[-1][-1].y1 < height * 2.2
            continues_cell = (
                len(row) == 1 and any(abs(row[0].x0 - x) < 6 for x in starts[1:]) and near
            )
            if (len(row) >= 2 and near) or continues_cell:
                region.append(row)
                if len(row) >= 2:
                    starts = sorted(set(starts) | {l.x0 for l in row})
                j += 1
            else:
                break
        has_math = any(s.math for r in region for l in r for s in l.spans)
        if sum(1 for r in region if len(r) >= 2) >= 2 and not has_math:
            columns = _cluster([l.x0 for r in region if len(r) >= 2 for l in r])
            table: list[list[str]] = []
            for row in region:
                cells_here = [(_column(l.x0, columns), clean_text(l.text).strip()) for l in row]
                if len(row) >= 2 or cells_here[0][0] == 0 or not table:
                    table.append([""] * len(columns))
                for col, text in cells_here:
                    cell = table[-1][col]
                    table[-1][col] = join_text(cell, text) if cell else text
            cells = [c for row in table for c in row]
            if len(columns) > 6 or sum(1 for c in cells if not c) > len(cells) / 2:
                i = j
                continue  # mostly empty: scattered text, not a table
            used = {id(l) for r in region for l in r}
            x0 = min(l.x0 for r in region for l in r)
            x1 = max(l.x1 for r in region for l in r)
            info.tables.append(TableItem(table, x0, region[0][0].y0, x1, region[-1][-1].y1, region[0][0].page))
            info.lines = [l for l in info.lines if id(l) not in used]
        i = j


def _cluster(xs: list[float], tolerance: float = 6) -> list[float]:
    columns: list[float] = []
    for x in sorted(xs):
        if not columns or x - columns[-1] > tolerance:
            columns.append(x)
    return columns


def _column(x: float, columns: list[float]) -> int:
    return max(i for i, c in enumerate(columns) if c <= x + 6) if x + 6 >= columns[0] else 0


def join_text(a: str, b: str) -> str:
    drop, sep = line_joint(a, b, frozenset())
    a = a.rstrip()
    return (a[: len(a) - drop] if drop else a) + sep + b.lstrip()


def body_size(pages: list[PageInfo]) -> float:
    weights: Counter[float] = Counter()
    for info in pages:
        for line in info.lines:
            weights[line.size] += len(line.text.strip())
    if not weights:
        return 10.0
    return max(weights.items(), key=lambda kv: (kv[1], -kv[0]))[0]


FOOTNOTE_START = re.compile(r"^\s*(\d{1,3}|[*†‡§])\s?\S")


def split_footnotes(pages: list[PageInfo], body: float) -> list[list[Line]]:
    """Small text at the foot of a page that starts with a marker is a footnote."""
    notes: list[list[Line]] = []
    for info in pages:
        cut = None
        ordered = sorted(info.lines, key=lambda l: (l.y0, l.x0))
        for i, line in enumerate(ordered):
            if line.y0 < info.height * 0.6 or line.size > body * 0.88:
                continue
            if FOOTNOTE_START.match(line.text) and all(l.size <= body * 0.88 for l in ordered[i:]):
                cut = i
                break
        if cut is None:
            continue
        foot = ordered[cut:]
        info.lines = ordered[:cut]
        current: list[Line] = []
        for line in foot:
            if FOOTNOTE_START.match(line.text) and current:
                notes.append(current)
                current = []
            current.append(line)
        if current:
            notes.append(current)
    return notes


# ---- 3. Reading order --------------------------------------------------------

Item = Line | ImageItem | TableItem


def is_two_column(lines: list[Line], width: float) -> bool:
    if len(lines) < 8:
        return False
    mid, tol = width / 2, width * 0.02
    left = sum(1 for l in lines if l.x1 < mid + tol)
    right = sum(1 for l in lines if l.x0 > mid - tol)
    spanning = len(lines) - left - right
    return spanning / len(lines) < 0.2 and right >= 0.2 * len(lines) and left >= 0.2 * len(lines)


def reading_order(info: PageInfo) -> list[Item]:
    """Order a page's items top to bottom, and left column before right."""
    items: list[Item] = [*info.lines, *info.images, *info.tables]
    if not is_two_column(info.lines, info.width):
        return sorted(items, key=lambda it: (round(it.y0, 1), it.x0))
    mid, tol = info.width / 2, info.width * 0.02

    def column(it) -> int:
        if it.x1 < mid + tol:
            return 0
        if it.x0 > mid - tol:
            return 1
        return -1  # spans both columns: a title, a wide figure

    ordered: list[Item] = []
    band: list[Item] = []
    for it in sorted(items, key=lambda it: (it.y0, it.x0)):
        if column(it) == -1:
            ordered.extend(sorted(band, key=lambda b: (column(b), b.y0, b.x0)))
            band = []
            ordered.append(it)
        else:
            band.append(it)
    ordered.extend(sorted(band, key=lambda b: (column(b), b.y0, b.x0)))
    return ordered


# ---- 4. Classification -------------------------------------------------------

HEADING_RATIO = 1.12


def heading_tiers(lines: list[Line], body: float) -> dict[float, int]:
    """Map each heading font size to a level: biggest size is level 1."""
    sizes = sorted({l.size for l in lines if l.size >= body * HEADING_RATIO and len(l.text) < 200}, reverse=True)
    return {size: i + 1 for i, size in enumerate(sizes[:5])}


def is_bold_heading(line: Line, body: float) -> bool:
    """A short, all-bold line at body size, on its own: a minor heading."""
    text = line.text.strip()
    return (
        line.bold
        and line.block_lines == 1
        and abs(line.size - body) < 1
        and len(text.split()) <= 14
        and not ends_sentence(text)
        and not text.endswith(",")
        and list_marker(text) is None
    )


# A caption's label is followed by a separator ("Figure 3: ...", "Figure 3 - ...",
# "Figure 3.") or ends the line. "Figure 3 shows ..." or "Figure 3). Thus ..." is
# a sentence that happens to start a line.
CAPTION_START = re.compile(
    r"^\s*(figure|fig\.?|table)\s*[A-Z]?\d+(?:[.\-]\d+)*[a-z]?\s*([:.\u2013\u2014]|-\s|$)", re.IGNORECASE
)


def is_caption(line: Line, body: float) -> bool:
    text = _without_bullet(line.text.strip())
    if not caption_label(text):
        return False
    return bool(CAPTION_START.match(text)) or line.size < body * 0.95


def _without_bullet(text: str) -> str:
    """"● Figure 2: ..." -> "Figure 2: ..." (captions written as bullet points)."""
    marker = list_marker(text)
    return text[marker[2]:] if marker and not marker[0] else text


def is_code(line: Line) -> bool:
    """Every visible character is in a monospace font: a line of code or terminal output."""
    visible = [s for s in line.spans if s.text.strip()]
    return bool(visible) and all(s.mono for s in visible)


def classify(line: Line, body: float, tiers: dict[float, int]) -> tuple[str, int]:
    """('heading', level) | ('caption', 0) | ('code', 0) | ('item', 0) | ('body', 0)."""
    text = line.text.strip()
    if is_caption(line, body):
        return "caption", 0
    if line.size in tiers:
        return "heading", tiers[line.size]
    if is_bold_heading(line, body):
        return "heading", len(tiers) + 1
    if is_code(line):
        return "code", 0
    if list_marker(text):
        return "item", 0
    return "body", 0


# ---- 5. Assembly -------------------------------------------------------------


def spans_to_runs(spans: list[Span]) -> Inlines:
    runs = []
    for s in spans:
        marks = set()
        if s.bold:
            marks.add("strong")
        if s.italic:
            marks.add("em")
        if s.mono:
            marks.add("code")
        if s.sup:
            marks.add("sup")
        runs.append(Run(s.text, frozenset(marks), s.href))
    return runs


def join_runs(lines: list[Inlines], vocab: frozenset[str]) -> Inlines:
    """Join the runs of several visual lines into one paragraph."""
    out: Inlines = []
    for runs in lines:
        runs = [r for r in runs if r.text]
        if not runs:
            continue
        if out:
            prev_text = "".join(r.text for r in out)
            drop, sep = line_joint(prev_text, runs[0].text, vocab)
            last = out[-1]
            trimmed = last.text.rstrip()
            if drop:
                trimmed = trimmed[:-drop]
            out[-1] = Run(trimmed, last.marks, last.href)
            if sep:
                shared = last.marks & runs[0].marks
                out.append(Run(sep, last.marks if sep == "-" else shared, last.href if last.href == runs[0].href else None))
            first = runs[0]
            runs = [Run(first.text.lstrip(), first.marks, first.href), *runs[1:]]
        out.extend(runs)
    return clean_runs(out)


def strip_marker(runs: Inlines, length: int) -> Inlines:
    out, remaining = [], length
    for run in runs:
        if remaining <= 0:
            out.append(run)
            continue
        if len(run.text) <= remaining:
            remaining -= len(run.text)
            continue
        out.append(Run(run.text[remaining:], run.marks, run.href))
        remaining = 0
    return out


def starts_paragraph(prev: Line, line: Line, pitch: float, body: float, frame: dict) -> bool:
    """Is `line` the first line of a new paragraph, given the line before it?"""
    prev_text = prev.text.rstrip()
    if prev.page != line.page or abs(prev.x0 - line.x0) > frame["width"] * 0.3:
        # Page or column break: continue unless the previous line ended a sentence
        # and this one is indented or starts with a capital letter.
        if not ends_sentence(prev_text):
            return False
        return not line.text.lstrip()[:1].islower()
    gap = line.y0 - prev.y0
    if gap > pitch * 1.35 or gap < -1:
        return True
    indent = line.x0 - frame["left"]
    if indent > body * 0.8 and prev.x0 - frame["left"] < body * 0.5:
        return True
    short = prev.x1 < frame["right"] - frame["width"] * 0.12
    return short and ends_sentence(prev_text)


def typical_pitch(lines: list[Line], body: float) -> float:
    """The usual distance from one line to the next, from the most common gap.

    Lines are taken top to bottom per page, whatever block they're in: some
    exporters (Google Docs) put every line in its own block, and double
    spacing must still read as one paragraph."""
    ordered = sorted(lines, key=lambda l: (l.page, l.y0))
    gaps = [
        round(b.y0 - a.y0)
        for a, b in zip(ordered, ordered[1:])
        if a.page == b.page and body * 0.8 < b.y0 - a.y0 < body * 3.2 and abs(a.size - b.size) < 1
    ]
    if not gaps:
        return body * 1.25
    # The most common gap is the line spacing; paragraph gaps are fewer and larger.
    counts = Counter(gaps)
    return float(min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0])


def frames(pages: list[PageInfo]) -> dict[tuple[int, int], dict]:
    """Left edge, right edge and width of the text in each page column."""
    out = {}
    for info in pages:
        two = is_two_column(info.lines, info.width)
        groups: dict[int, list[Line]] = defaultdict(list)
        for line in info.lines:
            col = 1 if two and line.x0 > info.width / 2 - info.width * 0.02 else 0
            groups[col].append(line)
        for col, lines in groups.items():
            left = statistics.median_low(sorted(l.x0 for l in lines))
            right = max(l.x1 for l in lines)
            out[(lines[0].page, col)] = {"left": left, "right": right, "width": max(right - left, 1)}
    return out


def frame_for(line: Line, info: PageInfo, table: dict) -> dict:
    two = is_two_column(info.lines, info.width)
    col = 1 if two and line.x0 > info.width / 2 - info.width * 0.02 else 0
    return table.get((line.page, col)) or {"left": line.x0, "right": line.x1, "width": info.width}


def read_pdf(path: Path, pages: str | None = None, clip: Clip | None = None) -> Document:
    infos, indices = extract(path, pages, clip)
    warnings = check_scanned(infos, indices, path.name)
    for info in infos:
        merge_fragments(info)
    remove_running_heads(infos)
    remove_repeated_images(infos)
    contents_pages = remove_contents_pages(infos)
    for info in infos:
        find_text_tables(info)
    if contents_pages:
        warnings.append(f"pages {_ranges(contents_pages)}: skipped the source's table of contents; "
                        "the site builds its own")
    body = body_size(infos)
    note_lines = split_footnotes(infos, body)
    all_lines = [l for info in infos for l in info.lines]
    tiers = heading_tiers(all_lines, body)
    vocab = hyphenated_vocabulary([l.text for l in all_lines])
    pitch = typical_pitch(sorted(all_lines, key=lambda l: (l.page, l.block, l.y0)), body)
    frame_table = frames(infos)
    page_of = dict(zip(indices, infos))

    grid_pages = [index + 1 for info, index in zip(infos, indices) if info.grid_paper]
    if grid_pages:
        warnings.append(f"pages {_ranges(grid_pages)}: drawn on graph or lined paper, so tables there "
                        "were not looked for; check the text came through as written")
    math_pages = sorted({l.page + 1 for l in all_lines if any(s.math for s in l.spans)})
    if math_pages:
        warnings.append(
            f"pages {_ranges(math_pages)}: math fonts found; equations are kept as plain text, so check them"
        )
    if any("�" in l.text for l in all_lines):
        warnings.append("some characters could not be decoded (shown as �); re-export the PDF with fonts embedded")

    blocks: list = []
    para: list[Line] = []
    deferred: list[Figure] = []  # figures that interrupted an unfinished sentence
    code: list[Line] = []
    # (marker x0 relative to the text column's left edge, list). Relative,
    # because left and right pages often have different margins.
    list_stack: list[tuple[float, ListBlock]] = []
    item_lines: list[Line] = []
    pending_caption: tuple[str, str, Inlines, Line] | None = None  # table captions sit above

    def flush_para():
        nonlocal para
        flush_code()
        if para:
            content = join_runs([spans_to_runs(l.spans) for l in para], vocab)
            if content:
                blocks.append(Paragraph(content))
            para = []
        blocks.extend(deferred)
        deferred.clear()

    def flush_code():
        nonlocal code
        if code:
            # Indentation is measured from each page's own text edge.
            rel = [l.x0 - frame_for(l, page_of[l.page], frame_table)["left"] for l in code]
            left = min(rel)
            width = max(code[0].size * 0.6, 1)
            text = "\n".join(" " * round((x - left) / width) + clean_text(l.text).rstrip() for x, l in zip(rel, code))
            blocks.append(Code(text))
            code = []

    def flush_item():
        nonlocal item_lines
        if item_lines and list_stack:
            marker = list_marker(item_lines[0].text)
            first = strip_marker(spans_to_runs(item_lines[0].spans), marker[2] if marker else 0)
            content = join_runs([first] + [spans_to_runs(l.spans) for l in item_lines[1:]], vocab)
            list_stack[-1][1].items.append(ListItem(content))
        item_lines = []

    def close_lists():
        flush_item()
        list_stack.clear()

    def last_block_on(page: int, kind, reach: int = 1):
        """The latest block of a kind on this page, looking back past at most
        `reach` - 1 short blocks (such as a figure's title line)."""
        for block in reversed(blocks[-reach:]):
            if isinstance(block, kind) and getattr(block, "_page", None) == page:
                return block
            if not isinstance(block, (Paragraph, Heading)) or len(plain_text(block.content)) > 160:
                return None
        return None

    # Figures whose caption sits above them: id(image item) -> (label, caption).
    caption_above: dict[int, tuple[str, Inlines]] = {}

    ordered: list[Item] = []
    for info in infos:
        ordered.extend(reading_order(info))

    i = 0
    prev_body: Line | None = None
    while i < len(ordered):
        item = ordered[i]
        if isinstance(item, ImageItem):
            figure = Figure(Image(item.data, item.ext), alt="")
            if id(item) in caption_above:
                figure.label, figure.caption = caption_above.pop(id(item))
            figure._page = item.page  # type: ignore[attr-defined]
            figure._box = (item.x0, item.y0, item.x1, item.y1)  # type: ignore[attr-defined]
            if para and not item_lines and not ends_sentence(para[-1].text):
                # A figure placed mid-sentence: the paragraph goes on after it.
                deferred.append(figure)
            else:
                flush_para()
                close_lists()
                blocks.append(figure)
                prev_body = None
            i += 1
            continue
        if isinstance(item, TableItem):
            flush_para()
            close_lists()
            table = Table([[[Run(cell)] if cell else [] for cell in row] for row in item.rows])
            table._page = item.page  # type: ignore[attr-defined]
            if id(item) in caption_above:  # a table captioned as "Figure N" above it
                table.label, table.caption = caption_above.pop(id(item))
            if pending_caption and pending_caption[0] == "table" and pending_caption[3].page == item.page:
                table.label, table.caption = pending_caption[1], pending_caption[2]
                pending_caption = None
            blocks.append(table)
            prev_body = None
            i += 1
            continue

        line = item
        kind, level = classify(line, body, tiers)

        if kind == "heading":
            flush_para()
            close_lists()
            group = [line]
            while (
                i + 1 < len(ordered)
                and isinstance(ordered[i + 1], Line)
                and ordered[i + 1].page == line.page
                and ordered[i + 1].block == line.block
                and classify(ordered[i + 1], body, tiers) == (kind, level)
            ):
                i += 1
                group.append(ordered[i])
            content = join_runs([spans_to_runs(l.spans) for l in group], vocab)
            # Heading weight is implied; don't wrap the whole heading in <strong>.
            content = [Run(r.text, r.marks - {"strong"}, r.href) for r in content]
            blocks.append(Heading(level, clean_runs(content)))
            prev_body = None
            i += 1
            continue

        if kind == "caption" and deferred and not deferred[-1].caption and (caption_label(_without_bullet(line.text.strip())) or ("",))[0] == "figure":
            group = [line]
            while (
                i + 1 < len(ordered)
                and isinstance(ordered[i + 1], Line)
                and ordered[i + 1].page == line.page
                and ordered[i + 1].block == line.block
            ):
                i += 1
                group.append(ordered[i])
            content = _caption_content(join_runs([spans_to_runs(l.spans) for l in group], vocab))
            deferred[-1].label = caption_label("".join(r.text for r in content))[1]
            deferred[-1].caption = _strip_label(content)
            i += 1
            continue

        if kind == "caption":
            flush_para()
            close_lists()
            group = [line]
            while (
                i + 1 < len(ordered)
                and isinstance(ordered[i + 1], Line)
                and ordered[i + 1].page == line.page
                and ordered[i + 1].block == line.block
            ):
                i += 1
                group.append(ordered[i])
            content = _caption_content(join_runs([spans_to_runs(l.spans) for l in group], vocab))
            cap_kind, label, _rest = caption_label("".join(r.text for r in content))
            caption = _strip_label(content)
            info = page_of[line.page]
            if cap_kind == "figure":
                figure = last_block_on(line.page, Figure, reach=3)
                below = _image_below(ordered, i, line)
                if figure is not None and not figure.caption:
                    figure.caption, figure.label = caption, label
                elif below is not None:
                    caption_above[id(below)] = (label, caption)  # the caption is above its figure
                else:
                    region = _figure_region(line, info, blocks)
                    if region:
                        data = rasterize(info, line.page, region)
                        fig = Figure(Image(data, "png"), alt="", caption=caption, label=label)
                        fig._page = line.page  # type: ignore[attr-defined]
                        blocks.append(fig)
                    else:
                        warnings.append(
                            f"page {line.page + 1}: found the caption \"{label}\" but no figure near it; kept as text"
                        )
                        blocks.append(Paragraph(content))
            else:
                table = last_block_on(line.page, Table)
                if table is not None and not table.caption:
                    table.caption, table.label = caption, label
                else:
                    pending_caption = ("table", label, caption, line)
            prev_body = None
            i += 1
            continue

        if kind == "code":
            if code and code[-1].page == line.page and line.y0 - code[-1].y0 > pitch * 2.5:
                flush_code()
            if para:
                flush_para()
            close_lists()
            code.append(line)
            prev_body = None
            i += 1
            continue

        if kind == "item":
            flush_para()
            marker = list_marker(line.text)
            ordered_list, number, _ = marker
            x = line.x0 - frame_for(line, page_of[line.page], frame_table)["left"]
            last_item = item_lines[-1] if item_lines else None
            if list_stack and last_item is not None and last_item.page != line.page:
                # First item on a new page, straight after an item on the last
                # one: same list, same level. Page margins can't be compared.
                current = list_stack[-1][1]
                expected = current.start + len(current.items) + 1
                if current.ordered == ordered_list and (not ordered_list or number == expected):
                    # Re-measure the open lists in this page's coordinates.
                    delta = x - list_stack[-1][0]
                    list_stack[:] = [(lx + delta, lst) for lx, lst in list_stack]
            flush_item()
            while list_stack and x < list_stack[-1][0] - 4:
                done = list_stack.pop()[1]
                if list_stack:
                    list_stack[-1][1].items[-1].children.append(done)
            if list_stack and x > list_stack[-1][0] + 8 and list_stack[-1][1].items:
                child = ListBlock(ordered_list, [], number)
                list_stack.append((x, child))
            elif not list_stack or list_stack[-1][1].ordered != ordered_list:
                if list_stack:
                    close_lists()
                new = ListBlock(ordered_list, [], number)
                blocks.append(new)
                list_stack.append((x, new))
            item_lines = [line]
            prev_body = line
            i += 1
            continue

        # Body line: continues a list item, continues a paragraph, or starts one.
        info = page_of[line.page]
        frame = frame_for(line, info, frame_table)
        flush_code()
        if item_lines:
            prev = item_lines[-1]
            marker_x = frame["left"] + list_stack[-1][0] if list_stack else prev.x0
            hanging = line.x0 >= marker_x + 2
            flush_left = abs(line.x0 - marker_x) <= 2
            item_frame = frame | {"left": line.x0 if hanging else marker_x}
            # Wrapped item text either hangs under the item's words or starts
            # back at the marker; a gap or a finished short line ends the item.
            if (hanging or flush_left) and not starts_paragraph(prev, line, pitch, body, item_frame):
                item_lines.append(line)
                prev_body = line
                i += 1
                continue
            # Nested children collapse back into the top list before it closes.
            flush_item()
            while len(list_stack) > 1:
                done = list_stack.pop()[1]
                list_stack[-1][1].items[-1].children.append(done)
            list_stack.clear()
        resumes = bool(deferred) and bool(para) and line.text.lstrip()[:1].islower()
        if para and prev_body is not None and not resumes and starts_paragraph(prev_body, line, pitch, body, frame):
            flush_para()
        para.append(line)
        prev_body = line
        i += 1

    flush_para()
    flush_item()
    flush_code()
    while len(list_stack) > 1:
        done = list_stack.pop()[1]
        list_stack[-1][1].items[-1].children.append(done)
    if pending_caption:
        blocks.append(Paragraph(pending_caption[2]))
        warnings.append(f"page {pending_caption[3].page + 1}: \"{pending_caption[1]}\" has no table; kept as text")

    notes = [join_runs([spans_to_runs(l.spans) for l in group], vocab) for group in note_lines]
    notes = [_strip_footnote_marker(n) for n in notes if n]

    for block in blocks:
        for attr in ("_page", "_box"):
            if hasattr(block, attr):
                delattr(block, attr)
    return Document(blocks, str(path), warnings, notes)


def _image_below(ordered: list, i: int, caption: Line) -> "ImageItem | TableItem | None":
    """The figure straight below a caption placed above it: an image (or a
    table the author captioned as a figure), with at most one short line
    between them, on the same page or first thing on the next one."""
    lines_between = 0
    for item in ordered[i + 1 : i + 4]:
        if item.page != caption.page:
            # A caption at the foot of a page, its figure first on the next one.
            if item.page == caption.page + 1 and isinstance(item, (ImageItem, TableItem)):
                return item
            return None
        if isinstance(item, (ImageItem, TableItem)):
            return item if item.y0 - caption.y1 < caption.size * 6 else None
        if not isinstance(item, Line) or len(item.text) > 120:
            return None
        lines_between += 1
        if lines_between > 1:
            return None
    return None


def _caption_content(content: Inlines) -> Inlines:
    """Drop a bullet in front of a caption."""
    text = "".join(r.text for r in content)
    stripped = _without_bullet(text)
    if stripped == text:
        return content
    return clean_runs(strip_marker(content, len(text) - len(stripped)))


def _strip_label(content: Inlines) -> Inlines:
    text = "".join(r.text for r in content)
    found = caption_label(text)
    if not found:
        return content
    cut = len(text) - len(found[2])
    return clean_runs(strip_marker(content, cut))


def _strip_footnote_marker(content: Inlines) -> Inlines:
    text = "".join(r.text for r in content)
    m = FOOTNOTE_START.match(text)
    if not m:
        return content
    return clean_runs(strip_marker(content, m.end(1)))


def _figure_region(caption: Line, info: PageInfo, blocks: list) -> tuple[float, float, float, float] | None:
    """Box above a caption that holds vector drawings: a figure drawn as paths."""
    above = [
        l.y1
        for l in info.lines
        if l.y1 <= caption.y0 - 1 and not (l.x1 < caption.x0 - 5 or l.x0 > caption.x1 + 5)
    ]
    top = max(above) if above else info.height * MARGIN
    bottom = caption.y0 - 1
    if bottom - top < 30:
        return None
    drawn = [
        d
        for d in info.drawings
        if d[1] >= top - 1 and d[3] <= bottom + 1 and (d[2] - d[0]) + (d[3] - d[1]) > 0
    ]
    if not drawn:
        return None
    x0 = min(d[0] for d in drawn)
    x1 = max(d[2] for d in drawn)
    y0 = min(d[1] for d in drawn)
    y1 = max(d[3] for d in drawn)
    pad = 4
    return (max(0, x0 - pad), max(0, y0 - pad), min(info.width, x1 + pad), min(info.height, y1 + pad))
