"""Keep only a chapter's written content, so every chapter has the same shape.

The class wrote each chapter to a template:

    UNIT AND CHAPTER / CONTRIBUTORS / LEARNING OBJECTIVES / CHAPTER OUTLINE
    CHAPTER WRITTEN CONTENT                       <- the chapter itself
    CHAPTER ADD-INS / GLOSSARY / REFERENCES

Chapters by several authors repeat the parts per author ("CHAPTER WRITTEN
CONTENT (Ben)", "CHAPTER OUTLINE (Joseph)", "Works Cited"). The site shows
only the written content, from every part, in order.

This works on the format-neutral Document, so it applies the same way to
PDF, Word and Markdown chapters. A chapter without any template label is
left untouched, so books that don't use the template are unaffected.
"""

from __future__ import annotations

import re

from .model import Document, Heading, Paragraph, plain_text

_LEAD = r"^[\s•●○■▪\-–*]*"
# Labels must be the label itself ("Sections:", "LEARNING OBJECTIVES"), so a
# real heading such as "Section 1: How the heart pumps blood" isn't one.
# Labels that name an author or a topic after them are allowed where the
# class used them ("CHAPTER OUTLINE (Ben) : The sleep/wake cycle").
FRONT = re.compile(
    _LEAD + r"((unit and chapter|chapter outline|outline of)\b[^.]{0,80}"
    r"|(contributors?|learning objectives|sections?|outline)\s*:?)\s*$",
    re.I,
)
CONTENT = re.compile(_LEAD + r"(chapter )?written (content|outline)\b[^.]{0,80}$", re.I)
# A stray unit line inside the text ("UNIT: CIRCADIAN RHYTHMS") is dropped.
UNIT_LINE = re.compile(r"^\s*unit\s*:\s*[^.]{0,60}$", re.I)
BACK = re.compile(
    _LEAD + r"((chapter )?add[- ]?ins?\b[^.]{0,80}|explanatory figures|glossary|vocab(ulary)?|references|"
    r"works cited|citations|bibliography)\s*:?\s*$",
    re.I,
)
PROSE = 150  # characters: a paragraph this long is chapter text, not an outline item


def _classify(text: str) -> str | None:
    if not text or len(text) > 90:
        return None
    if CONTENT.match(text):
        return "content"
    if BACK.match(text):
        return "back"
    if FRONT.match(text):
        return "front"
    if UNIT_LINE.match(text):
        return "drop"
    return None


def _label(block) -> str | None:
    """'front', 'content', 'back' or 'drop' if the block is a template label.

    A heading or paragraph that is nothing but a label ("Learning Objectives:",
    "GLOSSARY") is one, bold or not. So is a paragraph that opens with a bold
    label and runs on into other text ("CHAPTER ADD-INS Explanatory figures
    ..."): the label marks where that part starts."""
    if not isinstance(block, (Heading, Paragraph)):
        return None
    label = _classify(plain_text(block.content).strip())
    if label or isinstance(block, Heading):
        return label
    lead = []
    for run in block.content:
        if "strong" not in run.marks:
            break
        lead.append(run.text)
    return _classify("".join(lead).strip()) if lead else None


def written_content(doc: Document) -> Document:
    """The written content as one Document (see written_parts)."""
    parts = written_parts(doc)
    if parts is None:
        return doc
    blocks = [b for part in parts for b in part]
    warnings = list(doc.warnings)
    if not blocks:
        warnings.append("no written content found between the template's labels; the chapter is empty")
    # Footnotes collected from outlines and add-ins aren't part of the text.
    return Document(blocks, doc.source, warnings, list(doc.notes) if blocks else [])


def written_parts(doc: Document) -> list[list] | None:
    """Each author's written content, in order; None if the chapter doesn't use
    the template. A part starts at each "written content" label."""
    labels = [_label(b) for b in doc.blocks]
    front = {plain_text(b.content).strip().lower().split()[0] for b, l in zip(doc.blocks, labels) if l == "front"}
    if "content" not in labels and len(front) < 2:
        # Not written to the template: keep everything. (A "References"
        # heading alone is just a normal chapter's reference list.)
        return None
    labelled = "content" in labels
    parts: list[list] = [[]]
    # "on": keeping text. "paused": a front label (such as a learning-objectives
    # list) inside the written content; the text resumes at the next heading
    # followed by prose. "off": before the content, or after an end label
    # (add-ins, glossary, references); only a written-content label resumes.
    state = "off"
    for i, (block, label) in enumerate(zip(doc.blocks, labels)):
        if label == "content":
            state = "on"
            if parts[-1]:
                parts.append([])
            continue
        if label == "back":
            state = "off"
            continue
        if label == "front":
            state = "paused" if state == "on" else state
            continue
        if label == "drop":
            continue
        starts_text = isinstance(block, Heading) and _prose_follows(doc.blocks, labels, i)
        if state == "paused" and _resumes(block):
            state = "on"  # the objectives list inside the text has ended
        elif state == "off" and not labelled and starts_text:
            # No "written content" label anywhere: the text starts at the
            # first heading that is followed by real paragraphs.
            state = "on"
        if state == "on":
            parts[-1].append(block)
    return [part for part in parts if part]


def _resumes(block) -> bool:
    """After a list of objectives inside the text: the next heading, bold
    heading-like line, or paragraph long enough to be prose."""
    if isinstance(block, Heading):
        return True
    if not isinstance(block, Paragraph):
        return False
    text = plain_text(block.content).strip()
    bold = all("strong" in r.marks for r in block.content if r.text.strip())
    return (bold and 0 < len(text) <= 100) or len(text) >= PROSE


def _prose_follows(blocks, labels, i: int) -> bool:
    for block, label in zip(blocks[i + 1 : i + 4], labels[i + 1 : i + 4]):
        if label:
            return False
        if isinstance(block, Paragraph):
            return len(plain_text(block.content)) >= PROSE
    return False
