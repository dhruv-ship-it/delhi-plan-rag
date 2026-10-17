"""Audit data/processed/chunks.jsonl for extraction and chunking damage.

    uv run python scripts/audit_chunks.py
    uv run python scripts/audit_chunks.py --out reports/chunk_audit_after.md
    uv run python scripts/audit_chunks.py --compare reports/chunk_audit_before.md

Writes a Markdown report with a count and up to five examples per check, and prints the
counts. With `--compare` it reads the counts out of an earlier report and adds a
before/after table at the top, so the effect of a fix is one table rather than two files
to diff by eye.

Safe to re-run: it only reads chunks.jsonl and writes the one report.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit import CHECKS, EXAMPLES, audit_chunks, counts  # noqa: E402
from app.config import settings  # noqa: E402

#: How the counts are written into the report, so --compare can read them back.
COUNT_LINE = re.compile(r"^\| `(?P<key>[a-z_]+)` \| (?P<count>\d+) \|")

#: The findings this corpus produces that are the documents being what they are, not
#: defects. Printed in every report so a reader can tell them from the rest (D-066).
KNOWN_CAUSES = """## Findings that are the corpus, not a defect

Four causes account for nearly everything the checks still report, and none of them is
fixed by changing the chunking rules.

**The FAQ is one question per chunk**, so 45 of its 99 chunks are under 40 words. A
24-word question and its answer is a complete thought, and merging two unrelated
questions to reach 40 words would make retrieval worse, not better.

**The norms tables really are mostly numbers.** Every chunk under 40% alphabetic
carries a table: FAR and ground coverage by plot size, drain buffer widths in metres.
That is the content, and `has_table` is in the report line so it can be checked.

**The NGT status report is a scan**, and PyMuPDF reads a scan as approximately the
right words. Signature blocks, distribution lists and stamp text come through as
fragments that end without punctuation. Only the punctuation-only lines are stripped,
because any wider rule would start deleting real text from the gazette as well.

**Nine service-plan drainage tables defeated table detection** and came through as rows
of loose numbers, which is why a few chunks there end mid-row. `chunk_report.md` counts
them as tables that fell back to plain text.

One real cause is left and is deliberately not fixed: a table title at the very end of
a *section* cannot be moved onto the table it introduces, because the table is in the
next section and moving text across a section boundary would re-attribute it to a
different clause. `_move_orphan_titles` handles the case inside one section; this one is
recorded instead (D-066).
"""


def read_chunks(path: Path) -> list[dict]:
    """Read chunks.jsonl into a list of records."""
    if not path.exists():
        raise SystemExit(
            f"{path.as_posix()} is missing. Run: uv run python scripts/03_chunk.py"
        )
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def previous_counts(path: Path) -> dict[str, int]:
    """Read the per-check counts out of an earlier report, or {} when there is none."""
    if not path or not path.exists():
        return {}
    found: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = COUNT_LINE.match(line)
        if match:
            found[match.group("key")] = int(match.group("count"))
    return found


def comparison_table(before: dict[str, int], after: dict[str, int]) -> list[str]:
    """A before/after table, with the change and its direction."""
    lines = [
        "## Before and after",
        "",
        "| check | before | after | change |",
        "| --- | --- | --- | --- |",
    ]
    for check in CHECKS:
        was = before.get(check.key)
        now = after.get(check.key, 0)
        if was is None:
            lines.append(f"| `{check.key}` | — | {now} | new check |")
            continue
        delta = now - was
        arrow = "no change" if delta == 0 else f"{delta:+d}"
        lines.append(f"| `{check.key}` | {was} | {now} | {arrow} |")
    lines.append("")
    return lines


def report(chunks: list[dict], results: dict, compare: Path | None) -> str:
    """Build the whole Markdown report."""
    found = counts(results)
    total_words = sum(chunk["n_words"] for chunk in chunks)
    lines = [
        "# Chunk quality audit",
        "",
        f"`data/processed/chunks.jsonl`: **{len(chunks)} chunks**, "
        f"{total_words:,} words, {total_words // max(len(chunks), 1)} words a chunk on average.",
        "",
        "Every check below is mechanical and some of them are meant to fire: a norms "
        "table really is mostly numbers, and an abbreviations entry really does end "
        "without a full stop. The examples are there so a person can tell a defect from "
        "a document simply being like that.",
        "",
    ]

    if compare is not None:
        before = previous_counts(compare)
        if before:
            lines += comparison_table(before, found)
        else:
            lines += [f"> No counts found in `{compare.as_posix()}`, so no comparison.", ""]

    lines += [KNOWN_CAUSES, "", "## Counts", "", "| check | chunks | share |", "| --- | --- | --- |"]
    for check in CHECKS:
        number = found[check.key]
        share = number / len(chunks) if chunks else 0.0
        lines.append(f"| `{check.key}` | {number} | {share:.1%} |")
    lines.append("")

    for check in CHECKS:
        findings = results[check.key]
        lines += [f"## {check.title}", "", check.note, "", f"**{len(findings)} chunks.**", ""]
        if not findings:
            lines += ["None.", ""]
            continue
        for finding in findings[:EXAMPLES]:
            lines.append(f"- `{finding.chunk_id}` — {finding.detail}")
        if len(findings) > EXAMPLES:
            lines.append(f"- ... and {len(findings) - EXAMPLES} more")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    """Run the audit and write the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(settings.reports_dir / "chunk_audit_before.md"),
        help="where to write the Markdown report",
    )
    parser.add_argument(
        "--compare",
        default=None,
        help="an earlier report to read counts from, for a before/after table",
    )
    args = parser.parse_args()

    chunks = read_chunks(settings.processed_dir / "chunks.jsonl")
    results = audit_chunks(chunks)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    compare = Path(args.compare) if args.compare else None
    out.write_text(report(chunks, results, compare), encoding="utf-8")

    found = counts(results)
    print(f"Audited {len(chunks)} chunks from data/processed/chunks.jsonl")
    for check in CHECKS:
        print(f"  {found[check.key]:5d}  {check.key}")
    flagged = sum(found.values())
    print(f"\n{flagged} finding(s) in total; up to {EXAMPLES} examples each.")
    print(f"Report: {out.as_posix()}")


if __name__ == "__main__":
    main()
