# Night 3 run, 17-18 October 2026

Eight stages, run unattended with no API key. **Stages 1-7 are complete. Stage 8 is
partial** — the session was ended early at the developer's request, so some
documentation is still outstanding. The list is in
[What is left](#7-what-is-left-for-the-next-session).

**379 tests pass** (up from 204), no paid API call was made, nothing is pushed, and there
are seven commits on `main` waiting for review.

| stage | what it did | state |
| --- | --- | --- |
| 1 | `LLM_MODEL` from `.env`, environment readers, night-2 flags decided | **done** |
| 2 | chunk quality audit, five extraction fixes, verified id remap | **done** |
| 3 | ridge and lda zone topics, wired end to end | **done** |
| 4 | raw retrieval scores, optional cross-encoder, a real abstention signal | **done** |
| 5 | four-step geocoding; the Dwarka miss fixed | **done**, gazetteer not built |
| 6 | dev-only question verification screen | **done** |
| 7 | hardening, deploy kit, CI | **done**, image not built |
| 8 | documentation and this report | **partial** |

Two things could not be done at all, both because a host was unreachable from the
sandbox this ran in, and both recorded rather than worked around: the **Overpass request**
for the metro gazetteer (D-074) and the **Docker build** (D-079).

---

## 1. Per stage, with the numbers

### Stage 1 — the night-2 flags, decided

`claude-haiku-5-5` confirmed as the default model and now overridable with `LLM_MODEL`
(D-063). FAQ heading phrases accepted as-is (D-064). Five environment readers added to
`app/config.py`, and a malformed value falls back to the default rather than stopping the
server (D-065). `.env.example` documents every setting.

### Stage 2 — the chunk audit, and five real defects

`scripts/audit_chunks.py` + `app/audit.py`: eight mechanical checks, five examples each.

| check | before | after |
| --- | --- | --- |
| starts mid-sentence | 4 | **0** |
| ends mid-sentence | 34 | 23 |
| broken markdown tables | 3 | **0** |
| leftover header / divider text | 6 | 2 |
| duplicate or near-duplicate | 0 | 0 |
| gazette ch. 1-13 with no clause id | 0 | 0 |
| under 40 or over 500 words | 56 | 53 |
| under 40% alphabetic | 18 | 18 |

**702 chunks became 700.** Five systematic causes fixed, each with tests (D-066): divider
titles spread over up to three lines whose tail was glued to the previous chapter's last
clause; a sentence cut at every page break (57 page breaks in this gazette); an all-empty
table header row repeated onto every piece of a split table; an annexure heading that
could not reach its own content; a table title stranded at the end of the chunk before
the table.

What remains is the corpus being what it is, and `reports/chunk_audit_after.md` says so
in its own words: 45 of the FAQ's 99 chunks are under 40 words because one question and
its answer is one chunk; every low-alphabetic chunk holds a norms table; the NGT report is
a scan; nine service-plan drainage tables defeated table detection.

One unrelated fix was needed to finish: `indexing.BATCH_SIZE` 128 → 32, because the
attention tensor is batch × 12 × 512 × 512 × 4 bytes = 1.5 GiB at 128, which this laptop
refused once the joined chunks started reaching the 512-token cap.

**The eval chunk ids were remapped and it was a verified no-op** (D-067): all 97
referenced ids still exist and still cover their old text, so
`eval/questions_draft.jsonl` came out byte-identical. Evidence in `eval/remap_log.json`.
The old chunks were regenerated from the pre-fix code in a scratch checkout to compare
against, because `data/processed` is not committed.

### Stage 3 — two more zone topics, and they behave differently

The gazette's headings were searched for a dedicated policy section for each, and the two
answers came out opposite (D-069):

- **LDA has one: `4.4 LOW DENSITY AREA (LDA)`**, with its own Applicability, Guiding
  principles and Development Control Norms, plus a "FAQs on LDA" section. So `lda` may
  **exclude**.
- **The Ridge has none.** 37 chunks mention it and every one sits in a section about
  something else. Chapter 10 defines Regional Park but is the norms for *all* recreational
  land; 3.1.2 was rejected for the same reason D-037 rejected it for Zone O. So `ridge`
  boosts and expands but can **never** exclude — two of the six topics now work that way,
  which makes it a pattern rather than an exception.

Tag counts: **ridge 0 primary / 37 mentions, lda 15 primary / 31 mentions.** 227 of 700
chunks carry a tag, up from 193.

P_RIDGE (28.42790, 77.20775) and P_LDA (28.60803, 76.90385) computed from the layers;
`eval/points.json` 18 → 26 points. Both new layers are served and drawn, off by default.

**`reports/location_compare_v3.md`, comparison E, "Can I build a house here?"** At
**P_LDA** plain hybrid returns TOD and HDC FAQs — the wrong policy entirely — and
location-aware search returns **4.4.3 LDA Development Control Norms at rank 1**, 4.4 at
rank 2, LDA FAQs at 3 and 5, after excluding 20 chunks. At **P_RIDGE** it returns 10.1's
definition of a Regional Park at rank 1; what it does *not* return is a clause saying you
may not build there, because the plan does not phrase it that way. A question at P_RIDGE
is probably a should-abstain question.

### Stage 4 — the abstention signal, and the reranker

`TextCrossEncoder` **is** available in fastembed 0.9.0. `Xenova/ms-marco-MiniLM-L-6-v2`
(0.08 GB) is cached in `data/index/models`. **Measured: 2.4 s a query against 0.031 s
without it** — 77× the cost of the search that produced the shortlist, not the 0.4 s first
guessed.

On the drafted questions the reranker lifts recall@1 from 0.340 to 0.460 and recall@5
from 0.720 to 0.780. That is **not evidence** — the questions were written by Claude from
the chunks, and a cross-encoder is exactly the component that benefits most from that. It
stays **off**. A counter-example is already visible in `reports/day2_queries_v3.md`: for
"Can a fuel station be built in Zone O?" it demotes the correct clause from rank 1 to 2.

**The pre-check was reading a number that could not work** (D-071). An RRF score encodes
rank position only, so a chunk both indexes ranked first scores 2/61 = 0.0328 whatever was
asked. Measured over the drafts:

| signal | answerable p5 / p50 / p95 | should-abstain p5 / p50 / p95 | provisional | widest margin |
| --- | --- | --- | --- | --- |
| `fused_score` | 0.0301 / **0.0328** / 0.0488 | 0.0285 / **0.0310** / 0.0488 | — | 0.0321 (catches 60%, loses 20%) |
| `dense_cosine` | 0.6371 / 0.7349 / 0.8303 | 0.5834 / 0.6765 / 0.7655 | **0.5804** | 0.6988 (catches 60%, loses 22%) |
| `rerank_score` | −8.479 / 1.344 / 8.022 | −9.680 / −4.451 / 4.172 | −10.238 | 1.233 (catches 90%, loses 44%) |

Configured: `ABSTAIN_SIGNAL=dense_cosine`, `ABSTAIN_THRESHOLD=0.5804`, **provisional and
labelled so everywhere**. It refuses none of the 50 answerable drafts and catches none of
the 10 should-abstain ones.

**The honest finding is bigger than the number: no single retrieval score separates these
two groups cleanly.** The pre-check is a cost guard, not a correctness guard. What stands
between an unanswerable question and a confident wrong answer is still rule 3 of the
system prompt and the citation check.

A bug in the first version of `scripts/tune_abstention.py` is recorded because it is the
same class of error: `provisional()` clamped at zero, which is harmless for a cosine and
turned "refuse nothing" into a threshold of 0.0 on the cross-encoder scale — **a value
that would have refused 40% of the answerable questions.**

Dry run: `eval/results/DRYRUN_night3_20261018_002259.md`, banner intact.

### Stage 5 — geocoding, and the Dwarka miss fixed

`locate_place` now has four steps and records which one answered (D-073). The live check
used **7 of the 8 allowed Nominatim requests**:

| query | result | path |
| --- | --- | --- |
| "Dwarka Sector 21 metro station" | **found**, 28.55192, 77.05856, in Delhi | `nominatim_normalised` |
| "near Rajiv Chowk" | found, 28.63177, 77.21938 | `nominatim_normalised` |
| "Hauz Khas" | found, 28.54981, 77.20776 | `nominatim_original` |
| "Connaught Place" | found, 28.63177, 77.21938 | `cache` |
| "Mumbai Central" | **not found** — correct | `not_found` |

**Night 2's open bug (D-049) is fixed**, by the normalisation rather than the gazetteer.
Two sub-findings worth keeping: `normalise("Station Road")` returned `"road"` in the first
version, which the docstring claimed could not happen, so station words now come off the
end only; and night 2's **cached miss** for Dwarka made the working fix look broken on the
first run, so a remembered miss recorded by an older algorithm is now invalidated.

`scripts/build_gazetteer.py` is written and tested on its parsing but **has never run**:
`overpass-api.de` times out at the TCP level from this sandbox and the sandbox bypass was
refused by policy. An absent gazetteer is a supported state (D-074).

### Stage 6 — the verification screen

`app/dev_eval.py` plus four endpoints under `/api/dev/eval/`, all **404 unless
`ZONEWISE_DEV=1`** (D-075). A Verify tab in the web app, plain state rather than a router,
showing one question at a time with a progress counter, an editable box with a live
leakage warning, a small map, the expected clause **in full**, and the current top 5
clickable to mark expected or acceptable; A / E / R / S and arrow keys (D-076).

Rejected and skipped decisions are recorded with `verified: false`, so "read it and
rejected it" is distinguishable from "never reached". The draft file is never written, and
a test asserts the bytes do not change. `run_eval.py` reads `questions_verified.jsonl`
first. `eval/README.md` rewritten around the screen with exact PowerShell steps.

### Stage 7 — hardening, deploy, CI

Everything configurable from `.env`. A body-size check in middleware (413 before
parsing), four security headers each closing something real, readable 422 messages, CORS
from config, and the map now credits "Boundaries: DDA GIS portal" beside OpenStreetMap
(D-077). `scripts/summarize_logs.py` works on the real 617-request log.

**`needs_data` marks 31 tests, and the set was proved by hiding the data** rather than
reasoned about: `data/index`, `data/processed` and `data/layers/dda` moved aside, suite
re-run — **348 passed, 31 deselected, nothing failed** — then restored, 379 pass. The
first attempt found a `test_web_build.py` case no reading of test names would have.

The Dockerfile bakes the built data in rather than building at startup, runs as non-root
with one worker (the rate-limit counters are in-memory), and its health check asks for
`status == "ok"` rather than a 200. **The build could not be run** — `docker pull` returns
zero bytes from this sandbox. Verified instead: all sixteen `COPY` paths exist, no
`.dockerignore` pattern excludes anything copied, `uv sync --frozen` is consistent, and
**the exact CMD was run outside a container** and smoke-tested: `/api/health` `status:
ok` with 700 chunks, `/api/zones` at Rajiv Chowk giving zone D with `tod: true`,
`/api/layers/regional_park` giving its 44 features, headers present, frontend served at
`/`, and the HEALTHCHECK expression exiting 0 (D-079).

`docs/DEPLOY.md` covers EC2 + Caddy end to end, Lightsail as the alternative with its
trade-offs, and a five-item cost-safety checklist whose first item is the Anthropic spend
limit.

---

## 2. Problems hit, and how they were handled

**Backslashes were being eaten in shell heredocs.** A regex written as `\\b` arrived as a
literal backspace character, which silently broke a pattern and cost about twenty minutes
before it was spotted by printing the compiled pattern. Every later patch was written to a
file with the Write tool instead. Nothing of the kind is left in the repository — all
source files were scanned for stray control characters.

**Two hosts were unreachable**: `overpass-api.de` and the Docker registry, while
`nominatim.openstreetmap.org` and HuggingFace worked. Both recorded, neither worked
around.

**The C: drive filled completely** (0 bytes free) during the aborted Docker build, which
is what stopped Stage 8 mid-way. Docker Desktop's VM disk is holding **25 GB** on C:, and
C: is at 201 GB of 201 GB. My own temp copies were deleted and the build cache pruned,
which recovered only tens of megabytes. **This needs attention independently of this
project** — see the checklist below.

**Three of my own test expectations were wrong and the tests caught them**: a sibling
annexure fold that correctly does not happen, a whole-audit test that tripped its own
word-count check, and one test that requested two conflicting fixtures at once.

---

## 3. Files created

**New modules** — `app/audit.py`, `app/rerank.py`, `app/dev_eval.py`.
**New scripts** — `audit_chunks.py`, `remap_eval_ids.py`, `tune_abstention.py`,
`build_gazetteer.py`, `check_geocoding.py`, `summarize_logs.py`.
**New tests** — `test_audit.py` (32), `test_rerank.py` (21), `test_geocode.py` (30),
`test_dev_eval.py` (37).
**New frontend** — `VerifyPanel.jsx`, `marker.js`.
**New infrastructure** — `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`.
**New docs** — `docs/DEPLOY.md`, `reports/chunk_audit_before.md`,
`chunk_audit_after.md`, `location_compare_v3.md`, `day2_queries_v3.md`, this report.
**Rewritten** — `app/geocode.py`, `eval/README.md`.
**Changed** — `app/config.py`, `cleaning.py`, `chunking.py`, `indexing.py`, `tagging.py`,
`spatial.py`, `location.py`, `retrieval.py`, `answer.py`, `api.py`, `eval/metrics.py`,
`eval/run_eval.py`, four scripts, six test files, `web/src/{App.jsx,api.js,layers.js,
styles.css}`, `MapView.jsx`, `ZoneChips.jsx`, `README.md`, `docs/ARCHITECTURE.md`,
`docs/DATA.md`, `.gitignore`, `pyproject.toml`, `.env.example`, `DECISIONS.md` (D-063 to
D-079).

**Commits** (none pushed): `night3-stage1` … `night3-stage7`, plus this report.

---

## 4. Remaining manual work for Dhruv

Ordered. The first two are housekeeping; the real work starts at 3.

**1. Free space on C:. (10 min, do this first)** The drive is at 100%, 0 bytes free, and
Docker Desktop's VM disk is 25 GB of it. Nothing else will build until this is fixed.
```powershell
docker system prune -a --volumes      # removes all images and build cache
wsl --shutdown
Optimize-VHD -Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Mode Full
```
`Optimize-VHD` needs the Hyper-V module and an elevated prompt; if it is unavailable,
Docker Desktop → Settings → Resources → "Clean / Purge data" does the same job.

**2. Build the gazetteer. (2 min)** One Overpass request.
```powershell
uv run python scripts\build_gazetteer.py
```
Expect **roughly 250-300 stations**. A count in the low tens or the thousands means the
query matched the wrong thing — the script prints the count, the element total and the
first and last name for exactly that reason. Then re-run the live check, which should now
answer the metro queries from the gazetteer with no network at all:
```powershell
uv run python scripts\check_geocoding.py --budget 2
```

**3. Review the chunk audit and the tag samples. (20 min)** This is the part only you can
judge.
```powershell
code reports\chunk_audit_after.md      # read the before/after table, then the examples
code data\processed\tag_report.md      # ridge 37 mentions, lda 15 primary - do they look right?
code reports\location_compare_v3.md    # comparison E is the new one
```
Specifically: do the `ridge` mentions look like the Ridge, and is leaving it unable to
exclude the right call (D-069)?

**4. Look at the map. (10 min)**
```powershell
uv run python scripts\serve.py
cd web; npm run dev
```
Open `http://localhost:5173`. Toggle the two new overlays — Regional park / Ridge and Low
density area — click P_RIDGE (28.4279, 77.2077) and P_LDA (28.6080, 76.9038), and check
the chips and the "no policy section" note read correctly.

**5. Set up the API key. (5 min)** Nothing works end to end without it.
```powershell
code .env      # ANTHROPIC_API_KEY=sk-ant-...
```
Then restart the server; `/api/health` should show `llm_available: true`. **Set a hard
spend limit in the Anthropic console first** — it is the only control that cannot be
defeated by a bug in this repository.

**6. Live-test real answers. (20 min)** Click Rajiv Chowk, ask "How much of my plot can I
build on?", and read the answer against the clause the citation chip opens. Then try
P_LDA and P_RIDGE, and something unanswerable like "what is my property tax?" — check it
declines rather than inventing.

**7. Verify the questions. (about 2 hours — the thing that unblocks every number)**
```powershell
$env:ZONEWISE_DEV = "1"
uv run python scripts\serve.py
# second terminal:
cd web; npm run dev
```
Open the **Verify** tab. Keep at least 40: about 17 location, 17 general, 6
should-abstain. `eval/README.md` has the four questions to ask yourself and two worked
examples of a good rewrite. Consider adding a should-abstain question at P_RIDGE.

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
Now the widest-margin value is a measurement rather than a number fitted to Claude's own
questions. Put it in `.env` and **remove the word "provisional"** from `app/config.py`,
`.env.example` and `eval/README.md`.

**10. Decide on the reranker. (5 min)** Compare `hybrid+location` against
`hybrid+location+rerank` in the verified report. If the paired interval excludes 0, the
2.4 s is probably worth it for a one-question-at-a-time interface; set `USE_RERANKER=1`
and record the decision. If it does not, leave it off and say so.

**11. Build and smoke-test the Docker image. (20 min)** After step 1.
```powershell
docker build -t zonewise:latest .
docker run --rm -p 8000:8000 zonewise:latest
curl http://localhost:8000/api/health     # expect status ok and chunks 700
```
Everything checkable without a registry was checked (D-079); what is untested is the
layer caching, the two `uv sync` steps and the non-root log directory.

**12. Record a GIF. (20 min)** Click a point, show the chips, ask a question, click a
citation chip to open the clause. 10-15 seconds, no audio. Put it at the top of the
README — it is the single highest-value thing for a reader who will not clone the repo.

**13. Deploy. (1-2 hours)** Follow `docs/DEPLOY.md` in order. Do not skip the
cost-safety checklist.

**14. Make the repo public, and fix the CI badge. (10 min)** Replace `OWNER/REPO` in the
README badge URL with the real path. Check `.gitignore` is doing its job before pushing:
```powershell
git ls-files | Select-String "\.env$|data/raw|data/index"   # must return nothing
```

**15. Final resume numbers. (15 min)** Only from step 8. Quote recall@5 for
`hybrid+location` against `hybrid` **with the confidence interval and the value of n**,
and say the questions were human-verified. An interval that includes 0 is a finding worth
stating, not a failure to hide.

---

## 5. Things I had to guess

**The provisional threshold catches nothing, and that is the honest answer.** 0.5804
refuses none of the answerable drafts and catches none of the should-abstain ones. The
alternative was a value fitted to questions Claude wrote. Step 9 replaces it.

**`ridge` cannot exclude.** Chapter 10 and 3.1.2 were both examined and rejected. If you
disagree, 10.1 is the section to add, and the trade-off is that a question about a
neighbourhood park at an ordinary address would then lose its answer.

**`farm house` counts as an LDA mention.** All four occurrences in the plan are inside the
LDA sections or the definition of the term, so it adds signal — but it is a word that
could appear elsewhere in a future edition.

**The verified file is committed.** It was briefly gitignored on the reflex that generated
files under `eval/` are not committed, and that was wrong: it is two hours of your
judgement and a few kilobytes, and CLAUDE.md lists the verified set as committed.

---

## 6. Before you push

Nothing has been pushed.

```powershell
git log --oneline --grep "^night3-"
uv run pytest                      # 379
uv run pytest -m "not needs_data"  # 348
git push
```

---

## 7. What is left for the next session

Stage 8 is partial. Still to do, all documentation:

1. **`docs/LEARNING_NOTES.md`** — five concepts to add, each with what it is, where it
   lives by file and function, why, and an interview answer: cross-encoder vs bi-encoder
   reranking; why RRF scores cannot drive abstention and what can; fuzzy matching and
   gazetteers; Docker multi-stage builds; CI and test markers.
2. **`CLAUDE.md`** — the layout and stack notes need the new modules (`audit.py`,
   `rerank.py`, `dev_eval.py`), the new scripts, `data/gazetteer/`, the Dockerfile and
   the CI workflow, and the endpoint count (seven plus four dev-only).
3. **`docs/DATA.md`** — the gazetteer section is written; the tagging table still lists
   four topics rather than six.
4. **A `reports/` index or a note in the README** pointing at which report is current
   (`day2_queries_v3.md`, `location_compare_v3.md`, `chunk_audit_after.md`).

Everything else in Stage 8 is done: `README.md`, `docs/ARCHITECTURE.md` (diagrams,
reranker, abstention signal, gazetteer, new topics, dev endpoints, decisions table),
`docs/DEPLOY.md`, `eval/README.md`, `DECISIONS.md` (D-063 to D-079),
`reports/day2_queries_v3.md` and this report.
