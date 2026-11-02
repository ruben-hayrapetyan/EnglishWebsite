"""Tests for the test helper: if the scanner misreads CSS, the rule tests
would pass silently. These pin down the cases the rules depend on."""

from cssscan import rules, selectors, strip_comments
from test_css_rules import DURATION, RAW_VALUE, is_bare, raw_parts


def test_reads_plain_rules_with_line_numbers():
    css = ".a { color: var(--x); }\n\n.b, .c:hover { gap: 0 }"
    found = rules(css)
    assert [r.selector for r in found] == [".a", ".b, .c:hover"]
    assert found[0].declarations == (("color", "var(--x)"),)
    assert [r.line for r in found] == [1, 3]
    assert selectors(found[1]) == [".b", ".c:hover"]


def test_reads_rules_inside_media_queries():
    css = "@media (min-width: 40rem) {\n  .a { gap: 0; }\n  .b { gap: 1; }\n}"
    found = rules(css)
    assert [r.selector for r in found] == [".a", ".b"]
    assert all(r.context == ("@media (min-width: 40rem)",) for r in found)
    assert [r.line for r in found] == [2, 3]


def test_font_face_is_a_leaf_not_a_context():
    found = rules('@font-face { font-family: "X"; src: url(x.woff2); }')
    assert found[0].selector == "@font-face"


def test_skips_statement_at_rules_before_a_block():
    found = rules('@import url("a.css");\n.a { gap: 0 }')
    assert [r.selector for r in found] == [".a"]


def test_comments_are_removed_but_lines_kept():
    css = "/* #fff\n 4px */\n.a{}"
    assert strip_comments(css) == "\n\n.a{}"
    assert not RAW_VALUE.search(strip_comments(css))


def test_raw_value_pattern_catches_each_kind():
    for bad in ("#fff", "#1d6b57", "12px", "rgb(0 0 0)", "rgba(0,0,0,.5)", "hsl(1 2% 3%)"):
        assert RAW_VALUE.search(bad), bad
    for ok in ("var(--space-s)", "1rem", "50%", "#main-title"[:0]):
        assert not RAW_VALUE.search(ok), ok


def test_bare_selector_detection():
    assert is_bare("body")
    assert is_bare("h2 + p")
    assert not is_bare(".prose h2")
    assert not is_bare("[data-open] a")


def test_raw_parts_allows_composed_tokens_and_zeros():
    assert raw_parts("0 0 0 var(--space-3xs) var(--color-accent-soft)") == []
    assert raw_parts("inset 0 0 0 var(--border-width) var(--color-accent)") == []
    assert raw_parts("var(--radius-s) var(--radius-m)") == []
    assert raw_parts("calc(var(--radius-m) * 2)") == ["*", "2"]
    assert raw_parts("0.2em 0.5em") == ["0.2em", "0.5em"]
    assert raw_parts("0 4px 8px black") == ["4px", "8px", "black"]


def test_duration_pattern_skips_zero():
    assert not DURATION.search("visibility 0s linear var(--duration-base)")
    assert DURATION.search("opacity 300ms")
    assert DURATION.search("opacity .2s")
