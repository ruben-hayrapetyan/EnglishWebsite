"""Turn a read Document into one chapter's body.

- pick the chapter out of a combined book (by heading)
- drop the chapter's own title (the page header shows it)
- renumber headings so the chapter's sections are h2, with no skipped levels
"""

from __future__ import annotations

from .model import Document, Heading, plain_text
from .normalize import comparable
from .readers import ReaderError


def headings(doc: Document) -> list[tuple[int, str]]:
    return [(b.level, plain_text(b.content)) for b in doc.blocks if isinstance(b, Heading)]


def select_section(doc: Document, heading: str) -> Document:
    """Keep the blocks from `heading` up to the next heading at its level or above."""
    wanted = comparable(heading)
    start = next(
        (i for i, b in enumerate(doc.blocks) if isinstance(b, Heading) and comparable(plain_text(b.content)) == wanted),
        None,
    )
    if start is None:
        found = "; ".join(f"h{lvl} {text!r}" for lvl, text in headings(doc)[:40]) or "none"
        raise ReaderError(
            f'{doc.source}: no heading matches "{heading}". Headings found: {found}. '
            'Set "heading" in textbook.json to one of these, or use "pages" for a PDF.'
        )
    level = doc.blocks[start].level
    end = next(
        (i for i in range(start + 1, len(doc.blocks)) if isinstance(doc.blocks[i], Heading) and doc.blocks[i].level <= level),
        len(doc.blocks),
    )
    return Document(doc.blocks[start:end], doc.source, list(doc.warnings), list(doc.notes))


def drop_title(doc: Document, title: str) -> Document:
    """Remove the leading chapter-title heading, if the source starts with one."""
    blocks = list(doc.blocks)
    warnings = list(doc.warnings)
    first_heading = next((i for i, b in enumerate(blocks) if isinstance(b, Heading)), None)
    if first_heading is None:
        return doc
    head = blocks[first_heading]
    levels = [b.level for b in blocks if isinstance(b, Heading)]
    is_title = comparable(plain_text(head.content)) == comparable(title) or (
        head.level == min(levels) and levels.count(head.level) == 1 and first_heading <= 1
    )
    if not is_title:
        return doc
    if comparable(plain_text(head.content)) != comparable(title):
        warnings.append(
            f'the source calls this chapter "{plain_text(head.content)}" but textbook.json says "{title}"; '
            "the page uses textbook.json"
        )
    del blocks[first_heading]
    return Document(blocks, doc.source, warnings, list(doc.notes))


def normalize_levels(doc: Document) -> Document:
    """Shift headings so the top level is h2 and no level is skipped."""
    levels = [b.level for b in doc.blocks if isinstance(b, Heading)]
    if not levels:
        return doc
    shift = 2 - min(levels)
    previous = 1
    for block in doc.blocks:
        if isinstance(block, Heading):
            level = block.level + shift
            level = min(level, previous + 1, 6)
            block.level = max(level, 2)
            previous = block.level
    return doc


def chapter_body(doc: Document, title: str, heading: str | None = None) -> Document:
    if heading:
        doc = select_section(doc, heading)
    doc = drop_title(doc, title)
    return normalize_levels(doc)
