"""Tests for app/extract.py, run against a tiny PDF built on the spot."""

from pathlib import Path

import pymupdf
import pytest

from app.extract import (
    devanagari_ratio,
    extract_document,
    find_repeated_lines,
    looks_scanned,
    parse_page_bound,
    select_pages,
    write_pages_jsonl,
)

FIRST_PAGE_TEXT = "Floor area ratio shall not exceed 200 in this zone."


@pytest.fixture
def two_page_pdf(tmp_path: Path) -> Path:
    """A PDF with text on page 1 and nothing at all on page 2."""
    path = tmp_path / "TEST_DOC.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), FIRST_PAGE_TEXT, fontsize=11)
    doc.new_page()  # left blank on purpose
    doc.save(path)
    doc.close()
    return path


def test_pages_start_at_one(two_page_pdf: Path) -> None:
    """Page numbers follow the PDF reader, so the first page is 1 and not 0."""
    result = extract_document(two_page_pdf, "TEST_DOC")
    assert [page.page for page in result.pages] == [1, 2]
    assert result.pdf_page_count == 2
    assert result.errors == []


def test_text_is_found_on_the_first_page(two_page_pdf: Path) -> None:
    """The text we wrote into page 1 comes back out of page 1."""
    result = extract_document(two_page_pdf, "TEST_DOC")
    first = result.pages[0]
    assert FIRST_PAGE_TEXT in first.text
    assert first.n_words == len(FIRST_PAGE_TEXT.split())
    assert first.n_chars == len(FIRST_PAGE_TEXT)
    assert first.likely_scanned is False


def test_blank_page_counts_as_empty(two_page_pdf: Path) -> None:
    """The blank page has no characters, no words, and is flagged as likely scanned."""
    result = extract_document(two_page_pdf, "TEST_DOC")
    blank = result.pages[1]
    assert blank.n_chars == 0
    assert blank.n_words == 0
    assert blank.text.strip() == ""
    assert blank.likely_scanned is True


def test_page_range_keeps_the_original_page_numbers(two_page_pdf: Path) -> None:
    """Reading from page 2 gives one record, still numbered 2, with page 1 counted as skipped."""
    result = extract_document(two_page_pdf, "TEST_DOC", page_start=2)
    assert [page.page for page in result.pages] == [2]
    assert result.skipped_pages == 1


def test_missing_file_is_reported_not_raised(tmp_path: Path) -> None:
    """A file that cannot be opened gives an error message and no pages."""
    result = extract_document(tmp_path / "NOPE.pdf", "NOPE")
    assert result.pages == []
    assert len(result.errors) == 1
    assert "cannot open" in result.errors[0]


def test_jsonl_has_one_line_per_page(two_page_pdf: Path, tmp_path: Path) -> None:
    """pages.jsonl holds one JSON object per page."""
    result = extract_document(two_page_pdf, "TEST_DOC", find_tables=False)
    out = tmp_path / "out" / "pages.jsonl"
    written = write_pages_jsonl([result], out)
    assert written == 2
    assert len(out.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_select_pages_handles_blank_bounds() -> None:
    """Blank page_start means page 1 and blank page_end means the last page."""
    assert list(select_pages(5)) == [1, 2, 3, 4, 5]
    assert list(select_pages(5, page_start=3)) == [3, 4, 5]
    assert list(select_pages(5, page_end=2)) == [1, 2]
    assert list(select_pages(5, page_start=2, page_end=3)) == [2, 3]
    assert list(select_pages(5, page_start=9)) == []


def test_parse_page_bound() -> None:
    """A blank cell means no bound; anything that is not a page number is an error."""
    assert parse_page_bound("", "page_start") is None
    assert parse_page_bound("640", "page_start") == 640
    with pytest.raises(ValueError):
        parse_page_bound("0", "page_start")
    with pytest.raises(ValueError):
        parse_page_bound("ten", "page_start")


def test_devanagari_ratio() -> None:
    """The ratio counts Devanagari characters against the non-space characters."""
    assert devanagari_ratio("") == 0.0
    assert devanagari_ratio("plain english text") == 0.0
    assert devanagari_ratio("दिल्ली") == 1.0
    assert devanagari_ratio("दिल्ली Delhi") == pytest.approx(6 / 11, abs=0.001)


def test_looks_scanned_thresholds() -> None:
    """Few characters plus an image, or almost no characters at all, looks scanned."""
    assert looks_scanned(n_chars=10, n_images=1) is True
    assert looks_scanned(n_chars=10, n_images=0) is True
    assert looks_scanned(n_chars=40, n_images=1) is True
    assert looks_scanned(n_chars=40, n_images=0) is False
    assert looks_scanned(n_chars=2000, n_images=3) is False


def test_find_repeated_lines() -> None:
    """A line on more than 40% of the pages is reported; a one-off line is not."""
    page_edges = [
        {"MASTER PLAN FOR DELHI 2047", "1"},
        {"MASTER PLAN FOR DELHI 2047", "2"},
        {"MASTER PLAN FOR DELHI 2047", "3"},
        {"something else", "4"},
    ]
    assert find_repeated_lines(page_edges) == [("MASTER PLAN FOR DELHI 2047", 3)]
    assert find_repeated_lines([]) == []
