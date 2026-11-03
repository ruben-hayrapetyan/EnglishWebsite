"""Build the textbook pages: textbook.json + source files -> HTML in the repo.

    build(root)                -> Result (nothing written)
    write(root, result)        -> writes files, removes ones no longer generated
    stale(root, result)        -> which files on disk differ from a fresh build

The list of files from the last build is kept in textbook/generated.txt so
a renamed or removed chapter's old files are cleaned up, and nothing that
the converter didn't create is ever deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import manifest as manifest_mod
from .readers import ReaderError, read
from .render import CONTENTS_FILE, load_template, render_chapter, render_contents
from .structure import chapter_body

MANIFEST = Path("textbook/textbook.json")
RECORD = Path("textbook/generated.txt")


@dataclass
class Result:
    files: dict[str, bytes] = field(default_factory=dict)  # repo-relative path -> content
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
    return result


def previous_outputs(root: Path) -> set[str]:
    path = root / RECORD
    if not path.is_file():
        return set()
    return {line.strip() for line in path.read_text().splitlines() if line.strip()}


def stale(root: Path, result: Result) -> list[str]:
    """Files that a build would create, change or delete."""
    out = []
    for name, data in sorted(result.files.items()):
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
    for name, data in sorted(result.files.items()):
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
