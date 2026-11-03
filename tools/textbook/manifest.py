"""textbook/textbook.json: the one place that lists the book's units,
chapters, authors and source files.

Everything the site says about the book's structure (chapter order,
numbers, titles, slugs, authors) comes from here, so the contents page,
the chapter pages and any add-on that reads this file always agree.
`load()` validates the whole file and reports every problem at once.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class ManifestError(Exception):
    def __init__(self, path: Path, problems: list[str]):
        self.problems = problems
        lines = "\n".join(f"  - {p}" for p in problems)
        super().__init__(f"{path} has {len(problems)} problem(s):\n{lines}")


@dataclass(frozen=True)
class Source:
    file: Path
    pages: str | None = None
    heading: str | None = None
    # False for chapters taken from a whole-book upload: if the chapter's
    # heading isn't in the book, it stays "Coming soon" with a warning.
    required: bool = True
    # Where the chapter sits inside a whole-book PDF (see split.py).
    clip: tuple | None = None


@dataclass
class OutlineNode:
    """One section of a chapter outline, with its subsections."""

    title: str
    children: list["OutlineNode"] = field(default_factory=list)


@dataclass(frozen=True)
class Unit:
    id: str
    title: str


@dataclass
class Chapter:
    id: str
    title: str
    unit: str
    authors: list[str]
    number: int
    summary: str | None = None
    highlight: str | None = None
    source: Source | None = None
    ai_credit: str | None = None
    figures: dict[str, dict] = field(default_factory=dict)
    # Section outline shown on author pages until the chapter's source is
    # converted; after that the real headings are used.
    outline: list["OutlineNode"] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return f"chapter-{self.id}.html"


@dataclass
class Manifest:
    path: Path
    title: str
    highlight: str | None
    lede: str
    description: str
    units: list[Unit]
    authors: dict[str, str]
    chapters: list[Chapter]

    def unit(self, unit_id: str) -> Unit:
        return next(u for u in self.units if u.id == unit_id)


TOP_KEYS = {"title", "highlight", "lede", "description", "units", "authors", "chapters"}
UNIT_KEYS = {"id", "title"}
CHAPTER_KEYS = {"id", "title", "unit", "authors", "summary", "highlight", "source", "ai_credit", "figures", "outline"}
SOURCE_KEYS = {"file", "pages", "heading"}


def _text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def load(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(path, ["the file does not exist"]) from None
    except json.JSONDecodeError as exc:
        raise ManifestError(path, [f"it is not valid JSON: {exc.msg} at line {exc.lineno}"]) from None
    problems: list[str] = []
    if not isinstance(data, dict):
        raise ManifestError(path, ["the top level must be an object"])

    for key in sorted(set(data) - TOP_KEYS):
        problems.append(f'unknown key "{key}" (allowed: {", ".join(sorted(TOP_KEYS))})')
    for key in ("title", "lede", "description"):
        if not _text(data.get(key)):
            problems.append(f'"{key}" must be a non-empty string')
    title = data.get("title") if _text(data.get("title")) else ""
    highlight = data.get("highlight")
    if highlight is not None and (not _text(highlight) or highlight not in title):
        problems.append(f'"highlight" must be words from the title ("{highlight}" is not in "{title}")')

    units: list[Unit] = []
    raw_units = data.get("units")
    if not isinstance(raw_units, list) or not raw_units:
        problems.append('"units" must be a non-empty list')
        raw_units = []
    for n, u in enumerate(raw_units, 1):
        where = f"units[{n}]"
        if not isinstance(u, dict):
            problems.append(f"{where} must be an object")
            continue
        for key in sorted(set(u) - UNIT_KEYS):
            problems.append(f'{where}: unknown key "{key}"')
        if not (isinstance(u.get("id"), str) and SLUG.match(u["id"])):
            problems.append(f'{where}: "id" must be lowercase-hyphenated, like "circadian"')
        if not _text(u.get("title")):
            problems.append(f'{where}: "title" must be a non-empty string')
        if any(x.id == u.get("id") for x in units):
            problems.append(f'{where}: unit id "{u.get("id")}" is used twice')
        units.append(Unit(str(u.get("id")), str(u.get("title", ""))))

    authors = data.get("authors")
    if not isinstance(authors, dict) or not authors:
        problems.append('"authors" must map author slugs to names, like {"jacob": "Jacob Li"}')
        authors = {}
    for slug, name in authors.items():
        if not SLUG.match(slug):
            problems.append(f'authors: "{slug}" must be lowercase-hyphenated (it names author-{slug}.html)')
        if not _text(name):
            problems.append(f'authors: "{slug}" needs a name')

    chapters: list[Chapter] = []
    raw_chapters = data.get("chapters")
    if not isinstance(raw_chapters, list) or not raw_chapters:
        problems.append('"chapters" must be a non-empty list')
        raw_chapters = []
    unit_ids = [u.id for u in units]
    for n, c in enumerate(raw_chapters, 1):
        where = f"chapters[{n}]"
        if not isinstance(c, dict):
            problems.append(f"{where} must be an object")
            continue
        cid = c.get("id")
        if isinstance(cid, str):
            where = f'chapter "{cid}"'
        for key in sorted(set(c) - CHAPTER_KEYS):
            problems.append(f'{where}: unknown key "{key}" (allowed: {", ".join(sorted(CHAPTER_KEYS))})')
        if not (isinstance(cid, str) and SLUG.match(cid)):
            problems.append(f'{where}: "id" must be lowercase-hyphenated, like "neuronal-activity"; '
                            "it becomes the file name chapter-<id>.html and must never change")
        elif any(x.id == cid for x in chapters):
            problems.append(f'{where}: the id is used by two chapters')
        ctitle = c.get("title")
        if not _text(ctitle):
            problems.append(f'{where}: "title" must be a non-empty string')
            ctitle = ""
        elif any(x.title == ctitle for x in chapters):
            problems.append(f'{where}: the title "{ctitle}" is used by two chapters')
        if c.get("unit") not in unit_ids:
            problems.append(f'{where}: unit "{c.get("unit")}" is not one of {unit_ids}')
        cauthors = c.get("authors")
        if not isinstance(cauthors, list) or not cauthors:
            problems.append(f'{where}: "authors" must list at least one author slug')
            cauthors = []
        for a in cauthors:
            if a not in authors:
                problems.append(f'{where}: author "{a}" is not in "authors"')
        chl = c.get("highlight")
        if chl is not None and (not _text(chl) or chl not in ctitle):
            problems.append(f'{where}: "highlight" must be words from its title')
        for key in ("summary", "ai_credit"):
            if key in c and not _text(c[key]):
                problems.append(f'{where}: "{key}" must be a non-empty string when present')
        figures = c.get("figures", {})
        if not isinstance(figures, dict) or not all(
            isinstance(v, dict) and set(v) <= {"alt"} and _text(v.get("alt")) for v in figures.values()
        ):
            problems.append(f'{where}: "figures" must look like {{"figure-1": {{"alt": "What the figure shows"}}}}')
            figures = {}
        outline, outline_ok = _outline(c.get("outline", []))
        if not outline_ok:
            problems.append(f'{where}: "outline" must be a list of section names, or of '
                            '{"section": "Name", "subsections": [...]} (subsections nest the same way)')
        source = None
        raw_source = c.get("source")
        if raw_source is not None:
            source, source_problems = _source(path.parent, raw_source, where)
            problems.extend(source_problems)
        chapters.append(
            Chapter(
                id=str(cid),
                title=str(ctitle),
                unit=str(c.get("unit")),
                authors=[str(a) for a in cauthors],
                number=n,
                summary=c.get("summary"),
                highlight=chl,
                source=source,
                ai_credit=c.get("ai_credit"),
                figures=figures,
                outline=outline,
            )
        )

    if problems:
        raise ManifestError(path, problems)
    return Manifest(
        path=path,
        title=title,
        highlight=highlight,
        lede=data["lede"],
        description=data["description"],
        units=units,
        authors=dict(authors),
        chapters=chapters,
    )


def _outline(raw) -> tuple[list["OutlineNode"], bool]:
    """A list of names, or {"section", "subsections"} objects nested to any depth."""
    if not isinstance(raw, list):
        return [], False
    out = []
    for item in raw:
        if _text(item):
            out.append(OutlineNode(item))
        elif isinstance(item, dict) and set(item) <= {"section", "subsections"} and _text(item.get("section")):
            children, ok = _outline(item.get("subsections", []))
            if not ok:
                return [], False
            out.append(OutlineNode(item["section"], children))
        else:
            return [], False
    return out, True


def _source(base: Path, raw, where: str) -> tuple[Source | None, list[str]]:
    problems = []
    if isinstance(raw, str):
        raw = {"file": raw}
    if not isinstance(raw, dict):
        return None, [f'{where}: "source" must be a file path or {{"file": ..., "pages": ..., "heading": ...}}']
    for key in sorted(set(raw) - SOURCE_KEYS):
        problems.append(f'{where}: unknown source key "{key}" (allowed: file, pages, heading)')
    file = raw.get("file")
    if not _text(file):
        return None, problems + [f'{where}: source "file" must be a path relative to textbook/']
    resolved = (base / file).resolve()
    if base.resolve() not in resolved.parents:
        problems.append(f'{where}: source "{file}" must be inside the textbook/ folder')
    elif not resolved.is_file():
        problems.append(f'{where}: source "{file}" does not exist (looked in {base / file})')
    pages = raw.get("pages")
    if pages is not None:
        if not re.fullmatch(r"\s*\d+(\s*-\s*\d+)?(\s*,\s*\d+(\s*-\s*\d+)?)*\s*", str(pages)):
            problems.append(f'{where}: "pages" must look like "12-30" or "3-7,10"')
        if not str(file).lower().endswith(".pdf"):
            problems.append(f'{where}: "pages" only works with PDF sources; use "heading" instead')
    heading = raw.get("heading")
    if heading is not None and not _text(heading):
        problems.append(f'{where}: "heading" must be the text of the heading that starts the chapter')
    return Source(resolved, str(pages) if pages is not None else None, heading), problems
