"""Tests for app/chunking.py: heading detection, the size rules, FAQ and court splitting.

The fixtures here are a handful of lines each, written out in the test, because the
rules they check are the ones that quietly go wrong on real data: a table cell read as
a heading, a clause cut in half, a page range that drifts.
"""

from app.chunking import (
    HARD_MAX_WORDS,
    _move_orphan_titles,
    MERGE_UNDER_WORDS,
    Section,
    assign_chunk_ids,
    chunk_faq,
    chunk_paragraph_document,
    fold_heading_only_sections,
    merge_small_sections,
    numbered_heading,
    page_span,
    render,
    sectionise,
    split_section,
)
from app.cleaning import Line


def chapter_of(number):
    """A chapter_of_page function that puts every page in the same chapter."""
    return lambda page: number


def heading(text: str, page: int = 750, chapter=4):
    """Run the heading detector over one line."""
    return numbered_heading(Line(text, page), chapter_of(chapter))


# --- heading detection ---------------------------------------------------------


def test_real_section_headings_are_found_at_every_depth() -> None:
    """N.N, N.N.N and N.N.N.N all count, and the clause number is the id."""
    assert heading("4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)").clause_id == "4.2"
    assert heading("4.2.1 Definitions").clause_id == "4.2.1"
    assert heading("4.2.1 Definitions").level == 3
    assert heading("4.10.2.1 Norms for Plotted Housing").clause_id == "4.10.2.1"


def test_the_first_number_has_to_be_the_chapter_number() -> None:
    """This is the rule that keeps decimals in 250 pages of norms tables out (D-019)."""
    assert heading("3.50 Ha of land shall be reserved", chapter=11) is None
    assert heading("2.0 Ha", page=844, chapter=10) is None
    assert heading("11.1 Transportation", page=851, chapter=11) is not None


def test_table_rows_and_measurements_are_not_headings() -> None:
    """A row of numbers, a lower-case continuation and a long line are all rejected."""
    assert heading("3.50 80.50 0.05", chapter=3) is None
    assert heading("8.9 subject to payment of use conversion charges.", chapter=8) is None
    assert heading("4.2 " + "word " * 40) is None


def test_service_plan_headings_have_their_own_guards() -> None:
    """With no chapter number to check, the number is capped and the title must be real."""
    service = "service_plans"
    assert heading("3.3 DETAILS OF MANAGEMENT OF PLASTIC WASTE", chapter=service) is not None
    assert heading("4.4 Timelines:", chapter=service) is not None
    # the drainage tables read as headings without these guards
    assert heading("5.90 Good NO NO RD-5900m to RD-0m", chapter=service) is None
    assert heading("19.7 RD", chapter=service) is None
    assert heading("45.31 Stable No NA", chapter=service) is None


# --- sections, merging and folding ---------------------------------------------


def lines_for(text: str, page: int = 750) -> list[Line]:
    """Turn a block of text into Line records on one page."""
    return [Line(line.strip(), page) for line in text.strip().split("\n")]


def test_text_before_the_first_heading_becomes_its_own_section() -> None:
    """A chapter's introduction has no clause number but must not be lost."""
    lines = lines_for(
        """
        Spatial development policies set out the plan's approach to growth.
        4.1 LAND POOLING
        Land pooling applies to the urbanisable areas of the zones listed below.
        """
    )
    sections = sectionise(lines, lambda line: heading(line.text), root_key="4")
    assert len(sections) == 2
    assert sections[0].clause_id is None
    assert sections[1].clause_id == "4.1"
    assert sections[0].parent_key == sections[1].parent_key == "4"


def test_a_short_section_merges_with_its_next_sibling_and_keeps_both_ids() -> None:
    """The merge rule, with both clause numbers recorded (D-020)."""
    small = Section("4.1.1", ["4.1.1"], ["4.1.1 Applicability"], "4.1", lines_for("4.1.1 Applicability"))
    sibling = Section(
        "4.1.2", ["4.1.2"], ["4.1.2 Guiding Principles"], "4.1", lines_for("word " * 100)
    )
    merged = merge_small_sections([small, sibling])
    assert len(merged) == 1
    assert merged[0].clause_ids == ["4.1.1", "4.1.2"]
    assert merged[0].clause_id == "4.1.1"


def test_merging_never_crosses_a_parent() -> None:
    """Two clauses under different parents are not siblings and stay apart."""
    small = Section("4.1.1", ["4.1.1"], ["4.1.1 Applicability"], "4.1", lines_for("short"))
    other = Section("4.2.1", ["4.2.1"], ["4.2.1 Definitions"], "4.2", lines_for("word " * 100))
    assert len(merge_small_sections([small, other])) == 2


def test_merging_stops_at_the_hard_maximum() -> None:
    """A small section is not merged into a sibling that is already nearly full."""
    small = Section("4.1.1", ["4.1.1"], ["4.1.1 Applicability"], "4.1", lines_for("short"))
    big = Section("4.1.2", ["4.1.2"], ["4.1.2 Norms"], "4.1", lines_for("word " * HARD_MAX_WORDS))
    assert len(merge_small_sections([small, big])) == 2


def test_a_heading_with_no_text_is_folded_into_its_child() -> None:
    """"11.1 Transportation" alone is a two-word chunk that says nothing (D-020)."""
    bare = Section("11.1", ["11.1"], ["11.1 Transportation"], "11", lines_for("11.1 Transportation"))
    bare.heading_only = True
    child = Section(
        "11.1.1",
        ["11.1.1"],
        ["11.1 Transportation", "11.1.1 Development Control Norms (DCN)"],
        "11.1",
        lines_for("word " * 600),
    )
    folded = fold_heading_only_sections([bare, child])
    assert len(folded) == 1
    assert folded[0].clause_ids == ["11.1", "11.1.1"]
    # folding has no size cap, unlike merging: the child is already over the hard maximum
    assert "11.1 Transportation" in render(folded[0].lines)


def test_folding_does_not_cross_into_another_chapter() -> None:
    """A dangling heading at the end of chapter 11 is not folded into chapter 12."""
    bare = Section("11.3", ["11.3"], ["11.3 Government"], "11", lines_for("11.3 Government"))
    bare.heading_only = True
    next_chapter = Section("12.1", ["12.1"], ["12.1 PSP"], "12", lines_for("word " * 100))
    assert len(fold_heading_only_sections([bare, next_chapter])) == 2


# --- splitting -----------------------------------------------------------------


def test_a_section_inside_the_limit_is_not_split() -> None:
    """Nothing is cut that does not have to be."""
    assert len(split_section(lines_for("word " * 300))) == 1


def test_an_oversized_section_is_split_at_sub_item_boundaries() -> None:
    """Sub-items are the first seam to cut on (D-020)."""
    lines = []
    for marker in ("(i)", "(ii)", "(iii)", "(iv)"):
        lines.append(Line(f"{marker} " + "word " * 200, 750))
        lines.append(Line("", 750))
    pieces = split_section(lines)
    assert len(pieces) > 1
    assert all(len(render(piece).split()) <= HARD_MAX_WORDS for piece in pieces)
    assert render(pieces[0]).startswith("(i)")


def test_a_single_huge_paragraph_is_split_by_sentences_with_overlap() -> None:
    """One paragraph has no seam, so sentences are used and a little text is repeated."""
    sentence = "The permissible floor area ratio shall not exceed two hundred in this zone. "
    pieces = split_section([Line(sentence * 40, 814)])
    assert len(pieces) > 1
    assert all(len(render(piece).split()) <= HARD_MAX_WORDS for piece in pieces)
    total = sum(len(render(piece).split()) for piece in pieces)
    assert total > len(sentence.split()) * 40  # the overlap means words are repeated


def test_a_scrap_left_by_a_split_is_put_back_on_the_piece_before_it() -> None:
    """A twelve-word tail means nothing without the list it closes (D-020)."""
    lines = [
        Line("(i) " + "word " * 400, 890),
        Line("", 890),
        Line("(ii) The above activities shall be subject to clearances.", 890),
    ]
    pieces = split_section(lines)
    assert all(len(render(piece).split()) >= MERGE_UNDER_WORDS for piece in pieces)
    assert "subject to clearances" in render(pieces[-1])


def test_a_split_keeps_the_page_range_of_each_piece() -> None:
    """A clause that crosses pages must report which pages each piece came from."""
    lines = []
    for page in (750, 751, 752):
        lines.append(Line("(i) " + "word " * 240, page))
        lines.append(Line("", page))
    spans = [page_span(piece) for piece in split_section(lines)]
    assert spans[0][0] == 750
    assert spans[-1][1] == 752
    assert all(start <= end for start, end in spans)


# --- the FAQ -------------------------------------------------------------------

FAQ_LINES = [
    Line("FAQs - GENERIC", 2),
    Line("Q1. Since when the MPD-2047 will be applicable?", 2),
    Line("MPD-2047 is in force from the date of its notification in the Official Gazette.", 2),
    Line("Q2. Does the provisions of MPD-2047 supersede the MPD-2021?", 2),
    Line("Yes, MPD-2047 supersedes the MPD-2021.", 2),
    Line("FAQs on High Density Corridor (HDC) Policy", 15),
    Line("Q1. What is a High Density Corridor (HDC) Zone?", 15),
    Line("The HDC Zone is an area comprising of compact, mixed-use development.", 15),
]


def test_the_faq_splits_one_chunk_per_question() -> None:
    """Each question travels with its own answer and nothing else."""
    sections = chunk_faq(FAQ_LINES)
    assert [section.clause_id for section in sections] == ["Q1", "Q2", "Q1"]
    assert "supersedes the MPD-2021" in render(sections[1].lines)
    assert "supersedes" not in render(sections[0].lines)


def test_the_faq_keeps_its_section_heading_in_the_path() -> None:
    """Both heading forms the document uses are recognised: "FAQs -" and "FAQs on"."""
    sections = chunk_faq(FAQ_LINES)
    assert sections[0].heading_path[0] == "FAQs - GENERIC"
    assert sections[2].heading_path[0] == "FAQs on High Density Corridor (HDC) Policy"
    assert sections[2].heading_path[1].startswith("Q1. What is a High Density Corridor")


def test_faq_question_numbers_repeat_so_the_chunk_id_uses_the_page() -> None:
    """Q1 appears in every FAQ section; the ids still have to be unique (D-021)."""
    ids = assign_chunk_ids("MPD47_FAQ", [("Q1", 2), ("Q2", 2), ("Q1", 15)])
    assert len(set(ids)) == 3
    assert ids[0] == "MPD47_FAQ:Q1@p2:0"
    assert ids[2] == "MPD47_FAQ:Q1@p15:0"
    assert ids[1] == "MPD47_FAQ:Q2:0"


def test_chunk_ids_count_the_pieces_of_one_section() -> None:
    """A section split into three pieces gives :0, :1, :2."""
    ids = assign_chunk_ids("MPD47_GAZETTE_EN", [("4.2.3", 751), ("4.2.3", 751), ("4.2.3", 751)])
    assert ids == [f"MPD47_GAZETTE_EN:4.2.3:{n}" for n in range(3)]


def test_a_chunk_with_no_clause_number_is_named_after_its_page() -> None:
    """The preamble and the maps captions have no numbering to use."""
    assert assign_chunk_ids("MPD47_GAZETTE_EN", [(None, 988)]) == ["MPD47_GAZETTE_EN:p988:0"]


# --- the court order and the NGT report -----------------------------------------


def test_numbered_court_paragraphs_become_clause_ids() -> None:
    """"3. Learned counsel ..." is paragraph 3 of the order.

    The real order's paragraphs run 46 to 109 words, all above the merge threshold, so
    each stays its own chunk; here they are padded to the same weight.
    """
    lines = []
    for number in (1, 2, 3):
        lines.append(Line(f"{number}. Learned counsel states that " + "word " * 60, 2))
        lines.append(Line("", 2))
    sections = chunk_paragraph_document(lines, "Delhi High Court order")
    assert [section.clause_id for section in sections] == ["1", "2", "3"]
    assert sections[0].heading_path == ["1."]


def test_short_numbered_court_paragraphs_merge_and_keep_every_id() -> None:
    """Three one-line paragraphs are siblings under the same parent, so they travel as one."""
    lines = [
        Line("1. Present writ petition has been filed by the petitioner seeking directions.", 2),
        Line("2. Learned counsel for petitioner states that the construction is illegal.", 2),
        Line("3. Learned counsel for the respondents admit that the floodplain is protected.", 2),
    ]
    sections = chunk_paragraph_document(lines, "Delhi High Court order")
    assert len(sections) == 1
    assert sections[0].clause_ids == ["1", "2", "3"]


def test_unnumbered_court_text_is_grouped_by_size_with_no_clause_id() -> None:
    """A cover page has no paragraph numbers, so the clause id stays empty."""
    lines = [Line("IN THE HIGH COURT OF DELHI AT NEW DELHI", 1), Line("word " * 300, 1)]
    sections = chunk_paragraph_document(lines, "Delhi High Court order")
    assert all(section.clause_id is None for section in sections)
    assert all(section.heading_path == ["Delhi High Court order"] for section in sections)


# --- heading folded into its own child (D-066) ---------------------------------


def test_an_annexure_heading_folds_into_its_lettered_child() -> None:
    """"Annexure 9" and "9a: Household Industries" share no dotted prefix.

    The child names its parent in `parent_key`, which is the relationship that matters;
    without reading it, the annexure heading stays a seven-word chunk of its own.
    """
    heading = Section(
        clause_id="Annexure 9",
        clause_ids=["Annexure 9"],
        heading_path=["Annexure 9: List of permissible Household Industries"],
        parent_key="annexures",
        lines=[Line("Annexure 9: List of permissible Household Industries", 947)],
        heading_only=True,
    )
    child = Section(
        clause_id="Annexure 9a",
        clause_ids=["Annexure 9a"],
        heading_path=["9a: Household Industries"],
        parent_key="Annexure 9",
        lines=[Line("9a: Household Industries", 948), Line("1. Agarbatti and similar products", 948)],
        heading_only=False,
    )
    folded = fold_heading_only_sections([heading, child])
    assert len(folded) == 1
    assert "Annexure 9: List of permissible" in render(folded[0].lines)
    assert folded[0].clause_ids == ["Annexure 9", "Annexure 9a"]


def test_a_heading_is_not_folded_into_a_sibling_annexure() -> None:
    """The parent test is an extra way in, not a way around the existing guards.

    Annexure 9's heading belongs to Annexure 9's content. Annexure 10 is the next
    annexure, not its child, so the heading is left where it is rather than being
    glued to the wrong list.
    """
    heading = Section(
        clause_id="Annexure 9",
        clause_ids=["Annexure 9"],
        heading_path=["Annexure 9: List"],
        parent_key="annexures",
        lines=[Line("Annexure 9: List", 947)],
        heading_only=True,
    )
    other = Section(
        clause_id="Annexure 10",
        clause_ids=["Annexure 10"],
        heading_path=["Annexure 10: Something else"],
        parent_key="annexures",
        lines=[Line("Annexure 10: Something else", 950), Line("Body text here.", 950)],
        heading_only=False,
    )
    folded = fold_heading_only_sections([heading, other])
    assert len(folded) == 2
    assert folded[0].clause_id == "Annexure 9"
    assert folded[1].clause_ids == ["Annexure 10"]


# --- a title stranded at the end of a chunk (D-066) ----------------------------


def test_a_table_title_at_the_end_of_a_chunk_moves_to_the_table() -> None:
    """"Table 2 Water Augmentation Action Plan" belongs with the table it introduces."""
    pieces = [
        [Line("Body text that fills the first chunk.", 995), Line("", 995), Line("Table 2 Water Augmentation Action Plan", 995)],
        [Line("| Source | MGD |\n| --- | --- |\n| Yamuna | 330 |", 996, is_table=True)],
    ]
    moved = _move_orphan_titles(pieces)
    assert len(moved) == 2
    assert "Table 2" not in render(moved[0].copy())
    assert moved[1][0].text == "Table 2 Water Augmentation Action Plan"


def test_a_finished_sentence_is_not_treated_as_a_title() -> None:
    """A full stop means it is the end of the chunk's own text."""
    pieces = [
        [Line("Body text.", 1), Line("", 1), Line("A complete closing sentence.", 1)],
        [Line("The next chunk.", 2)],
    ]
    assert _move_orphan_titles([list(piece) for piece in pieces]) == pieces


def test_a_long_trailing_line_is_not_treated_as_a_title() -> None:
    """Over fifteen words it is prose, whatever punctuation it ends with."""
    long_line = " ".join(["word"] * 20)
    pieces = [[Line("Body.", 1), Line("", 1), Line(long_line, 1)], [Line("Next.", 2)]]
    assert _move_orphan_titles([list(piece) for piece in pieces]) == pieces


def test_a_title_is_not_moved_out_of_the_last_chunk() -> None:
    """There is nothing after it to introduce."""
    pieces = [[Line("Body.", 1), Line("", 1), Line("Annexure 19B-i: Status of Drains", 1)]]
    assert _move_orphan_titles([list(piece) for piece in pieces]) == pieces


def test_a_title_is_not_moved_when_it_would_empty_its_chunk() -> None:
    """A chunk that is only a title is `fold_heading_only_sections`'s problem, not this one."""
    pieces = [[Line("", 1), Line("Table 3 Something", 1)], [Line("Next chunk.", 2)]]
    assert len(_move_orphan_titles([list(piece) for piece in pieces])) == 2


def test_a_title_is_not_moved_when_the_next_chunk_is_already_full() -> None:
    """The hard maximum stands; a stranded title is the lesser problem."""
    full = " ".join(["word"] * HARD_MAX_WORDS)
    pieces = [[Line("Body.", 1), Line("", 1), Line("Table 4 Title", 1)], [Line(full, 2)]]
    assert _move_orphan_titles([list(piece) for piece in pieces])[1][0].text == full


def test_a_title_must_be_its_own_paragraph_to_move() -> None:
    """A line attached to the paragraph above it is part of that paragraph."""
    pieces = [
        [Line("Body text here.", 1), Line("the rest of the sentence", 1)],
        [Line("Next.", 2)],
    ]
    assert _move_orphan_titles([list(piece) for piece in pieces]) == pieces
