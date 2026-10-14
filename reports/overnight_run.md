# Overnight run, 15 October 2026

Day 2 of ZoneWise, run unattended. Seven stages: housekeeping, cleaning and chunking,
zone tagging, the search indexes, retrieval, the DDA map layers and location-aware
search, then tests and this report.

**All seven stages finished.** 96 tests pass, nothing is pushed, and there are seven
commits on `main` waiting for review.

| stage | what it built | state |
| --- | --- | --- |
| 0 | lower-case chapter labels, `reports/` and `data/layers/dda/`, seven dependencies | done |
| 1 | `app/cleaning.py`, `app/chunking.py`, `scripts/03_chunk.py` — 702 chunks | done |
| 2 | `app/tagging.py`, `scripts/04_tag_zones.py` — 181 chunks tagged | done |
| 3 | `app/indexing.py`, `scripts/05_build_index.py` — Chroma + BM25 | done |
| 4 | `app/retrieval.py`, `scripts/search.py` — hybrid search, 8 queries run | done |
| 5 | `scripts/06_fetch_layers.py`, `app/spatial.py`, `scripts/07_test_points.py` — 8 layers | done |
| 6 | `app/location.py` — exclusion, expansion, boost; 7 comparisons run | done |
| 7 | 82 new tests, 24 decisions logged (D-013 to D-036), this report | done |

Nothing failed and no stage had to be skipped. Two things need your judgement rather
than your attention, and they are in **Things I had to guess** below.

---

## 1. What each stage did

### Stage 0 — housekeeping

`scripts/build_chapter_map.py` now writes every label in lower case, so
`data/chapter_map.json` reads `preamble` rather than `Preamble` and nothing downstream
has to remember the one capitalised exception (D-013). The map still covers gazette
pages 640 to 1144 in 19 entries with no gaps and no overlaps.

`reports/` was created and is committed; `data/layers/dda/` was created and is
gitignored, because DDA states no licence for the data (D-014). `.gitignore` and the
repo layout in `CLAUDE.md` were both updated.

All seven pre-approved dependencies installed on Windows first try, no version pinning
needed: fastembed 0.9.0, chromadb 1.5.9, rank-bm25 0.2.2, geopandas 1.2.0, shapely
2.2.0, pyproj 3.8.0, requests 2.34.2.

### Stage 1 — cleaning and chunking

`uv run python scripts/03_chunk.py` — **25 seconds**.

**702 chunks, 162,461 words**, from 560 pages of four documents.

| document | chunks | words | mean | with a table |
| --- | --- | --- | --- | --- |
| MPD47_GAZETTE_EN | 548 | 147,490 | 269 | 244 |
| MPD47_FAQ | 99 | 5,485 | 55 | 2 |
| DHC_YAMUNA_20240708 | 8 | 730 | 91 | 0 |
| NGT_OA572_GNCTD_REPORT | 47 | 8,756 | 186 | 1 |

Chunk sizes, against a 150-400 word target: **446 in the target band (64%)**, 44 at
401-500, 156 at 40-149, 56 under 40, and **none over 500**. The 56 short ones are
honest — 45 are FAQ answers that really are one line, which is what "one chunk per
question" produces, and the rest are annexure titles whose body table was split off and
cover-page fragments of the NGT report. 132 chunks have no clause number: the preamble,
the abbreviations and definitions lists, the map captions and the court documents' front
matter.

**Tables: 292 converted to markdown, 42 fell back to plain text.** All but five of the
fallbacks are in the service plans' drainage and waste sheets, which are sparse
engineering grids that PyMuPDF reads as mostly empty cells. Every one is listed by page
in `data/processed/chunk_report.md`.

The hard part was telling a heading from a table cell. Inside chapters 1 to 13 the
first number of a heading must equal the chapter number from `chapter_map.json`, and
that one check removes every false positive across 250 pages of norms tables (D-019).

### Stage 2 — zone tagging

`uv run python scripts/04_tag_zones.py` — **0.5 seconds**.

**181 of 702 chunks (26%) carry at least one zone tag.**

| topic | own policy section | zone_primary | mentioned | either |
| --- | --- | --- | --- | --- |
| tod | 4.2 | 10 | 64 | 64 |
| hdc | 4.3 | 9 | 47 | 47 |
| zone_o | *none* | 0 | 53 | 53 |
| land_pooling | 4.1 | 5 | 55 | 58 |

The 24 primary-zone chunks are listed one by one in `data/processed/tag_report.md`, and
all 24 are genuinely the policy sections. The zone regexes survive every false positive
in the brief: "TOD Zone or" tags tod and nothing else, and "flood plain zone of river"
tags nothing at all.

### Stage 3 — search indexes

`uv run python scripts/05_build_index.py` — **about 155 seconds**, of which 17 was the
one-off model download.

702 vectors in the Chroma collection `chunks` (cosine distance), and a BM25 model over
the same text with **11,126 distinct tokens**. Sizes on disk: Chroma 12.1 MB, bm25.pkl
963 KB, model weights 64.1 MB. All three are gitignored.

### Stage 4 — retrieval and the eight queries

`uv run python scripts/day2_queries.py` — **2.5 seconds**.

Dense and keyword each return 30, fused with reciprocal rank fusion at k = 60. All eight
queries ran in all three modes at k = 5; the output is in
**`reports/day2_queries.md`** for you to judge. One worth looking at: "Can a fuel
station be built in Zone O?" puts 11.1.1(d) at hybrid rank 1, which is the clause that
answers it.

### Stage 5 — DDA map layers

`uv run python scripts/06_fetch_layers.py` — **about 25 seconds** (one request a second).
`uv run python scripts/07_test_points.py` — **0.7 seconds**.

**All 8 layers downloaded.** Layer 6 (ZONE_BOUNDARY_TEXT) turned out to be polygons with
a `zone_name` field, so the planned fallback of building the planning zones from layer 7
was not needed.

| layer | role | features | area km² | repaired |
| --- | --- | --- | --- | --- |
| nctd_boundary | core | 1 | 1,486.7 | 0 |
| planning_zones | core | 16 | 1,475.0 | 0 |
| high_density_corridor | core | 1 | 19.1 | 0 |
| tod_zone | core | 13 | 252.4 | 0 |
| land_pooling_area | core | 9 | 334.3 | 1 |
| regional_park | extra | 44 | 91.0 | 1 |
| yamuna_river | extra | 3 | 20.4 | 0 |
| low_density_area | extra | 208 | 281.8 | 1 |

**NCT Delhi comes out at 1,486.7 km² against a published figure of about 1,480 km²**, so
the download, the EPSG:32643 projection and the geometry repair all worked. Three invalid
geometries were repaired with `make_valid` before anything was measured.

### Stage 6 — location-aware retrieval

`uv run python scripts/day3_location_compare.py` — **2.4 seconds**.

Three steps, in this order: exclude chunks whose own policy is a zone the point is not
in, append the point's zone words to the query, then multiply the fused score of
matching chunks by 1.5. All four comparisons ran at seven points; the output is in
**`reports/day3_location_compare.md`**.

### Stage 7 — tests

`uv run pytest` — **96 passed in 1.4 seconds** (14 were already there, 82 are new).

`tests/test_cleaning.py` (14), `tests/test_chunking.py` (23), `tests/test_tagging.py`
(13), `tests/test_retrieval.py` (19), `tests/test_spatial.py` (13). Every fixture is
written out in the test — a tiny PDF built on the spot for the table tests, nine toy
polygons for `get_zones` — so the suite passes on a clone with no PDFs and no indexes.

---

## 2. Problems hit, and how they were handled

**702 chunks were nearly 795, because of useless two-word chunks.** The specified merge
rule joins a section under 40 words with its *next sibling under the same parent*. It
cannot reach "11.1 Transportation", a heading sitting alone above 11.1.1 and 11.1.2,
because 11.1.1 is its child and not its sibling — and there were 36 such chunks, all
two or three words long. I added a second rule: a heading with no text of its own is
folded into its first child, keeping both clause numbers. Folding has no size cap,
unlike merging, because a heading belongs to the text beneath it and cannot glue two
unrelated clauses together. Logged as part of D-020.

**Splitting left scraps.** Cutting a long section at sub-item boundaries left tails like
"(ii) The above activities shall be subject to clearances from ..." — 12 words that mean
nothing without the list they close. A piece under 40 words is now put back on the piece
before it where there is room; both came from one section, so nothing is mixed up.

**The service plans have no chapter number to check headings against.** Each of the nine
agency documents numbers its own sections from 1.1, so the chapter check that works for
chapters 1 to 13 has nothing to compare with, and the drainage tables' measurements read
as headings ("5.90 Good NO NO RD-5900m to RD-0m", "19.7 RD"). Three guards replaced it:
no part of the number above 20, at most three levels deep, and a title of at least four
characters. The agency headings themselves are matched case-sensitively, because the
contents page on page 994 lists the same nine plans in title case and those lines are a
table of contents, not the start of a plan (D-019).

**Clause numbers are not unique, so the first chunk-id format collided.** The FAQ
restarts at Q1 in each of its nine sections, and the nine service plans each number from
1.1 — numbers that also collide with chapters 1 to 13 inside the same `doc_id`. Any id
that would repeat now gets its page appended: `MPD47_FAQ:Q12@p16:0`,
`MPD47_GAZETTE_EN:3.1@p677:0`. All 702 ids are distinct (D-021).

**Two FAQ sections were being filed under the wrong heading.** Seven of the nine FAQ
section headings read "FAQs - <topic>" and two read "FAQs on <topic>". Matching only the
dash form put the HDC and LDA questions under the previous section, so a question about
HDC plots was labelled TOD policy. Both forms are now matched, and all eight sections
in the indexed range come out right.

**The court order's footer carried a page number, so it survived the first pass.**
"Indian Kanoon - http://indiankanoon.org/doc/28108780/ 3" is the same footer on every
page, but the trailing number makes each copy unique, so the repeated-line rule missed
it. Repeated lines are now compared with their digits removed, which is the same trick
the gazette header rule uses. Zero residue left in the chunks.

**A test caught two mistakes of mine rather than the code's.** `test_chunking.py` first
asserted that three short numbered court paragraphs stay separate; they correctly merge,
because each is under 40 words and they are siblings — on the real order the paragraphs
run 46 to 109 words and do stay separate, so both behaviours are now tested.
`test_retrieval.py` first asserted the 1.5 boost is worth about nine ranks; the
break-even is actually rank 31.5, which is past the end of the 30-deep pool, so within
the pool a boosted chunk that both indexes returned beats any unboosted chunk. D-034 was
corrected to say that, and both arithmetic claims are now assertions rather than prose.

**Chroma's collection config API moved.** In chromadb 1.5.9 cosine distance is set with
`configuration={"hnsw": {"space": "cosine"}}`, not the older `metadata={"hnsw:space":
...}`. Checked against the installed version rather than guessed. Telemetry is off, and
the collection is rebuilt through the client rather than by deleting the folder, because
Windows holds a lock on the SQLite file while the client is open (D-026).

**P_HDC was in three zones at once.** The High Density Corridor follows UER-II straight
through the land pooling areas and across TOD corridors, so the first point found inside
it was also in TOD and in land pooling, which would have made the Stage 6 comparison
impossible to read. The search now prefers a point in the HDC and nothing else — there
are 425 such points on a 200×200 grid — and falls back to any HDC point if none exists
(D-032).

---

## 3. Things I had to guess

Two decisions were mine, and both are worth your opinion. Neither is a bug; both are
places where the brief asked for something the documents or the data do not contain.

### Guess 1 — `zone_o` has no policy section, so it can never exclude (D-024)

The brief asks for each topic's own policy section. TOD is 4.2, HDC is 4.3, land pooling
is 4.1 — all clean. **MPD-2047 has no Zone O policy.** Section 1.7.2 defines planning
zone O as "River Yamuna / Riverfront", one of the 17 planning zones, and after that the
plan names it only inside *other* policies' exclusion lists: "shall not apply to ...
Zone 'O'" in 4.2.2, 4.5.1 and 4.6.1, and "all Use Zones except Recreational ... and Zone
O" in 11.1.1 — which is the clause that answers the fuel-station question.

The nearest candidate was **3.1.2 Green-Blue Infrastructure**, which carries the real
floodplain rule ("Active floodplain shall be a 'no construction zone' and only
recreational uses shall be permitted"). I left it out. That section is about every green
and blue asset in Delhi — parks, drains, water-body buffers, eco-cultural assets — not
about Zone O, and `zone_primary` is the one tag search is allowed to **drop** on. Naming
it would mean that a question about a water-body buffer, asked at an ordinary address,
loses its answer.

So `data/zone_sections.json` maps `zone_o` to an empty list, and Zone O works through
mentions alone: it can boost and expand, and it can never lose a chunk. It works — at
P_ZONEO, "Can I construct a building here?" goes from heritage-façade FAQs to 3.1.2's
no-construction rule at rank 1, with the Delhi High Court order second. **If you want
Zone O to be able to exclude, 3.1.2 is the section to add, and the paragraph above is
the reason I did not.**

### Guess 2 — the FAQ's policy sections cannot be excluded (D-035)

Exclusion only reaches chunks with a `zone_primary`, and `zone_primary` is matched
against gazette *section numbers*. The FAQ has policy sections of its own — "FAQs -
Transit Oriented Development (TOD) Policy", "FAQs on High Density Corridor (HDC)
Policy", "FAQs – Land Pooling Policy" — but they are headings, not numbers, so those
chunks are tagged by mention only and are never excluded.

**It shows in the report.** At P_PLAIN, a plot in planning zone G in none of the four
policies, the top result for "What is the maximum ground coverage allowed on my plot?"
is still `MPD47_FAQ:Q13` — "What is the maximum ground coverage permissible for a TOD
Plot? Maximum permissible ground coverage is 40%" — while the gazette's own TOD clause
on exactly that point *was* correctly dropped.

I changed nothing, deliberately. The brief scopes `zone_sections.json` to gazette
section numbers; giving the FAQ exclusion power needs a second mechanism, matching a
heading's text instead of a number, which is a design decision rather than a fix. It is
also the less conservative direction — exclusion is the only step that can lose a
relevant answer, so widening it unattended seemed wrong. The fix, if you want it, is to
let `primary_zone` also match a FAQ section heading against a per-topic pattern.

### Smaller calls, all logged

- **A wrapped hyphen keeps its hyphen** (D-017). "compact mixed-" + "use" becomes
  "mixed-use", because we cannot tell a wrapped compound from a typesetter's
  hyphenation, and in this gazette the wrapped ones are compounds. Dropping it would
  rewrite "mixed-use" as "mixeduse" and break the keyword index.
- **A bad table fails the whole page, not just itself** (D-018). The clipping bands are
  computed from all of a page's tables at once, so mixing a converted table with a
  plain-text read of the same page would duplicate text.
- **`covers`, not `contains`, for point-in-polygon** (D-031). The planning zones tile
  Delhi with shared edges, so a point exactly on a boundary would otherwise belong to no
  zone at all.
- **A point outside Delhi gets a plain search, all three location steps off** (D-033).
  Strictly, exclusion would drop all 24 primary-zone chunks for such a point. That would
  be the wrong behaviour dressed as the right one — MPD-2047 does not apply in Gurugram,
  so filtering its TOD sections there answers a question nobody asked. Saying "this
  point is not in Delhi" belongs to the answering step on Day 4.
- **Exclusion filters the pools before the ranks are read**, and the pools are fetched
  twice as deep (60, used 30) so there is still a full pool to fuse. If a dropped chunk
  kept its rank slot, everything below it would lose fusion points for the presence of
  something not in the results.

### Two things about the DDA data you should know

- **The planning zones layer has 16 features, not 17.** Zone A — Old City, Walled City
  and the area outside it — is absent, so a point in the Walled City gets
  `planning_zone = None`. The plan's own 1.7.2 lists 17.
- **`LAND POOLING AREA` labels its `zone` field "L" for polygons inside planning zone
  K-I.** The land pooling zone and the planning zone are different letters and should
  not be compared. P_LP shows this: planning zone K-I, land pooling zone L.

---

## 4. The zone section mapping

`data/zone_sections.json`, committed:

```json
{
  "tod": ["4.2"],
  "hdc": ["4.3"],
  "zone_o": [],
  "land_pooling": ["4.1"]
}
```

A chunk is primary for a topic when any heading in its path is one of these numbers or
sits under one, so 4.2, 4.2.1 and 4.2.3.1 are all TOD. Only the plan's numbered chapters
are considered — a Delhi Jal Board section numbered 4.2 in the service plans is not the
TOD policy. See Guess 1 for why `zone_o` is empty.

## 5. The test points

`data/test_points.json`, committed. Computed from the polygons, not typed in, so they
stay right if the layers are re-downloaded.

| point | lat, lon | in Delhi | zone | tod | hdc | pooling | zone O | park | lda |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P_TOD | 28.63280, 77.21970 | yes | D | yes | - | - | - | - | - |
| P_HDC | 28.65953, 77.00665 | yes | K-I | - | yes | - | - | - | - |
| P_ZONEO | 28.67291, 77.24354 | yes | O | - | - | - | yes | - | - |
| P_LP | 28.67690, 77.02708 | yes | K-I | - | - | yes, L | - | - | - |
| P_PLAIN | 28.63997, 77.08899 | yes | G | - | - | - | - | - | - |
| P_OUT | 28.49500, 77.08900 | **no** | - | - | - | - | - | - | - |

Rajiv Chowk (28.6328, 77.2197) was tried first for P_TOD as the brief suggests and it
qualified — in a TOD zone and in none of the others — so it was kept, because you can
check a named landmark by eye and cannot check a point found by searching. P_ZONEO is
additionally required to be outside the Yamuna river polygon, so it is on the floodplain
rather than in the water.

## 6. Files created or changed

**New Python modules** — `app/cleaning.py`, `app/chunking.py`, `app/tagging.py`,
`app/indexing.py`, `app/retrieval.py`, `app/location.py`, `app/spatial.py`.

**New scripts** — `scripts/03_chunk.py`, `scripts/04_tag_zones.py`,
`scripts/05_build_index.py`, `scripts/06_fetch_layers.py`, `scripts/07_test_points.py`,
`scripts/search.py`, `scripts/day2_queries.py`, `scripts/day3_location_compare.py`.

**New tests** — `tests/test_cleaning.py`, `tests/test_chunking.py`,
`tests/test_tagging.py`, `tests/test_retrieval.py`, `tests/test_spatial.py`.

**Changed** — `app/config.py` (layer and index paths, the search and location settings),
`scripts/build_chapter_map.py` (lower-case labels), `data/chapter_map.json` (rebuilt),
`.gitignore`, `CLAUDE.md` (repo layout), `DECISIONS.md` (D-013 to D-036, 24 new entries), `pyproject.toml`
and `uv.lock` (seven dependencies).

**New committed data** — `data/zone_sections.json`, `data/test_points.json`,
`data/layers/manifest.json`.

**New generated, not committed** — `data/processed/chunks.jsonl`,
`data/processed/chunk_report.md`, `data/processed/chunk_sample.md`,
`data/processed/tag_report.md`, `data/processed/tag_sample.md`, `data/index/chroma/`,
`data/index/bm25.pkl`, `data/index/models/`, `data/layers/dda/*.geojson`,
`data/layers/dda/preview.html`.

**New committed reports** — `reports/day2_queries.md`,
`reports/day3_location_compare.md`, `reports/overnight_run.md`.

**Commits** (seven, none pushed):

```
day2-stage0: lowercase chapter labels, reports/ and layers/dda folders, day 2 dependencies
day2-stage1: clean pages and cut them into 702 chunks with tables as markdown
day2-stage2: tag chunks with zone topics, primary from headings and mentions from text
day2-stage3: build the dense Chroma index and the BM25 keyword index
day2-stage4: hybrid retrieval with RRF, search CLI and the eight day 2 queries
day2-stage5: fetch the DDA layers, add get_zones and six computed test points
day2-stage6: location-aware retrieval with exclusion, query expansion and boost
```

---

## 7. Morning checklist for Dhruv

Four files to read by hand, in this order. The first two are the ones that matter — if
the chunks are wrong, everything above them is wrong too.

```
# 1. 20 random chunks in full. Does each one say one thing? Is the clause whole?
#    Is the heading path right? Is the page range right?
code data/processed/chunk_sample.md

# 2. 30 tagged chunks. Is every matched phrase a real mention of that zone?
#    Where a chunk has a zone_primary, is it really a rule for that zone only
#    (because search is allowed to drop it for a point outside)?
code data/processed/tag_sample.md

# 3. The eight test queries, three modes each. Mark which ones answer the question.
code reports/day2_queries.md

# 4. Plain hybrid against location-aware search at the test points.
#    Look at A at P_HDC and B at P_ZONEO first; they show the biggest change.
code reports/day3_location_compare.md
```

Two more worth a glance:

```
# The counts: chunks per chapter, size buckets, every table that fell back, all warnings
code data/processed/chunk_report.md

# The map. Toggle each layer; click the six markers to see their get_zones result.
start data\layers\dda\preview.html
```

Then run the tests:

```
uv run pytest
```

Expected: **96 passed**, in under two seconds.

To rebuild anything from scratch, in this order (`03` must run before `04`, and both
before `05`):

```
uv run python scripts/03_chunk.py              # ~25s
uv run python scripts/04_tag_zones.py          # ~1s
uv run python scripts/05_build_index.py        # ~140s, the model is already cached
uv run python scripts/06_fetch_layers.py       # ~25s, needs the network
uv run python scripts/07_test_points.py        # ~1s
uv run python scripts/day2_queries.py          # ~3s
uv run python scripts/day3_location_compare.py # ~3s
```

Ad-hoc searching:

```
uv run python scripts/search.py "minimum plot size for a TOD project"
uv run python scripts/search.py "what FAR can I get here" --lat 28.6328 --lon 77.2197
```

**Two decisions want your answer**, both in section 3 above: whether Zone O should be
able to exclude (I say no, and 3.1.2 is the section you would add), and whether the
FAQ's policy sections should be able to exclude (I say it is a design call, and the
visible cost of leaving it is a TOD answer at the top of a plain plot's results).

**Nothing has been pushed.** When you are happy with the above:

```
git log --oneline -7     # the seven day-2 commits
git push
```
