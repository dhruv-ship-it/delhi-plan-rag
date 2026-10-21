# Project status

**As of 20 October 2026.** This page is for whoever picks ZoneWise up next with no memory
of it — a new AI session, or Dhruv in three weeks. It is deliberately not architecture
(that is [ARCHITECTURE.md](ARCHITECTURE.md)) and not history (that is
[reports/](../reports/README.md)). It is **state**: what exists, what a human has actually
looked at, what the numbers are, and what is still open.

If you read one section, read [What a human has checked](#3-what-a-human-has-checked-and-what-they-have-not).

---

## Frozen for evaluation (v1.0-rc2)

**The repository is tagged `v1.0-rc2`.** Fix round 1 (D-100 to D-107) is complete, and
D-108 closes it: no further prompt or retrieval change before the evaluation runs,
because demo-12 flipped between declining and answering under byte-identical retrieval
and prompt (D-107), so a single run cannot tell a fix from noise, and repeated runs
exceed the free Groq budget. Remaining answer failures are documented as known
limitations rather than chased further. From this point, no change to retrieval,
chunking, prompts, the model or any threshold until the evaluation on
`eval/questions_verified.jsonl` has run — a score against a target that keeps moving
proves nothing about the target. Three settings are deliberately left open, each decided
*by* that evaluation rather than before it:

| Setting | Current state | Decided by |
| --- | --- | --- |
| `SUPPORT_CHECK` | **`enforce`** (D-103) | settled: Phase C read the v3 verdicts |
| `ABSTAIN_THRESHOLD` | provisional (D-071) | `scripts\tune_abstention.py` on verified questions only |
| `USE_RERANKER` | off (D-070) | comparing `hybrid+location` against `hybrid+location+rerank` in the verified report |

A fix is allowed only for a defect a human check actually finds, must be minimal and done
in one round, and is followed by its own tag, `v1.0-rc2` — not folded into further feature
work. Documentation, `DECISIONS.md` and reports are not frozen; this entry and the parts
of this page below it are an example of the kind of change that still happens.

**The v3 live run is complete: 23 of 23 cases** (resumed on 21 October after the
free-tier token limit reset). 17 answered, 6 declined, 0 failed, 123,276 tokens over
57 LLM calls in 2 sittings (`reports/live_run_state_v3.json`,
`reports/live_answers_v3.md`). Its answers have now been read: Phase C of
`reports/manual_checks.md` judges them case by case, and fix round 1 (D-100 to D-107)
is what came out of that reading.

**Current test count: 628 pass, 1 skipped on Windows** (deployment preparation; 554 after fix round 1, 527 when `v1.0-rc1` was tagged).

**Open items, in order.** Phase D — trying to break it, to run on the deployed app
(`reports/manual_checks.md`, not done yet) — then Phase E — decide the reranker, Phase F
— build the image, which is now a GitHub Actions run rather than a laptop `docker build`
(D-115), and Phase G — deploy, record the demo GIF and make the repository public.
**The deployment plumbing itself is done** (D-109 to D-115, `reports/deploy_prep.md`):
the host is chosen, the image is code-only, the data travels as a bundle, and
`docs/DEPLOY.md` is the click-by-click runbook. What has not happened is anyone running
it.

---

## 1. What ZoneWise is

A location-aware RAG assistant for Delhi planning law. You click a point on a map of
Delhi and ask what you can build there; it looks up which planning zones contain that
point from DDA's own GIS layers, uses those zones to decide which clauses can possibly
apply *before* searching, retrieves with hybrid search (BM25 + embeddings fused by RRF),
and answers with clause-level citations — or declines when no clause supports an answer.

The corpus is the Master Plan for Delhi 2047 gazette notification plus related court
orders. No RAG or agent framework is used: the chunking, fusion, citation validation and
agent loop are all written in this repository.

---

## 2. What is built, by component

Everything in this table exists, is tested, and runs.

| Component | Where | State |
| --- | --- | --- |
| **Config** | [app/config.py](../app/config.py) | One frozen `Settings`, every value readable from `.env`; a malformed value falls back rather than stopping the server (D-065) |
| **LLM wrapper** | [app/llm.py](../app/llm.py) | The only module that imports `anthropic` or `openai`. `LLM_PROVIDER` picks Anthropic or **Groq** (D-082); `GroqLLM` translates both ways so nothing else knows which; `FakeLLM` is the scripted stand-in every test uses. `json_object` asks for Groq's JSON mode, confirmed live on `gpt-oss-120b` (D-088) |
| **PDF extraction** | [app/extract.py](../app/extract.py), [app/cleaning.py](../app/cleaning.py) | 560 pages extracted from 4 indexed documents, 1-based page numbers throughout |
| **Chunking** | [app/chunking.py](../app/chunking.py) | 653 chunks, cut on the documents' own headings. Five systematic defects found and fixed by audit (D-066) |
| **Audit** | [app/audit.py](../app/audit.py), [scripts/audit_chunks.py](../scripts/audit_chunks.py) | Eight mechanical quality checks with examples; before/after reports in `reports/` |
| **Zone tagging** | [app/tagging.py](../app/tagging.py) | Six topics; 207 of 653 chunks tagged. Four may exclude, two may only boost |
| **Indexes** | [app/indexing.py](../app/indexing.py) | Chroma (700 × 384-dim vectors) + BM25 pickle, both local and persistent |
| **Retrieval** | [app/retrieval.py](../app/retrieval.py) | Hybrid search, RRF at k=60, raw per-index scores carried on every result |
| **Query expansion scope** | [app/location.py](../app/location.py) | Only the **four** topics with a policy section expand the query — the same four that may exclude (D-086) |
| **Reranker** | [app/rerank.py](../app/rerank.py) | Cross-encoder, working and measured — **off by default** (2.4 s vs 0.031 s a query, D-070) |
| **Location logic** | [app/location.py](../app/location.py), [app/spatial.py](../app/spatial.py) | exclude / expand / boost from the zones at a point; buffers in EPSG:32643, stored as EPSG:4326 |
| **Geocoding** | [app/geocode.py](../app/geocode.py) | **Five** steps — normalise, gazetteer, Nominatim ×2, the contiguous sub-phrases, not-found — each recording which one answered (D-073, D-090). Interchanges are grouped under their bare name within 300 m (D-084) |
| **Answering** | [app/answer.py](../app/answer.py) | Five-step path with four abstention routes. The model returns **JSON** — a list of sentences, each with its citations — and validation is structural, with one retry (D-088) |
| **Agent** | [app/agent.py](../app/agent.py) | Tool loop with a round cap, for questions that arrive as text rather than a point. Search results are labelled `S1`, `S2`, … and the agent cites the label (D-089) |
| **HTTP API** | [app/api.py](../app/api.py) | Seven public endpoints, five of which need no API key; rate limits, body-size check, four security headers, JSONL request log |
| **Dev eval screen** | [app/dev_eval.py](../app/dev_eval.py), [web/src/components/VerifyPanel.jsx](../web/src/components/VerifyPanel.jsx) | Four endpoints, **404 unless `ZONEWISE_DEV=1`** (D-075); writes `eval/questions_verified.jsonl` and never touches the draft |
| **Frontend** | [web/](../web/) | React + Vite + react-leaflet; map, zone chips, answer panel, clause drawer, tool trace, legend, verify panel |
| **Evaluation** | [eval/](../eval/README.md) | `metrics.py` (recall@k, MRR, bootstrap CIs), `run_eval.py` scoring four configurations |
| **Deploy** | [Dockerfile](../Dockerfile), [app/data_bootstrap.py](../app/data_bootstrap.py), [scripts/make_data_bundle.py](../scripts/make_data_bundle.py), [docs/DEPLOY.md](DEPLOY.md) | Two-stage build carrying **code only**; the runtime data is a zip in private blob storage, fetched and checksummed at startup (D-112, D-114); Azure App Service B1 runbook with a cost-safety checklist |
| **Image CI** | [.github/workflows/image.yml](../.github/workflows/image.yml) | Builds and pushes `ghcr.io/<owner>/zonewise:latest` and `:<short sha>` on demand and on a `v*` tag (D-115) |
| **CI** | [.github/workflows/ci.yml](../.github/workflows/ci.yml) | Tests without data + frontend build, on every push |
| **Windows helpers** | [scripts/rebuild_all.ps1](../scripts/rebuild_all.ps1), [dev.ps1](../scripts/dev.ps1), [check.ps1](../scripts/check.ps1) | Rebuild the pipeline, start both servers, run all three checks |

---

## 3. What a human has checked, and what they have not

This is the section that decides what you are allowed to say about this project.

### Verified by a human

- **The source documents.** Which 4 of 13 are indexed, and why each of the 9 is excluded:
  6 are 2-page scanned pamphlets with no text layer, 1 is the land-use plan (scanned,
  used by hand on day 3), 1 has a dead source link, and 1 is the publication edition
  carrying the same text as the gazette. Dhruv's own call, in `data/sources.csv`.
- **The gazette's page range.** That the English text starts at page 640 of the gazette
  PDF was read off the document by hand.
- **The test points.** The 8 points in `data/test_points.json` were checked against the
  map, including that P_ZONEO is on land rather than in the river.

### Verified by measurement, not by a person

- **The gazetteer is built and works** — 278 stations, and four metro queries resolve
  with no network call at all, one of them to the identical coordinate Nominatim gave
  (D-081). Also: the suite passes with the file hidden *and* present, so the
  absent-gazetteer fallback is proved rather than asserted.
- **Interchange stations resolve under their bare name** — 14 of the 278 are named per
  line by OSM, and `Hauz Khas` now answers from the gazetteer with the centre of its two
  platforms (190 m apart) and no network call. The 300 m rule was checked against the
  real data: widest real pair 281 m, and the centre, both platforms and Nominatim's own
  answer are all in planning zone F and all in a TOD zone (D-084).
- **The `needs_data` set** was established by hiding the data directories and re-running,
  not by reading test names (D-078).
- **The Dockerfile's `COPY` paths, `.dockerignore` and exact `CMD`** were each checked
  another way when the registry proved unreachable (D-079).
- **The whole answering path runs against a real model, twice.** v1: 37 cases, 0
  failures, every abstention route except `weak_retrieval` taken at least once and the
  citation retry exercised 18 times (D-085). v2: the same 21 DEMO and agent cases after
  D-086 to D-090, and **every one passed the citation check on its first attempt** — 0
  retries against 12, 0 `citation_check_failed` against 3, 3,610 tokens a case against
  5,354 (D-091). That the paths *work* is now measured twice; whether the answers are
  *right* is still not measured at all.
- **The fuel-station miss is fixed and the fix is bounded.** `11.1.1@p854` is rank 1 at
  P_ZONEO under both wordings, three of the five demo beats are bit-identical, and
  `reports/location_compare_v4.md` shows **2 of 9 points changed** — the two the change
  is about. The cost is measured too, and it is real (D-086).

### Not checked by a human — be explicit about this

| Not yet checked | What that blocks |
| --- | --- |
| **The chunk samples have not been hand-reviewed.** `reports/chunk_audit_after.md` and `data/processed/chunk_sample.md` exist and the mechanical checks pass, but no person has read a sample of chunks and said "yes, these are clauses". | Any claim that chunking is *good*, as opposed to passing its own checks |
| **The tag samples have not been hand-reviewed.** `data/processed/tag_sample.md` exists; nobody has read the 37 `ridge` mentions to confirm they are about the Ridge, or the 15 `lda` primaries. | Confidence in the exclude/boost calls, particularly D-069 for `ridge` |
| **No live answer has been read by a person.** 37 in `reports/live_answers_v1.md` and 18 more in `reports/live_answers_v2.md` (D-085, D-091). Every mechanical rule in both files is syntax, not judgement. **Two things make this the top of the list now.** v2's answers are *much* shorter — median 116 words → 42, median citations 2 → 1 — and whether that is prompt rule 8 removing unsupported padding or the model dropping detail a user wanted is a question only a reader can answer. And `demo-07` still answers a should-abstain question: 60 confident words at P_RIDGE, down from 134, citing clauses that do not say it. | Any claim about answer quality or citation accuracy. The answers exist, the structure is sound, and their correctness is unassessed |
| **The sub-phrase geocoding fallback has never run live.** D-090 is covered by nine unit tests and nothing triggered it in v2: the agent asked `locate_place("Chhatarpur")` on its own, which is D-089's prompt fix, so the fallback was never reached. | Any claim that the fallback works outside its tests |
| **The evaluation questions are unverified.** All 60 in `eval/questions_draft.jsonl` are `drafted_by: claude_code` and `verified: false`. They were written by Claude *from the chunks*, which is the one setup that flatters retrieval metrics. | Every retrieval number. This is the single biggest blocker |
| **The Docker image has never been built.** True of the rewritten one too (D-115): the sandbox that wrote it cannot reach a container registry. It was verified by reading it against the audit, by parsing its instructions, by running both python snippets it embeds, and by `tests/test_deploy_files.py`, which pins the dozen facts the deployment turns on. The first real build is the GitHub Actions run in step C of `docs/DEPLOY.md`. | Any claim that it deploys |


### So: there are no resume-quotable numbers yet

**Do not quote any retrieval metric from this repository.** The only numbers that exist
come from questions Claude wrote about chunks Claude could see, and both the recall
figures and the abstention threshold are fitted to them. `eval/results/` contains only
`DRYRUN_*` files, and they carry a banner saying so.

The path to real numbers is: verify ≥40 questions in the Verify screen → run
`eval/run_eval.py` → *those* are quotable, with the confidence interval and the value of
n, and saying the questions were human-verified.

---

## 4. Current key numbers

| | |
| --- | --- |
| Documents indexed | **3** of 13 in `data/sources.csv` (gazette, FAQ, 1 court order). The GNCTD report to the NGT was removed on 21 Oct 2026: unreadable OCR (D-105) |
| Pages extracted | **560** |
| Chunks | **700** (162,436 words, 232 words a chunk average) |
| Chunks carrying a zone tag | **227** (32.4%) |
| Map layers | **8**, from DDA's GIS portal |
| Eval points | **26** in `eval/points.json`; 8 named test points |
| Eval questions | **60** drafted, **0 verified** |
| Tests | **628 pass, 1 skipped on Windows**; 591 run with no data at all, 38 marked `needs_data` |
| Provider / model | **Groq**, `openai/gpt-oss-120b` (D-082). `LLM_PROVIDER=anthropic` still works unchanged |
| Live answers recorded | **37** in v1 and **21** in v2, **none human-reviewed** (D-085, D-091) |
| First-attempt citation pass rate | **100%** in v2 (18 of 18 answers), against 14% over the same cases in v1 |
| Tokens per live case | **3,610** mean in v2, against 5,354 in v1 |
| Decisions recorded | **91** in `DECISIONS.md` |
| API endpoints | **7** public + **4** dev-only behind `ZONEWISE_DEV=1` |
| Metro gazetteer | **278** stations from OpenStreetMap, **14** of them interchanges also keyed under their bare name (gitignored, so a clone rebuilds it in one request) |
| Requests logged | 727 lines in `data/logs/requests.jsonl`, all local testing |

### Tags per topic

| Topic | `zone_primary` | mentioned | may exclude |
| --- | --- | --- | --- |
| tod | 29 | 64 | yes |
| hdc | 36 | 47 | yes |
| land_pooling | 23 | 55 | yes |
| lda | 15 | 31 | yes |
| zone_o | 0 | 54 | **no** — no Zone O policy exists in MPD-2047 |
| ridge | 0 | 37 | **no** — no Ridge policy exists in MPD-2047 |

Regenerate with `uv run python scripts/04_tag_zones.py`, which rewrites
`data/processed/tag_report.md`. If this table and that file disagree, that file is right.

---

## 5. Known limitations

1. **The live answers exist but nobody has read them, and that is now the single
   biggest gap.** Two runs: 37 cases in v1 and the same 21 DEMO and agent cases again in
   v2 after D-086 to D-090 (`reports/live_answers_v1.md`, `reports/live_answers_v2.md`,
   D-085 and D-091). Three of v1's four findings are **fixed and measured**: the citation
   retry has gone from firing on 18 of 22 map answers to **never**; agent mode, which
   cited far worse than map mode because it had to reproduce a whole chunk id, now
   passes 5 of 5 first time citing `[S1]`; and the agent's compound place query is
   gone — it asks `locate_place("Chhatarpur")` and lands 3 m away. The fourth is
   **not** fixed: **P_RIDGE still answers when it should decline**, in 60 words rather
   than 134, still built out of clauses that do not say it. Structured output and an
   explicit no-synthesis rule shortened the answer and did not stop it, which is the
   clearest statement available of what a structural check cannot do.

   Two new things to read, both of which need judgement rather than a rule. **v2's
   answers are much shorter**: median 116 words → 42, median citations 2 → 1. That is
   either rule 8 removing padding v1 could not support, or detail a user wanted.
   And **`agent-02` may be a regression dressed as a win**: it now answers "Can I build
   a house on the Yamuna floodplain near ITO?" by correctly quoting the no-construction
   clause — at a point `get_zones` says is in a TOD zone, about a kilometre from the
   floodplain. v1 abstained there.
2. **The abstention pre-check catches nothing.** `ABSTAIN_THRESHOLD=0.5804` on
   `dense_cosine` refuses none of the 50 answerable drafts and catches none of the 10
   should-abstain ones. That is deliberate and provisional: **no retrieval score
   separates those two groups cleanly** (D-071), so the pre-check is a cost guard and the
   citation check is the correctness guard.
3. **Two zone topics can neither exclude nor expand the query.** `zone_o` and `ridge`
   have no policy section in MPD-2047, so for a point in the Ridge, search can boost
   Ridge clauses but cannot drop clauses belonging elsewhere — and since D-086 it cannot
   append the zone's words to the query either, because with no chapter to aim at those
   words name a *place* and half-replace the question. One cause now disables two of the
   three location steps for the same two topics. At P_RIDGE the plan simply does not
   contain a clause saying you may not build there.
4. **The fuel-station miss is fixed, and the fix has a cost.** At P_ZONEO, "Can a fuel
   station be built here?" used to miss 11.1.1 — the clause that says fuel stations are
   allowed "in all Use Zones except … Zone O" — at rank 14. Diagnosed on 20 October
   (`reports/diagnosis_fuel_station.md`): the step was **query expansion**, and the
   mechanism is that `zone_o` has no policy section to expand towards, so its terms act
   as a new *subject* rather than a qualifier. **Fixed the same day by D-086**: only the
   four topics with a policy section expand the query, which is the same four that may
   exclude. The clause is now **rank 1** under both wordings and three of the five demo
   beats are bit-identical. **What it cost:** questions whose subject *is* the place now
   do worse — "Can I construct a building here?" at P_ZONEO loses `3.1.2@p681` from rank
   1 to outside a 200-deep list, and "Can I build a house here?" at P_RIDGE loses the
   Regional Park definition the same way. A measured four-list alternative keeps both
   sides and is **not applied**, waiting on the verified questions like everything else
   (D-086). `reports/location_compare_v4.md` has the before/after at nine points.
5. **The corpus is what it is.** 45 of the FAQ's 99 chunks are under 40 words (one Q+A is
   one chunk); 18 chunks are under 40% alphabetic because they are norms tables; the NGT
   report is a scan; nine drainage tables defeated table detection. Documented in
   `reports/chunk_audit_after.md`.
6. **Rate limits are in-memory.** One process only — a second worker would have its own
   counters and the daily cap protecting the API bill would silently double. The
   Dockerfile pins `--workers 1` for this reason.
7. **The reranker costs 2.4 s a query** and is off, pending verified questions.
8. **The citation check is structural, never semantic.** It proves that every sentence
   names a source that was really supplied and that the source exists. It cannot prove
   the clause *says* the sentence, and v2 is the evidence: a 100% first-attempt pass
   rate alongside `demo-07` still concluding something no clause states. The sharpest
   version is that **the prompt asks for the defect**: rule 6 tells the model to say
   official DDA documents should be checked — a sentence no clause supports — while rule
   2 demands a citation on every sentence, and 7 of v1's 17 answers carry that line with
   a marker bolted on (`reports/citation_failures_v1.md`). Both rules were kept, as
   instructed; this is recorded, not fixed.
9. **Six source documents are unreadable.** 2-page scanned pamphlets with no text layer;
   OCR was not attempted.
10. **Geocoding depends on one donated service.** Nominatim, 1 req/sec, cached. The
    gazetteer removes most of that dependency for metro-station queries, but it is
    gitignored, so each machine builds it once. The sub-phrase fallback (D-090) can add
    one more request for a query nothing else answers, so the worst case for one unknown
    name is three.
11. **Not legal advice**, and the README says so above the fold.

*(Two former limitations are gone. `Hauz Khas` not resolving from the gazetteer: fixed,
interchanges are now grouped under their bare name at the centre of their platforms,
with a hard 300 m rule and no merging beyond it — D-081 resolved by D-084. And the
fuel-station retrieval miss: diagnosed and fixed the same day, D-083 resolved by D-086,
which is why limitation 4 now records a fix and its cost rather than a defect.)*

---

## 6. Open decisions

Three, all waiting on the same thing: human-verified evaluation questions.

| Open question | Current state | How it gets closed |
| --- | --- | --- |
| **The final abstention threshold** | `ABSTAIN_SIGNAL=dense_cosine`, `ABSTAIN_THRESHOLD=0.5804`, labelled *provisional* in `app/config.py`, `.env.example` and `eval/README.md` | `uv run python scripts\tune_abstention.py --questions eval\questions_verified.jsonl`, then put the widest-margin value in `.env` and **delete the word "provisional"** from those three files |
| **Reranker on or off** | Off (`USE_RERANKER=0`). Lifts recall@1 0.340 → 0.460 on drafted questions, which is not evidence; demotes the correct clause on one real query | Compare `hybrid+location` against `hybrid+location+rerank` in the verified report. If the paired interval excludes 0, 2.4 s is probably worth it for a one-question interface; otherwise leave it off and say so |
| **Whether Zone O and the Ridge should fuse four lists** | D-086 scoped expansion out for those two topics, which fixed the fuel-station miss and cost the questions whose subject *is* the place. A **four-list** variant — `dense(plain)`, `bm25(plain)`, `dense(expanded)`, `bm25(expanded)`, scoped to those two topics only — is measured and keeps both sides on all six questions tried. Not applied: six questions at two points is a finding, and it is a second embedding call for those points | Score it as a fifth configuration in `eval/run_eval.py` against `questions_verified.jsonl`, beside `hybrid+location+rerank`. The measurements are in `reports/diagnosis_fuel_station.md` § 5 |

One smaller one: the model id **`claude-haiku-5-5`** in `app/config.py` is the default and
has never been called, so it has never been confirmed against the live API. `LLM_MODEL`
overrides it without a code change (D-063).

---

## 7. The remaining manual work, in order

**The authoritative list is [reports/night3_run.md § 4](../reports/night3_run.md#4-remaining-manual-work-for-dhruv)**, carried
forward and updated in [reports/night4_run.md](../reports/night4_run.md). Summarised, in
dependency order:

1. **Free space on C:** — still tight at ~5 GB; Docker Desktop's VM disk holds 25 GB.
2. **Build the gazetteer** — one Overpass request, from Dhruv's own terminal, because
   the data is gitignored and does not travel with the repo:
   `uv run python scripts\build_gazetteer.py`. It worked on 19 October and produced
   **278 stations**, so expect that; the script prints the count for exactly this reason.
3. **Review the chunk audit and the tag samples** (~20 min) — the part only a human can
   judge, and item 1 of §3 above.
4. **Look at the map** (~10 min) — toggle the Ridge and LDA overlays, click P_RIDGE and
   P_LDA, check the chips.
5. ~~**Set up the API key**~~ — **done**, as a Groq key rather than an Anthropic one, so
   there is no bill to limit (D-082). `uv run python -m app.llm` confirms it.
6. ~~**Live-test real answers**~~ — **done twice**: 37 cases in
   `reports/live_answers_v1.md` and the 21 DEMO and agent cases again in
   `reports/live_answers_v2.md` after the five fixes (D-085, D-091). What is left is the
   part only a person can do: **read v2's 18 answers** and say which are right, in this
   order — `demo-07` (still answers where it should decline), `agent-02` (answers about
   the floodplain at a point that is not in it), then any two short ones, because the
   question to settle is whether 42 words with one citation is better or worse than
   v1's 116 with two. Allow ~30 minutes. `uv run python scripts\live_run.py --resume`
   on the **v1** state file finishes its remaining 14 draft cases if you want them.
7. **Verify the questions** (~2 hours) — **the step that unblocks every number.** Keep
   ≥40: ~17 location, ~17 general, ~6 should-abstain.
8. **Run the real evaluation** — the first quotable numbers.
9. **Set the final abstention threshold** — and remove "provisional".
10. **Decide on the reranker.**
11. **Build the image** — GitHub → Actions → Image → Run workflow. The first build of
    a Dockerfile nobody has ever built (D-115).
12. **Record a GIF** — [docs/DEMO.md](DEMO.md) is the script to follow.
13. **Deploy** — `docs/DEPLOY.md`, steps A to E, including the cost-safety checklist.
    The two values to carry from the laptop to the portal are the bundle's SAS URL and
    its SHA-256.
14. **Make the repo public and fix the CI badge** — `OWNER/REPO` is still a placeholder.
15. **Write the resume numbers** — only from step 8, with n and the interval.

---

## Where to go next

| You want | Read |
| --- | --- |
| How it works, with diagrams | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| The documents, chunks, tags, layers | [docs/DATA.md](DATA.md) |
| Every AI-engineering concept used, explained | [docs/LEARNING_NOTES.md](LEARNING_NOTES.md) |
| Why any given choice was made | [DECISIONS.md](../DECISIONS.md) — 113 entries |
| To demo it in 3 minutes | [docs/DEMO.md](DEMO.md) |
| To deploy it | [docs/DEPLOY.md](DEPLOY.md) |
| To verify evaluation questions | [eval/README.md](../eval/README.md) |
| Which report is current | [reports/README.md](../reports/README.md) |
