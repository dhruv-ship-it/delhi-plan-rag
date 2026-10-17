"""Tests for the raw score plumbing, the reranker, and the abstention decision.

No test here loads the cross-encoder. `apply_reranker` is driven with a stubbed
`rerank_scores`, because what needs protecting is the wiring — which query is handed
over, what happens when it is off, what happens when it fails — and not the model's
arithmetic, which is not ours.
"""

from dataclasses import replace

import pytest

from app.answer import is_weak
from app.config import DENSE_COSINE, RERANK_SCORE, settings
from app.rerank import available, supported_models, unavailable_reason
from app.retrieval import Result, SearchReport, apply_reranker, signal_value


def result(chunk_id: str, fused: float = 0.03, cosine: float | None = 0.8) -> Result:
    """One result with the score fields the signal readers use."""
    return Result(
        chunk_id=chunk_id,
        doc_id="MPD47_GAZETTE_EN",
        clause_id="4.2.3",
        heading_path=["4.2 TOD"],
        chapter="4",
        page_start=753,
        page_end=753,
        zone_primary="tod",
        zone_mentions=["tod"],
        text=f"text of {chunk_id}",
        dense_rank=1,
        bm25_rank=1,
        dense_distance=None if cosine is None else 1.0 - cosine,
        fused_score=fused,
        bm25_score=12.5,
    )


# --- the raw scores on a Result -------------------------------------------------


def test_dense_cosine_is_one_minus_the_distance() -> None:
    """Chroma is built with cosine space, where the distance is 1 - similarity."""
    assert result("a", cosine=0.8).dense_cosine == pytest.approx(0.8)
    assert result("a", cosine=0.0).dense_cosine == pytest.approx(0.0)


def test_dense_cosine_is_none_when_the_dense_pool_missed_the_chunk() -> None:
    """A keyword-only hit has no similarity, and that is a gap, not a zero."""
    assert result("a", cosine=None).dense_cosine is None


def test_every_raw_score_reaches_to_dict() -> None:
    """The API and the answer record both read the breakdown from here."""
    record = result("a").to_dict(include_text=False)
    for field in ("dense_cosine", "bm25_score", "rerank_score", "rerank_rank", "fused_score"):
        assert field in record, field
    assert record["bm25_score"] == 12.5
    assert record["rerank_score"] is None


def test_signal_value_reads_the_named_field() -> None:
    """One function, so the pre-check and the evaluation cannot disagree."""
    item = replace(result("a", cosine=0.75), rerank_score=3.5)
    assert signal_value(item, DENSE_COSINE) == pytest.approx(0.75)
    assert signal_value(item, RERANK_SCORE) == pytest.approx(3.5)


def test_an_unknown_signal_falls_back_to_the_dense_one() -> None:
    """A typo in .env should degrade to the default, not disable the guard."""
    assert signal_value(result("a", cosine=0.75), "nonsense") == pytest.approx(0.75)


# --- the reranker, on and off ---------------------------------------------------


def test_the_reranker_is_skipped_when_it_is_off() -> None:
    """Off is the default, and off means the fused order is returned untouched."""
    results = [result("a", fused=0.05), result("b", fused=0.04), result("c", fused=0.03)]
    report = SearchReport(query="q", expanded_query="q")
    out = apply_reranker("q", results, k=2, report=report)
    assert [item.chunk_id for item in out] == ["a", "b"]
    assert all(item.rerank_score is None for item in out)
    assert report.reranked == 0


def test_the_reranker_reorders_and_records_its_scores(monkeypatch) -> None:
    """The cross-encoder's order wins, and each result keeps the score it won with."""
    monkeypatch.setattr("app.retrieval.settings", replace(settings, use_reranker=True))
    monkeypatch.setattr("app.rerank.available", lambda: True)
    monkeypatch.setattr("app.rerank.rerank_scores", lambda query, docs: [1.0, 9.0, 5.0])

    results = [result("a", fused=0.05), result("b", fused=0.04), result("c", fused=0.03)]
    report = SearchReport(query="q", expanded_query="q")
    out = apply_reranker("q", results, k=3, report=report)

    assert [item.chunk_id for item in out] == ["b", "c", "a"]
    assert [item.rerank_rank for item in out] == [1, 2, 3]
    assert out[0].rerank_score == pytest.approx(9.0)
    assert report.reranked == 3


def test_the_reranker_keeps_the_fused_score_it_started_from(monkeypatch) -> None:
    """Reranking replaces the order, not the record of how the chunk got there."""
    monkeypatch.setattr("app.retrieval.settings", replace(settings, use_reranker=True))
    monkeypatch.setattr("app.rerank.available", lambda: True)
    monkeypatch.setattr("app.rerank.rerank_scores", lambda query, docs: [1.0, 9.0])

    out = apply_reranker("q", [result("a", fused=0.05), result("b", fused=0.04)], k=2)
    assert out[0].chunk_id == "b"
    assert out[0].fused_score == pytest.approx(0.04)
    assert out[0].dense_rank == 1


def test_the_reranker_is_handed_the_query_it_is_given(monkeypatch) -> None:
    """Location-aware search passes the expanded query, so it judges the same question."""
    monkeypatch.setattr("app.retrieval.settings", replace(settings, use_reranker=True))
    monkeypatch.setattr("app.rerank.available", lambda: True)
    seen = {}

    def spy(query, docs):
        seen["query"] = query
        seen["docs"] = list(docs)
        return [1.0] * len(docs)

    monkeypatch.setattr("app.rerank.rerank_scores", spy)
    apply_reranker("plot size transit oriented development TOD zone", [result("a")], k=1)
    assert seen["query"] == "plot size transit oriented development TOD zone"
    assert seen["docs"] == ["text of a"]


def test_only_the_shortlist_is_reranked(monkeypatch) -> None:
    """The cross-encoder rescores rerank_pool results, not the whole pool."""
    monkeypatch.setattr(
        "app.retrieval.settings", replace(settings, use_reranker=True, rerank_pool=3)
    )
    monkeypatch.setattr("app.rerank.available", lambda: True)
    counted = {}

    def spy(query, docs):
        counted["n"] = len(docs)
        return list(range(len(docs)))

    monkeypatch.setattr("app.rerank.rerank_scores", spy)
    results = [result(f"c{number}") for number in range(10)]
    apply_reranker("q", results, k=2)
    assert counted["n"] == 3


def test_a_reranker_failure_falls_back_to_the_fused_order(monkeypatch) -> None:
    """The reranker is an optimisation; losing it must not lose the answer."""
    monkeypatch.setattr("app.retrieval.settings", replace(settings, use_reranker=True))
    monkeypatch.setattr("app.rerank.available", lambda: True)

    def boom(query, docs):
        raise RuntimeError("onnx said no")

    monkeypatch.setattr("app.rerank.rerank_scores", boom)
    report = SearchReport(query="q", expanded_query="q")
    out = apply_reranker("q", [result("a", fused=0.05), result("b", fused=0.04)], k=2, report=report)

    assert [item.chunk_id for item in out] == ["a", "b"]
    assert report.reranked == 0
    assert "onnx said no" in report.rerank_error


def test_reranking_nothing_returns_nothing(monkeypatch) -> None:
    """An empty result list is not an error."""
    monkeypatch.setattr("app.retrieval.settings", replace(settings, use_reranker=True))
    assert apply_reranker("q", [], k=5) == []


def test_the_installed_fastembed_is_reported_either_way() -> None:
    """Whether the cross-encoder exists is a fact to record, not to assume (D-070)."""
    if available():
        assert unavailable_reason() == ""
        names = [model["model"] for model in supported_models()]
        assert settings.rerank_model in names
    else:
        assert unavailable_reason()
        assert supported_models() == []


# --- what the settings do with the two signals ---------------------------------


def test_the_rerank_signal_falls_back_when_the_reranker_is_off() -> None:
    """Asking for a score nothing produces would silently disable the guard."""
    asked = replace(settings, abstain_signal=RERANK_SCORE, use_reranker=False)
    assert asked.abstention_signal == DENSE_COSINE


def test_an_unknown_signal_name_falls_back_too() -> None:
    assert replace(settings, abstain_signal="guesswork").abstention_signal == DENSE_COSINE


def test_the_dense_signal_is_used_as_asked() -> None:
    assert replace(settings, abstain_signal=DENSE_COSINE).abstention_signal == DENSE_COSINE


# --- the abstention decision, per signal ---------------------------------------


def test_nothing_retrieved_is_always_weak() -> None:
    assert is_weak([]) is True


def test_the_dense_signal_decides_on_each_side_of_the_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.answer.settings",
        replace(settings, abstain_signal=DENSE_COSINE, abstain_threshold=0.70),
    )
    assert is_weak([result("a", cosine=0.69)]) is True
    assert is_weak([result("a", cosine=0.71)]) is False


def test_the_rerank_signal_decides_when_the_reranker_is_on(monkeypatch) -> None:
    """A negative threshold is normal here: cross-encoder scores run about -11 to +11."""
    monkeypatch.setattr("app.rerank.available", lambda: True)
    monkeypatch.setattr(
        "app.answer.settings",
        replace(
            settings,
            abstain_signal=RERANK_SCORE,
            abstain_threshold=-2.0,
            use_reranker=True,
        ),
    )
    assert is_weak([replace(result("a"), rerank_score=-3.0)]) is True
    assert is_weak([replace(result("a"), rerank_score=-1.0)]) is False


def test_a_missing_signal_value_is_not_treated_as_weak(monkeypatch) -> None:
    """A keyword-only hit has no cosine similarity, which is a gap and not evidence."""
    monkeypatch.setattr(
        "app.answer.settings",
        replace(settings, abstain_signal=DENSE_COSINE, abstain_threshold=0.70),
    )
    assert is_weak([result("a", cosine=None)]) is False


def test_the_fused_score_no_longer_decides_anything(monkeypatch) -> None:
    """The point of D-071: a high fused score cannot rescue a low signal, or vice versa.

    Both results below have the fused score of a chunk both indexes ranked first. Only
    the raw signal separates them, which is the behaviour the old check could not have.
    """
    monkeypatch.setattr(
        "app.answer.settings",
        replace(settings, abstain_signal=DENSE_COSINE, abstain_threshold=0.70),
    )
    both_ranked_first = 2 / 61
    assert is_weak([result("a", fused=both_ranked_first, cosine=0.50)]) is True
    assert is_weak([result("a", fused=0.0001, cosine=0.90)]) is False
