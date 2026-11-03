"""Text clean-up shared by every reader.

The output must be stable: the notes feature finds a reader's highlight
again by its exact words, so the same source must always give the same
characters. Everything here is a pure function.
"""

from __future__ import annotations

import re
import unicodedata

from .model import Inlines, Run, merge_runs

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}

# Characters that are layout artifacts, not content.
INVISIBLE = {
    "­": "",   # soft hyphen
    "​": "",   # zero-width space
    "‌": "",   # zero-width non-joiner
    "⁠": "",   # word joiner
    "﻿": "",   # byte-order mark
}

SPACES = re.compile(r"[ \t\r\n\f\v  -   　]+")


def clean_text(text: str) -> str:
    """Normalize one run of text without trimming its ends."""
    for src, dst in LIGATURES.items():
        text = text.replace(src, dst)
    for src, dst in INVISIBLE.items():
        text = text.replace(src, dst)
    text = SPACES.sub(" ", text)
    # Drop control characters other than the space we just normalized to.
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc")
    return unicodedata.normalize("NFC", text)


def clean_runs(content: Inlines) -> Inlines:
    """Clean every run, then collapse spaces across run boundaries and trim."""
    cleaned = [Run(clean_text(r.text), r.marks, r.href) for r in content]
    out: Inlines = []
    for run in merge_runs(cleaned):
        text = run.text
        if out and out[-1].text.endswith(" ") and text.startswith(" "):
            text = text.lstrip(" ")
        if not out:
            text = text.lstrip(" ")
        if text:
            out.append(Run(text, run.marks, run.href))
    if out:
        last = out[-1]
        out[-1] = Run(last.text.rstrip(" "), last.marks, last.href)
    return [r for r in merge_runs(out) if r.text]


def comparable(text: str) -> str:
    """Loose form for matching titles: case, punctuation and numbering ignored."""
    text = clean_text(text).casefold()
    text = re.sub(r"^\s*(chapter|unit|part)\s+[\w.]+\s*[:.\-–—]?\s*", "", text)
    text = re.sub(r"^\s*\d+(\.\d+)*[.)]?\s+", "", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def slugify(text: str, fallback: str = "section") -> str:
    """Lowercase, hyphenated, ASCII-only id. Accents are folded (é -> e)."""
    text = unicodedata.normalize("NFKD", clean_text(text))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    if text and text[0].isdigit():
        text = f"{fallback}-{text}"
    return text[:60].rstrip("-") or fallback


class IdAllocator:
    """Hands out unique ids within one page: 'x', 'x-2', 'x-3', ..."""

    def __init__(self, reserved: set[str] | None = None):
        self.used: set[str] = set(reserved or ())

    def take(self, base: str) -> str:
        candidate, n = base, 2
        while candidate in self.used:
            candidate = f"{base}-{n}"
            n += 1
        self.used.add(candidate)
        return candidate


# ---- Joining lines broken by a layout ----------------------------------------

HYPHENS = ("-", "‐", "­")
TRAILING_WORD = re.compile(r"(\w+)[-‐­]$")
LEADING_WORD = re.compile(r"^(\w+)")


def line_joint(previous: str, following: str, hyphenated_words: frozenset[str]) -> tuple[int, str]:
    """How to join two visual lines of one paragraph.

    Returns (characters to drop from the end of `previous` after trimming
    trailing space, separator to insert). A word split across the line break
    ("circa-" + "dian") is rejoined without the hyphen, unless the hyphenated
    spelling ("self-aware") is used elsewhere in the source, in which case
    the hyphen is real and kept.
    """
    previous = previous.rstrip()
    following = following.lstrip()
    if not previous or not following:
        return 0, ""
    if previous.endswith("­"):
        return 1, ""
    tail = TRAILING_WORD.search(previous)
    head = LEADING_WORD.match(following)
    if tail and head and previous.endswith(HYPHENS) and following[0].islower():
        compound = f"{tail.group(1)}-{head.group(1)}".casefold()
        if compound in hyphenated_words:
            return 1, "-"
        return 1, ""
    if previous.endswith(HYPHENS) and following[0].isdigit():
        return 0, ""  # ranges like "10-" + "12" stay together
    if previous.endswith("/") and not following.startswith("/"):
        return 0, ""  # paths and web addresses broken after a slash
    return 0, " "


def join_lines(previous: str, following: str, hyphenated_words: frozenset[str]) -> str:
    """Join two visual lines as plain text (see line_joint)."""
    drop, sep = line_joint(previous, following, hyphenated_words)
    head = previous.rstrip()
    head = head[: len(head) - drop] if drop else head
    return head + sep + following.lstrip()


HYPHENATED = re.compile(r"\b(\w+)-(\w+)\b")


def hyphenated_vocabulary(lines: list[str]) -> frozenset[str]:
    """Hyphenated compounds that occur mid-line, so the hyphen is real."""
    words = set()
    for line in lines:
        body = line.rstrip()
        if body.endswith(HYPHENS):
            body = body[:-1]
        for a, b in HYPHENATED.findall(body):
            words.add(f"{a}-{b}".casefold())
    return frozenset(words)


# ---- Recognizing captions and list markers ----------------------------------

CAPTION = re.compile(
    r"^\s*(?P<kind>figure|fig\.?|table)\s*(?P<num>[A-Z]?\d+(?:[.\-]\d+)*[a-z]?)\s*[:.\-–—]?\s*",
    re.IGNORECASE,
)


def caption_label(text: str) -> tuple[str, str, str] | None:
    """('figure'|'table', 'Figure 3.1', rest of caption) or None."""
    m = CAPTION.match(text)
    if not m:
        return None
    kind = "table" if m.group("kind").lower() == "table" else "figure"
    label = f"{kind.capitalize()} {m.group('num')}"
    return kind, label, text[m.end():].strip()


BULLET = re.compile(r"^\s*([•◦▪●‣⁃∙·–—*\-])\s+")
NUMBERED = re.compile(r"^\s*\(?(\d{1,3}|[a-z]|[ivx]{1,4})[.)]\s+")


def list_marker(text: str) -> tuple[bool, int, int] | None:
    """(ordered, number, marker length) if the line starts a list item."""
    m = BULLET.match(text)
    if m:
        return False, 1, m.end()
    m = NUMBERED.match(text)
    if m:
        token = m.group(1)
        number = int(token) if token.isdigit() else 1
        return True, number, m.end()
    return None


def ends_sentence(text: str) -> bool:
    return bool(re.search(r"[.!?:;][\"'”’)\]]*\s*$", text))
