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
| [live_answers_v2.md](live_answers_v2.md) | **The current real-model answers** (20 Oct 2026): the 16 DEMO and 5 agent cases re-run after D-086 to D-090, through Groq's `openai/gpt-oss-120b`. Opens with a case-by-case **v1-against-v2 table and the totals**, which is the measurement of what those five changes did. Every case then appears in full. **Still nobody has read these answers** — the "suspected problems" list is mechanical rules, not judgement. |
| [live_run_state_v2.json](live_run_state_v2.json) | The machine state behind the file above. It carries `validation_failures` per case, which v1's does not: one problems list per rejected attempt, so "which rule rejected this" is readable rather than inferred (D-087). |
| [citation_failures_v1.md](citation_failures_v1.md) | **Why the v1 citation retries happened** (20 Oct 2026). Opens by saying what v1 **cannot** answer and why, then gives the part that is exact: 22 map-mode answers reached the citation check, **4 passed and 18 failed**. Its most useful finding was not the one it was looking for — **prompt rules 2 and 6 contradict each other**. Regenerate with `uv run python scripts\classify_citation_failures.py`. |
| [diagnosis_fuel_station.md](diagnosis_fuel_station.md) | **Why clause 11.1.1 did not come back at P_ZONEO** (20 Oct 2026). Names the step responsible — query expansion — explains the mechanism, and records the fix that was then **applied** as D-086, including **what it cost**: a question whose subject *is* the place now does worse. Regenerate the tables with `uv run python scripts\diagnose_fuel_station.py`. |
| [diagnosis_fuel_station_tables.md](diagnosis_fuel_station_tables.md) | The generated measurements behind the file above: 2 wordings x 7 configurations, all five chunks of 11.1.1, and the five demo beats before and after the fix. 700 chunks. |
| [location_compare_v4.md](location_compare_v4.md) | Plain hybrid against location-aware search at every test point, **after D-086**. Opens with a before/after table across nine points — **2 of 9 changed**, and they are the two the change is about — and a table of what left the top 5 at those two. |
| [live_answers_v1.md](live_answers_v1.md) | **The first real-model answers this project ever produced** (20 Oct 2026). Superseded as a description of the system by v2, and current as the other half of a before/after pair — keep it. 37 cases, including the 30 draft questions v2 does not re-run. |
| [live_run_state.json](live_run_state.json) | The machine state behind v1, and the file v2's comparison is computed against. |
| [night4_run.md](night4_run.md) | **Latest run report** (19 Oct 2026): the documentation night 3 left over, PROJECT_STATUS, the Windows helper scripts, the demo script, ruff. Its last section is the ordered manual to-do list. |
| [night3_run.md](night3_run.md) | Run report, 17-18 Oct 2026: the chunk audit, the ridge and LDA topics, the abstention signal, four-step geocoding, the Verify screen, hardening and the deploy kit. Section 4 is the manual to-do list night 4 inherits. |
| [chunk_audit_after.md](chunk_audit_after.md) | Chunk quality, 700 chunks, **after** the five extraction fixes. Eight mechanical checks with five examples each. The file to read when judging whether chunking is good enough. |
| [day2_queries_v3.md](day2_queries_v3.md) | The eight test queries across **all four** retrieval modes (bm25, dense, hybrid, hybrid+rerank), top 5 each, 700 chunks. The reranker counter-example is here. |
| [chunk_audit_before.md](chunk_audit_before.md) | Chunk quality at 702 chunks, **before** the fixes. Superseded as a description of the corpus, but current as the other half of a before/after pair — keep it. |

## Superseded

Kept for the record. Their numbers are out of date; do not quote them.

| Report | Superseded by | Why |
| --- | --- | --- |
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
uv run python scripts\live_run.py --state reports\live_run_state_v2.json `
    --out reports\live_answers_v2.md --label "Second real-model run (v2)" `
    --groups ab --compare reports\live_run_state.json
```

`--resume` continues one that stopped on its budget; `--groups ab` is the 16 DEMO and 5
agent cases, which is the set v1 and v2 share.

Each script prints a summary and the path it wrote. If you produce a genuinely new
version, add a row above and move the old one down to **Superseded** rather than
deleting it.
