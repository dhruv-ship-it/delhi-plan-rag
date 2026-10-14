# Day 3: plain hybrid against location-aware search (v2)

Generated 2026-10-15 by `scripts/day3_location_compare.py`.

> **What changed since v1.** `reports/day3_location_compare.md` was run before the FAQ
> could carry a `zone_primary`. Last night's report flagged that gap (D-035): the FAQ's
> policy sections are headings, not numbered sections, so a TOD FAQ answer could never
> be excluded. `data/zone_sections.json` now has a second half that matches FAQ section
> headings on their words (D-038), which tagged 64 more chunks as primary — 29 tod,
> 36 hdc and 23 land_pooling in total, up from 10, 9 and 5.

## Before and after: the P_PLAIN ground-coverage case

This is the case v1 got visibly wrong. P_PLAIN is an ordinary plot in planning zone G,
in none of the four policy zones, and the question is "What is the maximum ground
coverage allowed on my plot?"

| | v1 (last night) | v2 (now) |
| --- | --- | --- |
| chunks excluded | 7 | 23 |
| rank 1 | `MPD47_FAQ:Q13@p13:0` — "maximum ground coverage permissible for a **TOD Plot**... 40%" | `MPD47_GAZETTE_EN:7.2.1@p814:0` — chapter 7 plotted-housing norms |
| rank 2 | `MPD47_GAZETTE_EN:7.2.1@p814:0` | `MPD47_FAQ:Q4@p20:0` |
| TOD content in the top 5 | yes, at rank 1 | none |

In v1 the gazette's own TOD ground-coverage clause *was* correctly dropped for this
point, but the FAQ's version of the same rule sailed through and took rank 1, so the top
answer for a plain plot was a rule that does not apply to it. In v2 the TOD FAQ section
carries `zone_primary = tod`, so it is excluded along with the gazette clause, and the
top result is 7.2.1 Plotted Housing — the chapter that actually governs that plot. The
new rank 3, `4.6.6@p790`, is a ground-coverage table with no primary zone, which is the
safety catch working as intended: general norms are never dropped.

The cost of the change is that exclusion is now stronger, so a mis-tagged FAQ section
would lose more. That is why only an explicit topic name in the heading counts: the five
generic sections ("FAQs - GENERIC", the DCN section, Heritage, LDA, Slum and JJ
Clusters) are still untagged and can never be excluded. The full list of headings and
what each was tagged as is in `data/processed/tag_report.md`.

Top 5 either way, 702 chunks indexed. The question is identical in both columns; the only difference is that the right-hand one knows where the user is standing.

Location-aware search does three things, with the settings in `app/config.py`:

1. **Exclusion** — a chunk whose `zone_primary` is a policy the point is *not* in is dropped. A chunk with no primary zone is never dropped, so the general norms in chapters 7 to 13 always stay in play.
2. **Query expansion** — the point's zone names are appended to the query text for both indexes, so a question with no zone words in it can still reach the right policy.
3. **Boost** — a chunk whose `zone_primary` *or* `zone_mentions` matches the point's zones has its fused score multiplied by 1.5.

`d3` is dense rank 3, `b1` is BM25 rank 1, **boosted** marks a chunk the boost applied to. Not judged here.

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
- excluded 10 chunk(s) whose primary zone is one of: hdc, land_pooling, zone_o
- boosted 23 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.2.3@p753:0` — clause 4.2.3, zone_primary `tod`, pages 753-754, [d1 b1 **boosted** score 0.0492]
   - (v) Ground Coverage: Maximum ground coverage of 40% shall be permitted in the proposed development on TOD Plot. However,...
2. `MPD47_FAQ:Q13@p13:0` — clause Q13, zone_primary `tod`, pages 13-13, [d2 b3 **boosted** score 0.0480]
   - Q13. What is the maximum ground coverage permissible for a TOD Plot? Maximum permissible ground coverage is 40%.
3. `MPD47_GAZETTE_EN:4.2.3@p752:1` — clause 4.2.3, zone_primary `tod`, pages 752-753, [d3 b5 **boosted** score 0.0469]
   - (b) The permissible mix of uses for each plot in a TOD Zone shall be as below: i. A minimum 65% of the total permissible...
4. `MPD47_GAZETTE_EN:4.2.3@p752:0` — clause 4.2.3, zone_primary `tod`, pages 752-752, [d8 b2 **boosted** score 0.0463]
   - (a) FAR of TOD Plot shall be as follows: i. Base FAR shall be 400 subject to payment of TOD charges, as notified from ti...
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
- excluded 10 chunk(s) whose primary zone is one of: land_pooling, tod, zone_o
- boosted 24 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.3.3@p759:0` — clause 4.3.3, zone_primary `hdc`, pages 759-760, [d1 b4 **boosted** score 0.0480]
   - (f) Vertical mix of uses shall be allowed except in plots earmarked for Warehousing/Logistics use. Separate entry/exits ...
2. `MPD47_GAZETTE_EN:4.3.3@p758:0` — clause 4.3.3, zone_primary `hdc`, pages 758-759, [d8 b2 **boosted** score 0.0463]
   - 4.3.3 HDC Norms (i) Participation in the HDC Policy is voluntary. In case of HDC Plots, the land use shall be as per the...
3. `MPD47_FAQ:Q1@p15:0` — clause Q1, zone_primary `hdc`, pages 15-15, [d16 b1 **boosted** score 0.0443]
   - Q1. What is a High Density Corridor (HDC) Zone? The HDC Zone is an area comprising of compact, mixed-use, and high-densi...
4. `MPD47_FAQ:Q17@p16:0` — clause Q17, zone_primary `hdc`, pages 16-16, [d4 b12 **boosted** score 0.0443]
   - Q17. Is relaxation in Ground Coverage provided? Relaxations in ground coverage for HDC Projects that are not able to uti...
5. `MPD47_GAZETTE_EN:1.7.1@p666:0` — clause 1.7.1, zone_primary `(none)`, pages 666-666, [d10 b6 **boosted** score 0.0442]
   - (d) High Density Corridor (HDC) Zone: HDC Zones, covering approximately 20 sq. km along the executed stretch of the Urba...

- new in the top 5: `MPD47_GAZETTE_EN:4.3.3@p759:0`, `MPD47_GAZETTE_EN:4.3.3@p758:0`, `MPD47_FAQ:Q1@p15:0`, `MPD47_FAQ:Q17@p16:0`, `MPD47_GAZETTE_EN:1.7.1@p666:0`
- dropped out of the top 5: `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_FAQ:Q16@p16:0`

### A at P_PLAIN — 28.639973, 77.088994

- planning zone G; in none of the four policy zones
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
- excluded 23 chunk(s) whose primary zone is one of: hdc, land_pooling, tod, zone_o
- boosted 0 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:7.2.1@p814:0` — clause 7.2.1, zone_primary `(none)`, pages 814-815, [d2 b4 score 0.0318]
   - (vi) Provision of stilt shall be mandatory for plots with area above 100 sqm up to 750 sqm. For plots above 750 sqm area...
2. `MPD47_FAQ:Q4@p20:0` — clause Q4, zone_primary `(none)`, pages 20-20, [d4 b6 score 0.0308]
   - Q4. What norms will be applicable on the ISR Project? The rehabilitation plot area shall not be less than 40% of the tot...
3. `MPD47_GAZETTE_EN:4.6.6@p790:0` — clause 4.6.6, zone_primary `(none)`, pages 790-790, [d5 b7 score 0.0303]
   - | Sl. No. | Plot Size (sqm) | Maximum Ground Coverage (%) | Maximum FAR | Maximum Height | | --- | --- | --- | --- | ---...
4. `MPD47_GAZETTE_EN:7.2.1@p813:0` — clause 7.2.1, zone_primary `(none)`, pages 813-814, [d3 b10 score 0.0302]
   - 7.2 Development Control Norms (DCN) 7.2.1 Plotted Housing | Use Premise | Plot Area (sqm) | | Max. Ground Coverage (%) |...
5. `MPD47_FAQ:Q3@p18:0` — clause Q3, zone_primary `(none)`, pages 18-18, [d1 b20 score 0.0289]
   - Q3. What are the permissible FAR, ground coverage and height for a Low Density Plot? The Development Control Norms appli...

- new in the top 5: `MPD47_GAZETTE_EN:4.6.6@p790:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_FAQ:Q3@p18:0`
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
5. `MPD47_FAQ:Q23:0` — clause Q23, zone_primary `hdc`, pages 17-17, [d15 b4 score 0.0290]
   - Q23. How are building plans and project proposals submitted? Proposals must be submitted through the Online Building Per...

**location-aware hybrid**

- query sent: “Can I construct a building here? Zone O Yamuna floodplain”
- expansion terms added: Zone O Yamuna floodplain
- excluded 1 chunk(s) whose primary zone is one of: hdc, land_pooling, tod
- boosted 21 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:3.1.2@p681:0` — clause 3.1.2, zone_primary `(none)`, pages 681-682, [d1 b9 **boosted** score 0.0463]
   - ii. Active floodplain shall be a ‘no construction zone’ and only recreational uses shall be permitted. All unauthorised ...
2. `DHC_YAMUNA_20240708:2:0` — clause 2, zone_primary `(none)`, pages 2-2, [d3 b10 **boosted** score 0.0452]
   - 2. Learned counsel for petitioner states that the illegal construction in question has been going on without any permiss...
3. `NGT_OA572_GNCTD_REPORT:3@p25:1` — clause 3, zone_primary `(none)`, pages 25-27, [d15 b3 **boosted** score 0.0438]
   - 7 | From the reply of NCT of Delhi, it Does not pertain to 1&FC cannot be ascertained that any Department. effective ste...
4. `NGT_OA572_GNCTD_REPORT:5@p30:0` — clause 5, zone_primary `(none)`, pages 30-31, [d11 b15 **boosted** score 0.0411]
   - 5. The status report dated 17.09.2024 has been filed by the NCT Delhi in compliance with the order dated 02.07.2024. The...
5. `NGT_OA572_GNCTD_REPORT:p1:0` — clause (none), zone_primary `(none)`, pages 1-2, [d27 b7 **boosted** score 0.0396]
   - BEFORE THE HON’BLE NATIONAL GREEN TRIBUNAL PRINCIPAL BENCH, NEW DELHI O. A. NO. 572 OF 2024 IN THE MATTER OF:- News Item...

- new in the top 5: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:2:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:p1:0`
- dropped out of the top 5: `MPD47_FAQ:Q4@p7:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`, `MPD47_GAZETTE_EN:13.1.1:0`, `MPD47_FAQ:Q5@p7:0`, `MPD47_FAQ:Q23:0`

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
- excluded 7 chunk(s) whose primary zone is one of: hdc, tod, zone_o
- boosted 31 chunk(s) in the pool

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
2. `MPD47_FAQ:Q15@p10:0` — clause Q15, zone_primary `land_pooling`, pages 10-10, [d3 b19 score 0.0285]
   - Q15. What will be the FAR applicable in the Scheme area? The FAR of each plot (except utilities & recreation) within a s...
3. `MPD47_FAQ:Q13@p16:0` — clause Q13, zone_primary `hdc`, pages 16-16, [d2 b22 score 0.0283]
   - Q13. What is the maximum permissible FAR for Residential, Commercial, and PSP uses? The maximum permissible FAR for Resi...
4. `MPD47_FAQ:Q14@p16:0` — clause Q14, zone_primary `hdc`, pages 16-16, [d1 b27 score 0.0279]
   - Q14. What is the maximum permissible FAR for Warehousing and Logistics uses? Warehousing and logistic nodes along Master...
5. `MPD47_FAQ:Q17@p13:0` — clause Q17, zone_primary `tod`, pages 13-13, [d11 b15 score 0.0274]
   - Q17. What are the applicable charges? i. The DE shall pay TOD charges for the Base FAR of 400, at a uniform rate of ₹10,...

**location-aware hybrid**

- query sent: “What FAR can I get here? transit oriented development TOD zone”
- expansion terms added: transit oriented development TOD zone
- excluded 5 chunk(s) whose primary zone is one of: hdc, land_pooling, zone_o
- boosted 34 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:4.2@p750:0` — clause 4.2, zone_primary `tod`, pages 750-750, [d1 b2 **boosted** score 0.0488]
   - 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) Transit-Oriented Development (TOD) is an innovative urban paradigm that involves ...
2. `MPD47_GAZETTE_EN:4.2.4@p755:0` — clause 4.2.4, zone_primary `tod`, pages 755-756, [d8 b1 **boosted** score 0.0466]
   - (e) The TOD Project proposal shall comply with mandatory sustainability provisions/Green Building Norms given in the pre...
3. `MPD47_GAZETTE_EN:4.2.1:0` — clause 4.2.1, zone_primary `tod`, pages 750-751, [d2 b7 **boosted** score 0.0466]
   - 4.2.1 Definitions (i) “TOD Zone”: area under 500m wide corridor on either side of centreline of the existing and planned...
4. `MPD47_GAZETTE_EN:4.2.3@p751:0` — clause 4.2.3, zone_primary `tod`, pages 751-752, [d6 b3 **boosted** score 0.0465]
   - 4.2.3 TOD Norms (i) Participation in TOD Policy is voluntary. In case of TOD Plots, the existing Land Use shall stand su...
5. `MPD47_GAZETTE_EN:3.6.1@p721:1` — clause 3.6.1, zone_primary `(none)`, pages 721-723, [d4 b9 **boosted** score 0.0452]
   - (j) In order to improve the utilisation of public transport, concerned transit agencies may consider the following: i. T...

- new in the top 5: `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`
- dropped out of the top 5: `MPD47_FAQ:Q8@p12:0`, `MPD47_FAQ:Q15@p10:0`, `MPD47_FAQ:Q13@p16:0`, `MPD47_FAQ:Q14@p16:0`, `MPD47_FAQ:Q17@p13:0`

### D at P_PLAIN — 28.639973, 77.088994

- planning zone G; in none of the four policy zones
- `get_zones`: `{"inside_delhi": true, "planning_zone": "G", "tod": false, "hdc": false, "land_pooling": false, "land_pooling_zone": null, "zone_o": false, "regional_park": false, "lda": false}`

**plain hybrid**

1. `MPD47_FAQ:Q8@p12:0` — clause Q8, zone_primary `tod`, pages 12-12, [d4 b13 score 0.0293]
   - Q8. What is the permissible FAR under the Policy? i. Base FAR shall be 400 subject to payment of TOD charges. ii. Maximu...
2. `MPD47_FAQ:Q15@p10:0` — clause Q15, zone_primary `land_pooling`, pages 10-10, [d3 b19 score 0.0285]
   - Q15. What will be the FAR applicable in the Scheme area? The FAR of each plot (except utilities & recreation) within a s...
3. `MPD47_FAQ:Q13@p16:0` — clause Q13, zone_primary `hdc`, pages 16-16, [d2 b22 score 0.0283]
   - Q13. What is the maximum permissible FAR for Residential, Commercial, and PSP uses? The maximum permissible FAR for Resi...
4. `MPD47_FAQ:Q14@p16:0` — clause Q14, zone_primary `hdc`, pages 16-16, [d1 b27 score 0.0279]
   - Q14. What is the maximum permissible FAR for Warehousing and Logistics uses? Warehousing and logistic nodes along Master...
5. `MPD47_FAQ:Q17@p13:0` — clause Q17, zone_primary `tod`, pages 13-13, [d11 b15 score 0.0274]
   - Q17. What are the applicable charges? i. The DE shall pay TOD charges for the Base FAR of 400, at a uniform rate of ₹10,...

**location-aware hybrid**

- query sent: “What FAR can I get here?”
- expansion terms added: (none)
- excluded 27 chunk(s) whose primary zone is one of: hdc, land_pooling, tod, zone_o
- boosted 0 chunk(s) in the pool

1. `MPD47_GAZETTE_EN:13.2:0` — clause 13.2, zone_primary `(none)`, pages 886-887, [d1 b17 score 0.0294]
   - 13.2 Norms for Data Centre Data centre shall be permitted in Industrial, Commercial and PSP use zone with following norm...
2. `MPD47_GAZETTE_EN:11.1.3@p860:0` — clause 11.1.3, zone_primary `(none)`, pages 860-860, [d6 b11 score 0.0292]
   - | Commerce | | | | | --- | --- | --- | --- | | Convenience Shopping Centre/ Local Shopping Centre | 2.0 ECS/100 sqm of F...
3. `MPD47_GAZETTE_EN:8.3.2@p830:0` — clause 8.3.2, zone_primary `(none)`, pages 830-831, [d4 b16 score 0.0288]
   - 8.3.2 Development Control Norms (DCN) (i) Hotel: | Sl. No. | Use Premise | Max. Ground Coverage (%) | Max. FAR | Height ...
4. `MPD47_GAZETTE_EN:p904:0` — clause (none), zone_primary `(none)`, pages 904-905, [d11 b15 score 0.0274]
   - DEFINITIONS Active frontage: A street stretch where there is an active engagement through visual/physical permeability b...
5. `MPD47_GAZETTE_EN:12.2.2@p874:0` — clause 12.2.2, zone_primary `(none)`, pages 874-874, [d20 b14 score 0.0260]
   - (ix) In case of School minimum 15% of the permissible FAR shall be utilised for developing infrastructure for extra-curr...

- new in the top 5: `MPD47_GAZETTE_EN:13.2:0`, `MPD47_GAZETTE_EN:11.1.3@p860:0`, `MPD47_GAZETTE_EN:8.3.2@p830:0`, `MPD47_GAZETTE_EN:p904:0`, `MPD47_GAZETTE_EN:12.2.2@p874:0`
- dropped out of the top 5: `MPD47_FAQ:Q8@p12:0`, `MPD47_FAQ:Q15@p10:0`, `MPD47_FAQ:Q13@p16:0`, `MPD47_FAQ:Q14@p16:0`, `MPD47_FAQ:Q17@p13:0`
