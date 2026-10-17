"""Check `chunks.jsonl` for the damage that PDF extraction and chunking leave behind.

Every retrieval score in this project is capped by chunk quality. A clause cut in half
cannot be cited; a table whose header was lost says nothing about what its numbers mean;
a running header left in the text adds the word "GAZETTE" to a third of the corpus and
tells BM25 nothing. None of that shows up in a recall number — it shows up as an answer
that reads oddly, which is much harder to notice.

So the checks here are deliberately mechanical and each one names the lines it objected
to, so a person can read five examples and decide whether it is a real defect or the
document simply being like that. Three of them are the second kind by design:

  * A chunk in the abbreviations chapter ends without a full stop because it is a list
    of abbreviations, not prose.
  * A norms table's text is 25% alphabetic because it is numbers, which is the point.
  * A chunk starting "(ii) Economy:" is a whole list item, not a sentence cut in half,
    so a leading list marker is stripped before the mid-sentence test.

`CHECKS` is the list, in report order. Each check returns a `Finding` per chunk it
objects to, and `audit_chunks` runs them all and counts.
"""

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass

#: How many examples of each problem a report shows.
EXAMPLES = 5

#: Chunks shorter or longer than the chunking rules intend (D-020).
MIN_WORDS = 40
MAX_WORDS = 500

#: Below this share of alphabetic characters a chunk is mostly numbers or table noise.
MIN_ALPHA_SHARE = 0.40

#: Two chunks in the same document whose normalised text is this similar are near-copies.
NEAR_DUPLICATE_RATIO = 0.95
#: Comparing every pair is quadratic, so pairs whose lengths differ by more than this
#: are skipped — they cannot reach the ratio above anyway.
LENGTH_TOLERANCE = 0.10

#: The gazette's chapters of plan text. A clause in one of these should have a number.
NUMBERED_CHAPTERS = range(1, 14)
GAZETTE_DOC_ID = "MPD47_GAZETTE_EN"

#: Chapters whose chunks are lists by nature, so an unterminated last line is correct.
LIST_CHAPTERS = {"abbreviations", "maps"}

#: A line that opens a list item: "(ii)", "a.", "3.", "-", "•".
LIST_MARKER = re.compile(r"^\s*(?:[-*•]|\(?[a-zA-Z0-9]{1,4}[).])\s+")

#: Words that can only continue a sentence, never start one.
CONTINUATION_WORDS = frozenset(
    {
        "and",
        "or",
        "but",
        "however",
        "therefore",
        "thus",
        "also",
        "moreover",
        "furthermore",
        "whereas",
        "thereof",
        "therein",
        "thereby",
        "hence",
        "besides",
        "nevertheless",
    }
)

#: What a finished sentence, quotation or bracket ends with.
TERMINAL_CHARACTERS = ".!?:;”’\")"

#: Running-header text that should never survive cleaning (D-016).
RUNNING_HEADER = re.compile(r"GAZETTE\s+OF\s+INDIA|राजपत्र|PART\s+II—SEC|PART\s+II\b")
#: Any Devanagari character, which the gazette's English range should not contain.
DEVANAGARI = re.compile(r"[ऀ-ॿ]")

#: Leftover divider text: an all-capitals fragment of a PART or CHAPTER title.
DIVIDER_LEFTOVER = re.compile(
    r"(?:^|\n)\s*(?:&\s+)?(?:FOR\s+)?[A-Z][A-Z &,–—()./-]{8,}\s*$"
)


@dataclass(frozen=True)
class Finding:
    """One chunk that failed one check, with the evidence that made it fail."""

    chunk_id: str
    detail: str


@dataclass(frozen=True)
class Check:
    """One named check over the whole chunk list."""

    key: str
    title: str
    note: str
    run: Callable[[list[dict]], list[Finding]]


# --- helpers -------------------------------------------------------------------


def normalised(text: str) -> str:
    """Text reduced to lower-case letters, digits and single spaces, for comparison."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def alpha_share(text: str) -> float:
    """Share of a chunk's non-space characters that are letters."""
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return 0.0
    return sum(1 for char in visible if char.isalpha()) / len(visible)


def first_word(text: str) -> str:
    """The first word of a chunk, with any list marker and opening quote removed.

    "(ii) Economy: Delhi is one of ..." gives "Economy:", not "ii)", because a list
    item is a whole thought and not a sentence cut in half.
    """
    body = LIST_MARKER.sub("", text.strip(), count=1).lstrip("“‘\"'([{")
    words = body.split()
    return words[0] if words else ""


def is_list_chunk(chunk: dict) -> bool:
    """True when this chunk is a list or a table, so an unterminated end is correct."""
    if chunk.get("has_table"):
        return True
    if chunk.get("chapter") in LIST_CHAPTERS:
        return True
    last = chunk["text"].rstrip().split("\n")[-1].strip()
    return last.startswith("|") or bool(LIST_MARKER.match(last))


def table_blocks(text: str) -> list[list[str]]:
    """Every run of consecutive markdown table rows in a chunk."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip().startswith("|"):
            current.append(line.strip())
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


# --- the checks ----------------------------------------------------------------


def starts_mid_sentence(chunks: list[dict]) -> list[Finding]:
    """Chunks whose first word can only be the middle of a sentence."""
    found = []
    for chunk in chunks:
        word = first_word(chunk["text"])
        if not word:
            continue
        if word[:1].islower() or word.lower() in CONTINUATION_WORDS:
            found.append(Finding(chunk["chunk_id"], chunk["text"][:120].replace("\n", " ")))
    return found


def ends_mid_sentence(chunks: list[dict]) -> list[Finding]:
    """Chunks whose text stops without terminal punctuation, excluding tables and lists."""
    found = []
    for chunk in chunks:
        text = chunk["text"].rstrip()
        if not text or is_list_chunk(chunk):
            continue
        if not text.endswith(tuple(TERMINAL_CHARACTERS)):
            found.append(Finding(chunk["chunk_id"], "..." + text[-120:].replace("\n", " / ")))
    return found


def broken_tables(chunks: list[dict]) -> list[Finding]:
    """Markdown tables with ragged rows, an empty header, or no separator row."""
    found = []
    for chunk in chunks:
        for position, block in enumerate(table_blocks(chunk["text"])):
            widths = {line.count("|") - 1 for line in block}
            header_cells = [cell.strip() for cell in block[0].strip("|").split("|")]
            problems = []
            if len(widths) > 1:
                problems.append(f"column counts {sorted(widths)}")
            if not any(header_cells):
                problems.append("empty header")
            if len(block) < 2 or not re.match(r"^\|\s*-{2,}", block[1]):
                problems.append("no separator row")
            if problems:
                found.append(
                    Finding(
                        chunk["chunk_id"],
                        f"table {position}: {', '.join(problems)} — {block[0][:70]}",
                    )
                )
    return found


def leftover_page_furniture(chunks: list[dict]) -> list[Finding]:
    """Running headers, Devanagari or all-capitals divider fragments left in the text."""
    found = []
    for chunk in chunks:
        text = chunk["text"]
        problems = []
        header = RUNNING_HEADER.search(text)
        if header:
            problems.append(f"running header {header.group(0)!r}")
        hindi = DEVANAGARI.search(text)
        if hindi and chunk["doc_id"] == GAZETTE_DOC_ID:
            problems.append(f"Devanagari {hindi.group(0)!r}")
        divider = DIVIDER_LEFTOVER.search(text)
        if divider and not chunk.get("has_table"):
            problems.append(f"divider text {divider.group(0).strip()!r}")
        if problems:
            found.append(Finding(chunk["chunk_id"], "; ".join(problems)))
    return found


def duplicate_chunks(chunks: list[dict]) -> list[Finding]:
    """Chunks in the same document whose normalised text is identical or near-identical.

    Exact copies are reported first. Near copies use difflib on the normalised text,
    which is why pairs whose lengths differ by more than 10% are skipped: the ratio
    cannot reach 0.95 across that gap, and skipping them keeps the pass quadratic in
    each length band rather than in the whole document.
    """
    found: list[Finding] = []
    by_document: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_document.setdefault(chunk["doc_id"], []).append(chunk)

    for doc_id, items in sorted(by_document.items()):
        keys = [(chunk["chunk_id"], normalised(chunk["text"])) for chunk in items]
        seen: dict[str, str] = {}
        remaining: list[tuple[str, str]] = []
        for chunk_id, key in keys:
            if key in seen:
                found.append(Finding(chunk_id, f"exact copy of {seen[key]} in {doc_id}"))
                continue
            seen[key] = chunk_id
            remaining.append((chunk_id, key))
        for index, (chunk_id, key) in enumerate(remaining):
            for other_id, other in remaining[index + 1 :]:
                longest = max(len(key), len(other), 1)
                if abs(len(key) - len(other)) / longest > LENGTH_TOLERANCE:
                    continue
                ratio = difflib.SequenceMatcher(None, key, other).ratio()
                if ratio > NEAR_DUPLICATE_RATIO:
                    found.append(Finding(chunk_id, f"{ratio:.3f} similar to {other_id}"))
    return found


def missing_clause_ids(chunks: list[dict]) -> list[Finding]:
    """Gazette chunks in chapters 1 to 13 with no clause number.

    Those chapters are the plan's own numbered text, so a chunk there without a number
    is a chunk a citation cannot point at precisely.
    """
    found = []
    for chunk in chunks:
        if chunk["doc_id"] != GAZETTE_DOC_ID or not chunk["chapter"].isdigit():
            continue
        if int(chunk["chapter"]) not in NUMBERED_CHAPTERS:
            continue
        if not chunk.get("clause_id"):
            found.append(
                Finding(chunk["chunk_id"], f"chapter {chunk['chapter']}, page {chunk['page_start']}")
            )
    return found


def wrong_size(chunks: list[dict]) -> list[Finding]:
    """Chunks under 40 words or over 500, the bounds the chunking rules set (D-020)."""
    found = []
    for chunk in chunks:
        words = chunk["n_words"]
        if words < MIN_WORDS:
            found.append(Finding(chunk["chunk_id"], f"{words} words (under {MIN_WORDS})"))
        elif words > MAX_WORDS:
            found.append(Finding(chunk["chunk_id"], f"{words} words (over {MAX_WORDS})"))
    return found


def mostly_not_text(chunks: list[dict]) -> list[Finding]:
    """Chunks under 40% alphabetic: numbers, table noise or extraction debris."""
    found = []
    for chunk in chunks:
        share = alpha_share(chunk["text"])
        if share < MIN_ALPHA_SHARE:
            kind = "table" if chunk.get("has_table") else "no table"
            found.append(Finding(chunk["chunk_id"], f"{share:.0%} alphabetic, {kind}"))
    return found


CHECKS: tuple[Check, ...] = (
    Check(
        "starts_mid_sentence",
        "Chunks that start mid-sentence",
        "The first word is lower case or can only continue a sentence. A leading list "
        'marker is stripped first, so "(ii) Economy: ..." is not counted.',
        starts_mid_sentence,
    ),
    Check(
        "ends_mid_sentence",
        "Chunks that end mid-sentence",
        "No terminal punctuation at the end. Tables, list items and the abbreviations "
        "chapter are excluded, because those are not prose and end without a full stop.",
        ends_mid_sentence,
    ),
    Check(
        "broken_tables",
        "Broken markdown tables",
        "Rows with inconsistent column counts, an entirely empty header row, or a "
        "missing separator row.",
        broken_tables,
    ),
    Check(
        "leftover_page_furniture",
        "Leftover running headers and divider text",
        'The gazette\'s running header, Devanagari inside the English range, or an '
        "all-capitals fragment of a PART or CHAPTER divider title.",
        leftover_page_furniture,
    ),
    Check(
        "duplicate_chunks",
        "Duplicate and near-duplicate chunks",
        "Identical normalised text, or over 0.95 similar, within the same document.",
        duplicate_chunks,
    ),
    Check(
        "missing_clause_ids",
        "Gazette chunks in chapters 1-13 with no clause id",
        "A chunk in the plan's own numbered chapters that a citation cannot point at "
        "by clause number.",
        missing_clause_ids,
    ),
    Check(
        "wrong_size",
        "Chunks under 40 or over 500 words",
        "The bounds the chunking rules set (D-020). Under 40 words should have been "
        "merged; over 500 should have been split.",
        wrong_size,
    ),
    Check(
        "mostly_not_text",
        "Chunks dominated by numbers or table noise",
        "Under 40% of the non-space characters are letters. A norms table is expected "
        "to appear here; a chunk without a table is not.",
        mostly_not_text,
    ),
)


def audit_chunks(chunks: list[dict]) -> dict[str, list[Finding]]:
    """Run every check and return its findings, keyed by check name, in report order."""
    return {check.key: check.run(chunks) for check in CHECKS}


def counts(results: dict[str, list[Finding]]) -> dict[str, int]:
    """How many chunks each check objected to."""
    return {key: len(findings) for key, findings in results.items()}


# --- remapping chunk ids after a re-chunk --------------------------------------

#: Below this word overlap a new chunk is not the same text as the old one, and a
#: question pointing at the old id is reported rather than silently re-pointed.
REMAP_MIN_OVERLAP = 0.50


def word_set(text: str) -> set[str]:
    """The distinct words of a chunk, normalised, for measuring overlap."""
    return set(normalised(text).split())


def overlap(old: str, new: str) -> float:
    """How much of the old chunk's wording the new chunk still contains, 0 to 1.

    Asymmetric on purpose: the question was written about the old chunk's content, so
    what matters is whether the new chunk still *says* that, not whether it says only
    that. A new chunk that absorbed its neighbour is still the right target; a new
    chunk holding half the old text is not.
    """
    old_words = word_set(old)
    if not old_words:
        return 0.0
    return len(old_words & word_set(new)) / len(old_words)


def best_overlap_match(old_text: str, candidates: dict[str, str]) -> tuple[str, float]:
    """The candidate chunk id whose text best covers `old_text`, and the overlap.

    Returns ("", 0.0) when nothing clears `REMAP_MIN_OVERLAP`. Ties go to the id that
    sorts first, so a re-run produces the same answer.
    """
    best_id, best_score = "", 0.0
    for chunk_id in sorted(candidates):
        score = overlap(old_text, candidates[chunk_id])
        if score > best_score:
            best_id, best_score = chunk_id, score
    if best_score < REMAP_MIN_OVERLAP:
        return "", best_score
    return best_id, best_score
