# Project status

**As of 19 October 2026.** This page is for whoever picks ZoneWise up next with no memory
of it — a new AI session, or Dhruv in three weeks. It is deliberately not architecture
(that is [ARCHITECTURE.md](ARCHITECTURE.md)) and not history (that is
[reports/](../reports/README.md)). It is **state**: what exists, what a human has actually
looked at, what the numbers are, and what is still open.

If you read one section, read [What a human has checked](#3-what-a-human-has-checked-and-what-they-have-not).

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
| **LLM wrapper** | [app/llm.py](../app/llm.py) | The only module that imports `anthropic` or `openai`. `LLM_PROVIDER` picks Anthropic or **Groq** (D-082); `GroqLLM` translates both ways so nothing else knows which; `FakeLLM` is the scripted stand-in every test uses |
| **PDF extraction** | [app/extract.py](../app/extract.py), [app/cleaning.py](../app/cleaning.py) | 560 pages extracted from 4 indexed documents, 1-based page numbers throughout |
| **Chunking** | [app/chunking.py](../app/chunking.py) | 700 chunks, cut on the documents' own headings. Five systematic defects found and fixed by audit (D-066) |
| **Audit** | [app/audit.py](../app/audit.py), [scripts/audit_chunks.py](../scripts/audit_chunks.py) | Eight mechanical quality checks with examples; before/after reports in `reports/` |
| **Zone tagging** | [app/tagging.py](../app/tagging.py) | Six topics; 227 of 700 chunks tagged. Four may exclude, two may only boost |
| **Indexes** | [app/indexing.py](../app/indexing.py) | Chroma (700 × 384-dim vectors) + BM25 pickle, both local and persistent |
| **Retrieval** | [app/retrieval.py](../app/retrieval.py) | Hybrid search, RRF at k=60, raw per-index scores carried on every result |
| **Reranker** | [app/rerank.py](../app/rerank.py) | Cross-encoder, working and measured — **off by default** (2.4 s vs 0.031 s a query, D-070) |
| **Location logic** | [app/location.py](../app/location.py), [app/spatial.py](../app/spatial.py) | exclude / expand / boost from the zones at a point; buffers in EPSG:32643, stored as EPSG:4326 |
| **Geocoding** | [app/geocode.py](../app/geocode.py) | Four steps — normalise, gazetteer, Nominatim ×2, not-found — each recording which one answered (D-073). Interchanges are grouped under their bare name within 300 m (D-084) |
| **Answering** | [app/answer.py](../app/answer.py) | Five-step path with four abstention routes and a citation check with one retry |
| **Agent** | [app/agent.py](../app/agent.py) | Tool loop with a round cap, for questions that arrive as text rather than a point |
| **HTTP API** | [app/api.py](../app/api.py) | Seven public endpoints, five of which need no API key; rate limits, body-size check, four security headers, JSONL request log |
| **Dev eval screen** | [app/dev_eval.py](../app/dev_eval.py), [web/src/components/VerifyPanel.jsx](../web/src/components/VerifyPanel.jsx) | Four endpoints, **404 unless `ZONEWISE_DEV=1`** (D-075); writes `eval/questions_verified.jsonl` and never touches the draft |
| **Frontend** | [web/](../web/) | React + Vite + react-leaflet; map, zone chips, answer panel, clause drawer, tool trace, legend, verify panel |
| **Evaluation** | [eval/](../eval/README.md) | `metrics.py` (recall@k, MRR, bootstrap CIs), `run_eval.py` scoring four configurations |
| **Deploy** | [Dockerfile](../Dockerfile), [docs/DEPLOY.md](DEPLOY.md) | Two-stage build carrying the built data; EC2 + Caddy runbook with a cost-safety checklist |
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
- **The whole answering path runs against a real model.** 37 cases, 0 failures and 0
  rate-limit errors through Groq, with every abstention route except `weak_retrieval`
  taken at least once and the citation retry exercised 18 times (D-085). That the paths
  *work* is now measured; whether the answers are *right* is not.

### Not checked by a human — be explicit about this

| Not yet checked | What that blocks |
| --- | --- |
| **The chunk samples have not been hand-reviewed.** `reports/chunk_audit_after.md` and `data/processed/chunk_sample.md` exist and the mechanical checks pass, but no person has read a sample of chunks and said "yes, these are clauses". | Any claim that chunking is *good*, as opposed to passing its own checks |
| **The tag samples have not been hand-reviewed.** `data/processed/tag_sample.md` exists; nobody has read the 37 `ridge` mentions to confirm they are about the Ridge, or the 15 `lda` primaries. | Confidence in the exclude/boost calls, particularly D-069 for `ridge` |
| **The 21 live answers have not been read by a person.** 37 real answers and abstentions now exist in `reports/live_answers_v1.md`, produced through Groq on 20 October (D-085). The file's "suspected problems" list is mechanical rules, not judgement, and nobody has read an answer and said whether it is right. | Any claim about answer quality or citation accuracy. The answers exist; their correctness is unassessed |
| **The evaluation questions are unverified.** All 60 in `eval/questions_draft.jsonl` are `drafted_by: claude_code` and `verified: false`. They were written by Claude *from the chunks*, which is the one setup that flatters retrieval metrics. | Every retrieval number. This is the single biggest blocker |
| **The Docker image has never been built.** The registry was unreachable; the `COPY` paths, `.dockerignore`, lockfile and the exact `CMD` were each verified another way (D-079). | Any claim that it deploys |


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
| Documents indexed | **4** of 13 in `data/sources.csv` (gazette, FAQ, 1 court order, 1 NGT report) |
| Pages extracted | **560** |
| Chunks | **700** (162,436 words, 232 words a chunk average) |
| Chunks carrying a zone tag | **227** (32.4%) |
| Map layers | **8**, from DDA's GIS portal |
| Eval points | **26** in `eval/points.json`; 8 named test points |
| Eval questions | **60** drafted, **0 verified** |
| Tests | **436 pass**; 405 run with no data at all, 31 marked `needs_data` |
| Provider / model | **Groq**, `openai/gpt-oss-120b` (D-082). `LLM_PROVIDER=anthropic` still works unchanged |
| Live answers recorded | **37** cases, 21 answered / 16 abstained, **not human-reviewed** (D-085) |
| Decisions recorded | **85** in `DECISIONS.md` |
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

1. **The live answers exist but nobody has read them.** 37 cases ran through Groq's
   `openai/gpt-oss-120b` on 20 October: 21 answered, 16 abstained, 0 failures
   (`reports/live_answers_v1.md`, D-085). Four things came out of it, none of them yet
   human-judged. **The citation check is load-bearing**: 18 of the 25 map-mode cases
   that reached the model needed the single retry, and most then passed — so two calls,
   not one, is the normal path. **Agent mode cites much worse than map mode**: 5 of 11
   failed the check twice against 5 of 26, because the agent must reproduce a full
   chunk id rather than `[C3]`. **P_RIDGE answers when it should decline**: 134
   confident words assembled from a Regional Park definition, a park built-up ceiling
   and a drain-buffer rule, every sentence correctly cited — exactly what
   `docs/DEMO.md` beat 5 predicted and called the first thing to check. And **the agent
   builds compound place queries that miss**: it asked `locate_place("Chhatarpur
   ridge")` and abstained, where `"Chhatarpur"` alone resolves instantly.
2. **The abstention pre-check catches nothing.** `ABSTAIN_THRESHOLD=0.5804` on
   `dense_cosine` refuses none of the 50 answerable drafts and catches none of the 10
   should-abstain ones. That is deliberate and provisional: **no retrieval score
   separates those two groups cleanly** (D-071), so the pre-check is a cost guard and the
   citation check is the correctness guard.
3. **Two zone topics can never exclude.** `zone_o` and `ridge` have no policy section in
   MPD-2047, so for a point in the Ridge, search can boost Ridge clauses but cannot drop
   clauses belonging elsewhere. At P_RIDGE the plan simply does not contain a clause
   saying you may not build there.
4. **One known retrieval miss, found on 19 October and diagnosed on 20 October.** At
   P_ZONEO, "Can a fuel station be built here?" does **not** return 11.1.1 — the clause
   that says fuel stations are allowed "in all Use Zones except … Zone O". It sits at
   rank 14 as shipped against rank 3 with no point at all. **The step responsible is
   query expansion** (step 2 of three), and the mechanism is that `zone_o` has no policy
   section to expand towards, so its terms `Zone O Yamuna floodplain` act as a new
   *subject* rather than as a qualifier: the clause's dense cosine actually *rises*
   (0.6143 → 0.6519) while its dense rank collapses from 11 to 173, because ~160
   floodplain chunks rise further. Exclusion changes nothing and the boost is helping.
   With expansion suppressed for the two topics that have no policy section the clause
   is **rank 1**, and three of the five demo beats come back bit-identical. **A fix is
   proposed and deliberately not applied** (D-083), because it waits on the verified
   question set like every other retrieval change and it moves two published demo beats.
   Full diagnosis: `reports/diagnosis_fuel_station.md`.
5. **The corpus is what it is.** 45 of the FAQ's 99 chunks are under 40 words (one Q+A is
   one chunk); 18 chunks are under 40% alphabetic because they are norms tables; the NGT
   report is a scan; nine drainage tables defeated table detection. Documented in
   `reports/chunk_audit_after.md`.
6. **Rate limits are in-memory.** One process only — a second worker would have its own
   counters and the daily cap protecting the API bill would silently double. The
   Dockerfile pins `--workers 1` for this reason.
7. **The reranker costs 2.4 s a query** and is off, pending verified questions.
8. **Six source documents are unreadable.** 2-page scanned pamphlets with no text layer;
   OCR was not attempted.
9. **Geocoding depends on one donated service.** Nominatim, 1 req/sec, cached. The
   gazetteer removes most of that dependency for metro-station queries, but it is
   gitignored, so each machine builds it once.
10. **Not legal advice**, and the README says so above the fold.

*(The former limitation 10 — `Hauz Khas` not resolving from the gazetteer — is fixed.
Interchanges are now grouped under their bare name at the centre of their platforms,
with a hard 300 m rule and no merging beyond it. D-081 is resolved by D-084.)*

---

## 6. Open decisions

Two, both waiting on the same thing: human-verified evaluation questions.

| Open question | Current state | How it gets closed |
| --- | --- | --- |
| **The final abstention threshold** | `ABSTAIN_SIGNAL=dense_cosine`, `ABSTAIN_THRESHOLD=0.5804`, labelled *provisional* in `app/config.py`, `.env.example` and `eval/README.md` | `uv run python scripts\tune_abstention.py --questions eval\questions_verified.jsonl`, then put the widest-margin value in `.env` and **delete the word "provisional"** from those three files |
| **Reranker on or off** | Off (`USE_RERANKER=0`). Lifts recall@1 0.340 → 0.460 on drafted questions, which is not evidence; demotes the correct clause on one real query | Compare `hybrid+location` against `hybrid+location+rerank` in the verified report. If the paired interval excludes 0, 2.4 s is probably worth it for a one-question interface; otherwise leave it off and say so |

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
6. ~~**Live-test real answers**~~ — **done**: 37 cases recorded in
   `reports/live_answers_v1.md` (D-085). What is left is the part only a person can do:
   **read the 21 answers** and say which are right. Start with `demo-07`, the P_RIDGE
   answer that should have been a refusal. `uv run python scripts\live_run.py --resume`
   finishes the remaining 14 draft cases if you want them.
7. **Verify the questions** (~2 hours) — **the step that unblocks every number.** Keep
   ≥40: ~17 location, ~17 general, ~6 should-abstain.
8. **Run the real evaluation** — the first quotable numbers.
9. **Set the final abstention threshold** — and remove "provisional".
10. **Decide on the reranker.**
11. **Build and smoke-test the Docker image** — after step 1.
12. **Record a GIF** — [docs/DEMO.md](DEMO.md) is the script to follow.
13. **Deploy** — `docs/DEPLOY.md`, including the cost-safety checklist.
14. **Make the repo public and fix the CI badge** — `OWNER/REPO` is still a placeholder.
15. **Write the resume numbers** — only from step 8, with n and the interval.

---

## Where to go next

| You want | Read |
| --- | --- |
| How it works, with diagrams | [docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| The documents, chunks, tags, layers | [docs/DATA.md](DATA.md) |
| Every AI-engineering concept used, explained | [docs/LEARNING_NOTES.md](LEARNING_NOTES.md) |
| Why any given choice was made | [DECISIONS.md](../DECISIONS.md) — 85 entries |
| To demo it in 3 minutes | [docs/DEMO.md](DEMO.md) |
| To deploy it | [docs/DEPLOY.md](DEPLOY.md) |
| To verify evaluation questions | [eval/README.md](../eval/README.md) |
| Which report is current | [reports/README.md](../reports/README.md) |
