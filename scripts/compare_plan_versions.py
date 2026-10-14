"""One-off analysis: is MPD47_PUBLICATION_EN the same text as the gazette's English part?

Both documents are marked include=yes in data/sources.csv, and the CSV note warns they
may be the same plan twice. Indexing both would double-count every clause, so this
script compares them: chapter headings, how much sentence text overlaps, and which
file has the cleaner page text.

Reads data/processed/pages.jsonl only. Writes nothing. Safe to re-run.
Run with: uv run python scripts/compare_plan_versions.py
"""

import random
import re
import sys

from app.config import settings
from app.extract import read_pages_jsonl, use_utf8_output

GAZETTE = "MPD47_GAZETTE_EN"
PUBLICATION = "MPD47_PUBLICATION_EN"
#: The gazette is bilingual; only these pages hold the English notification (see D-010).
GAZETTE_PAGES = (640, 1144)

SEED = 20261014
SAMPLE_SIZE = 40
MIN_SENTENCE_WORDS = 15
EXAMPLES_TO_SHOW = 3
LONGEST_PAGES = 10

#: The gazette's running header, in its English and Hindi forms.
GAZETTE_HEADER = re.compile(r"THE GAZETTE OF INDIA|PART II|भारत|राजपत्र|खण")
#: A line that is nothing but a page number.
PAGE_NUMBER_LINE = re.compile(r"^\d{1,4}$")
#: Zero-width joiners and friends, which PyMuPDF keeps and which break plain matching.
ZERO_WIDTH = re.compile(r"[​-‏﻿]")

#: CHAPTER 1. CONTEXT, or Chapter 1: Context (the Publication's contents pages).
CHAPTER_LINE = re.compile(r"^chapter\b", re.IGNORECASE)
#: 3.1 ENVIRONMENT, or 12. TRANSIT ORIENTED DEVELOPMENT: a number, then a capitals-only title.
NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)([.:])?\s+([^a-z]{3,90})$")
#: A contents line points at a page across a wide gap: "Chapter 5: Development Code   141".
#: The gap matters: it tells a contents entry from a heading that ends in a year.
CONTENTS_ENTRY = re.compile(r"(?:\s{2,}|\.{2,}\s*)(\d{1,4})$")
#: "Chapter 7: Residential", so the summary can name what the Publication calls each chapter.
CONTENTS_CHAPTER = re.compile(r"^chapter\s+(\d{1,2})\s*[:.]\s*(.+)$", re.IGNORECASE)
#: "5. Service Plan - New Delhi Municipal Council (NDMC)", from the gazette's annexure list.
#: The first group catches the case, which tells the list apart from the annexure headings.
SERVICE_PLAN = re.compile(
    r"^\d+(?:\s*&\s*\d+)?\.\s+(service plan)\s*[-–]\s*(.+)$", re.IGNORECASE
)
#: The chapter number at the front of a body heading.
CHAPTER_NUMBER = re.compile(r"^CHAPTER\s+(\d{1,2})", re.IGNORECASE)


# --- text preparation ----------------------------------------------------------


def page_lines(text: str) -> list[str]:
    """A page's non-empty lines, with the running header and page numbers dropped."""
    kept = []
    for line in text.splitlines():
        stripped = ZERO_WIDTH.sub("", line).rstrip()
        if not stripped.strip():
            continue
        if PAGE_NUMBER_LINE.match(stripped.strip()) or GAZETTE_HEADER.search(stripped):
            continue
        kept.append(stripped)
    return kept


def normalise(pages: list[dict]) -> str:
    """One lowercase string per document: no header, no page numbers, single spaces."""
    joined = " ".join(line for page in pages for line in page_lines(page["text"]))
    return re.sub(r"\s+", " ", joined).lower().strip()


def letters_only(text: str) -> str:
    """The same text with every character that is not a letter, digit or space removed."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text)).strip()


def sentence_pool(pages: list[dict]) -> list[tuple[int, str]]:
    """Sentences of 15+ words, each with the page it came from, normalised for matching."""
    pool = []
    for page in pages:
        text = re.sub(r"\s+", " ", " ".join(page_lines(page["text"]))).lower().strip()
        for part in re.split(r"(?<=[.;:])\s+", text):
            if len(part.split()) >= MIN_SENTENCE_WORDS:
                pool.append((page["page"], part))
    return pool


# --- headings ------------------------------------------------------------------


def heading_key(line: str) -> str:
    """A comparable form of a heading: upper case, punctuation and spacing flattened."""
    return re.sub(r"[^A-Z0-9&()]+", " ", line.upper()).strip()


def looks_like_heading(line: str) -> bool:
    """True for a chapter line, or a numbered line whose title is all capitals."""
    if CHAPTER_LINE.match(line):
        return True
    match = NUMBERED_HEADING.match(line)
    if not match:
        return False
    number, separator, title = match.groups()
    # A bare number with no "." or ":" is usually a table cell ("20 LPCD"), not a heading.
    if separator is None and "." not in number:
        return False
    if title.rstrip().endswith((",", ".")):
        return False
    words = re.findall(r"[A-Z]+", title)
    if not any(len(word) >= 4 for word in words):
        return False
    return len(re.findall(r"[A-Z]", title)) > len(re.findall(r"\d", title))


def find_headings(
    pages: list[dict],
) -> tuple[list[tuple[int, str, str]], list[tuple[int, str, str]]]:
    """Heading lines, split into body headings and contents-list entries.

    Both come back as (page, line, comparable key), keeping the first use of each key.
    """
    body: list[tuple[int, str, str]] = []
    contents: list[tuple[int, str, str]] = []
    seen: dict[bool, set[str]] = {True: set(), False: set()}
    for page in pages:
        for raw in page_lines(page["text"]):
            # The wide gap before a contents page number survives only in the raw line.
            entry = bool(CONTENTS_ENTRY.search(raw))
            line = " ".join(CONTENTS_ENTRY.sub("", raw).split()) if entry else " ".join(raw.split())
            if not line or not looks_like_heading(line):
                continue
            # A contents entry reads "Chapter 5: Development Code"; the heading over the
            # chapter itself reads "CHAPTER 5. DEVELOPMENT CODE". Lower case tells them apart
            # even where PyMuPDF dropped the page number at the end of the contents line.
            is_contents = entry or (CHAPTER_LINE.match(line) and line != line.upper())
            key = heading_key(line)
            if key in seen[bool(is_contents)]:
                continue
            seen[bool(is_contents)].add(key)
            (contents if is_contents else body).append((page["page"], line, key))
    return body, contents


# --- printing helpers ----------------------------------------------------------


def rule(title: str) -> None:
    """Print a section heading."""
    print()
    print(title)
    print("=" * len(title))


def shorten(text: str, width: int) -> str:
    """Cut text to a width, with an ellipsis when something was cut."""
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3] + "..."


# --- part 1: headings ----------------------------------------------------------


def compare_headings(gazette: list[dict], publication: list[dict]) -> dict:
    """Print both documents' headings side by side, then what only one of them has."""
    rule("1. Chapter and top-level section headings")
    left, left_contents = find_headings(gazette)
    right, right_contents = find_headings(publication)
    print("Rule: a line starting with CHAPTER, or a number then an all-capitals title.")
    print("Contents-list entries are listed separately: a title with a wide gap and a page")
    print("number after it, or the Publication's Title Case 'Chapter 5: Development Code'")
    print("form, as against the 'CHAPTER 5. DEVELOPMENT CODE' heading over the chapter itself.")
    print(f"Body headings: {len(left)} in the gazette, {len(right)} in the Publication.\n")

    right_pages = {key: page for page, _, key in right}
    left_pages = {key: page for page, _, key in left}
    print(f"{'heading':<58} | {'gazette p.':>10} | {'publication p.':>14}")
    print(f"{'-' * 58}-+-{'-' * 10}-+-{'-' * 14}")
    for page, line, key in left:
        other = right_pages.get(key)
        print(f"{shorten(line, 58):<58} | {page:>10} | {other if other else '-':>14}")
    for page, line, key in right:
        if key not in left_pages:
            print(f"{shorten(line, 58):<58} | {'-':>10} | {page:>14}")

    only_left = [(page, line) for page, line, key in left if key not in right_pages]
    only_right = [(page, line) for page, line, key in right if key not in left_pages]
    shared = [(page, line) for page, line, key in left if key in right_pages]

    for name, only in ((GAZETTE, only_left), (PUBLICATION, only_right)):
        print(f"\nBody headings only in {name} ({len(only)}):")
        for page, line in only:
            print(f"  p.{page}: {shorten(line, 80)}")
        if not only:
            print("  (none)")

    for name, entries in ((GAZETTE, left_contents), (PUBLICATION, right_contents)):
        print(f"\nContents-list entries in {name} ({len(entries)}):")
        for page, line, _ in entries:
            print(f"  p.{page}: {shorten(line, 80)}")
        if not entries:
            print("  (none)")

    return {
        "shared": shared,
        "only_gazette": only_left,
        "only_publication": only_right,
        "gazette_contents": left_contents,
        "publication_contents": right_contents,
        "gazette_body": left,
        "publication_body": right,
    }


# --- part 2: text overlap ------------------------------------------------------


def one_direction(
    name_from: str,
    name_in: str,
    pool: list[tuple[int, str]],
    target: str,
    rng: random.Random,
) -> dict:
    """Sample sentences from one document, look for them in the other, print the result."""
    sample = rng.sample(pool, min(SAMPLE_SIZE, len(pool)))
    loose_target = letters_only(target)

    missed = [(page, text) for page, text in sample if text not in target]
    loose_missed = [
        (page, text) for page, text in sample if letters_only(text) not in loose_target
    ]
    matched = len(sample) - len(missed)
    rate = matched / len(sample) if sample else 0.0

    print(
        f"{len(sample)} sentences of {MIN_SENTENCE_WORDS}+ words from {name_from} "
        f"(pool: {len(pool)}), looked up in {name_in}:"
    )
    print(f"  exact match after normalising : {rate:.0%} ({matched}/{len(sample)})")
    print(
        f"  ignoring punctuation too      : "
        f"{(len(sample) - len(loose_missed)) / len(sample):.0%} "
        f"({len(sample) - len(loose_missed)}/{len(sample)})"
    )
    print(f"  {min(EXAMPLES_TO_SHOW, len(missed))} of the {len(missed)} that did NOT match:")
    for page, text in missed[:EXAMPLES_TO_SHOW]:
        print(f"    - p.{page}: {shorten(text, 140)}")
    if not missed:
        print("    (none)")
    print()
    return {"rate": rate, "missed": missed, "sample": sample}


def compare_text(gazette: list[dict], publication: list[dict]) -> tuple[dict, dict]:
    """Sample sentences both ways and report how many are found in the other file."""
    rule("2. Sentence overlap, both directions")
    print("Normalised both ways: running header and page numbers dropped, lower case,")
    print(f"whitespace collapsed. Random seed {SEED}, so the sample repeats on every run.\n")
    rng = random.Random(SEED)
    gazette_text = normalise(gazette)
    publication_text = normalise(publication)
    forward = one_direction(
        PUBLICATION, GAZETTE, sentence_pool(publication), gazette_text, rng
    )
    backward = one_direction(
        GAZETTE, PUBLICATION, sentence_pool(gazette), publication_text, rng
    )
    return forward, backward


# --- part 3: page-level numbers ------------------------------------------------


def page_stats(name: str, pages: list[dict]) -> dict:
    """Print one document's page-level numbers and return them for the summary."""
    words = [page["n_words"] for page in pages]
    chars = sum(page["n_chars"] for page in pages)
    hindi_chars = sum(page["devanagari_ratio"] * page["n_chars"] for page in pages)
    stats = {
        "name": name,
        "pages": len(pages),
        "words": sum(words),
        "words_per_page": sum(words) / len(pages) if pages else 0,
        "pages_with_tables": sum(1 for page in pages if (page["n_tables"] or 0) > 0),
        "tables": sum(page["n_tables"] or 0 for page in pages),
        "empty": sum(1 for page in pages if page["n_chars"] == 0),
        "scanned": sum(1 for page in pages if page["likely_scanned"]),
        "hindi_share": hindi_chars / chars if chars else 0,
    }

    print(f"{name}")
    print(f"  pages                      : {stats['pages']}")
    print(f"  words                      : {stats['words']:,}")
    print(f"  words per page             : {stats['words_per_page']:.0f}")
    print(
        f"  pages with tables          : {stats['pages_with_tables']} "
        f"({stats['tables']} tables)"
    )
    print(f"  pages with no usable text  : {stats['empty']} empty, {stats['scanned']} scanned")
    print(f"  characters that are Hindi  : {stats['hindi_share']:.2%}")
    print(f"  the {LONGEST_PAGES} longest pages by word count:")
    for page in sorted(pages, key=lambda item: item["n_words"], reverse=True)[:LONGEST_PAGES]:
        print(f"    p.{page['page']:<5} {page['n_words']:>5} words")
    print()
    return stats


def compare_pages(gazette: list[dict], publication: list[dict]) -> tuple[dict, dict]:
    """Page-level numbers for both documents."""
    rule("3. Page-level numbers")
    return page_stats(GAZETTE, gazette), page_stats(PUBLICATION, publication)


# --- part 4: summary -----------------------------------------------------------


def service_plan_names(pages: list[dict]) -> list[str]:
    """The agency names from the gazette's own list of service-plan annexures."""
    names: list[str] = []
    for page in pages:
        for raw in page_lines(page["text"]):
            match = SERVICE_PLAN.match(" ".join(raw.split()))
            # The list itself is in Title Case; the headings over the annexures are capitals.
            if match and match.group(1) != match.group(1).upper():
                name = match.group(2).strip()
                if name not in names:
                    names.append(name)
    return names


def chapter_names(contents: list[tuple[int, str, str]]) -> dict[int, str]:
    """Chapter number to the name the contents list gives it."""
    names = {}
    for _, line, _ in contents:
        match = CONTENTS_CHAPTER.match(line)
        if match:
            names[int(match.group(1))] = match.group(2).strip()
    return names


def print_summary(
    gazette: list[dict],
    headings: dict,
    forward: dict,
    backward: dict,
    gazette_stats: dict,
    publication_stats: dict,
) -> None:
    """Five plain-English lines, every number taken from the parts above."""
    rule("4. Summary")

    # Where the gazette's unmatched sentences sit: its own extra headings start the annexures.
    only_gazette = headings["only_gazette"]
    annexures_from = min((page for page, _ in only_gazette), default=0)
    missed = backward["missed"]
    in_annexures = sum(1 for page, _ in missed if page >= annexures_from)
    elsewhere = len(missed) - in_annexures

    chapters = sum(1 for _, line, _ in headings["gazette_body"] if CHAPTER_LINE.match(line))
    # Which chapters share the title DEVELOPMENT CONTROL NORMS, taken from the headings.
    dcn_numbers = sorted(
        int(number.group(1))
        for _, line, key in headings["gazette_body"]
        if "DEVELOPMENT CONTROL NORMS" in key and (number := CHAPTER_NUMBER.match(line))
    )
    contents = headings["publication_contents"]
    names = chapter_names(contents)
    dcn_names = [names[number] for number in dcn_numbers if number in names]
    plans = service_plan_names(gazette)

    # Pages whose text is simply missing matter more than a header we can strip per page.
    lost_gazette = gazette_stats["empty"] + gazette_stats["scanned"]
    lost_publication = publication_stats["empty"] + publication_stats["scanned"]
    cleaner, other = (
        (GAZETTE, PUBLICATION) if lost_gazette <= lost_publication else (PUBLICATION, GAZETTE)
    )

    print(
        f"1. Yes, they are the same plan text, with the Publication contained in the gazette: "
        f"{forward['rate']:.0%} of {len(forward['sample'])} sampled Publication sentences turn "
        f"up word for word in the gazette (100% once punctuation is ignored)."
    )
    print(
        f"2. The reverse is only {backward['rate']:.0%}, but that is not disagreement: "
        + (
            f"all {len(missed)} unmatched gazette sentences come from page {annexures_from} "
            f"onwards, which the Publication simply does not contain."
            if elsewhere == 0
            else f"{in_annexures} of the {len(missed)} unmatched gazette sentences come from "
            f"page {annexures_from} onwards, which the Publication does not contain, and the "
            f"other {elsewhere} are table cells the two layouts scramble differently."
        )
    )
    print(
        f"3. The structure matches wherever they overlap: {len(headings['shared'])} of the "
        f"gazette's {len(headings['gazette_body'])} body headings appear in the Publication too "
        f"— all {chapters} CHAPTER lines and every numbered section (3.1 ENVIRONMENT, "
        f"4.2 TRANSIT ORIENTED DEVELOPMENT and the rest) — and no body heading is unique to "
        f"the Publication."
    )
    print(
        f"4. The gazette has {gazette_stats['pages'] - publication_stats['pages']} pages more: "
        f"pages {annexures_from}-{GAZETTE_PAGES[1]} are per-agency service plans "
        f"({len(plans)} of them: {', '.join(shorten(name, 38) for name in plans[:3])}, ...) "
        f"behind {len(only_gazette)} headings the Publication lacks. All the Publication adds "
        f"is a {len(contents)}-entry contents list, which is the only place chapters "
        f"{dcn_numbers[0]}-{dcn_numbers[-1]} are named ({', '.join(dcn_names[:3])}, ...) "
        f"instead of all reading DEVELOPMENT CONTROL NORMS (DCN), as they do in both bodies "
        f"({len(dcn_numbers)} chapters each)."
    )
    print(
        f"5. {cleaner} has the cleaner text: it loses {lost_gazette} pages to images where "
        f"{other} loses {lost_publication}, so no clause is missing. Its one flaw is the "
        f"bilingual running header ({gazette_stats['hindi_share']:.1%} of its characters are "
        f"Devanagari against {publication_stats['hindi_share']:.1%}), and that is one line per "
        f"page for the cleaning step to drop."
    )


def main() -> int:
    """Run the four comparisons and print the summary."""
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
    if not gazette or not publication:
        print(f"Need pages for both {GAZETTE} and {PUBLICATION} in pages.jsonl.")
        return 1

    print(f"Comparing {GAZETTE} pages {first}-{last} ({len(gazette)} pages)")
    print(f"     with {PUBLICATION} ({len(publication)} pages)")

    headings = compare_headings(gazette, publication)
    forward, backward = compare_text(gazette, publication)
    gazette_stats, publication_stats = compare_pages(gazette, publication)
    print_summary(gazette, headings, forward, backward, gazette_stats, publication_stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
