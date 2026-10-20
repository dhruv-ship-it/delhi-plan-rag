# Why the citation retries happened (v1)

Read from `reports/live_run_state.json`, 37 recorded case(s), 26 of them map mode. Regenerate with `uv run python scripts\classify_citation_failures.py`.

## The question this file was asked, and why it cannot be answered exactly

The task was to classify **every first-attempt validation failure by rule** —
unknown marker, uncited sentence, a sentence-splitting artefact, or something
else. That cannot be done from a v1 state file, and the reason is worth stating
plainly rather than worked around:

- `app/answer.py` built the problems list, put it in the retry prompt, and threw
  it away. Nothing returned it to the caller.
- `scripts/live_run.py` recorded the **final** answer and the retry **count**. The
  rejected attempt was never written down, and neither was the problems list.
- `data/logs/requests.jsonl` is written by `app/api.py`; the live run called
  `answer_point` directly, so none of it is in there either.

So the 18 retries are a number without a breakdown. Two things follow. The
structured-answer change this file was written to sanity-check **adds
`validation_failures` to `AnswerResult`**, one problems list per rejected
attempt, so a v2 state file answers the question by being read rather than
inferred from. And what *can* be derived from v1 is derived below, labelled for
what it is.

## What the first attempt did, per case (exact)

This part needs no inference: a map-mode case made one call unless the check
rejected it, so the retry count is the first-attempt verdict.

| first-attempt outcome | n |
| --- | --- |
| failed the check | **18** |
| passed the check | **4** |
| the model declined, so there was nothing to check | **3** |
| never reached the model | **1** |

So of the **22** map-mode answers that actually reached the citation
check, **18 failed** and **4 passed** — a first-attempt pass rate of **18%**
(4 of 22). 13 were rescued by the single retry and **5** failed twice and abstained.

| | cases |
| --- | --- |
| passed first time | `demo-10`, `demo-15`, `draft-loc-15`, `draft-loc-21` |
| failed, then passed | `demo-01`, `demo-02`, `demo-03`, `demo-04`, `demo-05`, `demo-06`, `demo-07`, `demo-11`, `demo-13`, `demo-14`, `draft-loc-18`, `draft-loc-17`, `draft-loc-19` |
| failed twice | `demo-12`, `demo-16`, `draft-loc-07`, `draft-loc-06`, `draft-loc-16` |

## What the surviving answers suggest about the rule (inference, not record)

Measured over the **17** map-mode answers that were shown. Every
one of them passed, so none of these numbers is a failure; they describe the
shape the model had to reach, which is evidence about what it had to be told.

| measurement | n of 17 |
| --- | --- |
| answers with at least one line holding more than one sentence | **6** |
| answers where a marker is repeated sentence-by-sentence inside one line | **3** |
| answers carrying prompt rule 6's “check official DDA documents” sentence | **7** |
| … and that sentence carries a citation marker | **7** |
| answers that cite the last source available to them (`[C6]`) | **5** |

Read the third and fourth rows together, because they are the sharpest thing in
this file. **The prompt's own rules 2 and 6 conflict.** Rule 6 asks the model to
say that official DDA documents should be checked; no clause in the corpus says
that, so the sentence has no source. Rule 2 says every sentence must carry a
marker. The only way to satisfy both is to attach a marker to a sentence the
marker does not support — which is what the surviving answers do, and which the
citation check cannot detect, because it checks that a marker is *present* and
*valid*, never that the clause *says* the sentence.

That is consistent with `uncited sentence` being the rule that fired, and with
the splitter being how it fired: a model writing ordinary prose puts one marker
at the end of a thought, and a thought is often two sentences. It is **not**
proof. The alternative — `unknown marker` — cannot be ruled out from here,
though it is the less likely of the two: the sources are printed to the model as
`[C1]` to `[C6]` immediately above the question, and an out-of-range marker
means inventing a seventh.

## What this says about the structured-answer change

It supports it, and it also moves the target.

1. **If the rule was `uncited sentence`, structure removes the rule.** The model
   returns `{"sentences": [{"text": …, "citations": […]}]}`, so there is no
   splitter to disagree with and no way to write a sentence without a citation
   field — the pairing is the data structure rather than a convention about where
   to put brackets. A list item, a heading and a parenthetical stop being hazards.
2. **If the rule was `unknown marker`, structure still helps**, because a citation
   is now one array element to check rather than a token inside prose, and the
   retry can name it exactly.
3. **Neither fixes the thing this file actually found.** A marker attached to a
   sentence it does not support passes every structural check there is. That is
   why the no-synthesis prompt rule ships alongside the JSON contract, and it is
   the same limitation `docs/ARCHITECTURE.md` already states and that `demo-07`
   demonstrated live (D-085).
