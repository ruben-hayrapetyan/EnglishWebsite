"""Command line: python -m tools.textbook <command>

    build            convert every chapter that has a source and write the pages
    build --check    write nothing; exit 1 if the committed pages are out of date
    build --strict   exit 1 if there are any warnings (missing alt text, etc.)
    inspect FILE     print the headings and page count the converter sees in a
                     source file, to help fill in "heading" or "pages"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build, stale, write
from .model import Figure, Heading, ListBlock, Paragraph, Table, plain_text
from .readers import ReaderError, read

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.textbook", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="convert sources and write the textbook pages")
    b.add_argument("--check", action="store_true", help="exit 1 if the pages on disk are out of date")
    b.add_argument("--strict", action="store_true", help="treat warnings as errors")
    b.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    i = sub.add_parser("inspect", help="show what the converter sees in a source file")
    i.add_argument("file", type=Path)
    i.add_argument("--pages", help='PDF page range, like "12-30"')
    args = parser.parse_args(argv)

    if args.command == "inspect":
        return inspect(args.file, args.pages)

    result = build(args.root)
    for message in result.errors:
        print(f"error: {message}", file=sys.stderr)
    if result.errors:
        print("Nothing was written. Fix the errors above and run the build again.", file=sys.stderr)
        return 2
    for message in result.warnings:
        print(f"warning: {message}", file=sys.stderr)

    if args.check:
        out_of_date = stale(args.root, result)
        if out_of_date:
            print("The textbook pages are out of date. Run `python -m tools.textbook build` "
                  "and commit the result. Out of date:", file=sys.stderr)
            for name in out_of_date:
                print(f"  {name}", file=sys.stderr)
            return 1
        print("Textbook pages are up to date.")
    else:
        changed = write(args.root, result)
        print(f"Wrote {len(changed)} file(s)." if changed else "Everything was already up to date.")
        for name in changed:
            print(f"  {name}")
    if args.strict and result.warnings:
        print(f"{len(result.warnings)} warning(s), and --strict was given.", file=sys.stderr)
        return 1
    return 0


def inspect(path: Path, pages: str | None) -> int:
    try:
        doc = read(path, pages)
    except ReaderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    counts = {"paragraphs": 0, "lists": 0, "figures": 0, "tables": 0}
    print(f"{path.name}: headings the converter found")
    for block in doc.blocks:
        if isinstance(block, Heading):
            print(f"  {'  ' * (block.level - 1)}h{block.level}  {plain_text(block.content)}")
        elif isinstance(block, Paragraph):
            counts["paragraphs"] += 1
        elif isinstance(block, ListBlock):
            counts["lists"] += 1
        elif isinstance(block, Figure):
            counts["figures"] += 1
        elif isinstance(block, Table):
            counts["tables"] += 1
    print("  " + ", ".join(f"{n} {k}" for k, n in counts.items()) + f", {len(doc.notes)} footnotes")
    for message in doc.warnings:
        print(f"warning: {message}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
