"""Read data/sources.csv and turn the source PDFs into one text record per page.

Two jobs live here so both pipeline scripts can share them:
  * reading and checking sources.csv (used by scripts/01_check_sources.py)
  * extracting page text and quality flags with PyMuPDF (used by scripts/02_extract.py)

Nothing here cleans the text. Pages are stored exactly as PyMuPDF reads them;
headers, footers and page numbers are only reported, never removed.
"""

import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import pymupdf

# --- sources.csv rules ---------------------------------------------------------

REQUIRED_COLUMNS = (
    "doc_id",
    "title",
    "doc_type",
    "issuer",
    "doc_date",
    "url",
    "downloaded_on",
    "language",
    "text_or_scanned",
    "authority_rank",
    "include",
    "notes",
    "page_start",
    "page_end",
)
VALID_INCLUDE = ("yes", "no", "reference")
VALID_AUTHORITY_RANKS = ("1", "2", "3")
DOC_ID_PATTERN = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")

# --- page quality rules --------------------------------------------------------

DEVANAGARI_FIRST = "ऀ"
DEVANAGARI_LAST = "ॿ"
#: A page with fewer characters than this plus at least one image looks scanned.
SCANNED_CHARS_WITH_IMAGE = 50
#: A page with fewer characters than this looks scanned (or simply empty).
SCANNED_CHARS_ANY = 20
#: Above this share of Devanagari characters we call a page mostly Hindi.
HINDI_PAGE_RATIO = 0.3
#: How many lines at the top and at the bottom of a page count as header/footer.
EDGE_LINE_COUNT = 2
#: A header/footer line must appear on more than this share of a document's pages.
REPEATED_LINE_SHARE = 0.4
#: How many repeated lines to list per document in the report.
REPEATED_LINE_LIMIT = 5


@dataclass(frozen=True)
class PageRecord:
    """One page of one document, as stored in data/processed/pages.jsonl."""

    doc_id: str
    page: int  # 1-based, the page number printed by a PDF reader
    text: str
    n_chars: int
    n_words: int
    n_images: int
    n_tables: int | None  # None when table finding was skipped or failed
    devanagari_ratio: float
    likely_scanned: bool


@dataclass
class DocResult:
    """Everything one document produced: its pages, what was skipped, what went wrong."""

    doc_id: str
    pdf_path: Path
    pages: list[PageRecord] = field(default_factory=list)
    pdf_page_count: int = 0
    page_start: int | None = None
    page_end: int | None = None
    skipped_pages: int = 0
    repeated_lines: list[tuple[str, int]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocSummary:
    """The counts shown for one document in the printed table and in the report."""

    doc_id: str
    pages: int
    words: int
    empty_pages: int
    likely_scanned: int
    hindi_pages: int
    tables: int
    errors: int
    skipped_pages: int


# --- reading and checking sources.csv ------------------------------------------


def read_sources(path: Path) -> list[dict[str, str]]:
    """Read sources.csv into a list of rows, with every value stripped of spaces."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def missing_columns(rows: Sequence[dict[str, str]]) -> list[str]:
    """Names of the required sources.csv columns that are not present."""
    present = set(rows[0]) if rows else set()
    return [column for column in REQUIRED_COLUMNS if column not in present]


def parse_page_bound(value: str, column: str) -> int | None:
    """Turn a page_start/page_end cell into a 1-based page number. Blank means None."""
    if not value:
        return None
    if not value.isdigit() or int(value) < 1:
        raise ValueError(f"{column} must be a page number of 1 or more, found {value!r}")
    return int(value)


def resolve_pdf_path(folder: Path, doc_id: str) -> Path | None:
    """Find <doc_id>.pdf in a folder, accepting .PDF as well. None when absent.

    The folder is listed rather than probed, so the path carries the file's real
    spelling. Windows would accept the wrong case silently; Linux would not.
    """
    if not folder.is_dir():
        return None
    wanted = f"{doc_id}.pdf".lower()
    for candidate in sorted(folder.iterdir()):
        if candidate.name.lower() == wanted:
            return candidate
    return None


def expected_folder(row: dict[str, str], raw_dir: Path, reference_dir: Path) -> Path | None:
    """Which folder a row's PDF belongs in. None for rows we do not use (include=no)."""
    if row.get("include") == "yes":
        return raw_dir
    if row.get("include") == "reference":
        return reference_dir
    return None


def pdf_page_count(path: Path) -> int:
    """How many pages a PDF has. Raises if the file cannot be opened."""
    with pymupdf.open(path) as doc:
        return doc.page_count


def check_row(
    row: dict[str, str],
    seen_doc_ids: set[str],
    raw_dir: Path,
    reference_dir: Path,
) -> tuple[Path | None, list[str]]:
    """Check one sources.csv row. Returns its PDF path (if any) and its problems."""
    problems: list[str] = []
    doc_id = row.get("doc_id", "")

    if not doc_id:
        problems.append("a row has an empty doc_id")
        return None, problems
    if doc_id in seen_doc_ids:
        problems.append(f"{doc_id}: doc_id appears more than once")
    if not DOC_ID_PATTERN.match(doc_id):
        problems.append(f"{doc_id}: doc_id is not UPPER_SNAKE_CASE")

    include = row.get("include", "")
    if include not in VALID_INCLUDE:
        problems.append(
            f"{doc_id}: include is {include!r}, expected one of {', '.join(VALID_INCLUDE)}"
        )
    rank = row.get("authority_rank", "")
    if rank not in VALID_AUTHORITY_RANKS:
        problems.append(f"{doc_id}: authority_rank is {rank!r}, expected 1, 2 or 3")

    folder = expected_folder(row, raw_dir, reference_dir)
    path = resolve_pdf_path(folder, doc_id) if folder is not None else None
    if folder is not None and path is None:
        relative = folder.name
        problems.append(f"{doc_id}: include={include} but data/{relative}/{doc_id}.pdf is missing")

    bounds: list[int | None] = []
    for column in ("page_start", "page_end"):
        try:
            bounds.append(parse_page_bound(row.get(column, ""), column))
        except ValueError as exc:
            problems.append(f"{doc_id}: {exc}")
            bounds.append(None)
    start, end = bounds
    if start is not None and end is not None and start > end:
        problems.append(f"{doc_id}: page_start {start} is after page_end {end}")

    if path is not None and (start is not None or end is not None):
        try:
            total = pdf_page_count(path)
        except Exception as exc:  # a broken PDF is reported by the extract step too
            problems.append(f"{doc_id}: cannot read the PDF to check its page range ({exc})")
        else:
            if start is not None and start > total:
                problems.append(f"{doc_id}: page_start {start} is past the last page ({total})")
            if end is not None and end > total:
                problems.append(f"{doc_id}: page_end {end} is past the last page ({total})")

    return path, problems


def unlisted_raw_pdfs(rows: Sequence[dict[str, str]], raw_dir: Path) -> list[str]:
    """PDF file names sitting in data/raw that no sources.csv row claims."""
    if not raw_dir.is_dir():
        return []
    listed = {f"{row.get('doc_id', '')}.pdf".lower() for row in rows}
    return [
        path.name
        for path in sorted(raw_dir.iterdir())
        if path.suffix.lower() == ".pdf" and path.name.lower() not in listed
    ]


# --- extracting pages ----------------------------------------------------------


def devanagari_ratio(text: str) -> float:
    """Share of the page's non-space characters that are Devanagari (the Hindi script)."""
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return 0.0
    hindi = sum(1 for char in visible if DEVANAGARI_FIRST <= char <= DEVANAGARI_LAST)
    return round(hindi / len(visible), 4)


def looks_scanned(n_chars: int, n_images: int) -> bool:
    """True when a page carries an image but almost no text, or no real text at all."""
    if n_chars < SCANNED_CHARS_WITH_IMAGE and n_images >= 1:
        return True
    return n_chars < SCANNED_CHARS_ANY


def select_pages(
    pdf_page_total: int, page_start: int | None = None, page_end: int | None = None
) -> range:
    """The 1-based page numbers to extract. Blank bounds mean first page / last page."""
    first = 1 if page_start is None else max(1, page_start)
    last = pdf_page_total if page_end is None else min(pdf_page_total, page_end)
    if first > last:
        return range(0)
    return range(first, last + 1)


def edge_lines(text: str, count: int = EDGE_LINE_COUNT) -> set[str]:
    """The first and last few non-empty lines of a page, where headers and footers sit."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return set()
    return set(lines[:count] + lines[-count:])


def find_repeated_lines(
    page_edges: Sequence[set[str]],
    share: float = REPEATED_LINE_SHARE,
    limit: int = REPEATED_LINE_LIMIT,
) -> list[tuple[str, int]]:
    """Lines at the top or bottom of more than `share` of a document's pages."""
    if not page_edges:
        return []
    counts = Counter(line for lines in page_edges for line in lines)
    threshold = share * len(page_edges)
    repeated = [(line, count) for line, count in counts.items() if count > threshold]
    repeated.sort(key=lambda pair: (-pair[1], pair[0]))
    return repeated[:limit]


def count_tables(page: pymupdf.Page) -> tuple[int | None, str | None]:
    """Count the tables PyMuPDF can see on a page. Returns (count, error message)."""
    try:
        return len(page.find_tables().tables), None
    except Exception as exc:  # table finding is best-effort and must never stop a run
        return None, f"find_tables failed: {exc}"


def extract_page(
    doc_id: str, page_number: int, page: pymupdf.Page, find_tables: bool = True
) -> tuple[PageRecord, list[str]]:
    """Build one PageRecord from an open PyMuPDF page. Returns the record and any errors."""
    text = page.get_text("text", sort=True)
    stripped = text.strip()
    n_images = len(page.get_images(full=True))

    errors: list[str] = []
    n_tables: int | None = None
    if find_tables:
        n_tables, error = count_tables(page)
        if error:
            errors.append(f"page {page_number}: {error}")

    record = PageRecord(
        doc_id=doc_id,
        page=page_number,
        text=text,
        n_chars=len(stripped),
        n_words=len(stripped.split()),
        n_images=n_images,
        n_tables=n_tables,
        devanagari_ratio=devanagari_ratio(text),
        likely_scanned=looks_scanned(len(stripped), n_images),
    )
    return record, errors


def extract_document(
    pdf_path: Path,
    doc_id: str,
    page_start: int | None = None,
    page_end: int | None = None,
    find_tables: bool = True,
) -> DocResult:
    """Extract one PDF into page records. Problems are collected, never raised."""
    result = DocResult(
        doc_id=doc_id, pdf_path=pdf_path, page_start=page_start, page_end=page_end
    )

    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        result.errors.append(f"cannot open the PDF: {exc}")
        return result

    with doc:
        result.pdf_page_count = doc.page_count
        if doc.needs_pass:
            result.errors.append("the PDF is encrypted and needs a password")
            result.skipped_pages = doc.page_count
            return result

        wanted = select_pages(doc.page_count, page_start, page_end)
        result.skipped_pages = doc.page_count - len(wanted)
        if not wanted:
            result.errors.append(
                f"page range {page_start}-{page_end} selects no pages "
                f"of the {doc.page_count} in the PDF"
            )
            return result

        page_edges: list[set[str]] = []
        for page_number in wanted:
            try:
                page = doc.load_page(page_number - 1)
                record, errors = extract_page(doc_id, page_number, page, find_tables)
            except Exception as exc:
                result.errors.append(f"page {page_number}: {exc}")
                continue
            result.pages.append(record)
            result.errors.extend(errors)
            page_edges.append(edge_lines(record.text))

    result.repeated_lines = find_repeated_lines(page_edges)
    return result


def summarise(result: DocResult) -> DocSummary:
    """Count up one document's pages for the summary table."""
    pages = result.pages
    return DocSummary(
        doc_id=result.doc_id,
        pages=len(pages),
        words=sum(page.n_words for page in pages),
        empty_pages=sum(1 for page in pages if page.n_chars == 0),
        likely_scanned=sum(1 for page in pages if page.likely_scanned),
        hindi_pages=sum(1 for page in pages if page.devanagari_ratio > HINDI_PAGE_RATIO),
        tables=sum(page.n_tables or 0 for page in pages),
        errors=len(result.errors),
        skipped_pages=result.skipped_pages,
    )


# --- writing the outputs -------------------------------------------------------


def write_pages_jsonl(results: Sequence[DocResult], path: Path) -> int:
    """Write every page of every document as one JSON object per line. Returns the count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for result in results:
            for page in result.pages:
                handle.write(json.dumps(asdict(page), ensure_ascii=False) + "\n")
                written += 1
    return written


def read_pages_jsonl(path: Path) -> list[dict]:
    """Read pages.jsonl back into a list of dictionaries."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


SUMMARY_HEADERS = (
    "doc_id",
    "pages",
    "words",
    "empty",
    "scanned?",
    "hindi",
    "tables",
    "errors",
    "skipped",
)


def summary_row(summary: DocSummary, tables_measured: bool = True) -> list[str]:
    """One summary line as plain strings, ready for a table."""
    return [
        summary.doc_id,
        str(summary.pages),
        f"{summary.words:,}",
        str(summary.empty_pages),
        str(summary.likely_scanned),
        str(summary.hindi_pages),
        str(summary.tables) if tables_measured else "-",
        str(summary.errors),
        str(summary.skipped_pages),
    ]


def use_utf8_output() -> None:
    """Let the terminal print Hindi and typographic characters instead of crashing.

    Windows consoles default to cp1252, which cannot encode Devanagari. Any script
    that prints page text calls this first.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def format_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Lay out rows as a plain text table for the terminal."""
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = [" | ".join(header.ljust(widths[i]) for i, header in enumerate(headers))]
    lines.append("-+-".join("-" * width for width in widths))
    for row in rows:
        lines.append(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Lay out rows as a Markdown table for the report."""
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def describe_range(result: DocResult) -> str:
    """Plain English for the page range a document was read with."""
    if result.page_start is None and result.page_end is None:
        return "all pages"
    start = result.page_start or 1
    end = result.page_end or result.pdf_page_count
    return f"pages {start}-{end}"


def build_report(
    results: Sequence[DocResult], generated_on: str, tables_measured: bool = True
) -> str:
    """Write the quality report as Markdown: one summary table, then one part per document."""
    summaries = [summarise(result) for result in results]
    rows = [summary_row(summary, tables_measured) for summary in summaries]

    lines = [
        "# Extraction report",
        "",
        f"Generated {generated_on} by `scripts/02_extract.py`.",
        "",
        "Page text is stored exactly as PyMuPDF reads it. Nothing is cleaned yet:",
        "the repeated header and footer lines below are only listed, not removed.",
        "",
        "## Summary",
        "",
        markdown_table(SUMMARY_HEADERS, rows),
        "",
        f"- `empty` = pages with no text at all; `scanned?` = pages that look scanned "
        f"(under {SCANNED_CHARS_WITH_IMAGE} characters with an image, or under "
        f"{SCANNED_CHARS_ANY} characters at all).",
        f"- `hindi` = pages where more than {HINDI_PAGE_RATIO:.0%} of the characters are "
        "Devanagari.",
        "- `skipped` = pages left out because they sit outside the page range in sources.csv.",
        "",
        f"Totals: {sum(s.pages for s in summaries)} pages extracted, "
        f"{sum(s.words for s in summaries):,} words, "
        f"{sum(s.skipped_pages for s in summaries)} pages skipped, "
        f"{sum(s.errors for s in summaries)} errors.",
        "",
    ]

    for result, summary in zip(results, summaries):
        lines += [
            f"## {result.doc_id}",
            "",
            f"- File: `{result.pdf_path.as_posix()}`",
            f"- PDF has {result.pdf_page_count} pages; read {describe_range(result)} "
            f"({summary.pages} extracted, {summary.skipped_pages} skipped)",
        ]
        if summary.likely_scanned:
            pages = [page.page for page in result.pages if page.likely_scanned]
            shown = ", ".join(str(page) for page in pages[:20])
            more = f" (+{len(pages) - 20} more)" if len(pages) > 20 else ""
            lines.append(f"- Pages that look scanned: {shown}{more}")
        if summary.hindi_pages:
            pages = [
                page.page for page in result.pages if page.devanagari_ratio > HINDI_PAGE_RATIO
            ]
            shown = ", ".join(str(page) for page in pages[:20])
            more = f" (+{len(pages) - 20} more)" if len(pages) > 20 else ""
            lines.append(f"- Mostly Hindi pages: {shown}{more}")

        lines.append("")
        if result.repeated_lines:
            lines.append(
                f"Repeated header/footer lines (on more than {REPEATED_LINE_SHARE:.0%} "
                f"of the {summary.pages} pages read):"
            )
            lines.append("")
            for line, count in result.repeated_lines:
                lines.append(f"- `{line}` — on {count} pages")
        else:
            lines.append("No repeated header or footer lines found.")
        lines.append("")

        if result.errors:
            lines.append("Errors:")
            lines.append("")
            for error in result.errors[:20]:
                lines.append(f"- {error}")
            if len(result.errors) > 20:
                lines.append(f"- (+{len(result.errors) - 20} more)")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
