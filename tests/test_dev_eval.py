"""Tests for the question verification screen: the flag, the saving, the leakage check.

Every test writes its own draft file into a tmp folder and points the module at it, so
nothing here reads `eval/questions_draft.jsonl` and nothing can write the real
`eval/questions_verified.jsonl` — which would be someone's evening of work.
"""

import json

import pytest
from fastapi.testclient import TestClient

import app.dev_eval as dev_eval
from app.api import app, require_index
from app.config import settings
from app.dev_eval import (
    ACCEPTED,
    EDITED,
    LEAKAGE_RUN,
    REJECTED,
    SKIPPED,
    Decision,
    DevEvalError,
    leakage,
    ngrams,
    progress,
    question_detail,
    question_list,
    save_decision,
    words_of,
)
from app.retrieval import Result

CLAUSE = (
    "The maximum permissible ground coverage for a TOD Plot shall be 40% of the plot "
    "area, and relaxations may be granted by the TOD Committee on a case by case basis."
)
OTHER = (
    "Parking shall be provided at the rate of two equivalent car spaces per hundred "
    "square metres of built up area in all commercial use premises."
)

CHUNKS = {
    "MPD47_GAZETTE_EN:4.2.3@p753:0": {
        "chunk_id": "MPD47_GAZETTE_EN:4.2.3@p753:0",
        "doc_id": "MPD47_GAZETTE_EN",
        "clause_id": "4.2.3",
        "heading_path": ["4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)", "4.2.3 TOD Norms"],
        "chapter": "4",
        "page_start": 753,
        "page_end": 753,
        "zone_primary": "tod",
        "n_words": 30,
        "text": CLAUSE,
    },
    "MPD47_GAZETTE_EN:11.2.1:0": {
        "chunk_id": "MPD47_GAZETTE_EN:11.2.1:0",
        "doc_id": "MPD47_GAZETTE_EN",
        "clause_id": "11.2.1",
        "heading_path": ["11.2 Parking"],
        "chapter": "11",
        "page_start": 855,
        "page_end": 855,
        "zone_primary": "",
        "n_words": 28,
        "text": OTHER,
    },
}

DRAFTS = [
    {
        "id": "loc-01",
        "question": "How much of this land am I allowed to cover with building?",
        "point_name": "P_TOD",
        "category": "location",
        "expected_chunk_ids": ["MPD47_GAZETTE_EN:4.2.3@p753:0"],
        "acceptable_chunk_ids": [],
        "expected_answer_short": "Up to 40% of the plot.",
        "should_abstain": False,
        "verified": False,
        "drafted_by": "claude_code",
        "notes": "",
        "lat": 28.6328,
        "lon": 77.2197,
    },
    {
        "id": "abs-01",
        "question": "How much property tax will I pay on this plot?",
        "point_name": "P_TOD",
        "category": "abstain",
        "expected_chunk_ids": [],
        "acceptable_chunk_ids": [],
        "expected_answer_short": "",
        "should_abstain": True,
        "verified": False,
        "drafted_by": "claude_code",
        "notes": "",
        "lat": 28.6328,
        "lon": 77.2197,
    },
]


class StubIndex:
    """Stands in for SearchIndex: the chunk records and nothing else."""

    def __init__(self, chunks: dict) -> None:
        self.chunks = chunks

    def __len__(self) -> int:
        return len(self.chunks)


def stub_result(chunk_id: str, score: float, cosine: float) -> Result:
    """One search result for the top-5 list."""
    chunk = CHUNKS[chunk_id]
    return Result(
        chunk_id=chunk_id,
        doc_id=chunk["doc_id"],
        clause_id=chunk["clause_id"],
        heading_path=list(chunk["heading_path"]),
        chapter=chunk["chapter"],
        page_start=chunk["page_start"],
        page_end=chunk["page_end"],
        zone_primary=chunk["zone_primary"],
        zone_mentions=[],
        text=chunk["text"],
        dense_rank=1,
        bm25_rank=1,
        dense_distance=1.0 - cosine,
        fused_score=score,
    )


@pytest.fixture
def files(monkeypatch, tmp_path):
    """Point the module's three file paths at a tmp folder with the drafts written."""
    drafts = tmp_path / "questions_draft.jsonl"
    with drafts.open("w", encoding="utf-8", newline="\n") as handle:
        for record in DRAFTS:
            handle.write(json.dumps(record) + "\n")
    verified = tmp_path / "questions_verified.jsonl"
    points = tmp_path / "points.json"
    points.write_text(
        json.dumps(
            [
                {
                    "name": "P_TOD",
                    "lat": 28.6328,
                    "lon": 77.2197,
                    "zones": {"inside_delhi": True, "planning_zone": "D", "tod": True},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dev_eval, "drafts_path", lambda: drafts)
    monkeypatch.setattr(dev_eval, "verified_path", lambda: verified)
    monkeypatch.setattr(dev_eval, "points_path", lambda: points)
    return {"drafts": drafts, "verified": verified, "points": points}


@pytest.fixture
def index():
    return StubIndex(CHUNKS)


# --- the leakage check ----------------------------------------------------------


def test_four_consecutive_words_are_leakage() -> None:
    """Three words is a phrase anybody might write; four is a quotation (D-055)."""
    assert leakage("what is the maximum permissible ground coverage", [CLAUSE])
    assert "maximum permissible ground coverage" in leakage(
        "the maximum permissible ground coverage here", [CLAUSE]
    )


def test_three_consecutive_words_are_not_leakage() -> None:
    assert leakage("what is the ground coverage limit", [CLAUSE]) == []


def test_a_question_in_its_own_words_passes() -> None:
    assert leakage("How much of my land can I build on?", [CLAUSE]) == []


def test_leakage_ignores_punctuation_and_case() -> None:
    assert leakage("MAXIMUM, PERMISSIBLE: GROUND -- COVERAGE!", [CLAUSE])


def test_leakage_checks_every_chunk_it_is_given() -> None:
    found = leakage("equivalent car spaces per hundred", [CLAUSE, OTHER])
    assert found


def test_a_short_question_cannot_leak() -> None:
    """Fewer words than the run length means there is no run to compare."""
    assert leakage("ground coverage", [CLAUSE]) == []
    assert ngrams(words_of("one two"), LEAKAGE_RUN) == set()


def test_leakage_against_no_chunks_is_a_pass() -> None:
    """A should-abstain question has no chunks, so there is nothing it could copy."""
    assert leakage("Will my plan be approved?", []) == []


# --- listing and progress -------------------------------------------------------


def test_the_list_shows_every_draft_as_pending_at_first(files) -> None:
    found = question_list()
    assert len(found["questions"]) == 2
    assert {item["status"] for item in found["questions"]} == {"pending"}
    assert found["progress"] == {
        "total": 2,
        "done": 0,
        "accepted": 0,
        "edited": 0,
        "rejected": 0,
    }


def test_progress_counts_each_status(files) -> None:
    verified = [
        {"id": "loc-01", "status": ACCEPTED, "verified": True},
        {"id": "abs-01", "status": REJECTED, "verified": False},
    ]
    assert progress(DRAFTS, verified) == {
        "total": 2,
        "done": 2,
        "accepted": 1,
        "edited": 0,
        "rejected": 1,
    }


def test_the_list_shows_the_edited_text_once_a_decision_exists(files, index) -> None:
    save_decision(
        Decision(
            id="loc-01",
            status=EDITED,
            question="Can I cover the whole plot with building?",
            expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
        ),
        index,
    )
    item = next(q for q in question_list()["questions"] if q["id"] == "loc-01")
    assert item["question"] == "Can I cover the whole plot with building?"
    assert item["status"] == EDITED
    assert item["verified"] is True


# --- one question's detail ------------------------------------------------------


def test_the_detail_carries_the_point_the_chunks_and_the_results(files, index) -> None:
    def searcher(query, zones):
        assert zones["tod"] is True, "the point's zones reach the search"
        return [
            stub_result("MPD47_GAZETTE_EN:4.2.3@p753:0", 0.049, 0.86),
            stub_result("MPD47_GAZETTE_EN:11.2.1:0", 0.031, 0.71),
        ]

    found = question_detail("loc-01", index, searcher=searcher)
    assert found["lat"] == pytest.approx(28.6328)
    assert found["zones"]["planning_zone"] == "D"
    assert found["expected_chunks"][0]["text"] == CLAUSE
    assert [result["rank"] for result in found["top_results"]] == [1, 2]
    assert found["top_results"][0]["is_expected"] is True
    assert found["top_results"][1]["is_expected"] is False
    assert found["top_results"][0]["dense_cosine"] == pytest.approx(0.86)


def test_the_detail_reports_leakage_in_the_current_question(files, index) -> None:
    save_decision(
        Decision(
            id="loc-01",
            status=EDITED,
            question="What is the ground coverage here?",
            expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
        ),
        index,
    )
    found = question_detail("loc-01", index, searcher=lambda query, zones: [])
    assert found["question"] == "What is the ground coverage here?"
    assert found["draft_question"] == DRAFTS[0]["question"]
    assert found["leakage"] == []


def test_an_unknown_question_id_is_an_error(files, index) -> None:
    with pytest.raises(DevEvalError):
        question_detail("nope-99", index, searcher=lambda query, zones: [])


# --- saving a decision ----------------------------------------------------------


def test_accepting_writes_a_verified_record(files, index) -> None:
    result = save_decision(
        Decision(
            id="loc-01",
            status=ACCEPTED,
            question=DRAFTS[0]["question"],
            expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            notes="checked against page 753",
        ),
        index,
    )
    assert result["saved"]["verified"] is True
    assert result["saved"]["verified_by"] == "dhruv"
    assert result["replaced"] is False
    stored = [json.loads(line) for line in files["verified"].read_text(encoding="utf-8").splitlines()]
    assert len(stored) == 1
    assert stored[0]["notes"] == "checked against page 753"


def test_saving_twice_updates_in_place_by_id(files, index) -> None:
    for text in ("first wording of the question", "second wording of the question"):
        result = save_decision(
            Decision(
                id="loc-01",
                status=EDITED,
                question=text,
                expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            ),
            index,
        )
    assert result["replaced"] is True
    stored = [json.loads(line) for line in files["verified"].read_text(encoding="utf-8").splitlines()]
    assert len(stored) == 1
    assert stored[0]["question"] == "second wording of the question"


def test_the_draft_file_is_never_written(files, index) -> None:
    """09_draft_questions.py owns it, and it is the record of what was generated."""
    before = files["drafts"].read_bytes()
    save_decision(
        Decision(
            id="loc-01",
            status=ACCEPTED,
            question="Something quite different now",
            expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
        ),
        index,
    )
    assert files["drafts"].read_bytes() == before


def test_rejecting_is_recorded_but_not_verified(files, index) -> None:
    """"I looked and it is a bad question" has to be distinguishable from "not reached"."""
    result = save_decision(Decision(id="abs-01", status=REJECTED, notes="ambiguous"), index)
    assert result["saved"]["verified"] is False
    assert result["saved"]["status"] == REJECTED
    assert result["saved"]["verified_by"] is None
    assert result["progress"]["done"] == 1


def test_skipping_is_recorded_too(files, index) -> None:
    result = save_decision(Decision(id="abs-01", status=SKIPPED), index)
    assert result["saved"]["status"] == SKIPPED
    assert result["saved"]["verified"] is False


def test_a_should_abstain_question_keeps_no_expected_chunks(files, index) -> None:
    result = save_decision(
        Decision(id="abs-01", status=ACCEPTED, question="Who decides my tax?", should_abstain=True),
        index,
    )
    assert result["saved"]["should_abstain"] is True
    assert result["saved"]["expected_chunk_ids"] == []


# --- the guards -----------------------------------------------------------------


def test_a_should_abstain_question_with_expected_chunks_is_refused(files, index) -> None:
    with pytest.raises(DevEvalError, match="no expected chunks"):
        save_decision(
            Decision(
                id="abs-01",
                status=ACCEPTED,
                question="Something",
                should_abstain=True,
                expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            ),
            index,
        )


def test_an_answerable_question_with_no_expected_chunk_is_refused(files, index) -> None:
    with pytest.raises(DevEvalError, match="1 to 3 expected"):
        save_decision(Decision(id="loc-01", status=ACCEPTED, question="Anything?"), index)


def test_a_chunk_id_that_is_not_in_the_index_is_refused(files, index) -> None:
    with pytest.raises(DevEvalError, match="not in the index"):
        save_decision(
            Decision(
                id="loc-01",
                status=ACCEPTED,
                question="Anything?",
                expected_chunk_ids=["MPD47_GAZETTE_EN:9.9.9:0"],
            ),
            index,
        )


def test_a_question_that_quotes_its_own_answer_is_refused(files, index) -> None:
    """The same guard the drafter enforces on itself (D-055)."""
    with pytest.raises(DevEvalError, match="words with a chunk"):
        save_decision(
            Decision(
                id="loc-01",
                status=EDITED,
                question="What is the maximum permissible ground coverage for a TOD Plot?",
                expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            ),
            index,
        )


def test_an_empty_accepted_question_is_refused(files, index) -> None:
    with pytest.raises(DevEvalError, match="needs some text"):
        save_decision(
            Decision(
                id="loc-01",
                status=ACCEPTED,
                question="   ",
                expected_chunk_ids=["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            ),
            index,
        )


def test_an_unknown_status_is_refused(files, index) -> None:
    with pytest.raises(DevEvalError, match="status must be"):
        save_decision(Decision(id="loc-01", status="maybe"), index)


def test_an_unknown_question_id_cannot_be_saved(files, index) -> None:
    with pytest.raises(DevEvalError, match="no drafted question"):
        save_decision(Decision(id="nope-99", status=SKIPPED), index)


def test_a_rejected_question_skips_the_guards(files, index) -> None:
    """Rejecting is how you get past a question whose ids are wrong."""
    result = save_decision(Decision(id="loc-01", status=REJECTED), index)
    assert result["saved"]["status"] == REJECTED


# --- the endpoints, flag off and flag on ---------------------------------------


@pytest.fixture
def dev_client(monkeypatch, files, index):
    """A TestClient with dev mode on and the index stubbed."""
    monkeypatch.setattr("app.api.settings", _with_dev(True))
    app.dependency_overrides[require_index] = lambda: index
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def plain_client(monkeypatch, files, index):
    """A TestClient with dev mode off."""
    monkeypatch.setattr("app.api.settings", _with_dev(False))
    app.dependency_overrides[require_index] = lambda: index
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _with_dev(on: bool):
    """A settings copy with dev_mode set."""
    from dataclasses import replace

    return replace(settings, dev_mode=on)


DEV_PATHS = (
    ("get", "/api/dev/eval/questions"),
    ("get", "/api/dev/eval/questions/loc-01"),
    ("post", "/api/dev/eval/questions/loc-01/leakage"),
    ("post", "/api/dev/eval/questions/loc-01/decision"),
)


def test_every_dev_endpoint_is_a_404_with_the_flag_off(plain_client) -> None:
    """A 404 rather than a 403: a 403 confirms the endpoint exists (D-075)."""
    for method, path in DEV_PATHS:
        if method == "get":
            response = plain_client.get(path)
        else:
            response = plain_client.post(path, json={"question": "x", "status": "skipped"})
        assert response.status_code == 404, path


def test_health_says_dev_mode_is_on(dev_client) -> None:
    assert dev_client.get("/api/health").json()["dev_mode"] is True


def test_health_says_dev_mode_is_off(plain_client) -> None:
    assert plain_client.get("/api/health").json()["dev_mode"] is False


def test_the_questions_endpoint_lists_them_with_the_flag_on(dev_client) -> None:
    body = dev_client.get("/api/dev/eval/questions").json()
    assert body["progress"]["total"] == 2
    assert {item["id"] for item in body["questions"]} == {"loc-01", "abs-01"}


def test_the_leakage_endpoint_returns_the_overlapping_phrase(dev_client) -> None:
    body = dev_client.post(
        "/api/dev/eval/questions/loc-01/leakage",
        json={"question": "What is the maximum permissible ground coverage?"},
    ).json()
    assert body["ok"] is False
    assert "maximum permissible ground coverage" in body["shared_word_runs"]
    assert body["run_length"] == LEAKAGE_RUN


def test_the_leakage_endpoint_passes_a_reworded_question(dev_client) -> None:
    body = dev_client.post(
        "/api/dev/eval/questions/loc-01/leakage",
        json={"question": "How much of my land may I build on?"},
    ).json()
    assert body["ok"] is True
    assert body["shared_word_runs"] == []


def test_the_decision_endpoint_saves(dev_client, files) -> None:
    response = dev_client.post(
        "/api/dev/eval/questions/loc-01/decision",
        json={
            "status": "accepted",
            "question": "How much of my land may I build on?",
            "expected_chunk_ids": ["MPD47_GAZETTE_EN:4.2.3@p753:0"],
            "acceptable_chunk_ids": [],
            "should_abstain": False,
            "notes": "fine",
        },
    )
    assert response.status_code == 200
    assert response.json()["saved"]["verified"] is True
    assert files["verified"].exists()


def test_the_decision_endpoint_explains_a_refusal(dev_client) -> None:
    """A 422 with the reason in words, because the person typing has to fix it."""
    response = dev_client.post(
        "/api/dev/eval/questions/loc-01/decision",
        json={
            "status": "accepted",
            "question": "What is the maximum permissible ground coverage for a TOD Plot?",
            "expected_chunk_ids": ["MPD47_GAZETTE_EN:4.2.3@p753:0"],
        },
    )
    assert response.status_code == 422
    assert "words with a chunk" in response.json()["detail"]["message"]


def test_an_unknown_question_is_a_404_even_with_the_flag_on(dev_client) -> None:
    assert dev_client.get("/api/dev/eval/questions/nope-99").status_code == 404


def test_a_question_over_the_length_limit_is_rejected_by_validation(dev_client) -> None:
    response = dev_client.post(
        "/api/dev/eval/questions/loc-01/leakage", json={"question": "x" * 600}
    )
    assert response.status_code == 422
