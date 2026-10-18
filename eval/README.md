# Evaluating ZoneWise retrieval

This folder answers one question: **when someone asks about Delhi planning law, does
ZoneWise find the clause that actually answers them?**

It does not yet. Not because the retriever is bad, but because nobody has checked the
questions. That is the job below, it takes about two hours, and it is the single piece
of work that unblocks every number this project could report.

There is now a screen for it. Read the next two sections and start.

---

## Do this (Windows PowerShell, from the repository root)

**1. Start the backend with the dev flag on.** Leave it running.

```powershell
$env:ZONEWISE_DEV = "1"
uv run python scripts\serve.py
```

Check `http://localhost:8000/api/health` — it should say `"dev_mode": true`. If it says
`false`, the variable was not set in the same terminal that started the server.

**2. Start the web dev server** in a second terminal.

```powershell
cd web
npm install      # first time only
npm run dev
```

**3. Open `http://localhost:5173` and click the "Verify" tab** in the top banner. The tab
only appears when the backend reports dev mode, so if it is missing go back to step 1.

**4. Work through the questions.** One at a time, keyboard-driven:

| key | what it does |
| --- | --- |
| <kbd>A</kbd> | **Accept** — the question and its expected clauses are right as they are |
| <kbd>E</kbd> | **Save edit** — you changed the wording or the expected clauses |
| <kbd>R</kbd> | **Reject** — a bad question; recorded, never scored |
| <kbd>S</kbd> | **Skip** — come back to it |
| <kbd>&larr;</kbd> <kbd>&rarr;</kbd> | previous and next |

Shortcuts are off while the caret is in a text box, so typing an "a" in a question does
not accept it. Accepting or saving an edit moves to the next question automatically.

**5. Run the evaluation** when you have at least 40.

```powershell
uv run python eval\run_eval.py
```

It reads `questions_verified.jsonl` and scores only the records marked `verified: true`,
so you can stop and resume as often as you like.

---

## What the screen shows you, and what to do with it

Everything needed to decide is on one screen, because the decision needs all of it at
once:

- **the question, in an editable box** — rewriting it is the most valuable thing you add
- **a live leakage warning** under the box, updating as you type
- **a small map** with the question's point and its planning zone
- **the expected clause or clauses in full**, not a snippet
- **the current top 5 from `hybrid+location`**, each clickable to mark it expected or
  acceptable
- **a should-abstain toggle** and a **notes** box

### The four things to ask yourself

**1. Does the expected clause really answer this question?** Read it in full — it is
there on screen. If it only half answers, either mark a better result as expected or
soften the question.

**2. Is Claude's one-line answer right?** It is printed under the question box. It is a
paraphrase and it may be subtly wrong: a number transposed, a condition dropped. If it
is wrong, that is a sign the expected clause is wrong too.

**3. Would a real person ask it this way? Rewrite it so they would.** This is the step
that matters most. The drafted questions were written by Claude, from the same chunks
the retriever searches — so a score against them partly measures how well the retriever
agrees with its own author. Your phrasing is independent of the corpus in a way Claude's
cannot be. Write it the way a resident or a small builder would actually put it,
including the vagueness.

**4. For a location question: does your rewrite still avoid naming the zone?** If it
mentions TOD, the metro, land pooling, the Ridge, a low density area or the river, the
location step is no longer being tested — only `get_zones` is supposed to be able to
supply those words. The screen does not check this one for you; it is the one judgement
that needs a person.

### What a good rewritten question looks like

| | |
| --- | --- |
| **Too close to the text** | "What is the maximum permissible ground coverage for a TOD Plot?" |
| **Good** | "How much of my plot am I actually allowed to build on?" |
| **Why** | The second names no zone, quotes no phrase, and is how someone with a plot would ask. Only the location step can know it is a TOD plot. |

| | |
| --- | --- |
| **Too vague to score** | "What are the rules here?" |
| **Good** | "I want to add two floors to my house here. Is that allowed?" |
| **Why** | A question with no subject matches everything and tests nothing. The second is still natural but has one clause that answers it. |

### The leakage warning

Red means the question copies a run of **four or more consecutive words** from a chunk it
points at. Reword it. A question that quotes its own answer tests nothing: BM25 finds it
by string overlap, and the score then says the retriever works when all it has shown is
that two pieces of text share a phrase.

The check also runs when you save, and a question that fails it is refused with the
offending phrase named — so the warning is a convenience, not the enforcement.

### How many to keep

**At least 40**, and the shape matters as much as the number:

| category | target | what it tests |
| --- | --- | --- |
| location | about 17 | the thing this project exists to test: does knowing where the user stands change what is retrieved |
| general | about 17 | ordinary retrieval, no coordinates |
| should-abstain | about 6 | that the system declines rather than inventing an answer |

`run_eval.py` reports `n` per category, so a small verified set is honest as long as its
size is stated. **40 verified questions are worth more than 60 unverified ones**, and
verifying 15 is worth far more than verifying none.

---

## Why the questions have to be verified by a person

`questions_draft.jsonl` holds 60 questions Claude Code wrote by reading the chunks. Every
one has `verified: false`, and `run_eval.py` refuses to score them unless you explicitly
pass `--include-unverified`, in which case every output file is prefixed `DRYRUN_` and
carries a banner.

The reason is not bureaucracy. Those questions were drafted **from the same text the
retriever searches**, by the same model that built the retriever. If a draft question
happens to use the words the chunk uses, retrieval finds it easily and the score says
the system works when all it has shown is that the question and the chunk came from one
mind. Two guards reduce that, both enforced in code:

- **No run of four or more consecutive words** copied from any chunk a question points
  at. All 60 drafts pass; the check is `app.dev_eval.leakage`, and the screen runs it on
  every rewrite.
- **A location question may not name its zone or topic.** All 25 pass.

Those guards stop the crudest form of cheating. They cannot fix a question that is
unnatural, or one whose expected answer is simply wrong. Only you can.

**Numbers from unverified questions must never appear in the README, on a resume, or in
an interview.** Every dry-run report carries a banner saying so.

---

## Running it

```powershell
# the real thing: verified questions only
uv run python eval\run_eval.py

# a dry run that proves the harness works, labelled so it cannot be mistaken
uv run python eval\run_eval.py --include-unverified --label night3
```

Results land in `eval/results/` as a Markdown report to read and a JSON file to compare
against later runs.

Five configurations are scored on the same questions:

| configuration | what it is |
| --- | --- |
| `dense` | embeddings only — matches meaning, misses exact strings |
| `bm25` | keywords only — matches exact strings, misses paraphrase |
| `hybrid` | both, fused with reciprocal rank fusion |
| `hybrid+location` | hybrid plus the zone exclusion, boost and query expansion |
| `hybrid+location+rerank` | and then a cross-encoder rescores the top 20 |

`hybrid+location` can only differ from `hybrid` on questions that carry coordinates, so
the report states how many of those there were. Comparing the two **is the experiment
this project exists to run**. The rerank configuration appears only when the installed
fastembed has a cross-encoder, and it is off in normal operation until these numbers say
it earns its 2.4 seconds a query.

---

## What each metric means

**recall@k** — "was the right clause in the top k?" One question scores 1 or 0, and the
metric is the share that scored 1. recall@5 of 0.74 means that for 74 questions in 100,
at least one acceptable clause appeared in the top five. It says nothing about where in
those five it was.

**MRR (mean reciprocal rank)** — the same question, but position matters. A question
whose answer came first scores 1, second 0.5, fourth 0.25, missed 0. Use it when two
configurations have the same recall@5: the one with the higher MRR is putting the answer
nearer the top, which is what a user actually experiences.

**Bootstrap 95% confidence interval** — "how much would this number move if I had asked
a different 50 questions?" The questions are resampled with replacement 1,000 times, the
average computed each time, and the middle 95% of those averages is the interval. It
exists because with 50 questions a recall of 0.74 could easily have been 0.62 or 0.86.
Two configurations whose intervals overlap heavily have **not** been shown to differ. The
seed is fixed, so the same data gives the same interval every run.

**The paired difference interval** — the same idea for "does location help?", computed
per question: for each question, (did location find it?) minus (did hybrid find it?),
then bootstrapped. Pairing cancels the fact that some questions are simply harder. An
interval that **excludes 0** is evidence the difference is real. An interval containing 0
means this question set is too small to say — which is a finding, not a failure.

**The abstention analysis** — retrieval only, no LLM call, one section per candidate
signal. For each, the p5/p25/p50/p75/p95 of the top-1 score for should-abstain questions
against answerable ones, then a sweep: for each candidate threshold, the share of
should-abstain questions caught against the share of answerable ones wrongly refused.

Read the `fused_score` section first, because it is there to be rejected. Its two
percentile rows are nearly identical — an RRF score only encodes rank position, so the
best chunk for an unanswerable question scores what the best chunk for a good question
scores. That is why `abstain_signal` is now `dense_cosine` or `rerank_score`
instead (D-071).

Each section names two thresholds. The **provisional** one is the highest value that
refuses nothing at all, and it is the only one that may be adopted from a dry run. The
**widest margin** one is the value to adopt once these questions are verified — at which
point it is a measurement rather than a number fitted to questions Claude wrote.

`settings.abstain_threshold` is **0.5804 today and that is provisional** (D-071). On the
drafted questions it catches none of the should-abstain questions, which is the honest
state of affairs rather than a broken guard: the two distributions overlap almost
entirely on the dense signal. Setting the real value is step 7 of the morning checklist.

---

## The files

| file | what it is |
| --- | --- |
| `points.json` | 26 named points with their full `get_zones` result, built by `scripts/08_eval_points.py` from the map layers. 8 come from `data/test_points.json`; 3 more sit in each of the six policy zones. |
| `questions_draft.jsonl` | the 60 drafted questions, all unverified. Regenerated by `scripts/09_draft_questions.py`, never written by the screen. |
| `questions_verified.jsonl` | **the screen writes this.** One record per decision, updated in place by id. Accepted and edited questions carry `verified: true`; rejected and skipped ones are recorded with `verified: false` so "looked at and rejected" is distinguishable from "not reached". |
| `questions.jsonl` | the hand-edited file night 2's instructions described. Still read if it exists, so that work is not orphaned. |
| `remap_log.json` | one row per chunk id the last re-chunk considered, and what happened to it (D-067). |
| `metrics.py` | the arithmetic: recall, MRR, bootstrap, the sweep. Tested against hand-worked numbers. |
| `run_eval.py` | runs every configuration over every question and writes the report. |
| `results/` | one Markdown report and one JSON file per run. |

---

## Known gaps in the evaluation

- **Retrieval only.** It scores whether the right clause was found, not whether the
  answer written from it was correct. Grading answers needs a verified expected answer
  per question and a second pass.
- **The question set is small.** 60 drafted, likely 40-odd verified. The confidence
  intervals are wide and the report says so rather than hiding it.
- **Three of the extra HDC points also fall in land pooling areas.** The corridor follows
  UER-II straight through them, so there is no point in the corridor alone there. The
  expected clauses for those questions were chosen with that in mind.
- **Planning zone A is missing from DDA's layer** (D-039), so no question is asked inside
  the Walled City.
- **No question is asked at P_RIDGE yet.** The Ridge has no policy section in MPD-2047
  (D-069), so the honest question there is probably a should-abstain one. Worth adding by
  hand while verifying.
