"""Tests for eval/answer_eval.py: the answer-level harness, against FakeLLM.

Everything here runs with a scripted FakeLLM and a hand-built search index, exactly as
tests/test_answer.py and tests/test_agent.py do for app/answer.py and app/agent.py
themselves - no API key, no Chroma store, no map layers. `app.answer.get_zones` and
`app.answer.search` are patched for the location-question path (the same two names
tests/test_answer.py patches, because `answer_point` calls them by those names);
`app.agent.search` is patched for the no-point path, which since D-117 runs through
`app.agent.run_agent` - the same function `/api/agent` calls - rather than a
location-free stand-in.
"""

import json

import pytest

from app.llm import FakeLLM, tool_use_response
from app.retrieval import Result
from eval.answer_eval import (
    InsufficientQuestions,
    citations_fully_valid,
    ensure_enough,
    run_one,
    run_questions,
)

# --- a tiny stand-in for the search index, as tests/test_answer.py builds one --------

CHUNKS = {
    "MPD47_GAZETTE_EN:4.2.3:0": {
        "chunk_id": "MPD47_GAZETTE_EN:4.2.3:0",
        "doc_title": "Master Plan for Delhi 2047 gazette notification (English)",
        "authority_rank": 1,
        "source_url": "https://dda.gov.in/gazette.pdf",
        "text": "Maximum ground coverage of 40% shall be permitted on a TOD Plot.",
    },
    "MPD47_FAQ:Q13@p13:0": {
        "chunk_id": "MPD47_FAQ:Q13@p13:0",
        "doc_title": "FAQs on MPD-2047",
        "authority_rank": 3,
        "source_url": "https://dda.gov.in/faq.pdf",
        "text": "Q13. Maximum permissible ground coverage is 40%.",
    },
    "MPD47_FAQ:Q2@p2:0": {
        "chunk_id": "MPD47_FAQ:Q2@p2:0",
        "doc_title": "FAQs on MPD-2047",
        "authority_rank": 3,
        "source_url": "https://dda.gov.in/faq.pdf",
        "text": "Q2. Yes, MPD-2047 takes over from MPD-2021.",
    },
}


class StubIndex:
    """Stands in for SearchIndex: holds the chunk records, nothing else."""

    def __init__(self, chunks: dict) -> None:
        self.chunks = chunks


def fake_result(chunk_id: str, cosine: float = 0.8, text: str | None = None) -> Result:
    """One search result carrying only the fields the answer path reads."""
    return Result(
        chunk_id=chunk_id,
        doc_id=chunk_id.split(":")[0],
        clause_id=chunk_id.split(":")[1] if ":" in chunk_id else None,
        heading_path=["4.2 TOD"],
        chapter="4",
        page_start=1,
        page_end=1,
        zone_primary="tod",
        zone_mentions=["tod"],
        text=CHUNKS[chunk_id]["text"] if text is None else text,
        dense_rank=1,
        bm25_rank=1,
        dense_distance=1.0 - cosine,
        fused_score=0.05,
        bm25_score=5.0,
    )


ZONES = {
    "inside_delhi": True,
    "planning_zone": "D",
    "tod": True,
    "hdc": False,
    "land_pooling": False,
    "land_pooling_zone": None,
    "zone_o": False,
    "regional_park": False,
    "lda": False,
}


def location_question(qid: str = "loc-01") -> dict:
    return {
        "id": qid,
        "question": "How much can I build here?",
        "category": "location",
        "lat": 28.63,
        "lon": 77.22,
        "expected_chunk_ids": ["MPD47_GAZETTE_EN:4.2.3:0"],
        "acceptable_chunk_ids": ["MPD47_FAQ:Q13@p13:0"],
        "should_abstain": False,
        "verified": True,
    }


def general_question(qid: str = "gen-01") -> dict:
    return {
        "id": qid,
        "question": "Does the 2047 plan take over from the 2021 one?",
        "category": "general",
        "lat": None,
        "lon": None,
        "expected_chunk_ids": ["MPD47_FAQ:Q2@p2:0"],
        "acceptable_chunk_ids": [],
        "should_abstain": False,
        "verified": True,
    }


def good_json(text: str, citation: str) -> str:
    return json.dumps({"abstain": None, "sentences": [{"text": text, "citations": [citation]}]})


def abstain_json(reason: str) -> str:
    return json.dumps({"abstain": reason, "sentences": []})


@pytest.fixture
def located(monkeypatch):
    """Patch app.answer's own get_zones and search, as tests/test_answer.py does."""
    monkeypatch.setattr("app.answer.get_zones", lambda lat, lon: ZONES)
    results = {"value": [fake_result("MPD47_GAZETTE_EN:4.2.3:0"), fake_result("MPD47_FAQ:Q13@p13:0")]}
    monkeypatch.setattr("app.answer.search", lambda *args, **kwargs: list(results["value"]))
    return results


@pytest.fixture
def agented(monkeypatch):
    """Patch app.agent's own search, used by the no-point path (D-117)."""
    results = {"value": [fake_result("MPD47_FAQ:Q2@p2:0")]}
    monkeypatch.setattr("app.agent.search", lambda *args, **kwargs: list(results["value"]))
    return results


# --- an answered question citing an expected clause -------------------------------


def test_an_answered_question_citing_an_expected_clause(located, monkeypatch) -> None:
    """A location question, answered first try, citing the chunk the question expects."""
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    llm = FakeLLM(responses=[good_json("Ground coverage is 40%.", "C1")])
    record = run_one(location_question(), llm, StubIndex(CHUNKS))

    assert record["mode"] == "map"
    assert record["answered"] is True
    assert record["abstained"] is False
    assert record["cited_chunk_ids"] == ["MPD47_GAZETTE_EN:4.2.3:0"]
    assert record["cites_verified_clause"] is True
    assert citations_fully_valid(record) is True
    assert record["llm_calls"] == 1


# --- an answered question citing a non-verified clause -----------------------------


def test_a_no_point_question_goes_through_the_agent_path(agented, monkeypatch) -> None:
    """A no-point question runs through `app.agent.run_agent` (D-117), the same
    function `/api/agent` calls, rather than a location-free stand-in.

    The model searches once, citing the agent's own `S1` label, then answers - the
    same two-call shape `tests/test_agent.py` scripts for a full tool conversation.
    """
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    other_chunk = dict(CHUNKS, **{
        "MPD47_FAQ:Q99@p99:0": {
            "chunk_id": "MPD47_FAQ:Q99@p99:0",
            "doc_title": "FAQs on MPD-2047",
            "authority_rank": 3,
            "source_url": "https://dda.gov.in/faq.pdf",
            "text": "Q99. An unrelated answer.",
        }
    })
    agented["value"] = [
        fake_result("MPD47_FAQ:Q99@p99:0", text="Q99. An unrelated answer."),
    ]
    llm = FakeLLM(
        responses=[
            tool_use_response("search_clauses", {"query": "2047 plan status"}, "t1"),
            good_json("An unrelated answer.", "S1"),
        ]
    )
    record = run_one(general_question(), llm, StubIndex(other_chunk))

    assert record["mode"] == "agent"
    assert record["has_point"] is False
    assert record["answered"] is True
    assert record["cited_chunk_ids"] == ["MPD47_FAQ:Q99@p99:0"]
    assert record["cites_verified_clause"] is False


# --- an abstention -----------------------------------------------------------------


def test_an_abstention(located, monkeypatch) -> None:
    """The model declines an answerable question; recorded as abstained, not answered."""
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    llm = FakeLLM(responses=[abstain_json("the sources do not cover this")])
    record = run_one(location_question(), llm, StubIndex(CHUNKS))

    assert record["answered"] is False
    assert record["abstained"] is True
    assert record["abstain_reason"].startswith("model_abstained")
    assert record["cited_chunk_ids"] == []
    assert record["cites_verified_clause"] is False


# --- a should-abstain question that is declined -------------------------------------


def test_a_should_abstain_question_that_is_declined(located, monkeypatch) -> None:
    """A should-abstain question the model correctly refuses to answer."""
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    question = location_question("abs-01")
    question["should_abstain"] = True
    question["expected_chunk_ids"] = []
    question["acceptable_chunk_ids"] = []
    llm = FakeLLM(responses=[abstain_json("not in the corpus")])
    record = run_one(question, llm, StubIndex(CHUNKS))

    assert record["should_abstain"] is True
    assert record["abstained"] is True
    assert record["answered"] is False


# --- a budget stop, then a resume ---------------------------------------------------


def test_a_budget_stop_then_a_resume(located, monkeypatch) -> None:
    """The run stops once its token budget is spent, and --resume picks up the rest."""
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    from app.llm import Response, TextBlock, Usage

    def costly(text: str, citation: str, tokens: int) -> Response:
        return Response(
            content=[TextBlock(text=good_json(text, citation))],
            usage=Usage(input_tokens=tokens, output_tokens=10),
        )

    questions = [location_question("loc-01"), location_question("loc-02")]
    llm = FakeLLM(responses=[costly("Ground coverage is 40%.", "C1", 900)])
    state = {"records": [], "runs": 0}

    run_questions(questions, llm, StubIndex(CHUNKS), state, budget_tokens=500, max_calls=100)

    assert state["stopped_because"] == "token_budget"
    assert len(state["records"]) == 1
    assert state["records"][0]["id"] == "loc-01"

    # --resume: a fresh client, the same state, the remaining question gets a turn
    llm2 = FakeLLM(responses=[good_json("Ground coverage is 40%.", "C1")])
    run_questions(questions, llm2, StubIndex(CHUNKS), state, budget_tokens=500, max_calls=100)

    assert len(state["records"]) == 2
    assert {r["id"] for r in state["records"]} == {"loc-01", "loc-02"}
    assert state["stopped_because"] == "finished"


# --- an agent case is budgeted and resumable too ------------------------------------


def test_an_agent_case_is_budgeted_and_resumable_like_a_map_case(agented, monkeypatch) -> None:
    """A no-point case spends tokens across two calls (search, then answer); the
    budget and --resume logic treat it the same way as a single-call map case (D-117).
    """
    monkeypatch.setattr("app.answer.settings", _with(support_check="off"))
    from app.llm import Response, TextBlock, ToolUseBlock, Usage

    def costly_search(tokens: int, call_id: str) -> Response:
        return Response(
            content=[ToolUseBlock(name="search_clauses", input={"query": "2047 plan"}, id=call_id)],
            stop_reason="tool_use",
            usage=Usage(input_tokens=tokens, output_tokens=10),
        )

    def costly_answer(text: str, citation: str, tokens: int) -> Response:
        return Response(
            content=[TextBlock(text=good_json(text, citation))],
            usage=Usage(input_tokens=tokens, output_tokens=10),
        )

    questions = [general_question("gen-01"), general_question("gen-02")]
    llm = FakeLLM(
        responses=[
            costly_search(300, "t1"),
            costly_answer("An unrelated answer.", "S1", 300),
        ]
    )
    state = {"records": [], "runs": 0}

    run_questions(questions, llm, StubIndex(CHUNKS), state, budget_tokens=500, max_calls=100)

    assert state["stopped_because"] == "token_budget"
    assert len(state["records"]) == 1
    assert state["records"][0]["id"] == "gen-01"
    assert state["records"][0]["mode"] == "agent"
    assert state["records"][0]["llm_calls"] == 2

    # --resume: a fresh client, the same state, the remaining question gets a turn
    llm2 = FakeLLM(
        responses=[
            tool_use_response("search_clauses", {"query": "2047 plan"}, "t2"),
            good_json("An unrelated answer.", "S1"),
        ]
    )
    run_questions(questions, llm2, StubIndex(CHUNKS), state, budget_tokens=500, max_calls=100)

    assert len(state["records"]) == 2
    assert {r["id"] for r in state["records"]} == {"gen-01", "gen-02"}
    assert state["stopped_because"] == "finished"


# --- refusal when fewer than 40 questions are verified ------------------------------


def test_refusal_when_fewer_than_40_questions_are_verified() -> None:
    """The gate is a count, independent of file I/O."""
    few = [location_question(f"q{n}") for n in range(39)]
    with pytest.raises(InsufficientQuestions):
        ensure_enough(few)

    enough = [location_question(f"q{n}") for n in range(40)]
    ensure_enough(enough)  # does not raise


# --- a small helper ------------------------------------------------------------------


def _with(**changes):
    """A copy of the real settings with some values changed, for monkeypatch.setattr."""
    from dataclasses import replace

    from app.config import settings

    return replace(settings, **changes)
