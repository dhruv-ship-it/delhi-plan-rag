# Manual checks (human review)

Hand checks of the frozen system (tag v1.0-rc1), following the manual checklist (phases A-G).

Method: for B1 and B2, Claude (the AI project lead) read each sample first and flagged problems. I made the final calls and checked the flagged items myself, including against the source PDF. I did B3 directly.

Rule: no fixes during the checks. Findings are collected here. After Phase C, each one is either fixed once, minimally (tag v1.0-rc2), or documented as a known limitation.

## Phase B: data quality (2026-10-21)

### B1. Chunk sample: 17/20 clean (pass mark 16)
Sample: chunk_sample.md (20 random chunks, seed 42).
- Bad: #1 and #9 (NGT_OA572_GNCTD_REPORT: garbled OCR text, a scrambled table); #13 (service-plan table cut mid-sentence at both ends).
- Counted OK, with a note: #5 and #19 (table continued from the previous page, header row missing, numbers intact); #17 (matches the PDF: the table splits across pages 835-836 and uses merged cells).
- Minor issues, still OK: #3 (starts with an orphan paragraph), #11 (ends with the next item's heading), #12 (heading path truncated).
- Page check: clause 4.1.1 is on PDF page 746, as cited. Page citations are not off by one.

### B2. Zone tag sample: 28/30 correct (pass mark 24)
Sample: tag_sample.md (30 tagged chunks, seed 7).
- zone_primary: 9/9 correct. Each comes from its zone's own policy section or FAQ.
- Wrong mentions: #19 ("UER II", the road, tagged as HDC) and #29 (the definition of "farm house" tagged as LDA). Mentions only boost ranking, so the effect is small.
- #30: "ridge" is a real Ridge mention, not a regex bug.

### B3. Map preview: pass
- All 8 test-point markers return the right zones. P_OUT is outside Delhi.
- Layer shapes are where they should be. planning_zones has 16 polygons: 17 zones minus the known missing Zone A.
- The background map shows "Access blocked" when preview.html is opened as a file. OpenStreetMap requires a Referer, and a file:// page sends none. Our layers draw fine.
- Moved to Phase A (needs a background map): do the TOD strips follow the metro lines, and does the HDC band follow UER-II?

### Patterns
1. NGT report: the PDF's text layer is low-quality OCR. Both NGT chunks in the sample are bad.
2. Tables that continue onto a new page lose their header row (#5, #13, #19). Merged cells show their value only in the first row (#17).
3. Service-plan chunks (agency progress tables) are messy and rarely useful for questions (2 of 20).
4. The mention regex treats related words as zones ("UER II" as HDC, "farm house" as LDA).
5. Minor chunk-boundary issues (#3, #11) and truncated FAQ heading paths (#12).

### Open questions
- Does the app's own background map load at http://localhost:5173? Check in Phase A.
- Referrer-Policy header: if it is set to no-referrer, a deployed build would hit the same OpenStreetMap block. Check pending.
- ANSWERED, DEFECT: app/api.py sets "Referrer-Policy: no-referrer" on every response. When FastAPI serves the built app (deployment), browsers send no Referer, so OpenStreetMap will block the background map. Dev mode (Vite on :5173) is not affected. To fix in the fix round.
- The NGT file is named OA 572, but its garbled text mentions No. 537/2023. Check the first page of that PDF.

## Phase A: using the app (2026-10-21)
The app ran locally with dev.ps1 at http://localhost:5173. The background map loads in dev mode.

- TOD question ("How much of my plot can I build on?"): pin at 28.6217, 77.1405, about 8 km west of Connaught Place. Chips: Planning zone B, Inside TOD zone. The answer has 5 cited sentences: 40% maximum ground coverage on a TOD plot, setbacks, 10% green space, parking norms, and the 2,000 sqm minimum TOD plot. Its citations open clause 4.2.3 (pages 751-754). I checked them, and the sentences match. 1 model call, 4.0 s.
- Floodplain inside Zone O ("Can I build on the Yamuna floodplain here?"): the answer says the active floodplain is a no-construction zone, citing clause 3.1.2 [1] and the Delhi High Court order [2]. I checked both citations, and both match.
- The same question away from the river (Old Delhi, about 2 km from Zone O): the yellow location note appears ("not inside Zone O ... nearest boundary about 2.0 km away").
- Outside Delhi: no answer, as expected.
- Agent ("What can be built near Hauz Khas metro?"): FAILED twice with "Request failed (500)". The same question was answered in the v3 live run, so the failure is in the app's request path. Cause pending; see the defects list.
- Map checks carried over from B3, now with a background map: the TOD strips follow the metro corridors, and the high density corridor runs along the west and north edges (UER-II).

### Defects found so far (for the fix round)
1. Referrer-Policy "no-referrer" will block the OpenStreetMap background in the deployed app (found in Phase B).
2. Agent requests fail with HTTP 500 in the app (found in Phase A).

## Phase C: judging the v3 answers
(not done yet)

## Phase D: trying to break it
(not done yet)