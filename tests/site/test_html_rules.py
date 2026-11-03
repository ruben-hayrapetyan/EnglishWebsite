"""The HTML rules from AGENTS.md, checked on every page at the repo root.

New pages are picked up automatically, so a branch that adds a page gets
these checks for free. Each test names the rule it enforces.
"""

from __future__ import annotations

import re

import pytest

from site_helpers import page_ids, parse_page, site_pages

PAGES = site_pages()

# The style guide demonstrates tokens with inline font shorthands and shows
# the highlighter many times. It is the one documented exception.
STYLEGUIDE = "styleguide.html"


@pytest.fixture(params=PAGES, ids=page_ids(PAGES))
def page(request):
    return request.param, parse_page(request.param)


def test_one_h1(page):
    path, doc = page
    assert len(doc.xpath("//h1")) == 1, f"{path.name}: use exactly one h1"


def test_headings_in_order(page):
    path, doc = page
    levels = [int(h.tag[1]) for h in doc.iter("h1", "h2", "h3", "h4", "h5", "h6")]
    assert levels and levels[0] == 1, f"{path.name}: the first heading must be the h1"
    for before, after in zip(levels, levels[1:]):
        assert after <= before + 1, f"{path.name}: heading jumps from h{before} to h{after}"


def test_images_have_alt(page):
    path, doc = page
    missing = [img.get("src") for img in doc.iter("img") if img.get("alt") is None]
    assert not missing, f"{path.name}: images need alt text (alt=\"\" if decorative): {missing}"


def test_form_controls_have_labels(page):
    path, doc = page
    unlabeled = []
    for control in doc.xpath("//input | //select | //textarea"):
        if control.get("type") in {"hidden", "submit", "button", "reset"}:
            continue
        cid = control.get("id")
        labelled = bool(cid and doc.xpath(f'//label[@for="{cid}"]')) or bool(
            control.xpath("ancestor::label")
        )
        if not labelled:
            unlabeled.append(control.get("name") or cid or control.tag)
    assert not unlabeled, f"{path.name}: every control needs a visible <label>: {unlabeled}"


def test_ids_are_unique(page):
    path, doc = page
    ids = [el.get("id") for el in doc.xpath("//*[@id]")]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"{path.name}: duplicate ids {dupes}"


def test_sections_are_labelled(page):
    path, doc = page
    for section in doc.iter("section"):
        target = section.get("aria-labelledby")
        assert target, f"{path.name}: <section> needs aria-labelledby pointing at its heading"
        assert doc.xpath(f'//*[@id="{target}"]'), f"{path.name}: aria-labelledby=\"{target}\" has no matching id"


def test_inline_styles_only_set_custom_properties(page):
    path, doc = page
    if path.name == STYLEGUIDE:
        pytest.skip("the style guide demos tokens with inline styles")
    bad = []
    for el in doc.xpath("//*[@style]"):
        for decl in filter(None, (d.strip() for d in el.get("style").split(";"))):
            if not decl.startswith("--"):
                bad.append(decl)
    assert not bad, f"{path.name}: inline style may only set layout custom properties: {bad}"


def test_no_inline_event_handlers(page):
    path, doc = page
    if path.name == STYLEGUIDE:
        pytest.skip("the style guide's demo form cancels submit inline")
    handlers = [
        f"<{el.tag} {name}>"
        for el in doc.iter()
        if isinstance(el.tag, str)
        for name in el.attrib
        if name.startswith("on")
    ]
    assert not handlers, f"{path.name}: put behavior in assets/js/<page>.js, not attributes: {handlers}"


def test_at_most_one_highlight(page):
    path, doc = page
    if path.name == STYLEGUIDE:
        pytest.skip("the style guide demonstrates the highlighter")
    assert len(doc.xpath("//mark")) <= 1, f"{path.name}: use <mark> on at most one phrase"


# ---- Page skeleton from _template.html ------------------------------------


def test_head_matches_template(page):
    path, doc = page
    assert doc.getroottree().docinfo.doctype.lower() == "<!doctype html>"
    assert doc.get("lang") == "en"
    assert doc.xpath("//head/meta[@charset='utf-8']"), "missing <meta charset>"
    assert doc.xpath("//head/meta[@name='viewport']"), "missing viewport meta"
    description = doc.xpath("string(//head/meta[@name='description']/@content)").strip()
    assert description, f"{path.name}: write a one-sentence meta description"
    title = doc.findtext(".//title") or ""
    assert title == "English Website" or title.endswith(" · English Website"), (
        f"{path.name}: <title> must be 'Page name · English Website', got {title!r}"
    )
    assert doc.xpath("//head/link[@rel='stylesheet'][@href='assets/css/main.css']")
    assert doc.xpath("//head/link[@rel='icon'][@href='assets/img/favicon.svg']")


def test_scripts_are_deferred(page):
    path, doc = page
    scripts = doc.xpath("//script[@src]")
    assert any(s.get("src") == "assets/js/site.js" for s in scripts), f"{path.name}: load site.js"
    # AGENTS.md: the one exception is a11y.js, which loads without defer in
    # <head>, before the stylesheet, so reader settings apply before first paint.
    eager = [s.get("src") for s in scripts if s.get("defer") is None and s.get("src") != "assets/js/a11y.js"]
    assert not eager, f"{path.name}: load scripts with defer: {eager}"
    for a11y in doc.xpath("//script[@src='assets/js/a11y.js']"):
        assert a11y.getparent().tag == "head", f"{path.name}: load a11y.js in <head>"
        head = list(a11y.getparent())
        sheet = doc.xpath("//head/link[@href='assets/css/main.css']")[0]
        assert head.index(a11y) < head.index(sheet), f"{path.name}: load a11y.js before main.css"
    assert not doc.xpath("//script[not(@src)][normalize-space()]"), (
        f"{path.name}: no inline scripts; use assets/js/<page>.js"
    )


def test_page_chrome(page):
    path, doc = page
    body = doc.find("body")
    first = body[0]
    assert first.tag == "a" and "skip-link" in first.get("class", "") and first.get("href") == "#main", (
        f"{path.name}: the skip link must come first in <body>"
    )
    assert doc.xpath("//header[@data-site-header]"), f"{path.name}: keep the data-site-header element"
    assert len(doc.xpath("//main[@id='main']")) == 1, f"{path.name}: one <main id=\"main\">"
    footers = doc.xpath("//footer[@data-site-footer]")
    assert footers, f"{path.name}: keep the data-site-footer element"


def test_ai_credit(page):
    path, doc = page
    credits = doc.xpath("//aside[contains(concat(' ', @class, ' '), ' ai-credit ')]")
    assert len(credits) == 1, f"{path.name}: needs exactly one .ai-credit"
    credit = credits[0]
    assert not credit.xpath("ancestor::main"), f"{path.name}: the AI credit sits outside <main>"
    following = credit.getnext()
    assert following is not None and following.get("data-site-footer") is not None, (
        f"{path.name}: the AI credit sits directly above the site footer"
    )
    assert credit.get("aria-label") == "Use of generative AI"
    text = re.sub(r"\s+", " ", credit.text_content()).strip()
    assert text.startswith("Generative AI:"), f"{path.name}: start the credit with 'Generative AI:'"
    assert "Tool name and version" not in text, f"{path.name}: fill in the AI credit from the template"
