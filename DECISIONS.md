# Decisions log
Each entry: what we decided, why, and what we rejected.

## D-001 · 2026-10-14 · Standalone repo
ZoneWise lives in its own repo, separate from the TerraTime capstone. Why: keeps the resume project clean. TerraTime can call ZoneWise's API later instead of merging code. Rejected: building inside the TerraTime repo.

## D-002 · 2026-10-14 · Python + FastAPI backend, React frontend, no MERN
Why: all the AI and map libraries we need are Python. There is nothing to store in MongoDB (no users; vectors live in Chroma), and Express would only add an extra hop. Rejected: MERN.

## D-003 · 2026-10-14 · No RAG frameworks
We write chunking, hybrid search, fusion and citation checks ourselves. Why: every step stays visible and explainable, and the codebase stays small. Rejected: LangChain, LlamaIndex.

## D-004 · 2026-10-14 · Documents downloaded by hand
Source PDFs are downloaded manually and listed in data/sources.csv with URL and download date. Why: government sites are slow and change often, there are only about 12 files, and the CSV keeps the work reproducible. Rejected: scraping scripts.

## D-005 · 2026-10-14 · Python 3.12 via uv
Why: one tool manages the Python version and the dependencies, with the same commands on Windows, Mac and Linux. Rejected: system Python + pip + venv.

## D-006 · 2026-10-14 · PyMuPDF for text, read in sorted order
We read page text with PyMuPDF's `page.get_text("text", sort=True)`. Why: PyMuPDF is fast (about 940 pages in under two minutes, including table detection) and `sort=True` returns the text blocks top-to-bottom and left-to-right instead of in the order the PDF happens to store them, which is what a reader sees. Without sorting, two-column pages come out interleaved and clauses break apart. Rejected: pdfplumber (slower on a 1144-page file), pypdf (weaker layout handling), and raw `get_text()` without sorting.

## D-007 · 2026-10-14 · Page text is stored raw, cleaning comes later
`pages.jsonl` holds each page's text exactly as PyMuPDF returns it: running headers, footers, page numbers and odd spacing included. Why: extraction and cleaning are separate steps, so a cleaning bug can be fixed and re-run without re-reading every PDF, and we can always compare the cleaned text against the original. The extract report only *lists* repeated header and footer lines so we can see what to strip next. Rejected: stripping headers during extraction, which hides what was removed and makes the output hard to check.

## D-008 · 2026-10-14 · The likely_scanned rule
A page is flagged `likely_scanned` when it has under 50 characters of text and at least one image, or under 20 characters in total. Why: a scanned page is a picture of text, so it reads as an image with almost no characters. The second half of the rule catches blank and image-free empty pages too. The thresholds are deliberately low so a sparse but real page (a section divider, a page with one heading) is not flagged. This is a flag for a human to look at, not a decision: nothing is dropped. It found all six DDA explainers to be fully scanned, which is what we needed to know. Rejected: comparing image area to page area (more code, no better answer at this stage) and running OCR right away (a separate decision, once we know how much text is missing).

## D-009 · 2026-10-14 · JSONL for page records
One JSON object per line in `data/processed/pages.jsonl`. Why: it appends and streams line by line, so a 944-page file never has to be held in memory at once, every record carries its own field names, and `git diff` on a generated file stays readable. Page text holds newlines, quotes and Hindi, all of which JSON escapes safely. Rejected: CSV (multi-line text in cells is fragile), one file per page (thousands of small files), and Parquet (an extra dependency for no gain at this size).

## D-010 · 2026-10-14 · The gazette's English part is selected by page range, not by editing the PDF
`MPD47_GAZETTE_EN.pdf` is the bilingual gazette: Hindi runs to page 639 and the English notification starts on page 640. `data/sources.csv` now has `page_start` and `page_end` columns (1-based, inclusive; blank means first page / last page), and the gazette is set to `page_start = 640`. Extraction reads only pages inside the range and keeps the original PDF page numbers. Why: a hand-split PDF is not reproducible (nobody can tell later which pages were cut, or re-do it after a re-download), and a citation has to point at the page number a reader will find in the official file. Rejected: splitting the PDF by hand, and renumbering the extracted pages from 1.

## D-011 · 2026-10-14 · Thresholds for the two report-only flags
A page counts as mostly Hindi when more than 30% of its non-space characters are in the Devanagari Unicode block. A line counts as a repeated header or footer when it is among the first two or last two non-empty lines on more than 40% of a document's pages. Why: both are warnings for a human reading the report, so loose thresholds are fine. Two notes from the first run, for the cleaning step: the gazette's running header carries the page number inside it, so no header line repeats literally and the 40% rule finds nothing for that document — matching will have to ignore digits. And the 8 "mostly Hindi" pages in the gazette's English range are sparse section dividers where the Hindi running header is most of the text on the page, not Hindi content. Rejected: counting Devanagari against all characters including spaces (whitespace-heavy pages would read as less Hindi than they are).
