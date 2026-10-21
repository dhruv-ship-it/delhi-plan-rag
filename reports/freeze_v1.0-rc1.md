# Freeze for evaluation: v1.0-rc1

> **This is a recording, built from existing reports and state files, not a new
> measurement.** No LLM call was made to produce it. Every number below comes from
> `reports/live_answers_v1.md`, `reports/live_answers_v2.md`, `reports/live_answers_v3.md`
> or `reports/live_run_state_v3.json`, read as they stood on 20 October 2026. Where a
> number is not stated in one of those files, this report says "not recorded" rather than
> estimating it.
>
> **Updated on 21 October 2026**, in one respect only: the v3 run was partial when this
> report was written and is now **complete, 23 of 23**. The v3 columns below carry the
> finished figures, each read from the same two files after the run ended. Nothing else
> in this report changed, and no LLM call was made to update it either (fix round 1,
> task 7a).

The repository is tagged `v1.0-rc1` here (L2, DECISIONS.md D-099): no change to
retrieval, chunking, prompts, the model or any threshold until the evaluation on
`eval/questions_verified.jsonl` has run. The v3 live run was **partial** when this
report was written — 16 of 23 cases — and was not resumed by the freezing job (L1,
D-098). It has since been resumed and **finished: 23 of 23**.

---

## v1 / v2 / v3 totals

Each row is read from that run's own report header (`reports/live_answers_v{N}.md`),
except where noted. "All runs" tokens and calls are the cumulative figures those headers
report — v1 ran in two sittings before being stopped by hand, v2 and v3 each ran once so
far.

| | v1 | v2 | v3 |
| --- | --- | --- | --- |
| Cases run | 37 of 51 | 21 of 21 | **23 of 23** |
| Answered | 21 | 18 | 17 |
| Abstained | 16 | 3 | 6 |
| Failed outright | 0 | 0 | 0 |
| … `citation_check_failed` | 10 | 0 | 0 |
| … `model_abstained` | 5 | 2 | 5 |
| … `outside_delhi` | 1 | 1 | 1 |
| First-attempt citation pass, full run | not recorded¹ | not recorded¹ | not recorded¹ |
| Citation retries | 18 | 0 | 0 |
| Tokens used, all runs | 197,200 | 75,808 | 123,276 |
| LLM calls, all runs | 80 | 35 | 57 |

¹ None of the three reports' own header tables states a single first-attempt pass rate
for the *whole* run. `reports/live_answers_v3.md` computes one, but only over the **21
cases all three runs share** — the 16 DEMO cases and the 5 agent cases, not v3's 2 new
probes and not the drafted questions v1 reached:

| | v1 | v2 | v3 |
| --- | --- | --- | --- |
| First-attempt pass rate, map mode (21 shared cases) | 14% (2 of 14) | 100% (13 of 13) | 100% (13 of 13) |
| First-attempt pass rate, agent mode (21 shared cases) | not recorded | 100% (5 of 5) | 100% (3 of 3) |

The agent denominators differ because only a case whose answer reached the citation
check is counted, and v3 declined two agent cases that v2 answered.

`reports/citation_failures_v1.md` separately states an **18%** first-attempt pass rate
for v1 (4 of 22), but that figure is computed over a different set — all 22 map-mode
cases v1 reached, including cases outside the 16-case comparison set — so it is not
placed in the table above, which this job was told to build only from the three
`live_answers` reports and the v3 state file.

**v3-only measurements, from `reports/live_answers_v3.md`** (neither v1 nor v2 has
these fields):

| | v3, over the 21 shared cases | v3, all 23 cases |
| --- | --- | --- |
| Location notes shown | 2 | 4 |
| Claim check ran on | 16 | 17 |
| Sentences `supported` | 34 | 35 |
| Sentences `partly` | 4 | 4 |
| Sentences `unsupported` | 1 | 1 |
| Cases `enforce` mode would change | 1 (`demo-10`) | 1 (`demo-10`) |
| … of those, would abstain | none | none |
| Tokens per case (mean) | 5,294 | not stated in the report |
| … of which, the answer | 3,917 | not stated in the report |
| … of which, the claim check | 1,377 | 1,765 (recounted from the state file) |

The two columns are two denominators, not a disagreement: the comparison table in
`reports/live_answers_v3.md` is computed over the 21 cases every run shares, and the
right-hand column counts all 23. `SUPPORT_CHECK=enforce` was decided on the left-hand
column (D-103).

---

## Remaining manual work

1. ~~**Resume the v3 live run.**~~ Done on 21 October 2026: 23 of 23 cases.
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
