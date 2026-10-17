"""Re-point the drafted questions' chunk ids after the chunks have been rebuilt.

    uv run python scripts/remap_eval_ids.py --old-chunks <path to the previous chunks.jsonl>
    uv run python scripts/remap_eval_ids.py --old-chunks <path> --dry-run

A chunk id encodes where the chunk starts (`MPD47_GAZETTE_EN:4.2.3@p753:0`), so any
change to the cleaning or chunking rules can move it. `eval/questions_draft.jsonl`
points at chunk ids, and a question whose expected id no longer exists scores zero
against every configuration — which looks like a retrieval failure and is not one.

So each referenced id is looked up in the *old* chunks, and the new chunk whose text
best covers that old text takes its place. Matching is by word overlap rather than by
id, because the id is the thing that moved. An id that cannot be matched above 50%
overlap is left alone and its question is flagged `notes="remap_failed"`, because a
wrong expected id is worse than a missing one: it would quietly measure the wrong thing.

**This script never touches a question's text, its category or its `should_abstain`
flag, and never sets `verified`.** Verification is a person's job (D-054); this is id
maintenance.

Safe to re-run: with the same old chunks it reaches the same answer, and an id that is
already correct maps to itself.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audit import REMAP_MIN_OVERLAP, best_overlap_match, overlap  # noqa: E402
from app.config import settings  # noqa: E402

#: The note put on a question whose expected id could not be matched.
FAILED_NOTE = "remap_failed"

#: Which fields hold chunk ids.
ID_FIELDS = ("expected_chunk_ids", "acceptable_chunk_ids")


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of records."""
    if not path.exists():
        raise SystemExit(f"{path.as_posix()} is missing.")
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records back as JSONL, one object per line."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def add_note(record: dict, note: str) -> None:
    """Append a note to a question without losing the note already there."""
    existing = (record.get("notes") or "").strip()
    if note in existing:
        return
    record["notes"] = f"{existing} {note}".strip() if existing else note


def remap(
    questions: list[dict], old_text: dict[str, str], new_text: dict[str, str]
) -> tuple[list[dict], list[dict]]:
    """Re-point every chunk id. Returns (one row per id considered, failed questions).

    An id still present in the new chunks is checked rather than trusted: the text
    behind it may have changed, and if it no longer covers the old text the id is
    re-matched like any other.
    """
    log: list[dict] = []
    failed: list[dict] = []
    for question in questions:
        question_failed = False
        for field in ID_FIELDS:
            updated: list[str] = []
            for chunk_id in question.get(field) or []:
                before = old_text.get(chunk_id)
                if before is None:
                    log.append(
                        {
                            "question": question["id"],
                            "field": field,
                            "old_id": chunk_id,
                            "new_id": chunk_id,
                            "overlap": None,
                            "outcome": "not in the old chunks, left alone",
                        }
                    )
                    updated.append(chunk_id)
                    continue
                if chunk_id in new_text and overlap(before, new_text[chunk_id]) >= REMAP_MIN_OVERLAP:
                    log.append(
                        {
                            "question": question["id"],
                            "field": field,
                            "old_id": chunk_id,
                            "new_id": chunk_id,
                            "overlap": round(overlap(before, new_text[chunk_id]), 3),
                            "outcome": "unchanged",
                        }
                    )
                    updated.append(chunk_id)
                    continue
                matched, score = best_overlap_match(before, new_text)
                if not matched:
                    log.append(
                        {
                            "question": question["id"],
                            "field": field,
                            "old_id": chunk_id,
                            "new_id": None,
                            "overlap": round(score, 3),
                            "outcome": "FAILED, best overlap below the threshold",
                        }
                    )
                    updated.append(chunk_id)
                    question_failed = True
                    continue
                log.append(
                    {
                        "question": question["id"],
                        "field": field,
                        "old_id": chunk_id,
                        "new_id": matched,
                        "overlap": round(score, 3),
                        "outcome": "remapped",
                    }
                )
                updated.append(matched)
            if field in question:
                question[field] = list(dict.fromkeys(updated))
        if question_failed:
            add_note(question, FAILED_NOTE)
            failed.append(question)
    return log, failed


def main() -> None:
    """Remap the ids and print what changed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--old-chunks", required=True, help="the chunks.jsonl the questions were written against"
    )
    parser.add_argument(
        "--questions",
        default=str(settings.project_root / "eval" / "questions_draft.jsonl"),
        help="the question file to re-point",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the log, write nothing")
    args = parser.parse_args()

    old = read_jsonl(Path(args.old_chunks))
    new = read_jsonl(settings.processed_dir / "chunks.jsonl")
    old_text = {chunk["chunk_id"]: chunk["text"] for chunk in old}
    new_text = {chunk["chunk_id"]: chunk["text"] for chunk in new}

    questions_path = Path(args.questions)
    questions = read_jsonl(questions_path)
    log, failed = remap(questions, old_text, new_text)

    changed = [row for row in log if row["outcome"] == "remapped"]
    broken = [row for row in log if row["outcome"].startswith("FAILED")]

    print(f"old chunks: {len(old)}   new chunks: {len(new)}")
    print(f"questions: {len(questions)}   chunk ids considered: {len(log)}")
    print(f"  unchanged: {sum(1 for row in log if row['outcome'] == 'unchanged')}")
    print(f"  remapped:  {len(changed)}")
    print(f"  failed:    {len(broken)}  (questions flagged {FAILED_NOTE}: {len(failed)})")
    for row in changed:
        print(f"    {row['question']:8s} {row['field']:22s} {row['old_id']} -> {row['new_id']}  ({row['overlap']})")
    for row in broken:
        print(f"    {row['question']:8s} {row['field']:22s} {row['old_id']} -> NO MATCH (best {row['overlap']})")

    if args.dry_run:
        print("\nDry run: nothing written.")
        return

    write_jsonl(questions_path, questions)
    log_path = questions_path.parent / "remap_log.json"
    log_path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {questions_path.as_posix()}")
    print(f"wrote {log_path.as_posix()}")


if __name__ == "__main__":
    main()
