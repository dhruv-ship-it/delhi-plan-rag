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
    """True for a line that carries no clause text: header, page number, caption, divider."""
    if not line:
        return False  # a blank line is a paragraph break, not noise
    if is_gazette_header(line) or PAGE_NUMBER_LINE.match(line):
        return True
    if FIGURE_CAPTION.match(line) or ILLUSTRATIVE_NOTE.match(line):
        return True
    if DIVIDER_LINE.match(line):
        return True
    return drop_hindi and is_mostly_hindi(line)


def clean_text_lines(text: str, drop_hindi: bool = False) -> list[str]:
    """Clean one page of text into lines, keeping blank lines as paragraph breaks.

    `drop_hindi` is on inside the gazette's English range, where any Devanagari left
    after the header is a divider page's Hindi title.
    """
    kept: list[str] = []
    for raw in strip_zero_width(text).splitlines():
        line = normalise_spaces(raw)
        if is_droppable(line, drop_hindi):
            continue
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
    """
    width = max(len(row) for row in rows)
    padded = [[_cell(row[i] if i < len(row) else "") for i in range(width)] for row in rows]
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
