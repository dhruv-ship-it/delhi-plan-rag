"""Look at the extracted text of one page, or find a phrase across pages.

Run with: uv run python scripts/show_page.py MPD47_FAQ 3
          uv run python scripts/show_page.py MPD47_GAZETTE_EN --find "floor area ratio"
          uv run python scripts/show_page.py ALL --find "land pooling"

Reads data/processed/pages.jsonl, so run scripts/02_extract.py first.
"""

import argparse
import re
import sys

from app.config import settings
from app.extract import read_pages_jsonl, use_utf8_output

SNIPPET_WIDTH = 80
MAX_HITS = 15


def parse_args() -> argparse.Namespace:
    """Read the command line options."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("doc_id", help="a doc_id from sources.csv, or ALL to search everything")
    parser.add_argument("page", nargs="?", type=int, help="a 1-based page number to print")
    parser.add_argument("--find", metavar="PHRASE", help="list pages holding this phrase")
    args = parser.parse_args()
    if (args.page is None) == (args.find is None):
        parser.error("give either a page number or --find \"phrase\", not both")
    return args


def snippet(text: str, start: int, end: int) -> str:
    """One line of about 80 characters around a hit, with the spacing squeezed out."""
    padding = max(SNIPPET_WIDTH - (end - start), 0) // 2
    left = max(0, start - padding)
    right = min(len(text), end + padding)
    body = re.sub(r"\s+", " ", text[left:right]).strip()
    return f"{'...' if left > 0 else ''}{body}{'...' if right < len(text) else ''}"


def print_page(pages: list[dict], doc_id: str, number: int) -> int:
    """Print one page's text under a header line. Returns an exit code."""
    wanted = [page for page in pages if page["doc_id"] == doc_id and page["page"] == number]
    if not wanted:
        in_doc = [page["page"] for page in pages if page["doc_id"] == doc_id]
        if not in_doc:
            print(f"No pages for {doc_id} in pages.jsonl.")
            return 1
        print(f"No page {number} for {doc_id}. Pages {min(in_doc)}-{max(in_doc)} are available.")
        return 1

    page = wanted[0]
    flags = []
    if page["likely_scanned"]:
        flags.append("looks scanned")
    if page["devanagari_ratio"] > 0.3:
        flags.append(f"{page['devanagari_ratio']:.0%} Devanagari")
    tables = page["n_tables"]
    extra = f" | {', '.join(flags)}" if flags else ""
    print(
        f"=== {doc_id} page {page['page']} | {page['n_chars']} chars | "
        f"{page['n_words']} words | {page['n_images']} images | "
        f"{'?' if tables is None else tables} tables{extra} ==="
    )
    print(page["text"] if page["text"].strip() else "(no text on this page)")
    return 0


def print_hits(pages: list[dict], doc_id: str, phrase: str) -> int:
    """List pages containing a phrase, with a snippet around each hit."""
    chosen = pages if doc_id == "ALL" else [page for page in pages if page["doc_id"] == doc_id]
    if not chosen:
        print(f"No pages for {doc_id} in pages.jsonl.")
        return 1

    needle = phrase.lower()
    shown = 0
    pages_hit = 0
    total = 0
    for page in chosen:
        haystack = page["text"].lower()
        starts = []
        at = haystack.find(needle)
        while at != -1:
            starts.append(at)
            at = haystack.find(needle, at + len(needle))
        if not starts:
            continue
        pages_hit += 1
        total += len(starts)
        for start in starts:
            if shown >= MAX_HITS:
                continue
            print(f"{page['doc_id']} p.{page['page']}: {snippet(page['text'], start, start + len(phrase))}")
            shown += 1

    if not total:
        print(f'No page contains "{phrase}" in {doc_id}.')
        return 1
    print()
    print(
        f'"{phrase}": {total} hit(s) on {pages_hit} page(s)'
        + (f", showing the first {MAX_HITS}." if total > MAX_HITS else ".")
    )
    return 0


def main() -> int:
    """Print a page or search for a phrase in data/processed/pages.jsonl."""
    use_utf8_output()
    args = parse_args()
    path = settings.processed_dir / "pages.jsonl"
    if not path.exists():
        print(f"{path.as_posix()} is missing. Run: uv run python scripts/02_extract.py")
        return 1

    pages = read_pages_jsonl(path)
    if args.find is not None:
        return print_hits(pages, args.doc_id, args.find)
    return print_page(pages, args.doc_id, args.page)


if __name__ == "__main__":
    sys.exit(main())
