"""The arithmetic behind the evaluation: recall@k, MRR, and bootstrap confidence intervals.

Kept in its own module, with no retrieval and no file reading, so every number
`run_eval.py` prints can be checked against hand-worked examples in
`tests/test_eval_metrics.py`. A metric that is wrong is worse than no metric, because it
looks like evidence.

What each one means, in one line each (eval/README.md has the longer version):

  recall@k   did the right clause appear in the top k? 1 or 0 per question, averaged
  MRR        1/(rank of the first right clause), so rank 1 scores 1 and rank 4 scores 0.25
  bootstrap  resample the questions with replacement 1,000 times to see how much the
             average would move if we had asked a different set of questions
"""

import random
from dataclasses import dataclass, field

#: The cut-offs recall is reported at.
RECALL_AT = (1, 3, 5)
#: How many resamples a bootstrap interval uses.
BOOTSTRAP_RESAMPLES = 1000
#: Fixed, so the same results file is produced every run.
BOOTSTRAP_SEED = 20261015
#: The interval reported: 95%, so the 2.5th and 97.5th percentiles.
CONFIDENCE = 0.95


@dataclass
class QuestionScore:
    """How one configuration did on one question."""

    question_id: str
    category: str
    #: 1-based rank of the first acceptable chunk, or None if none was retrieved.
    first_hit_rank: int | None
    #: The best fused score the retriever produced, for the abstention sweep.
    top_score: float
    retrieved: list[str] = field(default_factory=list)

    def recall_at(self, k: int) -> int:
        """1 when an acceptable chunk is in the top k, else 0."""
        return 1 if self.first_hit_rank is not None and self.first_hit_rank <= k else 0

    @property
    def reciprocal_rank(self) -> float:
        """1/rank of the first acceptable chunk, or 0 when there was none."""
        return 1.0 / self.first_hit_rank if self.first_hit_rank else 0.0


def first_hit_rank(retrieved: list[str], wanted: set[str]) -> int | None:
    """The 1-based position of the first retrieved chunk that is acceptable."""
    for position, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in wanted:
            return position
    return None


def mean(values: list[float]) -> float:
    """The average, or 0.0 for an empty list."""
    return sum(values) / len(values) if values else 0.0


def recall(scores: list[QuestionScore], k: int) -> float:
    """The share of questions whose answer was in the top k."""
    return mean([score.recall_at(k) for score in scores])


def mrr(scores: list[QuestionScore]) -> float:
    """Mean reciprocal rank over the questions."""
    return mean([score.reciprocal_rank for score in scores])


def percentile(sorted_values: list[float], fraction: float) -> float:
    """A percentile of an already-sorted list, by linear interpolation."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def bootstrap_interval(
    values: list[float],
    resamples: int = BOOTSTRAP_RESAMPLES,
    confidence: float = CONFIDENCE,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """A confidence interval for the mean of `values`, by resampling with replacement.

    With 50-odd questions, an average of 0.72 could easily have been 0.62 or 0.82 on a
    different set of questions. Resampling the questions we have, 1,000 times, shows how
    wide that range is, so a difference between two configurations is not read as real
    when it is inside the noise. The seed is fixed so the same numbers come out of every
    run of the same data.
    """
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    count = len(values)
    means = sorted(
        mean([values[rng.randrange(count)] for _ in range(count)]) for _ in range(resamples)
    )
    tail = (1 - confidence) / 2
    return (percentile(means, tail), percentile(means, 1 - tail))


def paired_difference_interval(
    first: list[float],
    second: list[float],
    resamples: int = BOOTSTRAP_RESAMPLES,
    confidence: float = CONFIDENCE,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """A confidence interval for the mean of (first - second), question by question.

    Paired, which matters: the two configurations answered the *same* questions, so the
    per-question difference removes the variation caused by some questions simply being
    harder than others. An interval that does not contain 0 is the evidence that one
    configuration is genuinely better, rather than luckier.
    """
    if len(first) != len(second):
        raise ValueError("paired comparison needs the same number of questions in both")
    return bootstrap_interval(
        [one - other for one, other in zip(first, second)], resamples, confidence, seed
    )


# --- choosing an abstention threshold --------------------------------------------


@dataclass
class ThresholdRow:
    """How one candidate abstention threshold would behave."""

    threshold: float
    #: Of the questions that should be refused, the share that fall below it. Higher is better.
    caught: float
    #: Of the answerable questions, the share wrongly falling below it. Lower is better.
    lost: float

    @property
    def margin(self) -> float:
        """How much better than chance this threshold separates the two groups."""
        return self.caught - self.lost


def threshold_sweep(
    answerable_scores: list[float],
    abstain_scores: list[float],
    thresholds: list[float] | None = None,
) -> list[ThresholdRow]:
    """For each candidate threshold, what it would catch and what it would lose.

    A retrieval-only check: it asks whether the top fused score alone can separate the
    questions the corpus answers from the ones it does not, with no LLM call involved.
    """
    if thresholds is None:
        thresholds = [round(0.002 * step, 4) for step in range(1, 26)]
    rows = []
    for threshold in thresholds:
        caught = mean([1 if score < threshold else 0 for score in abstain_scores])
        lost = mean([1 if score < threshold else 0 for score in answerable_scores])
        rows.append(ThresholdRow(threshold=threshold, caught=caught, lost=lost))
    return rows


def suggest_threshold(rows: list[ThresholdRow]) -> ThresholdRow | None:
    """The threshold with the widest gap between what it catches and what it loses.

    Ties go to the lower threshold, because losing a real answer is worse than failing
    to catch an unanswerable question: the first is a wrong answer withheld from someone
    who needed it, the second is a bad answer that the citation check may still stop.
    """
    if not rows:
        return None
    return max(rows, key=lambda row: (round(row.margin, 6), -row.threshold))
