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
| [diagnosis_fuel_station.md](diagnosis_fuel_station.md) | **Why clause 11.1.1 does not come back at P_ZONEO** (20 Oct 2026). Names the step responsible — query expansion — explains the mechanism, and proposes a fix that is **not applied**. Regenerate the tables with `uv run python scripts\diagnose_fuel_station.py`. |
| [diagnosis_fuel_station_tables.md](diagnosis_fuel_station_tables.md) | The generated measurements behind the file above: 2 wordings x 7 configurations, all five chunks of 11.1.1, and the five demo beats under the proposal. 700 chunks. |
| [night4_run.md](night4_run.md) | **Latest run report** (19 Oct 2026): the documentation night 3 left over, PROJECT_STATUS, the Windows helper scripts, the demo script, ruff. Its last section is the ordered manual to-do list. |
| [night3_run.md](night3_run.md) | Run report, 17-18 Oct 2026: the chunk audit, the ridge and LDA topics, the abstention signal, four-step geocoding, the Verify screen, hardening and the deploy kit. Section 4 is the manual to-do list night 4 inherits. |
| [chunk_audit_after.md](chunk_audit_after.md) | Chunk quality, 700 chunks, **after** the five extraction fixes. Eight mechanical checks with five examples each. The file to read when judging whether chunking is good enough. |
| [day2_queries_v3.md](day2_queries_v3.md) | The eight test queries across **all four** retrieval modes (bm25, dense, hybrid, hybrid+rerank), top 5 each, 700 chunks. The reranker counter-example is here. |
| [location_compare_v3.md](location_compare_v3.md) | Plain hybrid against location-aware search at every test point, 700 chunks. Comparison E (P_LDA and P_RIDGE) is the newest and the most interesting. |
| [chunk_audit_before.md](chunk_audit_before.md) | Chunk quality at 702 chunks, **before** the fixes. Superseded as a description of the corpus, but current as the other half of a before/after pair — keep it. |

## Superseded

Kept for the record. Their numbers are out of date; do not quote them.

| Report | Superseded by | Why |
| --- | --- | --- |
| [day2_queries.md](day2_queries.md) | `day2_queries_v3.md` | 702 chunks, and only three retrieval modes — no reranker column. |
| [day3_location_compare.md](day3_location_compare.md) | `location_compare_v3.md` | 702 chunks, and run before the FAQ could carry a `zone_primary` (D-035), so location-aware search was weaker than it now is. |
| [day3_location_compare_v2.md](day3_location_compare_v2.md) | `location_compare_v3.md` | 702 chunks, and before the `ridge` and `lda` topics existed, so it has no comparison E. |
| [overnight_run.md](overnight_run.md) | — | Run report, 15 Oct 2026 (day 2): cleaning, chunking, tagging, the indexes, the DDA layers. History, still accurate as history. |
| [night2_run.md](night2_run.md) | — | Run report, 15 Oct 2026 (days 3-4): the answering layer, the agent, the API, the evaluation harness, the React interface. History, still accurate as history. |

## Regenerating the generated ones

All three need the built index (`scripts/05_build_index.py`) and the DDA layers.

**Pass `--out`.** Each script's default output name is its *v1* name, which is how the
superseded files above got their names — running them bare would overwrite a kept
before/after half rather than refreshing the current report. The commands that reproduce
the current four are:

```powershell
uv run python scripts\day2_queries.py --out day2_queries_v3.md
uv run python scripts\day3_location_compare.py --out location_compare_v3.md
uv run python scripts\audit_chunks.py --out reports\chunk_audit_after.md --compare reports\chunk_audit_before.md
```

Each prints a summary and the path it wrote. If you produce a genuinely new version, add
a row above and move the old one down to **Superseded** rather than deleting it.
