"""Tests for textbook.json validation: every mistake gets a clear message."""

import json

import pytest

from book_helpers import book_manifest, write_manifest
from tools.textbook.manifest import ManifestError, load


def chapter(**kw):
    base = {"id": "one", "title": "One", "unit": "first", "authors": ["ada"]}
    base.update(kw)
    return base


def problems(site, data) -> list[str]:
    path = write_manifest(site, data)
    with pytest.raises(ManifestError) as info:
        load(path)
    return info.value.problems


def test_a_valid_manifest_loads_and_numbers_chapters(site):
    path = write_manifest(site, book_manifest([chapter(), chapter(id="two", title="Two", unit="second")]))
    book = load(path)
    assert [(c.id, c.number, c.filename) for c in book.chapters] == [
        ("one", 1, "chapter-one.html"), ("two", 2, "chapter-two.html")]
    assert book.unit("second").title == "Second unit"


def test_source_can_be_a_plain_path_or_an_object(site):
    (site / "textbook" / "sources" / "a.md").write_text("# A\n")
    data = book_manifest([chapter(source="sources/a.md"),
                          chapter(id="two", title="Two", source={"file": "sources/a.md", "heading": "A"})])
    book = load(write_manifest(site, data))
    assert book.chapters[0].source.file.name == "a.md"
    assert book.chapters[1].source.heading == "A"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.update(extra=1), 'unknown key "extra"'),
        (lambda d: d.update(title=""), '"title" must be a non-empty string'),
        (lambda d: d.update(highlight="missing"), '"highlight" must be words from the title'),
        (lambda d: d.update(units=[]), '"units" must be a non-empty list'),
        (lambda d: d["units"].append({"id": "first", "title": "Again"}), 'unit id "first" is used twice'),
        (lambda d: d["units"].append({"id": "Bad Id", "title": "X"}), "lowercase-hyphenated"),
        (lambda d: d["authors"].update({"Bad": "Name"}), 'authors: "Bad" must be lowercase-hyphenated'),
        (lambda d: d["chapters"].append(chapter()), "the id is used by two chapters"),
        (lambda d: d["chapters"].append(chapter(id="x", title="One")), 'the title "One" is used by two chapters'),
        (lambda d: d["chapters"].append(chapter(id="Not OK", title="Q")), "must never change"),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", unit="nope")), 'unit "nope" is not one of'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", authors=["zed"])), 'author "zed" is not in "authors"'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", authors=[])), "at least one author"),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", highlight="Z")), "words from its title"),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", summary="")), '"summary" must be a non-empty'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", figures={"f": {}})), '"figures" must look like'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", colour="red")), 'unknown key "colour"'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source="sources/none.pdf")), "does not exist"),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source="../../etc/passwd")), "inside the textbook/ folder"),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source={"file": "a.md", "pages": "1-2"})),
         '"pages" only works with PDF'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source={"file": "a.pdf", "pages": "one"})),
         '"pages" must look like'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source={"file": "a.md", "page": 1})),
         'unknown source key "page"'),
        (lambda d: d["chapters"].append(chapter(id="q", title="Q", source=5)), '"source" must be a file path'),
    ],
)
def test_each_mistake_is_reported(site, mutate, message):
    data = book_manifest([chapter()])
    mutate(data)
    assert any(message in p for p in problems(site, data)), problems(site, data)


def test_all_problems_are_reported_together(site):
    data = book_manifest([chapter(unit="nope", authors=["zed"])], title="")
    found = problems(site, data)
    assert len(found) >= 3
    assert "3 problem(s)" in str(ManifestError(site, found[:3]))


def test_unreadable_files_are_reported(site):
    path = site / "textbook" / "textbook.json"
    with pytest.raises(ManifestError, match="does not exist"):
        load(path)
    path.write_text("{ not json")
    with pytest.raises(ManifestError, match="not valid JSON"):
        load(path)
    path.write_text(json.dumps([1, 2]))
    with pytest.raises(ManifestError, match="top level must be an object"):
        load(path)
