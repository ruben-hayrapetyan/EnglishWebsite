"""Keeping only the written content, and giving every chapter one shape.

Glass-box tests on the format-neutral Document (sections.py, structure.py),
so they hold for PDF, Word and Markdown chapters alike."""

from tools.textbook.model import Document, Figure, Heading, Image, ListBlock, ListItem, Paragraph, Run
from tools.textbook.sections import written_content, written_parts
from tools.textbook.structure import align_numbered, chapter_body, normalize_levels, tidy

B = frozenset({"strong"})
PROSE = "This is a sentence of real chapter text that goes on long enough to be prose. " * 3


def H(text, level=2):
    return Heading(level, [Run(text)])


def P(text, bold=False):
    return Paragraph([Run(text, B if bold else frozenset())])


def texts(doc):
    return [b.content[0].text if b.content else "" for b in doc.blocks]


def outline(doc):
    return [(b.level, "".join(r.text for r in b.content)) if isinstance(b, Heading)
            else "".join(r.text for r in b.content)[:20] for b in doc.blocks]


TEMPLATE = [
    H("UNIT AND CHAPTER: Sleep"), H("CONTRIBUTORS"), P("Ada, subject matter expert"),
    H("LEARNING OBJECTIVES"), P("1. Explain sleep"), H("CHAPTER OUTLINE"), P("Section: Intro"),
    H("CHAPTER WRITTEN CONTENT"), H("Introduction"), P(PROSE),
    H("CHAPTER ADD-INS"), P("A case study box"), H("GLOSSARY"), P("Sleep: rest"), H("REFERENCES"), P("Ada (2020)."),
]


def test_only_written_content_is_kept():
    assert texts(written_content(Document(TEMPLATE, "s"))) == ["Introduction", PROSE]


def test_chapters_not_written_to_the_template_are_untouched():
    doc = Document([H("Introduction"), P(PROSE), H("References"), P("Ada (2020).")], "s")
    assert written_content(doc) is doc


def test_each_authors_part_is_kept_in_order():
    blocks = [H("CONTRIBUTORS"), P("x", bold=True),
              P("CHAPTER WRITTEN CONTENT (Ben) : Sleep", bold=True), H("Ben's section"), P(PROSE),
              H("Works Cited"), P("Ben (2020)."), P("CHAPTER Outline (Joseph)", bold=True), P("- point"),
              P("CHAPTER WRITTEN OUTLINE (Sarah Kim): Caffeine"),  # not bold, still a content label
              H("Sarah's section"), P(PROSE), P("GLOSSARY", bold=True), P("term")]
    parts = written_parts(Document(blocks, "s"))
    assert [[t for t in texts(Document(part, "s"))] for part in parts] == [
        ["Ben's section", PROSE], ["Sarah's section", PROSE]]


def test_objectives_inside_the_text_pause_it_until_the_next_section():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Learning Objectives"), P("1. Describe chronotypes"),
              H("Introduction"), P(PROSE)]
    assert texts(written_content(Document(blocks, "s"))) == ["Introduction", PROSE]


def test_an_unlabelled_chapter_starts_at_the_first_heading_with_prose():
    blocks = [H("CONTRIBUTORS"), P("Clara"), P("Sections:", bold=True), H("Meal timing"), P("- hormones"),
              P("Vocab:", bold=True), P("Leptin: a hormone that " + "x" * 160), P("Citations:", bold=True),
              P("Young ER (2023)."), H("Overview"), P(PROSE)]
    assert texts(written_content(Document(blocks, "s"))) == ["Overview", PROSE]


def test_label_words_in_ordinary_text_are_not_labels():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Section 1: How the heart pumps blood"), P(PROSE),
              P("Our learning objectives: understand the heart and its rhythm."),  # a sentence
              H("UNIT: CIRCADIAN RHYTHMS"), P(PROSE + "!")]
    assert texts(written_content(Document(blocks, "s"))) == [
        "Section 1: How the heart pumps blood", PROSE, "Our learning objectives: understand the heart and its rhythm.",
        PROSE + "!"]


def test_a_paragraph_that_is_only_a_label_is_a_label_even_if_not_bold():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Intro"), P(PROSE), P("Learning Objectives:"), P("1. Describe it"),
              H("Next section"), P(PROSE)]
    assert texts(written_content(Document(blocks, "s"))) == ["Intro", PROSE, "Next section", PROSE]


def test_a_bold_label_that_runs_into_text_starts_that_part():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Intro"), P(PROSE),
              Paragraph([Run("CHAPTER ADD-INS", frozenset({"strong"})), Run(" Explanatory figure of hamsters.")]),
              P("More add-in text.")]
    assert texts(written_content(Document(blocks, "s"))) == ["Intro", PROSE]


def test_bold_lines_and_one_item_bold_lists_become_headings():
    blocks = [H("Top", 1), P("A bold subheading", bold=True), P(PROSE),
              ListBlock(True, [ListItem([Run("Neural activity is rhythmic", B)])]), P(PROSE),
              P("A bold sentence that ends.", bold=True), H("   ", 1)]
    doc = tidy(Document(blocks, "s"))
    assert [type(b).__name__ for b in doc.blocks] == ["Heading", "Heading", "Paragraph", "Heading", "Paragraph", "Paragraph"]
    assert doc.blocks[3].content[0].marks == frozenset()  # the heading's bold is implied


def test_a_wrapped_heading_is_joined_back_together():
    doc = tidy(Document([H("What Factors Drive the Periodic Cycles in Predator-Prey"), P("Systems?", bold=True), P(PROSE)], "s"))
    assert outline(doc)[0] == (2, "What Factors Drive the Periodic Cycles in Predator-Prey Systems?")


def test_levels_are_ranked_without_skips():
    doc = normalize_levels(Document([H("A", 1), H("B", 4), H("C", 4), H("D", 1), H("E", 6)], "s"))
    assert [b.level for b in doc.blocks] == [2, 3, 3, 2, 3]


def test_numbered_headings_share_a_level():
    doc = align_numbered(Document([H("1. What is serotonin?", 2), H("2. Its daily rhythm", 4), H("2.1 Detail", 2)], "s"))
    assert [b.level for b in doc.blocks] == [2, 2, 3]


def test_chapter_body_levels_each_part_and_drops_a_restated_title():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Unit: Infradian Rhythms Chapter: Breeding and Migration", 1),
              H("Seasons", 3), P(PROSE), H("CHAPTER WRITTEN CONTENT - John"), H("Migration", 1), P(PROSE)]
    doc = chapter_body(Document(blocks, "s"), "Breeding and migration")
    assert [x for x in outline(doc) if isinstance(x, tuple)] == [(2, "Seasons"), (2, "Migration")]


def test_figures_inside_the_text_stay():
    fig = Figure(Image(b"x", "png"), alt="")
    doc = written_content(Document([H("CHAPTER WRITTEN CONTENT"), H("Intro"), fig, P(PROSE), H("CHAPTER ADD-INS"),
                                    Figure(Image(b"y", "png"), alt="")], "s"))
    assert [type(b).__name__ for b in doc.blocks] == ["Heading", "Figure", "Paragraph"]


def test_text_resumes_after_inner_objectives_at_a_bold_line_or_prose():
    blocks = [H("CHAPTER WRITTEN CONTENT"), H("Factors"), P("Learning Objectives:"), P("1. Name the factors"),
              P(PROSE), P("Abiotic factors", bold=True), P("Rain matters.")]
    assert texts(written_content(Document(blocks, "s"))) == ["Factors", PROSE, "Abiotic factors", "Rain matters."]
