"""Measure how well retrieval finds the right clause, across four configurations.

Reads  eval/questions.jsonl if it exists, else eval/questions_draft.jsonl
       eval/points.json
Writes eval/results/<timestamp>.md and .json
       eval/results/DRYRUN_<label>_<timestamp>.md for an unverified run

    uv run python eval/run_eval.py                       # verified questions only
    uv run python eval/run_eval.py --include-unverified  # a dry run, clearly labelled

By default only questions with `verified: true` are used, and the script stops with an
explanation if there are none. That is deliberate: the 60 questions in
`questions_draft.jsonl` were written by Claude from the same chunks the retriever
searches, so a score against them measures how well the retriever agrees with its own
author. Those numbers must never be reported as results. See eval/README.md.

Four configurations are compared:

  dense            embeddings only
  bm25             keywords only
  hybrid           both, fused with reciprocal rank fusion
  hybrid+location  hybrid plus the zone exclusion, boost and query expansion

The location configuration can only differ on questions that carry coordinates, so the
report states how many of those there were.
"""

import argparse
import json
import sys
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.metrics import (  # noqa: E402
    BOOTSTRAP_RESAMPLES,
    CONFIDENCE,
    RECALL_AT,
    QuestionScore,
    bootstrap_interval,
    first_hit_rank,
    mrr,
    paired_difference_interval,
    recall,
    safest_threshold,
    suggest_threshold,
    threshold_sweep,
)

from app.config import ABSTAIN_SIGNALS, settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402
from app.rerank import available as reranker_available  # noqa: E402
from app.retrieval import get_index, rank, search  # noqa: E402

#: The configurations always scored.
BASE_CONFIGURATIONS = ("dense", "bm25", "hybrid", "hybrid+location")
#: Scored as well when the installed fastembed has a cross-encoder (D-070).
RERANK_CONFIGURATION = "hybrid+location+rerank"


def configurations() -> tuple[str, ...]:
    """Which configurations this run can score.

    The rerank configuration is included only when the cross-encoder is importable,
    so the harness runs on a machine whose fastembed does not have one and says so
    in the report rather than failing.
    """
    if reranker_available():
        return BASE_CONFIGURATIONS + (RERANK_CONFIGURATION,)
    return BASE_CONFIGURATIONS


CONFIGURATIONS = configurations()

#: The signals the abstention analysis reports on, in report order. `fused_score`
#: is included so a reader can see for themselves why it was replaced (D-071).
ANALYSED_SIGNALS = ("fused_score",) + tuple(ABSTAIN_SIGNALS)
#: How deep to retrieve. Must be at least the largest recall cut-off.
TOP_K = max(RECALL_AT)

DRY_RUN_BANNER = (
    "> # DRY RUN - UNVERIFIED QUESTIONS - NOT FOR RESUME OR REPORTING\n"
    "> \n"
    "> Every question in this run has `verified: false`. They were drafted by Claude "
    "from the same chunks the retriever searches, so these numbers measure how well "
    "the retriever agrees with the person who wrote the questions, not how well it "
    "answers real ones. They are here to prove the harness runs end to end.\n"
    "> \n"
    "> **Do not put these numbers in a README, a resume or a conversation.** "
    "Verify the questions first: see `eval/README.md`."
)


@contextmanager
def reranker(on: bool):
    """Turn the reranker on or off for the body of the block.

    Settings is a frozen dataclass, so this swaps the module globals the retrieval
    code reads for a replaced copy and puts them back afterwards, whatever happens
    inside.
    """
    import app.location as location_module
    import app.retrieval as retrieval_module

    if on == settings.use_reranker:
        yield
        return
    patched = replace(settings, use_reranker=on)
    modules = (retrieval_module, location_module)
    originals = [(module, module.settings) for module in modules]
    for module, _ in originals:
        module.settings = patched
    try:
        yield
    finally:
        for module, original in originals:
            module.settings = original


def load_questions(include_unverified: bool) -> tuple[list[dict], Path, int]:
    """The questions to run, where they came from, and how many were skipped."""
    verified_path = settings.project_root / "eval" / "questions.jsonl"
    draft_path = settings.project_root / "eval" / "questions_draft.jsonl"
    path = verified_path if verified_path.exists() else draft_path
    if not path.exists():
        return [], path, 0

    with path.open(encoding="utf-8") as handle:
        everything = [json.loads(line) for line in handle if line.strip()]
    if include_unverified:
        return everything, path, 0
    kept = [item for item in everything if item.get("verified")]
    return kept, path, len(everything) - len(kept)


def retrieve(question: dict, configuration: str, index) -> tuple[list[str], dict]:
    """Run one question through one configuration. Returns (chunk ids, top-1 signals).

    The rerank configuration turns the reranker on for the length of the call by
    swapping in a copy of the settings, rather than relying on whatever USE_RERANKER
    happens to be: one run has to score every configuration in one pass, so the flag
    cannot be process-wide.
    """
    text = question["question"]
    has_point = question.get("lat") is not None and question.get("lon") is not None
    wants_location = configuration.startswith("hybrid+location")
    wants_rerank = configuration == RERANK_CONFIGURATION

    with reranker(wants_rerank):
        if wants_location and has_point:
            from app.spatial import get_zones

            zones = get_zones(question["lat"], question["lon"])
            results = search(text, k=TOP_K, mode="hybrid", zones=zones, index=index)
        else:
            mode = "hybrid" if wants_location else configuration
            results = rank(text, k=TOP_K, mode=mode, index=index)

    if not results:
        return [], {"fused_score": 0.0, "dense_cosine": None, "rerank_score": None}
    best = results[0]
    return (
        [result.chunk_id for result in results],
        {
            "fused_score": best.fused_score,
            "dense_cosine": best.dense_cosine,
            "rerank_score": best.rerank_score,
        },
    )


def score_questions(questions: list[dict], configuration: str, index) -> list[QuestionScore]:
    """Score every question under one configuration."""
    scored: list[QuestionScore] = []
    for question in questions:
        retrieved, signals = retrieve(question, configuration, index)
        wanted = set(question["expected_chunk_ids"]) | set(question["acceptable_chunk_ids"])
        scored.append(
            QuestionScore(
                question_id=question["id"],
                category=question["category"],
                first_hit_rank=first_hit_rank(retrieved, wanted) if wanted else None,
                top_score=signals["fused_score"],
                retrieved=retrieved,
                top_dense_cosine=signals["dense_cosine"],
                top_rerank_score=signals["rerank_score"],
            )
        )
    return scored


#: The percentiles the abstention analysis reports, in report order.
REPORTED_PERCENTILES = ((0.05, "p5"), (0.25, "p25"), (0.50, "p50"), (0.75, "p75"), (0.95, "p95"))


def signal_percentiles(values: list[float]) -> dict[str, float | None]:
    """p5, p25, p50, p75 and p95 of one signal's values, by nearest rank.

    Percentiles rather than a mean, because the question is not how high the signal
    usually is but how far the two groups overlap. Two distributions can share a mean
    and still be perfectly separable, or differ in mean and overlap completely, and it
    is the overlap that decides whether a threshold can work at all.
    """
    if not values:
        return {name: None for _, name in REPORTED_PERCENTILES}
    ordered = sorted(values)
    found = {}
    for share, name in REPORTED_PERCENTILES:
        position = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
        found[name] = ordered[position]
    return found


def summarise(scores: list[QuestionScore]) -> dict:
    """recall@1/3/5 and MRR for one group of scored questions."""
    return {
        "n": len(scores),
        **{f"recall@{k}": recall(scores, k) for k in RECALL_AT},
        "mrr": mrr(scores),
    }


def build_report(
    results: dict[str, list[QuestionScore]],
    questions: list[dict],
    source: Path,
    skipped: int,
    dry_run: bool,
    generated_at: str,
) -> tuple[str, dict]:
    """The Markdown report and the matching JSON record."""
    answerable = [item for item in questions if not item["should_abstain"]]
    answerable_ids = {item["id"] for item in answerable}
    with_point = [item for item in answerable if item.get("lat") is not None]

    lines: list[str] = []
    if dry_run:
        lines += [DRY_RUN_BANNER, ""]
    lines += [
        "# Retrieval evaluation",
        "",
        f"Generated {generated_at} by `eval/run_eval.py`.",
        "",
        f"Questions from `{source.relative_to(settings.project_root).as_posix()}`: "
        f"{len(questions)} used"
        + (f", {skipped} skipped as unverified" if skipped else "")
        + ".",
        "",
        "## How many questions of each kind",
        "",
    ]

    by_category: dict[str, list[dict]] = {}
    for item in questions:
        by_category.setdefault(item["category"], []).append(item)
    lines += [
        markdown_table(
            ("category", "questions", "with coordinates", "verified"),
            [
                [
                    category,
                    str(len(items)),
                    str(sum(1 for item in items if item.get("lat") is not None)),
                    str(sum(1 for item in items if item.get("verified"))),
                ]
                for category, items in sorted(by_category.items())
            ],
        ),
        "",
        f"Scores below are over the {len(answerable)} answerable questions (the "
        f"{len(questions) - len(answerable)} abstain questions have no right answer to "
        f"find). {len(with_point)} of them carry coordinates, which is the only subset "
        "where `hybrid+location` can differ from `hybrid`.",
        "",
        "## Overall",
        "",
    ]

    rows = []
    for configuration in CONFIGURATIONS:
        kept = [score for score in results[configuration] if score.question_id in answerable_ids]
        stats = summarise(kept)
        low, high = bootstrap_interval([score.recall_at(5) for score in kept])
        rows.append(
            [
                configuration,
                str(stats["n"]),
                f"{stats['recall@1']:.3f}",
                f"{stats['recall@3']:.3f}",
                f"{stats['recall@5']:.3f}",
                f"[{low:.3f}, {high:.3f}]",
                f"{stats['mrr']:.3f}",
            ]
        )
    lines += [
        markdown_table(
            ("configuration", "n", "recall@1", "recall@3", "recall@5", "recall@5 95% CI", "MRR"),
            rows,
        ),
        "",
        f"The interval is a bootstrap {CONFIDENCE:.0%} confidence interval over "
        f"{BOOTSTRAP_RESAMPLES:,} resamples of the questions. Two configurations whose "
        "intervals overlap heavily have not been shown to differ.",
        "",
        "## Per category",
        "",
    ]

    for category in sorted(by_category):
        if category == "abstain":
            continue
        ids = {item["id"] for item in by_category[category] if not item["should_abstain"]}
        if not ids:
            continue
        rows = []
        for configuration in CONFIGURATIONS:
            kept = [score for score in results[configuration] if score.question_id in ids]
            stats = summarise(kept)
            rows.append(
                [
                    configuration,
                    str(stats["n"]),
                    f"{stats['recall@1']:.3f}",
                    f"{stats['recall@3']:.3f}",
                    f"{stats['recall@5']:.3f}",
                    f"{stats['mrr']:.3f}",
                ]
            )
        lines += [
            f"### {category}",
            "",
            markdown_table(
                ("configuration", "n", "recall@1", "recall@3", "recall@5", "MRR"), rows
            ),
            "",
        ]

    # the paired comparison, on the questions where location can make a difference
    point_ids = {item["id"] for item in with_point}
    comparison: dict = {}
    if point_ids:
        aware = [s for s in results["hybrid+location"] if s.question_id in point_ids]
        plain = [s for s in results["hybrid"] if s.question_id in point_ids]
        aware.sort(key=lambda score: score.question_id)
        plain.sort(key=lambda score: score.question_id)
        for k in RECALL_AT:
            low, high = paired_difference_interval(
                [score.recall_at(k) for score in aware],
                [score.recall_at(k) for score in plain],
            )
            comparison[f"recall@{k}"] = {
                "difference": recall(aware, k) - recall(plain, k),
                "ci_low": low,
                "ci_high": high,
            }
        lines += [
            "## Does the location step help?",
            "",
            f"Paired comparison on the {len(point_ids)} answerable questions that carry "
            "coordinates: `hybrid+location` minus `hybrid`, question by question. Paired, "
            "because both configurations answered the same questions, so the difference "
            "removes the variation caused by some questions being harder than others.",
            "",
            markdown_table(
                ("metric", "hybrid", "hybrid+location", "difference", f"{CONFIDENCE:.0%} CI"),
                [
                    [
                        f"recall@{k}",
                        f"{recall(plain, k):.3f}",
                        f"{recall(aware, k):.3f}",
                        f"{comparison[f'recall@{k}']['difference']:+.3f}",
                        f"[{comparison[f'recall@{k}']['ci_low']:+.3f}, "
                        f"{comparison[f'recall@{k}']['ci_high']:+.3f}]",
                    ]
                    for k in RECALL_AT
                ],
            ),
            "",
            "An interval that excludes 0 is evidence the difference is real rather than "
            "luck. An interval containing 0 means this question set is too small to say.",
            "",
        ]

    # the abstention analysis, one section per signal
    abstain_ids = {item["id"] for item in questions if item["should_abstain"]}
    signal_analysis: dict[str, dict] = {}
    if abstain_ids:
        lines += [
            "## Which score can decide when to refuse?",
            "",
            "Retrieval only, no LLM call, scored under `hybrid+location` (and under "
            "`hybrid+location+rerank` for the cross-encoder signal, which only exists "
            "there). Each signal is the **top-1** value for the question: the question "
            "is refused before any API call when that value falls below "
            "`settings.abstain_threshold`.",
            "",
            "`fused_score` is here to be rejected rather than used. An RRF score only "
            "encodes rank position, so the best chunk for a question about Mumbai "
            "property tax scores exactly what the best chunk for a question the "
            "gazette answers in full scores. Read its two percentile rows against each "
            "other and the point is immediate (D-071).",
            "",
        ]
        for signal in ANALYSED_SIGNALS:
            source_configuration = (
                RERANK_CONFIGURATION if signal == "rerank_score" else "hybrid+location"
            )
            if source_configuration not in results:
                lines += [
                    f"### `{signal}`",
                    "",
                    "Not available: the installed fastembed has no cross-encoder, so "
                    "nothing produced this signal (D-070).",
                    "",
                ]
                continue
            scored = results[source_configuration]
            answerable_values = [
                value
                for score in scored
                if score.question_id in answerable_ids
                and (value := score.signal(signal)) is not None
            ]
            abstain_values = [
                value
                for score in scored
                if score.question_id in abstain_ids
                and (value := score.signal(signal)) is not None
            ]
            rows_data = threshold_sweep(answerable_values, abstain_values)
            widest = suggest_threshold(rows_data)
            safest = safest_threshold(rows_data)
            signal_analysis[signal] = {
                "configuration": source_configuration,
                "percentiles": {
                    "answerable": signal_percentiles(answerable_values),
                    "should_abstain": signal_percentiles(abstain_values),
                },
                "sweep": [asdict(row) | {"margin": row.margin} for row in rows_data],
                "widest_margin": asdict(widest) if widest else None,
                "provisional": asdict(safest) if safest else None,
            }
            lines += [
                f"### `{signal}`" + (
                    f" — from `{source_configuration}`"
                    if source_configuration != "hybrid+location"
                    else ""
                ),
                "",
                markdown_table(
                    ("group", "n", "p5", "p25", "p50", "p75", "p95"),
                    [
                        [name, str(len(values))]
                        + [
                            "-" if value is None else f"{value:.4f}"
                            for value in signal_percentiles(values).values()
                        ]
                        for name, values in (
                            ("answerable", answerable_values),
                            ("should abstain", abstain_values),
                        )
                    ],
                ),
                "",
            ]
            if not answerable_values or not abstain_values:
                lines += ["No values for one of the two groups, so no sweep.", ""]
                continue
            lines += [
                markdown_table(
                    ("threshold", "caught", "lost", "margin"),
                    [
                        [
                            f"{row.threshold:.4f}",
                            f"{row.caught:.0%}",
                            f"{row.lost:.0%}",
                            f"{row.margin:+.2f}",
                        ]
                        for row in rows_data
                    ],
                ),
                "",
            ]
            if safest is not None:
                lines += [
                    f"**Provisional threshold {safest.threshold:.4f}** — the highest "
                    f"value that refuses none of the answerable questions. It catches "
                    f"{safest.caught:.0%} of the should-abstain ones.",
                    "",
                ]
            if widest is not None:
                lines += [
                    f"**Widest margin at {widest.threshold:.4f}** — catches "
                    f"{widest.caught:.0%}, wrongly refuses {widest.lost:.0%}.",
                    "",
                ]
        lines += [
            f"`settings.abstain_signal` is `{settings.abstain_signal}` and "
            f"`settings.abstain_threshold` is {settings.abstain_threshold}, which is "
            "**provisional** (D-071). The two signals are on different scales, so the "
            "threshold has to be reset whenever the signal changes.",
            "",
        ]
        if dry_run:
            lines += [
                "Only the provisional value above may be adopted from this run. The "
                "widest-margin values are fitted to questions Claude wrote and are not "
                "measurements (D-054).",
                "",
            ]

    # per-question detail, so a bad score can be traced to a question
    lines += ["## Every question, under hybrid+location", "", ]
    detail_rows = []
    for item in questions:
        score = next(s for s in results["hybrid+location"] if s.question_id == item["id"])
        detail_rows.append(
            [
                item["id"],
                item["category"],
                item["point_name"] or "-",
                str(score.first_hit_rank) if score.first_hit_rank else ("n/a" if item["should_abstain"] else "MISS"),
                f"{score.top_score:.4f}",
                item["question"][:58] + ("..." if len(item["question"]) > 58 else ""),
            ]
        )
    lines += [
        markdown_table(
            ("id", "category", "point", "rank of first hit", "top score", "question"),
            detail_rows,
        ),
        "",
    ]

    record = {
        "generated_at": generated_at,
        "dry_run": dry_run,
        "source": source.relative_to(settings.project_root).as_posix(),
        "questions_used": len(questions),
        "questions_skipped_unverified": skipped,
        "counts_per_category": {
            category: len(items) for category, items in sorted(by_category.items())
        },
        "answerable": len(answerable),
        "answerable_with_coordinates": len(with_point),
        "configurations": {
            configuration: {
                "overall": summarise(
                    [s for s in results[configuration] if s.question_id in answerable_ids]
                ),
                "per_category": {
                    category: summarise(
                        [
                            s
                            for s in results[configuration]
                            if s.question_id
                            in {i["id"] for i in by_category[category] if not i["should_abstain"]}
                        ]
                    )
                    for category in sorted(by_category)
                    if category != "abstain"
                },
            }
            for configuration in CONFIGURATIONS
        },
        "location_vs_hybrid": comparison,
        "reranker_available": reranker_available(),
        "abstention_by_signal": signal_analysis,
        "configured_abstain_signal": settings.abstain_signal,
        "configured_abstain_threshold": settings.abstain_threshold,
        "per_question": {
            configuration: [
                {
                    "id": score.question_id,
                    "category": score.category,
                    "first_hit_rank": score.first_hit_rank,
                    "top_score": score.top_score,
                    "top_dense_cosine": score.top_dense_cosine,
                    "top_rerank_score": score.top_rerank_score,
                    "retrieved": score.retrieved,
                }
                for score in results[configuration]
            ]
            for configuration in CONFIGURATIONS
        },
    }
    return "\n".join(lines).rstrip() + "\n", record


def main(argv: list[str] | None = None) -> int:
    """Run every configuration over every question and write the results."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Evaluate ZoneWise retrieval.")
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="also use questions with verified=false; the report is labelled a dry run",
    )
    parser.add_argument(
        "--label",
        default="",
        help="a short name put in the output file name, e.g. night3",
    )
    args = parser.parse_args(argv)

    questions, source, skipped = load_questions(args.include_unverified)
    if not questions:
        print(f"No questions to run from {source.as_posix()}.")
        if not args.include_unverified:
            print()
            print("Nothing in the file is marked verified=true yet. Either verify some")
            print("questions (see eval/README.md) or, for a dry run that proves the")
            print("harness works, use:")
            print("  uv run python eval/run_eval.py --include-unverified")
        return 1

    dry_run = any(not item.get("verified") for item in questions)
    index = get_index()
    print(f"{len(questions)} question(s) from {source.name}, {len(index)} chunks indexed")
    if dry_run:
        print("DRY RUN: unverified questions are included, so the numbers are not results.")
    print()

    results: dict[str, list[QuestionScore]] = {}
    for configuration in CONFIGURATIONS:
        results[configuration] = score_questions(questions, configuration, index)
        answerable = [
            score
            for score, item in zip(results[configuration], questions)
            if not item["should_abstain"]
        ]
        print(
            f"  {configuration:<16} recall@1 {recall(answerable, 1):.3f}  "
            f"recall@3 {recall(answerable, 3):.3f}  "
            f"recall@5 {recall(answerable, 5):.3f}  MRR {mrr(answerable):.3f}"
        )

    generated_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report, record = build_report(results, questions, source, skipped, dry_run, generated_at)

    out_dir = settings.project_root / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "DRYRUN_" if dry_run else ""
    label = f"{args.label}_" if args.label else ""
    report_path = out_dir / f"{prefix}{label}{stamp}.md"
    json_path = out_dir / f"{prefix}{label}{stamp}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print()
    if dry_run:
        print("DRY RUN - UNVERIFIED QUESTIONS - NOT FOR RESUME OR REPORTING")
    for path in (report_path, json_path):
        print(f"wrote {path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
