"""A tiny CSS scanner for the style-rule tests.

It is not a full CSS parser. It understands just enough of the site's plain
CSS (comments, nested at-rules, rule blocks, declarations) to answer
"which selectors exist" and "which declarations does this file contain".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

COMMENT = re.compile(r"/\*.*?\*/", re.S)


@dataclass(frozen=True)
class Rule:
    selector: str           # the prelude, e.g. ".card:hover" or "@font-face"
    context: tuple[str, ...]  # enclosing at-rules, outermost first
    declarations: tuple[tuple[str, str], ...]
    line: int


def strip_comments(css: str) -> str:
    # Keep newlines so line numbers stay accurate.
    return COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), css)


def _declarations(body: str) -> tuple[tuple[str, str], ...]:
    decls = []
    for chunk in body.split(";"):
        if ":" not in chunk:
            continue
        prop, value = chunk.split(":", 1)
        decls.append((prop.strip().lower(), value.strip()))
    return tuple(decls)


def rules(css: str) -> list[Rule]:
    """Return every leaf rule block (one that holds declarations)."""
    css = strip_comments(css)
    out: list[Rule] = []
    buf_start = 0
    i = 0
    while i < len(css):
        ch = css[i]
        if ch == "{":
            prelude = css[buf_start:i].strip()
            # Statement at-rules like @import end with ';' before this brace.
            prelude = prelude.rsplit(";", 1)[-1].strip()
            depth, j = 1, i + 1
            while j < len(css) and depth:
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
            body = css[i + 1 : j - 1]
            line = css.count("\n", 0, i) + 1
            if prelude.startswith("@") and "{" in body and not prelude.startswith(("@font-face", "@page")):
                out.extend(rules_with_offset(body, (prelude,), line - 1))
            else:
                out.append(Rule(prelude, (), _declarations(body), line))
            i = j
            buf_start = j
            continue
        if ch == "}":
            buf_start = i + 1
        i += 1
    return out


def rules_with_offset(css: str, context: tuple[str, ...], line_offset: int) -> list[Rule]:
    nested = rules(css)
    return [
        Rule(r.selector, context + r.context, r.declarations, r.line + line_offset)
        for r in nested
    ]


def selectors(rule: Rule) -> list[str]:
    return [s.strip() for s in rule.selector.split(",") if s.strip()]
