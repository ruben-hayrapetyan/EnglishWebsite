"""Helpers shared by the site test suites (import from here, not conftest)."""

from __future__ import annotations

from pathlib import Path

from lxml import html as lxml_html

ROOT = Path(__file__).resolve().parent.parent


def site_pages() -> list[Path]:
    """Every real page: *.html at the repo root, minus templates (_*.html)."""
    return sorted(p for p in ROOT.glob("*.html") if not p.name.startswith("_"))


def parse_page(path: Path):
    return lxml_html.fromstring(path.read_bytes())


def page_ids(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]
