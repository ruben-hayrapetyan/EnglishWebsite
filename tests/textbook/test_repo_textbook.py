"""Checks on the real repo: the committed textbook pages are fresh, and the
add-on pages (study kits, author profiles) agree with textbook.json.

The add-on checks only run once those pages exist on the branch, so they
switch on by themselves when page/study-materials or page/teams merges.
"""

import re

import pytest
from lxml import html as lxml_html

from book_helpers import ROOT
from tools.textbook.build import build, stale
from tools.textbook.manifest import load
from tools.textbook.normalize import comparable

BOOK = load(ROOT / "textbook" / "textbook.json")
TITLES = {comparable(c.title): c for c in BOOK.chapters}


def test_committed_pages_are_up_to_date():
    result = build(ROOT)
    assert not result.errors, result.errors
    out_of_date = stale(ROOT, result)
    assert not out_of_date, (
        "Run `python -m tools.textbook build` and commit the result. Out of date: " + ", ".join(out_of_date)
    )


def test_contents_page_is_in_the_menu():
    assert '{ label: "Textbook", href: "textbook.html" }' in (ROOT / "assets/js/site.js").read_text()


def study_kits():
    return sorted(p for p in ROOT.glob("study-*.html"))


@pytest.mark.parametrize("kit", study_kits(), ids=lambda p: p.name)
def test_every_study_kit_matches_a_chapter(kit):
    chapter_id = kit.stem.removeprefix("study-")
    assert chapter_id in {c.id for c in BOOK.chapters}, (
        f"{kit.name}: no chapter has the id {chapter_id!r} in textbook/textbook.json. "
        "Study kits are named study-<chapter id>.html."
    )


def card_titles(path):
    doc = lxml_html.fromstring(path.read_bytes())
    return [re.sub(r"\s+", " ", t.text_content()).strip() for t in doc.xpath("//*[contains(@class,'card__title')]")]


@pytest.mark.skipif(not (ROOT / "study.html").exists(), reason="study hub not on this branch yet")
def test_study_hub_titles_match_the_book():
    unknown = [t for t in card_titles(ROOT / "study.html") if comparable(t) not in TITLES]
    assert not unknown, f"study.html lists chapters that textbook.json doesn't have: {unknown}"


@pytest.mark.skipif(not (ROOT / "teams.html").exists(), reason="team pages not on this branch yet")
def test_every_author_has_a_profile_page():
    missing = [slug for slug in BOOK.authors if not (ROOT / f"author-{slug}.html").exists()]
    assert not missing, f"textbook.json names authors with no author-<slug>.html page: {missing}"


AUTHOR_PAGES = sorted(ROOT.glob("author-*.html"))


@pytest.mark.parametrize("page", AUTHOR_PAGES, ids=lambda p: p.name)
def test_chapters_credited_on_author_pages_exist(page):
    doc = lxml_html.fromstring(page.read_bytes())
    credited = [
        re.sub(r"\s+", " ", t.text_content()).strip()
        for t in doc.xpath("//section[.//h2[contains(., 'textbook')]]//*[contains(@class,'card__title')]")
    ]
    unknown = [t for t in credited if comparable(t) not in TITLES]
    assert not unknown, f"{page.name} credits chapters that textbook.json doesn't have: {unknown}"
