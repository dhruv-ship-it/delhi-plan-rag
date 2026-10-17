"""Measure the abstention signal over a question set and report what a threshold costs.

    uv run python scripts/tune_abstention.py
    uv run python scripts/tune_abstention.py --signal rerank_score
    uv run python scripts/tune_abstention.py --questions eval/questions_verified.jsonl

For each question it runs the real location-aware search and records the top-1 value of
the signal. Then it reports, for each candidate threshold, how many should-abstain
questions fall below it (**caught**) against how many answerable ones would be wrongly
refused (**lost**), and names two values:

  * the **provisional** threshold — the largest value that loses nothing at all, which
    is the most conservative choice available and the one to use before anybody has
    checked the questions (D-071);
  * the **best margin** threshold — the widest gap between caught and lost, which is
    the value worth adopting *once the questions are verified*.

It prints both and changes nothing. Setting `ABSTAIN_THRESHOLD` is a deliberate act in
`.env`, because the number is only as trustworthy as the questions it came from: a
threshold fitted to questions Claude wrote measures Claude's agreement with itself
(D-054). The script says so in its own output when the questions are unverified.

Safe to re-run. It only reads.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import ABSTAIN_SIGNALS, DENSE_COSINE, settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402
from app.retrieval import SearchReport, get_index, search, signal_value  # noqa: E402

#: How many thresholds to try between the lowest and highest observed value.
SWEEP_STEPS = 24
#: A little below the lowest answerable score, so the provisional value is strictly safe.
PROVISIONAL_MARGIN = 0.01


def read_questions(path: Path) -> list[dict]:
    """Read a questions JSONL file."""
    if not path.exists():
        raise SystemExit(f"{path.as_posix()} is missing.")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def top_signal(question: dict, signal: str, index, points: dict) -> float | None:
    """The top-1 value of `signal` for one question's own search."""
    point = points.get(question.get("point_name") or "")
    zones = point["zones"] if point else None
    report = SearchReport(query=question["question"], expanded_query=question["question"])
    results = search(
        question["question"], k=5, mode="hybrid", zones=zones, index=index, report=report
    )
    if not results:
        return None
    return signal_value(results[0], signal)


def percentiles(values: list[float]) -> dict[str, float | None]:
    """p5, p25, p50, p75 and p95 of a list, by nearest rank."""
    if not values:
        return {name: None for name in ("p5", "p25", "p50", "p75", "p95")}
    ordered = sorted(values)
    def at(share: float) -> float:
        position = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
        return ordered[position]
    return {"p5": at(0.05), "p25": at(0.25), "p50": at(0.50), "p75": at(0.75), "p95": at(0.95)}


def sweep(answerable: list[float], should_abstain: list[float]) -> list[dict]:
    """For each candidate threshold, the share caught and the share lost."""
    everything = answerable + should_abstain
    if not everything:
        return []
    low, high = min(everything), max(everything)
    if high == low:
        high = low + 1.0
    rows = []
    for step in range(SWEEP_STEPS + 1):
        threshold = low + (high - low) * step / SWEEP_STEPS
        caught = sum(1 for value in should_abstain if value < threshold)
        lost = sum(1 for value in answerable if value < threshold)
        rows.append(
            {
                "threshold": threshold,
                "caught": caught,
                "caught_share": caught / len(should_abstain) if should_abstain else 0.0,
                "lost": lost,
                "lost_share": lost / len(answerable) if answerable else 0.0,
            }
        )
    return rows


def provisional(answerable: list[float]) -> float:
    """The largest threshold that refuses none of the answerable questions.

    A little below the lowest answerable score, not equal to it, so a question that
    scored exactly the minimum is still answered.

    **The value is not clamped at zero**, and that matters. The first version of this
    function returned `max(0.0, ...)`, which is harmless for a cosine similarity and
    actively wrong for a cross-encoder score: those run from about -11 to +11, the
    lowest answerable draft question scored about -10, and clamping turned "refuse
    nothing" into a recommended threshold of 0.0 that would have refused 40% of the
    answerable questions. A guard written for one signal's range silently inverted its
    own meaning on another's (D-071).
    """
    if not answerable:
        return float("-inf")
    return min(answerable) - PROVISIONAL_MARGIN


def best_margin(rows: list[dict]) -> dict | None:
    """The row with the widest gap between caught and lost. Ties go to the lower value.

    Wrongly refusing a real question is worse than letting an unanswerable one through,
    because the first denies someone an answer the documents do contain while the second
    still has the citation check behind it (D-057).
    """
    if not rows:
        return None
    return max(rows, key=lambda row: (row["caught_share"] - row["lost_share"], -row["threshold"]))


def main() -> int:
    """Measure the signal and print the two candidate thresholds."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        default=str(Path("eval") / "questions_draft.jsonl"),
        help="the question file to measure (default: the drafts)",
    )
    parser.add_argument(
        "--signal", default=DENSE_COSINE, choices=list(ABSTAIN_SIGNALS), help="which score to read"
    )
    args = parser.parse_args()

    if args.signal == "rerank_score" and not settings.reranker_on:
        print("rerank_score needs the reranker on. Re-run with USE_RERANKER=1 set.")
        return 1

    questions = read_questions(Path(args.questions))
    points = {
        record["name"]: record
        for record in json.loads(
            (settings.project_root / "eval" / "points.json").read_text(encoding="utf-8")
        )
    }
    index = get_index()

    unverified = sum(1 for question in questions if not question.get("verified"))
    answerable: list[float] = []
    should_abstain: list[float] = []
    missing = 0

    for number, question in enumerate(questions, start=1):
        value = top_signal(question, args.signal, index, points)
        print(f"  {number:3d}/{len(questions)} {question['id']:10s} {args.signal} = "
              f"{'none' if value is None else f'{value:.4f}'}")
        if value is None:
            missing += 1
            continue
        (should_abstain if question.get("should_abstain") else answerable).append(value)

    rows = sweep(answerable, should_abstain)
    print()
    print(f"signal: {args.signal}   questions: {len(questions)}   "
          f"answerable: {len(answerable)}   should abstain: {len(should_abstain)}   "
          f"no result: {missing}")
    print()
    print("percentiles")
    print(
        markdown_table(
            ("group", "n", "p5", "p25", "p50", "p75", "p95", "min", "max"),
            [
                [name, str(len(values))]
                + [
                    "-" if value is None else f"{value:.4f}"
                    for value in percentiles(values).values()
                ]
                + [
                    "-" if not values else f"{min(values):.4f}",
                    "-" if not values else f"{max(values):.4f}",
                ]
                for name, values in (("answerable", answerable), ("should abstain", should_abstain))
            ],
        )
    )
    print()
    print("threshold sweep")
    print(
        markdown_table(
            ("threshold", "caught", "lost"),
            [
                [f"{row['threshold']:.4f}", f"{row['caught']} ({row['caught_share']:.0%})",
                 f"{row['lost']} ({row['lost_share']:.0%})"]
                for row in rows
            ],
        )
    )

    safe = provisional(answerable)
    best = best_margin(rows)
    print()
    print(f"PROVISIONAL threshold (loses nothing): {safe:.4f}")
    print(f"  it refuses {sum(1 for v in answerable if v < safe)} of {len(answerable)} answerable "
          f"and catches {sum(1 for v in should_abstain if v < safe)} of {len(should_abstain)} "
          "should-abstain questions")
    if best:
        print(
            f"widest margin:                         {best['threshold']:.4f} "
            f"(catches {best['caught_share']:.0%}, loses {best['lost_share']:.0%})"
        )
    if unverified:
        print()
        print(
            f"{unverified} of {len(questions)} questions are unverified, so only the "
            "provisional value may be used. The widest-margin value above is fitted to "
            "questions Claude wrote and is not a measurement (D-054, D-071)."
        )
    print()
    print(f"Set it in .env:  ABSTAIN_SIGNAL={args.signal}  ABSTAIN_THRESHOLD={safe:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
