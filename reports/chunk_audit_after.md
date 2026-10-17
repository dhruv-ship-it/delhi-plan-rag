# Chunk quality audit

`data/processed/chunks.jsonl`: **700 chunks**, 162,436 words, 232 words a chunk on average.

Every check below is mechanical and some of them are meant to fire: a norms table really is mostly numbers, and an abbreviations entry really does end without a full stop. The examples are there so a person can tell a defect from a document simply being like that.

## Before and after

| check | before | after | change |
| --- | --- | --- | --- |
| `starts_mid_sentence` | 4 | 0 | -4 |
| `ends_mid_sentence` | 34 | 23 | -11 |
| `broken_tables` | 3 | 0 | -3 |
| `leftover_page_furniture` | 6 | 2 | -4 |
| `duplicate_chunks` | 0 | 0 | no change |
| `missing_clause_ids` | 0 | 0 | no change |
| `wrong_size` | 56 | 53 | -3 |
| `mostly_not_text` | 18 | 18 | no change |

## Findings that are the corpus, not a defect

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


## Counts

| check | chunks | share |
| --- | --- | --- |
| `starts_mid_sentence` | 0 | 0.0% |
| `ends_mid_sentence` | 23 | 3.3% |
| `broken_tables` | 0 | 0.0% |
| `leftover_page_furniture` | 2 | 0.3% |
| `duplicate_chunks` | 0 | 0.0% |
| `missing_clause_ids` | 0 | 0.0% |
| `wrong_size` | 53 | 7.6% |
| `mostly_not_text` | 18 | 2.6% |

## Chunks that start mid-sentence

The first word is lower case or can only continue a sentence. A leading list marker is stripped first, so "(ii) Economy: ..." is not counted.

**0 chunks.**

None.

## Chunks that end mid-sentence

No terminal punctuation at the end. Tables, list items and the abbreviations chapter are excluded, because those are not prose and end without a full stop.

**23 chunks.**

- `MPD47_GAZETTE_EN:p907:1` — ...: The area obtained as a resultant of applying the FAR (Floor Area Ratio) on the plot area. Floor area = FAR x Plot area
- `MPD47_GAZETTE_EN:p1016:0` — ...re 19B-iii: Detail of Effluent Irrigation System /  / ANNEXURE 19B-i: Embankment Strengthening /Remodelling Status of Drains
- `MPD47_GAZETTE_EN:p1019:0` — ...3.45m /  / CD-IV /  / Trunk Drain No.I , CD- 8.13 IV-5260m, to 13387m RD 5260m to 6690m 1.43 /  / RD 6690m to 10330m 3.64 Good No No
- `MPD47_GAZETTE_EN:p1029:0` — ...2.00 to RD 5470m /  / Trunk Drains Drain under the No.I , 5.26 2.67 20.00 jurisdiction CD-III- are passing 5260m through the
- `MPD47_GAZETTE_EN:p1032:0` — ...D- 5900m 135.0 58.764 76.236 10.00 14.00 5.00 5.00 20.06 to RD- 0 0m /  / DETAILS OF BUFFERS ALONG DRAINS OF I&FC DEPARTMENT
- ... and 18 more

## Broken markdown tables

Rows with inconsistent column counts, an entirely empty header row, or a missing separator row.

**0 chunks.**

None.

## Leftover running headers and divider text

The gazette's running header, Devanagari inside the English range, or an all-capitals fragment of a PART or CHAPTER divider title.

**2 chunks.**

- `MPD47_GAZETTE_EN:p1032:0` — divider text 'DETAILS OF BUFFERS ALONG DRAINS OF I&FC DEPARTMENT'
- `MPD47_GAZETTE_EN:p1034:0` — divider text 'DETAILS OF BUFFERS ALONG DRAINS OF I&FC DEPARTMENT'

## Duplicate and near-duplicate chunks

Identical normalised text, or over 0.95 similar, within the same document.

**0 chunks.**

None.

## Gazette chunks in chapters 1-13 with no clause id

A chunk in the plan's own numbered chapters that a citation cannot point at by clause number.

**0 chunks.**

None.

## Chunks under 40 or over 500 words

The bounds the chunking rules set (D-020). Under 40 words should have been merged; over 500 should have been split.

**53 chunks.**

- `MPD47_GAZETTE_EN:4.1.4:0` — 23 words (under 40)
- `MPD47_GAZETTE_EN:4.5.8:0` — 32 words (under 40)
- `MPD47_GAZETTE_EN:Annexure 5b:0` — 29 words (under 40)
- `MPD47_GAZETTE_EN:Annexure 13:0` — 38 words (under 40)
- `MPD47_GAZETTE_EN:p988:0` — 33 words (under 40)
- ... and 48 more

## Chunks dominated by numbers or table noise

Under 40% of the non-space characters are letters. A norms table is expected to appear here; a chunk without a table is not.

**18 chunks.**

- `MPD47_GAZETTE_EN:3.1@p1002:0` — 37% alphabetic, table
- `MPD47_GAZETTE_EN:p1043:0` — 16% alphabetic, table
- `MPD47_GAZETTE_EN:p1044:0` — 15% alphabetic, table
- `MPD47_GAZETTE_EN:p1045:0` — 37% alphabetic, table
- `MPD47_GAZETTE_EN:p1047:0` — 30% alphabetic, table
- ... and 13 more

