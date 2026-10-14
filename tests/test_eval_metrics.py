"""Tests for eval/metrics.py: the arithmetic, on numbers worked out by hand.

A wrong metric is worse than no metric, because it looks like evidence. Everything here
is small enough to check on paper.
"""

import pytest

from eval.metrics import (
    BOOTSTRAP_RESAMPLES,
    QuestionScore,
    ThresholdRow,
    bootstrap_interval,
    first_hit_rank,
    mean,
    mrr,
    paired_difference_interval,
    percentile,
    recall,
    suggest_threshold,
    threshold_sweep,
)


def score(rank: int | None, top: float = 0.05, category: str = "general") -> QuestionScore:
    """One question's score, with only what the metrics read."""
    return QuestionScore(
        question_id=f"q{rank}", category=category, first_hit_rank=rank, top_score=top
    )


# --- finding the first hit -------------------------------------------------------


def test_the_first_acceptable_chunk_is_found_by_position() -> None:
    """Ranks are 1-based, so the top result is rank 1 and not rank 0."""
    assert first_hit_rank(["a", "b", "c"], {"a"}) == 1
    assert first_hit_rank(["a", "b", "c"], {"c"}) == 3
    assert first_hit_rank(["a", "b", "c"], {"b", "c"}) == 2, "the first one counts"
    assert first_hit_rank(["a", "b", "c"], {"z"}) is None
    assert first_hit_rank([], {"a"}) is None


# --- recall ----------------------------------------------------------------------


def test_recall_at_k_is_a_share_of_questions_not_of_results() -> None:
    """One question either had its answer in the top k or it did not."""
    scores = [score(1), score(3), score(5), score(None)]
    assert recall(scores, 1) == pytest.approx(1 / 4)
    assert recall(scores, 3) == pytest.approx(2 / 4)
    assert recall(scores, 5) == pytest.approx(3 / 4)


def test_recall_is_monotonic_in_k() -> None:
    """A deeper cut-off can never find less."""
    scores = [score(1), score(2), score(4), score(None), score(7)]
    assert recall(scores, 1) <= recall(scores, 3) <= recall(scores, 5)


def test_a_question_whose_answer_was_missed_scores_zero_everywhere() -> None:
    assert recall([score(None)], 1) == 0.0
    assert recall([score(None)], 5) == 0.0
    assert mrr([score(None)]) == 0.0


def test_recall_of_an_empty_set_is_zero_not_an_error() -> None:
    """A category with no questions must not divide by zero."""
    assert recall([], 5) == 0.0
    assert mrr([]) == 0.0
    assert mean([]) == 0.0


# --- MRR -------------------------------------------------------------------------


def test_reciprocal_rank_is_one_over_the_rank() -> None:
    """Rank 1 is worth 1, rank 4 is worth 0.25."""
    assert score(1).reciprocal_rank == 1.0
    assert score(2).reciprocal_rank == 0.5
    assert score(4).reciprocal_rank == pytest.approx(0.25)
    assert score(None).reciprocal_rank == 0.0


def test_mrr_worked_out_by_hand() -> None:
    """(1 + 0.5 + 0.25 + 0) / 4 = 0.4375."""
    assert mrr([score(1), score(2), score(4), score(None)]) == pytest.approx(0.4375)


def test_mrr_rewards_a_higher_rank_where_recall_cannot_tell() -> None:
    """Both sets have the answer in the top 5; MRR says which found it sooner."""
    sooner = [score(1), score(1)]
    later = [score(5), score(5)]
    assert recall(sooner, 5) == recall(later, 5) == 1.0
    assert mrr(sooner) > mrr(later)


# --- percentiles and bootstrap ---------------------------------------------------


def test_percentile_interpolates_between_points() -> None:
    values = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0.0) == 0.0
    assert percentile(values, 1.0) == 4.0
    assert percentile(values, 0.5) == 2.0
    assert percentile(values, 0.25) == pytest.approx(1.0)
    assert percentile([], 0.5) == 0.0
    assert percentile([7.0], 0.9) == 7.0


def test_a_bootstrap_interval_brackets_the_mean() -> None:
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    low, high = bootstrap_interval(values)
    assert low <= mean(values) <= high
    assert 0.0 <= low < high <= 1.0


def test_a_bootstrap_interval_is_reproducible() -> None:
    """The seed is fixed, so the same data gives the same results file every run."""
    values = [1.0, 0.0, 1.0, 1.0, 0.0]
    assert bootstrap_interval(values) == bootstrap_interval(values)


def test_identical_values_give_a_zero_width_interval() -> None:
    """Every resample of the same number is that number, so there is no uncertainty."""
    low, high = bootstrap_interval([1.0] * 20)
    assert low == high == 1.0


def test_more_questions_give_a_narrower_interval() -> None:
    """The point of the interval: a small question set cannot support a strong claim."""
    pattern = [1.0, 0.0]
    few = bootstrap_interval(pattern * 5)
    many = bootstrap_interval(pattern * 100)
    assert (many[1] - many[0]) < (few[1] - few[0])


def test_an_empty_bootstrap_is_zero_rather_than_an_error() -> None:
    assert bootstrap_interval([]) == (0.0, 0.0)


# --- the paired comparison -------------------------------------------------------


def test_a_paired_interval_excludes_zero_when_one_side_always_wins() -> None:
    """Location helps on every question: the difference is real, not luck."""
    aware = [1.0] * 20
    plain = [0.0] * 20
    low, high = paired_difference_interval(aware, plain)
    assert low == high == 1.0
    assert low > 0


def test_a_paired_interval_contains_zero_when_the_two_are_the_same() -> None:
    """No difference per question means no difference to detect."""
    same = [1.0, 0.0, 1.0, 1.0, 0.0] * 4
    low, high = paired_difference_interval(same, list(same))
    assert low == high == 0.0


def test_a_paired_interval_contains_zero_when_wins_and_losses_cancel() -> None:
    """Better on half, worse on half: this set cannot say either is better."""
    aware = [1.0, 0.0] * 10
    plain = [0.0, 1.0] * 10
    low, high = paired_difference_interval(aware, plain)
    assert low < 0 < high


def test_a_paired_comparison_needs_matching_lengths() -> None:
    """Mismatched lists would pair the wrong questions together, silently."""
    with pytest.raises(ValueError):
        paired_difference_interval([1.0, 0.0], [1.0])


def test_the_resample_count_is_the_documented_one() -> None:
    """A guard on the number quoted in the reports."""
    assert BOOTSTRAP_RESAMPLES == 1000


# --- the threshold sweep ---------------------------------------------------------


def test_the_sweep_measures_what_is_caught_against_what_is_lost() -> None:
    """Answerable questions score high; unanswerable ones score low."""
    answerable = [0.05, 0.06, 0.04, 0.05]
    unanswerable = [0.01, 0.02]
    rows = threshold_sweep(answerable, unanswerable, thresholds=[0.03])
    assert rows[0].caught == 1.0, "both unanswerable questions fall below 0.03"
    assert rows[0].lost == 0.0, "no answerable question does"
    assert rows[0].margin == 1.0


def test_a_threshold_that_is_too_high_loses_real_answers() -> None:
    rows = threshold_sweep([0.05, 0.06], [0.01], thresholds=[0.10])
    assert rows[0].caught == 1.0
    assert rows[0].lost == 1.0
    assert rows[0].margin == 0.0, "catching everything by refusing everything is worth nothing"


def test_a_threshold_that_is_too_low_catches_nothing() -> None:
    rows = threshold_sweep([0.05], [0.01], thresholds=[0.001])
    assert rows[0].caught == 0.0
    assert rows[0].lost == 0.0


def test_the_suggestion_is_the_widest_margin() -> None:
    rows = [
        ThresholdRow(threshold=0.01, caught=0.2, lost=0.0),
        ThresholdRow(threshold=0.03, caught=0.9, lost=0.1),
        ThresholdRow(threshold=0.09, caught=1.0, lost=0.9),
    ]
    assert suggest_threshold(rows).threshold == 0.03


def test_a_tie_goes_to_the_lower_threshold() -> None:
    """Losing a real answer is worse than failing to catch an unanswerable question."""
    rows = [
        ThresholdRow(threshold=0.02, caught=0.5, lost=0.1),
        ThresholdRow(threshold=0.08, caught=0.9, lost=0.5),
    ]
    assert suggest_threshold(rows).threshold == 0.02


def test_suggesting_from_nothing_returns_nothing() -> None:
    assert suggest_threshold([]) is None
