"""Word (.docx) reader. Also covers Google Docs, Pages and LibreOffice, which
all export .docx.

Unlike PDF, a .docx keeps its structure: heading styles, list numbering,
image alt text and tables are all in the file, so this reader maps them
directly instead of guessing from layout.
"""

from __future__ import annotations

import re
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
    Quote,
    Run,
    Table,
)
from ..normalize import caption_label, clean_runs, clean_text
from . import ReaderError

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}
W = "{%s}" % NS["w"]
R = "{%s}" % NS["r"]

HEADING_STYLE = re.compile(r"^heading\s*(\d)$", re.I)
MONO = re.compile(r"mono|courier|consol|code", re.I)
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg"}


def read_docx(path: Path) -> Document:
    import docx  # python-docx

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise ReaderError(f"{path.name} could not be opened as a Word document ({exc}).") from exc

    reader = _DocxReader(document, path)
    reader.walk()
    return Document(reader.blocks, str(path), reader.warnings)


class _DocxReader:
    def __init__(self, document, path: Path):
        self.document = document
        self.path = path
        self.blocks: list = []
        self.warnings: list[str] = []
        self.list_stack: list[tuple[int, ListBlock]] = []  # (level, list)
        self.numbering = self._numbering_formats()
        self.quote: Quote | None = None

    # -- numbering.xml: which lists are ordered ------------------------------

    def _numbering_formats(self) -> dict[tuple[str, int], str]:
        try:
            root = self.document.part.numbering_part.element
        except (KeyError, AttributeError, NotImplementedError):
            return {}
        abstract = {}
        for absnum in root.findall(f"{W}abstractNum"):
            levels = {}
            for lvl in absnum.findall(f"{W}lvl"):
                fmt = lvl.find(f"{W}numFmt")
                levels[int(lvl.get(f"{W}ilvl"))] = fmt.get(f"{W}val") if fmt is not None else "bullet"
            abstract[absnum.get(f"{W}abstractNumId")] = levels
        formats = {}
        for num in root.findall(f"{W}num"):
            ref = num.find(f"{W}abstractNumId")
            levels = abstract.get(ref.get(f"{W}val"), {}) if ref is not None else {}
            for level, fmt in levels.items():
                formats[(num.get(f"{W}numId"), level)] = fmt
        return formats

    # -- walking the body ----------------------------------------------------

    def walk(self):
        from docx.table import Table as DocxTable
        from docx.text.paragraph import Paragraph as DocxParagraph

        for child in self.document.iter_inner_content():
            if isinstance(child, DocxParagraph):
                self.paragraph(child)
            elif isinstance(child, DocxTable):
                self.close_lists()
                self.close_quote()
                self.table(child)
        self.close_lists()
        self.close_quote()
        if self.document.part.package and any(
            "footnotes" in rel.reltype for rel in self.document.part.rels.values()
        ):
            if self.document.element.body.findall(f".//{W}footnoteReference"):
                self.warnings.append("footnotes are not converted yet; move them into the text or a Notes section")

    def style_name(self, paragraph) -> str:
        try:
            return (paragraph.style.name or "").strip()
        except Exception:
            return ""

    def paragraph(self, paragraph):
        style = self.style_name(paragraph)
        element = paragraph._p
        images = self.images(element)
        if element.findall(f".//{{{NS['m']}}}oMath"):
            self.warnings.append("an equation (Word math) was kept as plain text; check it")
        runs = self.runs(paragraph)
        text = "".join(r.text for r in runs).strip()

        if images:
            self.close_lists()
            self.close_quote()
            for data, ext, alt in images:
                self.blocks.append(Figure(Image(data, ext), alt=alt))
            if not text:
                return

        if not text:
            return

        found = caption_label(text)
        if style.lower() == "caption" or (found and self._captionable()):
            if self._attach_caption(runs, found):
                return

        heading = HEADING_STYLE.match(style)
        if style.lower() == "title" or heading:
            self.close_lists()
            self.close_quote()
            level = 1 if style.lower() == "title" else int(heading.group(1)) + (1 if self._has_title() else 0)
            plain = [Run(r.text, r.marks - {"strong"}, r.href) for r in runs]
            self.blocks.append(Heading(min(level, 6), clean_runs(plain)))
            return

        num = self.numbering_of(paragraph)
        if num is not None or style.lower().startswith(("list bullet", "list number")):
            self.close_quote()
            if num is not None:
                num_id, level = num
                fmt = self.numbering.get((num_id, level), "bullet")
                ordered = fmt not in ("bullet", "none")
            else:
                level = 0
                m = re.search(r"(\d)$", style)
                level = int(m.group(1)) - 1 if m else 0
                ordered = style.lower().startswith("list number")
            self.list_item(level, ordered, runs)
            return

        self.close_lists()
        if style.lower() in ("quote", "intense quote"):
            if self.quote is None:
                self.quote = Quote([])
                self.blocks.append(self.quote)
            self.quote.content.append(clean_runs(runs))
            return
        self.close_quote()
        if MONO.search(style) or (runs and all("code" in r.marks for r in runs if r.text.strip())):
            self.blocks.append(Code(paragraph.text))
            return
        self.blocks.append(Paragraph(clean_runs(runs)))

    def _has_title(self) -> bool:
        return any(isinstance(b, Heading) and b.level == 1 for b in self.blocks)

    def _captionable(self) -> bool:
        return bool(self.blocks) and isinstance(self.blocks[-1], (Figure, Table))

    def _attach_caption(self, runs: Inlines, found) -> bool:
        target = self.blocks[-1] if self._captionable() else None
        if target is None or target.caption:
            return False
        content = clean_runs(runs)
        if found:
            text = "".join(r.text for r in content)
            cut = len(text) - len(found[2])
            content = _drop_prefix(content, cut)
            target.label = found[1]
        target.caption = content
        return True

    # -- lists -----------------------------------------------------------------

    def numbering_of(self, paragraph) -> tuple[str, int] | None:
        ppr = paragraph._p.pPr
        if ppr is None or ppr.numPr is None:
            return None
        num_id = ppr.numPr.numId
        ilvl = ppr.numPr.ilvl
        if num_id is None or num_id.val == 0:
            return None
        return str(num_id.val), int(ilvl.val) if ilvl is not None else 0

    def list_item(self, level: int, ordered: bool, runs: Inlines):
        while self.list_stack and self.list_stack[-1][0] > level:
            self._pop_list()
        if not self.list_stack or self.list_stack[-1][0] < level:
            new = ListBlock(ordered, [])
            if self.list_stack and self.list_stack[-1][1].items:
                self.list_stack[-1][1].items[-1].children.append(new)
            else:
                self.close_lists()
                self.blocks.append(new)
            self.list_stack.append((level, new))
        elif self.list_stack[-1][1].ordered != ordered and len(self.list_stack) == 1:
            self.close_lists()
            new = ListBlock(ordered, [])
            self.blocks.append(new)
            self.list_stack.append((level, new))
        self.list_stack[-1][1].items.append(ListItem(clean_runs(runs)))

    def _pop_list(self):
        self.list_stack.pop()

    def close_lists(self):
        self.list_stack.clear()

    def close_quote(self):
        self.quote = None

    # -- inline content --------------------------------------------------------

    def runs(self, paragraph) -> Inlines:
        from docx.text.hyperlink import Hyperlink

        out: Inlines = []
        for item in paragraph.iter_inner_content():
            if isinstance(item, Hyperlink):
                href = item.url or None
                if href and item.fragment:
                    href = f"{href}#{item.fragment}"
                for run in item.runs:
                    out.append(self.run(run, href))
            else:
                out.append(self.run(item, None))
        return out

    def run(self, run, href) -> Run:
        marks = set()
        if run.bold:
            marks.add("strong")
        if run.italic:
            marks.add("em")
        font = run.font
        if font.superscript:
            marks.add("sup")
        if font.subscript:
            marks.add("sub")
        if font.name and MONO.search(font.name):
            marks.add("code")
        text = run.text.replace("\t", " ")
        return Run(clean_text(text), frozenset(marks), href)

    # -- images and tables -----------------------------------------------------

    def images(self, element) -> list[tuple[bytes, str, str]]:
        found = []
        for drawing in element.iter(f"{W}drawing"):
            blip = drawing.find(f".//{{{NS['a']}}}blip")
            if blip is None:
                continue
            rid = blip.get(f"{R}embed")
            part = self.document.part.related_parts.get(rid)
            if part is None:
                continue
            ext = IMAGE_TYPES.get(part.content_type)
            data = part.blob
            if ext is None:
                data, ext = _to_png(data)
                if not data:
                    self.warnings.append(f"an image of type {part.content_type} could not be converted; skipped")
                    continue
            doc_pr = drawing.find(f".//{{{NS['wp']}}}docPr")
            alt = ""
            if doc_pr is not None:
                alt = clean_text(doc_pr.get("descr") or doc_pr.get("title") or "").strip()
            found.append((data, ext, alt))
        return found

    def table(self, table):
        rows = []
        for row in table.rows:
            cells = []
            for cell in row.cells:
                runs: Inlines = []
                for para in cell.paragraphs:
                    if runs:
                        runs.append(Run(" "))
                    runs.extend(self.runs(para))
                cells.append(clean_runs(runs))
            rows.append(cells)
        if rows:
            self.blocks.append(Table(rows))


def _drop_prefix(content: Inlines, length: int) -> Inlines:
    out, remaining = [], length
    for run in content:
        if remaining >= len(run.text):
            remaining -= len(run.text)
            continue
        out.append(Run(run.text[remaining:], run.marks, run.href))
        remaining = 0
    return clean_runs(out)


def _to_png(data: bytes) -> tuple[bytes, str]:
    try:
        import pymupdf

        pix = pymupdf.Pixmap(data)
        if pix.colorspace and pix.colorspace.n > 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        return pix.tobytes("png"), "png"
    except Exception:
        return b"", ""
