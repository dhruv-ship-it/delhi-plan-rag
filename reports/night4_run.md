# Night 4 run, 19 October 2026

Six tasks, run unattended with no API key. **All six are done.** Nothing was pushed, no
paid API call was made, and the one network request allowed (Task 6) was made once and
succeeded.

**383 tests pass**, up from 379. `ruff check` is clean. The frontend builds.

| task | what it did | state |
| --- | --- | --- |
| 1 | the four documentation items night 3 left outstanding | **done** |
| 2 | `docs/PROJECT_STATUS.md`, linked from the README | **done** |
| 3 | three Windows helper scripts, documented | **done** |
| 4 | `docs/DEMO.md`, with every question actually run first | **done** |
| 5 | ruff, three rules, in CI and `check.ps1` | **done** |
| 6 | the gazetteer — **built**, and the absent-file case tested | **done** |

**Two things night 3 could not do are no longer blocked.** The Overpass request that
failed at the TCP level from two earlier sandboxes **succeeded from this one**: the metro
gazetteer exists, with 278 stations (D-081). The Docker build was not attempted — it was
not in scope tonight and C: is still too tight for it.

**Tasks 3 and 5 were done in the other order**, because `check.ps1` runs `ruff check` and
there was no point testing a script against a linter that was not installed yet. Both are
committed under their own task names.

---

## 1. Per task

### Task 1 — the documentation night 3 left outstanding

All four items done, and finishing them turned up a pattern worth recording: **every
stale sentence in this repository was a count.** Not one piece of prose was wrong; the
numbers were (D-080).

| document | was | is |
| --- | --- | --- |
| `CLAUDE.md` module list | 13 modules | 17, plus `data/gazetteer/`, the Dockerfile, CI, ruff, and 7 + 4 endpoints |
| `docs/DATA.md` tagging | "four topics", 192 of 700 chunks | **six topics**, 227 of 700, matching `tag_report.md` field for field |
| `README.md` project tree | `tests/ 204 pytest tests` | 383, and the real module and script lists |
| `docs/LEARNING_NOTES.md` footer | "all 62 decisions" | 81 |

**`docs/LEARNING_NOTES.md` gained five entries (16–20)**, each with what it is, where it
lives by file and function, why, and a spoken interview answer: cross-encoder vs
bi-encoder reranking; why an RRF score cannot drive abstention and what can; fuzzy
matching and gazetteers; Docker multi-stage builds; CI and pytest markers. The file went
from 430 to 708 lines.

**`docs/DATA.md` section 4 was rewritten around a table that did not exist before:
which topics may exclude and which may not.** Four of six may (`tod`, `hdc`,
`land_pooling`, `lda`); two may not (`zone_o`, `ridge`), both because MPD-2047 gives the
area no policy section of its own. The section now says that **two of six makes it a
pattern rather than an exception**, and states the visible cost at P_RIDGE rather than
leaving it in a run report.

**`reports/README.md` is new**: every report with a one-line description, split into
current and superseded, plus the rule that **a chunk count dates a report** — 702 means
before the night-3 extraction fixes, 700 means after. One thing was caught while writing
it: `day2_queries.py` and `day3_location_compare.py` **default to their v1 output
names**, so the regeneration commands need `--out` or they would overwrite a kept
before/after half. The commands in that file are the ones that reproduce the current
reports.

### Task 2 — `docs/PROJECT_STATUS.md`

One page for whoever picks this up next with no memory of it. What ZoneWise is in three
lines, every component with its file path, the current numbers, the known limitations,
the two open decisions, and the ordered remaining work pointing at night 3 § 4.

Its most important section is **what a human has checked versus what they have not**, and
it is blunt: the chunk and tag samples are not hand-reviewed; there has never been a live
LLM answer; all 60 evaluation questions are `drafted_by: claude_code` and
`verified: false`. It states in those words that **there are no resume-quotable numbers
yet**, and says what each gap blocks, so nobody — including a future session — quietly
starts quoting the draft figures.

A third category turned out to be needed: **verified by measurement, not by a person.**
The `needs_data` set, the Dockerfile's `COPY` paths, and now the gazetteer all sit there.
They are not human-checked and they are not unchecked either.

### Task 3 — the Windows helper scripts

`scripts/rebuild_all.ps1`, `dev.ps1`, `check.ps1`, documented in the README with the
`powershell -ExecutionPolicy Bypass -File ...` form.

`rebuild_all.ps1` runs `01_check_sources`, `02_extract`, `build_chapter_map`, `03_chunk`,
`04_tag_zones`, `05_build_index` and stops at the first failure, because everything after
a step reads what it wrote. `06_fetch_layers` runs only when `data/layers/dda` holds no
GeoJSON or `-RefreshLayers` is passed, and runs **first** when it runs at all — finding
out the download is broken is better before ten minutes of embedding than after.
`build_gazetteer` runs last and **a failure there is a warning**, with the message
pointing at D-074 and the command to re-run.

`check.ps1` runs all three checks **even when an earlier one fails**, because knowing
everything that is broken in one pass beats finding out one thing at a time, and exits
non-zero only if something failed.

**Tested non-destructively, as instructed.** `-DryRun` with and without `-RefreshLayers`:
the conditional logic flips correctly (layers "would skip — already populated" →
"WOULD RUN — forced by -RefreshLayers"). `check.ps1` in four forms, including
`-NoData -SkipWeb`, and **once with a deliberate one-line lint error** in a temp file to
confirm the FAIL row, the summary and exit 1 — the temp file was removed and verified
gone. No layers were re-fetched and the index was not rebuilt.

### Task 4 — `docs/DEMO.md`

A three-minute script, six beats, with a search-only version that works today and a
full-answer version for after the key, plus a 10–15 second GIF shot list and a
what-to-do-if-it-breaks table.

**Every candidate question was run through `/api/search` at its own point before being
written up**, and the observed clause ids are printed beside each beat. The spine is one
question at three points, which is the thing a plain RAG demo cannot show:

| point | "How much of my plot can I build on?" → top 3 |
| --- | --- |
| **P_TOD** (Rajiv Chowk) | `4.2.1`, `4.2.3@p751`, `4.2.3@p753` — all TOD policy |
| **P_HDC** (18 km west) | `4.3@p757`, HDC FAQ `Q1@p15`, `1.7.1@p666` |
| **P_LDA** | `4.4.3`, LDA FAQ `Q4@p18`, `4.4@p764` |

**Three candidates were cut after being run**, which is the whole reason the task said to
run them first:

- **"Can a fuel station be built here?" at P_ZONEO does not return 11.1.1** — the clause
  that says fuel stations are allowed "in all Use Zones except … Zone O" — under that
  wording *or* the explicit "in Zone O" one. The same question asked **without a point**
  has 11.1.1 at ranks 1 and 2 in hybrid mode (`reports/day2_queries_v3.md`). **So the
  location path is costing it.** Not diagnosed — it was found at the end of a
  documentation task and guessing at a retrieval change unattended is not worth it — but
  recorded in `docs/DEMO.md` and added to the limitations in `docs/PROJECT_STATUS.md`.
  This is the most interesting thing found tonight.
- "Can I build a house here?" at P_RIDGE: works, but top cosine 0.6907 against 0.7419 for
  "Is construction allowed here?", which also sets the abstention point up better.
- "How much of my plot can I build on?" at P_PLAIN: honest but wandering at ranks 2–3.
  **"What is the permissible FAR for plotted housing?"** is the question for that point —
  `7.2.1 Plotted Housing` at ranks 2 and 3, with 28 chunks excluded and 0 boosted.

The **P_RIDGE beat is kept deliberately as the honest one**: the chips say Regional Park,
and what comes back is chapter 10's *definition* of a Regional Park, not a clause saying
you may not build — because the plan does not phrase it that way. The script says to land
that beat rather than skip it.

**What `/api/ask` really does in search-only mode was checked, not inferred**: 503 with
the five retrieved clauses at an in-Delhi point, and 503 with **zero** clauses outside
Delhi, because the endpoint does not retrieve for a point it has already decided is out
of scope. The DEMO's beat 6 describes that, accurately.

One number in the file is worth knowing before recording: at P_OUT, "What is my property
tax?" has a top-1 cosine of **0.6082**, which is **above** the configured
`ABSTAIN_THRESHOLD` of 0.5804. The cheap pre-check does not catch it, exactly as D-071
says, and the refusal has to come from the system prompt and the citation check. The demo
script states that rather than hoping nobody asks.

### Task 5 — lint

`ruff` added as a dev dependency (0.17.1), configured in `pyproject.toml` with **`F`,
`E9` and `I` only** (D-080). `E501` line length is deliberately off and **`ruff format`
is never run**: it would reflow the long explanatory docstrings that are most of this
repository's teaching value, and bury the night-4 diff. `scripts/*.py` carries an
explicit `E402` ignore to record *why* those `app.*` imports sit below a
`sys.path.insert`.

**11 findings, all fixed by `ruff check --fix` with safe fixes only, nothing left to fix
by hand:** 7 unsorted import blocks, 3 f-strings with no placeholders, and **one
genuinely unused import** — `ABSTAIN_PREFIX` in `app/agent.py`, imported and then used
nowhere, re-exported nowhere. Harmless, and exactly what `F` is for.

The two larger import diffs were read rather than trusted, because import sorting near a
`sys.path.insert` is the one place this could have broken something: in `eval/run_eval.py`
every moved `app.*` import stays **below** the insert that makes it importable, and in
`scripts/07_test_points.py` a long import was only wrapped in parentheses.

Added to CI as a step **before** the tests — two seconds, and an undefined name is better
reported as a lint error than as a test failure — and to `check.ps1`.

### Task 6 — the gazetteer

**It built.** One Overpass request, 48 seconds: `291 OSM elements -> 278 distinct
stations`, 20 with at least one alternate name, `A.I.I.M.S.` to `Yashobhoomi Dwarka
Sector 25`. 278 is inside the 250–300 band the script prints its counts for. **D-074 is
resolved.**

Verified with **no network call at all**, through the real loader rather than a stubbed
dict:

| query | path | result |
| --- | --- | --- |
| "Dwarka Sector 21 metro station" | gazetteer | 28.55192, 77.05856 — **the identical coordinate night 3 got from Nominatim** |
| "near Rajiv Chowk" | gazetteer | 28.63271, 77.21931 |
| "dwarka sec 21" | gazetteer | 28.55192, 77.05856 |
| "Yashobhoomi Dwarka Sector 25" | gazetteer | 28.55083, 77.04531 |
| "Mumbai Central" | falls through | correctly not a Delhi Metro station |

`"dwarka sec 21"` is the one that matters most: a contraction no geocoder indexed, which
resolves. That is the **first evidence the 0.85 fuzzy cutoff does the job it was chosen
for** rather than matching exact strings with extra steps.

**The finding: `"Hauz Khas"` misses, and it is a real metro station.** OSM names
interchange stations **per line**, so the gazetteer holds `Hauz Khas (Magenta Line)` and
`Hauz Khas (Yellow Line)` and no plain `Hauz Khas` — 0.5806 and 0.6000 against
`hauz khas`, well under the cutoff. It falls through to Nominatim, which answers it, so
the user gets the right point and loses only the free lookup. **Recorded and deliberately
not fixed** (D-081): lowering the cutoff that far would also let "Dwarka Sector 21" match
"Dwarka Sector 12" — a wrong coordinate rather than a missing one — and collapsing the
suffix would make the loader silently keep one of two platforms 150 m apart, which is the
exact failure the unique-best rule exists to prevent. For Dhruv to decide.

**Four new tests, because the "absent gazetteer is a supported state" claim had never
been tested against an absent file.** Every existing gazetteer test monkeypatches
`gazetteer()` to a dict, which exercises the matching and never the loading — and now
that the file exists here, the untested path is the one a fresh clone takes. Added: a
missing file loads as `{}`; `locate_place` end to end with no file falls through to
`nominatim_original`; a **corrupt half-written file** is the same supported state rather
than an exception (night 3 filled this laptop's C: drive mid-write, so this is not
hypothetical); and the other half — a real file in the shape the build script writes,
answering both a station's name and its alternate name with no request.

**Proved by hiding the file**, the way D-078 established `needs_data`: gazetteer moved
aside, suite re-run — **383 pass** — restored — **383 pass**. The suite is now indifferent
to whether the file exists, which is what was being claimed all along.

---

## 2. Problems hit, and how they were handled

**PowerShell ate a commit message.** `git commit -m @'...'@` with a here-string
containing double quotes was re-split by PowerShell on the way to the native executable,
and git received a dozen stray pathspecs instead of a message. The commit simply did not
happen, which was visible in `git log`. Every later commit message was written to a file
and passed with `-F`. This is the same class of problem as night 3's eaten backslashes,
and the same answer: **do not pass non-trivial text through a shell.**

**`TestClient(app)` returned `KeyError: 'index'`.** The app loads Chroma, BM25 and the
GeoJSON layers in a FastAPI lifespan, so a bare `TestClient` never populates
`app.state.index`. `tests/test_api.py` already does it correctly with a context manager;
the probe script did not. Fixed in the probe, with a comment saying why.

**C: is tighter than it was at the start of the night: 5.22 GB → 4.06 GB.** Above the
3 GB floor the brief set, so work continued, but it moved the wrong way by over a
gigabyte across a `uv add`, a frozen resync, several npm builds and the model caches.
Nothing outside the repository was deleted and Docker data was not touched, as instructed.
**This is still item 1 on the manual list**, and Docker Desktop's 25 GB VM disk is still
the single biggest thing on that drive.

**Three documents I wrote on Task 1 were wrong by Task 6** — they said the gazetteer had
never been built, which was true when written and false four hours later. `LEARNING_NOTES`
entry 18, `PROJECT_STATUS` and the `DATA.md` gazetteer section were all corrected, along
with every stated test count (379/348 → 383/352). Mildly ironic given that D-080 is about
exactly this, and a decent argument for its rule.

---

## 3. Files created or changed

**New** — `docs/PROJECT_STATUS.md`, `docs/DEMO.md`, `reports/README.md`,
`scripts/rebuild_all.ps1`, `scripts/dev.ps1`, `scripts/check.ps1`, this report.

**Changed** — `CLAUDE.md` (layout and stack notes), `README.md` (project tree, test
counts, lint, the three helper scripts, links to PROJECT_STATUS and DEMO),
`docs/LEARNING_NOTES.md` (+5 entries, 430 → 708 lines), `docs/DATA.md` (section 4
rewritten for six topics; gazetteer state), `DECISIONS.md` (D-080, D-081),
`pyproject.toml` (ruff dependency and config), `uv.lock`,
`.github/workflows/ci.yml` (lint step), `tests/test_geocode.py` (+4 tests),
`app/agent.py`, `eval/run_eval.py`, `scripts/07_test_points.py`,
`scripts/day3_location_compare.py` and six test files (ruff's safe fixes).

**Built, not committed** — `data/gazetteer/metro_stations.json`, 278 stations
(gitignored: ODbL data, one request rebuilds it).

**Commits** (none pushed): `night4-task1`, `night4-task2`, `night4-task3`,
`night4-task5`, `night4-task6`, `night4-task4`, plus this report.

---

## 4. Remaining manual work for Dhruv

Night 3's list, updated. **Items 1 and 2 have changed** and two items are now cheaper
than they were.

**1. Free space on C:. (10 min, still first)** It was 0 bytes at the end of night 3 and is
**4.06 GB now** — someone has already cleared some, and the night's work took 1.16 GB of
it back. Docker Desktop's VM disk is still ~25 GB and nothing will `docker build` until
that is dealt with.
```powershell
docker system prune -a --volumes      # removes all images and build cache
wsl --shutdown
Optimize-VHD -Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Mode Full
```
`Optimize-VHD` needs the Hyper-V module and an elevated prompt; Docker Desktop →
Settings → Resources → "Clean / Purge data" does the same job.

**2. Build the gazetteer. (2 min — now a known quantity)** It **worked** on 19 October
from this environment and produced **278 stations**, so this is no longer a gamble. The
file is gitignored, so your machine still needs its own copy.
```powershell
uv run python scripts\build_gazetteer.py
```
Expect ~278. A count in the low tens or the thousands means the query matched the wrong
thing. Then, optionally, the live check — now mostly answered from the gazetteer with no
network:
```powershell
uv run python scripts\check_geocoding.py --budget 2
```

**3. Review the chunk audit and the tag samples. (20 min)** Still the part only you can
judge, and it is item 1 of "not checked by a human" in `docs/PROJECT_STATUS.md`.
```powershell
code reports\chunk_audit_after.md      # the before/after table, then the examples
code data\processed\tag_report.md      # ridge 37 mentions, lda 15 primary - right?
code reports\location_compare_v3.md    # comparison E is the new one
```
Specifically: do the `ridge` mentions look like the Ridge, and is leaving it unable to
exclude the right call (D-069)?

**4. Look at the map. (10 min)** Now one command:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```
Open `http://localhost:5173`. Toggle Regional park / Ridge and Low density area, click
P_RIDGE (28.4279, 77.2077) and P_LDA (28.6080, 76.9038), and check the chips and the "no
policy section" note read correctly.

**5. Set up the API key. (5 min)** Nothing works end to end without it.
```powershell
code .env      # ANTHROPIC_API_KEY=sk-ant-...
```
Then restart; `/api/health` should show `llm_available: true`. **Set a hard spend limit in
the Anthropic console first** — it is the only control that cannot be defeated by a bug in
this repository.

**6. Live-test real answers. (20 min)** `docs/DEMO.md` is now the script for this — it has
the exact questions and the clause ids each one should return in search-only mode, so you
can see at a glance whether the written answer matches the clauses it was given. Do the
P_RIDGE beat and "what is my property tax?" as well: both should decline.

**7. Verify the questions. (about 2 hours — the thing that unblocks every number)**
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Verify
```
Open the **Verify** tab. Keep at least 40: about 17 location, 17 general, 6
should-abstain. `eval/README.md` has the four questions to ask yourself and two worked
rewrites. Consider adding a should-abstain question at P_RIDGE — `docs/DEMO.md` beat 5
explains why that is the natural one.

**8. Run the real evaluation. (5 min)**
```powershell
uv run python eval\run_eval.py
```
These are the first numbers that may be quoted anywhere.

**9. Set the final abstention threshold. (10 min)**
```powershell
uv run python scripts\tune_abstention.py --questions eval\questions_verified.jsonl
$env:USE_RERANKER = "1"
uv run python scripts\tune_abstention.py --questions eval\questions_verified.jsonl --signal rerank_score
```
Put the widest-margin value in `.env` and **remove the word "provisional"** from
`app/config.py`, `.env.example`, `eval/README.md` and `docs/PROJECT_STATUS.md` § 6.

**10. Decide on the reranker. (5 min)** Compare `hybrid+location` against
`hybrid+location+rerank` in the verified report. If the paired interval excludes 0, the
2.4 s is probably worth it for a one-question-at-a-time interface; set `USE_RERANKER=1`
and record it. If not, leave it off and say so.

**11. Build and smoke-test the Docker image. (20 min)** After item 1.
```powershell
docker build -t zonewise:latest .
docker run --rm -p 8000:8000 zonewise:latest
curl http://localhost:8000/api/health     # expect status ok and chunks 700
```
Everything checkable without a registry was checked (D-079); untested are the layer
caching, the two `uv sync` steps and the non-root log directory. **Note:** the Dockerfile
`COPY`s `data/gazetteer/`, which now actually has something in it.

**12. Record a GIF. (20 min)** `docs/DEMO.md` has a shot list — beats 1 and 2 only, five
shots, 10–15 seconds, no audio. Put it at the top of the README; it is the highest-value
thing for a reader who will not clone the repo.

**13. Deploy. (1–2 hours)** Follow `docs/DEPLOY.md` in order. Do not skip the cost-safety
checklist.

**14. Make the repo public, and fix the CI badge. (10 min)** Replace `OWNER/REPO` in the
README badge URL. Check `.gitignore` is doing its job first:
```powershell
git ls-files | Select-String "\.env$|data/raw|data/index|data/gazetteer"   # must return nothing
```

**15. Final resume numbers. (15 min)** Only from item 8. Quote recall@5 for
`hybrid+location` against `hybrid` **with the confidence interval and the value of n**,
and say the questions were human-verified. An interval that includes 0 is a finding worth
stating, not a failure to hide.

### New, from tonight — optional, and both are findings rather than chores

**16. The fuel-station miss at P_ZONEO. (30 min, if you want to know)** "Can a fuel
station be built here?" at P_ZONEO does not return 11.1.1, the clause that answers it,
while the same question **without** a point has it at rank 1 in hybrid mode. Something in
the location path — the query expansion adding "Zone O Yamuna floodplain", the boost, or
the exclusion — is costing it. `scripts/search.py` with and without `--lat/--lon` is the
quickest way to see which.

**17. Interchange stations in the gazetteer. (20 min, a design call)** `"Hauz Khas"` does
not match `Hauz Khas (Magenta Line)` or `(Yellow Line)` at any cutoff worth using. The
options and why each was rejected tonight are in D-081. Doing nothing is a defensible
answer — it costs one Nominatim request, not an answer.

---

## 5. Things I had to guess

**The `ruff` rule set.** `F`, `E9` and `I` is a judgement, not a standard. The reasoning
is in D-080: this code is written to be read by someone learning, `E501` would fire on
dozens of docstring lines wrapped for reading rather than to a column, and a lint you
routinely ignore is worse than none. If you want the usual `E` + `F`, it is one line in
`pyproject.toml` — but run it before you commit to it, because the first run will be
noisy.

**Cutting three demo questions.** Keeping a question whose top results are wrong would
have made for a smoother-looking file and a worse demo. The cuts and the reasons are both
written down, so you can disagree with any of them from the evidence.

**Not chasing the fuel-station miss.** It surfaced in the last task of the night, in a
documentation exercise, and changing retrieval behaviour unattended on the strength of one
query is how a working system stops working. Recorded in two places instead.

**Not fixing the Hauz Khas miss.** Three options were considered and all three traded a
missing match for a possibly wrong one. See D-081.

---

## 6. Before you push

Nothing has been pushed.

```powershell
git log --oneline --grep "^night4-"
powershell -ExecutionPolicy Bypass -File scripts\check.ps1   # ruff + 383 tests + web build
git push
```

Last run, all three green: `ruff` clean, **383 passed**, `web/dist/index.html` written.
