"""Save the gazette's chapter structure before MPD47_PUBLICATION_EN leaves the index.

The gazette titles chapters 7 to 12 identically ("DEVELOPMENT CONTROL NORMS (DCN)"),
so a citation taken from the gazette alone cannot say which chapter it came from. The
Publication's contents list is the only place those chapters are named, so this script
reads the names from the Publication, matches each chapter to the gazette page it starts
on, and writes data/chapter_map.json. After that the Publication is no longer needed.

Reads data/processed/pages.jsonl, writes data/chapter_map.json. Safe to re-run.
Run with: uv run python scripts/build_chapter_map.py
"""

import json
import re
import sys

from app.config import settings
from app.extract import read_pages_jsonl, use_utf8_output

GAZETTE = "MPD47_GAZETTE_EN"
PUBLICATION = "MPD47_PUBLICATION_EN"
#: The gazette is bilingual; only these pages hold the English notification (see D-010).
GAZETTE_PAGES = (640, 1144)

#: The gazette's running header, in its English and Hindi forms.
GAZETTE_HEADER = re.compile(r"THE GAZETTE OF INDIA|PART II|भारत|राजपत्र|खण")
PAGE_NUMBER_LINE = re.compile(r"^\d{1,4}$")
ZERO_WIDTH = re.compile(r"[​-‏﻿]")

#: "Chapter 7: Residential", the Publication's contents list. Title Case, unlike the body.
CONTENTS_CHAPTER = re.compile(r"^Chapter\s+(\d{1,2})\s*:\s*(.+)$")
#: A contents line ends in the page it points at, across a wide gap or a run of dots.
CONTENTS_PAGE = re.compile(r"(?:\s{2,}|\.{2,}\s*)\d{1,4}$")
#: "CHAPTER 7. DEVELOPMENT CONTROL NORMS (DCN)", the heading over the chapter itself.
BODY_CHAPTER = re.compile(r"^CHAPTER\s+(\d{1,2})\b")
#: The longest a divider page's one line can be.
DIVIDER_WIDTH = 60


def page_lines(text: str) -> list[str]:
    """A page's non-empty lines, with the running header and page numbers dropped.

    Spacing inside a line is left alone: the wide gap before a contents-list page
    number is what tells "Chapter 6: Plan Monitoring    154" from a title ending in a year.
    """
    kept = []
    for raw in text.splitlines():
        line = ZERO_WIDTH.sub("", raw).strip()
        if not line or PAGE_NUMBER_LINE.match(line) or GAZETTE_HEADER.search(line):
            continue
        kept.append(line)
    return kept


def squeeze(line: str) -> str:
    """The same line with runs of spaces reduced to one."""
    return " ".join(line.split())


def contents_titles(pages: list[dict]) -> dict[int, str]:
    """Chapter number to full title, read from the Publication's contents list."""
    titles: dict[int, str] = {}
    for page in pages:
        for line in page_lines(page["text"]):
            match = CONTENTS_CHAPTER.match(squeeze(CONTENTS_PAGE.sub("", line)))
            if match:
                number = int(match.group(1))
                titles.setdefault(number, match.group(2).strip())
    return titles


def chapter_start_pages(pages: list[dict]) -> dict[int, int]:
    """Chapter number to the gazette page its heading sits on, first use only."""
    starts: dict[int, int] = {}
    for page in pages:
        for line in page_lines(page["text"]):
            match = BODY_CHAPTER.match(squeeze(line))
            if match:
                starts.setdefault(int(match.group(1)), page["page"])
    return starts


def back_matter_dividers(pages: list[dict], after_page: int) -> list[tuple[int, str]]:
    """The gazette's back-matter part titles: a page holding one all-capitals line.

    ABBREVIATIONS, DEFINITIONS, ANNEXURES, MAPS and SERVICE PLANS each get a divider
    page of their own after the last chapter. Without them the last chapter's range
    would swallow all of the back matter.
    """
    dividers = []
    for page in pages:
        if page["page"] <= after_page:
            continue
        lines = page_lines(page["text"])
        if len(lines) != 1:
            continue
        line = squeeze(lines[0])
        if len(line) > DIVIDER_WIDTH or BODY_CHAPTER.match(line):
            continue
        if line == line.upper() and len(re.findall(r"[A-Z]", line)) >= 3:
            dividers.append((page["page"], line))
    return dividers


def build_entries(
    titles: dict[int, str], starts: dict[int, int], dividers: list[tuple[int, str]]
) -> tuple[list[dict], list[str]]:
    """Put the chapters and the back-matter sections in page order and close each range."""
    warnings: list[str] = []
    entries: list[dict] = []

    for number in sorted(starts):
        if number not in titles:
            warnings.append(f"chapter {number} starts on gazette page {starts[number]} "
                            "but the Publication's contents list does not name it")
        entries.append(
            {
                "chapter": number,
                "title": titles.get(number, ""),
                "gazette_start_page": starts[number],
            }
        )
    for number in sorted(titles):
        if number not in starts:
            warnings.append(
                f"chapter {number} ({titles[number]}) is in the contents list but no "
                "CHAPTER heading for it was found in the gazette"
            )

    for page, line in dividers:
        entries.append(
            {
                "chapter": line.lower().replace(" ", "_"),
                "title": line.title(),
                "gazette_start_page": page,
            }
        )

    entries.sort(key=lambda entry: entry["gazette_start_page"])
    for index, entry in enumerate(entries):
        following = entries[index + 1]["gazette_start_page"] if index + 1 < len(entries) else None
        entry["gazette_end_page"] = following - 1 if following else GAZETTE_PAGES[1]
        if entry["gazette_end_page"] < entry["gazette_start_page"]:
            warnings.append(
                f"entry {entry['chapter']} ends before it starts "
                f"({entry['gazette_start_page']}-{entry['gazette_end_page']})"
            )
    return entries, warnings


def print_table(entries: list[dict]) -> None:
    """Print one line per entry: what it is, what it is called, which pages it covers."""
    headers = ("chapter", "title", "gazette pages", "pages")
    rows = [
        (
            str(entry["chapter"]),
            entry["title"],
            f"{entry['gazette_start_page']}-{entry['gazette_end_page']}",
            str(entry["gazette_end_page"] - entry["gazette_start_page"] + 1),
        )
        for entry in entries
    ]
    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]
    print(" | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))


def main() -> int:
    """Read both documents, build the chapter map, write it and print it."""
    use_utf8_output()
    path = settings.processed_dir / "pages.jsonl"
    if not path.exists():
        print(f"{path.as_posix()} is missing. Run: uv run python scripts/02_extract.py")
        return 1

    pages = read_pages_jsonl(path)
    first, last = GAZETTE_PAGES
    gazette = [
        page for page in pages if page["doc_id"] == GAZETTE and first <= page["page"] <= last
    ]
    publication = [page for page in pages if page["doc_id"] == PUBLICATION]
    if not gazette:
        print(f"No {GAZETTE} pages in {first}-{last}. Run scripts/02_extract.py first.")
        return 1
    if not publication:
        print(
            f"No {PUBLICATION} pages in pages.jsonl, so the chapter names cannot be read.\n"
            f"This script needs an extract made while {PUBLICATION} was still include=yes."
        )
        return 1

    print(f"Reading chapter names from {PUBLICATION} ({len(publication)} pages)")
    print(f"Reading start pages from {GAZETTE} pages {first}-{last} ({len(gazette)} pages)")
    print()

    titles = contents_titles(publication)
    starts = chapter_start_pages(gazette)
    dividers = back_matter_dividers(gazette, after_page=max(starts.values()) if starts else first)
    entries, warnings = build_entries(titles, starts, dividers)

    print_table(entries)
    print()

    out_path = settings.project_root / "data" / "chapter_map.json"
    out_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    chapters = [entry for entry in entries if isinstance(entry["chapter"], int)]
    sections = [entry for entry in entries if not isinstance(entry["chapter"], int)]
    covered = entries[0]["gazette_start_page"] if entries else first
    print(
        f"{len(entries)} entries: {len(chapters)} chapters and {len(sections)} back-matter "
        f"sections ({', '.join(entry['title'] for entry in sections)})."
    )
    print(
        f"Covered: gazette pages {covered}-{last}. Pages {first}-{covered - 1} hold the "
        f"notification preamble before chapter 1 and belong to no chapter."
    )
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"Wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
