# Freeze for evaluation: v1.0-rc1

> **This is a recording, built from existing reports and state files, not a new
> measurement.** No LLM call was made to produce it. Every number below comes from
> `reports/live_answers_v1.md`, `reports/live_answers_v2.md`, `reports/live_answers_v3.md`
> or `reports/live_run_state_v3.json`, read as they stood on 20 October 2026. Where a
> number is not stated in one of those files, this report says "not recorded" rather than
> estimating it.

The repository is tagged `v1.0-rc1` here (L2, DECISIONS.md D-099): no change to
retrieval, chunking, prompts, the model or any threshold until the evaluation on
`eval/questions_verified.jsonl` has run. The v3 live run itself is **partial** — 16 of 23
cases — and is not resumed by this job (L1, D-098); the state and report files for v3
are untouched here and will be rewritten when Dhruv runs `--resume` in his own terminal.

---

## v1 / v2 / v3 totals

Each row is read from that run's own report header (`reports/live_answers_v{N}.md`),
except where noted. "All runs" tokens and calls are the cumulative figures those headers
report — v1 ran in two sittings before being stopped by hand, v2 and v3 each ran once so
far.

| | v1 | v2 | v3 (partial) |
| --- | --- | --- | --- |
| Cases run | 37 of 51 | 21 of 21 | **16 of 23** |
| Answered | 21 | 18 | 13 |
| Abstained | 16 | 3 | 3 |
| … `citation_check_failed` | 10 | 0 | 0 |
| … `model_abstained` | 5 | 2 | 2 |
| … `outside_delhi` | 1 | 1 | 1 |
| First-attempt citation pass, full run | not recorded¹ | not recorded¹ | not recorded¹ |
| Citation retries | 18 | 0 | 0 |
| Tokens used, all runs | 197,200 | 75,808 | 68,400 |
| LLM calls, all runs | 80 | 35 | 28 |

¹ None of the three reports' own header tables states a single first-attempt pass rate
for the *whole* run. `reports/live_answers_v3.md` computes one, but only over the **16
DEMO cases all three runs share** (not the full case count of any of them, and not
including any agent-mode case, since v3's partial run has not yet reached its 5 agent
cases or 2 probes):

| | v1 | v2 | v3 |
| --- | --- | --- | --- |
| First-attempt pass rate, map mode (16 shared cases) | 14% (2 of 14) | 100% (13 of 13) | 100% (13 of 13) |
| First-attempt pass rate, agent mode (16 shared cases) | not recorded | not recorded | not recorded |

`reports/citation_failures_v1.md` separately states an **18%** first-attempt pass rate
for v1 (4 of 22), but that figure is computed over a different set — all 22 map-mode
cases v1 reached, including cases outside the 16-case comparison set — so it is not
placed in the table above, which this job was told to build only from the three
`live_answers` reports and the v3 state file.

**v3-only measurements, from `reports/live_answers_v3.md`** (neither v1 nor v2 has
these fields):

| | v3 |
| --- | --- |
| Location notes shown (of 13 answered) | 0 |
| Claim check ran on | 13 |
| Sentences `supported` | 29 |
| Sentences `partly` | 3 |
| Sentences `unsupported` | 1 |
| Cases `enforce` mode would change | 1 (`demo-10`) |
| … of those, would abstain | none |
| Tokens per case (mean) | 4,275 |
| … of which, the answer | 2,730 |
| … of which, the claim check | 1,546 |

---

## Remaining manual work

1. **Resume the v3 live run.** `uv run python scripts\live_run.py --resume`, from
   Dhruv's own terminal — not part of this freeze, and not run by this job (L1).
2. **Phase A — verify the evaluation questions.** Keep ≥40 in the Verify screen: ~17
   location, ~17 general, ~6 should-abstain (`docs/PROJECT_STATUS.md` §7, item 7).
3. **Phase B — run the real evaluation.** `eval/run_eval.py` against
   `eval/questions_verified.jsonl` — the first quotable retrieval numbers this project
   will have had.
4. **Phase C — read the claim check's verdicts and decide `SUPPORT_CHECK`.** v3's
   shadow-mode verdicts (13 answers, 1 `enforce`-would-change) are a start; Phase B's
   verified-question run is what the decision should actually rest on.
5. **Phase D — set the final `ABSTAIN_THRESHOLD`.** `scripts\tune_abstention.py` against
   the verified questions, then remove the word "provisional" from `app/config.py`,
   `.env.example` and `eval/README.md`.
6. **Phase E — decide the reranker.** Compare `hybrid+location` against
   `hybrid+location+rerank` (and `hybrid+location_v2` against the shipped four-list
   fusion) in the verified evaluation report.
7. **Phase F — build and smoke-test the Docker image**, after the C: free-space item in
   `docs/PROJECT_STATUS.md` §7 is resolved.
8. **Phase G — deploy, record the demo GIF, make the repository public**, and only then
   write the resume-quotable numbers — from Phase B's run, with n and the confidence
   interval, per `docs/PROJECT_STATUS.md` §7 items 12-15.

Any fix made along the way is governed by L2 (D-099): minimal, in response to a defect a
human check actually found, done in one round, tagged `v1.0-rc2`.
