"""End-to-end: a reader moving through the generated textbook in a browser.

Runs on the sample site (chapters converted from PDF, Word and Markdown),
served over HTTP from a temp folder.
"""

import functools
import http.server
import threading

import pytest

pytestmark = pytest.mark.e2e

CHAPTERS = ["chapter-from-pdf.html", "chapter-from-word.html", "chapter-from-markdown.html"]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture
def book_url(sample_site):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(sample_site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def visit(new_page, url, **kw):
    page = new_page(**kw)
    page.goto(url, wait_until="networkidle")
    return page


def test_reader_goes_from_contents_through_every_chapter_and_back(new_page, book_url):
    page = visit(new_page, f"{book_url}/textbook.html")
    page.get_by_role("link", name="Sample rhythms", exact=True).click()
    page.wait_for_url("**/chapter-from-pdf.html")
    assert page.locator("h1").inner_text() == "Sample rhythms"
    page.get_by_role("link", name="Next chapter Sample rhythms in Word").click()
    page.wait_for_url("**/chapter-from-word.html")
    page.get_by_role("link", name="Next chapter Sample rhythms in Markdown").click()
    page.wait_for_url("**/chapter-from-markdown.html")
    page.get_by_role("link", name="Previous chapter Sample rhythms in Word").click()
    page.wait_for_url("**/chapter-from-word.html")
    page.get_by_role("link", name="See all chapters").click()
    page.wait_for_url("**/textbook.html")
    assert page.errors == []


def test_chapter_without_a_source_is_not_a_link(new_page, book_url):
    page = visit(new_page, f"{book_url}/textbook.html")
    card = page.locator("article#not-written")
    assert card.get_by_text("Coming soon").is_visible()
    assert card.locator("a").count() == 0


def test_in_chapter_contents_jumps_to_the_section_below_the_sticky_header(new_page, book_url):
    page = visit(new_page, f"{book_url}/chapter-from-pdf.html", height=700)
    page.locator(".chapter-nav__link", has_text="Summary").click()
    page.wait_for_url("**#summary")
    page.wait_for_timeout(100)
    top = page.evaluate("document.getElementById('summary').getBoundingClientRect().top")
    header = page.evaluate("document.querySelector('.site-header').getBoundingClientRect().bottom")
    assert header <= top < 250, (header, top)


def test_menu_marks_the_contents_page(new_page, book_url):
    page = visit(new_page, f"{book_url}/textbook.html")
    assert page.locator('.site-nav a[aria-current="page"]').get_attribute("href") == "textbook.html"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("width", [390, 1440])
@pytest.mark.parametrize("name", ["textbook.html", *CHAPTERS])
def test_no_sideways_scroll(new_page, book_url, name, width, theme):
    page = visit(new_page, f"{book_url}/{name}?theme={theme}", width=width)
    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0, f"{name} at {width}px ({theme}) scrolls sideways by {overflow}px"
    assert page.errors == []


@pytest.mark.parametrize("name", ["textbook.html", *CHAPTERS])
def test_readable_without_javascript(new_page, book_url, name):
    page = visit(new_page, f"{book_url}/{name}", javascript=False)
    assert page.locator("h1").is_visible()
    assert len(page.inner_text("main")) > 200


def test_images_load(new_page, book_url):
    page = visit(new_page, f"{book_url}/chapter-from-word.html")
    img = page.locator("figure img")
    img.scroll_into_view_if_needed()
    page.wait_for_function("document.querySelector('figure img').complete")
    assert page.evaluate("document.querySelector('figure img').naturalWidth") == 120


def test_wide_table_scrolls_on_its_own_and_takes_focus(new_page, book_url):
    page = visit(new_page, f"{book_url}/chapter-from-pdf.html", width=390)
    table = page.locator("table")
    table.focus()
    assert page.evaluate("document.activeElement.tagName") == "TABLE"
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("name", ["textbook.html", "chapter-from-pdf.html"])
def test_axe_finds_no_serious_problems(new_page, book_url, name, theme):
    axe_module = pytest.importorskip("axe_playwright_python.sync_playwright")
    page = visit(new_page, f"{book_url}/{name}?theme={theme}")
    results = axe_module.Axe().run(page)
    serious = [f"{v['id']}: {v['help']}" for v in results.response["violations"] if v["impact"] in {"serious", "critical"}]
    assert not serious, serious


def test_every_tab_stop_shows_a_focus_ring(new_page, book_url):
    page = visit(new_page, f"{book_url}/chapter-from-word.html")
    seen = set()
    for _ in range(60):
        page.keyboard.press("Tab")
        key = page.evaluate("document.activeElement === document.body ? null : document.activeElement.outerHTML.slice(0, 100)")
        if key is None or key in seen:
            break
        seen.add(key)
        ring = page.evaluate("""() => { for (let n = document.activeElement; n && n !== document.body; n = n.parentElement) {
            const s = getComputedStyle(n); if (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) return true; }
            return false; }""")
        assert ring, f"no focus ring on {key}"
    assert len(seen) > 5
