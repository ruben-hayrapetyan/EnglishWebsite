"""The upload page, in a browser, against a fake GitHub API.

Playwright intercepts every request to api.github.com, so these tests check
exactly what the page asks GitHub to do, without touching the real repo.
"""

from __future__ import annotations

import base64
import json

import pytest

pytestmark = pytest.mark.e2e

PDF = b"%PDF-1.4 a pretend chapter"
TOKEN = "github_pat_test_token"


class FakeGitHub:
    def __init__(self, sources=(), fail=None):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.sources = list(sources)
        self.fail = fail  # (method, path suffix, status)

    def handle(self, route):
        request = route.request
        path = request.url.split("/repos/ruben-hayrapetyan/EnglishWebsite", 1)[1]
        body = json.loads(request.post_data) if request.post_data else None
        self.calls.append((request.method, path, body))
        assert request.headers.get("authorization") == f"Bearer {TOKEN}"
        if self.fail and request.method == self.fail[0] and path.startswith(self.fail[1]):
            return route.fulfill(status=self.fail[2], json={"message": "nope"})
        if request.method == "GET" and path == "/git/ref/heads/main":
            return route.fulfill(json={"object": {"sha": "abc123"}})
        if request.method == "GET" and path.startswith("/contents/textbook/sources"):
            return route.fulfill(json=[{"type": "file", "name": n, "path": f"textbook/sources/{n}", "sha": f"sha-{n}"}
                                       for n in self.sources])
        if request.method == "POST" and path == "/pulls":
            return route.fulfill(status=201, json={"html_url": "https://github.com/ruben-hayrapetyan/EnglishWebsite/pull/99"})
        return route.fulfill(status=201, json={})


def open_upload(new_page, site_url, fake):
    page = new_page()
    page.route("https://api.github.com/**", fake.handle)
    page.goto(f"{site_url}/upload.html", wait_until="networkidle")
    return page


def submit(page, scope="chapter", chapter="neuronal-activity", name="chapter.pdf"):
    page.locator(f'input[name="scope"][value="{scope}"]').check()
    if scope == "chapter":
        page.select_option("#upload-chapter", chapter)
    page.set_input_files("#upload-file", files=[{"name": name, "mimeType": "application/pdf", "buffer": PDF}])
    page.fill("#upload-token", TOKEN)
    page.get_by_role("button", name="Upload and open a pull request").click()
    page.wait_for_function("document.querySelector('[data-upload-status]').textContent.length > 20"
                           " && !document.querySelector('button[type=submit]').disabled")
    return page.locator("[data-upload-status]")


def test_a_chapter_upload_becomes_a_pull_request(new_page, site_url):
    fake = FakeGitHub(sources=["neuronal-activity.docx", "book.pdf", "README.md"])
    page = open_upload(new_page, site_url, fake)
    status = submit(page)
    assert "follow the pull request" in status.inner_text()
    assert status.locator("a").get_attribute("href").endswith("/pull/99")

    steps = [(m, p.split("?")[0]) for m, p, _ in fake.calls]
    assert steps[0] == ("GET", "/git/ref/heads/main")
    (method, _, branch_body) = fake.calls[1]
    assert method == "POST" and branch_body["sha"] == "abc123"
    branch = branch_body["ref"].removeprefix("refs/heads/")
    assert branch.startswith("upload/neuronal-activity-")
    # The earlier .docx of the same chapter is removed; other files are left alone.
    deletes = [(p, b) for m, p, b in fake.calls if m == "DELETE"]
    assert [p for p, _ in deletes] == ["/contents/textbook/sources/neuronal-activity.docx"]
    (put_path, put_body) = next((p, b) for m, p, b in fake.calls if m == "PUT")
    assert put_path == "/contents/textbook/sources/neuronal-activity.pdf"
    assert base64.b64decode(put_body["content"]) == PDF and put_body["branch"] == branch
    pr = next(b for m, p, b in fake.calls if m == "POST" and p == "/pulls")
    assert pr["head"] == branch and pr["base"] == "main"
    assert "Neuronal activity" in pr["title"]
    # The token is cleared and never kept in the browser.
    assert page.input_value("#upload-token") == ""
    assert TOKEN not in page.evaluate("JSON.stringify(localStorage) + JSON.stringify(sessionStorage)")
    assert page.errors == []


def test_the_whole_book_goes_to_book_pdf(new_page, site_url):
    fake = FakeGitHub(sources=["book.pdf"])
    page = open_upload(new_page, site_url, fake)
    page.locator('input[name="scope"][value="book"]').check()
    assert not page.locator("#upload-chapter").is_visible()
    submit(page, scope="book", name="whole-textbook.pdf")
    (put_path, put_body) = next((p, b) for m, p, b in fake.calls if m == "PUT")
    assert put_path == "/contents/textbook/sources/book.pdf"
    assert put_body["sha"] == "sha-book.pdf"  # replaces the earlier book
    assert not [c for c in fake.calls if c[0] == "DELETE"]


@pytest.mark.parametrize(
    "fail, message",
    [
        (("GET", "/git/ref/heads/main", 401), "didn't accept the token"),
        (("POST", "/git/refs", 403), "Contents and Pull requests"),
        (("PUT", "/contents/", 500), "couldn't upload the file"),
    ],
)
def test_github_errors_say_what_to_do(new_page, site_url, fail, message):
    page = open_upload(new_page, site_url, FakeGitHub(fail=fail))
    status = submit(page)
    assert message in status.inner_text()
    assert "upload__status--error" in status.get_attribute("class")


def test_wrong_file_type_is_refused_before_contacting_github(new_page, site_url):
    fake = FakeGitHub()
    page = open_upload(new_page, site_url, fake)
    status = submit(page, name="notes.txt")
    assert "Choose a PDF or Word" in status.inner_text()
    assert fake.calls == []


def test_without_javascript_the_page_explains_the_github_route(new_page, site_url):
    page = new_page(javascript=False)
    page.goto(f"{site_url}/upload.html", wait_until="networkidle")
    assert not page.locator("form[data-upload]").is_visible()
    link = page.get_by_role("link", name="upload the file on GitHub")
    assert link.get_attribute("href").endswith("/upload/main/textbook/sources")
