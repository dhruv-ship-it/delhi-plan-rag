"""Measure how well retrieval finds the right clause, across four configurations.

Reads  eval/questions.jsonl if it exists, else eval/questions_draft.jsonl
       eval/points.json
Writes eval/results/<timestamp>.md and .json
       eval/results/DRYRUN_<timestamp>.md for an unverified run

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
from dataclasses import asdict
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
    suggest_threshold,
    threshold_sweep,
)

from app.config import settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402
from app.retrieval import get_index, rank, search  # noqa: E402

CONFIGURATIONS = ("dense", "bm25", "hybrid", "hybrid+location")
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


def retrieve(question: dict, configuration: str, index) -> tuple[list[str], float]:
    """Run one question through one configuration. Returns (chunk ids, best score)."""
    text = question["question"]
    has_point = question.get("lat") is not None and question.get("lon") is not None

    if configuration == "hybrid+location" and has_point:
        from app.spatial import get_zones

        zones = get_zones(question["lat"], question["lon"])
        results = search(text, k=TOP_K, mode="hybrid", zones=zones, index=index)
    else:
        mode = "hybrid" if configuration == "hybrid+location" else configuration
        results = rank(text, k=TOP_K, mode=mode, index=index)

    return (
        [result.chunk_id for result in results],
        results[0].fused_score if results else 0.0,
    )


def score_questions(questions: list[dict], configuration: str, index) -> list[QuestionScore]:
    """Score every question under one configuration."""
    scored: list[QuestionScore] = []
    for question in questions:
        retrieved, top_score = retrieve(question, configuration, index)
        wanted = set(question["expected_chunk_ids"]) | set(question["acceptable_chunk_ids"])
        scored.append(
            QuestionScore(
                question_id=question["id"],
                category=question["category"],
                first_hit_rank=first_hit_rank(retrieved, wanted) if wanted else None,
                top_score=top_score,
                retrieved=retrieved,
            )
        )
    return scored


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

    # the abstention threshold sweep
    abstain_ids = {item["id"] for item in questions if item["should_abstain"]}
    sweep_rows: list[dict] = []
    suggestion = None
    if abstain_ids:
        hybrid = results["hybrid+location"]
        abstain_scores = [s.top_score for s in hybrid if s.question_id in abstain_ids]
        answer_scores = [s.top_score for s in hybrid if s.question_id in answerable_ids]
        rows_data = threshold_sweep(answer_scores, abstain_scores)
        suggestion = suggest_threshold(rows_data)
        sweep_rows = [asdict(row) | {"margin": row.margin} for row in rows_data]
        lines += [
            "## Could the top score alone decide when to refuse?",
            "",
            f"Retrieval only, no LLM call. For each candidate threshold: the share of the "
            f"{len(abstain_ids)} should-abstain questions whose best fused score falls "
            f"below it (caught, higher is better), against the share of the "
            f"{len(answerable_ids)} answerable ones that would be wrongly refused (lost, "
            "lower is better).",
            "",
            markdown_table(
                ("threshold", "caught", "lost", "margin"),
                [
                    [
                        f"{row.threshold:.4f}",
                        f"{row.caught:.2f}",
                        f"{row.lost:.2f}",
                        f"{row.margin:+.2f}",
                    ]
                    for row in rows_data
                ],
            ),
            "",
        ]
        if suggestion is not None:
            lines += [
                f"**Widest margin at {suggestion.threshold:.4f}**: it would catch "
                f"{suggestion.caught:.0%} of the unanswerable questions and wrongly "
                f"refuse {suggestion.lost:.0%} of the answerable ones. "
                f"`settings.abstain_threshold` is currently "
                f"{settings.abstain_threshold} (a placeholder, D-042).",
                "",
            ]
            if dry_run:
                lines += [
                    "This suggestion is from unverified questions, so it is not a reason "
                    "to change the setting yet.",
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
        "threshold_sweep": sweep_rows,
        "suggested_threshold": asdict(suggestion) if suggestion else None,
        "configured_abstain_threshold": settings.abstain_threshold,
        "per_question": {
            configuration: [
                {
                    "id": score.question_id,
                    "category": score.category,
                    "first_hit_rank": score.first_hit_rank,
                    "top_score": score.top_score,
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
    report_path = out_dir / f"{prefix}{stamp}.md"
    json_path = out_dir / f"{prefix}{stamp}.json"
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
