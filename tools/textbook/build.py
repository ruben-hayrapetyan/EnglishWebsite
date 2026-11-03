"""Build the textbook pages: textbook.json + source files -> HTML in the repo.

    build(root)                -> Result (nothing written)
    write(root, result)        -> writes files, removes ones no longer generated
    stale(root, result)        -> which files on disk differ from a fresh build

The list of files from the last build is kept in textbook/generated.txt so
a renamed or removed chapter's old files are cleaned up, and nothing that
the converter didn't create is ever deleted.

Hand-written pages with book-driven regions (see regions.py) are updated in
place: only their regions change, and they are never deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import manifest as manifest_mod
from .manifest import OutlineNode
from .model import Heading, plain_text
from .readers import ReaderError, read
from .regions import Book, RegionError, fill, has_regions
from .render import CONTENTS_FILE, load_template, render_chapter, render_contents
from .structure import chapter_body

MANIFEST = Path("textbook/textbook.json")
RECORD = Path("textbook/generated.txt")


@dataclass
class Result:
    files: dict[str, bytes] = field(default_factory=dict)  # repo-relative path -> content
    regions: dict[str, bytes] = field(default_factory=dict)  # hand-written pages with regions filled in
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build(root: Path) -> Result:
    result = Result()
    try:
        book = manifest_mod.load(root / MANIFEST)
    except manifest_mod.ManifestError as exc:
        result.errors.extend(exc.problems)
        return result
    template = load_template(root / "_template.html")

    docs = {}
    for chapter in book.chapters:
        if chapter.source is None:
            continue
        try:
            doc = read(chapter.source.file, chapter.source.pages)
            docs[chapter.id] = chapter_body(doc, chapter.title, chapter.source.heading)
        except ReaderError as exc:
            result.errors.append(f"{chapter.id}: {exc}")
    available = [c for c in book.chapters if c.id in docs]

    for chapter in available:
        doc = docs[chapter.id]
        rendered = render_chapter(book, chapter, doc, template, root, available)
        result.files[chapter.filename] = rendered.html.encode("utf-8")
        result.files.update(rendered.images)
        for message in doc.warnings + rendered.warnings:
            result.warnings.append(f"{chapter.id}: {message}")
        known = set(rendered.images)
        for fig_id in chapter.figures:
            if not any(name.endswith(f"-{fig_id}.png") or name.endswith(f"-{fig_id}.jpg") for name in known):
                result.warnings.append(f'{chapter.id}: textbook.json gives alt text for "{fig_id}", '
                                       "but the chapter has no figure with that id")

    contents = render_contents(book, template, root, {c.id for c in available})
    result.files[CONTENTS_FILE] = contents.encode("utf-8")
    record = "\n".join(sorted(result.files)) + "\n"
    result.files[str(RECORD)] = record.encode("utf-8")

    facts = Book(book, root, {c.id for c in available}, {cid: outline_of(doc) for cid, doc in docs.items()})
    for page in sorted(root.glob("*.html")):
        if page.name in result.files or page.name.startswith("_"):
            continue
        text = page.read_text(encoding="utf-8")
        if not has_regions(text):
            continue
        try:
            result.regions[page.name] = fill(text, facts).encode("utf-8")
        except RegionError as exc:
            result.errors.append(f"{page.name}: {exc}")
    return result


def outline_of(doc) -> list[OutlineNode]:
    """A converted chapter's headings as a tree: h2 sections, h3 under them, and so on."""
    root = OutlineNode("")
    stack: list[tuple[int, OutlineNode]] = [(1, root)]
    for block in doc.blocks:
        if not isinstance(block, Heading):
            continue
        node = OutlineNode(plain_text(block.content))
        while stack[-1][0] >= block.level:
            stack.pop()
        stack[-1][1].children.append(node)
        stack.append((block.level, node))
    return root.children


def previous_outputs(root: Path) -> set[str]:
    path = root / RECORD
    if not path.is_file():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def stale(root: Path, result: Result) -> list[str]:
    """Files that a build would create, change or delete."""
    out = []
    for name, data in sorted({**result.files, **result.regions}.items()):
        path = root / name
        if not path.is_file() or path.read_bytes() != data:
            out.append(name)
    for name in sorted(previous_outputs(root) - set(result.files)):
        if (root / name).exists():
            out.append(f"{name} (no longer generated)")
    return out


def write(root: Path, result: Result) -> list[str]:
    previous = previous_outputs(root)  # read before the new record overwrites it
    changed = []
    for name, data in sorted({**result.files, **result.regions}.items()):
        path = root / name
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        changed.append(name)
    for name in sorted(previous - set(result.files)):
        path = root / name
        if path.is_file():
            path.unlink()
            changed.append(f"{name} (removed)")
    return changed
