# Plain hybrid against location-aware search

Generated 2026-10-20 by `scripts/day3_location_compare.py`.

Top 5 either way, 700 chunks indexed. The question is identical in both columns; the only difference is that the right-hand one knows where the user is standing.

Location-aware search does three things, with the settings in `app/config.py`:

1. **Exclusion** — a chunk whose `zone_primary` is a policy the point is *not* in is dropped. A chunk with no primary zone is never dropped, so the general norms in chapters 7 to 13 always stay in play.
2. **Query expansion** — the point's zone names are appended to the query text for both indexes, so a question with no zone words in it can still reach the right policy. **Only the four topics with a policy section of their own do this** (`tod`, `hdc`, `land_pooling`, `lda`), which is the same four that may exclude: Zone O and the Ridge name a place rather than a policy, and appending a place replaces the subject of the question instead of qualifying it (D-086).
3. **Boost** — a chunk whose `zone_primary` *or* `zone_mentions` matches the point's zones has its fused score multiplied by 1.5.

Two of the six topics can only do step 3. Zone O and the Ridge have no policy section of their own in MPD-2047, so no chunk ever carries them as a `zone_primary` and the exclusion step has nothing to find for them (D-037, D-069) — and for the same reason they no longer expand the query either (D-086). The three corridor policies and the LDA do have sections, so a point outside them can drop their rules and a point inside them expands towards their chapter.

`d3` is dense rank 3, `b1` is BM25 rank 1, **boosted** marks a chunk the boost applied to. Not judged here.

## Before and after D-086

On 20 October query expansion was scoped to the four topics that have a policy
section of their own, so a point in **Zone O** or on the **Ridge** now searches
with the user's own words and relies on the boost instead. Every other point is
untouched, and this table is the check on that claim rather than an assertion of
it: `before` widens `location.EXPANDS_QUERY` back out to all six topics.

| comparison | point | topics | query sent, before | top 5, before | top 5, now | same? |
| --- | --- | --- | --- | --- | --- | --- |
| A | P_TOD | tod | “What is the maximum ground coverage allowed on my plot? transit oriented development TOD zone” | `4.2.3@p753:0`, `Q13@p13:0`, `4.2.3@p752:1`, `4.2.3@p752:0`, `4.2.1:0` | `4.2.3@p753:0`, `Q13@p13:0`, `4.2.3@p752:1`, `4.2.3@p752:0`, `4.2.1:0` | **identical** |
| A | P_HDC | hdc | “What is the maximum ground coverage allowed on my plot? high density corridor HDC UER-II” | `4.3.3@p759:0`, `4.3.3@p758:0`, `Q1@p15:0`, `Q17@p16:0`, `4.3@p757:0` | `4.3.3@p759:0`, `4.3.3@p758:0`, `Q1@p15:0`, `Q17@p16:0`, `4.3@p757:0` | **identical** |
| A | P_PLAIN | (none) | “What is the maximum ground coverage allowed on my plot?” | `7.2.1@p814:0`, `Q4@p20:0`, `7.2.1@p813:0`, `4.6.6@p790:0`, `7.2.2@p815:0` | `7.2.1@p814:0`, `Q4@p20:0`, `7.2.1@p813:0`, `4.6.6@p790:0`, `7.2.2@p815:0` | **identical** |
| B | P_ZONEO | zone_o | “Can I construct a building here? Zone O Yamuna floodplain” | `3.1.2@p681:0`, `2:0`, `3@p25:1`, `5@p30:0`, `p1:0` | `Q4@p7:0`, `13.1.1:0`, `5.1.6@p800:0`, `Q5@p7:0`, `3.3.1@p701:0` | changed |
| C | P_LP | land_pooling | “What development rules apply to my land here? land pooling” | `Q18@p10:0`, `4.1.2:0`, `4.1@p746:0`, `Q7@p8:0`, `Q5@p8:0` | `Q18@p10:0`, `4.1.2:0`, `4.1@p746:0`, `Q7@p8:0`, `Q5@p8:0` | **identical** |
| D | P_TOD | tod | “What FAR can I get here? transit oriented development TOD zone” | `4.2@p750:0`, `4.2.4@p755:0`, `4.2.1:0`, `4.2.3@p751:0`, `3.6.1@p721:1` | `4.2@p750:0`, `4.2.4@p755:0`, `4.2.1:0`, `4.2.3@p751:0`, `3.6.1@p721:1` | **identical** |
| D | P_PLAIN | (none) | “What FAR can I get here?” | `13.2:0`, `11.1.3@p860:0`, `8.3.2@p830:0`, `p904:0`, `12.2.2@p874:0` | `13.2:0`, `11.1.3@p860:0`, `8.3.2@p830:0`, `p904:0`, `12.2.2@p874:0` | **identical** |
| E | P_RIDGE | ridge | “Can I build a house here? Ridge regional park Aravalli forest” | `10.1@p842:0`, `1.6.2@p657:0`, `Annexure 1@p937:0`, `10.2.1@p846:0`, `Annexure 1@p919:0` | `7.2.2@p815:0`, `Q3@p20:0`, `9.2:0`, `Annexure 22@p984:0`, `p911:1` | changed |
| E | P_LDA | lda | “Can I build a house here? low density area LDA farmhouse” | `4.4.3:0`, `4.4@p764:0`, `Q1@p18:0`, `3.4.2:0`, `Q4@p18:0` | `4.4.3:0`, `4.4@p764:0`, `Q1@p18:0`, `3.4.2:0`, `Q4@p18:0` | **identical** |

**2 of 9 point(s) changed**, and they are the two the change is about. The clause that prompted it, `MPD47_GAZETTE_EN:11.1.1@p854:0` for “Can a fuel station be built here?” at P_ZONEO, moved from rank 14 to **rank 1**; the measurement is in `reports/diagnosis_fuel_station.md`.

### What the change cost at those two points

Printing only the winners would be dishonest, so here is what left the top 5. `>200` means the clause is no longer anywhere in a 200-deep result list. The pattern is the same at both points and it is the mirror image of the fix: the expansion was **helping** whenever the question's own subject was the place, because then the appended words were a qualifier after all. These two questions are of that kind, and they pay for the ones that are not.

**B at P_ZONEO — “Can I construct a building here?”**

| clause | rank before | rank now | |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 1 | >200 | left the top 5 |
| `DHC_YAMUNA_20240708:2:0` | 2 | 9 | left the top 5 |
| `NGT_OA572_GNCTD_REPORT:3@p25:1` | 3 | >200 | left the top 5 |
| `NGT_OA572_GNCTD_REPORT:5@p30:0` | 4 | >200 | left the top 5 |
| `NGT_OA572_GNCTD_REPORT:p1:0` | 5 | >200 | left the top 5 |
| `MPD47_FAQ:Q4@p7:0` | >200 | 1 | new in the top 5 |
| `MPD47_GAZETTE_EN:13.1.1:0` | >200 | 2 | new in the top 5 |
| `MPD47_GAZETTE_EN:5.1.6@p800:0` | >200 | 3 | new in the top 5 |
| `MPD47_FAQ:Q5@p7:0` | >200 | 4 | new in the top 5 |
| `MPD47_GAZETTE_EN:3.3.1@p701:0` | >200 | 5 | new in the top 5 |

**E at P_RIDGE — “Can I build a house here?”**

| clause | rank before | rank now | |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 1 | >200 | left the top 5 |
| `MPD47_GAZETTE_EN:1.6.2@p657:0` | 2 | >200 | left the top 5 |
| `MPD47_GAZETTE_EN:Annexure 1@p937:0` | 3 | >200 | left the top 5 |
| `MPD47_GAZETTE_EN:10.2.1@p846:0` | 4 | >200 | left the top 5 |
| `MPD47_GAZETTE_EN:Annexure 1@p919:0` | 5 | >200 | left the top 5 |
| `MPD47_GAZETTE_EN:7.2.2@p815:0` | >200 | 1 | new in the top 5 |
| `MPD47_FAQ:Q3@p20:0` | 26 | 2 | new in the top 5 |
| `MPD47_GAZETTE_EN:9.2:0` | >200 | 3 | new in the top 5 |
| `MPD47_GAZETTE_EN:Annexure 22@p984:0` | 7 | 4 | new in the top 5 |
| `MPD47_GAZETTE_EN:p911:1` | 12 | 5 | new in the top 5 |

## A. “What is the maximum ground coverage allowed on my plot?”

### A at P_TOD — 28.6328, 77.2197

- planning zone D; in TOD zone
- `get_zones`: `{"inside_delhi": true, "planning_zone": "D", "tod": true, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q13@p13:0` — clause Q13, zone_primary `tod`, pages 13-13, [d1 b1 score 0.0328]
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
2. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, zone_primary `tod`, pages 753-754, [d5 b4 score 0.0310]
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However,...
3. `MPD47_GAZETTE_EN:7.2.1@p814:0` — clause 7.2.1, zone_primary `(none)`, pages 814-815, [d3 b7 score 0.0308]
   - (vi) Provision of stilt shall be mandatory for plots with area above 100 sqm up to 750 sqm. For plots above 750 sqm area...
4. `MPD47_FAQ:Q4@p20:0` — clause Q4, zone_primary `(none)`, pages 20-20, [d7 b9 score 0.0294]
   - Q4. What norms will be applicable on the ISR Project? The rehabilitation plot area shall not be less than 40% of the tot...
5. `MPD47_FAQ:Q16@p16:0` — clause Q16, zone_primary `hdc`, pages 16-16, [d4 b15 score 0.0290]
   - Q16. What are the ground coverage limits for different uses? Maximum ground coverage is 40% for Residential, Commercial,...

**location-aware hybrid**

- query sent: “What is the maximum ground coverage allowed on my plot? transit oriented development TOD zone”
- expansion terms added: transit oriented development TOD zone
- excluded 17 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, ridge, zone_o
- boosted 27 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, zone_primary `tod`, pages 753-754, [d1 b1 **boosted** score 0.0492]
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However,...
2. `MPD47_FAQ:Q13@p13:0` — clause Q13, zone_primary `tod`, pages 13-13, [d2 b3 **boosted** score 0.0480]
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
3. `MPD47_GAZETTE_EN:4.2.3@p752:1` — clause 4.2.3, zone_primary `tod`, pages 752-753, [d3 b5 **boosted** score 0.0469]
   - (b) The permissible mix of uses for each plot in a TOD Zone shall be as below: i. A minimum 65% of the total permissible...
4. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, zone_primary `tod`, pages 752-752, [d9 b2 **boosted** score 0.0459]
   - (iv) FAR (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notifie...
5. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, zone_primary `tod`, pages 750-751, [d5 b6 **boosted** score 0.0458]
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned...

- new in the top 5: `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.1:0`
- dropped out of the top 5: `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_FAQ:Q16@p16:0`

### A at P_HDC — 28.659532, 77.006649

- planning zone K-I; in high density corridor
- `get_zones`: `{"inside_delhi": true, "planning_zone": "K-I", "tod": false, "hdc": true, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q13@p13:0` — clause Q13, zone_primary `tod`, pages 13-13, [d1 b1 score 0.0328]
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
2. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, zone_primary `tod`, pages 753-754, [d5 b4 score 0.0310]
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However,...
3. `MPD47_GAZETTE_EN:7.2.1@p814:0` — clause 7.2.1, zone_primary `(none)`, pages 814-815, [d3 b7 score 0.0308]
   - (vi) Provision of stilt shall be mandatory for plots with area above 100 sqm up to 750 sqm. For plots above 750 sqm area...
4. `MPD47_FAQ:Q4@p20:0` — clause Q4, zone_primary `(none)`, pages 20-20, [d7 b9 score 0.0294]
   - Q4. What norms will be applicable on the ISR Project? The rehabilitation plot area shall not be less than 40% of the tot...
5. `MPD47_FAQ:Q16@p16:0` — clause Q16, zone_primary `hdc`, pages 16-16, [d4 b15 score 0.0290]
   - Q16. What are the ground coverage limits for different uses? Maximum ground coverage is 40% for Residential, Commercial,...

**location-aware hybrid**

- query sent: “What is the maximum ground coverage allowed on my plot? high density corridor HDC UER-II”
- expansion terms added: high density corridor HDC UER-II
- excluded 18 chunk(s) whose primary zone is one of: land_pooling, lda, ridge, tod, zone_o
- boosted 26 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.3.3@p759:0` — clause 4.3.3, zone_primary `hdc`, pages 759-760, [d1 b4 **boosted** score 0.0480]
   - (f) Vertical mix of uses shall be allowed except in plots earmarked for Warehousing/Logistics use. Separate entry/exits ...
2. `MPD47_GAZETTE_EN:4.3.3@p758:0` — clause 4.3.3, zone_primary `hdc`, pages 758-759, [d7 b2 **boosted** score 0.0466]
   - 4.3.3 HDC Norms (i) Participation in the HDC Policy is voluntary. In case of HDC Plots, the land use shall be as per the...
3. `MPD47_FAQ:Q1@p15:0` — clause Q1, zone_primary `hdc`, pages 15-15, [d14 b1 **boosted** score 0.0449]
   - Q1. What is a High Density Corridor (HDC) Zone? The HDC Zone is an area comprising of compact, mixed-use, and high-densi...
4. `MPD47_FAQ:Q17@p16:0` — clause Q17, zone_primary `hdc`, pages 16-16, [d3 b12 **boosted** score 0.0446]
   - Q17. Is relaxation in Ground Coverage provided? Relaxations in ground coverage for HDC Projects that are not able to uti...
5. `MPD47_GAZETTE_EN:4.3@p757:0` — clause 4.3, zone_primary `hdc`, pages 757-757, [d12 b3 **boosted** score 0.0446]
   - 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT High Density Corridor (HDC) Zone is envisioned to optimize land use efficiency by ...

- new in the top 5: `MPD47_GAZETTE_EN:4.3.3@p759:0`, `MPD47_GAZETTE_EN:4.3.3@p758:0`, `MPD47_FAQ:Q1@p15:0`, `MPD47_FAQ:Q17@p16:0`, `MPD47_GAZETTE_EN:4.3@p757:0`
- dropped out of the top 5: `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_FAQ:Q16@p16:0`

### A at P_PLAIN — 28.639973, 77.088994

- planning zone G; in none of the six policy zones
- `get_zones`: `{"inside_delhi": true, "planning_zone": "G", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q13@p13:0` — clause Q13, zone_primary `tod`, pages 13-13, [d1 b1 score 0.0328]
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
2. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, zone_primary `tod`, pages 753-754, [d5 b4 score 0.0310]
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However,...
3. `MPD47_GAZETTE_EN:7.2.1@p814:0` — clause 7.2.1, zone_primary `(none)`, pages 814-815, [d3 b7 score 0.0308]
   - (vi) Provision of stilt shall be mandatory for plots with area above 100 sqm up to 750 sqm. For plots above 750 sqm area...
4. `MPD47_FAQ:Q4@p20:0` — clause Q4, zone_primary `(none)`, pages 20-20, [d7 b9 score 0.0294]
   - Q4. What norms will be applicable on the ISR Project? The rehabilitation plot area shall not be less than 40% of the tot...
5. `MPD47_FAQ:Q16@p16:0` — clause Q16, zone_primary `hdc`, pages 16-16, [d4 b15 score 0.0290]
   - Q16. What are the ground coverage limits for different uses? Maximum ground coverage is 40% for Residential, Commercial,...

**location-aware hybrid**

- query sent: “What is the maximum ground coverage allowed on my plot?”
- expansion terms added: (none)
- excluded 30 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, ridge, tod, zone_o
- boosted 0 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:7.2.1@p814:0` — clause 7.2.1, zone_primary `(none)`, pages 814-815, [d1 b4 score 0.0320]
   - (vi) Provision of stilt shall be mandatory for plots with area above 100 sqm up to 750 sqm. For plots above 750 sqm area...
2. `MPD47_FAQ:Q4@p20:0` — clause Q4, zone_primary `(none)`, pages 20-20, [d3 b6 score 0.0310]
   - Q4. What norms will be applicable on the ISR Project? The rehabilitation plot area shall not be less than 40% of the tot...
3. `MPD47_GAZETTE_EN:7.2.1@p813:0` — clause 7.2.1, zone_primary `(none)`, pages 813-814, [d2 b10 score 0.0304]
   - 7.2 Development Control Norms (DCN) 7.2.1 Plotted Housing | Use Premise | Plot Area (sqm) | | Max. Ground Coverage (%) |...
4. `MPD47_GAZETTE_EN:4.6.6@p790:0` — clause 4.6.6, zone_primary `(none)`, pages 790-790, [d5 b8 score 0.0301]
   - (vi) Development norms applicable to godowns are as follows: | Sl. No. | Plot Size (sqm) | Maximum Ground Coverage (%) |...
5. `MPD47_GAZETTE_EN:7.2.2@p815:0` — clause 7.2.2, zone_primary `(none)`, pages 815-816, [d18 b1 score 0.0292]
   - 7.2.2 Group Housing, Affordable Rental Housing Complex (ARHC), Studio Apartment, State Bhawan/State Guest House and Host...

- new in the top 5: `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:4.6.6@p790:0`, `MPD47_GAZETTE_EN:7.2.2@p815:0`
- dropped out of the top 5: `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_FAQ:Q16@p16:0`

## B. “Can I construct a building here?”

### B at P_ZONEO — 28.672913, 77.243545

- planning zone O; in Zone O (Yamuna floodplain)
- `get_zones`: `{"inside_delhi": true, "planning_zone": "O", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": true, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q4@p7:0` — clause Q4, zone_primary `(none)`, pages 7-7, [d2 b6 score 0.0313]
   - Q4. A heritage building can be used for what other purposes? Adaptive reuse of heritage buildings for cultural centres, ...
2. `MPD47_GAZETTE_EN:5.1.6@p800:0` — clause 5.1.6, zone_primary `(none)`, pages 800-800, [d6 b3 score 0.0310]
   - (xii) Every applicant seeking sanction or regularisation of additional FAR and/or height shall submit a certificate of s...
3. `MPD47_GAZETTE_EN:13.1.1:0` — clause 13.1.1, zone_primary `(none)`, pages 885-885, [d1 b9 score 0.0309]
   - 13.1 Other Controls 13.1.1 Tall Building Tall buildings, i.e. structures having more than 100 floors, shall be designed ...
4. `MPD47_FAQ:Q5@p7:0` — clause Q5, zone_primary `(none)`, pages 7-7, [d3 b11 score 0.0300]
   - Q5. Can changes be made to the façade of a heritage building? The façade and important architectural features must be pr...
5. `MPD47_FAQ:Q23:0` — clause Q23, zone_primary `hdc`, pages 17-17, [d12 b4 score 0.0295]
   - Q23. How are building plans and project proposals submitted? Proposals must be submitted through the Online Building Per...

**location-aware hybrid**

- query sent: “Can I construct a building here?”
- expansion terms added: (none)
- excluded 13 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, ridge, tod
- boosted 3 chunk(s) in the pool

1. `MPD47_FAQ:Q4@p7:0` — clause Q4, zone_primary `(none)`, pages 7-7, [d2 b4 score 0.0318]
   - Q4. A heritage building can be used for what other purposes? Adaptive reuse of heritage buildings for cultural centres, ...
2. `MPD47_GAZETTE_EN:13.1.1:0` — clause 13.1.1, zone_primary `(none)`, pages 885-885, [d1 b6 score 0.0315]
   - 13.1 Other Controls 13.1.1 Tall Building Tall buildings, i.e. structures having more than 100 floors, shall be designed ...
3. `MPD47_GAZETTE_EN:5.1.6@p800:0` — clause 5.1.6, zone_primary `(none)`, pages 800-800, [d6 b3 score 0.0310]
   - (xii) Every applicant seeking sanction or regularisation of additional FAR and/or height shall submit a certificate of s...
4. `MPD47_FAQ:Q5@p7:0` — clause Q5, zone_primary `(none)`, pages 7-7, [d3 b8 score 0.0306]
   - Q5. Can changes be made to the façade of a heritage building? The façade and important architectural features must be pr...
5. `MPD47_GAZETTE_EN:3.3.1@p701:0` — clause 3.3.1, zone_primary `(none)`, pages 701-702, [d8 b11 score 0.0288]
   - (b) Adaptive Reuse: Adaptive reuse of heritage buildings is permitted in conformity with the historic context. Compatibl...

- new in the top 5: `MPD47_GAZETTE_EN:3.3.1@p701:0`
- dropped out of the top 5: `MPD47_FAQ:Q23:0`

## C. “What development rules apply to my land here?”

### C at P_LP — 28.676901, 77.027085

- planning zone K-I; in land pooling area L
- `get_zones`: `{"inside_delhi": true, "planning_zone": "K-I", "tod": false, "hdc": false, "land_pooling": true, "land_pooling_zone": "L", "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_GAZETTE_EN:4.5.1:0` — clause 4.5.1, zone_primary `(none)`, pages 770-770, [d5 b8 score 0.0301]
   - 4.5.1 Applicability Provisions of this Chapter shall apply to all developed areas in the city, except: (i) Urban village...
2. `MPD47_GAZETTE_EN:9.3.1:0` — clause 9.3.1, zone_primary `(none)`, pages 839-839, [d17 b14 score 0.0265]
   - 9.3.1 Land Distribution in New Industrial Area (i) For new industrial area/township development, 50-70% of the total lan...
3. `MPD47_GAZETTE_EN:4.1.2:0` — clause 4.1.2, zone_primary `land_pooling`, pages 747-748, [d1 score 0.0164]
   - 4.1.2 Guiding Principles (i) Preparation of schemes in the land pooling areas shall be taken up by adopting any of the f...
4. `MPD47_GAZETTE_EN:4.4@p1006:0` — clause 4.4, zone_primary `(none)`, pages 1006-1006, [b1 score 0.0164]
   - 4.4. Septage Management Rules 2018 DJB has made efforts to implement the septage management rules in Delhi ‘Delhi Water ...
5. `MPD47_GAZETTE_EN:4.3@p1092:1` — clause 4.3, zone_primary `(none)`, pages 1092-1093, [b2 score 0.0161]
   - 1. City Level & Ward-level waste generator mapping and compliance monitoring is being undertaken in collaboration with I...

**location-aware hybrid**

- query sent: “What development rules apply to my land here? land pooling”
- expansion terms added: land pooling
- excluded 16 chunk(s) whose primary zone is one of: hdc, lda, ridge, tod, zone_o
- boosted 30 chunk(s) in the pool

1. `MPD47_FAQ:Q18@p10:0` — clause Q18, zone_primary `land_pooling`, pages 10-10, [d5 b2 **boosted** score 0.0473]
   - Q18. I have built-up structure on my land for which the plan is approved / sanctioned by the Govt. agencies. If I do not...
2. `MPD47_GAZETTE_EN:4.1.2:0` — clause 4.1.2, zone_primary `land_pooling`, pages 747-748, [d3 b4 **boosted** score 0.0472]
   - 4.1.2 Guiding Principles (i) Preparation of schemes in the land pooling areas shall be taken up by adopting any of the f...
3. `MPD47_GAZETTE_EN:4.1@p746:0` — clause 4.1, zone_primary `land_pooling`, pages 746-746, [d2 b6 **boosted** score 0.0469]
   - 4.1 LAND POOLING Land Pooling Policy is a new framework for urban development, wherein the private entity/ landowners wi...
4. `MPD47_FAQ:Q7@p8:0` — clause Q7, zone_primary `land_pooling`, pages 8-9, [d1 b10 **boosted** score 0.0460]
   - Q7. What development model shall be applicable in the land pooling areas? Preparation of schemes in the land pooling are...
5. `MPD47_FAQ:Q5@p8:0` — clause Q5, zone_primary `land_pooling`, pages 8-8, [d7 b7 **boosted** score 0.0448]
   - Q5. What is the minimum land size to participate in Land Pooling? Land parcels of any size can be brought under pooling,...

- new in the top 5: `MPD47_FAQ:Q18@p10:0`, `MPD47_GAZETTE_EN:4.1@p746:0`, `MPD47_FAQ:Q7@p8:0`, `MPD47_FAQ:Q5@p8:0`
- dropped out of the top 5: `MPD47_GAZETTE_EN:4.5.1:0`, `MPD47_GAZETTE_EN:9.3.1:0`, `MPD47_GAZETTE_EN:4.4@p1006:0`, `MPD47_GAZETTE_EN:4.3@p1092:1`

## D. “What FAR can I get here?”

### D at P_TOD — 28.6328, 77.2197

- planning zone D; in TOD zone
- `get_zones`: `{"inside_delhi": true, "planning_zone": "D", "tod": true, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q8@p12:0` — clause Q8, zone_primary `tod`, pages 12-12, [d4 b13 score 0.0293]
   - Q8. What is the permissible FAR under the Policy? i. Base FAR shall be 400 subject to payment of TOD charges. ii. Maximu...
2. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, zone_primary `tod`, pages 752-752, [d11 b9 score 0.0286]
   - (iv) FAR (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notifie...
3. `MPD47_FAQ:Q15@p10:0` — clause Q15, zone_primary `land_pooling`, pages 10-10, [d3 b20 score 0.0284]
   - Q15. What will be the FAR applicable in the Scheme area? The FAR of each plot (except utilities & recreation) within a s...
4. `MPD47_FAQ:Q13@p16:0` — clause Q13, zone_primary `hdc`, pages 16-16, [d2 b22 score 0.0283]
   - Q13. What is the maximum permissible FAR for Residential, Commercial, and PSP uses? The maximum permissible FAR for Resi...
5. `MPD47_FAQ:Q14@p16:0` — clause Q14, zone_primary `hdc`, pages 16-16, [d1 b27 score 0.0279]
   - Q14. What is the maximum permissible FAR for Warehousing and Logistics uses? Warehousing and logistic nodes along Master...

**location-aware hybrid**

- query sent: “What FAR can I get here? transit oriented development TOD zone”
- expansion terms added: transit oriented development TOD zone
- excluded 7 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, ridge, zone_o
- boosted 34 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.2@p750:0` — clause 4.2, zone_primary `tod`, pages 750-750, [d1 b2 **boosted** score 0.0488]
   - 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) Transit-Oriented Development (TOD) is an innovative urban paradigm that involves ...
2. `MPD47_GAZETTE_EN:4.2.4@p755:0` — clause 4.2.4, zone_primary `tod`, pages 755-756, [d8 b1 **boosted** score 0.0466]
   - (e) The TOD Project proposal shall comply with mandatory sustainability provisions/Green Building Norms given in the pre...
3. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, zone_primary `tod`, pages 750-751, [d2 b7 **boosted** score 0.0466]
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned...
4. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, zone_primary `tod`, pages 751-752, [d7 b4 **boosted** score 0.0458]
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand su...
5. `MPD47_GAZETTE_EN:3.6.1@p721:1` — clause 3.6.1, zone_primary `(none)`, pages 721-723, [d4 b9 **boosted** score 0.0452]
   - (j) In order to improve the utilisation of public transport, concerned transit agencies may consider the following: i. T...

- new in the top 5: `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`
- dropped out of the top 5: `MPD47_FAQ:Q8@p12:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_FAQ:Q15@p10:0`, `MPD47_FAQ:Q13@p16:0`, `MPD47_FAQ:Q14@p16:0`

### D at P_PLAIN — 28.639973, 77.088994

- planning zone G; in none of the six policy zones
- `get_zones`: `{"inside_delhi": true, "planning_zone": "G", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q8@p12:0` — clause Q8, zone_primary `tod`, pages 12-12, [d4 b13 score 0.0293]
   - Q8. What is the permissible FAR under the Policy? i. Base FAR shall be 400 subject to payment of TOD charges. ii. Maximu...
2. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, zone_primary `tod`, pages 752-752, [d11 b9 score 0.0286]
   - (iv) FAR (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notifie...
3. `MPD47_FAQ:Q15@p10:0` — clause Q15, zone_primary `land_pooling`, pages 10-10, [d3 b20 score 0.0284]
   - Q15. What will be the FAR applicable in the Scheme area? The FAR of each plot (except utilities & recreation) within a s...
4. `MPD47_FAQ:Q13@p16:0` — clause Q13, zone_primary `hdc`, pages 16-16, [d2 b22 score 0.0283]
   - Q13. What is the maximum permissible FAR for Residential, Commercial, and PSP uses? The maximum permissible FAR for Resi...
5. `MPD47_FAQ:Q14@p16:0` — clause Q14, zone_primary `hdc`, pages 16-16, [d1 b27 score 0.0279]
   - Q14. What is the maximum permissible FAR for Warehousing and Logistics uses? Warehousing and logistic nodes along Master...

**location-aware hybrid**

- query sent: “What FAR can I get here?”
- expansion terms added: (none)
- excluded 34 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, ridge, tod, zone_o
- boosted 0 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:13.2:0` — clause 13.2, zone_primary `(none)`, pages 886-887, [d1 b15 score 0.0297]
   - 13.2 Norms for Data Centre Data centre shall be permitted in Industrial, Commercial and PSP use zone with following norm...
2. `MPD47_GAZETTE_EN:11.1.3@p860:0` — clause 11.1.3, zone_primary `(none)`, pages 860-860, [d5 b10 score 0.0297]
   - | Commerce | | | | | --- | --- | --- | --- | | Convenience Shopping Centre/ Local Shopping Centre | 2.0 ECS/100 sqm of F...
3. `MPD47_GAZETTE_EN:8.3.2@p830:0` — clause 8.3.2, zone_primary `(none)`, pages 830-831, [d3 b14 score 0.0294]
   - 8.3.2 Development Control Norms (DCN) (i) Hotel: | Sl. No. | Use Premise | Max. Ground Coverage (%) | Max. FAR | Height ...
4. `MPD47_GAZETTE_EN:p904:0` — clause (none), zone_primary `(none)`, pages 904-905, [d9 b13 score 0.0282]
   - DEFINITIONS Active frontage: A street stretch where there is an active engagement through visual/physical permeability b...
5. `MPD47_GAZETTE_EN:12.2.2@p874:0` — clause 12.2.2, zone_primary `(none)`, pages 874-874, [d18 b12 score 0.0267]
   - (ix) In case of School minimum 15% of the permissible FAR shall be utilised for developing infrastructure for extra-curr...

- new in the top 5: `MPD47_GAZETTE_EN:13.2:0`, `MPD47_GAZETTE_EN:11.1.3@p860:0`, `MPD47_GAZETTE_EN:8.3.2@p830:0`, `MPD47_GAZETTE_EN:p904:0`, `MPD47_GAZETTE_EN:12.2.2@p874:0`
- dropped out of the top 5: `MPD47_FAQ:Q8@p12:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_FAQ:Q15@p10:0`, `MPD47_FAQ:Q13@p16:0`, `MPD47_FAQ:Q14@p16:0`

## E. “Can I build a house here?”

### E at P_RIDGE — 28.427902, 77.207749

- planning zone J; in Ridge / regional park
- `get_zones`: `{"inside_delhi": true, "planning_zone": "J", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": true, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q10@p12:0` — clause Q10, zone_primary `tod`, pages 12-12, [d5 b6 score 0.0305]
   - Q10. What kind of development is allowed under TOD Policy? The permissible mix of uses are as follows: i. Minimum 65%: F...
2. `MPD47_GAZETTE_EN:7.2.2@p815:0` — clause 7.2.2, zone_primary `(none)`, pages 815-816, [d28 b4 score 0.0270]
   - 7.2.2 Group Housing, Affordable Rental Housing Complex (ARHC), Studio Apartment, State Bhawan/State Guest House and Host...
3. `MPD47_FAQ:Q15@p16:0` — clause Q15, zone_primary `hdc`, pages 16-16, [d1 score 0.0164]
   - Q15. Is affordable housing mandatory in HDC developments? Yes, 20% of the permissible FAR must be utilized for affordabl...
4. `MPD47_FAQ:Q3@p20:0` — clause Q3, zone_primary `(none)`, pages 20-20, [b1 score 0.0164]
   - Q3. Who will develop the project? ISR projects will be built on Public-Private Partnership (PPP) basis — a private devel...
5. `MPD47_FAQ:Q18@p10:0` — clause Q18, zone_primary `land_pooling`, pages 10-10, [d2 score 0.0161]
   - Q18. I have built-up structure on my land for which the plan is approved / sanctioned by the Govt. agencies. If I do not...

**location-aware hybrid**

- query sent: “Can I build a house here?”
- expansion terms added: (none)
- excluded 13 chunk(s) whose primary zone is one of: hdc, land_pooling, lda, tod, zone_o
- boosted 4 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:7.2.2@p815:0` — clause 7.2.2, zone_primary `(none)`, pages 815-816, [d20 b4 score 0.0281]
   - 7.2.2 Group Housing, Affordable Rental Housing Complex (ARHC), Studio Apartment, State Bhawan/State Guest House and Host...
2. `MPD47_FAQ:Q3@p20:0` — clause Q3, zone_primary `(none)`, pages 20-20, [d27 b1 score 0.0279]
   - Q3. Who will develop the project? ISR projects will be built on Public-Private Partnership (PPP) basis — a private devel...
3. `MPD47_GAZETTE_EN:9.2:0` — clause 9.2, zone_primary `(none)`, pages 838-838, [d9 **boosted** score 0.0217]
   - 9.2 Household Industries Industrial activities (listed in Annexure 9a and 9b) shall be permitted as Household Industries...
4. `MPD47_GAZETTE_EN:Annexure 22@p984:0` — clause Annexure 22, zone_primary `(none)`, pages 984-984, [b14 **boosted** score 0.0203]
   - Annexure 22: Land Use, Use Zone and Use Premise | Land Use | Use Zone | | Use Premise | | --- | --- | --- | --- | | Resi...
5. `MPD47_GAZETTE_EN:p911:1` — clause (none), zone_primary `(none)`, pages 911-912, [b15 **boosted** score 0.0200]
   - Personnel Service Shop: A premise equivalent of retail shop providing personnel services like tailor, barber, etc. Plane...

- new in the top 5: `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_GAZETTE_EN:p911:1`
- dropped out of the top 5: `MPD47_FAQ:Q10@p12:0`, `MPD47_FAQ:Q15@p16:0`, `MPD47_FAQ:Q18@p10:0`

### E at P_LDA — 28.608034, 76.903849

- planning zone L; in low density area
- `get_zones`: `{"inside_delhi": true, "planning_zone": "L", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": true}`

**plain hybrid**

1. `MPD47_FAQ:Q10@p12:0` — clause Q10, zone_primary `tod`, pages 12-12, [d5 b6 score 0.0305]
   - Q10. What kind of development is allowed under TOD Policy? The permissible mix of uses are as follows: i. Minimum 65%: F...
2. `MPD47_GAZETTE_EN:7.2.2@p815:0` — clause 7.2.2, zone_primary `(none)`, pages 815-816, [d28 b4 score 0.0270]
   - 7.2.2 Group Housing, Affordable Rental Housing Complex (ARHC), Studio Apartment, State Bhawan/State Guest House and Host...
3. `MPD47_FAQ:Q15@p16:0` — clause Q15, zone_primary `hdc`, pages 16-16, [d1 score 0.0164]
   - Q15. Is affordable housing mandatory in HDC developments? Yes, 20% of the permissible FAR must be utilized for affordabl...
4. `MPD47_FAQ:Q3@p20:0` — clause Q3, zone_primary `(none)`, pages 20-20, [b1 score 0.0164]
   - Q3. Who will develop the project? ISR projects will be built on Public-Private Partnership (PPP) basis — a private devel...
5. `MPD47_FAQ:Q18@p10:0` — clause Q18, zone_primary `land_pooling`, pages 10-10, [d2 score 0.0161]
   - Q18. I have built-up structure on my land for which the plan is approved / sanctioned by the Govt. agencies. If I do not...

**location-aware hybrid**

- query sent: “Can I build a house here? low density area LDA farmhouse”
- expansion terms added: low density area LDA farmhouse
- excluded 20 chunk(s) whose primary zone is one of: hdc, land_pooling, ridge, tod, zone_o
- boosted 25 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.4.3:0` — clause 4.4.3, zone_primary `lda`, pages 766-767, [d1 b1 **boosted** score 0.0492]
   - 4.4.3 Development Control Norms for plots in Low Density Area (LDA) | | MINIMUM | | | | --- | --- | --- | --- | | USE | ...
2. `MPD47_GAZETTE_EN:4.4@p764:0` — clause 4.4, zone_primary `lda`, pages 764-764, [d2 b2 **boosted** score 0.0484]
   - 4.4 LOW DENSITY AREA (LDA) Low Density Area shall comprise the areas within the depth of one peripheral village revenue ...
3. `MPD47_FAQ:Q1@p18:0` — clause Q1, zone_primary `lda`, pages 18-18, [d5 b3 **boosted** score 0.0469]
   - Q1. What is LDA under MPD-2047, and where does it apply? Low Density Area (LDA) in MPD-2047 comprises areas within the d...
4. `MPD47_GAZETTE_EN:3.4.2:0` — clause 3.4.2, zone_primary `(none)`, pages 708-708, [d3 b5 **boosted** score 0.0469]
   - 3.4.2 Housing in Greenfield Areas (i) Housing in Land Pooling area/TOD zone: Development in the land pooling areas and T...
5. `MPD47_FAQ:Q4@p18:0` — clause Q4, zone_primary `lda`, pages 18-18, [d4 b4 **boosted** score 0.0469]
   - Q4. What activities besides residential use are permitted on plots in Low Density Area? The activities permitted under e...

- new in the top 5: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_FAQ:Q4@p18:0`
- dropped out of the top 5: `MPD47_FAQ:Q10@p12:0`, `MPD47_GAZETTE_EN:7.2.2@p815:0`, `MPD47_FAQ:Q15@p16:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_FAQ:Q18@p10:0`
