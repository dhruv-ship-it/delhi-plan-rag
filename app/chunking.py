"""Cut the cleaned documents into chunks a retriever can return and a reader can cite.

A chunk is one clause-sized piece of text with everything needed to cite it: the
document it came from, its chapter, the heading path above it, its clause number and
the page range it covers. The sizes are a compromise: small enough that a retrieved
chunk is mostly about one thing, big enough that a clause is not cut in half.

The gazette is the hard case. It is one continuous text across 505 pages with four
levels of numbered sections, tables in the middle of clauses, and back matter
(definitions, annexures, maps, nine service plans) that has no decimal numbering at
all. So each part of the gazette gets the sectioniser that fits it, chosen by page
range from data/chapter_map.json, and every part then goes through the same size rules.

The FAQ, the High Court order and the NGT report are small and are handled by their
own, shorter functions at the bottom.
"""

import re
from dataclasses import dataclass, field

from app.cleaning import Line, count_words, split_markdown_table

# --- size rules ----------------------------------------------------------------

#: What a chunk should weigh. Most chunks land here.
TARGET_MIN_WORDS = 150
TARGET_MAX_WORDS = 400
#: Under this a section is too thin to stand alone and is merged with its next sibling.
MERGE_UNDER_WORDS = 40
#: A chunk is never knowingly built above this, except where nothing can be split.
HARD_MAX_WORDS = 500
#: A single paragraph above this is split by sentences, because it has no other seam.
PARAGRAPH_MAX_WORDS = 650
#: How much text a sentence-split piece repeats from the piece before it.
SENTENCE_OVERLAP_WORDS = 40
#: Abbreviation lists have no structure worth keeping, so they are cut by size alone.
ABBREVIATION_CHUNK_WORDS = 300
#: A page of the Maps section with fewer words than this is a divider, not content.
MAPS_MIN_WORDS = 5

# --- the shapes we detect ------------------------------------------------------

#: "4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)", "4.2.1 Definitions", "7.3.2.1 Norms".
#: The title has to start with a capital and run no longer than 120 characters, which
#: is what keeps table cells and stray decimals ("3.50 80.50 0.05") out.
SECTION_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s+([A-Z].{0,119})$")
#: In the service plans there is no chapter number to check the first number against,
#: so no part of the number may run above this. Real headings there are numbered 1 to
#: 10 at both levels, while the stray table rows that look like headings are the
#: engineering measurements in the drainage tables ("5.90 Good NO NO RD-5900m to RD-0m").
SERVICE_PLAN_MAX_SECTION = 20
#: And a service-plan heading needs a title of at least this many characters, which
#: rules out a measurement column read as "19.7 RD".
SERVICE_PLAN_MIN_TITLE_CHARS = 4
#: "1. SERVICE PLAN – DELHI JAL BOARD (DJB)" starts one agency's plan. Matched
#: case-sensitively on purpose: the contents page on gazette page 994 lists the same
#: nine plans in title case ("1. Service Plan - Delhi Jal Board (DJB)"), and those
#: lines are a table of contents, not the start of a plan.
SERVICE_PLAN_HEADING = re.compile(r"^(\d{1,2})\.\s*SERVICE\s+PLAN\s*[-–—:]?\s*(.*)$")

#: "Annexure 21: Use Premises and Permissible Activities".
ANNEXURE_HEADING = re.compile(r"^Annexure\s*[-–]?\s*(\d{1,2}[a-z]?)\s*[:.]?\s*(.*)$", re.I)
#: "5a: Sub-City Level Wholesale Markets" — an annexure's own sub-heading.
ANNEXURE_SUB_HEADING = re.compile(r"^(\d{1,2}[a-z])\s*[:.]\s*(.+)$")

#: "Active frontage: A street stretch where ..." — one entry of the Definitions part.
DEFINITION_ENTRY = re.compile(r"^([A-Z][^:]{0,79}):\s+(\S.*)$")
#: The single capital letters that divide the Definitions part alphabetically.
ALPHABET_DIVIDER = re.compile(r"^[A-Z]$")

#: "Q12. Is any relaxation in ground coverage allowed ...", in MPD47_FAQ.
FAQ_QUESTION = re.compile(r"^Q\s*(\d{1,3})\s*[.)]\s*(.*)$")
#: "FAQs - GENERIC", "FAQs – Land Pooling Policy", "FAQs on High Density Corridor
#: (HDC) Policy". The document is inconsistent: seven sections use a dash and two use
#: the word "on", so both forms are matched.
FAQ_SECTION = re.compile(r"^FAQs?\s*(?:[-–—:]\s*|on\s+)(.+)$", re.I)
#: How long a line may be and still be read as the wrapped tail of a FAQ section title.
FAQ_SECTION_TAIL_CHARS = 60

#: "3. Learned counsel for the respondents admit that ..." — a numbered court paragraph.
NUMBERED_PARAGRAPH = re.compile(r"^(\d{1,3})\.\s+([A-Z\"“(].*)$")

#: Sub-items inside a clause: "(i)", "(ii)", "(a)", "(b)", "(1)". Used as split points
#: only when a section is too long to keep whole.
SUB_ITEM = re.compile(r"^\(\s*(?:x{0,3}(?:ix|iv|v?i{0,3})|[a-z]|\d{1,2})\s*\)\s*\S")
#: Anything that starts a new visual block, used when laying text out for display.
BLOCK_START = re.compile(
    r"^(?:[•▪◦‣·]\s*"
    r"|\(\s*(?:x{0,3}(?:ix|iv|v?i{0,3})|[a-z]|\d{1,2})\s*\)\s*"
    r"|\d{1,2}\.\s+[A-Z])"
)
#: A sentence end followed by the start of the next sentence.
SENTENCE_BREAK = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z(\"“])")


@dataclass(frozen=True)
class Heading:
    """One heading found in the text, and where it sits in the hierarchy."""

    level: int
    title: str
    clause_id: str | None
    parent_key: str


@dataclass
class Section:
    """A run of lines under one heading, before the size rules are applied."""

    clause_id: str | None
    clause_ids: list[str]
    heading_path: list[str]
    parent_key: str
    lines: list[Line] = field(default_factory=list)
    #: True when the section is its heading line and nothing else, so it has no clause
    #: text of its own. Set by `sectionise`, used by `fold_heading_only_sections`.
    heading_only: bool = False


# --- laying lines out as text --------------------------------------------------


def render(lines: list[Line]) -> str:
    """Join cleaned lines into display text: one paragraph per block, blank line between.

    Lines inside a paragraph are joined with a space, because the hard wrapping a PDF
    leaves behind is an artefact of the page width, not of the clause. Bullets, roman
    sub-items and numbered items each start their own paragraph, and a table keeps its
    own newlines.
    """
    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(" ".join(current))
            current.clear()

    for line in lines:
        if line.is_table:
            flush()
            paragraphs.append(line.text)
        elif not line.text:
            flush()
        elif current and BLOCK_START.match(line.text):
            flush()
            current.append(line.text)
        else:
            current.append(line.text)
    flush()
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph.strip())


def words_of(lines: list[Line]) -> int:
    """How many words a run of lines comes to once laid out."""
    return count_words(render(lines))


def page_span(lines: list[Line]) -> tuple[int, int]:
    """The first and last page a run of lines came from."""
    pages = [line.page for line in lines] + [line.page_end for line in lines]
    return min(pages), max(pages)


def _strip_edges(lines: list[Line]) -> list[Line]:
    """Drop blank lines from both ends of a run."""
    start, end = 0, len(lines)
    while start < end and not lines[start].text and not lines[start].is_table:
        start += 1
    while end > start and not lines[end - 1].text and not lines[end - 1].is_table:
        end -= 1
    return lines[start:end]


# --- splitting a run of lines into units ---------------------------------------


def units_at_blocks(lines: list[Line]) -> list[list[Line]]:
    """Split a run of lines at paragraph breaks and around tables."""
    units: list[list[Line]] = []
    current: list[Line] = []
    for line in lines:
        if line.is_table:
            if current:
                units.append(_strip_edges(current))
                current = []
            units.append([line])
        elif not line.text:
            if current:
                units.append(_strip_edges(current))
                current = []
        else:
            current.append(line)
    if current:
        units.append(_strip_edges(current))
    return [unit for unit in units if unit]


def units_at_sub_items(lines: list[Line]) -> list[list[Line]]:
    """Split a run of lines where a sub-item "(i)" or "(a)" starts, and around tables.

    Sub-items belong inside their clause, so this is only ever used on a section that
    is too long to keep in one chunk.
    """
    units: list[list[Line]] = []
    current: list[Line] = []
    for line in lines:
        starts_item = not line.is_table and bool(line.text) and bool(SUB_ITEM.match(line.text))
        if line.is_table or starts_item:
            if _strip_edges(current):
                units.append(_strip_edges(current))
            current = [line]
            if line.is_table:
                units.append([line])
                current = []
        else:
            current.append(line)
    if _strip_edges(current):
        units.append(_strip_edges(current))
    return [unit for unit in units if unit]


def split_by_sentences(lines: list[Line]) -> list[list[Line]]:
    """Cut one over-long paragraph into pieces at sentence ends, with a little overlap.

    Each piece repeats about `SENTENCE_OVERLAP_WORDS` words of the piece before it, so a
    sentence that happens to fall on a seam is still readable in one of them. The pieces
    are rebuilt as single lines, and every piece carries the whole paragraph's page
    range, because once the sentences are regrouped we no longer know which page each
    sentence sat on.
    """
    first_page, last_page = page_span(lines)
    sentences = [part for part in SENTENCE_BREAK.split(render(lines)) if part.strip()]
    pieces: list[list[Line]] = []
    current: list[str] = []
    for sentence in sentences:
        if current and count_words(" ".join(current)) + count_words(sentence) > TARGET_MAX_WORDS:
            pieces.append(current)
            tail: list[str] = []
            for earlier in reversed(current):
                if count_words(" ".join(tail)) >= SENTENCE_OVERLAP_WORDS:
                    break
                tail.insert(0, earlier)
            current = tail
        current.append(sentence)
    if current:
        pieces.append(current)
    return [
        [Line(" ".join(piece), first_page, last_page=last_page)] for piece in pieces if piece
    ]


def split_oversized_unit(unit: list[Line]) -> list[list[Line]]:
    """Break a single unit that is still too long: a table by rows, a paragraph by sentences."""
    if len(unit) == 1 and unit[0].is_table:
        markdown = unit[0].text
        body_rows = max(1, len(markdown.split("\n")) - 2)
        words_per_row = max(1, count_words(markdown) // body_rows)
        max_rows = max(1, TARGET_MAX_WORDS // words_per_row)
        return [
            [Line(piece, unit[0].page, is_table=True, last_page=unit[0].page_end)]
            for piece in split_markdown_table(markdown, max_rows)
        ]
    return split_by_sentences(unit)


def pack_units(units: list[list[Line]]) -> list[list[Line]]:
    """Fill chunks from units, aiming at 150-400 words and never knowingly over 500."""
    pieces: list[list[Line]] = []
    current: list[Line] = []
    current_words = 0
    for unit in units:
        unit_words = words_of(unit)
        if not current:
            current, current_words = list(unit), unit_words
            continue
        fits = current_words + unit_words <= TARGET_MAX_WORDS
        too_thin = current_words < TARGET_MIN_WORDS and current_words + unit_words <= HARD_MAX_WORDS
        if fits or too_thin:
            current = current + [Line("", unit[0].page)] + list(unit)
            current_words += unit_words
        else:
            pieces.append(current)
            current, current_words = list(unit), unit_words
    if current:
        pieces.append(current)
    return _absorb_scraps(pieces)


def _absorb_scraps(pieces: list[list[Line]]) -> list[list[Line]]:
    """Put a piece under 40 words back on the piece before it, where there is room.

    Splitting at sub-item boundaries can leave a scrap at the end: "(ii) The above
    activities shall be subject to clearances from ..." on its own is 12 words and
    means nothing without the list it closes. Both pieces came from one section, so
    joining them cannot mix clauses up.
    """
    out: list[list[Line]] = []
    for piece in pieces:
        if (
            out
            and words_of(piece) < MERGE_UNDER_WORDS
            and words_of(out[-1]) + words_of(piece) <= HARD_MAX_WORDS
        ):
            out[-1] = out[-1] + [Line("", piece[0].page)] + piece
            continue
        out.append(piece)
    return out


def split_section(lines: list[Line]) -> list[list[Line]]:
    """Apply the splitting rules to one section's lines. Returns one run per chunk."""
    lines = _strip_edges(lines)
    if not lines:
        return []
    if words_of(lines) <= HARD_MAX_WORDS:
        return [lines]

    units = units_at_sub_items(lines)
    if len(units) < 2:
        units = units_at_blocks(lines)

    expanded: list[list[Line]] = []
    for unit in units:
        if words_of(unit) <= HARD_MAX_WORDS:
            expanded.append(unit)
            continue
        inner = units_at_blocks(unit)
        if len(inner) < 2:
            expanded.extend(split_oversized_unit(unit))
            continue
        for part in inner:
            if words_of(part) <= PARAGRAPH_MAX_WORDS:
                expanded.append(part)
            else:
                expanded.extend(split_oversized_unit(part))
    return pack_units(expanded)


# --- the merge rule ------------------------------------------------------------


def merge_small_sections(sections: list[Section]) -> list[Section]:
    """Fold a section under 40 words into the next section with the same parent.

    A one-line heading with no body of its own ("4.2.3 TOD Norms" followed straight by
    "4.2.3.1 ...") is useless on its own in a search result, so it is carried into the
    text of what follows it. Both clause numbers are kept in `clause_ids` so a citation
    can still name either. Merging stops at 500 words and never crosses a parent, so
    two unrelated clauses are never glued together.
    """
    merged: list[Section] = []
    for section in sections:
        if merged:
            previous = merged[-1]
            small = words_of(previous.lines) < MERGE_UNDER_WORDS
            same_parent = previous.parent_key == section.parent_key
            room = words_of(previous.lines) + words_of(section.lines) <= HARD_MAX_WORDS
            if small and same_parent and room:
                previous.lines = previous.lines + [Line("", section.lines[0].page)] + section.lines
                previous.clause_ids = previous.clause_ids + [
                    cid for cid in section.clause_ids if cid not in previous.clause_ids
                ]
                if previous.clause_id is None:
                    previous.clause_id = section.clause_id
                if not previous.heading_path:
                    previous.heading_path = section.heading_path
                continue
        merged.append(section)
    return merged


# --- turning lines into sections ------------------------------------------------


def sectionise(
    lines: list[Line],
    detect,
    root_key: str,
) -> list[Section]:
    """Walk a run of lines and cut it where `detect` finds a heading.

    `detect(line)` returns a `Heading` or None. A heading closes the section before it
    and opens a new one, and the heading line itself stays at the top of the new
    section's text. Text before the first heading becomes a section of its own with no
    clause number, which is how a chapter's introduction survives.
    """
    sections: list[Section] = []
    stack: list[Heading] = []
    current = Section(clause_id=None, clause_ids=[], heading_path=[], parent_key=root_key)

    for line in lines:
        heading = None if line.is_table else detect(line)
        if heading is None:
            current.lines.append(line)
            continue
        if _strip_edges(current.lines):
            sections.append(current)
        while stack and stack[-1].level >= heading.level:
            stack.pop()
        stack.append(heading)
        current = Section(
            clause_id=heading.clause_id,
            clause_ids=[heading.clause_id] if heading.clause_id else [],
            heading_path=[item.title for item in stack],
            parent_key=heading.parent_key,
            lines=[line],
        )
    if _strip_edges(current.lines):
        sections.append(current)
    for section in sections:
        body = [line for line in section.lines if line.text or line.is_table]
        section.heading_only = len(body) <= 1 and bool(section.heading_path)
    return sections


def fold_heading_only_sections(sections: list[Section]) -> list[Section]:
    """Carry a heading that has no text of its own into the section below it.

    "11.1 Transportation" sits on its own line with nothing under it but "11.1.1",
    "11.1.2" and so on. On its own that is a two-word chunk that can be retrieved and
    says nothing, so it is folded into the first section that does have text, and both
    clause numbers are kept. This is a different case from `merge_small_sections`,
    which joins siblings: here the heading is folded into its own child, which already
    names it in `heading_path`. Folding stops at 500 words and never crosses into
    another top-level number.
    """
    out: list[Section] = []
    carried: list[Section] = []

    for section in sections:
        if carried:
            if _can_fold_into(carried, section):
                extra: list[Line] = []
                ids: list[str] = []
                for held in carried:
                    extra += held.lines + [Line("", section.lines[0].page)]
                    ids += held.clause_ids
                section.lines = extra + section.lines
                section.clause_ids = list(
                    dict.fromkeys(ids + section.clause_ids)
                )
                if section.clause_id is None and ids:
                    section.clause_id = ids[-1]
                carried = []
            else:
                out.extend(carried)
                carried = []
        if section.heading_only:
            carried.append(section)
        else:
            out.append(section)
    out.extend(carried)
    return out


def _can_fold_into(carried: list[Section], section: Section) -> bool:
    """May the carried heading-only sections be folded into this one?

    There is no size limit here, unlike `merge_small_sections`. A heading belongs to
    the text under it, so folding cannot glue two unrelated clauses together, and
    whatever comes out is put through the splitting rules straight afterwards.
    """
    last = carried[-1]
    if last.clause_id and section.clause_id:
        return last.clause_id.split(".")[0] == section.clause_id.split(".")[0]
    return last.parent_key == section.parent_key


def parent_of(number: str) -> str:
    """The clause number one level up: "4.2.1" -> "4.2", "4.1" -> "4"."""
    parts = number.split(".")
    return ".".join(parts[:-1]) if len(parts) > 1 else number


def numbered_heading(line: Line, chapter_of_page) -> Heading | None:
    """Detect a decimal section heading, checked against the chapter it sits in.

    Inside chapters 1-13 the first number must equal the chapter number, so a table
    cell like "3.50 80.50" in chapter 11 cannot pass as a heading. In the service plans
    there is no chapter number to check against, so the first number is capped instead.
    """
    match = SECTION_HEADING.match(line.text)
    if not match:
        return None
    number, title = match.group(1), match.group(2).strip()
    chapter = chapter_of_page(line.page)
    first = int(number.split(".")[0])
    if isinstance(chapter, int):
        if first != chapter:
            return None
    elif (
        number.count(".") > 2
        or len(title) < SERVICE_PLAN_MIN_TITLE_CHARS
        or any(int(part) > SERVICE_PLAN_MAX_SECTION for part in number.split("."))
    ):
        return None
    return Heading(
        level=number.count(".") + 1,
        title=f"{number} {title}",
        clause_id=number,
        parent_key=parent_of(number),
    )


# --- the gazette ----------------------------------------------------------------


def chunk_numbered_chapters(lines: list[Line], chapter_of_page) -> list[Section]:
    """Chapters 1-13: decimal section headings, with sub-items kept inside their clause."""

    def detect(line: Line) -> Heading | None:
        return numbered_heading(line, chapter_of_page)

    first_page = lines[0].page if lines else 0
    root = str(chapter_of_page(first_page))
    sections = fold_heading_only_sections(sectionise(lines, detect, root_key=root))
    return merge_small_sections(sections)


def chunk_service_plans(lines: list[Line], chapter_of_page) -> list[Section]:
    """The nine agency service plans: an agency heading, then their own numbered headings."""

    def detect(line: Line) -> Heading | None:
        agency = SERVICE_PLAN_HEADING.match(line.text)
        if agency and len(line.text) <= 130:
            return Heading(
                level=1,
                title=line.text,
                clause_id=None,
                parent_key=f"service_plan_{agency.group(1)}",
            )
        heading = numbered_heading(line, chapter_of_page)
        if heading is None:
            return None
        return Heading(
            level=heading.level + 1,
            title=heading.title,
            clause_id=heading.clause_id,
            parent_key=heading.parent_key,
        )

    sections = fold_heading_only_sections(sectionise(lines, detect, root_key="service_plans"))
    return merge_small_sections(sections)


def chunk_annexures(lines: list[Line]) -> list[Section]:
    """The annexures: split at "Annexure N" and at each annexure's own sub-headings."""

    def detect(line: Line) -> Heading | None:
        annexure = ANNEXURE_HEADING.match(line.text)
        if annexure:
            number = annexure.group(1)
            return Heading(
                level=1,
                title=line.text,
                clause_id=f"Annexure {number}",
                parent_key="annexures",
            )
        sub = ANNEXURE_SUB_HEADING.match(line.text)
        if sub and len(line.text) <= 120:
            number = sub.group(1)
            return Heading(
                level=2,
                title=line.text,
                clause_id=f"Annexure {number}",
                parent_key=f"Annexure {number[:-1]}",
            )
        return None

    sections = fold_heading_only_sections(sectionise(lines, detect, root_key="annexures"))
    return merge_small_sections(sections)


def chunk_definitions(lines: list[Line]) -> list[Section]:
    """The Definitions part: one chunk per definition, with short ones grouped together.

    The alphabetical divider lines ("A", "B") are dropped. A group is flushed once it
    reaches the target minimum, so a long definition stands alone and a run of
    one-liners travels together.
    """
    entries: list[tuple[str, list[Line]]] = []
    for line in lines:
        if not line.is_table and ALPHABET_DIVIDER.match(line.text):
            continue
        match = None if line.is_table else DEFINITION_ENTRY.match(line.text)
        if match:
            entries.append((match.group(1).strip(), [line]))
        elif entries:
            entries[-1][1].append(line)
        elif line.text or line.is_table:
            entries.append(("", [line]))

    sections: list[Section] = []
    group: list[Line] = []
    terms: list[str] = []
    for term, body in entries:
        if group:
            group.append(Line("", body[0].page))
        group.extend(body)
        if term:
            terms.append(term)
        if words_of(group) >= TARGET_MIN_WORDS:
            sections.append(_definition_section(group, terms))
            group, terms = [], []
    if _strip_edges(group):
        sections.append(_definition_section(group, terms))
    return sections


def _definition_section(group: list[Line], terms: list[str]) -> Section:
    """One Definitions chunk, named after the terms it holds."""
    if len(terms) == 1:
        label = terms[0]
    elif terms:
        label = f"{terms[0]} - {terms[-1]}"
    else:
        label = "Definitions"
    return Section(
        clause_id=None,
        clause_ids=[],
        heading_path=[label],
        parent_key="definitions",
        lines=list(group),
    )


def chunk_by_size(
    lines: list[Line], heading_path: list[str], parent_key: str, size: int
) -> list[Section]:
    """Cut a run of lines into chunks of about `size` words, at paragraph breaks.

    Used for the parts that have no structure worth keeping: the abbreviations list,
    the preamble's paragraphs and the list of maps.
    """
    sections: list[Section] = []
    current: list[Line] = []
    for unit in units_at_blocks(lines):
        if current and words_of(current) + words_of(unit) > size:
            sections.append(
                Section(None, [], list(heading_path), parent_key, lines=list(current))
            )
            current = []
        if current:
            current.append(Line("", unit[0].page))
        current.extend(unit)
    if _strip_edges(current):
        sections.append(Section(None, [], list(heading_path), parent_key, lines=list(current)))
    return sections


def chunk_preamble(lines: list[Line]) -> list[Section]:
    """The S.O. notification and the plan's opening paragraphs, grouped by size."""
    return chunk_by_size(lines, ["Notification preamble"], "preamble", TARGET_MAX_WORDS)


def chunk_abbreviations(lines: list[Line]) -> list[Section]:
    """The abbreviations list, cut into chunks of about 300 words."""
    return chunk_by_size(lines, ["Abbreviations"], "abbreviations", ABBREVIATION_CHUNK_WORDS)


def chunk_maps(lines: list[Line]) -> list[Section]:
    """The Maps part: captions only. Pages with no text of their own are skipped."""
    by_page: dict[int, list[Line]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)
    kept = [
        line
        for page in sorted(by_page)
        for line in by_page[page]
        if words_of(by_page[page]) >= MAPS_MIN_WORDS
    ]
    return chunk_by_size(kept, ["Maps"], "maps", TARGET_MAX_WORDS)


#: Which sectioniser each chapter_map label gets. Integers are chapters 1-13.
GAZETTE_PART_ORDER = (
    "preamble",
    "chapters",
    "abbreviations",
    "definitions",
    "annexures",
    "maps",
    "service_plans",
)


def chunk_gazette(lines: list[Line], chapter_of_page) -> list[Section]:
    """Chunk the whole gazette, giving each part of it the rules that fit.

    Chapters 1-13 are chunked as one continuous stream so a clause that runs over a
    chapter's last page is not cut; every other part is chunked on its own.
    """
    parts: dict[str, list[Line]] = {name: [] for name in GAZETTE_PART_ORDER}
    for line in lines:
        chapter = chapter_of_page(line.page)
        key = "chapters" if isinstance(chapter, int) else str(chapter)
        parts.setdefault(key, []).append(line)

    sections: list[Section] = []
    sections += chunk_preamble(parts["preamble"])
    sections += chunk_numbered_chapters(parts["chapters"], chapter_of_page)
    sections += chunk_abbreviations(parts["abbreviations"])
    sections += chunk_definitions(parts["definitions"])
    sections += chunk_annexures(parts["annexures"])
    sections += chunk_maps(parts["maps"])
    sections += chunk_service_plans(parts["service_plans"], chapter_of_page)
    return sections


# --- the FAQ --------------------------------------------------------------------


def chunk_faq(lines: list[Line]) -> list[Section]:
    """MPD47_FAQ: one chunk per question, with its answer and its section heading.

    Question numbers restart in every section ("Q1." appears nine times), so the
    clause id is not unique on its own; `app.chunking.assign_chunk_ids` disambiguates.
    """
    sections: list[Section] = []
    heading = "FAQs"
    current: Section | None = None
    expect_tail = False

    for line in lines:
        if line.is_table:
            if current:
                current.lines.append(line)
            continue
        section_match = FAQ_SECTION.match(line.text)
        question = FAQ_QUESTION.match(line.text)
        if section_match and not question:
            heading = line.text
            expect_tail = True
            continue
        if expect_tail:
            expect_tail = False
            if (
                line.text
                and not question
                and len(line.text) <= FAQ_SECTION_TAIL_CHARS
                and not line.text.endswith(".")
            ):
                heading = f"{heading} {line.text}"
                continue
        if question:
            if current:
                sections.append(current)
            number = f"Q{question.group(1)}"
            current = Section(
                clause_id=number,
                clause_ids=[number],
                heading_path=[heading, f"{number}. {question.group(2).strip()}"],
                parent_key=heading,
                lines=[line],
            )
            continue
        if current:
            current.lines.append(line)
    if current:
        sections.append(current)
    return [section for section in sections if _strip_edges(section.lines)]


# --- the court order and the NGT report -----------------------------------------


def chunk_paragraph_document(lines: list[Line], label: str) -> list[Section]:
    """DHC_YAMUNA_20240708 and NGT_OA572_GNCTD_REPORT: paragraphs of 150-400 words.

    Where the document numbers its paragraphs, the number becomes the clause id; where
    it does not (cover pages, index, annexed tables), the clause id stays empty.
    """

    def detect(line: Line) -> Heading | None:
        match = NUMBERED_PARAGRAPH.match(line.text)
        if not match:
            return None
        number = match.group(1)
        return Heading(level=1, title=f"{number}.", clause_id=number, parent_key=label)

    sections = merge_small_sections(sectionise(lines, detect, root_key=label))
    out: list[Section] = []
    for section in sections:
        if section.clause_id is None:
            out.extend(chunk_by_size(section.lines, [label], label, TARGET_MAX_WORDS))
        else:
            out.append(section)
    return out


# --- chunk ids ------------------------------------------------------------------


def assign_chunk_ids(doc_id: str, pieces: list[tuple[str | None, int]]) -> list[str]:
    """Build a deterministic id for every chunk of one document.

    The shape is "<doc_id>:<clause id>:<piece number>", for example
    "MPD47_GAZETTE_EN:4.2.1:0". A chunk with no clause number uses its first page
    instead ("MPD47_GAZETTE_EN:p640:0"). Clause numbers are not unique everywhere —
    the FAQ restarts at Q1 in every section and the nine service plans each start at
    1.1 — so any id that would repeat gets its page appended, and a counter after that.
    """
    bases = [
        f"{doc_id}:{clause_id if clause_id else f'p{page_start}'}"
        for clause_id, page_start in pieces
    ]
    pages_per_base: dict[str, set[int]] = {}
    for base, (_, page_start) in zip(bases, pieces):
        pages_per_base.setdefault(base, set()).add(page_start)

    ids: list[str] = []
    per_prefix: dict[str, int] = {}
    used: set[str] = set()
    for base, (_, page_start) in zip(bases, pieces):
        prefix = base if len(pages_per_base[base]) == 1 else f"{base}@p{page_start}"
        index = per_prefix.get(prefix, 0)
        per_prefix[prefix] = index + 1
        chunk_id = f"{prefix}:{index}"
        while chunk_id in used:
            chunk_id = f"{chunk_id}+"
        used.add(chunk_id)
        ids.append(chunk_id)
    return ids
