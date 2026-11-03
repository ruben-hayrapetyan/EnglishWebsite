"""Book-driven regions inside hand-written pages.

Add-on pages (the study hub, author profiles, the team page) are written by
hand, but parts of them describe the book: which chapters exist, their
titles, units and authors, their sections, whether a chapter or study kit
is ready. Those parts must never be typed out by hand, or they drift from
the book. Instead the page marks a region and the converter fills it in
from textbook.json and the converted chapters:

    <!-- textbook:author-chapters daniel -->
    ...written by tools/textbook...
    <!-- /textbook -->

    <span><!-- textbook:count chapters -->12<!-- /textbook --></span>

Only the text between the markers is generated; the rest of the page stays
the author's. A region that starts on its own line is a block region: its
output is indented to match the start marker. Otherwise it is inline.

Regions (name and argument):
    count authors|chapters|units     a number from textbook.json
    study-cards <unit id>            study-kit cards for a unit's chapters
    author-chapters <author slug>    an author's chapter cards, with section
                                     outlines and links once chapters exist
    chapter-options                  <option>s for every chapter (upload page)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import Chapter, Manifest, OutlineNode
from .render import esc

REGION = re.compile(
    r"<!-- textbook:(?P<name>[a-z-]+)(?: (?P<arg>[a-z0-9-]+))? -->(?P<body>.*?)<!-- /textbook -->",
    re.S,
)

Outline = list[OutlineNode]


@dataclass
class Book:
    """What regions may draw on: the manifest and the converted chapters."""

    manifest: Manifest
    root: Path
    available: set[str] = field(default_factory=set)  # chapter ids with a page
    outlines: dict[str, Outline] = field(default_factory=dict)  # from converted chapters

    def outline(self, chapter: Chapter) -> Outline:
        """The real section headings once the chapter is converted; until then
        the outline written in textbook.json."""
        if chapter.id in self.outlines:
            return self.outlines[chapter.id]
        return chapter.outline


class RegionError(Exception):
    pass


def fill(text: str, book: Book) -> str:
    """Regenerate every region in a page. Raises RegionError for unknown ones."""

    def replace(m: re.Match) -> str:
        name, arg, body = m.group("name"), m.group("arg"), m.group("body")
        renderer = RENDERERS.get(name)
        if renderer is None:
            raise RegionError(f'unknown region "textbook:{name}" (known: {", ".join(sorted(RENDERERS))})')
        output = renderer(book, arg)
        start = f"<!-- textbook:{name}{' ' + arg if arg else ''} -->"
        if isinstance(output, str):
            return f"{start}{output}<!-- /textbook -->"
        line_start = text.rfind("\n", 0, m.start()) + 1
        indent = text[line_start : m.start()]
        if indent.strip():
            raise RegionError(f'"textbook:{name}" makes several lines, so its start marker needs its own line')
        lines = "".join(f"{indent}{line}\n" if line else "\n" for line in output)
        return f"{start}\n{lines}{indent}<!-- /textbook -->"

    return REGION.sub(replace, text)


def has_regions(text: str) -> bool:
    return bool(REGION.search(text))


# ---- Renderers ---------------------------------------------------------------


def _count(book: Book, what: str | None) -> str:
    counts = {
        "authors": len(book.manifest.authors),
        "chapters": len(book.manifest.chapters),
        "units": len(book.manifest.units),
    }
    if what not in counts:
        raise RegionError(f'"textbook:count" needs one of {", ".join(counts)}, not "{what}"')
    return str(counts[what])


def _unit(book: Book, unit_id: str | None):
    unit = next((u for u in book.manifest.units if u.id == unit_id), None)
    if unit is None:
        raise RegionError(f'unit "{unit_id}" is not in textbook.json')
    return unit


def kit_size(path: Path) -> tuple[int, int]:
    """(slides, questions) in a study kit."""
    text = path.read_text(encoding="utf-8")
    return len(re.findall(r'class="deck__slide[ "]', text)), len(re.findall(r'class="quiz__item[ "]', text))


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _study_cards(book: Book, unit_id: str | None) -> list[str]:
    unit = _unit(book, unit_id)
    lines: list[str] = []
    for chapter in [c for c in book.manifest.chapters if c.unit == unit.id]:
        kit = f"study-{chapter.id}.html"
        ready = (book.root / kit).is_file()
        names = ", ".join(esc(book.manifest.authors[a]) for a in chapter.authors)
        title = f'<a href="{kit}">{esc(chapter.title)}</a>' if ready else esc(chapter.title)
        lines += ['<article class="card">', f'  <p class="card__meta">{esc(unit.title)}</p>',
                  f'  <h3 class="card__title">{title}</h3>', f'  <p class="card__body">{names}</p>']
        if ready:
            slides, questions = kit_size(book.root / kit)
            lines.append('  <div class="cluster"><span class="tag tag--accent">Ready</span>'
                         f'<span class="tag">{plural(slides, "slide")}</span>'
                         f'<span class="tag">{plural(questions, "question")}</span></div>')
            lines.append('  <span class="card__footer" aria-hidden="true">Open the study kit &rarr;</span>')
        else:
            lines.append('  <div class="cluster"><span class="tag">Not ready yet</span></div>')
        lines.append("</article>")
    return lines


def _author_link(book: Book, slug: str) -> str:
    name = esc(book.manifest.authors[slug])
    if (book.root / f"author-{slug}.html").is_file():
        return f'<a href="author-{slug}.html">{name}</a>'
    return name


def _author_chapters(book: Book, slug: str | None) -> list[str]:
    if slug not in book.manifest.authors:
        raise RegionError(f'author "{slug}" is not in textbook.json')
    lines: list[str] = []
    for chapter in [c for c in book.manifest.chapters if slug in c.authors]:
        unit = book.manifest.unit(chapter.unit)
        if lines:
            lines.append("")
        lines += ['<article class="card author-chapter">', f'  <p class="card__meta">{esc(unit.title)}</p>',
                  f'  <h3 class="card__title">{esc(chapter.title)}</h3>']
        others = [a for a in chapter.authors if a != slug]
        if others:
            lines.append(f'  <p class="team-note">Coauthors: {", ".join(_author_link(book, a) for a in others)}</p>')
        if chapter.id in book.available:
            lines.append(f'  <p class="team-note"><a href="{chapter.filename}">Read the chapter</a></p>')
        else:
            lines.append('  <p class="team-note">Textbook link to come.</p>')
        outline = book.outline(chapter)
        if outline:
            lines += ['  <details class="author-outline">',
                      '    <summary class="author-outline__summary">View chapter sections</summary>',
                      '    <div class="prose author-outline__body">']
            lines += outline_list(outline, "      ")
            lines += ["    </div>", "  </details>"]
        lines.append("</article>")
    if not lines:
        raise RegionError(f'author "{slug}" has no chapters in textbook.json')
    return lines


def outline_list(nodes: Outline, indent: str) -> list[str]:
    """Nested <ul> for an outline, any depth."""
    lines = [f"{indent}<ul>"]
    for node in nodes:
        if node.children:
            lines.append(f"{indent}  <li>{esc(node.title)}")
            lines += outline_list(node.children, indent + "    ")
            lines.append(f"{indent}  </li>")
        else:
            lines.append(f"{indent}  <li>{esc(node.title)}</li>")
    return lines + [f"{indent}</ul>"]


def _chapter_options(book: Book, arg: str | None) -> list[str]:
    """<option>s for every chapter, for the upload page's chapter picker."""
    return [f'<option value="{c.id}">Chapter {c.number}: {esc(c.title)}'
            f'{" (on the site)" if c.id in book.available else ""}</option>' for c in book.manifest.chapters]


RENDERERS = {
    "count": _count,
    "study-cards": _study_cards,
    "author-chapters": _author_chapters,
    "chapter-options": _chapter_options,
}
