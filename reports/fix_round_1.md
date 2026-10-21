# Fix round 1

**21 October 2026. Tag `v1.0-rc2`.** One round of minimal fixes, each for a defect a human
check found, with one commit per task. The findings are in
[manual_checks.md](manual_checks.md); the reasoning behind every choice is in
`DECISIONS.md` **D-100 to D-107**.

Nothing in retrieval, chunking, fusion, the thresholds, the embeddings, the reranker or
the zone-tagging rules was touched. The three prompt instructions in task 5 are the only
prompt changes. The corpus changed in one way only: one document left it.

| | |
| --- | --- |
| Tests | **554 pass** (518 with no built data, 36 marked `needs_data`); 527 at `v1.0-rc1` |
| Chunks indexed | **653**, down from 700 |
| Documents indexed | 3 of 13 (gazette, FAQs, Delhi High Court order) |
| `scripts\check.ps1` | green: ruff clean, 554 tests, web build written |
| Verification run | 12 cases, 0 failed, 93,907 tokens and 40 calls across 3 runs, inside the 100,000 / 70 budget |

---

## What changed, per task

| task | commit | what changed |
| --- | --- | --- |
| 1. Agent and provider errors | `b4b830d` | The HTTP 500 is fixed at three levels. A final answer Groq rejects as a call to a tool named `JSON` is read back out of `error.failed_generation` and validated exactly like any other reply, with **no extra model call** (`app/llm.py`, `salvaged_answer`). `/api/ask` and `/api/agent` answer any provider failure — `APIStatusError` including 400, 429 and 5xx, `APIConnectionError`, `APITimeoutError` — with **503** and the message *"The AI service is busy or returned an error. Please try again in a minute."*, which the interface already shows in place of "Request failed (500)". Every failed request now writes one line to `data/logs/requests.jsonl` with `abstain_reason: "request_failed"` and an `error` field holding the exception type and a one-line message. A bug of **ours** is logged the same way and still returns 500, because "the AI service is busy" must never be the message for a fault in this repository. **15 tests.** |
| 2. Referrer-Policy | `4844bfa` | The page keeps `Referrer-Policy: no-referrer`. The OpenStreetMap tile layer now carries `referrerPolicy="strict-origin-when-cross-origin"`, which Leaflet 1.9 puts on each tile `<img>`; an element's own policy overrides the document's for that request alone, so the tiles send the site's origin and nothing else on the page sends anything. **2 tests**, one of which pins the leaflet version, because the option exists only from 1.7. **Needs a browser check on the deployed build** — this sandbox cannot reach OSM. |
| 3. Empty lists in the answer panel | `0afd2de` | **No code change, by the task's own rule.** Both lists already render visible text: each retrieved clause as `Clause 4.2.3 — pages 753-754` plus the first 180 characters of the clause, and each agent step as its plain-English tool name, its input and its summary. The empty bullets came from **copying a collapsed `<details>`**: a browser takes the `<summary>` and the list structure while the hidden children contribute nothing. Expanding both sections before copying gives the full text. |
| 4. `SUPPORT_CHECK=enforce` | `10cd454` | Now the default in `app/config.py`, `.env.example`, `docs/ARCHITECTURE.md`, `docs/LEARNING_NOTES.md` and `docs/PROJECT_STATUS.md`. **The checker itself is unchanged.** Its limits are written down everywhere it is described: a sentence rated `partly` is kept, so demo-14's wrong FAR tier and demo-06's mislabelled RoW both survive it, and it cannot see that a correctly quoted clause is about the wrong place (demo-07). |
| 5. Three prompt instructions | `9dd072d` | Appended as rules **10, 11, 12** (map) and **11, 12, 13** (agent), so no existing rule number shifted. (a) A note saying the point is not inside a zone the question names is not on its own a reason to decline. (b) Every figure must carry the exact row, use, column and scheme the clause gives it; never merge table rows; never present a special case as a general rule. (c) In a court document, say who made each statement, and never say the court ordered anything unless the cited text says it did. Nothing else in either prompt changed. **4 tests.** |
| 6. The NGT report leaves the index | `f060fd5` | `NGT_OA572_GNCTD_REPORT` marked `include=no` in `data/sources.csv` with its reason, and the pipeline re-run: **653 chunks**. All 700 ids were saved first and compared: **47 removed, 0 added, every other id byte-identical**, and the 47 are exactly the `NGT_OA572_GNCTD_REPORT:*` ids. `data/chapter_map.json` and `data/zone_sections.json` came out unchanged. Counts updated in README, `docs/DATA.md`, `docs/ARCHITECTURE.md`, `docs/PROJECT_STATUS.md`, `docs/DEMO.md`, `docs/LEARNING_NOTES.md`, `app/rerank.py`, the `Dockerfile`, the interface footer and the `search_clauses` tool description. **0 of 60 draft eval questions** referenced an NGT chunk, so none was removed, and every expected chunk id still exists. |
| 7. Records and docs | `0731c53` | The v3 run marked **complete, 23 of 23** (17 answered, 6 declined, 0 failed, 123,276 tokens, 57 calls) in `docs/PROJECT_STATUS.md`, `reports/freeze_v1.0-rc1.md` and `reports/README.md`. `agent-05` and `probe-02` now expect **"either"**, with the reason recorded once in `scripts/live_run.py`. `scripts/live_run.py` gained `--cases` for naming single cases. `manual_checks.md` gained Phase C, the Phase A addendum and the fix-round table. README gained a **known limitations of the answers** section. **5 tests.** |
| 8. Verification run | `4f2b291` | 12 cases re-asked, plus two controlled re-runs to apply the revert rule. Results below. |

**Two counts were stale before this round and are now right**: `scripts\check.ps1`, the CI
comment, README, `docs/PROJECT_STATUS.md` and `docs/LEARNING_NOTES.md` all said 477 tests
(446 without data) when the suite was already 527. They now say 554 and 518.

---

## The verification run

`reports/live_answers_fix1.md`, 12 cases, `SUPPORT_CHECK=enforce`, the 653-chunk index,
Groq `openai/gpt-oss-120b`. **12 of 12 done, 8 answered, 4 declined, 0 failed, 69,576
tokens, 30 calls.** No 429s and no rate-limit waits.

| pass criterion | result | what happened |
| --- | --- | --- |
| **demo-14**'s FAR tiers match 7.2.1, or leave tiers out | **PASS** | "350 for plots up to 100 sqm, 300 for plots above 100 sqm up to 250 sqm, and 225 - 200 for larger plots", then each larger row. That is the table. v3 said "350 up to 250 sqm". |
| **demo-03** does not say the court ordered demolition | **PASS** | It now cites `DHC_YAMUNA_20240708:6:0` — *"this Court directs the Vice Chairman, DDA, to remove all encroachments"* — where v3 cited chunk 1, the petitioner's prayer. Its first sentence still slides Zone O and the active floodplain together, which the claim check rated `partly` and kept. |
| **demo-04** and **demo-10** still state 3.1.2 and 11.1.1 correctly | **PASS** | demo-04 gives 3.1.2 (ii) in full **and** attributes the "prohibited activity zone" line to *"respondents in the court proceedings"*. demo-10 answers "Fuel stations are not permitted in Zone O" from 11.1.1 — and `enforce` **dropped** its second sentence, the Zone O / active floodplain conflation, which is the one sentence Phase C said deserved it. |
| **agent-05** and **probe-02** decline, or answer only from a clause that states a Ridge rule | **PASS** | Both declined. |
| **demo-12** still declines | **FAIL** | It answered. Investigated below: not caused by any instruction. |
| **demo-06** does not call the 18 m RoW a setback | **FAIL** | "a minimum rear-of-site (RoW) setback of 18 m". Clause 4.4.3 gives **Min. RoW 18 m** in the residential row and its setbacks separately in note (c): 15 m front, 5 m on the other three sides, which the answer never mentions. FAR 10, 15%, 10 m and the 10,000 sqm minimum plot are all right. |
| **agent-02** answers with 3.1.2's no-construction rule, and the note is shown | **FAIL** | The note was shown ("not inside Zone O … about 600 m away"); **3.1.2 was not retrieved at all.** The agent located ITO, read the zones, and searched "Yamuna floodplain house construction"; all five clauses that came back were 4.2.x TOD policy. In v3 the same point and a near-identical query returned 3.1.2 as `S3`. The instruction was never put to the test. |
| **demo-07** — record the outcome | **as expected** | Still answers, and its first sentence still applies 3.1.2's restricted-development list to the Ridge. It did move: v3 built the answer from a park built-up ceiling and a drain-buffer rule, this run cites 3.1.2 and **10.2.1**, the Regional Park's own section. `enforce` would not change it. Known limitation, in README. |

### Why 3.1.2 stopped being retrieved at two points

This is the one unintended consequence of task 6, and it cost two cases
(`agent-02`, `probe-01`). Retrieval is frozen and unchanged — but **BM25's idf is computed
over the whole corpus**, so removing 47 documents re-weights every keyword score and
re-orders the fusion. `scripts\search.py` at ITO now returns six 4.2.x TOD clauses in the
located top 6, with the query expanded to "… transit oriented development TOD zone"
because the point is in a TOD zone (D-086). 3.1.2 is not excluded there — it has no
`zone_primary` — it simply no longer scores into the top 5.

`probe-01` shows the same thing with `enforce` behind it: it was **right in v3** ("states
3.1.2 at a TOD point"), 3.1.2 is no longer in its top 6, so the model answered from TOD
clauses instead, its first sentence was rated `unsupported`, and D-096's rule that a
dropped first sentence throws the whole answer away did the rest. Two supported sentences
went with it. That is `enforce`'s first live cost and it is the behaviour D-096 chose on
purpose, but it is now a measured cost rather than a predicted one.

### demo-12, the revert rule, and why nothing was reverted

demo-12 ("Can I build a house here?" at `P_RIDGE`) declined in v1, v2 and v3, and
answered here — the revert rule's trigger exactly. Its six retrieved chunks are
**byte-identical to v3's**, so the prompt was the only changed input, and only one of the
three instructions is about whether to decline. So:

| run | prompt | demo-12 |
| --- | --- | --- |
| v3 | `v1.0-rc1`, no new instructions | **declined** |
| `fix1` | all three instructions | answered (10.1, 5.1.3) |
| `fix1b` | named-zone instruction **reverted** | answered (10.1, 1.6.2) |
| `fix1c` | **all three removed** — the `v1.0-rc1` prompt | answered (50 words, 1 sentence called `unsupported`) |

The third call's input is identical to v3's: the same six clauses in the same order, the
same zones, no location note, the same prompt, `temperature=0`. **The variable is the
model, not the prompt** — `openai/gpt-oss-120b` on Groq is not deterministic at
temperature 0, and demo-12 sits close enough to the line to fall on either side of it.
The revert rule was therefore applied in full and found no instruction to revert: all
three were restored, and demo-12's instability is recorded as a finding instead (D-107).

**One run is evidence, not proof.** This round is the proof of that sentence: a case that
declined three times running answered three times running with the same input. Every
verdict in the table above rests on a single call.

---

## The DEMO.md beats that were wrong in v3

| beat | case | v3 | now |
| --- | --- | --- | --- |
| 3 — the floodplain | demo-03 | **wrong**: said the High Court ordered demolition | **right on that point**: cites the court's own direction. Sentence 1 still conflates Zone O with the active floodplain (`partly`, kept) |
| 4, alternative — "can I build a house" in an LDA | demo-06 | **wrong**: called the 18 m RoW a "rear setback" | **still wrong, the same way** |
| 5 — the should-decline beat | demo-07 | **wrong**: floodplain rules applied to the Ridge | **still answers**, now from 3.1.2 + 10.2.1. Known limitation |
| the replacement question — FAR for plotted housing | demo-14 | **wrong**: FAR 350 up to 250 sqm | **right**: every tier as 7.2.1 gives it |
| (a cut question, not a live beat) | demo-13 | **wrong**: a regeneration FAR presented as general, plus an irrelevant sentence | **better**: the irrelevant sentences are gone, but sentence 1 still merges the 350 tier up to 250 sqm (`partly`, kept) |
| 4 — maximum ground coverage in an LDA | demo-05 | **thin, misleading**: 70% is the godowns figure | **not re-run** — it was not in the verification set |

So of the three live beats that were wrong, **one is fixed, one is unchanged, one is the
documented limitation**, and the demo's replacement question is fixed.

---

## Remaining manual work, for Dhruv

1. **`SUPPORT_CHECK` needs nothing.** `enforce` is the default now and your `.env` sets
   only `LLM_PROVIDER` and `LLM_MODEL`, so your runs already enforce. Add
   `SUPPORT_CHECK=enforce` to `.env` only if you want it pinned where you can see it;
   `GET /api/health` reports the live mode either way.
2. **Four browser checks**, none of which can be done from this sandbox:
   - **The agent answers.** Ask "What can be built near Hauz Khas metro?" in the app a
     few times. It should answer, or decline honestly — never "Request failed (500)".
   - **A failed request shows the friendly message.** The easiest way to force one is to
     put a wrong `GROQ_API_KEY` in `.env`, restart, and ask a question: the panel should
     read "The AI service is busy or returned an error. Please try again in a minute."
     and `data/logs/requests.jsonl` should have a line with an `error` field.
   - **The answer panel's lists.** Open "N clause(s) retrieved" and "How the agent worked
     this out": each item should show a clause label with its pages and a snippet, or a
     tool name with its summary. **Expand both before copying**, or the paste loses them
     (task 3).
   - **The map tiles in the built app**, once deployed: `npm run build`, serve with
     FastAPI, and confirm the OpenStreetMap background draws instead of "Access blocked".
     Dev mode at `:5173` does not test this — Vite sends no `Referrer-Policy`.
3. **No resume is needed.** The verification run finished, 12 of 12. If you want to re-ask
   any of it:
   ```powershell
   uv run python scripts\live_run.py --state reports\live_run_state_fix1.json ^
     --out reports\live_answers_fix1.md --groups abd --cases demo-06,agent-02 --restart
   ```
   (`--resume` would report that all 12 are done; `--restart` throws the state away and
   asks the named cases again.)
4. **Three defects this round found and did not fix.** None is urgent; all are written
   down so the next round does not rediscover them.
   - **demo-06's RoW-as-setback survives an instruction written for it.** The next thing
     to try is probably not a prompt rule.
   - **3.1.2 falls out of the top 5 at ITO and at `P_TOD`** since the corpus shrank. That
     is a retrieval question, and retrieval is frozen until the verified-question
     evaluation runs — which is exactly the measurement that should decide it.
   - **`scripts\rebuild_all.ps1` stops at step 1 although the step succeeds.**
     `Invoke-Step` assigns `$code = $LASTEXITCODE` but returns the function's whole output
     stream, which in PowerShell includes the native command's stdout, so the caller's
     `$code` is an array of printed lines and `$code -ne 0` is truthy whenever a step
     prints anything. Its `-DryRun` is correct and was used. The six stages were run
     directly instead, in the order the dry run printed. A one-line fix, left alone
     because this round changes only what its tasks name.
5. **Phase D of the manual checks is still open**, and so are the three things the freeze
   left: the verified questions, the abstention threshold and the reranker.
   `SUPPORT_CHECK` was one of them and is now settled (D-103).
