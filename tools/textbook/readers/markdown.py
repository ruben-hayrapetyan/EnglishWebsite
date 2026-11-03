"""Markdown reader (CommonMark plus tables), via markdown-it-py.

Images are read from paths relative to the Markdown file. A paragraph that
holds only an image becomes a figure; its caption is the image title
(![alt](src "caption")) or a following "Figure N." paragraph. Raw HTML in
the source is not passed through: it is dropped with a warning, so a source
file can never inject markup into the site.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

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

EXT = {".png": "png", ".jpg": "jpg", ".jpeg": "jpg"}
INLINE_TAGS = {"<sup>": "sup", "<sub>": "sub", "<strong>": "strong", "<b>": "strong", "<em>": "em", "<i>": "em"}


def read_markdown(path: Path) -> Document:
    from markdown_it import MarkdownIt

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ReaderError(f"{path.name} is not UTF-8 text. Save it with UTF-8 encoding.") from exc
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(text)
    reader = _MarkdownReader(path)
    reader.blocks = reader.walk(tokens, 0, len(tokens))
    return Document(reader.blocks, str(path), reader.warnings)


class _MarkdownReader:
    def __init__(self, path: Path):
        self.path = path
        self.warnings: list[str] = []
        self.blocks: list = []

    def walk(self, tokens, start: int, end: int) -> list:
        blocks: list = []
        i = start
        while i < end:
            tok = tokens[i]
            t = tok.type
            if t == "heading_open":
                inline = tokens[i + 1]
                level = int(tok.tag[1])
                content = [Run(r.text, r.marks - {"strong"}, r.href) for r in self.inline(inline)]
                blocks.append(Heading(level, clean_runs(content)))
                i += 3
            elif t == "paragraph_open":
                inline = tokens[i + 1]
                figure = self.figure(inline)
                if figure is not None:
                    blocks.append(figure)
                else:
                    runs = clean_runs(self.inline(inline))
                    found = caption_label("".join(r.text for r in runs))
                    prev = blocks[-1] if blocks else None
                    if found and isinstance(prev, (Figure, Table)) and not prev.caption:
                        cut = len("".join(r.text for r in runs)) - len(found[2])
                        prev.caption = _drop_prefix(runs, cut)
                        prev.label = found[1]
                    elif runs:
                        blocks.append(Paragraph(runs))
                i += 3
            elif t in ("bullet_list_open", "ordered_list_open"):
                close = self.matching(tokens, i)
                blocks.append(self.list_block(tokens, i, close))
                i = close + 1
            elif t == "blockquote_open":
                close = self.matching(tokens, i)
                inner = self.walk(tokens, i + 1, close)
                paras = [b.content for b in inner if isinstance(b, Paragraph)]
                if len(paras) != len(inner):
                    self.warnings.append("a block quote held more than paragraphs; only its paragraphs were kept")
                blocks.append(Quote(paras))
                i = close + 1
            elif t in ("fence", "code_block"):
                blocks.append(Code(tok.content.rstrip("\n")))
                i += 1
            elif t == "table_open":
                close = self.matching(tokens, i)
                blocks.append(self.table(tokens, i, close))
                i = close + 1
            elif t == "html_block":
                self.warnings.append("raw HTML in the Markdown was dropped; write it as Markdown instead")
                i += 1
            elif t == "hr":
                i += 1
            else:
                i += 1
        return blocks

    @staticmethod
    def matching(tokens, i: int) -> int:
        depth = 0
        for j in range(i, len(tokens)):
            depth += tokens[j].nesting
            if depth == 0:
                return j
        raise ReaderError("the Markdown has an unclosed block")  # pragma: no cover

    def list_block(self, tokens, start: int, end: int) -> ListBlock:
        opener = tokens[start]
        ordered = opener.type == "ordered_list_open"
        first = int(opener.attrGet("start") or 1) if ordered else 1
        block = ListBlock(ordered, [], first)
        i = start + 1
        while i < end:
            if tokens[i].type == "list_item_open":
                close = self.matching(tokens, i)
                inner = self.walk(tokens, i + 1, close)
                content: Inlines = []
                children = []
                for b in inner:
                    if isinstance(b, Paragraph):
                        if content:
                            content.append(Run(" "))
                        content.extend(b.content)
                    elif isinstance(b, ListBlock):
                        children.append(b)
                block.items.append(ListItem(clean_runs(content), children))
                i = close + 1
            else:
                i += 1
        return block

    def table(self, tokens, start: int, end: int) -> Table:
        rows, row = [], None
        for tok in tokens[start:end]:
            if tok.type == "tr_open":
                row = []
            elif tok.type == "inline" and row is not None:
                row.append(clean_runs(self.inline(tok)))
            elif tok.type == "tr_close":
                rows.append(row)
                row = None
        return Table(rows)

    def figure(self, inline) -> Figure | None:
        children = [c for c in inline.children or [] if not (c.type == "text" and not c.content.strip())]
        if len(children) != 1 or children[0].type != "image":
            return None
        img = children[0]
        src = img.attrGet("src") or ""
        data, ext = self.load_image(src)
        alt = clean_text(img.content or "").strip()
        title = clean_text(img.attrGet("title") or "").strip()
        figure = Figure(Image(data, ext), alt=alt)
        if title:
            found = caption_label(title)
            if found:
                figure.label = found[1]
                title = found[2]
            figure.caption = [Run(title)]
        return figure

    def load_image(self, src: str) -> tuple[bytes, str]:
        parts = urlsplit(src)
        if parts.scheme or parts.netloc:
            raise ReaderError(
                f"{self.path.name}: the image {src} is on the web. Download it next to the Markdown file "
                "and link it with a relative path."
            )
        file = (self.path.parent / unquote(parts.path)).resolve()
        ext = EXT.get(file.suffix.lower())
        if not file.is_file():
            raise ReaderError(f"{self.path.name}: the image {src} was not found next to the Markdown file.")
        if ext is None:
            raise ReaderError(f"{self.path.name}: the image {src} must be PNG or JPEG.")
        return file.read_bytes(), ext

    def inline(self, token) -> Inlines:
        runs: Inlines = []
        marks: list[str] = []
        href: list[str] = []
        for child in token.children or []:
            t = child.type
            current = frozenset(marks)
            link = href[-1] if href else None
            if t == "text":
                runs.append(Run(child.content, current, link))
            elif t == "code_inline":
                runs.append(Run(child.content, current | {"code"}, link))
            elif t in ("softbreak", "hardbreak"):
                runs.append(Run(" ", current, link))
            elif t == "strong_open":
                marks.append("strong")
            elif t == "em_open":
                marks.append("em")
            elif t in ("strong_close", "em_close"):
                tag = "strong" if t == "strong_close" else "em"
                if tag in marks:
                    marks.reverse()
                    marks.remove(tag)
                    marks.reverse()
            elif t == "link_open":
                href.append(child.attrGet("href"))
            elif t == "link_close":
                if href:
                    href.pop()
            elif t == "html_inline":
                tag = child.content.strip().lower()
                if tag in INLINE_TAGS:
                    marks.append(INLINE_TAGS[tag])
                elif tag.startswith("</") and "<" + tag[2:] in INLINE_TAGS:
                    name = INLINE_TAGS["<" + tag[2:]]
                    if name in marks:
                        marks.remove(name)
                else:
                    self.warnings.append(f"inline HTML {child.content!r} was dropped")
            elif t == "image":
                self.warnings.append("an image inside a sentence was dropped; put images in their own paragraph")
        return runs


def _drop_prefix(content: Inlines, length: int) -> Inlines:
    out, remaining = [], length
    for run in content:
        if remaining >= len(run.text):
            remaining -= len(run.text)
            continue
        out.append(Run(run.text[remaining:], run.marks, run.href))
        remaining = 0
    return clean_runs(out)
