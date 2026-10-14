"""Extract page text from every include=yes PDF and write a quality report.

Reads data/sources.csv, obeys the page_start/page_end range of each row, and writes
data/processed/pages.jsonl and data/processed/extract_report.md. Safe to re-run:
both outputs are overwritten.

Run with: uv run python scripts/02_extract.py
          uv run python scripts/02_extract.py --no-tables   (skip table counting)
"""

import argparse
import sys
from datetime import date

from app.config import settings
from app.extract import (
    SUMMARY_HEADERS,
    build_report,
    extract_document,
    format_table,
    missing_columns,
    parse_page_bound,
    read_sources,
    resolve_pdf_path,
    summarise,
    summary_row,
    use_utf8_output,
    write_pages_jsonl,
)


def parse_args() -> argparse.Namespace:
    """Read the command line options."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="skip page.find_tables(), which is the slow part of extraction",
    )
    return parser.parse_args()


def main() -> int:
    """Extract every document we index, write the outputs, print a summary table."""
    use_utf8_output()
    args = parse_args()
    find_tables = not args.no_tables

    print("ZoneWise page extraction")
    print("-" * 24)

    if not settings.sources_csv.exists():
        print("data/sources.csv is missing. Run scripts/01_check_sources.py first.")
        return 1

    rows = read_sources(settings.sources_csv)
    absent = missing_columns(rows)
    if absent:
        print(f"sources.csv is missing columns: {', '.join(absent)}")
        print("Run scripts/01_check_sources.py first.")
        return 1

    to_index = [row for row in rows if row.get("include") == "yes"]
    if not to_index:
        print("No rows with include=yes, so there is nothing to extract.")
        return 1

    print(f"{len(to_index)} document(s) to extract, tables {'on' if find_tables else 'off'}.")
    print()

    results = []
    missing_files: list[str] = []
    for row in to_index:
        doc_id = row["doc_id"]
        path = resolve_pdf_path(settings.raw_dir, doc_id)
        if path is None:
            print(f"{doc_id}: data/raw/{doc_id}.pdf is missing, skipping")
            missing_files.append(doc_id)
            continue
        try:
            page_start = parse_page_bound(row.get("page_start", ""), "page_start")
            page_end = parse_page_bound(row.get("page_end", ""), "page_end")
        except ValueError as exc:
            print(f"{doc_id}: {exc}, skipping")
            missing_files.append(doc_id)
            continue

        print(f"{doc_id}: reading {path.name} ...", end="", flush=True)
        result = extract_document(path, doc_id, page_start, page_end, find_tables)
        results.append(result)
        print(f" {len(result.pages)} page(s), {len(result.errors)} error(s)")

    print()
    summaries = [summarise(result) for result in results]
    print(
        format_table(
            SUMMARY_HEADERS, [summary_row(summary, find_tables) for summary in summaries]
        )
    )
    print()

    pages_path = settings.processed_dir / "pages.jsonl"
    report_path = settings.processed_dir / "extract_report.md"
    written = write_pages_jsonl(results, pages_path)
    report = build_report(results, date.today().isoformat(), find_tables)
    report_path.write_text(report, encoding="utf-8")

    errors = sum(len(result.errors) for result in results)
    print(f"Wrote {written} page record(s) to {pages_path.as_posix()}")
    print(f"Wrote the report to {report_path.as_posix()}")
    print("-" * 24)
    print(
        f"{len(results)} document(s), {written} pages, "
        f"{sum(summary.words for summary in summaries):,} words, "
        f"{sum(summary.skipped_pages for summary in summaries)} pages skipped, "
        f"{sum(summary.likely_scanned for summary in summaries)} pages that look scanned, "
        f"{errors} error(s)."
    )
    if missing_files:
        print(f"Skipped {len(missing_files)} document(s) with no readable file: "
              f"{', '.join(missing_files)}")
    return 1 if missing_files else 0


if __name__ == "__main__":
    sys.exit(main())
