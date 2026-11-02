"""End-to-end checks of every page in a real browser (Chromium).

These automate the parts of the AGENTS.md checklist that need a browser:
both themes, 390px and 1440px with no horizontal scroll, keyboard focus,
the menu, no console errors, content readable with JavaScript off, and an
axe accessibility scan.
"""

from __future__ import annotations

import pytest

from site_helpers import page_ids, site_pages

pytestmark = pytest.mark.e2e

PAGES = site_pages()
NAMES = page_ids(PAGES)
WIDTHS = [390, 1440]
THEMES = ["light", "dark"]


def open_page(new_page, site_url, name, **kwargs):
    query = f"?theme={kwargs.pop('theme')}" if "theme" in kwargs else ""
    page = new_page(**kwargs)
    page.goto(f"{site_url}/{name}{query}", wait_until="networkidle")
    return page


@pytest.mark.parametrize("name", NAMES)
def test_no_console_errors(new_page, site_url, name):
    page = open_page(new_page, site_url, name)
    assert page.errors == [], f"{name}: console errors {page.errors}"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("name", NAMES)
def test_no_horizontal_scroll(new_page, site_url, name, width, theme):
    page = open_page(new_page, site_url, name, width=width, theme=theme)
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0, f"{name} at {width}px ({theme}): scrolls sideways by {overflow}px"


@pytest.mark.parametrize("name", NAMES)
def test_dark_theme_applies(new_page, site_url, name):
    def background(theme):
        page = open_page(new_page, site_url, name, theme=theme)
        return page.evaluate(
            """() => {
              const [r, g, b] = getComputedStyle(document.body).backgroundColor
                .match(/[\\d.]+/g).map(Number);
              return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
            }"""
        )

    assert background("light") > 0.8, f"{name}: light theme background should be light"
    assert background("dark") < 0.2, f"{name}: dark theme background should be dark"


@pytest.mark.parametrize("name", NAMES)
def test_readable_without_javascript(new_page, site_url, name):
    page = open_page(new_page, site_url, name, javascript=False)
    text = page.inner_text("main").strip()
    assert len(text) > 40, f"{name}: main content must be readable with JavaScript off"
    assert page.is_visible("h1"), f"{name}: the h1 must be visible with JavaScript off"


@pytest.mark.parametrize("name", NAMES)
def test_menu_marks_current_page(new_page, site_url, name):
    page = open_page(new_page, site_url, name)
    links = page.locator(".site-nav a")
    assert links.count() > 0, f"{name}: site.js should render the menu"
    current = [
        links.nth(i).get_attribute("href")
        for i in range(links.count())
        if links.nth(i).get_attribute("aria-current") == "page"
    ]
    in_nav = [links.nth(i).get_attribute("href") for i in range(links.count())]
    expected = [name] if name in in_nav else []
    assert current == expected, f"{name}: menu marks {current}, expected {expected}"


def test_mobile_menu_opens_and_closes(new_page, site_url):
    page = open_page(new_page, site_url, "index.html", width=390)
    toggle = page.locator(".site-header__toggle")
    assert toggle.is_visible()
    assert not page.locator(".site-nav a").first.is_visible()
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert page.locator(".site-nav a").first.is_visible()
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "false"


@pytest.mark.parametrize("name", NAMES)
def test_skip_link_is_first_and_works(new_page, site_url, name):
    page = open_page(new_page, site_url, name)
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement.className")
    assert "skip-link" in focused, f"{name}: the first Tab stop must be the skip link"
    assert page.locator(".skip-link").is_visible(), f"{name}: the skip link must show on focus"
    page.keyboard.press("Enter")
    assert page.url.endswith("#main")


# The ring may sit on the element or on an ancestor that shows it through
# :focus-within (a card around its title link), so walk up to <body>.
FOCUS_RING = """() => {
  for (let node = document.activeElement; node && node !== document.body; node = node.parentElement) {
    const style = getComputedStyle(node);
    if (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0) return true;
  }
  return false;
}"""


@pytest.mark.parametrize("name", NAMES)
def test_every_tab_stop_shows_a_focus_ring(new_page, site_url, name):
    page = open_page(new_page, site_url, name)
    missing, seen = [], set()
    for _ in range(80):
        page.keyboard.press("Tab")
        key = page.evaluate(
            "(() => { const el = document.activeElement;"
            " return el === document.body ? null : el.outerHTML.slice(0, 120); })()"
        )
        if key is None or key in seen:
            break
        seen.add(key)
        if not page.evaluate(FOCUS_RING):
            missing.append(key)
    assert seen, f"{name}: nothing on the page can be reached with Tab"
    assert not missing, f"{name}: no visible focus ring on: {missing}"


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("name", NAMES)
def test_axe_finds_no_serious_problems(new_page, site_url, name, theme):
    axe_module = pytest.importorskip("axe_playwright_python.sync_playwright")
    page = open_page(new_page, site_url, name, theme=theme)
    results = axe_module.Axe().run(page)
    serious = [
        f"{v['id']}: {v['help']} ({len(v['nodes'])} element(s))"
        for v in results.response["violations"]
        if v["impact"] in {"serious", "critical"}
    ]
    assert not serious, f"{name} ({theme}): " + "; ".join(serious)
