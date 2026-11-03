"""The format-neutral document model every reader produces.

Readers (PDF, DOCX, Markdown, ...) turn a source file into a Document: a flat
list of blocks with inline runs inside. The renderer only ever sees this
model, so adding an input format never touches the HTML side, and the same
chapter written in two formats renders to the same page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# Inline marks a run of text can carry. Rendered as the matching HTML element.
MARKS = ("strong", "em", "code", "sup", "sub")


@dataclass(frozen=True)
class Run:
    """A run of text with the same formatting and link target."""

    text: str
    marks: frozenset[str] = frozenset()
    href: str | None = None


Inlines = list[Run]


@dataclass
class Heading:
    level: int  # 1 = chapter title in the source; renderer shifts to h2+
    content: Inlines
    id: str | None = None  # assigned by the renderer


@dataclass
class Paragraph:
    content: Inlines


@dataclass
class ListItem:
    content: Inlines
    children: list["ListBlock"] = field(default_factory=list)


@dataclass
class ListBlock:
    ordered: bool
    items: list[ListItem]
    start: int = 1


@dataclass
class Image:
    data: bytes
    ext: str  # "png" or "jpg"


@dataclass
class Figure:
    image: Image
    alt: str  # "" means the source gave none; the build reports it
    caption: Inlines = field(default_factory=list)
    label: str | None = None  # e.g. "Figure 3.1", from the caption
    id: str | None = None


@dataclass
class Table:
    rows: list[list[Inlines]]  # first row is the header row
    caption: Inlines = field(default_factory=list)
    label: str | None = None
    id: str | None = None


@dataclass
class Quote:
    content: list[Inlines]  # one entry per paragraph


@dataclass
class Code:
    text: str


Block = Union[Heading, Paragraph, ListBlock, Figure, Table, Quote, Code]


@dataclass
class Document:
    blocks: list[Block]
    source: str  # path the document came from, for messages
    warnings: list[str] = field(default_factory=list)
    notes: list[Inlines] = field(default_factory=list)  # footnotes, in order


def plain_text(content: Inlines) -> str:
    return "".join(run.text for run in content)


def merge_runs(content: Inlines) -> Inlines:
    """Join neighbouring runs with identical formatting; drop empty runs."""
    merged: Inlines = []
    for run in content:
        if not run.text:
            continue
        if merged and merged[-1].marks == run.marks and merged[-1].href == run.href:
            merged[-1] = Run(merged[-1].text + run.text, run.marks, run.href)
        else:
            merged.append(run)
    return merged

