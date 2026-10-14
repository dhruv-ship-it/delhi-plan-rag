"""Run the eight Day 2 test queries in all three modes and write reports/day2_queries.md.

Reads  the indexes in data/index/
Writes reports/day2_queries.md

The file is for reading by hand. Nothing here judges a result: the point is to see what
dense search finds that keyword search misses, and the other way round, before any of
it is tuned.

Safe to re-run. Run with: uv run python scripts/day2_queries.py
"""

import sys
from datetime import date

from app.config import settings
from app.extract import use_utf8_output
from app.retrieval import MODES, get_index, rank

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
    if not settings.bm25_path.exists():
        print("No index found. Run: uv run python scripts/05_build_index.py")
        return 1

    index = get_index()
    lines = [
        "# Day 2 test queries",
        "",
        f"Generated {date.today().isoformat()} by `scripts/day2_queries.py`.",
        "",
        f"Eight queries, three modes each, top {K}. {len(index)} chunks indexed.",
        "",
        "`dense` is nearest-neighbour search on the embeddings, `bm25` is keyword search, "
        "`hybrid` fuses the two with reciprocal rank fusion (k = 60). The tags after each "
        "result say where each index placed it: `d3` means dense rank 3, `b1` means BM25 "
        "rank 1, and a missing tag means that index did not return the chunk at all. Where "
        "`hybrid` beats both, it is because the two indexes agreed.",
        "",
        "These are not judged here. Read them and mark which ones answer the question.",
        "",
    ]

    for number, query in enumerate(QUERIES, start=1):
        print(f"{number}. {query}")
        lines += [f"## {number}. {query}", ""]
        for mode in MODES:
            results = rank(query, k=K, mode=mode, index=index)
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
    out_path = settings.reports_dir / "day2_queries.md"
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print()
    print(f"{len(QUERIES)} queries x {len(MODES)} modes x top {K}.")
    print(f"wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
