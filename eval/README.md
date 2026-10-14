# Evaluating ZoneWise retrieval

This folder answers one question: **when someone asks about Delhi planning law, does
ZoneWise find the clause that actually answers them?**

It does not yet. Not because the retriever is bad, but because nobody has checked the
questions. That is the job described below, and it is yours — it cannot be delegated to
the thing being measured.

---

## Why the questions have to be verified by a person

`questions_draft.jsonl` holds 60 questions that Claude Code wrote by reading the chunks.
Every one has `verified: false`, and `run_eval.py` refuses to score them unless you
explicitly pass `--include-unverified`.

The reason is not bureaucracy. Those questions were drafted **from the same text the
retriever searches**, by the same model that built the retriever. If a draft question
happens to use the words the chunk uses, retrieval finds it easily and the score says
the system works when all it has shown is that the question and the chunk came from one
mind. Two guards reduce that, both enforced in code by `scripts/09_draft_questions.py`:

- **No run of four or more consecutive words** may be copied from any chunk a question
  points at. (All 60 pass; the check is in `leakage()`.)
- **A location question may not name its zone or topic.** "How much of my plot can I
  build on?" asked at a point in a TOD zone is the real test, because only the location
  step can supply the word TOD. (All 25 pass; the check is `names_a_zone()`.)

Those guards stop the crudest form of cheating. They cannot fix a question that is
unnatural, or one whose expected answer is simply wrong. Only you can.

**Numbers from unverified questions must never appear in the README, on a resume, or in
an interview.** Every dry-run report carries a banner saying so.

---

## How to verify one question

Expect about three minutes each, so roughly three hours for all 60. Doing 15 is far
better than doing none — `run_eval.py` reports `n` per category, so a small verified set
is honest as long as its size is stated.

**1. Open the draft file.**

```powershell
code eval\questions_draft.jsonl
```

Each line is one question:

```json
{"id": "loc-01", "question": "I own a 2,500 sqm plot here. How much of the land am I allowed to cover with building?",
 "point_name": "P_TOD", "lat": 28.6328, "lon": 77.2197, "category": "location",
 "expected_chunk_ids": ["MPD47_GAZETTE_EN:4.2.3@p753:0"],
 "acceptable_chunk_ids": ["MPD47_FAQ:Q13@p13:0", "MPD47_FAQ:Q12@p13:0"],
 "expected_answer_short": "Up to 40% of the plot, with relaxations possible from the TOD Committee.",
 "should_abstain": false, "verified": false, "drafted_by": "claude_code", "notes": "..."}
```

**2. Read the chunk it expects.**

```powershell
uv run python scripts\show_chunk.py MPD47_GAZETTE_EN:4.2.3@p753:0
```

This prints the clause in full with its document, chapter, clause number, pages and
source link.

**3. Ask yourself four things.**

- **Does this chunk really answer the question?** If it only half answers, either fix
  the expected id or soften the question.
- **Is `expected_answer_short` correct?** It is Claude's paraphrase and may be subtly
  wrong — a number transposed, a condition dropped.
- **Would a real person ask it this way?** This is the most valuable thing you add.
  Rewrite it in your own words, the way a resident or a small builder would actually
  put it. Your phrasing is independent of the corpus in a way Claude's cannot be.
- **For a location question: does it still avoid naming the zone?** If your rewrite
  mentions TOD, the metro, land pooling or the river, the location step is no longer
  being tested.

**4. Fix the expected ids if they are wrong.** To find the right one:

```powershell
uv run python scripts\search.py "maximum ground coverage TOD plot" --k 5
uv run python scripts\search.py "how much can I build here" --lat 28.6328 --lon 77.2197
```

Put the clause that genuinely answers the question in `expected_chunk_ids` (1 to 3
ids). Put anything that would also be a fair answer — the FAQ version of the same rule,
an adjacent clause — in `acceptable_chunk_ids`. Both count as a hit when scoring.

**5. Set `verified: true`** and save the line into `eval/questions.jsonl`.

`run_eval.py` reads `questions.jsonl` when it exists and falls back to
`questions_draft.jsonl` otherwise, so the draft stays untouched as a record of what was
generated. Start the verified file by copying the draft:

```powershell
Copy-Item eval\questions_draft.jsonl eval\questions.jsonl
```

then edit `questions.jsonl` as you go. Re-running `scripts\09_draft_questions.py`
overwrites the draft but never the verified file.

---

## Running it

```powershell
# the real thing: verified questions only
uv run python eval\run_eval.py

# a dry run that proves the harness works, labelled so the numbers cannot be mistaken
uv run python eval\run_eval.py --include-unverified
```

Results land in `eval/results/` as a Markdown report to read and a JSON file to compare
against later runs. A dry run is prefixed `DRYRUN_`.

Four configurations are scored on the same questions:

| configuration | what it is |
| --- | --- |
| `dense` | embeddings only — matches meaning, misses exact strings |
| `bm25` | keywords only — matches exact strings, misses paraphrase |
| `hybrid` | both, fused with reciprocal rank fusion |
| `hybrid+location` | hybrid plus the zone exclusion, boost and query expansion |

`hybrid+location` can only differ from `hybrid` on questions that carry coordinates, so
the report states how many of those there were. Comparing the two **is the experiment
this project exists to run**: it is the number that says whether knowing where the user
is standing actually helps.

---

## What each metric means

**recall@k** — "was the right clause in the top k?" One question scores 1 or 0, and the
metric is the share that scored 1. recall@5 of 0.74 means that for 74 questions in 100,
at least one acceptable clause appeared in the top five. It says nothing about where in
those five it was.

**MRR (mean reciprocal rank)** — the same question, but position matters. A question
whose answer came first scores 1, second 0.5, fourth 0.25, missed 0. Averaged over the
questions. Use it when two configurations have the same recall@5: the one with the
higher MRR is putting the answer nearer the top, which is what a user actually
experiences.

**Bootstrap 95% confidence interval** — "how much would this number move if I had asked
a different 50 questions?" The questions you have are resampled with replacement 1,000
times, the average is computed each time, and the middle 95% of those averages is the
interval. It exists because with 50 questions a recall of 0.74 could easily have been
0.62 or 0.86, and quoting 0.74 alone hides that. Two configurations whose intervals
overlap heavily have **not** been shown to differ. The seed is fixed, so the same data
gives the same interval every run.

**The paired difference interval** — the same idea for "does location help?", but
computed per question: for each question, (did location find it?) minus (did hybrid find
it?), then bootstrapped. Pairing matters because both configurations answered the same
questions, so the difference cancels out the fact that some questions are simply harder.
An interval that **excludes 0** is evidence the difference is real. An interval
containing 0 means this question set is too small to say — which is a finding, not a
failure.

**The threshold sweep** — retrieval only, no LLM call. For each candidate value of
`settings.abstain_threshold`, it reports the share of should-abstain questions whose top
fused score falls below it (**caught**, higher is better) against the share of answerable
questions that would be wrongly refused (**lost**, lower is better), and suggests the
value with the widest gap. Ties go to the lower threshold, because wrongly refusing a
real question is worse than letting an unanswerable one through to the citation check.

This sweep is how `abstain_threshold` gets its real value. It is **0.02 today, and that
is a placeholder** (D-042) — a guess from the arithmetic of RRF, not a measurement.
Do not change it from a dry run.

---

## The files

| file | what it is |
| --- | --- |
| `points.json` | 18 named points with their full `get_zones` result, built by `scripts/08_eval_points.py` from the map layers. 6 come from `data/test_points.json`; 3 more sit in each of the four policy zones. |
| `questions_draft.jsonl` | the 60 drafted questions, all unverified. Regenerated by `scripts/09_draft_questions.py`. |
| `questions.jsonl` | **you create this** — the verified questions. Read in preference to the draft. |
| `metrics.py` | the arithmetic: recall, MRR, bootstrap, the threshold sweep. Tested in `tests/test_eval_metrics.py` against hand-worked numbers. |
| `run_eval.py` | runs every configuration over every question and writes the report. |
| `results/` | one Markdown report and one JSON file per run. |

## What the question set covers

**25 location questions**, at points in TOD zones, the high density corridor, land
pooling areas, planning zone O and one ordinary plot in none of them. None names its
zone.

**25 general questions** with no coordinates, spread across TOD, the high density
corridor, land pooling, the river and floodplain, redevelopment, residential, commercial
and industrial norms, the annexures on permissible activities, the FAQs and the Delhi
High Court order.

**10 that should be refused**: property tax, Mumbai rules, rent control, land prices,
bank loans, a point in Gurugram, and questions the documents genuinely do not settle
("will my plan be approved?", "who won the case?"). These have no expected chunks; they
exist to test that the system declines rather than inventing an answer.

## Known gaps in the evaluation

- **Retrieval only.** It scores whether the right clause was found, not whether the
  answer written from it was correct. Grading answers needs a second pass and a
  verified expected answer for each question, which is a Day 5 job.
- **The question set is small.** 60 questions, likely fewer once verified. The
  confidence intervals are wide and the report says so rather than hiding it.
- **Three of the extra HDC points also fall in land pooling areas.** The corridor
  follows UER-II straight through them, so there is no point in the corridor alone at
  those locations. The expected clauses for those questions were chosen with that in
  mind.
- **Planning zone A is missing from DDA's layer** (D-039), so no question is asked
  inside the Walled City.
