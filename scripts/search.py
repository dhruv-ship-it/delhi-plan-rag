"""Search the indexes from the command line and print the modes side by side.

    uv run python scripts/search.py "minimum plot size for a TOD project"
    uv run python scripts/search.py "what FAR can I get here" --k 5 --mode hybrid
    uv run python scripts/search.py "can I build here" --lat 28.6328 --lon 77.2197

With --mode all (the default) the three modes are printed next to each other, so it is
easy to see which index found what. With --lat/--lon the point's zones are looked up
and plain hybrid is printed against location-aware hybrid.

Nothing here judges the results; that is for a person reading them.
"""

import argparse
import sys

from app.config import settings
from app.extract import use_utf8_output
from app.retrieval import MODES, Result, SearchReport, get_index, rank

#: How much of a result's text the one-line view shows.
SNIPPET_CHARS = 150


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    """The opening of a chunk's text on one line."""
    flat = " ".join(text.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def result_lines(results: list[Result], snippet_chars: int = SNIPPET_CHARS) -> list[str]:
    """One line per result: rank, chunk id, clause, pages, the opening of the text."""
    if not results:
        return ["  (nothing found)"]
    lines = []
    for position, result in enumerate(results, start=1):
        marks = []
        if result.dense_rank:
            marks.append(f"d{result.dense_rank}")
        if result.bm25_rank:
            marks.append(f"b{result.bm25_rank}")
        if result.boosted:
            marks.append("boost")
        lines.append(
            f"  {position}. {result.chunk_id}  clause {result.clause_id or '-'}  "
            f"pages {result.page_start}-{result.page_end}  "
            f"[{' '.join(marks)} score {result.fused_score:.4f}]"
        )
        lines.append(f"     {snippet(result.text, snippet_chars)}")
    return lines


def print_modes(query: str, k: int, modes: tuple[str, ...]) -> None:
    """Run the query in each mode and print the results under each other."""
    index = get_index()
    print(f'query: "{query}"   k={k}   {len(index)} chunks indexed')
    for mode in modes:
        results = rank(query, k=k, mode=mode, index=index)
        print()
        print(f"--- {mode} ---")
        for line in result_lines(results):
            print(line)


def print_location(query: str, k: int, lat: float, lon: float) -> None:
    """Look up the point's zones, then print plain hybrid against location-aware hybrid."""
    from app.location import describe_zones
    from app.retrieval import search
    from app.spatial import get_zones

    index = get_index()
    zones = get_zones(lat, lon)
    print(f'query: "{query}"   k={k}   point: {lat}, {lon}')
    print(f"zones: {describe_zones(zones)}")

    print()
    print("--- plain hybrid ---")
    for line in result_lines(rank(query, k=k, mode="hybrid", index=index)):
        print(line)

    report = SearchReport(query=query, expanded_query=query)
    aware = search(query, k=k, mode="hybrid", zones=zones, index=index, report=report)
    print()
    print("--- location-aware hybrid ---")
    print(f"  query sent: \"{report.expanded_query}\"")
    print(
        f"  excluded {report.excluded} chunk(s) "
        f"({', '.join(report.excluded_topics) or 'no zone topics to exclude'}), "
        f"boosted {report.boosted}"
    )
    for line in result_lines(aware):
        print(line)


def main(argv: list[str] | None = None) -> int:
    """Parse the arguments and print the results."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Search the ZoneWise indexes.")
    parser.add_argument("query", help="what to search for")
    parser.add_argument("--k", type=int, default=settings.default_k, help="how many results")
    parser.add_argument(
        "--mode",
        default="all",
        choices=("all", *MODES),
        help="which mode to run; all prints the three side by side",
    )
    parser.add_argument("--lat", type=float, help="latitude of the point the question is about")
    parser.add_argument("--lon", type=float, help="longitude of the point the question is about")
    args = parser.parse_args(argv)

    if not settings.bm25_path.exists():
        print("No index found. Run: uv run python scripts/05_build_index.py")
        return 1
    if (args.lat is None) != (args.lon is None):
        print("--lat and --lon go together.")
        return 1

    if args.lat is not None:
        print_location(args.query, args.k, args.lat, args.lon)
    else:
        modes = MODES if args.mode == "all" else (args.mode,)
        print_modes(args.query, args.k, modes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
