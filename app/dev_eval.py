"""The question verification screen's logic: list, inspect, check and save a decision.

Verifying the 60 drafted questions is the one job on this project that cannot be
delegated to the thing being measured (D-054). It is also three hours of reading JSONL
in an editor, cross-referencing chunk ids with `show_chunk.py`, and re-running a leakage
check by hand — which is how a necessary task becomes one that does not get done.

So the work gets a screen. This module is everything behind it that is worth testing on
its own: reading the drafts, pairing each one with its expected chunk text and the
current top 5 from hybrid+location, running the leakage check on a rewritten question,
and writing a decision into `eval/questions_verified.jsonl` without touching the draft
file.

Three rules this module enforces, and the reasons they are rules:

**The draft file is never written.** `scripts/09_draft_questions.py` owns it and
regenerates it; a verified question is a different record in a different file, so the
record of what was generated survives and re-running the drafter cannot destroy an
evening's work.

**`verified: true` is only ever set by a decision from the screen.** Not by this module
on its own, not by the drafter, not by the remapper (D-067). It is the one field that
means a person looked.

**The leakage check runs on the rewritten text, not the original.** Rewriting the
question in your own words is the step that makes the question independent of the corpus
(D-055), and it is also the step most likely to accidentally quote the clause that is
open on screen beside it.

The HTTP endpoints that expose this are in `app/api.py` under `/api/dev/eval/`, and they
return 404 unless `ZONEWISE_DEV=1` (D-075). Nothing here checks that flag: a module that
reads and writes evaluation files is not a security boundary, and pretending otherwise
would put the check in two places and the authority in neither.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings

#: A question may not share a run of this many words with a chunk it points at. Four,
#: because three is a phrase anybody might write ("the ground coverage") and four is a
#: quotation (D-055).
LEAKAGE_RUN = 4

#: What counts as a word for the leakage check: letters and digits, case-folded.
WORD = re.compile(r"[a-z0-9]+")

#: How many retrieval results the screen shows per question.
TOP_K = 5

#: The statuses a decision may carry.
ACCEPTED = "accepted"
EDITED = "edited"
REJECTED = "rejected"
SKIPPED = "skipped"
DECISION_STATUSES = (ACCEPTED, EDITED, REJECTED, SKIPPED)

#: Which statuses mean the question goes into the verified file.
KEPT_STATUSES = (ACCEPTED, EDITED)


class DevEvalError(RuntimeError):
    """Raised for a decision that cannot be saved, with a message for the screen."""


@dataclass
class Decision:
    """One verification decision, as the screen sends it."""

    id: str
    status: str
    question: str = ""
    expected_chunk_ids: list[str] = field(default_factory=list)
    acceptable_chunk_ids: list[str] = field(default_factory=list)
    should_abstain: bool = False
    notes: str = ""


# --- the files ------------------------------------------------------------------


def drafts_path() -> Path:
    """Where the drafted questions live. Read only, as far as this module is concerned."""
    return settings.project_root / "eval" / "questions_draft.jsonl"


def verified_path() -> Path:
    """Where verified questions are written, one line per question."""
    return settings.project_root / "eval" / "questions_verified.jsonl"


def points_path() -> Path:
    """The named points, so the screen can show the question's point on a map."""
    return settings.project_root / "eval" / "points.json"


def shown_path(path: Path) -> str:
    """A path to print back to the screen: relative to the repo when it is inside it.

    `relative_to` raises for a path outside the root, which a test's tmp folder always
    is — and so is a repo checked out somewhere the settings do not expect. A message
    saying where a file was written must not be able to fail.
    """
    try:
        return path.relative_to(settings.project_root).as_posix()
    except ValueError:
        return path.as_posix()


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file, or return [] when it does not exist yet."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as JSONL, one object per line, newline-terminated."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_points() -> dict[str, dict]:
    """The named points, keyed by name."""
    if not points_path().exists():
        return {}
    return {
        point["name"]: point
        for point in json.loads(points_path().read_text(encoding="utf-8"))
    }


# --- the leakage check ----------------------------------------------------------


def words_of(text: str) -> list[str]:
    """The words of a piece of text, lower case, punctuation dropped."""
    return WORD.findall(text.lower())


def ngrams(words: list[str], size: int) -> set[tuple[str, ...]]:
    """Every run of `size` consecutive words."""
    if size <= 0 or len(words) < size:
        return set()
    return {tuple(words[index : index + size]) for index in range(len(words) - size + 1)}


def leakage(question: str, chunk_texts: list[str], size: int = LEAKAGE_RUN) -> list[str]:
    """Runs of `size` words the question shares with any chunk it points at.

    An empty list is a pass. A question that quotes its own answer tests nothing: BM25
    finds it by string overlap and the score then says the retriever works when all it
    has shown is that two pieces of text share a phrase (D-055).
    """
    asked = ngrams(words_of(question), size)
    if not asked:
        return []
    shared: set[tuple[str, ...]] = set()
    for text in chunk_texts:
        shared |= asked & ngrams(words_of(text), size)
    return sorted(" ".join(run) for run in shared)


# --- listing and inspecting -----------------------------------------------------


def progress(drafts: list[dict], verified: list[dict]) -> dict:
    """How much of the verification is done, for the counter on the screen."""
    by_id = {record["id"]: record for record in verified}
    return {
        "total": len(drafts),
        "done": sum(1 for record in drafts if record["id"] in by_id),
        "accepted": sum(1 for record in verified if record.get("status") == ACCEPTED),
        "edited": sum(1 for record in verified if record.get("status") == EDITED),
        "rejected": sum(1 for record in verified if record.get("status") == REJECTED),
    }


def question_list() -> dict:
    """Every drafted question with its verification status, in draft order."""
    drafts = read_jsonl(drafts_path())
    verified = {record["id"]: record for record in read_jsonl(verified_path())}
    items = []
    for record in drafts:
        decided = verified.get(record["id"])
        items.append(
            {
                "id": record["id"],
                "category": record["category"],
                "point_name": record.get("point_name"),
                "question": (decided or record)["question"],
                "should_abstain": bool((decided or record).get("should_abstain")),
                "status": (decided or {}).get("status", "pending"),
                "verified": bool((decided or {}).get("verified")),
            }
        )
    return {
        "questions": items,
        "progress": progress(drafts, read_jsonl(verified_path())),
    }


def chunk_summary(chunk: dict, text: str | None = None) -> dict:
    """One chunk as the screen shows it: where it is, and its text in full."""
    return {
        "chunk_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "clause_id": chunk.get("clause_id") or None,
        "heading_path": list(chunk.get("heading_path") or []),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "zone_primary": chunk.get("zone_primary") or "",
        "n_words": chunk.get("n_words"),
        "text": chunk["text"] if text is None else text,
    }


def question_detail(question_id: str, index, searcher=None) -> dict:
    """One question, its point, its expected chunks in full, and the current top 5.

    `index` and `searcher` are passed in rather than imported so a test can drive this
    with a stub and no Chroma store. The default searcher is the real location-aware
    hybrid search, which is the configuration the evaluation reports and therefore the
    one whose results are worth looking at while deciding what the answer should be.
    """
    drafts = {record["id"]: record for record in read_jsonl(drafts_path())}
    if question_id not in drafts:
        raise DevEvalError(f"no drafted question with id {question_id!r}")
    draft = drafts[question_id]
    decided = {record["id"]: record for record in read_jsonl(verified_path())}.get(question_id)
    current = decided or draft

    point = load_points().get(draft.get("point_name") or "")
    zones = point["zones"] if point else None

    if searcher is None:
        from app.retrieval import search as real_search

        def searcher(query, zones):  # noqa: ANN001 - a local default, not an API
            return real_search(query, k=TOP_K, mode="hybrid", zones=zones, index=index)

    results = searcher(current["question"], zones)
    expected = [
        chunk_summary(index.chunks[chunk_id])
        for chunk_id in current.get("expected_chunk_ids") or []
        if chunk_id in index.chunks
    ]
    acceptable = [
        chunk_summary(index.chunks[chunk_id])
        for chunk_id in current.get("acceptable_chunk_ids") or []
        if chunk_id in index.chunks
    ]
    wanted = {chunk["chunk_id"] for chunk in expected} | {
        chunk["chunk_id"] for chunk in acceptable
    }

    return {
        "id": question_id,
        "category": draft["category"],
        "point_name": draft.get("point_name"),
        "lat": draft.get("lat"),
        "lon": draft.get("lon"),
        "zones": zones,
        "question": current["question"],
        "draft_question": draft["question"],
        "expected_answer_short": draft.get("expected_answer_short", ""),
        "expected_chunk_ids": list(current.get("expected_chunk_ids") or []),
        "acceptable_chunk_ids": list(current.get("acceptable_chunk_ids") or []),
        "should_abstain": bool(current.get("should_abstain")),
        "notes": current.get("notes", "") or "",
        "status": (decided or {}).get("status", "pending"),
        "expected_chunks": expected,
        "acceptable_chunks": acceptable,
        "top_results": [
            chunk_summary(index.chunks[result.chunk_id])
            | {
                "rank": position,
                "fused_score": result.fused_score,
                "dense_cosine": result.dense_cosine,
                "is_expected": result.chunk_id in wanted,
            }
            for position, result in enumerate(results, start=1)
            if result.chunk_id in index.chunks
        ],
        "leakage": leakage(
            current["question"],
            [chunk["text"] for chunk in expected + acceptable],
        ),
    }


def check_leakage(question_id: str, text: str, index) -> dict:
    """The leakage check for a rewritten question, against its own chunks.

    This is what the screen calls while someone is typing, so it must not search: it
    reads the question's current expected and acceptable chunks out of the index and
    compares word runs, which is pure string work.
    """
    drafts = {record["id"]: record for record in read_jsonl(drafts_path())}
    decided = {record["id"]: record for record in read_jsonl(verified_path())}
    current = decided.get(question_id) or drafts.get(question_id)
    if current is None:
        raise DevEvalError(f"no question with id {question_id!r}")

    chunk_ids = list(current.get("expected_chunk_ids") or []) + list(
        current.get("acceptable_chunk_ids") or []
    )
    texts = [index.chunks[chunk_id]["text"] for chunk_id in chunk_ids if chunk_id in index.chunks]
    shared = leakage(text, texts)
    return {
        "id": question_id,
        "question": text,
        "run_length": LEAKAGE_RUN,
        "chunks_checked": len(texts),
        "shared_word_runs": shared,
        "ok": not shared,
    }


# --- saving a decision ----------------------------------------------------------


def validate(decision: Decision, index) -> None:
    """Raise `DevEvalError` when a decision cannot be saved, with a readable reason.

    The checks are the ones `scripts/09_draft_questions.py` enforces on its own output
    (D-055), because a question edited by hand deserves the same guards as a generated
    one — more so, since nothing else will look at it again.
    """
    if decision.status not in DECISION_STATUSES:
        raise DevEvalError(
            f"status must be one of {', '.join(DECISION_STATUSES)}, not {decision.status!r}"
        )
    if decision.status not in KEPT_STATUSES:
        return

    if not decision.question.strip():
        raise DevEvalError("an accepted question needs some text")

    unknown = [
        chunk_id
        for chunk_id in decision.expected_chunk_ids + decision.acceptable_chunk_ids
        if chunk_id not in index.chunks
    ]
    if unknown:
        raise DevEvalError(f"these chunk ids are not in the index: {', '.join(unknown)}")

    if decision.should_abstain:
        if decision.expected_chunk_ids:
            raise DevEvalError(
                "a should-abstain question has no expected chunks: the point is that the "
                "documents do not answer it"
            )
        return

    if not 1 <= len(decision.expected_chunk_ids) <= 3:
        raise DevEvalError(
            f"an answerable question needs 1 to 3 expected chunk ids, got "
            f"{len(decision.expected_chunk_ids)}"
        )

    texts = [
        index.chunks[chunk_id]["text"]
        for chunk_id in decision.expected_chunk_ids + decision.acceptable_chunk_ids
    ]
    shared = leakage(decision.question, texts)
    if shared:
        raise DevEvalError(
            "the question shares a run of "
            f"{LEAKAGE_RUN} or more words with a chunk it points at: "
            + "; ".join(f"'{run}'" for run in shared)
        )


def save_decision(decision: Decision, index) -> dict:
    """Write one decision into the verified file, replacing any earlier one for that id.

    Returns the record as saved, or, for a rejected or skipped question, the bookkeeping
    record. **An accepted or edited question is written with `verified: true`**; a
    rejected one is written with `verified: false` and kept, because "I looked at this
    and it is not a good question" is a result worth recording — without it, a rejected
    question is indistinguishable from one nobody reached.
    """
    drafts = {record["id"]: record for record in read_jsonl(drafts_path())}
    if decision.id not in drafts:
        raise DevEvalError(f"no drafted question with id {decision.id!r}")
    validate(decision, index)

    draft = drafts[decision.id]
    kept = decision.status in KEPT_STATUSES
    record = {
        "id": decision.id,
        "question": decision.question.strip() if kept else draft["question"],
        "point_name": draft.get("point_name"),
        "category": draft["category"],
        "expected_chunk_ids": list(decision.expected_chunk_ids) if kept else [],
        "acceptable_chunk_ids": list(decision.acceptable_chunk_ids) if kept else [],
        "expected_answer_short": draft.get("expected_answer_short", ""),
        "should_abstain": bool(decision.should_abstain),
        "verified": kept,
        "status": decision.status,
        "drafted_by": draft.get("drafted_by", "claude_code"),
        "verified_by": "dhruv" if kept else None,
        "notes": decision.notes.strip(),
        "lat": draft.get("lat"),
        "lon": draft.get("lon"),
    }

    existing = read_jsonl(verified_path())
    replaced = False
    for position, stored in enumerate(existing):
        if stored["id"] == decision.id:
            existing[position] = record
            replaced = True
            break
    if not replaced:
        existing.append(record)
    write_jsonl(verified_path(), existing)

    return {
        "saved": record,
        "replaced": replaced,
        "progress": progress(read_jsonl(drafts_path()), existing),
        "path": shown_path(verified_path()),
    }
