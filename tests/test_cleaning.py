"""Tests for app/cleaning.py: what gets stripped, what gets joined, how tables come out.

Every fixture is written out here rather than read from data/, so the tests pass on a
clone with no PDFs in it.
"""

from pathlib import Path

import pymupdf
import pytest

from app.cleaning import (
    Line,
    clean_text_lines,
    is_gazette_header,
    join_hyphenated,
    join_pages,
    page_lines_from_pdf,
    split_markdown_table,
    table_is_usable,
    table_to_markdown,
)

#: The gazette's running header, English form, with the page number inside the line.
HEADER_EN = "750                THE GAZETTE OF INDIA : EXTRAORDINARY           [PART II—SEC. 3(ii)]"
#: The same header, Hindi form, from a left-hand page. The zero-width joiners are real.
HEADER_HI = "[भाग II—खण्\u200dड  3(ii)]                    भारत\u200dका\u200dराजपत्र\u200d:\u200dअसाधारण                           649"


def test_the_english_header_is_matched_on_any_page() -> None:
    """The page number sits inside the header, so matching has to ignore the digits."""
    assert is_gazette_header(HEADER_EN)
    assert is_gazette_header(HEADER_EN.replace("750", "1144"))
    assert is_gazette_header("THE GAZETTE OF INDIA : EXTRAORDINARY")


def test_the_hindi_header_is_matched_too() -> None:
    """Left-hand pages carry the Hindi form of the same line."""
    assert is_gazette_header(HEADER_HI)
    assert is_gazette_header(HEADER_HI.replace("649", "1000"))


def test_a_clause_line_is_not_a_header() -> None:
    """Ordinary text that happens to name India must survive."""
    assert not is_gazette_header("4.2.1 Definitions")
    assert not is_gazette_header(
        "The Master Plan positions DDA as the lead agency in the capital of India."
    )


def test_cleaning_strips_headers_numbers_captions_and_dividers() -> None:
    """One page in, only the clause text out."""
    page = "\n".join(
        [
            HEADER_EN,
            "",
            "CHAPTER 4. SPATIAL DEVELOPMENT POLICIES",
            "4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)",
            "Transit-Oriented   Development  (TOD)  is  an  innovative  urban  paradigm.",
            "Illustration 6: Transit Oriented Development (TOD)",
            "(For illustrative purpose only)",
            "750",
            "",
        ]
    )
    assert clean_text_lines(page) == [
        "4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)",
        "Transit-Oriented Development (TOD) is an innovative urban paradigm.",
    ]


def test_hindi_divider_lines_go_only_when_asked() -> None:
    """Inside the gazette's English range a Devanagari line is a divider page's title."""
    page = "\n".join([HEADER_HI, "PART I: BACKGROUND", "भारतीय विकास प्राधिकरण का कार्य"])
    assert clean_text_lines(page, drop_hindi=True) == []
    assert clean_text_lines(page, drop_hindi=False) == ["भारतीय विकास प्राधिकरण का कार्य"]


def test_blank_lines_survive_but_never_two_in_a_row() -> None:
    """A blank line is a paragraph break the chunker splits on, so one is kept."""
    page = "First paragraph.\n\n\n\nSecond paragraph.\n"
    assert clean_text_lines(page) == ["First paragraph.", "", "Second paragraph."]


def test_a_word_broken_across_a_line_end_is_joined_and_keeps_its_hyphen() -> None:
    """"compact mixed-" + "use development" -> "compact mixed-use development" (D-017)."""
    lines = [
        Line("leveraging land through compact mixed-", 750),
        Line("use development.", 750),
    ]
    assert join_hyphenated(lines) == [
        Line("leveraging land through compact mixed-use development.", 750)
    ]


def test_joining_across_a_page_break_keeps_the_earlier_page() -> None:
    """A clause that wraps over a page break must still report where it started."""
    joined = join_hyphenated([Line("the permissible ground co-", 814), Line("verage shall", 815)])
    assert len(joined) == 1
    assert joined[0].page == 814
    assert joined[0].text == "the permissible ground co-verage shall"


def test_a_hyphen_before_a_capital_is_left_alone() -> None:
    """Only a lower-case continuation is a broken word; a heading end is not."""
    lines = [Line("Annexure 5 - List of Markets-", 918), Line("Sub-City Level", 918)]
    assert len(join_hyphenated(lines)) == 2


def test_table_quality_rules() -> None:
    """A table is rejected for too many empty cells or for having one column."""
    good = [["Sl. No.", "Use Premise", "Max. FAR"], ["1.", "Convenience Shopping", "150"]]
    assert table_is_usable(good)[0]

    one_column = [["Najafgarh Drain"], ["Palam Drain"]]
    assert not table_is_usable(one_column)[0]
    assert "column" in table_is_usable(one_column)[1]

    mostly_empty = [["Name", "Length", "Status"], ["CD-I", "", ""], ["", "", ""]]
    usable, reason = table_is_usable(mostly_empty)
    assert not usable
    assert "empty" in reason


def test_table_to_markdown_pads_ragged_rows_and_escapes_pipes() -> None:
    """Every markdown row needs the same number of pipes, and a cell pipe must not add one."""
    markdown = table_to_markdown([["Zone", "Max | FAR"], ["C1", "200"], ["C2"]])
    rows = markdown.split("\n")
    assert rows[0] == "| Zone | Max \\| FAR |"
    assert rows[1] == "| --- | --- |"
    assert rows[3] == "| C2 |  |"
    # count delimiters only: the escaped pipe inside a cell must not add a column
    delimiters = [row.replace(r"\|", "").count("|") for row in rows]
    assert delimiters == [3, 3, 3, 3]


def test_splitting_a_table_repeats_the_header_in_every_piece() -> None:
    """A piece retrieved on its own has to say what its columns mean."""
    markdown = table_to_markdown([["Zone", "FAR"]] + [[f"Z{n}", str(n)] for n in range(6)])
    pieces = split_markdown_table(markdown, max_rows=2)
    assert len(pieces) == 3
    for piece in pieces:
        assert piece.startswith("| Zone | FAR |\n| --- | --- |")
    assert sum(len(piece.split("\n")) - 2 for piece in pieces) == 6


@pytest.fixture
def table_pdf(tmp_path: Path) -> Path:
    """A one-page PDF with a drawn table and a line of text above and below it."""
    path = tmp_path / "TABLE_DOC.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 70), "4.2.3 TOD Norms", fontsize=11)
    top, left, row_height, column_width = 110, 60, 22, 120
    for row in range(3):
        for column in range(3):
            rect = pymupdf.Rect(
                left + column * column_width,
                top + row * row_height,
                left + (column + 1) * column_width,
                top + (row + 1) * row_height,
            )
            page.draw_rect(rect, color=(0, 0, 0), width=0.7)
            label = ["Zone", "FAR", "Height"][column] if row == 0 else f"r{row}c{column}"
            page.insert_text((rect.x0 + 4, rect.y1 - 7), label, fontsize=9)
    page.insert_text((60, 240), "Relaxations shall be allowed by the TOD Committee.", fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_a_table_page_comes_back_as_text_then_table_then_text(table_pdf: Path) -> None:
    """The table is markdown, the text around it is read in order, and nothing repeats."""
    with pymupdf.open(table_pdf) as doc:
        lines, warnings = page_lines_from_pdf(doc.load_page(0), 751)

    kinds = [("table" if line.is_table else "text") for line in lines if line.text]
    assert kinds == ["text", "table", "text"]
    assert all(line.page == 751 for line in lines)

    heading, table, closing = [line for line in lines if line.text]
    assert heading.text == "4.2.3 TOD Norms"
    assert table.text.startswith("| Zone | FAR | Height |")
    assert closing.text.startswith("Relaxations shall be allowed")
    # the table's own cells must not also appear as loose text
    assert not any(line.text.startswith("r1c0") for line in lines if not line.is_table)
    assert warnings == []


def test_a_page_with_no_tables_still_comes_back_clean(table_pdf: Path) -> None:
    """A page PyMuPDF finds no table on falls straight through to the text path."""
    with pymupdf.open(table_pdf) as doc:
        page = doc.load_page(0)
        page.clean_contents()
        lines, _ = page_lines_from_pdf(page, 751)
    assert any("TOD Norms" in line.text for line in lines)


# --- divider continuation lines (D-066) ----------------------------------------


def test_a_divider_title_spread_over_two_lines_goes_entirely() -> None:
    """"FOR RESIDENTIAL" under the chapter 7 divider is the rest of its title."""
    page = (
        "812   THE GAZETTE OF INDIA : EXTRAORDINARY   [PART II—SEC. 3(ii)]\n"
        "\n"
        " CHAPTER 7. DEVELOPMENT CONTROL NORMS (DCN)\n"
        "              FOR RESIDENTIAL"
    )
    assert clean_text_lines(page, drop_hindi=True) == []


def test_a_divider_title_survives_a_blank_line_in_the_middle() -> None:
    """Page 811 prints "PART III:" and "DEVELOPMENT CONTROL NORMS" with a gap between."""
    page = "PART III:\n\n      DEVELOPMENT CONTROL NORMS"
    assert clean_text_lines(page, drop_hindi=True) == []


def test_a_three_line_divider_title_goes_entirely() -> None:
    """Chapter 11's divider title runs over three lines."""
    page = (
        " CHAPTER 11. DEVELOPMENT CONTROL NORMS (DCN)\n"
        "       FOR TRANSPORTATION, UTILITIES AND\n"
        "               GOVERNMENT"
    )
    assert clean_text_lines(page, drop_hindi=True) == []


def test_a_contents_entry_in_title_case_does_not_open_a_divider_block() -> None:
    """Page 647 has "Part I: Background" inside 384 words of prose, which must survive."""
    page = (
        "Part I: Background\n"
        "THE PLAN sets out the context for Delhi in 2047.\n"
        "It then describes the existing scenario."
    )
    kept = clean_text_lines(page, drop_hindi=True)
    assert kept == [
        "THE PLAN sets out the context for Delhi in 2047.",
        "It then describes the existing scenario.",
    ]


def test_a_capitalised_sentence_after_a_divider_is_kept() -> None:
    """A capitals line that ends a sentence is text, not the rest of a title."""
    page = "PART I: BACKGROUND\nTHIS IS A REAL SENTENCE IN CAPITALS."
    assert clean_text_lines(page, drop_hindi=True) == ["THIS IS A REAL SENTENCE IN CAPITALS."]


def test_a_long_capitals_line_after_a_divider_is_kept() -> None:
    """Over ten words it is prose shouted in capitals, not a divider title."""
    shouting = "ALL DEVELOPMENT IN THE AREA SHALL BE SUBJECT TO THE NORMS LISTED BELOW"
    page = f"PART I: BACKGROUND\n{shouting}"
    assert clean_text_lines(page, drop_hindi=True) == [shouting]


def test_a_mixed_case_line_after_a_divider_closes_the_block() -> None:
    """Ordinary text ends the divider block, so later capitals lines are safe."""
    page = "PART I: BACKGROUND\nThe plan begins here.\nFOR RESIDENTIAL USE"
    assert clean_text_lines(page, drop_hindi=True) == [
        "The plan begins here.",
        "FOR RESIDENTIAL USE",
    ]


def test_punctuation_only_lines_are_dropped() -> None:
    """A rule of dashes or a stray bracket is OCR debris from the scanned documents."""
    page = "The report is enclosed.\n———————\n»\nSigned."
    assert clean_text_lines(page) == ["The report is enclosed.", "Signed."]


def test_a_line_with_a_single_letter_is_kept() -> None:
    """The punctuation rule is narrow on purpose: anything with a letter stays."""
    assert clean_text_lines("A\n1.") == ["A", "1."]


# --- joining a sentence across a page break (D-066) ----------------------------


def test_a_sentence_running_over_a_page_break_is_joined() -> None:
    """Page 643 of the gazette opens with "colonies, Rehabilitation Colonies, ..."."""
    joined = join_pages(
        [
            [Line("including DDA housing schemes, DDA plotted developments, resettlement", 642)],
            [Line("colonies, Rehabilitation Colonies and other planned developments.", 643)],
        ]
    )
    assert len(joined) == 1
    assert joined[0].text.startswith("including DDA housing schemes")
    assert "resettlement colonies, Rehabilitation" in joined[0].text


def test_a_joined_line_reports_both_pages() -> None:
    """The page range has to stay honest: it starts on 642 and ends on 643."""
    joined = join_pages([[Line("ends with", 642)], [Line("more words here.", 643)]])
    assert joined[0].page == 642
    assert joined[0].page_end == 643


def test_two_finished_sentences_keep_their_paragraph_break() -> None:
    """A full stop at the page foot means the pages are separate paragraphs."""
    joined = join_pages([[Line("A complete sentence.", 1)], [Line("Another one.", 2)]])
    assert [line.text for line in joined] == ["A complete sentence.", "", "Another one."]


def test_a_capitalised_word_starts_a_new_thought() -> None:
    """A heading has no full stop either, so the next page must start lower case."""
    joined = join_pages([[Line("4.2 Transit Oriented Development", 1)], [Line("Delhi shall.", 2)]])
    assert [line.text for line in joined] == ["4.2 Transit Oriented Development", "", "Delhi shall."]


def test_a_list_marker_is_never_joined_to_the_page_before() -> None:
    """"(ii) ..." opens an item however the previous page ended."""
    joined = join_pages([[Line("the following shall apply", 1)], [Line("(ii) parking norms", 2)]])
    assert len(joined) == 3


def test_a_continuation_word_is_joined_even_though_it_is_capitalised() -> None:
    """Page 683 really does open with "and seamlessly integrated ...", lower case."""
    joined = join_pages([[Line("shall be restored", 1)], [Line("And seamlessly integrated.", 2)]])
    assert len(joined) == 1


def test_a_table_is_never_joined_across_a_page_break() -> None:
    """A markdown table is one line already; concatenating it would destroy it."""
    table = Line("| a | b |\n| --- | --- |", 2, is_table=True)
    joined = join_pages([[Line("continues on", 1)], [table]])
    assert len(joined) == 3
    assert joined[-1].is_table


def test_join_pages_skips_empty_pages() -> None:
    """A divider page cleans down to nothing and must not leave two blank lines."""
    joined = join_pages([[Line("First page.", 1)], [], [Line("Third page.", 3)]])
    assert [line.text for line in joined] == ["First page.", "", "Third page."]


# --- empty table headers (D-066) -----------------------------------------------


def test_a_leading_empty_row_is_not_used_as_the_table_header() -> None:
    """PyMuPDF reads some top borders as a row of empty cells."""
    markdown = table_to_markdown([["", "", ""], ["2", "ACTION PLAN", ""], ["", "CIVIL", "ARMY"]])
    assert markdown.splitlines()[0] == "| 2 | ACTION PLAN |  |"
    assert markdown.splitlines()[1] == "| --- | --- | --- |"


def test_dropping_empty_rows_never_reorders_the_table() -> None:
    """Only leading rows go, so the header is still the first printed row with content."""
    markdown = table_to_markdown([["", ""], ["Zone", "FAR"], ["", "200"], ["D", "300"]])
    assert [line for line in markdown.splitlines()] == [
        "| Zone | FAR |",
        "| --- | --- |",
        "|  | 200 |",
        "| D | 300 |",
    ]


def test_a_table_of_nothing_but_empty_rows_keeps_one_row() -> None:
    """There is nothing to promote, and table_is_usable rejects it anyway."""
    assert table_to_markdown([["", ""], ["", ""]]).splitlines()[0] == "|  |  |"
    assert table_is_usable([["", ""], ["", ""]])[0] is False


def test_a_numbered_heading_after_a_divider_is_never_a_divider_tail() -> None:
    """"4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)" names itself, whatever sits above it."""
    page = "CHAPTER 4. SPATIAL DEVELOPMENT POLICIES\n4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)"
    assert clean_text_lines(page, drop_hindi=True) == ["4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)"]


def test_an_annexure_heading_after_a_divider_survives() -> None:
    """The annexure headings are capitalised too, and they name themselves."""
    page = "PART IV: ANNEXURES\nANNEXURE 9: LIST OF PERMISSIBLE HOUSEHOLD INDUSTRIES"
    assert clean_text_lines(page, drop_hindi=True) == [
        "ANNEXURE 9: LIST OF PERMISSIBLE HOUSEHOLD INDUSTRIES"
    ]
