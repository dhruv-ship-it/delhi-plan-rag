"""Check that data/sources.csv is sound and that every document we need is on disk.

Safe to re-run. Writes nothing. Exit code 1 when there are problems.
Run with: uv run python scripts/01_check_sources.py
"""

import sys

from app.config import settings
from app.extract import (
    check_row,
    format_table,
    missing_columns,
    read_sources,
    unlisted_raw_pdfs,
)

MEGABYTE = 1024 * 1024


def size_mb(path) -> str:
    """A file's size in megabytes, as text with one decimal place."""
    return f"{path.stat().st_size / MEGABYTE:.1f}"


def main() -> int:
    """Check the CSV, print one line per document, then print OK or the problems."""
    print("ZoneWise sources check")
    print("-" * 22)

    if not settings.sources_csv.exists():
        print("data/sources.csv is missing.")
        return 1

    rows = read_sources(settings.sources_csv)
    if not rows:
        print("data/sources.csv has no document rows.")
        return 1

    problems: list[str] = []
    absent = missing_columns(rows)
    if absent:
        problems.append(f"sources.csv is missing columns: {', '.join(absent)}")

    table_rows: list[list[str]] = []
    seen: set[str] = set()
    for row in rows:
        path, row_problems = check_row(row, seen, settings.raw_dir, settings.reference_dir)
        problems.extend(row_problems)
        doc_id = row.get("doc_id", "(no doc_id)")
        seen.add(doc_id)

        include = row.get("include", "")
        if include == "no":
            found, size = "not needed", "-"
        elif path is None:
            found, size = "MISSING", "-"
        else:
            # Show the real file name when it differs from the <doc_id>.pdf convention.
            expected = f"{doc_id}.pdf"
            found = "yes" if path.name == expected else f"yes ({path.name})"
            size = size_mb(path)

        pages = row.get("page_start", "") or "1"
        pages = f"{pages}-{row.get('page_end', '') or 'end'}"
        table_rows.append([doc_id, include, found, size, pages])

    print(format_table(["doc_id", "include", "file found", "size (MB)", "pages"], table_rows))
    print()

    warnings = [
        f"data/raw/{name} is not listed in sources.csv" for name in unlisted_raw_pdfs(rows, settings.raw_dir)
    ]
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    print(f"{len(rows)} rows, {sum(1 for row in rows if row.get('include') == 'yes')} to index.")
    print("-" * 22)
    if problems:
        print(f"{len(problems)} problem(s) found:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK" if not warnings else f"OK ({len(warnings)} warning(s) above)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
