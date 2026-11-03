"""Glass-box tests for tools/textbook/normalize.py: the pure text helpers."""

import pytest

from tools.textbook.model import Run
from tools.textbook.normalize import (
    IdAllocator,
    caption_label,
    clean_runs,
    clean_text,
    comparable,
    ends_sentence,
    hyphenated_vocabulary,
    join_lines,
    line_joint,
    list_marker,
    slugify,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ﬁrst ﬂow", "first flow"),          # ligatures
        ("eﬀect oﬃce", "effect office"),
        ("cir­cadian", "circadian"),              # soft hyphen
        ("a b c", "a b c"),                   # no-break and thin spaces
        ("a \t\n  b", "a b"),                           # whitespace runs
        ("zero​width﻿", "zerowidth"),
        ("café", "café"),                    # NFC composes accents
        ("bell\x07", "bell"),                           # control characters
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_clean_text_keeps_ends_and_curly_quotes():
    assert clean_text(" “quoted” ") == " “quoted” "


def test_clean_runs_collapses_spaces_across_runs_and_trims():
    runs = [Run("  A "), Run(" bold", frozenset({"strong"})), Run(" word  ")]
    assert clean_runs(runs) == [Run("A "), Run("bold", frozenset({"strong"})), Run(" word")]


def test_clean_runs_merges_matching_runs_and_drops_empty():
    assert clean_runs([Run("a"), Run(""), Run("b")]) == [Run("ab")]


@pytest.mark.parametrize(
    "text, slug",
    [
        ("Measuring a period", "measuring-a-period"),
        ("Neuronal activity: spikes & LFPs", "neuronal-activity-spikes-lfps"),
        ("Café résumé", "cafe-resume"),
        ("  --Weird--  ", "weird"),
        ("3.1 Results", "section-3-1-results"),   # ids can't start with a digit
        ("!!!", "section"),
        ("x" * 80, "x" * 60),
    ],
)
def test_slugify(text, slug):
    assert slugify(text) == slug


def test_id_allocator_makes_unique_ids_and_respects_reserved():
    ids = IdAllocator({"main"})
    assert [ids.take("main"), ids.take("summary"), ids.take("summary"), ids.take("summary")] == [
        "main-2", "summary", "summary-2", "summary-3"]


@pytest.mark.parametrize(
    "a, b, vocab, joined",
    [
        ("the circa-", "dian clock", set(), "the circadian clock"),          # split word
        ("a self-", "sustained rhythm", {"self-sustained"}, "a self-sustained rhythm"),  # real hyphen
        ("pages 10-", "12 show", set(), "pages 10-12 show"),                # number range
        ("the end.", "Next", set(), "the end. Next"),
        ("cir­", "cadian", set(), "circadian"),                         # soft hyphen
        ("Ultra-", "Long", set(), "Ultra- Long"),                            # capital: not a split word
        ("", "only", set(), "only"),
        ("only", "", set(), "only"),
    ],
)
def test_join_lines(a, b, vocab, joined):
    assert join_lines(a, b, frozenset(vocab)) == joined


def test_line_joint_reports_what_to_drop():
    assert line_joint("circa-", "dian", frozenset()) == (1, "")
    assert line_joint("self-", "aware", frozenset({"self-aware"})) == (1, "-")
    assert line_joint("word", "next", frozenset()) == (0, " ")


def test_hyphenated_vocabulary_ignores_line_end_hyphens():
    vocab = hyphenated_vocabulary(["a self-sustained loop", "the circa-", "well-known and peer-reviewed"])
    assert vocab == {"self-sustained", "well-known", "peer-reviewed"}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Figure 3. A wave.", ("figure", "Figure 3", "A wave.")),
        ("Fig. 2.1: Spikes", ("figure", "Figure 2.1", "Spikes")),
        ("FIGURE A1 — Bands", ("figure", "Figure A1", "Bands")),
        ("Table 4 Periods", ("table", "Table 4", "Periods")),
        ("Figures show", None),
        ("The figure 3 shows", None),
    ],
)
def test_caption_label(text, expected):
    assert caption_label(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("• item", (False, 1, 2)),
        ("○ second level", (False, 1, 2)),
        ("■ third level", (False, 1, 2)),
        ("- item", (False, 1, 2)),
        ("3. step", (True, 3, 3)),
        ("(2) step", (True, 2, 4)),
        ("b) step", (True, 1, 3)),
        ("iv. step", (True, 1, 4)),
        ("2020 was a year", None),
        ("Plain text", None),
    ],
)
def test_list_marker(text, expected):
    assert list_marker(text) == expected


@pytest.mark.parametrize("text", ["Done.", "Really?", "Wait!", "as follows:", "said “yes.”", "(see above.)"])
def test_ends_sentence(text):
    assert ends_sentence(text)


@pytest.mark.parametrize("text", ["and then", "the circa-", "e.g", "items,"])
def test_does_not_end_sentence(text):
    assert not ends_sentence(text)


@pytest.mark.parametrize(
    "a, b",
    [
        ("Chapter 3: Sleep, caffeine and jet lag", "Sleep, caffeine & jet lag"),
        ("3. Chronotypes", "chronotypes"),
        ("Hair growth/shedding", "Hair growth shedding"),
    ],
)
def test_comparable_ignores_numbering_case_and_punctuation(a, b):
    assert comparable(a) == comparable(b)


def test_paths_broken_after_a_slash_rejoin_without_a_space():
    assert join_lines("change to /usr/", "bin now", frozenset()) == "change to /usr/bin now"
    assert join_lines("see https://example.org/", "docs", frozenset()) == "see https://example.org/docs"
    assert join_lines("either a/", "/b", frozenset()) == "either a/ /b"


def test_strip_invisible_keeps_soft_hyphens():
    from tools.textbook.normalize import strip_invisible

    assert strip_invisible("●​ Item‎﻿") == "● Item"
    assert strip_invisible("cir­") == "cir­"
