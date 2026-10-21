# reports/

Two kinds of file live here, and the difference matters when you are deciding which
number to trust.

**Generated reports** are written by a script and are a snapshot of the system as it was
on that date. When the pipeline changes, the old file is kept rather than overwritten —
so there are several of some — and the newest one is the only one whose numbers are
current. The superseded ones are kept on purpose: the difference between a v1 and a v3 is
the evidence that a fix did something.

**Run reports** are written for a human at the end of a working session: what was done,
what broke, what is left. They are history and all of them stay valid as history.

Chunk counts are the quickest way to date a generated report: **702 chunks** means it was
run before the night-3 extraction fixes, **700** means after.

---

## Current

Read these. They describe the system as it stands.

| Report | What it is |
| --- | --- |
| [fix_round_1.md](fix_round_1.md) | **What fix round 1 changed and what the verification run showed** (21 Oct 2026, tag `v1.0-rc2`): one commit per task, the test and chunk counts, the 12-case verification against its pass criteria, how the DEMO beats that were wrong in v3 did now, and what is left for Dhruv by hand. Start here for anything about this round. |
| [live_answers_fix1.md](live_answers_fix1.md) | **The verification run** (21 Oct 2026): 12 of the 23 cases re-asked after the fixes, with `SUPPORT_CHECK=enforce` and the 653-chunk index. 12 of 12 done, 8 answered, 4 declined, 0 failed, 69,576 tokens, 30 calls. Columns v1-v4 in its comparison table are v1, v2, v3 and this run. |
| [live_answers_fix1b.md](live_answers_fix1b.md) | **Three cases re-run with the named-zone instruction removed** (21 Oct 2026), to find out whether it was what made `demo-12` answer a should-decline question. It was not: demo-12 answered again. |
| [live_answers_fix1c.md](live_answers_fix1c.md) | **One case with all three new instructions removed** (21 Oct 2026) — the `v1.0-rc1` prompt, the only control run in this repository. `demo-12` answered a third time from the same six clauses, which is why nothing was reverted: the variable is the model, not the prompt (D-107). |
| [live_answers_v3.md](live_answers_v3.md) | **The current real-model answers — complete** (20-21 Oct 2026, at `v1.0-rc1`): the 21 DEMO and agent cases plus 2 new location-note probes, re-run after D-092 to D-096, through Groq's `openai/gpt-oss-120b`. **23 of 23 cases** in 2 sittings: 17 answered, 6 declined, 0 failed, 123,276 tokens over 57 calls. Opens with a case-by-case **v1-against-v2-against-v3 table and the totals**, including the claim check's shadow-mode verdicts and which cases `enforce` mode would have changed. **These answers have now been read**, case by case, in Phase C of [manual_checks.md](manual_checks.md) — 8 right, 4 thin, 5 wrong of 17 answers, and 5 of 6 declines right — which is what fix round 1 acts on. |
| [live_run_state_v3.json](live_run_state_v3.json) | The machine state behind the file above. Carries `location_note` and `support_check` per case, and splits each case's tokens into the answering call's and the claim check's (D-097). |
| [citation_failures_v1.md](citation_failures_v1.md) | **Why the v1 citation retries happened** (20 Oct 2026). Opens by saying what v1 **cannot** answer and why, then gives the part that is exact: 22 map-mode answers reached the citation check, **4 passed and 18 failed**. Its most useful finding was not the one it was looking for — **prompt rules 2 and 6 contradict each other**. Regenerate with `uv run python scripts\classify_citation_failures.py`. |
| [diagnosis_fuel_station.md](diagnosis_fuel_station.md) | **Why clause 11.1.1 did not come back at P_ZONEO** (20 Oct 2026). Names the step responsible — query expansion — explains the mechanism, and records the fix that was then **applied** as D-086, including **what it cost**: a question whose subject *is* the place now does worse. Regenerate the tables with `uv run python scripts\diagnose_fuel_station.py`. |
| [diagnosis_fuel_station_tables.md](diagnosis_fuel_station_tables.md) | The generated measurements behind the file above: 2 wordings x 7 configurations, all five chunks of 11.1.1, and the five demo beats before and after the fix. 700 chunks. |
| [location_compare_v4.md](location_compare_v4.md) | Plain hybrid against location-aware search at every test point, **after D-086**. Opens with a before/after table across nine points — **2 of 9 changed**, and they are the two the change is about — and a table of what left the top 5 at those two. |
| [night4_run.md](night4_run.md) | **Latest run report** (19 Oct 2026): the documentation night 3 left over, PROJECT_STATUS, the Windows helper scripts, the demo script, ruff. Its last section is the ordered manual to-do list. |
| [night3_run.md](night3_run.md) | Run report, 17-18 Oct 2026: the chunk audit, the ridge and LDA topics, the abstention signal, four-step geocoding, the Verify screen, hardening and the deploy kit. Section 4 is the manual to-do list night 4 inherits. |
| [chunk_audit_after.md](chunk_audit_after.md) | Chunk quality, 700 chunks, **after** the five extraction fixes. Eight mechanical checks with five examples each. The file to read when judging whether chunking is good enough. |
| [day2_queries_v3.md](day2_queries_v3.md) | The eight test queries across **all four** retrieval modes (bm25, dense, hybrid, hybrid+rerank), top 5 each, 700 chunks. The reranker counter-example is here. |
| [chunk_audit_before.md](chunk_audit_before.md) | Chunk quality at 702 chunks, **before** the fixes. Superseded as a description of the corpus, but current as the other half of a before/after pair — keep it. |

## Superseded

Kept for the record. Their numbers are out of date; do not quote them.

| Report | Superseded by | Why |
| --- | --- | --- |
| [live_answers_v2.md](live_answers_v2.md) | `live_answers_v3.md` | The 16 DEMO and 5 agent cases re-run a second time, after D-086 to D-090. v3's own report carries the three-way v1-v2-v3 comparison, so this file's numbers are history rather than the current measurement. |
| [live_run_state_v2.json](live_run_state_v2.json) | `live_run_state_v3.json` | The machine state behind v2. Carries `validation_failures` per case (D-087), which v1's does not. |
| [live_answers_v1.md](live_answers_v1.md) | `live_answers_v3.md` | **The first real-model answers this project ever produced** (20 Oct 2026): 37 cases, including the 30 draft questions neither v2 nor v3 re-run. Kept as history and as the oldest half of the v1-v2-v3 comparison in v3's own report; its numbers describe a system two sets of changes out of date. |
| [live_run_state.json](live_run_state.json) | `live_run_state_v3.json` | The machine state behind v1, and the file both v2's and v3's comparisons are computed against. |
| [day2_queries.md](day2_queries.md) | `day2_queries_v3.md` | 702 chunks, and only three retrieval modes — no reranker column. |
| [day3_location_compare.md](day3_location_compare.md) | `location_compare_v3.md` | 702 chunks, and run before the FAQ could carry a `zone_primary` (D-035), so location-aware search was weaker than it now is. |
| [day3_location_compare_v2.md](day3_location_compare_v2.md) | `location_compare_v4.md` | 702 chunks, and before the `ridge` and `lda` topics existed, so it has no comparison E. |
| [location_compare_v3.md](location_compare_v3.md) | `location_compare_v4.md` | Run before D-086 scoped query expansion, so its P_ZONEO and P_RIDGE sections describe retrieval that no longer ships. The other seven points are unchanged, and v4's own before/after table is the proof of that. |
| [overnight_run.md](overnight_run.md) | — | Run report, 15 Oct 2026 (day 2): cleaning, chunking, tagging, the indexes, the DDA layers. History, still accurate as history. |
| [night2_run.md](night2_run.md) | — | Run report, 15 Oct 2026 (days 3-4): the answering layer, the agent, the API, the evaluation harness, the React interface. History, still accurate as history. |

## Regenerating the generated ones

All of these need the built index (`scripts/05_build_index.py`) and the DDA layers. Only
the live run needs an API key.

**Pass `--out`.** Each script's default output name is its *v1* name, which is how the
superseded files above got their names — running them bare would overwrite a kept
before/after half rather than refreshing the current report. The commands that reproduce
the current set are:

```powershell
uv run python scripts\day2_queries.py --out day2_queries_v3.md
uv run python scripts\day3_location_compare.py --out location_compare_v4.md
uv run python scripts\audit_chunks.py --out reports\chunk_audit_after.md --compare reports\chunk_audit_before.md
uv run python scripts\diagnose_fuel_station.py
uv run python scripts\classify_citation_failures.py
```

**The live run is the one that costs something**, so it is separate and resumable. It
rewrites its report after every case, and `--report-only` rebuilds the report from the
state file with no API call at all:

```powershell
uv run python scripts\live_run.py --state reports\live_run_state_v3.json `
    --out reports\live_answers_v3.md --label "Third real-model run (v3)" `
    --groups abd --compare reports\live_run_state.json,reports\live_run_state_v2.json
```

`--resume` continues one that stopped on its budget — **v3 needs exactly this**, at 16 of
23 cases, complete at `v1.0-rc1`. `--groups abd` is the 21 DEMO and agent cases
plus the 2 location-note probes D-094 and D-097 added; `--compare` takes a
comma-separated list, so v3's report can show v1, v2 and v3 side by side.

Each script prints a summary and the path it wrote. If you produce a genuinely new
version, add a row above and move the old one down to **Superseded** rather than
deleting it.
