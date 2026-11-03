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


# ---- A whole book compiled from several authors (see samples.compiled_book_pdf) ----

import pytest  # noqa: E402

from tools.textbook.split import find_chapters  # noqa: E402


@pytest.fixture
def compiled(site):
    write_manifest(site, book_manifest(samples.COMPILED_CHAPTERS))
    samples.compiled_book_pdf(site / "textbook/sources/book.pdf")
    result = build(site)
    assert not result.errors, result.errors
    return result


def page(result, cid):
    return result.files[f"chapter-{cid}.html"].decode()


def test_chapters_are_found_by_their_title_lines_not_the_contents_page(site):
    path = samples.compiled_book_pdf(site / "book.pdf")
    ranges, missing = find_chapters(path, {c["id"]: c["title"] for c in samples.COMPILED_CHAPTERS})
    assert {cid: r.pages for cid, r in ranges.items()} == {
        "first-topic": "2-3", "second-topic": "3-3", "third-topic": "3-3"}
    assert missing == ["fourth-topic"]


def test_each_chapter_gets_only_its_own_text(compiled):
    first, second, third = page(compiled, "first-topic"), page(compiled, "second-topic"), page(compiled, "third-topic")
    assert "The topic ends after the figure." in first and "second topic." not in first
    assert "More text about the second topic." in second and "third topic." not in second
    assert "Text that belongs to the third topic." in third
    assert "Chapter X:" not in first and "Chapter 4:" not in second and "UNIT AND CHAPTER" not in third
    assert "chapter-fourth-topic.html" not in compiled.files
    assert any(w.startswith("fourth-topic: not found in book.pdf") for w in compiled.warnings)


def test_double_spaced_lines_stay_one_paragraph(compiled):
    assert ("<p>The first paragraph of the first topic runs over three double spaced lines and is still one "
            "paragraph until it ends here.</p>") in page(compiled, "first-topic")


def test_captions_above_and_below_figures_are_paired(compiled):
    assert "<figcaption><strong>Figure 1.</strong> A picture with its caption above it.</figcaption>" in page(compiled, "first-topic")
    # The bold title between the image and its caption joins the caption.
    assert ("<figcaption><strong>Figure 2.</strong> A bold title for the figure. "
            "A caption below the figure and its title.</figcaption>") in page(compiled, "second-topic")
    assert not any("no figure near it" in w for w in compiled.warnings)


def test_a_template_book_gives_uniform_chapters_with_only_their_written_content(site):
    write_manifest(site, book_manifest(samples.TEMPLATE_CHAPTERS))
    samples.template_book_pdf(site / "textbook/sources/book.pdf")
    result = build(site)
    assert not result.errors, result.errors
    first, second = page(result, "first-topic"), page(result, "second-topic")
    assert ('<h2 id="background">Background</h2>' in first
            and "The first topic is written content that readers should see on the site, and it runs" in first)
    for leftover in ("CONTRIBUTORS", "LEARNING OBJECTIVES", "Explain the first topic", "add-in figure",
                     "Rhythm: something", "Ada (2020)", "<figure"):
        assert leftover not in first, leftover
    assert second.index("Ben&#x27;s part") < second.index("Cy&#x27;s part") if "&#x27;" in second else \
        second.index("Ben's part") < second.index("Cy's part")
    for leftover in ("Describe the second topic", "Works Cited", "Cy's plan", "Ben (2021)", "Cy (2022)", "Unit:"):
        assert leftover not in second, leftover
    assert '<h2 id="ben-s-part">' in second and '<h2 id="cy-s-part">' in second  # each part levelled the same
