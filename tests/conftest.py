"""Shared fixtures for every test suite.

The site is plain static files, so most fixtures just find files at the repo
root. The end-to-end fixtures serve the repo over HTTP on a random local port
and drive Chromium through Playwright.
"""

from __future__ import annotations

import functools
import http.server
import os
import threading
from pathlib import Path

import pytest

from site_helpers import ROOT


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


# ---- Local server for end-to-end tests -----------------------------------


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture(scope="session")
def site_url():
    handler = functools.partial(_QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            chromium = pw.chromium.launch()
        except Exception as exc:  # Chromium not installed locally
            if os.environ.get("CI"):
                raise
            pytest.skip(
                "Chromium for Playwright is missing. Run "
                "`.venv/bin/python -m playwright install chromium`. "
                f"({exc.__class__.__name__})"
            )
        yield chromium
        chromium.close()


FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


@pytest.fixture
def new_page(browser):
    """Open a fresh page. Web fonts are stubbed so tests run offline and
    deterministically. Console errors and uncaught exceptions are collected
    on page.errors."""
    contexts = []

    def make(*, width=1440, height=900, javascript=True, color_scheme="light"):
        context = browser.new_context(
            viewport={"width": width, "height": height},
            java_script_enabled=javascript,
            color_scheme=color_scheme,
        )
        contexts.append(context)

        def stub_fonts(route):
            if any(host in route.request.url for host in FONT_HOSTS):
                return route.fulfill(status=200, content_type="text/css", body="")
            return route.continue_()

        context.route("**/*", stub_fonts)
        page = context.new_page()
        page.errors = []
        page.on(
            "console",
            lambda msg: page.errors.append(msg.text) if msg.type == "error" else None,
        )
        page.on("pageerror", lambda exc: page.errors.append(str(exc)))
        return page

    yield make
    for context in contexts:
        context.close()
