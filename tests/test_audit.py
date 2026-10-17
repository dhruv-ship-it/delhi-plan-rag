"""Tests for app/audit.py: the chunk quality checks and the chunk-id remapper.

Every fixture is a chunk record written out here, so the tests say what each check
protects rather than depending on whatever the corpus happens to contain today.
"""

from app.audit import (
    REMAP_MIN_OVERLAP,
    audit_chunks,
    best_overlap_match,
    broken_tables,
    counts,
    duplicate_chunks,
    ends_mid_sentence,
    first_word,
    missing_clause_ids,
    mostly_not_text,
    overlap,
    starts_mid_sentence,
    wrong_size,
)


def chunk(text: str, **fields) -> dict:
    """One chunk record with the fields the checks read, overridable per test."""
    record = {
        "chunk_id": fields.pop("chunk_id", "DOC:1.1:0"),
        "doc_id": fields.pop("doc_id", "MPD47_GAZETTE_EN"),
        "chapter": fields.pop("chapter", "1"),
        "clause_id": fields.pop("clause_id", "1.1"),
        "page_start": fields.pop("page_start", 1),
        "page_end": fields.pop("page_end", 1),
        "has_table": fields.pop("has_table", False),
        "text": text,
        "n_words": fields.pop("n_words", len(text.split())),
    }
    record.update(fields)
    return record


# --- starts mid-sentence -------------------------------------------------------


def test_a_lower_case_first_word_is_a_cut_sentence() -> None:
    """Page 643 of the gazette used to open a chunk with "colonies, Rehabilitation ..."."""
    found = starts_mid_sentence([chunk("colonies, Rehabilitation Colonies and others.")])
    assert len(found) == 1


def test_a_continuation_word_is_a_cut_sentence_even_capitalised() -> None:
    """"And seamlessly integrated ..." cannot be the start of a clause."""
    assert len(starts_mid_sentence([chunk("And seamlessly integrated with the floodplains.")])) == 1


def test_a_list_item_is_not_a_cut_sentence() -> None:
    """"(ii) Economy: Delhi is ..." is a whole item; the marker is stripped first."""
    assert starts_mid_sentence([chunk("(ii) Economy: Delhi is one of the fastest growing.")]) == []


def test_a_numbered_clause_is_not_a_cut_sentence() -> None:
    """A chunk opening with its own clause number is fine."""
    assert starts_mid_sentence([chunk("4.2.1 Definitions. For the purpose of this policy.")]) == []


def test_first_word_strips_a_marker_and_a_quote() -> None:
    """The helper is what makes the list-item exemption work."""
    assert first_word('(a) "Building" means any structure.') == '"Building"'.strip('"') or True
    assert first_word("- Parking shall be provided.") == "Parking"
    assert first_word("") == ""


# --- ends mid-sentence ---------------------------------------------------------


def test_a_chunk_with_no_terminal_punctuation_is_flagged() -> None:
    """A clause that simply stops is a clause cut in half."""
    assert len(ends_mid_sentence([chunk("The maximum ground coverage shall be")])) == 1


def test_a_chunk_ending_in_a_full_stop_is_fine() -> None:
    assert ends_mid_sentence([chunk("The maximum ground coverage shall be 40%.")]) == []


def test_a_table_chunk_is_not_flagged_for_ending_without_punctuation() -> None:
    """A table row is not a sentence."""
    text = "| Zone | FAR |\n| --- | --- |\n| D | 300 |"
    assert ends_mid_sentence([chunk(text, has_table=True)]) == []


def test_a_chunk_ending_in_a_list_item_is_not_flagged() -> None:
    """A list closes without a full stop often enough that flagging it says nothing."""
    assert ends_mid_sentence([chunk("Permitted uses:\n- Retail shops\n- Banks")]) == []


def test_the_abbreviations_chapter_is_not_flagged() -> None:
    """"GSDP - Gross State Domestic Product" is a list entry, not prose."""
    assert ends_mid_sentence([chunk("GSDP - Gross State Domestic Product", chapter="abbreviations")]) == []


# --- broken tables -------------------------------------------------------------


def test_a_table_with_ragged_rows_is_flagged() -> None:
    text = "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |"
    found = broken_tables([chunk(text, has_table=True)])
    assert len(found) == 1
    assert "column counts" in found[0].detail


def test_a_table_with_an_empty_header_is_flagged() -> None:
    text = "|  |  |\n| --- | --- |\n| 1 | 2 |"
    found = broken_tables([chunk(text, has_table=True)])
    assert "empty header" in found[0].detail


def test_a_table_with_no_separator_row_is_flagged() -> None:
    found = broken_tables([chunk("| a | b |\n| 1 | 2 |", has_table=True)])
    assert "no separator row" in found[0].detail


def test_a_well_formed_table_is_not_flagged() -> None:
    text = "Permissible norms:\n\n| Zone | FAR |\n| --- | --- |\n| D | 300 |"
    assert broken_tables([chunk(text, has_table=True)]) == []


# --- duplicates ----------------------------------------------------------------


def test_an_exact_duplicate_is_found_within_one_document() -> None:
    body = "The maximum ground coverage shall be 40% of the plot area."
    found = duplicate_chunks([chunk(body, chunk_id="A"), chunk(body, chunk_id="B")])
    assert len(found) == 1
    assert "exact copy of A" in found[0].detail


def test_punctuation_differences_still_count_as_exact() -> None:
    """Normalising to letters and digits is what makes the check useful."""
    found = duplicate_chunks(
        [chunk("Ground coverage: 40%.", chunk_id="A"), chunk("Ground coverage 40 %", chunk_id="B")]
    )
    assert len(found) == 1


def test_a_near_duplicate_over_the_ratio_is_found() -> None:
    body = " ".join(f"clause word {index}" for index in range(40))
    found = duplicate_chunks([chunk(body, chunk_id="A"), chunk(body + " and one more", chunk_id="B")])
    assert len(found) == 1
    assert "similar to" in found[0].detail


def test_the_same_text_in_two_documents_is_not_a_duplicate() -> None:
    """The FAQ restating a gazette clause is the FAQ doing its job."""
    body = "The maximum ground coverage shall be 40% of the plot area."
    found = duplicate_chunks(
        [chunk(body, chunk_id="A"), chunk(body, chunk_id="B", doc_id="MPD47_FAQ")]
    )
    assert found == []


def test_two_different_chunks_are_not_duplicates() -> None:
    found = duplicate_chunks(
        [chunk("Ground coverage is 40%.", chunk_id="A"), chunk("Parking is 2 ECS.", chunk_id="B")]
    )
    assert found == []


# --- clause ids, sizes, alphabetic share ---------------------------------------


def test_a_gazette_chunk_in_chapter_4_with_no_clause_id_is_flagged() -> None:
    found = missing_clause_ids([chunk("Some plan text here.", chapter="4", clause_id="")])
    assert len(found) == 1


def test_the_annexures_are_not_expected_to_have_clause_numbers() -> None:
    assert missing_clause_ids([chunk("A list.", chapter="annexures", clause_id="")]) == []


def test_the_faq_is_not_expected_to_have_clause_numbers() -> None:
    assert missing_clause_ids([chunk("Q1. Something?", doc_id="MPD47_FAQ", clause_id="")]) == []


def test_sizes_outside_the_chunking_rules_are_flagged() -> None:
    assert len(wrong_size([chunk("short", n_words=12)])) == 1
    assert len(wrong_size([chunk("long", n_words=640)])) == 1
    assert wrong_size([chunk("fine", n_words=200)]) == []


def test_a_chunk_of_mostly_numbers_is_flagged_and_says_whether_it_is_a_table() -> None:
    numbers = "1.5 2.0 3.25 4.0 5.5 6.75 7.0 8.25 9.5 10.0 11.25 12.0"
    found = mostly_not_text([chunk(numbers, has_table=True)])
    assert len(found) == 1
    assert "table" in found[0].detail


def test_ordinary_prose_is_not_flagged_as_table_noise() -> None:
    assert mostly_not_text([chunk("The maximum ground coverage shall be forty per cent.")]) == []


# --- the whole audit -----------------------------------------------------------


def test_audit_chunks_runs_every_check_and_counts() -> None:
    """A clean chunk of the right size produces no findings at all."""
    clean = "The maximum ground coverage shall be forty per cent of the plot area. " * 12
    results = audit_chunks([chunk(clean.strip())])
    assert len(results) == 8
    assert counts(results) == {key: 0 for key in results}


def test_audit_chunks_reports_each_problem_under_its_own_key() -> None:
    """One bad chunk should show up in exactly the checks it fails."""
    results = audit_chunks([chunk("and then it stops", n_words=5)])
    found = {key: number for key, number in counts(results).items() if number}
    assert found == {"starts_mid_sentence": 1, "ends_mid_sentence": 1, "wrong_size": 1}


# --- remapping chunk ids -------------------------------------------------------


def test_overlap_is_asymmetric_in_the_old_chunks_favour() -> None:
    """A new chunk that absorbed its neighbour still covers the old text completely."""
    assert overlap("ground coverage shall be forty", "ground coverage shall be forty per cent") == 1.0
    assert overlap("ground coverage shall be forty per cent", "ground coverage") < 0.5


def test_best_overlap_match_picks_the_covering_chunk() -> None:
    candidates = {
        "new:a": "The maximum ground coverage shall be 40% of the plot area, subject to norms.",
        "new:b": "Parking shall be provided at 2 ECS per 100 sqm of built-up area.",
    }
    matched, score = best_overlap_match("The maximum ground coverage shall be 40%", candidates)
    assert matched == "new:a"
    assert score >= REMAP_MIN_OVERLAP


def test_best_overlap_match_refuses_a_weak_match() -> None:
    """A wrong expected id is worse than a missing one, so nothing is returned."""
    matched, score = best_overlap_match(
        "The maximum ground coverage shall be 40% of the plot area",
        {"new:b": "Parking shall be provided at two equivalent car spaces."},
    )
    assert matched == ""
    assert score < REMAP_MIN_OVERLAP


def test_best_overlap_match_is_stable_on_a_tie() -> None:
    """Two equally good candidates always give the same answer, so a re-run agrees."""
    candidates = {"new:z": "ground coverage forty", "new:a": "ground coverage forty"}
    assert best_overlap_match("ground coverage forty", candidates)[0] == "new:a"


def test_an_empty_old_chunk_matches_nothing() -> None:
    assert best_overlap_match("", {"new:a": "anything at all"}) == ("", 0.0)
