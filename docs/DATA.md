# The data behind ZoneWise

What is indexed, what it was turned into, and what is missing. Every number here comes
from a generated report: `data/processed/chunk_report.md`, `data/processed/tag_report.md`
and `data/layers/manifest.json`, all of which are rebuilt by the pipeline scripts.

---

## 1. The documents

`data/sources.csv` lists 13 documents. **Four are indexed**, one is kept for reading by
hand, and eight are deliberately out.

### Indexed

| doc_id | What it is | Authority | Pages | Chunks | Words |
| --- | --- | --- | --- | --- | --- |
| `MPD47_GAZETTE_EN` | Master Plan for Delhi 2047, gazette notification, 20 Aug 2026 | 1 — the law | 505 (640-1144) | 546 | 147,469 |
| `MPD47_FAQ` | DDA's FAQs on MPD-2047 | 3 — FAQ | 20 | 99 | 5,485 |
| `DHC_YAMUNA_20240708` | Delhi High Court order on Yamuna floodplain encroachments | 2 — court order | 3 | 8 | 730 |
| `NGT_OA572_GNCTD_REPORT` | GNCTD report to the NGT on floodplain demarcation, OA 572/2024 | 3 — report | 32 | 47 | 8,752 |
| | | | **560** | **700** | **162,436** |

`authority_rank` is used by the answering prompt: when two sources disagree, the model
is told to follow the lower rank and to say that they differ. 1 is the gazette, which is
the law; 2 a court order; 3 an FAQ or report that paraphrases.

### Not indexed, and why

| doc_id | Why not |
| --- | --- |
| `MPD47_PUBLICATION_EN` | The same plan text as the gazette. `scripts/compare_plan_versions.py` found 98% of sampled sentences word for word in the gazette, 100% ignoring punctuation, and every chapter heading matching. Indexing both would double-count every clause. The gazette also carries 152 extra pages of service plans and loses no pages to images, where the publication loses 31 (D-012). |
| 6 × `MPD47_*_EXPLAINER` | Two-page image pamphlets with no text layer. The `likely_scanned` check found all six to be fully scanned (D-008). OCR is a separate decision that has not been taken. |
| `NGT_YAMUNA_20250206` | The source URL returns 404. Listed with `include=no` so the gap is visible rather than forgotten. |
| `MPD47_LANDUSE_PLAN` | A map, not text. Kept in `data/reference/` for reading by hand. |

### The gazette's page range

`MPD47_GAZETTE_EN.pdf` is bilingual: Hindi runs to page 639 and the English notification
starts at 640. `data/sources.csv` carries `page_start = 640`, and extraction keeps the
**original PDF page numbers** rather than renumbering from 1, so a citation points at
the page a reader will actually find in the official file (D-010).

---

## 2. Cleaning

`app/cleaning.py`, applied per page before anything is chunked. Six things are removed
and everything else is kept.

| Removed | Why |
| --- | --- |
| The running header, English and Hindi | On every page, carrying the page number inside the line, so it is matched on wording rather than exact text — no two copies are identical (D-011, D-016). |
| Lines that are only a page number | Nothing to cite. |
| Figure and map captions | "Illustration 6: Transit Oriented Development (TOD)", "(For illustrative purpose only)". The picture is not indexed, so the caption alone is a retrievable line that answers nothing. |
| Chapter and part dividers | `data/chapter_map.json` already says which chapter a page is in; the line would become a two-word chunk. |
| Devanagari lines inside the English range | Eight section-divider pages where the Hindi header is most of the text. |
| Repeated spaces inside a line | Justified text leaves them behind ("Kartavya&nbsp;&nbsp;Path&nbsp;&nbsp;development"). |

Two more rules are worth knowing:

- **A word broken across a line end keeps its hyphen.** "compact mixed-" + "use" becomes
  "mixed-use". We cannot tell a wrapped compound from a typesetter's hyphenation, and in
  this gazette the wrapped ones are compounds; dropping the hyphen would silently
  rewrite "mixed-use" as "mixeduse" and break the keyword index (D-017).
- **The FAQ and the two court documents get a different header rule.** Each carries its
  own running header, found by the 40% repeated-edge-line test with digits removed —
  which is what catches "Indian Kanoon - http://indiankanoon.org/doc/28108780/ 3", whose
  trailing page number makes every copy unique.

### Tables

On a page where PyMuPDF finds tables, each is read with `table.extract()` and written as
a markdown table; the text around it is read with `get_text(clip=...)` over the bands the
tables leave free, so nothing appears twice.

**292 tables converted, 42 fell back to plain text.** A table is rejected when more than
half its cells are empty or it has fewer than two columns, and then the whole page falls
back. All but five of the fallbacks are in the service plans' drainage and waste sheets,
which are sparse engineering grids. Every one is listed by page in
`data/processed/chunk_report.md` (D-018).

This matters because the development control norms in chapters 7 to 12 are almost
entirely tables: losing their shape would lose the plan's actual numbers.

---

## 3. Chunking

`app/chunking.py`. Target 150-400 words.

| Rule | Value |
| --- | --- |
| Target size | 150-400 words |
| Merge a section with its next sibling under | 40 words |
| Split a section over | 500 words |
| Sentence-split a single paragraph over | 650 words |
| Sentence-split overlap | ~40 words |
| Abbreviation chunks | ~300 words |

### Size distribution

| Words | Chunks | Share |
| --- | --- | --- |
| under 40 | 56 | 8.0% |
| 40-149 | 156 | 22.2% |
| **150-400 (target)** | **446** | **63.5%** |
| 401-500 | 44 | 6.3% |
| 501-650 | 0 | 0% |
| over 650 | 0 | 0% |

Nothing exceeds 500 words. The 56 under 40 are honest: 45 are FAQ answers that really
are one line, where the specification asks for one chunk per question, and the rest are
annexure titles whose body table was split off and cover-page fragments of the NGT
report.

### How each part is cut

| Part | Rule |
| --- | --- |
| Gazette chapters 1-13 | Decimal section headings (`4.2`, `4.2.1`, `4.2.3.1`). A heading's first number must equal its chapter number, which removes every false positive across 250 pages of tables (D-019). |
| Preamble | Paragraphs, grouped by size. |
| Abbreviations | ~300-word chunks. |
| Definitions | One chunk per definition, short ones grouped. |
| Annexures | `Annexure N` headings and their sub-headings. |
| Maps | Captions only; pages with no real text are skipped. |
| Service plans | Each agency's own numbered headings. No chapter number to check against, so three guards stand in: no part of the number above 20, at most three levels, a title of at least four characters. |
| `MPD47_FAQ` | One chunk per question, with its section heading in the path. |
| Court order, NGT report | Paragraphs of 150-400 words, numbered paragraphs as the clause id. |

### What a chunk record holds

```json
{
  "chunk_id": "MPD47_GAZETTE_EN:4.2.1:0",
  "doc_id": "MPD47_GAZETTE_EN",
  "doc_title": "Master Plan for Delhi 2047 gazette notification (English)",
  "doc_type": "plan", "authority_rank": 1, "doc_date": "2026-08-20",
  "source_url": "https://dda.gov.in/...",
  "chapter": "4", "chapter_title": "Spatial Development Policies",
  "heading_path": ["4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)", "4.2.1 Definitions"],
  "clause_id": "4.2.1", "clause_ids": ["4.2.1"],
  "page_start": 750, "page_end": 751,
  "text": "4.2.1 Definitions\n\n(i) “TOD Zone”: area under 500m wide corridor ...",
  "embed_text": "MPD-2047 › Spatial Development Policies › 4.2 TRANSIT ... \n\n4.2.1 ...",
  "n_words": 167, "has_table": false,
  "zone_primary": "tod", "zone_mentions": ["tod"],
  "zp_tod": true, "zm_tod": true, "...": "and six more zone booleans"
}
```

Two fields are easy to confuse. **`text`** is clean and is what gets displayed and
quoted. **`embed_text`** is what goes to the index: the same text with one breadcrumb
line above it, `MPD-2047 › <chapter> › <heading path>`. Clause 4.2.1 never says the
words "transit oriented development" in a sentence a user would match on, so without
the breadcrumb a question about TOD cannot reach it (D-022).

**Chunk ids are deterministic and unique.** Clause numbers are not: the FAQ restarts at
Q1 in each of its nine sections, and the nine service plans each number from 1.1 inside
the same `doc_id`. An id that would repeat gets its page appended — `MPD47_FAQ:Q12@p16:0`
— so all 700 are distinct (D-021). Re-running the pipeline on the same input produces a
byte-identical `chunks.jsonl`.

---

## 4. Zone tagging

`app/tagging.py`. **Six topics**: `tod`, `hdc`, `zone_o`, `land_pooling`, `ridge`, `lda`.

**227 of 700 chunks (32.4%) carry at least one zone tag.**

| Topic | Name | `zone_primary` | mentioned in text | either |
| --- | --- | --- | --- | --- |
| tod | Transit Oriented Development | 29 | 64 | 64 |
| hdc | High Density Corridor | 36 | 47 | 53 |
| zone_o | Zone O (Yamuna floodplain) | 0 | 54 | 54 |
| land_pooling | Land Pooling | 23 | 55 | 63 |
| ridge | the Ridge / Regional Park | 0 | 37 | 37 |
| lda | Low Density Area | 15 | 31 | 37 |

### The two kinds of tag

`zone_primary` comes from the heading path, never the words, and is **the only tag
search may exclude on**. `zone_mentions` comes from the text and can only boost: section
4.6.1 names Zone O in the list of areas it does *not* apply to, and 11.1.1 says fuel
stations are allowed "in all Use Zones except ... Zone O" — a chunk that mentions a zone
to exclude it is exactly what a user standing in that zone needs (D-023).

### Which topics may exclude, and which may not

This is the single most consequential thing in this section, so it is a table of its own.
"May exclude" means: for a point **outside** this zone, search is allowed to drop chunks
whose `zone_primary` is this topic, because they are rules that apply inside it and
nowhere else.

| Topic | May exclude | Why |
| --- | --- | --- |
| tod | **yes** | 4.2 is a dedicated TOD policy chapter — Applicability, norms, the lot |
| hdc | **yes** | 4.3 is the HDC policy, including the UER-II corridor |
| land_pooling | **yes** | 4.1 is the Land Pooling policy |
| lda | **yes** | 4.4 LOW DENSITY AREA (LDA), with its own Applicability, Guiding principles and Development Control Norms, plus a "FAQs on LDA" section (D-069) |
| zone_o | **no** | MPD-2047 contains no Zone O policy at all (D-024, D-037) |
| ridge | **no** | MPD-2047 contains no Ridge policy at all (D-069) |

Four of six may exclude; two may only boost and expand. That two of them behave this way
makes it a **pattern rather than an exception**, and the reason is the same both times:
the plan never gives the area a policy section of its own, so there is no heading path
that means "this rule is about that place".

**Why `zone_o` has no sections.** Section 1.7.2 defines planning zone O as "River Yamuna
/ Riverfront", one of the 17 planning zones, and after that the plan names it only inside
other policies' exclusion lists — "this shall not apply to ... Zone 'O'" in 4.2.2, 4.5.1
and 4.6.1, and "all Use Zones except ... Zone O" in 11.1.1. The closest candidate, 3.1.2
Green-Blue Infrastructure, carries the real floodplain rule ("Active floodplain shall be
a 'no construction zone'") but is about every green and blue asset in Delhi, so claiming
it would let search drop it for any point outside the floodplain.

**Why `ridge` has no sections.** The gazette's headings were searched for a dedicated
Ridge or Regional Park policy and there is none. 37 chunks mention the Ridge and **every
one of them sits in a section about something else**. Chapter 10 defines Regional Park,
but it is the norms for *all* recreational land; 3.1.2 was rejected again for exactly the
reason it was rejected for Zone O. So `ridge` boosts and expands but can never exclude.
The visible cost is recorded honestly: at P_RIDGE, location-aware search returns 10.1's
definition of a Regional Park at rank 1, and what it does *not* return is a clause saying
you may not build there — because the plan does not phrase it that way. A question at
P_RIDGE is probably a should-abstain question (`reports/location_compare_v3.md`).

### The mapping, `data/zone_sections.json`

| Topic | Gazette sections | FAQ heading phrases |
| --- | --- | --- |
| tod | 4.2 | "Transit Oriented Development", "TOD Policy" |
| hdc | 4.3 | "High Density Corridor", "HDC Policy" |
| zone_o | *(none)* | *(none)* |
| land_pooling | 4.1 | "Land Pooling" |
| ridge | *(none)* | *(none)* |
| lda | 4.4 | "LDA", "Low Density Area" |

A gazette section number covers everything under it, so 4.2 covers 4.2.1 and 4.2.3.1,
and 4.4 covers 4.4.3 LDA Development Control Norms. The FAQ has no section numbers, so
its headings are matched on words, and **only an explicit topic name counts** — four of
the eight FAQ sections match and four do not:

| FAQ section heading | Tagged |
| --- | --- |
| FAQs - Transit Oriented Development (TOD) Policy | tod |
| FAQs on High Density Corridor (HDC) Policy | hdc |
| FAQs – Land Pooling Policy | land_pooling |
| FAQs on LDA | lda |
| FAQs - GENERIC | — |
| FAQs – Development Control Norms (DCN) for already existing developed areas | — |
| FAQs – Heritage, Culture & Public Spaces | — |
| FAQs - Slum and JJ Clusters | — |

That table is regenerated into `data/processed/tag_report.md` on every run, so a renamed
section cannot silently change what is tagged (D-038).

### The mention patterns

Case matters where the short form is also an ordinary word.

| Topic | Patterns |
| --- | --- |
| tod | `\bTOD\b` (capitals only), `transit[- ]oriented development` |
| hdc | `high[- ]density corridor`, `\bHDC\b`, `\bUER[- ]?II\b`, `urban extension road` |
| zone_o | `\bZone\s*['"]?O\b`, `Zone O-1`, `Zone O-2`, `Yamuna flood ?plain`, and "river Yamuna" together with "flood" |
| land_pooling | `land pooling`, `pooled land` |
| ridge | `\bridge\b`, `regional park`, `\bAravalli` (all case-insensitive) |
| lda | `\bLDA\b` (capitals only), `low density (area\|residential)`, `\bfarm ?house` |

The capital-O-as-a-whole-word rule is what makes "zone of", "Zone of the river" and
"TOD Zone or" fail to match while "Zone O" and "Zone 'O'" match. All of those are in
`tests/test_tagging.py`.

Two of the newer patterns are judgement calls worth flagging. `\bridge\b` is
case-insensitive and matches the ordinary English word, which is safe here only because
"ridge" in a Delhi planning document means the Ridge — but it would not survive a corpus
that discussed roof ridges. And `farm house` counts as an LDA mention because all four
occurrences in this plan fall inside the LDA sections or the definition of the term, so
it adds signal; it is still a word that could appear elsewhere in a future edition
(D-069).

---

## 5. The indexes

| Index | What | Size |
| --- | --- | --- |
| Chroma | 700 vectors, BAAI/bge-small-en-v1.5, 384 dimensions, cosine | 12.3 MB |
| BM25 | 700 documents, 11,126 distinct tokens | 963 KB |
| Model weights | downloaded once into `data/index/models` | 64 MB |

Both run over `embed_text`. The keyword tokenizer keeps a dotted clause number whole, so
searching "4.2.1" finds clause 4.2.1 rather than every chunk containing a 4, a 2 and a 1
(D-027). Embedding all 700 chunks takes about 150 seconds on a laptop CPU.

---

## 6. The map layers

`data/layers/manifest.json`, fetched by `scripts/06_fetch_layers.py` from DDA's ArcGIS
service. Areas computed in EPSG:32643 (UTM 43N); stored as EPSG:4326.

| Layer | Role | Features | Area km² | Repaired |
| --- | --- | --- | --- | --- |
| `nctd_boundary` | core | 1 | 1,486.7 | 0 |
| `planning_zones` | core | 16 | 1,475.0 | 0 |
| `high_density_corridor` | core | 1 | 19.1 | 0 |
| `tod_zone` | core | 13 | 252.4 | 0 |
| `land_pooling_area` | core | 9 | 334.3 | 1 |
| `regional_park` | extra | 44 | 91.0 | 1 |
| `yamuna_river` | extra | 3 | 20.4 | 0 |
| `low_density_area` | extra | 208 | 281.8 | 1 |

**NCT Delhi comes out at 1,486.7 km² against a published figure of about 1,480 km²**,
which is the check that the download, the projection and the geometry repair all worked.
Three invalid geometries were repaired with `make_valid` before anything was measured.

The five core layers answer `get_zones`. The three extra ones are downloaded and loaded
but not yet wired to any policy; only the core five are served to the browser.

**The layers are not committed.** DDA states no licence or terms of use anywhere on the
service, so we do not know we may redistribute them. The manifest is committed instead
and records the URL, the fetch time, the feature count, the geometry type, the field
names and the area for each (D-014, D-030).

---

## 7. Known gaps

- **Planning zone A is missing from DDA's layer.** 16 polygons where the plan's own
  1.7.2 lists 17; the absent one is Old City — the Walled City and the area outside it.
  A point there returns `planning_zone = null` rather than a guess. Drawing our own
  boundary would mean inventing a legal line from a scanned map (D-039).
- **The land pooling layer's zone letters are its own.** Its `zone` field holds "L" for
  polygons inside planning zone K-I. They are returned as a separate field,
  `land_pooling_zone`, precisely so the two cannot be compared.
- **42 tables fell back to plain text**, almost all in the service plans' engineering
  sheets. The text survives; the row and column structure does not.
- **Six explainer PDFs are scanned images** and are not indexed.
- **One NGT order could not be downloaded** (404).
- **English only.** The gazette's Hindi half is outside the indexed range.
- **Zone boundaries are approximate.** A web GIS service is not a survey.

## Reproducing all of this

```powershell
uv run python scripts/02_extract.py        # pages.jsonl
uv run python scripts/03_chunk.py          # chunks.jsonl + chunk_report.md
uv run python scripts/04_tag_zones.py      # zone tags + tag_report.md
uv run python scripts/05_build_index.py    # Chroma + BM25
uv run python scripts/06_fetch_layers.py   # the layers + manifest.json
```

Every one is safe to re-run and prints its own summary. `03` then `04` reproduces a
byte-identical `chunks.jsonl`.

---

## The place-name gazetteer

`data/gazetteer/metro_stations.json`, built by `scripts/build_gazetteer.py` from
OpenStreetMap in **one** Overpass request bounded to the NCT Delhi bounding box. One
record per distinct station name:

```json
{"name": "Rajiv Chowk", "alt_names": ["Rajiv Chowk Metro Station"],
 "lat": 28.632800, "lon": 77.219700}
```

The query asks for `railway=station` with either `station=subway` or a `network` matching
"Delhi Metro", over nodes, ways and relations — OSM models a station sometimes as a
point, sometimes as the building's outline, sometimes as a relation over both. Records
are keyed by lower-case name and the first element with coordinates wins, because the
gazetteer answers "roughly where is Rajiv Chowk" and not "where is platform 3".

Every tag that can hold a name is read, in preference order: `name`, `name:en`,
`official_name`, `alt_name`, `old_name`, `short_name`. The first becomes `name` and the
rest become `alt_names`, so a station is findable under the name on the signage and the
name people use. `alt_name` and `old_name` are split on semicolons, which is OSM's
convention for a multi-valued tag.

**Why it exists.** `app/geocode.locate_place` tries the gazetteer before Nominatim, so
the commonest way a Delhi resident describes a location — a metro station — is a local
string match with no network request. Night 2 found that Nominatim returns nothing for
"Dwarka Sector 21 metro station" with a bounded search (D-049), which is close to the
phrase the interface itself suggests typing.

**Licence and attribution.** OpenStreetMap data, &copy; OpenStreetMap contributors,
published under the [Open Database License](https://opendatacommons.org/licenses/odbl/).
`data/gazetteer/` is gitignored: the data is OSM's, and one script call rebuilds it.

**State in this repository.** The file is **not present**. The Overpass request could not
be made on the machine this was built on, so `locate_place` falls through to Nominatim
for every query, which is a supported state and not an error — the gazetteer is an
optimisation, and its logic is covered by tests that write their own fixture. Running
`uv run python scripts/build_gazetteer.py` fills it in. See D-073.
