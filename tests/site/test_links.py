"""Every relative link and asset reference resolves, including #fragments.

Pages live flat at the repo root and link with relative paths (AGENTS.md),
so a missing file or a renamed heading id is always a bug.
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import unquote, urlsplit

import pytest

from site_helpers import ROOT, page_ids, parse_page, site_pages

PAGES = site_pages()


@lru_cache(maxsize=None)
def ids_in(name: str) -> frozenset[str]:
    return frozenset(parse_page(ROOT / name).xpath("//@id"))


def references(doc):
    for el, attr in ((e, a) for a in ("href", "src") for e in doc.xpath(f"//*[@{a}]")):
        yield el, el.get(attr)


@pytest.mark.parametrize("path", PAGES, ids=page_ids(PAGES))
def test_relative_references_resolve(path):
    doc = parse_page(path)
    broken = []
    for el, ref in references(doc):
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc or ref.startswith(("mailto:", "tel:")):
            continue
        if parts.path.startswith("/"):
            broken.append(f"{ref} (use a relative path)")
            continue
        target_name = unquote(parts.path) or path.name
        target = ROOT / target_name
        if not target.is_file():
            broken.append(f"{ref} (no file {target_name})")
            continue
        if parts.fragment and target.suffix == ".html":
            if parts.fragment not in ids_in(target_name):
                broken.append(f"{ref} (no id {parts.fragment!r} in {target_name})")
    assert not broken, f"{path.name}: broken references:\n  " + "\n  ".join(broken)
