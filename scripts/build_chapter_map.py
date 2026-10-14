"""Write data/chapter_map.json: which gazette pages each chapter and section covers.

Nothing in a page's own text says which chapter the page belongs to, so a citation
cannot name the chapter without this map. Every title here comes from the gazette's own
heading page, including the second and third lines that chapters 7 to 12 carry
("CHAPTER 7. DEVELOPMENT CONTROL NORMS (DCN)" then "FOR RESIDENTIAL").

Labels for the unnumbered entries (preamble, abbreviations, definitions, annexures, maps,
service_plans) are lower case with underscores; chapters keep their integer number.

The map covers gazette pages 640-1144, the English part of the notification, with every
page in exactly one entry. See D-010 for the page range and D-012 for why we index the
gazette alone.

Reads data/processed/pages.jsonl, writes data/chapter_map.json. Safe to re-run.
Run with: uv run python scripts/build_chapter_map.py
"""

import json
import re
import sys

from app.config import settings
from app.extract import read_pages_jsonl, use_utf8_output

GAZETTE = "MPD47_GAZETTE_EN"
#: The gazette is bilingual; only these pages hold the English notification (see D-010).
GAZETTE_PAGES = (640, 1144)

#: The pages before chapter 1: the S.O. notification and the plan's opening paragraphs.
#: Labels are lower case with underscores, like the back-matter ones, so nothing
#: downstream has to special-case a capital (see D-013).
PREAMBLE_LABEL = "preamble"
PREAMBLE_TITLE = "Notification preamble"

#: The gazette's running header, in its English and Hindi forms.
GAZETTE_HEADER = re.compile(r"THE GAZETTE OF INDIA|PART II|भारत|राजपत्र|खण")
PAGE_NUMBER_LINE = re.compile(r"^\d{1,4}$")
ZERO_WIDTH = re.compile(r"[​-‏﻿]")

#: "CHAPTER 7. DEVELOPMENT CONTROL NORMS (DCN)", with the title in the second group.
CHAPTER_HEADING = re.compile(r"^CHAPTER\s+(\d{1,2})\s*[.:]?\s*(.*)$")
#: The longest a divider page's one line can be.
DIVIDER_WIDTH = 60

#: Words that stay in lower case inside a title.
SMALL_WORDS = frozenset("a an and as at but by for from in nor of on or the to with".split())
#: Short forms the gazette writes in capitals, which title case must leave alone.
KNOWN_ACRONYMS = frozenset({"DCN", "PSP", "GIS", "TOD", "LDA", "DDA", "MPD", "NCR"})


def page_lines(text: str) -> list[str]:
    """A page's non-empty lines, with the running header and page numbers dropped."""
    kept = []
    for raw in text.splitlines():
        line = " ".join(ZERO_WIDTH.sub("", raw).split())
        if not line or PAGE_NUMBER_LINE.match(line) or GAZETTE_HEADER.search(line):
            continue
        kept.append(line)
    return kept


def title_case(text: str) -> str:
    """Turn an all-capitals gazette heading into title case, leaving acronyms alone."""
    words = []
    for index, token in enumerate(text.split()):
        bare = token.strip("()[].,;:")
        if bare.upper() in KNOWN_ACRONYMS or (
            token.startswith("(") and bare.isalpha() and len(bare) <= 5
        ):
            words.append(token)
        elif index and token.lower() in SMALL_WORDS:
            words.append(token.lower())
        else:
            words.append("-".join(part.capitalize() for part in token.split("-")))
    return " ".join(words)


def chapter_headings(pages: list[dict]) -> dict[int, tuple[int, str]]:
    """Chapter number to (start page, title), read from the gazette's heading pages.

    A chapter heading sits alone on its own page, so every line on that page belongs to
    the title. Chapters 7 to 12 run onto a second and sometimes a third line.
    """
    found: dict[int, tuple[int, str]] = {}
    for page in pages:
        lines = page_lines(page["text"])
        if not lines:
            continue
        match = CHAPTER_HEADING.match(" ".join(lines))
        if match:
            number = int(match.group(1))
            found.setdefault(number, (page["page"], title_case(match.group(2).strip())))
    return found


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
        line = lines[0]
        if len(line) > DIVIDER_WIDTH or CHAPTER_HEADING.match(line):
            continue
        if line == line.upper() and len(re.findall(r"[A-Z]", line)) >= 3:
            dividers.append((page["page"], line))
    return dividers


def build_entries(
    chapters: dict[int, tuple[int, str]], dividers: list[tuple[int, str]]
) -> tuple[list[dict], list[str]]:
    """Put the preamble, the chapters and the back matter in page order and close each range."""
    first, last = GAZETTE_PAGES
    entries: list[dict] = [
        {"chapter": PREAMBLE_LABEL, "title": PREAMBLE_TITLE, "gazette_start_page": first}
    ]
    for number in sorted(chapters):
        start, title = chapters[number]
        entries.append({"chapter": number, "title": title, "gazette_start_page": start})
    for page, line in dividers:
        entries.append(
            {
                "chapter": line.lower().replace(" ", "_"),
                "title": title_case(line),
                "gazette_start_page": page,
            }
        )

    entries.sort(key=lambda entry: entry["gazette_start_page"])
    for index, entry in enumerate(entries):
        following = entries[index + 1]["gazette_start_page"] if index + 1 < len(entries) else None
        entry["gazette_end_page"] = following - 1 if following else last

    warnings = check_coverage(entries, chapters)
    return entries, warnings


def check_coverage(entries: list[dict], chapters: dict[int, tuple[int, str]]) -> list[str]:
    """Check that every page from 640 to 1144 sits in exactly one entry."""
    first, last = GAZETTE_PAGES
    warnings: list[str] = []

    if not entries:
        return ["no entries were built"]
    if entries[0]["gazette_start_page"] != first:
        warnings.append(f"the first entry starts on {entries[0]['gazette_start_page']}, not {first}")
    if entries[-1]["gazette_end_page"] != last:
        warnings.append(f"the last entry ends on {entries[-1]['gazette_end_page']}, not {last}")
    for entry in entries:
        if entry["gazette_end_page"] < entry["gazette_start_page"]:
            warnings.append(
                f"entry {entry['chapter']} ends before it starts "
                f"({entry['gazette_start_page']}-{entry['gazette_end_page']})"
            )
    for earlier, later in zip(entries, entries[1:]):
        if earlier["gazette_end_page"] + 1 < later["gazette_start_page"]:
            warnings.append(
                f"gap between {earlier['chapter']} (ends {earlier['gazette_end_page']}) and "
                f"{later['chapter']} (starts {later['gazette_start_page']})"
            )
        elif earlier["gazette_end_page"] + 1 > later["gazette_start_page"]:
            warnings.append(
                f"overlap between {earlier['chapter']} (ends {earlier['gazette_end_page']}) and "
                f"{later['chapter']} (starts {later['gazette_start_page']})"
            )
    if chapters:
        missing = [n for n in range(1, max(chapters) + 1) if n not in chapters]
        if missing:
            warnings.append(
                f"no heading page found for chapter(s) {', '.join(str(n) for n in missing)}"
            )
    return warnings


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
    """Read the gazette, build the chapter map, write it and print it."""
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
    if not gazette:
        print(f"No {GAZETTE} pages in {first}-{last}. Run scripts/02_extract.py first.")
        return 1

    print(f"Reading chapter titles and start pages from {GAZETTE} pages {first}-{last} "
          f"({len(gazette)} pages)")
    print()

    chapters = chapter_headings(gazette)
    after = max(start for start, _ in chapters.values()) if chapters else first
    dividers = back_matter_dividers(gazette, after_page=after)
    entries, warnings = build_entries(chapters, dividers)

    print_table(entries)
    print()

    out_path = settings.project_root / "data" / "chapter_map.json"
    out_path.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    numbered = [entry for entry in entries if isinstance(entry["chapter"], int)]
    labelled = [entry for entry in entries if not isinstance(entry["chapter"], int)]
    pages_covered = sum(
        entry["gazette_end_page"] - entry["gazette_start_page"] + 1 for entry in entries
    )
    print(
        f"{len(entries)} entries: {len(numbered)} chapters and {len(labelled)} labelled "
        f"sections ({', '.join(str(entry['chapter']) for entry in labelled)})."
    )
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print(
            f"Coverage: pages {first}-{last} with no gaps and no overlaps "
            f"({pages_covered} pages in {len(entries)} entries)."
        )
    print(f"Wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
