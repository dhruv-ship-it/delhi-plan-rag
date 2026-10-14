"""Compare plain hybrid search against location-aware search at the test points.

Reads  data/test_points.json, the indexes in data/index/, the layers in data/layers/dda/
Writes reports/day3_location_compare.md

Four comparisons, each the same question asked at different points, so the only thing
that changes between the two columns is where the user is standing.

The file is for reading by hand. Nothing here judges a result.

Safe to re-run. Run with: uv run python scripts/day3_location_compare.py
"""

import json
import sys
from datetime import date

from app.config import settings
from app.extract import use_utf8_output
from app.location import describe_zones
from app.retrieval import SearchReport, get_index, rank, search

K = 5
SNIPPET_CHARS = 120

#: (label, question, the test points to ask it at).
COMPARISONS = (
    ("A", "What is the maximum ground coverage allowed on my plot?", ("P_TOD", "P_HDC", "P_PLAIN")),
    ("B", "Can I construct a building here?", ("P_ZONEO",)),
    ("C", "What development rules apply to my land here?", ("P_LP",)),
    ("D", "What FAR can I get here?", ("P_TOD", "P_PLAIN")),
)


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    """The opening of a chunk's text on one line."""
    flat = " ".join(text.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def result_rows(results) -> list[str]:
    """A numbered list of results, one entry per result."""
    if not results:
        return ["(nothing found)", ""]
    lines = []
    for position, result in enumerate(results, start=1):
        marks = []
        if result.dense_rank:
            marks.append(f"d{result.dense_rank}")
        if result.bm25_rank:
            marks.append(f"b{result.bm25_rank}")
        if result.boosted:
            marks.append("**boosted**")
        lines.append(
            f"{position}. `{result.chunk_id}` — clause {result.clause_id or '(none)'}, "
            f"zone_primary `{result.zone_primary or '(none)'}`, pages "
            f"{result.page_start}-{result.page_end}, [{' '.join(marks)} "
            f"score {result.fused_score:.4f}]"
        )
        lines.append(f"   - {snippet(result.text)}")
    lines.append("")
    return lines


def main() -> int:
    """Run the four comparisons and write the report."""
    use_utf8_output()
    points_path = settings.project_root / "data" / "test_points.json"
    if not points_path.exists():
        print(f"{points_path.as_posix()} is missing. Run: uv run python scripts/07_test_points.py")
        return 1
    if not settings.bm25_path.exists():
        print("No index found. Run: uv run python scripts/05_build_index.py")
        return 1

    points = {record["name"]: record for record in json.loads(points_path.read_text(encoding="utf-8"))}
    index = get_index()

    lines = [
        "# Day 3: plain hybrid against location-aware search",
        "",
        f"Generated {date.today().isoformat()} by `scripts/day3_location_compare.py`.",
        "",
        f"Top {K} either way, {len(index)} chunks indexed. The question is identical in both "
        "columns; the only difference is that the right-hand one knows where the user is "
        "standing.",
        "",
        "Location-aware search does three things, with the settings in `app/config.py`:",
        "",
        f"1. **Exclusion** — a chunk whose `zone_primary` is a policy the point is *not* in "
        "is dropped. A chunk with no primary zone is never dropped, so the general norms in "
        "chapters 7 to 13 always stay in play.",
        f"2. **Query expansion** — the point's zone names are appended to the query text for "
        "both indexes, so a question with no zone words in it can still reach the right policy.",
        f"3. **Boost** — a chunk whose `zone_primary` *or* `zone_mentions` matches the point's "
        f"zones has its fused score multiplied by {settings.zone_boost}.",
        "",
        "`d3` is dense rank 3, `b1` is BM25 rank 1, **boosted** marks a chunk the boost "
        "applied to. Not judged here.",
        "",
    ]

    for label, question, names in COMPARISONS:
        lines += [f"## {label}. “{question}”", ""]
        for name in names:
            record = points.get(name)
            if record is None:
                lines += [f"### {name} — missing from data/test_points.json", ""]
                continue
            zones = record["zones"]
            print(f"{label} at {name}: {question}")
            lines += [
                f"### {label} at {name} — {record['lat']}, {record['lon']}",
                "",
                f"- {describe_zones(zones)}",
                f"- `get_zones`: `{json.dumps(zones)}`",
                "",
            ]
            plain = rank(question, k=K, mode="hybrid", index=index)
            report = SearchReport(query=question, expanded_query=question)
            aware = search(
                question, k=K, mode="hybrid", zones=zones, index=index, report=report
            )
            lines += ["**plain hybrid**", ""] + result_rows(plain)
            lines += [
                "**location-aware hybrid**",
                "",
                f"- query sent: “{report.expanded_query}”",
                f"- expansion terms added: {', '.join(report.expansion_terms) or '(none)'}",
                f"- excluded {report.excluded} chunk(s) whose primary zone is one of: "
                f"{', '.join(report.excluded_topics) or '(none)'}",
                f"- boosted {report.boosted} chunk(s) in the pool",
                "",
            ] + result_rows(aware)

            plain_ids = [result.chunk_id for result in plain]
            aware_ids = [result.chunk_id for result in aware]
            moved = [chunk_id for chunk_id in aware_ids if chunk_id not in plain_ids]
            gone = [chunk_id for chunk_id in plain_ids if chunk_id not in aware_ids]
            lines += [
                f"- new in the top {K}: "
                + (", ".join(f"`{chunk_id}`" for chunk_id in moved) or "(none)"),
                f"- dropped out of the top {K}: "
                + (", ".join(f"`{chunk_id}`" for chunk_id in gone) or "(none)"),
                "",
            ]

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.reports_dir / "day3_location_compare.md"
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    asked = sum(len(names) for _, _, names in COMPARISONS)
    print()
    print(f"{len(COMPARISONS)} comparisons at {asked} point(s), top {K} each way.")
    print(f"wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
