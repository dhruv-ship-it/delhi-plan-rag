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
    #: The best fused score the retriever produced. Kept for continuity with earlier
    #: runs; it is **not** a usable abstention signal, because an RRF score only
    #: encodes rank position (D-071).
    top_score: float
    retrieved: list[str] = field(default_factory=list)
    #: Top-1 dense cosine similarity, or None when the dense pool missed everything.
    top_dense_cosine: float | None = None
    #: Top-1 cross-encoder score, or None when the reranker did not run.
    top_rerank_score: float | None = None

    def signal(self, name: str) -> float | None:
        """The named signal's top-1 value for this question, or None when it has none."""
        return {
            "fused_score": self.top_score,
            "dense_cosine": self.top_dense_cosine,
            "rerank_score": self.top_rerank_score,
        }.get(name)

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


#: z for a 95% Wilson interval: the inverse normal CDF at 0.975. Hardcoded rather than
#: computed, because `CONFIDENCE` above is the only level this project reports at and a
#: general inverse-normal routine is not worth a new dependency for one constant.
WILSON_Z_95 = 1.959963985


def wilson_interval(successes: int, n: int) -> tuple[float, float]:
    """A 95% Wilson score interval for a proportion from `n` Bernoulli trials.

    Unlike `bootstrap_interval`, this needs no resampling and no question-level data:
    just a count of successes out of n, which is what `answer_eval.py` has for "was
    this question answered", "did the citation cite a verified clause", and so on. It
    behaves better than a plain `phat ± z*se` interval exactly where that one breaks —
    n small, or phat near 0 or 1 — which is the normal case for an evaluation run of a
    few dozen questions.

    (0.0, 0.0) for n = 0, matching `bootstrap_interval`'s empty-list behaviour: there is
    nothing to report, not a rate of zero.
    """
    if n <= 0:
        return (0.0, 0.0)
    z = WILSON_Z_95
    phat = successes / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    margin = (z * ((phat * (1 - phat) + z * z / (4 * n)) / n) ** 0.5) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


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


#: How many candidate thresholds a sweep tries when it picks its own.
SWEEP_STEPS = 25


def sweep_thresholds(scores: list[float], steps: int = SWEEP_STEPS) -> list[float]:
    """Candidate thresholds spread across the range the scores actually occupy.

    The thresholds cannot be a fixed list any more. The sweep used to try 0.002 to 0.05,
    which is the range an RRF score lives in; a cosine similarity sits around 0.6 to
    0.9 and a cross-encoder score runs from about -11 to +11, so a fixed list would
    report 25 rows of zeroes for either of them (D-071).
    """
    if not scores:
        return []
    low, high = min(scores), max(scores)
    if high == low:
        high = low + 1.0
    return [round(low + (high - low) * step / steps, 4) for step in range(steps + 1)]


def threshold_sweep(
    answerable_scores: list[float],
    abstain_scores: list[float],
    thresholds: list[float] | None = None,
) -> list[ThresholdRow]:
    """For each candidate threshold, what it would catch and what it would lose.

    A retrieval-only check: it asks whether one top-1 score can separate the questions
    the corpus answers from the ones it does not, with no LLM call involved. When no
    thresholds are given it picks them from the range the scores occupy, so the same
    function works for every signal.
    """
    if thresholds is None:
        thresholds = sweep_thresholds(answerable_scores + abstain_scores)
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


def safest_threshold(rows: list[ThresholdRow]) -> ThresholdRow | None:
    """The highest threshold that loses nothing at all: the provisional value.

    This is the one that may be used before the questions have been checked by a
    person. It is chosen without reference to what it catches, which is the point —
    anything that trades a real answer away has been fitted to the question set, and a
    question set nobody has verified is not evidence (D-054, D-071).
    """
    harmless = [row for row in rows if row.lost == 0.0]
    if not harmless:
        return None
    return max(harmless, key=lambda row: row.threshold)
