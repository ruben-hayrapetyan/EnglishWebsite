"""Sources found by file name: what the upload page relies on.

The upload page (and anyone using GitHub's own upload) only puts a file in
textbook/sources; nothing edits textbook.json. These tests drive the real
build with files named that way.
"""


from book_helpers import book_manifest, samples, write_manifest
from tools.textbook.build import build, write
from tools.textbook.regions import Book, fill
from tools.textbook.manifest import load


def chapters():
    return [
        {"id": "first-chapter", "title": "First chapter", "unit": "first", "authors": ["ada"]},
        {"id": "second-chapter", "title": "Second chapter", "unit": "first", "authors": ["ben"]},
        {"id": "missing-chapter", "title": "A chapter the book lacks", "unit": "second", "authors": ["cy"]},
    ]


def test_a_file_named_after_a_chapter_becomes_that_chapter(site):
    write_manifest(site, book_manifest(chapters()))
    samples.sample_markdown(site / "textbook/sources/second-chapter.md")
    result = build(site)
    assert not result.errors
    assert "chapter-second-chapter.html" in result.files
    assert "chapter-first-chapter.html" not in result.files


def test_a_whole_book_is_split_into_chapters_by_heading(site):
    write_manifest(site, book_manifest(chapters()))
    samples.book_pdf(site / "textbook/sources/book.pdf")  # "Chapter 1: First chapter", "Chapter 2: Second chapter"
    result = build(site)
    assert not result.errors
    first = result.files["chapter-first-chapter.html"].decode()
    second = result.files["chapter-second-chapter.html"].decode()
    assert "Text that belongs to the first chapter." in first and "second chapter." not in first
    assert "Text that belongs to the second chapter." in second
    assert "chapter-missing-chapter.html" not in result.files
    assert any(w.startswith("missing-chapter: not found in book.pdf") for w in result.warnings)


def test_a_chapter_file_wins_over_the_whole_book(site):
    write_manifest(site, book_manifest(chapters()))
    samples.book_pdf(site / "textbook/sources/book.pdf")
    samples.sample_markdown(site / "textbook/sources/first-chapter.md")
    page = build(site).files["chapter-first-chapter.html"].decode()
    assert "Measuring a period" in page and "Text that belongs to the first chapter." not in page


def test_textbook_json_wins_over_file_names(site):
    data = book_manifest(chapters())
    samples.sample_markdown(site / "textbook/sources/elsewhere.md")
    data["chapters"][0]["source"] = {"file": "sources/elsewhere.md", "heading": samples.TITLE}
    write_manifest(site, data)
    samples.book_pdf(site / "textbook/sources/first-chapter.pdf")
    assert "Measuring a period" in build(site).files["chapter-first-chapter.html"].decode()


def test_two_files_for_one_chapter_is_an_error(site):
    write_manifest(site, book_manifest(chapters()))
    samples.sample_markdown(site / "textbook/sources/first-chapter.md")
    samples.book_pdf(site / "textbook/sources/first-chapter.pdf")
    (error,) = build(site).errors
    assert 'more than one file for "first-chapter"' in error and "Keep one." in error


def test_replacing_an_upload_rebuilds_the_chapter(site):
    write_manifest(site, book_manifest(chapters()))
    src = site / "textbook/sources/first-chapter.md"
    samples.sample_markdown(src)
    write(site, build(site))
    src.unlink()
    samples.book_pdf(site / "textbook/sources/book.pdf")
    write(site, build(site))
    assert "Text that belongs to the first chapter." in (site / "chapter-first-chapter.html").read_text()


def test_chapter_options_region_lists_every_chapter(site):
    write_manifest(site, book_manifest(chapters()))
    book = Book(load(site / "textbook/textbook.json"), site, available={"second-chapter"})
    out = fill("<select>\n  <!-- textbook:chapter-options -->\n  <!-- /textbook -->\n</select>", book)
    assert '<option value="first-chapter">Chapter 1: First chapter</option>' in out
    assert '<option value="second-chapter">Chapter 2: Second chapter (on the site)</option>' in out
