"""The styling rules from AGENTS.md, checked on every stylesheet.

tokens.css is the only file allowed to hold raw values. base.css is the only
file allowed to style bare elements and IDs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from site_helpers import ROOT
from cssscan import rules, selectors, strip_comments

CSS_DIR = ROOT / "assets" / "css"
ALL_CSS = sorted(CSS_DIR.rglob("*.css"))
NOT_TOKENS = [p for p in ALL_CSS if p.name != "tokens.css"]
COMPONENTS = sorted((CSS_DIR / "components").glob("*.css"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


# Deliberate exceptions that already exist on main. The highlighter's stroke is
# shaped in em so it scales with the text it sits behind, and it styles <mark>
# itself. Changing or adding to this list needs a design/* branch.
KNOWN_EXCEPTIONS = {
    ("highlight.css", "border-radius"),
    ("highlight.css", "animation"),
    ("highlight.css", "mark"),
}


def excepted(path: Path, what: str) -> bool:
    return (path.name, what) in KNOWN_EXCEPTIONS


def without_visually_hidden(css: str) -> str:
    # The 1px clip in .visually-hidden is the one allowed raw value.
    return re.sub(r"\.visually-hidden\s*\{[^}]*\}", "", css)


RAW_VALUE = re.compile(r"#[0-9a-fA-F]{3,8}\b|[0-9]px|rgba?\(|hsla?\(")


@pytest.mark.parametrize("path", NOT_TOKENS, ids=rel)
def test_no_raw_values(path):
    """The checklist grep, minus comments: no hex, px or rgb outside tokens."""
    css = without_visually_hidden(strip_comments(path.read_text()))
    hits = [
        f"line {css.count(chr(10), 0, m.start()) + 1}: {m.group(0)}"
        for m in RAW_VALUE.finditer(css)
    ]
    assert not hits, f"{rel(path)} uses raw values; use tokens: {hits}"


# Every non-zero value must come from a token. Composing tokens is fine
# ("0 0 0 var(--space-3xs) var(--color-accent-soft)"); writing "4px" isn't.
KEYWORDS = {"none", "inherit", "initial", "unset", "inset", "0", "transparent", "currentcolor"}


def raw_parts(value: str) -> list[str]:
    value = re.sub(r"var\(--[\w-]+(?:,[^()]*)?\)", " ", value)
    value = re.sub(r"(?:calc|min|max|clamp)\(", " ", value).replace(")", " ").replace(",", " ")
    return [part for part in value.split() if part.lower() not in KEYWORDS and not re.fullmatch(r"0+(\.0+)?", part)]


TOKEN_ONLY_PROPERTIES = {"font-family", "box-shadow", "border-radius"}


def reduced_motion(path: Path, rule) -> bool:
    """base.css may switch motion off with !important (AGENTS.md)."""
    return path.name == "base.css" and (
        any("prefers-reduced-motion" in c for c in rule.context) or "motion" in rule.selector
    )


@pytest.mark.parametrize("path", NOT_TOKENS, ids=rel)
def test_fonts_shadows_radii_come_from_tokens(path):
    bad = []
    for rule in rules(path.read_text()):
        if rule.selector.startswith("@font-face"):
            continue
        for prop, value in rule.declarations:
            if prop in TOKEN_ONLY_PROPERTIES and raw_parts(value) and not excepted(path, prop):
                bad.append(f"line {rule.line}: {prop}: {value}")
    assert not bad, f"{rel(path)}: use a token for these: {bad}"


# A duration that isn't zero ("0s" just means "no delay").
DURATION = re.compile(r"(?<![\w.-])(?!0+(?:\.0+)?m?s\b)\d*\.?\d+m?s\b")


@pytest.mark.parametrize("path", NOT_TOKENS, ids=rel)
def test_durations_come_from_tokens(path):
    bad = []
    for rule in rules(path.read_text()):
        if reduced_motion(path, rule):
            continue
        for prop, value in rule.declarations:
            if excepted(path, prop):
                continue
            if prop.startswith(("transition", "animation")) and DURATION.search(value):
                bad.append(f"line {rule.line}: {prop}: {value}")
    assert not bad, f"{rel(path)}: use --duration-* tokens: {bad}"


@pytest.mark.parametrize("path", NOT_TOKENS, ids=rel)
def test_no_important(path):
    css = path.read_text()
    if path.name == "layout.css":
        css = without_visually_hidden(strip_comments(css))
        assert "!important" not in css, f"{rel(path)}: never use !important"
        return
    bad = [
        f"line {rule.line}: {rule.selector}"
        for rule in rules(css)
        if any("!important" in value for _, value in rule.declarations) and not reduced_motion(path, rule)
    ]
    assert not bad, f"{rel(path)}: never use !important: {bad}"


ID_SELECTOR = re.compile(r"#[A-Za-z_][\w-]*")


def is_bare(selector: str) -> bool:
    """True when nothing in the selector is a class or attribute hook."""
    return "." not in selector and "[" not in selector


@pytest.mark.parametrize("path", [p for p in NOT_TOKENS if p.name != "base.css"], ids=rel)
def test_no_ids_or_bare_elements(path):
    bad = []
    for rule in rules(path.read_text()):
        if rule.selector.startswith("@") or any("keyframes" in c for c in rule.context):
            continue
        for sel in selectors(rule):
            if excepted(path, sel):
                continue
            if ID_SELECTOR.search(sel) or is_bare(sel):
                bad.append(f"line {rule.line}: {sel}")
    assert not bad, f"{rel(path)}: style classes, not IDs or bare elements: {bad}"


@pytest.mark.parametrize("path", NOT_TOKENS, ids=rel)
def test_themes_live_only_in_tokens(path):
    css = strip_comments(path.read_text())
    assert "prefers-color-scheme" not in css and "[data-theme" not in css, (
        f"{rel(path)}: theme rules belong in tokens.css only"
    )


MEDIA_WIDTH = re.compile(r"\((?:min|max)-width:\s*([^)]+)\)")


@pytest.mark.parametrize("path", ALL_CSS, ids=rel)
def test_only_the_two_breakpoints(path):
    widths = set(MEDIA_WIDTH.findall(strip_comments(path.read_text())))
    assert widths <= {"40rem", "52rem"}, f"{rel(path)}: breakpoints are 40rem and 52rem only, found {widths}"


def test_main_css_imports_every_component_alphabetically():
    css = (CSS_DIR / "main.css").read_text()
    imported = re.findall(r'@import url\("components/([\w-]+)\.css"\);', css)
    assert imported == sorted(imported), "keep the components block in main.css alphabetical"
    on_disk = [p.stem for p in COMPONENTS]
    assert sorted(imported) == on_disk, (
        f"main.css imports and components/ disagree: "
        f"missing {set(on_disk) - set(imported)}, extra {set(imported) - set(on_disk)}"
    )


@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: p.stem)
def test_component_is_documented(path):
    readme = (ROOT / "README.md").read_text()
    assert path.name in readme, f"add {path.stem} to the README component table"
    head = path.read_text().lstrip()
    assert head.startswith("/*"), f"{rel(path)}: start with a header comment explaining the component"


@pytest.mark.parametrize("path", COMPONENTS, ids=lambda p: p.stem)
def test_component_is_in_styleguide(path):
    styleguide = (ROOT / "styleguide.html").read_text()
    if path.stem in {"site-header", "site-footer"}:
        hook = f"data-{path.stem}"  # rendered by site.js on every page
    else:
        hook = path.stem
    assert re.search(rf'(class="[^"]*\b{re.escape(hook)}\b|{re.escape(hook)})', styleguide), (
        f"add a demo of {path.stem} to styleguide.html"
    )
