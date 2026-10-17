"""Turn raw page text into clean lines that remember which page they came from.

`pages.jsonl` holds page text exactly as PyMuPDF read it (see D-007): the gazette's
bilingual running header on every page, bare page numbers, figure captions and the
double spaces that justified text leaves behind. This module strips all of that and
hands the chunker one list of `Line` records, each carrying its own page number so a
chunk that crosses a page break still knows its first and last page.

Tables are handled here too, because a table has to be pulled out of the page before
the text around it can be read in order. `page_lines_from_pdf()` reads a page's tables
with PyMuPDF, turns each into a markdown table, and takes the text between them with
`get_text(clip=...)` so no sentence appears twice.

Two of the rules exist because a page is a printing unit and not a unit of meaning.
`clean_text_lines` drops the all-capitals continuation lines of a PART or CHAPTER
divider title, which are the second and third lines of a divider page and otherwise end
up glued to the last clause of the previous chapter (D-066). `join_pages` is the other
half: a sentence that runs over a page break is joined instead of being split by the
paragraph break that a page boundary would otherwise insert.

Nothing in here knows about clauses or chunk sizes; that is app/chunking.py.
"""

import re
from dataclasses import dataclass

import pymupdf

# --- what a cleaned page is made of --------------------------------------------


@dataclass(frozen=True)
class Line:
    """One line of cleaned text, and the 1-based PDF page it was printed on.

    An empty `text` is a paragraph break, kept because the chunker splits on them.
    A line with `is_table` holds a whole markdown table, newlines and all.
    `last_page` is set only when the chunker rebuilds a line out of several pages'
    worth of text, so the page range it reports stays honest.
    """

    text: str
    page: int
    is_table: bool = False
    last_page: int | None = None

    @property
    def page_end(self) -> int:
        """The last page this line's text came from."""
        return self.last_page if self.last_page is not None else self.page


# --- the patterns we strip -----------------------------------------------------

#: Zero-width joiners and marks. The gazette's Hindi header is full of them.
ZERO_WIDTH = re.compile(r"[​-‏⁠﻿]")

DEVANAGARI_FIRST = "ऀ"
DEVANAGARI_LAST = "ॿ"
#: Above this share of Devanagari characters a line counts as Hindi (matches D-011).
HINDI_LINE_RATIO = 0.3

#: "750 THE GAZETTE OF INDIA : EXTRAORDINARY [PART II—SEC. 3(ii)]" — the page number
#: sits inside the header, so matching is digit-insensitive: we look for the wording.
GAZETTE_HEADER_EN = re.compile(r"THE\s+GAZETTE\s+OF\s+INDIA", re.I)
#: "[भाग II—खण्ड 3(ii)] भारत का राजपत्र : असाधारण 649" — the Hindi form of the same line.
GAZETTE_HEADER_HI = re.compile(r"भारत\s*का\s*राजपत्र|भाग\s*II|असाधारण")

#: A line that is nothing but a page number.
PAGE_NUMBER_LINE = re.compile(r"^\d{1,4}$")

#: Figure and map captions, which say nothing a clause can be cited for.
FIGURE_CAPTION = re.compile(r"^(?:Illustration|Map|Figure|Fig\.?|Table)\s*\d+\s*[:.]", re.I)
ILLUSTRATIVE_NOTE = re.compile(r"^\(?\s*for\s+illustrative\s+purposes?\s+only\s*\.?\)?$", re.I)

#: "CHAPTER 4. SPATIAL DEVELOPMENT POLICIES" and "PART I: BACKGROUND" divider lines.
#: The chapter is already known from data/chapter_map.json, so the line adds nothing.
DIVIDER_LINE = re.compile(r"^(?:CHAPTER\s+\d{1,2}\b|PART\s+[IVX]+\s*[:.])", re.I)

#: The characters a divider title is printed with: capitals, digits and light
#: punctuation. A continuation line has to be made only of these, which is what
#: keeps the rule from reaching ordinary text (D-066).
DIVIDER_CONTINUATION = re.compile(r"^[A-Z0-9 &,:;.()–—/'\"-]+$")
#: A divider title spread over more lines than this is not a divider title.
DIVIDER_CONTINUATION_MAX_WORDS = 10
#: A line that names itself: "4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)", "Annexure 9:".
#: A numbered heading can follow a divider line on the same page and is never part of
#: the divider's title, so it is excluded from the continuation rule.
NUMBERED_OR_NAMED_HEADING = re.compile(r"^(?:\d|Annexure)", re.I)

#: A line with no letter and no digit anywhere: a rule of dashes, a stray bracket,
#: the punctuation debris an OCR pass leaves behind on a scanned page.
PUNCTUATION_ONLY = re.compile(r"^[^\w]+$")

#: A word broken across a line end: "compact mixed-" / "use development".
HYPHEN_BREAK = re.compile(r"(\w)-$")
LOWERCASE_START = re.compile(r"^[a-z]")


def strip_zero_width(text: str) -> str:
    """Remove zero-width joiners and byte-order marks."""
    return ZERO_WIDTH.sub("", text)


def normalise_spaces(text: str) -> str:
    """Collapse runs of spaces and tabs into one space, and trim the ends.

    Justified gazette text is padded with extra spaces inside lines
    ("Kartavya  Path  development"), which would otherwise reach the index.
    """
    return " ".join(text.split())


def devanagari_share(text: str) -> float:
    """Share of a line's non-space characters that are Devanagari (the Hindi script)."""
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return 0.0
    hindi = sum(1 for char in visible if DEVANAGARI_FIRST <= char <= DEVANAGARI_LAST)
    return hindi / len(visible)


def is_gazette_header(line: str) -> bool:
    """True for the gazette's running header, in either language, on any page."""
    return bool(GAZETTE_HEADER_EN.search(line) or GAZETTE_HEADER_HI.search(line))


def is_mostly_hindi(line: str) -> bool:
    """True when more than 30% of a line's characters are Devanagari."""
    return devanagari_share(line) > HINDI_LINE_RATIO


def is_droppable(line: str, drop_hindi: bool) -> bool:
    """True for a line that carries no clause text.

    A running header, a bare page number, a figure caption, a PART or CHAPTER divider,
    a line of pure punctuation, and — inside the gazette's English range — a line of
    Hindi. The punctuation-only rule is the narrowest one that still catches the
    debris an OCR pass leaves on the scanned court documents, such as a rule of dashes
    or a stray bracket on its own line (D-066).
    """
    if not line:
        return False  # a blank line is a paragraph break, not noise
    if is_gazette_header(line) or PAGE_NUMBER_LINE.match(line):
        return True
    if FIGURE_CAPTION.match(line) or ILLUSTRATIVE_NOTE.match(line):
        return True
    if DIVIDER_LINE.match(line):
        return True
    if PUNCTUATION_ONLY.match(line):
        return True
    return drop_hindi and is_mostly_hindi(line)


def is_capitals(line: str) -> bool:
    """True when every letter in the line is a capital. Blank or letterless lines are not."""
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def starts_divider_block(line: str) -> bool:
    """True for a divider line printed in capitals, which is a real divider page title.

    The distinction matters. "PART I: BACKGROUND" on page 649 is a divider page and the
    lines under it are the rest of its title. "Part I: Background" on page 647 is a
    contents entry in the middle of 384 words of prose, and the lines under *it* are
    text. Only the capitalised form opens a divider block (D-066).
    """
    return bool(DIVIDER_LINE.match(line)) and is_capitals(line)


def continues_divider_title(line: str) -> bool:
    """True for a line that can only be the rest of a divider title.

    "FOR RESIDENTIAL" under "CHAPTER 7. DEVELOPMENT CONTROL NORMS (DCN)", and
    "& DEVELOPMENT FRAMEWORK" under "PART II: VISION, STRATEGIES, SPATIAL POLICIES".
    Capitals only, short, and no sentence-ending punctuation, so a capitalised sentence
    of real text cannot match. A line that starts with its own number is excluded
    outright: "4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)" can sit under a chapter divider
    on the same page, and a numbered heading is never the tail of a divider title.
    """
    if not is_capitals(line) or len(line.split()) > DIVIDER_CONTINUATION_MAX_WORDS:
        return False
    if line.endswith((".", "!", "?")):
        return False
    if NUMBERED_OR_NAMED_HEADING.match(line):
        return False
    return bool(DIVIDER_CONTINUATION.match(line))


def clean_text_lines(text: str, drop_hindi: bool = False) -> list[str]:
    """Clean one page of text into lines, keeping blank lines as paragraph breaks.

    `drop_hindi` is on inside the gazette's English range, where any Devanagari left
    after the header is a divider page's Hindi title.

    A divider line in capitals opens a divider block, and the capitalised lines that
    follow it — with blanks allowed between, because the title is spread down the page —
    are the rest of its title and go too. Without that, "FOR RESIDENTIAL" from the
    chapter 7 divider page ends up glued to the last clause of chapter 6 (D-066).
    """
    kept: list[str] = []
    in_divider = False
    for raw in strip_zero_width(text).splitlines():
        line = normalise_spaces(raw)
        if is_droppable(line, drop_hindi):
            if starts_divider_block(line):
                in_divider = True
            continue
        if line and in_divider:
            if continues_divider_title(line):
                continue
            in_divider = False
        if not line and (not kept or not kept[-1]):
            continue  # never keep two blank lines in a row
        kept.append(line)
    while kept and not kept[-1]:
        kept.pop()
    return kept


def join_hyphenated(lines: list[Line]) -> list[Line]:
    """Join a word split across a line end: "compact mixed-" + "use ..." -> "mixed-use ...".

    The hyphen is kept. We cannot tell a wrapped compound word ("mixed-use") from a
    word the typesetter hyphenated to fit the line, and in this gazette the wrapped
    ones are compounds, so keeping the hyphen is the safer of the two guesses (D-017).
    The joined line keeps the page of its first half, so a clause that wraps across a
    page break still starts on the earlier page.
    """
    out: list[Line] = []
    for line in lines:
        if (
            out
            and not out[-1].is_table
            and not line.is_table
            and line.text
            and HYPHEN_BREAK.search(out[-1].text)
            and LOWERCASE_START.match(line.text)
        ):
            previous = out.pop()
            out.append(Line(previous.text + line.text, previous.page))
            continue
        out.append(line)
    return out


# --- joining pages -------------------------------------------------------------

#: What a finished sentence, quotation or bracket ends with.
SENTENCE_END = (".", "!", "?", ":", ";", "”", "’", '"', ")")

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


def sentence_continues(previous: Line, following: Line) -> bool:
    """True when `following` is the rest of the sentence `previous` was in the middle of.

    Both conditions have to hold, because either on its own is wrong often enough to
    matter. The earlier line must not end a sentence, and the later line must start
    with something that cannot start one: a lower-case word, or a word like "and" or
    "however" that only ever continues. A list marker, a table row or a capitalised
    word means a new thought, whatever the line before it ended with — a heading has
    no full stop either.
    """
    if previous.is_table or following.is_table:
        return False
    if not previous.text or not following.text:
        return False
    if previous.text.rstrip().endswith(SENTENCE_END):
        return False
    if following.text.startswith("|") or LIST_MARKER.match(following.text):
        return False
    words = following.text.split()
    if not words:
        return False
    first = words[0]
    return first[:1].islower() or first.lower() in CONTINUATION_WORDS


def join_pages(pages: list[list[Line]]) -> list[Line]:
    """Join a document's per-page lines into one stream, one blank line between pages.

    The blank line is a paragraph break, which is where the chunker is allowed to cut.
    That is right almost everywhere and wrong at the 57 places in this gazette where a
    sentence runs over a page break: page 683 of MPD-2047 opens with "and seamlessly
    integrated with the green spaces ...", and inserting a break there let the chunker
    cut the sentence in half (D-066). So when the next page carries on the sentence,
    the two lines are concatenated instead, and the joined line keeps the earlier page
    as its start and the later one as its end, so the chunk's page range stays honest.
    """
    out: list[Line] = []
    for page in pages:
        if not page:
            continue
        if out and sentence_continues(out[-1], page[0]):
            previous = out.pop()
            out.append(
                Line(
                    f"{previous.text} {page[0].text}",
                    previous.page,
                    last_page=page[0].page_end,
                )
            )
            out += page[1:]
            continue
        if out:
            out.append(Line("", page[0].page))
        out += page
    return out


# --- tables --------------------------------------------------------------------

#: A table needs at least this many columns to be worth keeping as a table.
MIN_TABLE_COLUMNS = 2
#: Over this share of empty cells the table came out garbled.
MAX_EMPTY_CELL_SHARE = 0.5


def table_is_usable(rows: list[list[str | None]]) -> tuple[bool, str]:
    """Is an extracted table good enough to keep? Returns (ok, reason when not)."""
    if not rows:
        return False, "no rows"
    columns = max(len(row) for row in rows)
    if columns < MIN_TABLE_COLUMNS:
        return False, f"only {columns} column(s)"
    cells = [cell for row in rows for cell in row]
    empty = sum(1 for cell in cells if not (cell or "").strip())
    share = empty / len(cells) if cells else 1.0
    if share > MAX_EMPTY_CELL_SHARE:
        return False, f"{share:.0%} of cells are empty"
    return True, ""


def _cell(value: str | None) -> str:
    """One table cell as a single line of markdown-safe text."""
    return normalise_spaces((value or "").replace("|", "\\|"))


def table_to_markdown(rows: list[list[str | None]]) -> str:
    """Turn the rows PyMuPDF's `table.extract()` returns into a markdown table.

    The first row is treated as the header, which is what these gazette tables have.
    Ragged rows are padded so every line has the same number of pipes.

    A leading row whose every cell is empty is dropped rather than rendered as the
    header. PyMuPDF returns one for a table whose top border it read as a row, and
    `| | | |` as a header tells a reader nothing and tells BM25 less — worse, the
    header is repeated on every piece when a long table is split, so one empty row
    becomes several. Rows are only ever dropped from the front, never reordered: the
    first row that has any content becomes the header in the order the document
    printed it (D-066).
    """
    width = max(len(row) for row in rows)
    padded = [[_cell(row[i] if i < len(row) else "") for i in range(width)] for row in rows]
    while len(padded) > 1 and not any(padded[0]):
        padded.pop(0)
    header, *body = padded
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def split_markdown_table(markdown: str, max_rows: int) -> list[str]:
    """Split a markdown table into pieces of at most `max_rows` body rows.

    The header row and its separator are repeated at the top of every piece, so a
    piece retrieved on its own still says what its columns mean.
    """
    lines = markdown.split("\n")
    if len(lines) <= 2:
        return [markdown]
    head, body = lines[:2], lines[2:]
    if len(body) <= max_rows:
        return [markdown]
    pieces = []
    for start in range(0, len(body), max_rows):
        pieces.append("\n".join(head + body[start : start + max_rows]))
    return pieces


def _table_bands(
    tables: list, page_rect: pymupdf.Rect
) -> list[tuple[float, float, list]]:
    """Group tables that overlap vertically, so each band of the page has one group.

    Returns (top, bottom, tables) per band, in reading order down the page.
    """
    ordered = sorted(tables, key=lambda t: (t.bbox[1], t.bbox[0]))
    bands: list[tuple[float, float, list]] = []
    for table in ordered:
        top, bottom = table.bbox[1], table.bbox[3]
        if bands and top <= bands[-1][1]:
            previous_top, previous_bottom, group = bands.pop()
            bands.append((min(previous_top, top), max(previous_bottom, bottom), group + [table]))
        else:
            bands.append((top, bottom, [table]))
    return [
        (max(top, page_rect.y0), min(bottom, page_rect.y1), group) for top, bottom, group in bands
    ]


def page_lines_from_pdf(
    page: pymupdf.Page, page_number: int, drop_hindi: bool = False
) -> tuple[list[Line], list[str]]:
    """Read one page as cleaned lines, with its tables as markdown in reading order.

    The text between the tables is read with `get_text(clip=...)` over the horizontal
    bands the tables leave free, so table text is never also present as loose text.
    If any table on the page comes out garbled the whole page falls back to plain
    text, and a warning says so.
    """
    warnings: list[str] = []
    try:
        tables = list(page.find_tables().tables)
    except Exception as exc:  # table finding is best-effort and must never stop a run
        tables = []
        warnings.append(f"page {page_number}: find_tables failed ({exc})")

    if not tables:
        plain = page.get_text("text", sort=True)
        return [Line(text, page_number) for text in clean_text_lines(plain, drop_hindi)], warnings

    extracted: list[tuple[list, str]] = []
    for index, table in enumerate(tables):
        try:
            rows = table.extract()
        except Exception as exc:
            warnings.append(f"page {page_number}: table {index} could not be extracted ({exc})")
            rows = []
        ok, reason = table_is_usable(rows)
        if not ok:
            warnings.append(
                f"page {page_number}: table {index} unusable ({reason}); "
                "using the plain text of the page instead"
            )
            plain = page.get_text("text", sort=True)
            return (
                [Line(text, page_number) for text in clean_text_lines(plain, drop_hindi)],
                warnings,
            )
        extracted.append((table, table_to_markdown(rows)))

    rect = page.rect
    bands = _table_bands([table for table, _ in extracted], rect)
    markdown_for = {id(table): text for table, text in extracted}

    lines: list[Line] = []
    cursor = rect.y0
    for top, bottom, group in bands:
        if top > cursor:
            clip = pymupdf.Rect(rect.x0, cursor, rect.x1, top)
            above = page.get_text("text", sort=True, clip=clip)
            lines += [Line(text, page_number) for text in clean_text_lines(above, drop_hindi)]
        for table in sorted(group, key=lambda t: t.bbox[0]):
            if lines and lines[-1].text:
                lines.append(Line("", page_number))
            lines.append(Line(markdown_for[id(table)], page_number, is_table=True))
            lines.append(Line("", page_number))
        cursor = max(cursor, bottom)
    if cursor < rect.y1:
        clip = pymupdf.Rect(rect.x0, cursor, rect.x1, rect.y1)
        below = page.get_text("text", sort=True, clip=clip)
        lines += [Line(text, page_number) for text in clean_text_lines(below, drop_hindi)]

    while lines and not lines[-1].text and not lines[-1].is_table:
        lines.pop()
    return lines, warnings


def count_words(text: str) -> int:
    """How many whitespace-separated words a piece of text holds."""
    return len(text.split())
