# Chunk quality audit

`data/processed/chunks.jsonl`: **702 chunks**, 162,461 words, 231 words a chunk on average.

Every check below is mechanical and some of them are meant to fire: a norms table really is mostly numbers, and an abbreviations entry really does end without a full stop. The examples are there so a person can tell a defect from a document simply being like that.

## Counts

| check | chunks | share |
| --- | --- | --- |
| `starts_mid_sentence` | 4 | 0.6% |
| `ends_mid_sentence` | 34 | 4.8% |
| `broken_tables` | 3 | 0.4% |
| `leftover_page_furniture` | 6 | 0.9% |
| `duplicate_chunks` | 0 | 0.0% |
| `missing_clause_ids` | 0 | 0.0% |
| `wrong_size` | 56 | 8.0% |
| `mostly_not_text` | 18 | 2.6% |

## Chunks that start mid-sentence

The first word is lower case or can only continue a sentence. A leading list marker is stripped first, so "(ii) Economy: ..." is not counted.

**4 chunks.**

- `MPD47_GAZETTE_EN:p643:0` — colonies, Rehabilitation Colonies, General Pool Residential Areas (GPRA), employer / government housing, Cooperative Gro
- `MPD47_GAZETTE_EN:3.1.2@p683:0` — and seamlessly integrated with the green spaces and floodplains to create continuous ecological corridors. Discharge of 
- `NGT_OA572_GNCTD_REPORT:7@p5:0` — removal fem floodplain on regular basis and so far 1530 acres of floodplain  have been repossessed during the period of 
- `NGT_OA572_GNCTD_REPORT:3@p21:0` — cerebee velocities a 25 20 104 area along petite nay etc, The assessment of impact on flood prone cross-section, hydraui

## Chunks that end mid-sentence

No terminal punctuation at the end. Tables, list items and the abbreviations chapter are excluded, because those are not prose and end without a full stop.

**34 chunks.**

- `MPD47_GAZETTE_EN:1.8@p670:0` — ...tors to enable course correction in the Plan as it is adapted to changing needs and priorities. /  / & DEVELOPMENT FRAMEWORK
- `MPD47_GAZETTE_EN:6.1.4:0` — ...public spaces through community action, greening of built environments, etc. /  / DEVELOPMENT CONTROL NORMS /  / FOR RESIDENTIAL
- `MPD47_GAZETTE_EN:7.2.5:0` — ...tegrated Residential School, Cultural and Information Centre, Police Post, Fire Station and Post office. /  / FOR COMMERCIAL
- `MPD47_GAZETTE_EN:8.3.2@p832:0` — ...me to time. /  / (k) Sustainable management of waste is to be carried out in all hotel and motel properties. /  / FOR INDUSTRIAL
- `MPD47_GAZETTE_EN:9.4:0` — ...Industrial area. Primary treatment of the effluent shall be done at the plot level as per requirement. /  / FOR RECREATIONAL
- ... and 29 more

## Broken markdown tables

Rows with inconsistent column counts, an entirely empty header row, or a missing separator row.

**3 chunks.**

- `MPD47_GAZETTE_EN:p1080:0` — table 0: empty header — |  |  |  |
- `MPD47_GAZETTE_EN:p1080:1` — table 0: empty header — |  |  |  |
- `NGT_OA572_GNCTD_REPORT:15:0` — table 0: empty header, no separator row — |

## Leftover running headers and divider text

The gazette's running header, Devanagari inside the English range, or an all-capitals fragment of a PART or CHAPTER divider title.

**6 chunks.**

- `MPD47_GAZETTE_EN:1.8@p670:0` — divider text '& DEVELOPMENT FRAMEWORK'
- `MPD47_GAZETTE_EN:6.1.4:0` — divider text 'FOR RESIDENTIAL'
- `MPD47_GAZETTE_EN:7.2.5:0` — divider text 'FOR COMMERCIAL'
- `MPD47_GAZETTE_EN:8.3.2@p832:0` — divider text 'FOR INDUSTRIAL'
- `MPD47_GAZETTE_EN:9.4:0` — divider text 'FOR RECREATIONAL'
- ... and 1 more

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

**56 chunks.**

- `MPD47_GAZETTE_EN:4.1.4:0` — 23 words (under 40)
- `MPD47_GAZETTE_EN:4.5.8:0` — 32 words (under 40)
- `MPD47_GAZETTE_EN:Annexure 5:0` — 8 words (under 40)
- `MPD47_GAZETTE_EN:Annexure 5b:0` — 29 words (under 40)
- `MPD47_GAZETTE_EN:Annexure 9:0` — 7 words (under 40)
- ... and 51 more

## Chunks dominated by numbers or table noise

Under 40% of the non-space characters are letters. A norms table is expected to appear here; a chunk without a table is not.

**18 chunks.**

- `MPD47_GAZETTE_EN:3.1@p1002:0` — 37% alphabetic, table
- `MPD47_GAZETTE_EN:p1043:0` — 16% alphabetic, table
- `MPD47_GAZETTE_EN:p1044:0` — 15% alphabetic, table
- `MPD47_GAZETTE_EN:p1045:0` — 37% alphabetic, table
- `MPD47_GAZETTE_EN:p1047:0` — 30% alphabetic, table
- ... and 13 more

