"""Helpers for the textbook converter tests (fixtures live in conftest.py).

`sample_site` builds a throwaway copy of the site (template, assets, menu)
in a temp folder, with a three-chapter sample book whose chapters come
from a PDF, a Word file and a Markdown file. Tests run the real converter
on it, so nothing in the repo is touched.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import samples  # noqa: E402

AUTHORS = {"ada": "Ada Example", "ben": "Ben Example", "cy": "Cy Example"}


def copy_site(dest: Path) -> Path:
    """The parts of the repo a generated page depends on."""
    shutil.copy(ROOT / "_template.html", dest / "_template.html")
    shutil.copytree(ROOT / "assets", dest / "assets")
    (dest / "textbook" / "sources").mkdir(parents=True)
    return dest


def book_manifest(chapters: list[dict], **overrides) -> dict:
    data = {
        "title": "The sample textbook",
        "highlight": "sample",
        "lede": "A sample book for the converter's tests.",
        "description": "A sample book used only by the tests.",
        "units": [{"id": "first", "title": "First unit"}, {"id": "second", "title": "Second unit"}],
        "authors": AUTHORS,
        "chapters": chapters,
    }
    data.update(overrides)
    return data


def write_manifest(root: Path, data: dict) -> Path:
    path = root / "textbook" / "textbook.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def sample_chapters(root: Path) -> list[dict]:
    src = root / "textbook" / "sources"
    samples.sample_pdf(src / "from-pdf.pdf")
    samples.sample_docx(src / "from-word.docx")
    samples.sample_markdown(src / "from-markdown.md")
    return [
        {"id": "from-pdf", "title": samples.TITLE, "unit": "first", "authors": ["ada"],
         "source": "sources/from-pdf.pdf", "highlight": "rhythms",
         "figures": {"figure-1": {"alt": "Black bars on white, evenly spaced"}}},
        {"id": "from-word", "title": "Sample rhythms in Word", "unit": "first", "authors": ["ben", "cy"],
         "source": {"file": "sources/from-word.docx", "heading": samples.TITLE},
         "summary": "The sample chapter, written in Word."},
        {"id": "from-markdown", "title": "Sample rhythms in Markdown", "unit": "second", "authors": ["ada", "ben", "cy"],
         "source": {"file": "sources/from-markdown.md", "heading": samples.TITLE},
         "ai_credit": "The authors used no generative AI."},
        {"id": "not-written", "title": "A chapter with no source yet", "unit": "second", "authors": ["cy"]},
    ]
