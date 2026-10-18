"""Run the eight Day 2 test queries in all three modes and write reports/day2_queries.md.

Reads  the indexes in data/index/
Writes reports/<--out>.md, default reports/day2_queries.md

The file is for reading by hand. Nothing here judges a result: the point is to see what
dense search finds that keyword search misses, and the other way round, before any of
it is tuned.

A fourth mode, `hybrid+rerank`, is included when the installed fastembed has a
cross-encoder (D-070). It is the only mode that reads the query and the chunk together
rather than comparing two separately computed representations, so it is the one worth
reading when hybrid puts something plausible-but-wrong first.

Safe to re-run. Run with: uv run python scripts/day2_queries.py
"""

import argparse
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import date

from app.config import settings
from app.extract import use_utf8_output
from app.rerank import available as reranker_available
from app.retrieval import MODES, get_index, rank

#: The name of the fourth mode, which is hybrid with the cross-encoder on top.
RERANK_MODE = "hybrid+rerank"


def modes() -> tuple[str, ...]:
    """The modes this run can report: the three always, plus rerank when available."""
    return MODES + (RERANK_MODE,) if reranker_available() else MODES


@contextmanager
def reranker(on: bool):
    """Turn the reranker on or off for the body of the block.

    `Settings` is frozen, so this rebinds the module global `app.retrieval` reads to a
    replaced copy and puts it back afterwards. Same approach as eval/run_eval.py, for
    the same reason: one run has to report several modes (D-072).
    """
    import app.retrieval as retrieval_module

    if on == settings.use_reranker:
        yield
        return
    original = retrieval_module.settings
    retrieval_module.settings = replace(settings, use_reranker=on)
    try:
        yield
    finally:
        retrieval_module.settings = original

K = 5
SNIPPET_CHARS = 150

QUERIES = (
    "What is the minimum plot size for a TOD project?",
    "How wide is the TOD zone around a metro line?",
    "Maximum ground coverage allowed for high density corridor projects",
    "Can a fuel station be built in Zone O?",
    "Minimum plot area for redevelopment of commercial areas",
    "Does MPD-2047 replace MPD-2021?",
    "Where can I find the permissible activities for a use premise?",
    "What is the land pooling policy and which zones does it cover?",
)


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    """The opening of a chunk's text on one line."""
    flat = " ".join(text.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def main() -> int:
    """Run every query in every mode and write the report."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="day2_queries.md",
        help="file name to write inside reports/ (default: day2_queries.md)",
    )
    args = parser.parse_args()

    if not settings.bm25_path.exists():
        print("No index found. Run: uv run python scripts/05_build_index.py")
        return 1

    index = get_index()
    all_modes = modes()
    lines = [
        "# The eight test queries, every retrieval mode",
        "",
        f"Generated {date.today().isoformat()} by `scripts/day2_queries.py`.",
        "",
        f"Eight queries, {len(all_modes)} modes each, top {K}. {len(index)} chunks indexed.",
        "",
        "`dense` is nearest-neighbour search on the embeddings, `bm25` is keyword search, "
        "`hybrid` fuses the two with reciprocal rank fusion (k = 60). The tags after each "
        "result say where each index placed it: `d3` means dense rank 3, `b1` means BM25 "
        "rank 1, and a missing tag means that index did not return the chunk at all. Where "
        "`hybrid` beats both, it is because the two indexes agreed.",
        "",
    ]
    if RERANK_MODE in all_modes:
        lines += [
            f"`{RERANK_MODE}` takes hybrid's top {settings.rerank_pool} and rescores them "
            f"with the cross-encoder `{settings.rerank_model}`. It is the only mode here "
            "that reads the query and the chunk **together**, so `rr` is its own rank and "
            "`rerank` is its score — an absolute judgement about this query and this "
            "chunk, unlike a fused score, which only encodes position (D-070, D-071). It "
            "is off in normal operation, because it costs 2.4 s a query against 0.031 s.",
            "",
        ]
    lines += [
        "None of this is judged here. Read it and mark which results answer the question.",
        "",
    ]

    for number, query in enumerate(QUERIES, start=1):
        print(f"{number}. {query}")
        lines += [f"## {number}. {query}", ""]
        for mode in all_modes:
            with reranker(mode == RERANK_MODE):
                search_mode = "hybrid" if mode == RERANK_MODE else mode
                results = rank(query, k=K, mode=search_mode, index=index)
            lines += [f"### {mode}", ""]
            if not results:
                lines += ["(nothing found)", ""]
                continue
            for position, result in enumerate(results, start=1):
                marks = []
                if result.dense_rank:
                    marks.append(f"d{result.dense_rank}")
                if result.bm25_rank:
                    marks.append(f"b{result.bm25_rank}")
                if result.rerank_rank:
                    marks.append(f"rr{result.rerank_rank}")
                if result.rerank_score is not None:
                    marks.append(f"rerank {result.rerank_score:+.2f}")
                lines.append(
                    f"{position}. `{result.chunk_id}` — clause "
                    f"{result.clause_id or '(none)'}, pages "
                    f"{result.page_start}-{result.page_end}, "
                    f"[{' '.join(marks)} score {result.fused_score:.4f}]"
                    + (f", zone_primary {result.zone_primary}" if result.zone_primary else "")
                )
                lines.append(f"   - path: {result.path or '(none)'}")
                lines.append(f"   - {snippet(result.text)}")
            lines.append("")

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.reports_dir / args.out
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print()
    print(f"{len(QUERIES)} queries x {len(all_modes)} modes x top {K}.")
    print(f"wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
