"""Black-box tests of the build and the command line, on a temp copy of the site."""

import json
import shutil

import pytest

from book_helpers import ROOT, book_manifest, copy_site, sample_chapters, samples, write_manifest
from tools.textbook.__main__ import main
from tools.textbook.build import RECORD, build, stale, write


def test_build_writes_pages_images_and_a_record(sample_site):
    for name in ("textbook.html", "chapter-from-pdf.html", "chapter-from-word.html", "chapter-from-markdown.html",
                 "assets/img/chapter-from-pdf-figure-1.png"):
        assert (sample_site / name).is_file(), name
    assert not (sample_site / "chapter-not-written.html").exists()
    record = (sample_site / RECORD).read_text().split()
    assert "chapter-from-pdf.html" in record and "textbook.html" in record


def test_a_fresh_build_matches_what_is_on_disk(sample_site):
    assert stale(sample_site, build(sample_site)) == []


def test_build_is_deterministic(tmp_path):
    """Same inputs, two separate folders: byte-identical output."""
    outputs = []
    for name in ("one", "two"):
        root = copy_site((tmp_path / name).mkdir() or tmp_path / name)
        write_manifest(root, book_manifest(sample_chapters(root)))
        outputs.append(build(root).files)
    assert outputs[0].keys() == outputs[1].keys()
    for key in outputs[0]:
        assert outputs[0][key] == outputs[1][key], key


def test_editing_a_page_by_hand_is_detected(sample_site):
    page = sample_site / "chapter-from-pdf.html"
    page.write_text(page.read_text().replace("Measuring", "Hand-edited"))
    assert stale(sample_site, build(sample_site)) == ["chapter-from-pdf.html"]


def test_removed_chapter_files_are_cleaned_up(sample_site):
    data = json.loads((sample_site / "textbook/textbook.json").read_text())
    data["chapters"] = [c for c in data["chapters"] if c["id"] != "from-word"]
    write_manifest(sample_site, data)
    result = build(sample_site)
    assert "chapter-from-word.html (no longer generated)" in stale(sample_site, result)
    changed = write(sample_site, result)
    assert "chapter-from-word.html (removed)" in changed
    assert not (sample_site / "chapter-from-word.html").exists()
    assert not (sample_site / "assets/img/chapter-from-word-figure-1.png").exists()


def test_files_the_converter_did_not_make_are_never_removed(sample_site):
    mine = sample_site / "assets/img/chapter-mine.png"
    mine.write_bytes(b"x")
    write(sample_site, build(sample_site))
    assert mine.exists()


def test_errors_stop_the_build(site):
    write_manifest(site, book_manifest([{"id": "x", "title": "X", "unit": "nope", "authors": ["ada"]}]))
    result = build(site)
    assert result.errors and not result.files


def test_reader_errors_name_the_chapter(site):
    samples.scanned_pdf(site / "textbook/sources/scan.pdf")
    write_manifest(site, book_manifest([{"id": "scan", "title": "Scan", "unit": "first", "authors": ["ada"],
                                         "source": "sources/scan.pdf"}]))
    (error,) = build(site).errors
    assert error.startswith("scan: ") and "looks like a scan" in error


def test_alt_text_for_a_figure_that_does_not_exist_is_a_warning(sample_site):
    data = json.loads((sample_site / "textbook/textbook.json").read_text())
    data["chapters"][0]["figures"]["figure-9"] = {"alt": "Nothing"}
    write_manifest(sample_site, data)
    assert any('"figure-9"' in w for w in build(sample_site).warnings)


def test_add_on_pages_are_linked_only_when_they_exist(sample_site):
    page = (sample_site / "chapter-from-pdf.html").read_text()
    assert "author-ada.html" not in page and "study-from-pdf.html" not in page
    (sample_site / "author-ada.html").write_text("x")
    (sample_site / "study-from-pdf.html").write_text("x")
    write(sample_site, build(sample_site))
    page = (sample_site / "chapter-from-pdf.html").read_text()
    assert '<a href="author-ada.html">Ada Example</a>' in page
    assert '<a class="button" href="study-from-pdf.html">Practice with the study kit</a>' in page


def test_template_changes_reach_generated_pages(sample_site):
    """A script added to _template.html (as the accessibility branch does) appears on every page."""
    tpl = sample_site / "_template.html"
    tpl.write_text(tpl.read_text().replace(
        '  <link rel="stylesheet" href="assets/css/main.css">',
        '  <script src="assets/js/a11y.js"></script>\n  <link rel="stylesheet" href="assets/css/main.css">'))
    write(sample_site, build(sample_site))
    for name in ("textbook.html", "chapter-from-pdf.html"):
        assert '<script src="assets/js/a11y.js"></script>' in (sample_site / name).read_text()


# ---- Command line ------------------------------------------------------------


def run(capsys, *args):
    code = main(list(args))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_build_then_check(site, capsys):
    write_manifest(site, book_manifest(sample_chapters(site)))
    code, out, err = run(capsys, "build", "--root", str(site))
    assert code == 0 and "Wrote" in out and "warning:" in err
    assert run(capsys, "build", "--root", str(site))[1].startswith("Everything was already up to date")
    code, out, _ = run(capsys, "build", "--check", "--root", str(site))
    assert code == 0 and "up to date" in out


def test_cli_check_fails_when_stale(sample_site, capsys):
    (sample_site / "textbook.html").write_text("old")
    code, _, err = run(capsys, "build", "--check", "--root", str(sample_site))
    assert code == 1 and "Run `python -m tools.textbook build`" in err and "textbook.html" in err


def test_cli_strict_fails_on_warnings(sample_site, capsys):
    code, _, err = run(capsys, "build", "--strict", "--root", str(sample_site))
    assert code == 1 and "--strict" in err


def test_cli_errors_exit_2(site, capsys):
    code, _, err = run(capsys, "build", "--root", str(site))
    assert code == 2 and "error:" in err and "Nothing was written" in err


def test_cli_inspect_shows_headings(tmp_path, capsys):
    path = samples.book_pdf(tmp_path / "book.pdf")
    code, out, _ = run(capsys, "inspect", str(path))
    assert code == 0 and "h1  Chapter 1: First chapter" in out and "h2  Opening" in out
    code, out, _ = run(capsys, "inspect", str(samples.sample_docx(tmp_path / "s.docx")))
    assert "1 figures, 1 tables" in out


def test_cli_inspect_reports_reader_errors(tmp_path, capsys):
    code, _, err = run(capsys, "inspect", str(tmp_path / "missing.pdf"))
    assert code == 2 and "does not exist" in err


def test_cli_runs_as_a_module(sample_site):
    import subprocess
    import sys

    proc = subprocess.run([sys.executable, "-m", "tools.textbook", "build", "--check", "--root", str(sample_site)],
                          cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
