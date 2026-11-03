"""Input readers: one per source format, all producing a model.Document.

To support a new format, add a module with a `read_<format>(path, ...)`
function and register its file extensions in READERS below. Nothing else
in the converter needs to change.
"""

from __future__ import annotations

from pathlib import Path


class ReaderError(Exception):
    """A source file can't be converted. The message says why and how to fix it."""


def _pdf(path: Path, pages: str | None):
    from .pdf import read_pdf

    return read_pdf(path, pages)


def _docx(path: Path, pages: str | None):
    from .docx import read_docx

    return read_docx(path)


def _markdown(path: Path, pages: str | None):
    from .markdown import read_markdown

    return read_markdown(path)


READERS = {
    ".pdf": _pdf,
    ".docx": _docx,
    ".md": _markdown,
    ".markdown": _markdown,
}

HELP = {
    ".doc": "Save it as .docx (Word: File > Save As > Word Document).",
    ".odt": "Save it as .docx (LibreOffice: File > Save As > Word 2007-365).",
    ".pages": "Export it as .docx or PDF (Pages: File > Export To).",
    ".gdoc": "Download it from Google Docs as .docx (File > Download > Microsoft Word).",
    ".tex": "Compile it to PDF first, then use the PDF.",
    ".html": "Convert it to Markdown or .docx, or print it to PDF.",
    ".txt": "Rename it to .md if it is plain text or Markdown.",
}


def read(path: Path, pages: str | None = None):
    """Read any supported source file into a Document."""
    suffix = path.suffix.lower()
    if not path.is_file():
        raise ReaderError(f"{path} does not exist. Check the source path in textbook.json.")
    reader = READERS.get(suffix)
    if reader is None:
        supported = ", ".join(sorted(READERS))
        hint = HELP.get(suffix, "Convert it to one of those formats.")
        raise ReaderError(f"{path.name}: {suffix or 'files without an extension'} is not supported "
                          f"(supported: {supported}). {hint}")
    if pages and suffix != ".pdf":
        raise ReaderError(f"{path.name}: \"pages\" only works for PDFs. Use \"heading\" to pick a chapter "
                          "out of a combined document.")
    return reader(path, pages)
