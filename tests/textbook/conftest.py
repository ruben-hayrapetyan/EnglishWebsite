"""Fixtures for the textbook converter tests. Helpers are in book_helpers.py.

`sample_site` builds a throwaway copy of the site in a temp folder with a
sample book whose chapters come from a PDF, a Word file and a Markdown file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from book_helpers import book_manifest, copy_site, sample_chapters, write_manifest


@pytest.fixture
def site(tmp_path) -> Path:
    return copy_site(tmp_path)


@pytest.fixture
def sample_site(site) -> Path:
    from tools.textbook.build import build, write

    write_manifest(site, book_manifest(sample_chapters(site)))
    result = build(site)
    assert not result.errors, result.errors
    write(site, result)
    return site
