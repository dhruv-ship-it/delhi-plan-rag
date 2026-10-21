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

### Phase A, added after the run
- Agent 500, root cause: gpt-oss sometimes sends its final answer as a call to a tool named "JSON" that the request does not offer. Groq rejects it (400, tool_use_failed), and the app did not catch the error. It happens at random, which is why a later try worked. Fixed in fix round 1, task 1.
- The same question ("How much of my plot can I build on?") used the TOD norms (4.2.3) at a TOD point and the general residential norms (7.2.1) at a zone G point. The location decides which rule answers.
- In the zone G answer, the claim checker rated one sentence "partly" (a ground-coverage size tier). The answer text is not logged, so this was not verified.
- In the Old Delhi test, 3.1.2 was retrieved at rank 1 and the location note was shown, but the model declined. Addressed in fix round 1, task 5.
- At the Zone O point, 3 of the 6 retrieved clauses came from the NGT report. Removed in fix round 1, task 6.
- Failed requests were not written to the request log. Fixed in fix round 1, task 1.

## Phase C: judging the v3 answers (2026-10-21)
First pass by Claude (the AI project lead) from reports/live_answers_v3.md. I then checked the four doubtful clauses myself with show_chunk.py: 3.1.2@p681, 7.2.1@p813, 4.4.3, and DHC_YAMUNA_20240708 chunks 1 and 2.

Summary: of 17 answers, 8 right, 4 thin, 5 wrong. Of 6 declines, 5 right, 1 wrongly declined. Enforce mode would have changed none of the 5 wrong answers; its one "unsupported" call (demo-10, sentence 2) was correct.

| case | verdict | why |
| --- | --- | --- |
| demo-01 | thin | 40% ground coverage on a TOD plot is right (4.2.3); no FAR |
| demo-02 | right | HDC plot norms (4.3.3) |
| demo-03 | wrong | says the High Court ordered demolition; the petitioner sought it (DHC chunk 1) |
| demo-04 | right | 3.1.2 floodplain rules |
| demo-05 | thin, misleading | 70% is the godowns figure (the highest across uses); residential is 15% (4.4.3) |
| demo-06 | wrong (one detail) | FAR 10, 15% and 10 m are right, but it calls the 18 m minimum road width a "rear setback"; setbacks are 15 m front and 5 m on the other sides |
| demo-07 | wrong, should have declined | applies 3.1.2's floodplain list of allowed uses to the Ridge; 3.1.2's only Ridge mention is the Ridge-Yamuna cycling connector |
| demo-08 | right | outside Delhi |
| demo-09 | right | declined; not in the documents |
| demo-10 | right, one overreach | sentence 2 equates Zone O with the active floodplain; the checker flagged it, and enforce would drop it |
| demo-11 | right | 11.1.1 |
| demo-12 | right | declined (should-decline case) |
| demo-13 | wrong, misleading | tiers are right, but sentence 4 presents a regeneration-section FAR (4.6.5) as general, and sentence 5 (ISR) is irrelevant |
| demo-14 | wrong | gives FAR 350 up to 250 sqm; 7.2.1 has 350 up to 100 and 300 for 100-250. The table is readable, so this is a model error |
| demo-15 | right | 4.2.1 definitions |
| demo-16 | right | land pooling participation |
| agent-01 | thin | describes TOD policy mechanics, not what can be built |
| agent-02 | wrongly declined | 3.1.2 was retrieved (S3) and the location note shown; it should have stated the rule |
| agent-03 | thin | 40% only |
| agent-04 | right | 40% for a TOD plot |
| agent-05 | right to decline | no retrieved clause states a construction rule for the Ridge (the case was mislabelled "answerable") |
| probe-01 | right | states 3.1.2 at a TOD point |
| probe-02 | right to decline | same as agent-05 |

Patterns:
1. Misreading tables: a skipped row (demo-14), a misread column label (demo-06).
2. Court orders: a party's request presented as the court's order (demo-03).
3. A clause that only names a zone gets boosted there, and its rules are applied to the wrong zone (demo-07).
4. Padding and misleading generalisation (demo-13, demo-05).
5. Declining when the point is outside the named zone, despite having the clause (agent-02).
Patterns 1, 2 and 5 are addressed by prompt instructions in fix round 1, task 5; pattern 3 is documented as a known limitation. The NGT report's retrieval noise is removed in task 6.

## Phase D: trying to break it
(not done yet)

---

## Fix round 1 (2026-10-21)

One round of minimal fixes, one commit per task, each for a defect a check above found.
The full write-up is [fix_round_1.md](fix_round_1.md); the reasoning for each decision is
in `DECISIONS.md` D-100 to D-107.

| task | commit | what changed |
| --- | --- | --- |
| 1. Agent and provider errors | `b4b830d` | A final answer Groq rejected as a call to a tool named `JSON` is read back out of the error and validated normally, with no extra call (`app/llm.py`). `/api/ask` and `/api/agent` answer a provider failure with 503 and a short message the interface shows instead of "Request failed (500)". Every failed request is now logged with a one-line `error` field. 15 tests. |
| 2. Referrer-Policy | `4844bfa` | The page keeps `no-referrer`; the OSM tile layer carries `referrerPolicy="strict-origin-when-cross-origin"`, which Leaflet 1.9 puts on each tile `<img>`. Needs a browser check on the deployed build. 2 tests. |
| 3. Empty lists in the answer panel | `0afd2de` | **No code change.** Both lists already render text (clause label, pages and a snippet; tool name, input and summary). The empty bullets came from copying a collapsed `<details>`, which takes the summary and the list structure without the hidden children. |
| 4. `SUPPORT_CHECK=enforce` | `10cd454` | Now the default, in `app/config.py`, `.env.example` and four docs. The checker itself is unchanged. Its limits are written down: `partly` is kept, so demo-14's wrong FAR tier and demo-06's mislabelled RoW both survive it. |
| 5. Three prompt instructions | `9dd072d` | A zone mismatch alone is no longer a reason to decline (agent-02); every figure must carry the row and condition the clause gives it (demo-14, demo-06, demo-13); a court document's statements must be attributed to whoever made them (demo-03). Appended as rules 10-12 (map) and 11-13 (agent); nothing else in either prompt changed. 4 tests. |
| 6. The NGT report leaves the index | `f060fd5` | `NGT_OA572_GNCTD_REPORT` marked `include=no` with its reason and the pipeline re-run: **653 chunks**, with the 47 removed ids verified as exactly the NGT ones and every other id unchanged. Counts updated in README, `docs/DATA.md`, `docs/PROJECT_STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DEMO.md`, the Dockerfile, the footer and the `search_clauses` description. **0 of 60 draft eval questions** referenced an NGT chunk, so none was removed. |
| 7. Records and docs | `TASK7` | The v3 run marked complete (23 of 23) in `docs/PROJECT_STATUS.md`, `reports/freeze_v1.0-rc1.md` and `reports/README.md`; agent-05 and probe-02 now expect "either"; this Phase C section and the Phase A addendum; README's known limitations. |
| 8. Verification run | `TASK8` | See [fix_round_1.md](fix_round_1.md) for the case-by-case result against the pass criteria. |
