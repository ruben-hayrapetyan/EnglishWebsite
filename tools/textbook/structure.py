"""Turn a read Document into one chapter's body.

- pick the chapter out of a combined book (by heading)
- drop the chapter's own title (the page header shows it)
- renumber headings so the chapter's sections are h2, with no skipped levels
"""

from __future__ import annotations

from collections import Counter

from .model import Document, Heading, ListBlock, Paragraph, Run, plain_text
from .normalize import comparable
from .readers import ReaderError
import re

from .sections import written_content, written_parts


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


MINOR_WORDS = {"a", "an", "and", "the", "of", "in", "on", "with", "to", "for"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", comparable(text)) if w not in MINOR_WORDS}


def _restates(heading: str, title: str) -> bool:
    """An opening heading that names the chapter again, worded differently:
    "Chronobiology of Hair Growth/Shedding" for "Hair growth and shedding",
    "Unit: Infradian Rhythms Chapter: Breeding and Migration". Only for titles
    of two or more words, so a one-word title doesn't swallow a section."""
    words = _words(title)
    return len(words) >= 2 and words <= _words(heading)


def drop_title(doc: Document, title: str, exact: bool = False) -> Document:
    """Remove the leading chapter-title heading, if the source starts with one.
    With exact=True only a heading that matches the title is removed."""
    blocks = list(doc.blocks)
    warnings = list(doc.warnings)
    first_heading = next((i for i, b in enumerate(blocks) if isinstance(b, Heading)), None)
    if first_heading is None:
        return doc
    head = blocks[first_heading]
    levels = [b.level for b in blocks if isinstance(b, Heading)]
    is_title = (
        comparable(plain_text(head.content)) == comparable(title)
        or (first_heading == 0 and _restates(plain_text(head.content), title))
        or (not exact and head.level == min(levels) and levels.count(head.level) == 1 and first_heading <= 1)
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
    """Rank the heading levels in use: the top one becomes h2, the next h3,
    and so on (at most h6). Ranking, rather than shifting, means headings at
    the same level stay at the same level and no level is ever skipped."""
    levels = sorted({b.level for b in doc.blocks if isinstance(b, Heading)})
    rank = {level: min(2 + n, 6) for n, level in enumerate(levels)}
    previous = 1
    for block in doc.blocks:
        if isinstance(block, Heading):
            # Never more than one level below the heading before it.
            block.level = min(rank[block.level], previous + 1)
            previous = block.level
    return doc


SHORT = 100  # characters: longer bold text is emphasis, not a heading


def _all_bold(content) -> bool:
    visible = [r for r in content if r.text.strip()]
    return bool(visible) and all("strong" in r.marks for r in visible)


def _heading_like(block) -> bool:
    """A short all-bold line used as a heading: a bold paragraph, or a list
    with a single bold item ("1. What is being measured?")."""
    if isinstance(block, Paragraph):
        content = block.content
    elif isinstance(block, ListBlock) and len(block.items) == 1 and not block.items[0].children:
        content = block.items[0].content
    else:
        return False
    text = plain_text(content).strip()
    return 0 < len(text) <= SHORT and _all_bold(content) and not text.endswith((".", ",", ";"))


def tidy(doc: Document) -> Document:
    """Give every chapter the same shape, whatever its author did:

    - short bold lines, and one-item bold lists, are headings
    - empty headings are dropped
    (A figure's title line between its image and caption is joined to the
    caption by the PDF reader, where the layout shows which is which.)
    """
    out = [b for b in doc.blocks if not (isinstance(b, Paragraph) and not plain_text(b.content).strip())]
    # A long heading that wrapped, with its last word or two left as a heading
    # of its own ("...Population Cycles in Predator-Prey" + "Systems?").
    merged: list = []
    for block in out:
        prev = merged[-1] if merged else None
        prev_text = plain_text(prev.content).strip() if isinstance(prev, Heading) else ""
        tail = block.content if isinstance(block, (Heading, Paragraph)) else None
        if (
            tail is not None and (isinstance(block, Heading) or _heading_like(block)) and isinstance(prev, Heading)
            and len(prev_text) >= 50 and not prev_text.endswith((".", "?", "!", ":"))
            and len(plain_text(tail).strip()) <= 20
        ):
            prev.content = prev.content + [Run(" ")] + [Run(r.text, r.marks - {"strong"}, r.href) for r in tail]
            continue
        merged.append(block)
    out = merged
    levels = [b.level for b in out if isinstance(b, Heading)]
    level = Counter(levels).most_common(1)[0][0] if levels else 2
    tidied: list = []
    for block in out:
        if _heading_like(block):
            content = block.content if isinstance(block, Paragraph) else block.items[0].content
            block = Heading(level, [Run(r.text, r.marks - {"strong"}, r.href) for r in content])
        if isinstance(block, Heading) and not plain_text(block.content).strip():
            continue
        tidied.append(block)
    return Document(tidied, doc.source, list(doc.warnings), list(doc.notes))


NUMBERED = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+\S")


def align_numbered(doc: Document) -> Document:
    """Numbered headings ("1. ...", "2. ...", "2.1 ...") get levels from their
    numbers, so one author's font sizes can't make "1." and "2." differ."""
    headings = [b for b in doc.blocks if isinstance(b, Heading)]
    numbered = [(b, NUMBERED.match(plain_text(b.content))) for b in headings]
    numbered = [(b, m.group(1).count(".")) for b, m in numbered if m]
    if len(numbered) < 2:
        return doc
    top = [b.level for b, depth in numbered if depth == 0]
    base = min(top) if top else min(b.level - depth for b, depth in numbered)
    for b, depth in numbered:
        b.level = base + depth
    return doc


def chapter_body(doc: Document, title: str, heading: str | None = None) -> Document:
    if heading:
        doc = select_section(doc, heading)
    parts = written_parts(doc)  # only the written content, if the chapter uses the template
    if parts is None:
        doc = drop_title(doc, title)
        return normalize_levels(align_numbered(tidy(doc)))
    # Each author's part is levelled on its own: its top headings become h2.
    blocks: list = []
    for part in parts:
        piece = Document(part, doc.source)
        piece = drop_title(piece, title, exact=True) if not blocks else piece
        blocks.extend(normalize_levels(align_numbered(tidy(piece))).blocks)
    warnings = list(doc.warnings)
    if not blocks:
        warnings.append("no written content found between the template's labels; the chapter is empty")
    return Document(blocks, doc.source, warnings, list(doc.notes) if blocks else [])
