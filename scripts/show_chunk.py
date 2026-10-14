"""Print one chunk in full, with everything known about it.

    uv run python scripts/show_chunk.py MPD47_GAZETTE_EN:4.2.1:0
    uv run python scripts/show_chunk.py MPD47_FAQ:Q13@p13:0 --json

This is the tool for verifying an evaluation question: open the chunk its answer is
supposed to come from and check that it really says what the question expects. See
eval/README.md for the whole procedure.

Takes a partial id too, so you do not have to remember the piece number:

    uv run python scripts/show_chunk.py 4.2.1

Run with: uv run python scripts/show_chunk.py CHUNK_ID
"""

import argparse
import json
import sys

from app.config import settings
from app.extract import use_utf8_output
from app.indexing import read_chunks


def find_matches(chunks: list[dict], wanted: str) -> list[dict]:
    """Chunks whose id matches exactly, or failing that, contains the text given."""
    exact = [chunk for chunk in chunks if chunk["chunk_id"] == wanted]
    if exact:
        return exact
    lowered = wanted.lower()
    return [chunk for chunk in chunks if lowered in chunk["chunk_id"].lower()]


def describe(chunk: dict) -> str:
    """One chunk laid out for reading."""
    lines = [
        "=" * 78,
        chunk["chunk_id"],
        "=" * 78,
        f"document    {chunk['doc_title']}",
        f"            {chunk['doc_id']} | {chunk['doc_type']} | "
        f"authority rank {chunk['authority_rank']}"
        + (f" | {chunk['doc_date']}" if chunk["doc_date"] else ""),
        f"chapter     {chunk['chapter'] or '(none)'}"
        + (f" — {chunk['chapter_title']}" if chunk["chapter_title"] else ""),
        f"heading     {' › '.join(chunk['heading_path']) or '(none)'}",
        f"clause      {chunk['clause_id'] or '(none)'}"
        + (
            f"   (all: {', '.join(chunk['clause_ids'])})"
            if len(chunk["clause_ids"]) > 1
            else ""
        ),
        f"pages       {chunk['page_start']}-{chunk['page_end']}",
        f"size        {chunk['n_words']} words"
        + ("   contains a table" if chunk["has_table"] else ""),
        f"zones       primary: {chunk.get('zone_primary') or '(none)'}   "
        f"mentions: {', '.join(chunk.get('zone_mentions', [])) or '(none)'}",
        f"source      {chunk['source_url']}",
        "-" * 78,
        "",
        chunk["text"],
        "",
        "-" * 78,
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Find the chunk and print it."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Print one chunk in full.")
    parser.add_argument("chunk_id", help="the chunk id, or any part of one")
    parser.add_argument("--json", action="store_true", help="print the raw record instead")
    parser.add_argument(
        "--limit", type=int, default=8, help="how many matches to print for a partial id"
    )
    args = parser.parse_args(argv)

    path = settings.processed_dir / "chunks.jsonl"
    if not path.exists():
        print(f"{path.as_posix()} is missing. Run: uv run python scripts/03_chunk.py")
        return 1

    chunks = read_chunks(path)
    matches = find_matches(chunks, args.chunk_id)

    if not matches:
        print(f"No chunk matches {args.chunk_id!r}. {len(chunks)} chunks are indexed.")
        print("Try a clause number (4.2.1), a doc id (MPD47_FAQ) or a page (p753).")
        return 1

    if args.json:
        for chunk in matches[: args.limit]:
            print(json.dumps(chunk, ensure_ascii=False, indent=2))
        return 0

    if len(matches) > 1:
        print(f"{len(matches)} chunks match {args.chunk_id!r}:")
        for chunk in matches[: args.limit]:
            print(
                f"  {chunk['chunk_id']:<46} {chunk['n_words']:>4}w  "
                f"pp{chunk['page_start']}-{chunk['page_end']}  "
                f"{' › '.join(chunk['heading_path'])[:60]}"
            )
        if len(matches) > args.limit:
            print(f"  (+{len(matches) - args.limit} more)")
        print()

    for chunk in matches[: args.limit]:
        print(describe(chunk))
    return 0


if __name__ == "__main__":
    sys.exit(main())
