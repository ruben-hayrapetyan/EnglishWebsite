"""Split a whole-book PDF into chapters by finding each chapter's title.

A book compiled from many authors rarely marks its chapters the same way:
"Chapter 1: A brief history", "Chapter X: Chronotypes", "UNIT AND CHAPTER:
Circulation...", or just a bold line. Each author may also use different
fonts, so heading sizes across the whole book mean little. So instead of
relying on detected headings, this finds, for each chapter in textbook.json,
the line in the book that names it:

- a short line in bold or larger type, or one starting "Chapter"/"Unit"
- not a bullet, and not on a contents page (a page naming 3+ chapters)
- the best match wins: an exact title beats "Chapter X: <title>", which
  beats a bold line merely containing the title; ties go to the earliest

Each chapter then runs from its title line to the next chapter's title
line, and is converted on its own, so each author's fonts are judged
separately. Chapters whose title isn't found are reported, not guessed.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .normalize import clean_text, comparable
from .readers.pdf import BOLD_FONT, Clip

BULLETS = "•●○◦▪■‣⁃∙·-*–—➢➔"
PREFIX = re.compile(r"^\s*(unit|chapter|part)\b", re.I)
# "Chapter", "Chapter 4", "Chapter X", "Unit IV" with an optional colon or dash.
LABEL = re.compile(r"^\s*(unit|chapter|part)\b\s*([0-9]{1,3}|[A-Z]{1,4}\b)?\s*[:.\-\u2013\u2014]?\s*", re.I)


@dataclass(frozen=True)
class TitleLine:
    page: int
    y0: float
    y1: float
    text: str
    bold: bool
    size: float


@dataclass(frozen=True)
class ChapterRange:
    first_page: int  # 0-based, inclusive
    last_page: int
    clip: Clip

    @property
    def pages(self) -> str:
        return f"{self.first_page + 1}-{self.last_page + 1}"


def _lines(path: Path) -> tuple[list[TitleLine], float]:
    import pymupdf

    pymupdf.no_recommend_layout()
    doc = pymupdf.open(path)
    lines: list[TitleLine] = []
    sizes: Counter[float] = Counter()
    for pno, page in enumerate(doc):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = clean_text("".join(s["text"] for s in line["spans"])).strip()
                size = max(round(s["size"] * 2) / 2 for s in spans)
                sizes[size] += len(text)
                bold = all(s["flags"] & 16 or BOLD_FONT.search(s["font"]) for s in spans)
                lines.append(TitleLine(pno, line["bbox"][1], line["bbox"][3], text, bold, size))
    body = max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else 10.0
    lines.sort(key=lambda l: (l.page, l.y0))
    return lines, body


def _rank(line: TitleLine, title_key: str, body: float) -> int | None:
    """0 = exact title, 1 = "Chapter ..: <title>", 2 = a title-like line containing it."""
    text = line.text
    if not text or len(text) > 160 or not title_key or text[0] in BULLETS:
        return None
    prefixed = bool(PREFIX.match(text))
    if not (line.bold or line.size > body * 1.1 or prefixed):
        return None
    key = comparable(text)
    # "Chapter X: Neuronal activity", "Chapter 4: Immunity" and
    # "Unit: Infradian rhythms Chapter: Breeding and migration" -> the words
    # after the last "Chapter <number>:" label.
    after = comparable(LABEL.sub("", re.split(r"(?=\bchapter\b)", text, flags=re.I)[-1])) if prefixed else key
    if key == title_key or after == title_key:
        return 0
    words = f" {key} "
    if f" {title_key} " in words:
        return 1 if prefixed else 2
    # "Chapter X: Neuronal activity" for "Neuronal activity: spikes and ..."
    if prefixed and len(after) >= 8 and (title_key + " ").startswith(after + " "):
        return 1
    return None


def find_chapters(path: Path, titles: dict[str, str]) -> tuple[dict[str, ChapterRange], list[str]]:
    """{chapter id: its pages in the book}, and the ids whose title wasn't found."""
    lines, body = _lines(path)
    keys = {cid: comparable(title) for cid, title in titles.items()}

    matches: dict[str, list[tuple[int, TitleLine]]] = {cid: [] for cid in titles}
    for line in lines:
        for cid, key in keys.items():
            rank = _rank(line, key, body)
            if rank is not None:
                matches[cid].append((rank, line))

    # A page that names three or more chapters is a contents page.
    per_page: Counter[int] = Counter()
    for cid, found in matches.items():
        for page in {line.page for _, line in found}:
            per_page[page] += 1
    contents_pages = {page for page, n in per_page.items() if n >= 3}

    starts: dict[str, tuple[TitleLine, TitleLine]] = {}  # first and last title line of the cluster
    for cid, found in matches.items():
        found = [(r, l) for r, l in found if l.page not in contents_pages]
        if not found:
            continue
        best = min(found, key=lambda rl: (rl[0], rl[1].page, rl[1].y0))[1]
        # Title lines just around the best one ("Circadian rhythms: Sleep..." above
        # "Chapter X: Sleep...") belong to the chapter's opening too.
        cluster = [l for _, l in found if l.page == best.page and abs(l.y0 - best.y0) < best.size * 6]
        starts[cid] = (min(cluster, key=lambda l: l.y0), max(cluster, key=lambda l: l.y0))

    ordered = sorted(starts.items(), key=lambda item: (item[1][0].page, item[1][0].y0))
    last_page = max((l.page for l in lines), default=0)
    ranges: dict[str, ChapterRange] = {}
    for n, (cid, (top, bottom)) in enumerate(ordered):
        if n + 1 < len(ordered):
            nxt = ordered[n + 1][1][0]
            end_page, end_y = nxt.page, nxt.y0 - 0.5
            last = end_page
        else:
            end_page, end_y, last = None, 0.0, last_page
        # Content starts below the chapter's title lines.
        clip: Clip = (bottom.page, bottom.y1 - 0.5, end_page, end_y)
        ranges[cid] = ChapterRange(bottom.page, last, clip)
    missing = [cid for cid in titles if cid not in ranges]
    return ranges, missing
