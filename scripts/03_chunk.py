"""Clean the extracted pages and cut them into chunks ready for indexing.

Reads  data/processed/pages.jsonl, data/chapter_map.json, data/sources.csv
Writes data/processed/chunks.jsonl
       data/processed/chunk_report.md   counts, size buckets, warnings
       data/processed/chunk_sample.md   20 random chunks for hand review

Table pages are re-read from the PDF, because pages.jsonl holds only text and a table
has to be pulled out of the page before the text around it can be read in order.

Safe to re-run. Run with: uv run python scripts/03_chunk.py
"""

import json
import random
import sys
from datetime import date
from pathlib import Path

import pymupdf

from app.chunking import (
    HARD_MAX_WORDS,
    MERGE_UNDER_WORDS,
    PARAGRAPH_MAX_WORDS,
    TARGET_MAX_WORDS,
    TARGET_MIN_WORDS,
    Section,
    assign_chunk_ids,
    chunk_faq,
    chunk_gazette,
    chunk_paragraph_document,
    page_span,
    render,
    split_section,
)
from app.cleaning import Line, clean_text_lines, count_words, join_hyphenated, page_lines_from_pdf
from app.config import settings
from app.extract import (
    edge_lines,
    find_repeated_lines,
    markdown_table,
    read_pages_jsonl,
    read_sources,
    resolve_pdf_path,
    use_utf8_output,
)

GAZETTE = "MPD47_GAZETTE_EN"
SAMPLE_SEED = 42
SAMPLE_SIZE = 20
#: Word-length buckets reported for a human to scan.
BUCKETS = (
    ("<40", 0, MERGE_UNDER_WORDS - 1),
    ("40-149", MERGE_UNDER_WORDS, TARGET_MIN_WORDS - 1),
    ("150-400", TARGET_MIN_WORDS, TARGET_MAX_WORDS),
    ("401-500", TARGET_MAX_WORDS + 1, HARD_MAX_WORDS),
    ("501-650", HARD_MAX_WORDS + 1, PARAGRAPH_MAX_WORDS),
    (">650", PARAGRAPH_MAX_WORDS + 1, 10**9),
)


def load_chapter_map(path: Path) -> list[dict]:
    """Read data/chapter_map.json."""
    return json.loads(path.read_text(encoding="utf-8"))


def chapter_lookup(chapter_map: list[dict]):
    """Build two functions: page -> chapter label, and page -> chapter title."""
    entries = [
        (entry["gazette_start_page"], entry["gazette_end_page"], entry["chapter"], entry["title"])
        for entry in chapter_map
    ]

    def label(page: int):
        for start, end, chapter, _ in entries:
            if start <= page <= end:
                return chapter
        return ""

    def title(page: int) -> str:
        for start, end, _, name in entries:
            if start <= page <= end:
                return name
        return ""

    return label, title


def document_lines(
    doc_id: str, pages: list[dict], pdf_path: Path | None, drop_hindi: bool
) -> tuple[list[Line], list[str], int, int]:
    """Clean one document's pages into one continuous line stream.

    Pages that PyMuPDF found tables on are re-read from the PDF so the tables come
    through as markdown; the rest use the text already in pages.jsonl. Returns the
    lines, any warnings, and how many tables were converted and fell back.
    """
    warnings: list[str] = []
    converted = fallen_back = 0
    table_pages = {page["page"] for page in pages if (page["n_tables"] or 0) > 0}

    doc = None
    if table_pages and pdf_path is not None:
        try:
            doc = pymupdf.open(pdf_path)
        except Exception as exc:
            warnings.append(f"{doc_id}: cannot reopen the PDF for tables ({exc}); using text only")

    lines: list[Line] = []
    for page in sorted(pages, key=lambda item: item["page"]):
        number = page["page"]
        if doc is not None and number in table_pages:
            try:
                page_lines, page_warnings = page_lines_from_pdf(
                    doc.load_page(number - 1), number, drop_hindi
                )
            except Exception as exc:
                warnings.append(f"{doc_id} page {number}: table reading failed ({exc})")
                page_lines, page_warnings = (
                    [Line(text, number) for text in clean_text_lines(page["text"], drop_hindi)],
                    [],
                )
            warnings += [f"{doc_id}: {item}" for item in page_warnings]
            tables_here = sum(1 for line in page_lines if line.is_table)
            if tables_here:
                converted += tables_here
            else:
                fallen_back += page["n_tables"] or 0
        else:
            page_lines = [Line(text, number) for text in clean_text_lines(page["text"], drop_hindi)]
        if lines and page_lines:
            lines.append(Line("", number))
        lines += page_lines

    if doc is not None:
        doc.close()
    return join_hyphenated(lines), warnings, converted, fallen_back


def without_digits(text: str) -> str:
    """A line with its digits taken out, so a footer that carries a page number matches.

    "Indian Kanoon - http://indiankanoon.org/doc/28108780/ 3" is the same footer on
    every page of the court order, but the page number at the end makes each copy
    unique. Comparing the digit-free form is the same trick the gazette header rule
    uses (D-011).
    """
    return " ".join("".join(char for char in text if not char.isdigit()).split())


def drop_running_headers(pages: list[dict], lines: list[Line]) -> tuple[list[Line], list[str]]:
    """Remove each document's own running header, found by how often a line repeats.

    The gazette's header is matched by wording in app/cleaning.py, but the FAQ, the
    court order and the NGT report each carry a different one ("Shabnam Burney vs Union
    Of India And Ors on 8 July, 2024" sits at the top of every page of the order). The
    same 40% rule the extract report uses finds them (see D-011), applied to the
    digit-free form of each line.
    """
    edges = [{without_digits(line) for line in edge_lines(page["text"])} for page in pages]
    repeated = find_repeated_lines(edges)
    headers = {line for line, _ in repeated if line}
    if not headers:
        return lines, []
    kept = [
        line for line in lines if line.is_table or without_digits(line.text) not in headers
    ]
    note = [
        f"dropped repeated header/footer line: {line!r} (on {count} pages)"
        for line, count in repeated
    ]
    return kept, note


def sections_for(doc_id: str, lines: list[Line], chapter_of_page, doc_title: str) -> list[Section]:
    """Pick the chunker that fits a document."""
    if doc_id == GAZETTE:
        return chunk_gazette(lines, chapter_of_page)
    if doc_id == "MPD47_FAQ":
        return chunk_faq(lines)
    return chunk_paragraph_document(lines, doc_title)


def build_records(
    doc: dict, sections: list[Section], chapter_of_page, chapter_title_of_page
) -> list[dict]:
    """Turn sections into chunk records, applying the splitting rules on the way."""
    pieces: list[tuple[Section, list[Line]]] = []
    for section in sections:
        for run in split_section(section.lines):
            pieces.append((section, run))

    spans = [page_span(run) for _, run in pieces]
    ids = assign_chunk_ids(
        doc["doc_id"],
        [(section.clause_id, span[0]) for (section, _), span in zip(pieces, spans)],
    )

    records: list[dict] = []
    for chunk_id, (section, run), (page_start, page_end) in zip(ids, pieces, spans):
        text = render(run)
        is_gazette = doc["doc_id"] == GAZETTE
        chapter = chapter_of_page(page_start) if is_gazette else ""
        chapter_title = chapter_title_of_page(page_start) if is_gazette else ""
        if is_gazette:
            header = " › ".join(["MPD-2047", str(chapter_title)] + section.heading_path)
        else:
            header = doc["title"]
        records.append(
            {
                "chunk_id": chunk_id,
                "doc_id": doc["doc_id"],
                "doc_title": doc["title"],
                "doc_type": doc["doc_type"],
                "authority_rank": int(doc["authority_rank"]),
                "doc_date": doc["doc_date"],
                "source_url": doc["url"],
                "chapter": chapter if isinstance(chapter, str) else str(chapter),
                "chapter_title": chapter_title,
                "heading_path": list(section.heading_path),
                "clause_id": section.clause_id,
                "clause_ids": list(section.clause_ids),
                "page_start": page_start,
                "page_end": page_end,
                "text": text,
                "embed_text": f"{header}\n\n{text}",
                "n_words": count_words(text),
                "has_table": any(line.is_table for line in run),
            }
        )
    return records


def bucket_of(words: int) -> str:
    """Which word-length bucket a chunk falls in."""
    for name, low, high in BUCKETS:
        if low <= words <= high:
            return name
    return ">650"


def build_report(
    records: list[dict],
    per_doc_tables: dict[str, tuple[int, int]],
    warnings: list[str],
    generated_on: str,
) -> str:
    """The chunk report: counts per document and chapter, size buckets, outliers, warnings."""
    lines = [
        "# Chunk report",
        "",
        f"Generated {generated_on} by `scripts/03_chunk.py`.",
        "",
        f"{len(records)} chunks, {sum(r['n_words'] for r in records):,} words in total.",
        "",
        "## Chunks per document",
        "",
    ]

    rows = []
    for doc_id in dict.fromkeys(record["doc_id"] for record in records):
        mine = [record for record in records if record["doc_id"] == doc_id]
        converted, fallen = per_doc_tables.get(doc_id, (0, 0))
        rows.append(
            [
                doc_id,
                str(len(mine)),
                f"{sum(r['n_words'] for r in mine):,}",
                str(round(sum(r["n_words"] for r in mine) / len(mine))),
                str(sum(1 for r in mine if r["has_table"])),
                str(converted),
                str(fallen),
            ]
        )
    lines += [
        markdown_table(
            ("doc_id", "chunks", "words", "mean words", "with table", "tables converted", "tables fallen back"),
            rows,
        ),
        "",
        "## Chunks per chapter (MPD47_GAZETTE_EN)",
        "",
    ]

    gazette = [record for record in records if record["doc_id"] == GAZETTE]
    chapter_rows = []
    for chapter in dict.fromkeys(record["chapter"] for record in gazette):
        mine = [record for record in gazette if record["chapter"] == chapter]
        chapter_rows.append(
            [
                chapter,
                mine[0]["chapter_title"],
                str(len(mine)),
                f"{sum(r['n_words'] for r in mine):,}",
                str(round(sum(r["n_words"] for r in mine) / len(mine))),
            ]
        )
    lines += [
        markdown_table(("chapter", "title", "chunks", "words", "mean words"), chapter_rows),
        "",
        "## Word-length buckets",
        "",
    ]

    counts = {name: 0 for name, _, _ in BUCKETS}
    for record in records:
        counts[bucket_of(record["n_words"])] += 1
    lines += [
        markdown_table(
            ("words", "chunks", "share"),
            [
                [name, str(counts[name]), f"{counts[name] / max(1, len(records)):.1%}"]
                for name, _, _ in BUCKETS
            ],
        ),
        "",
        f"Target is {TARGET_MIN_WORDS}-{TARGET_MAX_WORDS} words. Sections under "
        f"{MERGE_UNDER_WORDS} words are merged with their next sibling where one exists, "
        f"and sections over {HARD_MAX_WORDS} are split; a chunk can still fall outside "
        "the target where the text gives nothing to split on.",
        "",
        "## Shortest and longest chunks",
        "",
    ]

    by_words = sorted(records, key=lambda record: record["n_words"])
    for label, group in (("5 shortest", by_words[:5]), ("5 longest", list(reversed(by_words[-5:])))):
        lines += [f"**{label}**", ""]
        for record in group:
            lines.append(
                f"- `{record['chunk_id']}` — {record['n_words']} words, "
                f"pages {record['page_start']}-{record['page_end']}, "
                f"path: {' › '.join(record['heading_path']) or '(none)'}"
            )
        lines.append("")

    no_clause = [record for record in records if not record["clause_id"]]
    lines += [
        "## Clause numbers",
        "",
        f"{len(no_clause)} of {len(records)} chunks have no clause_id "
        f"({len(no_clause) / max(1, len(records)):.1%}). "
        "These are the parts of the text that are not numbered: the preamble, the "
        "abbreviations and definitions lists, the maps captions, chapter introductions "
        "and the unnumbered front pages of the court order and the NGT report.",
        "",
    ]
    rows = []
    for doc_id in dict.fromkeys(record["doc_id"] for record in records):
        mine = [record for record in records if record["doc_id"] == doc_id]
        rows.append(
            [doc_id, str(sum(1 for r in mine if not r["clause_id"])), str(len(mine))]
        )
    lines += [markdown_table(("doc_id", "no clause_id", "chunks"), rows), ""]

    total_converted = sum(converted for converted, _ in per_doc_tables.values())
    total_fallen = sum(fallen for _, fallen in per_doc_tables.values())
    lines += [
        "## Tables",
        "",
        f"{total_converted} tables converted to markdown, {total_fallen} fell back to "
        "the plain text of their page (over half the cells empty, or fewer than two "
        "columns).",
        "",
        "## Warnings",
        "",
    ]
    if warnings:
        lines.append(f"{len(warnings)} warning(s):")
        lines.append("")
        lines += [f"- {warning}" for warning in warnings]
    else:
        lines.append("None.")
    return "\n".join(lines).rstrip() + "\n"


def build_sample(records: list[dict], generated_on: str) -> str:
    """20 random chunks in full, for reading by hand."""
    chosen = random.Random(SAMPLE_SEED).sample(records, min(SAMPLE_SIZE, len(records)))
    lines = [
        "# Chunk sample",
        "",
        f"Generated {generated_on} by `scripts/03_chunk.py`: "
        f"{len(chosen)} chunks drawn at random with seed {SAMPLE_SEED}, shown in full.",
        "",
        "Read these the way a user would read a search result: does the chunk say one "
        "thing, is the clause whole, does the heading path place it, and is the page "
        "range right?",
        "",
    ]
    for index, record in enumerate(chosen, start=1):
        lines += [
            f"## {index}. `{record['chunk_id']}`",
            "",
            f"- document: {record['doc_id']} ({record['doc_type']}, "
            f"authority rank {record['authority_rank']})",
            f"- chapter: {record['chapter'] or '(none)'} — {record['chapter_title'] or '(none)'}",
            f"- heading path: {' › '.join(record['heading_path']) or '(none)'}",
            f"- clause_id: {record['clause_id'] or '(none)'}   clause_ids: "
            f"{', '.join(record['clause_ids']) or '(none)'}",
            f"- pages {record['page_start']}-{record['page_end']}, "
            f"{record['n_words']} words, has_table: {record['has_table']}",
            "",
            "```",
            record["text"],
            "```",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Clean, chunk, write the three output files and print a summary."""
    use_utf8_output()
    pages_path = settings.processed_dir / "pages.jsonl"
    if not pages_path.exists():
        print(f"{pages_path.as_posix()} is missing. Run: uv run python scripts/02_extract.py")
        return 1

    pages = read_pages_jsonl(pages_path)
    sources = {row["doc_id"]: row for row in read_sources(settings.sources_csv)}
    chapter_map = load_chapter_map(settings.project_root / "data" / "chapter_map.json")
    chapter_of_page, chapter_title_of_page = chapter_lookup(chapter_map)

    by_doc: dict[str, list[dict]] = {}
    for page in pages:
        by_doc.setdefault(page["doc_id"], []).append(page)

    records: list[dict] = []
    warnings: list[str] = []
    per_doc_tables: dict[str, tuple[int, int]] = {}

    for doc_id, doc_pages in by_doc.items():
        doc = sources.get(doc_id)
        if doc is None:
            warnings.append(f"{doc_id}: not listed in sources.csv, skipped")
            continue
        if doc.get("include") != "yes":
            warnings.append(f"{doc_id}: include={doc.get('include')!r}, skipped")
            continue

        pdf_path = resolve_pdf_path(settings.raw_dir, doc_id)
        lines, doc_warnings, converted, fallen = document_lines(
            doc_id, doc_pages, pdf_path, drop_hindi=(doc_id == GAZETTE)
        )
        warnings += doc_warnings
        per_doc_tables[doc_id] = (converted, fallen)

        if doc_id != GAZETTE:
            lines, notes = drop_running_headers(doc_pages, lines)
            warnings += [f"{doc_id}: {note}" for note in notes]

        sections = sections_for(doc_id, lines, chapter_of_page, doc["title"])
        doc_records = build_records(doc, sections, chapter_of_page, chapter_title_of_page)
        records += doc_records
        print(
            f"{doc_id}: {len(doc_pages)} pages -> {len(sections)} sections -> "
            f"{len(doc_records)} chunks ({converted} tables converted, {fallen} fell back)"
        )

    if not records:
        print("No chunks were built. Nothing written.")
        return 1

    generated_on = date.today().isoformat()
    out_path = settings.processed_dir / "chunks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    report_path = settings.processed_dir / "chunk_report.md"
    report_path.write_text(
        build_report(records, per_doc_tables, warnings, generated_on), encoding="utf-8"
    )
    sample_path = settings.processed_dir / "chunk_sample.md"
    sample_path.write_text(build_sample(records, generated_on), encoding="utf-8")

    counts = {name: 0 for name, _, _ in BUCKETS}
    for record in records:
        counts[bucket_of(record["n_words"])] += 1
    in_target = counts["150-400"] / len(records)

    print()
    print(f"{len(records)} chunks, {sum(r['n_words'] for r in records):,} words.")
    print(
        "word buckets: "
        + ", ".join(f"{name} {counts[name]}" for name, _, _ in BUCKETS)
        + f" ({in_target:.0%} in the 150-400 target)"
    )
    print(
        f"{sum(1 for r in records if r['has_table'])} chunks contain a table; "
        f"{sum(1 for r in records if not r['clause_id'])} have no clause_id."
    )
    print(f"{len(warnings)} warning(s); see {report_path.relative_to(settings.project_root).as_posix()}")
    for path in (out_path, report_path, sample_path):
        print(f"wrote {path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
