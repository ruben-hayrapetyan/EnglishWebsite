"""Study kit quizzes: every option has a reason, readers see it after answering,
and the reasons stay readable with JavaScript off (AGENTS.md)."""

from __future__ import annotations

import re

import pytest

from site_helpers import ROOT, parse_page

KITS = sorted(p for p in ROOT.glob("study-*.html"))


def questions(path):
    doc = parse_page(path)
    for item in doc.xpath("//li[contains(@class,'quiz__item')]"):
        options = item.xpath("./ol[contains(@class,'quiz__options')]/li")
        if not options:
            continue  # number-answer question
        whys = item.xpath(".//ol[contains(@class,'quiz__whys')]/li")
        prompt = " ".join(item.xpath("string(./p[contains(@class,'quiz__question')])").split())
        yield prompt, options, whys, item


@pytest.mark.parametrize("kit", KITS, ids=lambda p: p.name)
def test_every_option_has_a_reason_inside_the_answer(kit):
    for prompt, options, whys, item in questions(kit):
        assert len(whys) == len(options), f"{kit.name}: {prompt!r} has {len(options)} options but {len(whys)} reasons"
        assert all(w.xpath("ancestor::details[contains(@class,'reveal')]") for w in whys), (
            f"{kit.name}: {prompt!r}: put .quiz__whys inside the answer, so it doesn't give the answer away")
        assert sum(1 for o in options if o.get("data-correct") is not None) == 1, f"{kit.name}: {prompt!r}"
        assert not item.xpath(".//*[@data-why]"), f"{kit.name}: move data-why text into .quiz__whys"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.e2e
@pytest.mark.parametrize("kit", KITS, ids=lambda p: p.name)
def test_a_wrong_answer_shows_why_it_is_wrong(new_page, site_url, kit):
    reasons = {}
    for prompt, options, whys, _ in questions(kit):
        reasons[prompt] = {norm(o.text_content()): (o.get("data-correct") is not None, norm(w.text_content()))
                           for o, w in zip(options, whys)}
    page = new_page()
    page.goto(f"{site_url}/{kit.name}", wait_until="networkidle")
    app = page.locator(".quiz__app")
    prompt = norm(app.locator(".quiz__prompt").inner_text())
    assert prompt in reasons, f"unknown question {prompt!r}"
    wrong_text, (_, why) = next((t, v) for t, v in reasons[prompt].items() if not v[0])
    app.locator(".quiz__option", has_text=wrong_text).click()
    app.locator(".quiz__segment", has_text="Certain").click()
    app.get_by_role("button", name="Check answer").click()
    feedback = app.locator(".quiz__feedback")
    assert "Not quite." in feedback.inner_text()
    assert why in norm(feedback.inner_text())
    assert page.errors == []


@pytest.mark.e2e
@pytest.mark.parametrize("kit", KITS, ids=lambda p: p.name)
def test_reasons_are_readable_without_javascript(new_page, site_url, kit):
    page = new_page(javascript=False)
    page.goto(f"{site_url}/{kit.name}", wait_until="networkidle")
    first = page.locator(".quiz__item").first
    reason = first.locator(".quiz__whys li").first
    assert not reason.is_visible()  # hidden until the reader asks for the answer
    first.locator(".reveal__summary").click()
    assert reason.is_visible() and len(reason.inner_text()) > 10
