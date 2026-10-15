# Learning notes

Every AI-engineering idea used in ZoneWise, explained from scratch, with the place in
this repository where it actually lives.

Each entry has four parts: **what it is**, **where it lives here**, **why we chose it**,
and **how to explain it in an interview** — two or three sentences you could say out
loud. The interview lines are deliberately concrete: they name what *this* project did,
because "we used hybrid search" is a thing anyone can say and "we used BM25 because
clause numbers like 4.2.1 are exact strings that embeddings blur" is not.

---

## 1. Chunking

**What it is.** A language model cannot read 560 pages for every question, and a search
index cannot usefully return "the whole gazette". So the documents are cut into pieces —
chunks — of a few hundred words each, and search returns the handful most likely to
answer the question. The hard part is deciding where to cut. Cut in the wrong place and
a clause is split down the middle, so neither half makes sense on its own.

**Where it lives here.** `app/chunking.py`. The entry points are `chunk_gazette()`,
`chunk_faq()` and `chunk_paragraph_document()`; the size rules are
`merge_small_sections()`, `fold_heading_only_sections()` and `split_section()`. Run by
`scripts/03_chunk.py`, which writes `data/processed/chunks.jsonl` and a report.

**Why we chose it this way.** We cut on the document's own structure rather than every
N characters, because the gazette already tells you where a thought begins: "4.2.1
Definitions" is a boundary the authors put there. Fixed-size chunking would cut through
the middle of a table of FAR limits. The sizes (target 150-400 words, merge under 40,
split over 500) come from a trade-off: too small and a chunk is half a thought with
little for the embedding to work with, too large and it covers two subjects so the
citation stops being precise. 64% of our chunks land in the target band and none exceeds
500 words.

**How to explain it in an interview.** "I chunked on the document's own section
headings rather than a fixed window, because the gazette numbers its clauses and those
numbers are where a reader's eye stops. The fiddly part was telling a real heading from
a table cell — a line like '3.50 80.50 0.05' looks exactly like one — so inside a
chapter I required a heading's first number to equal the chapter number, which removed
every false positive across 250 pages of norms tables."

---

## 2. Embeddings and dense retrieval

**What it is.** An embedding turns a piece of text into a list of numbers — here 384 of
them — positioned so that texts meaning similar things end up close together. Searching
means embedding the question and finding the chunks whose vectors are nearest. The
useful property is that it matches **meaning, not words**: "how wide is the TOD zone"
can find a clause that says "area under 500m wide corridor on either side of centreline"
without sharing a single content word.

**Where it lives here.** `app/indexing.py`: `embedder()` opens the model,
`build_dense_index()` embeds every chunk, and `SearchIndex.dense_pool()` in
`app/retrieval.py` searches. The model is `BAAI/bge-small-en-v1.5` via fastembed, cached
in `data/index/models`.

**Why we chose it this way.** A small local model rather than an embedding API: it is
384 dimensions and 64 MB, runs on a laptop CPU at about five chunks a second, costs
nothing and needs no key, which matters for a project that must stay free to run.
One subtlety: BGE models are trained **asymmetrically**, so documents go through
`passage_embed()` and questions through `query_embed()`, which adds an instruction
prefix. Using the same call for both costs real accuracy on short questions, which is
exactly what we get asked.

**How to explain it in an interview.** "Dense retrieval matches meaning, so a question
phrased in everyday words can reach a clause written in planning language. I used a
small local BGE model so there is no embedding API in the loop, and I was careful to use
the passage and query sides of it correctly — BGE is trained asymmetrically and using
`embed()` for both sides quietly costs you accuracy on short questions."

---

## 3. BM25 and keyword retrieval

**What it is.** The classic keyword method. BM25 scores a document by how many of the
query's words it contains, weighted so that rare words count for more than common ones
and so that a very long document does not win just by being long. No machine learning;
it is counting, done carefully.

**Where it lives here.** `app/indexing.py`: `tokenize()` and `build_bm25_index()`, with
`SearchIndex.bm25_pool()` searching. The model and the chunk order are pickled together
into `data/index/bm25.pkl`.

**Why we chose it this way.** Because embeddings are bad at exactly the things this
corpus is full of. "4.2.1", "FAR", "2000 sqm", "UER-II" are **exact strings**: an
embedding blurs them into a general sense of planning-ness, while BM25 lands on the
clause that literally contains them. Our tokenizer therefore keeps a dotted clause
number whole, so searching "4.2.1" finds clause 4.2.1 rather than every chunk containing
a 4, a 2 and a 1. The stopword list is written out in the file rather than pulled from
NLTK, because one list of common words is not worth a dependency.

**How to explain it in an interview.** "BM25 is there for the things embeddings are
worst at: clause numbers, acronyms and figures. In a legal corpus those are most of what
people actually search for, so I kept dotted clause numbers as single tokens — searching
'4.2.1' should find clause 4.2.1, not every chunk with a four in it."

---

## 4. Hybrid search and reciprocal rank fusion

**What it is.** Running both searches and combining the two result lists. The catch is
that the two scores are not comparable: a cosine distance runs 0 to 2 and a BM25 score
runs 0 to about 30 and depends on the corpus, so adding them would let BM25 decide
everything. Reciprocal rank fusion sidesteps that by throwing the scores away and using
only the **positions**: a chunk scores `1/(k + rank)` in each list it appears in, summed.

**Where it lives here.** `reciprocal_rank_fusion()` in `app/retrieval.py`, with `k = 60`
in `app/config.py`. Each index contributes its top 30.

**Why we chose it this way.** k = 60 is the value from the original paper, and it has
the behaviour we want: rank 1 scores 0.0164 and rank 2 scores 0.0161, a 2% gap, so a
chunk that **both** indexes placed in their top ten beats a chunk one index ranked first
and the other missed entirely. Agreement counts for more than one index's confidence. A
small k would do the opposite. One detail that is a decision rather than a default: a
BM25 result scoring exactly zero shares no word with the query, so it is dropped rather
than padding the pool — otherwise an unrelated chunk at keyword rank 12 would still earn
fusion points.

**How to explain it in an interview.** "RRF fuses on rank rather than score, which is
what makes it safe — a cosine distance and a BM25 score aren't on the same scale and
can't be added. With k=60 the gap between consecutive ranks is small, so a chunk both
indexes liked beats a chunk that only one was confident about. That's the behaviour you
want from a fusion: agreement should outweigh one retriever's enthusiasm."

---

## 5. Metadata filtering

**What it is.** Storing structured fields next to each vector — document, chapter, page,
clause number, zone flags — so a search can be restricted before or after the similarity
step. The index stops being "a bag of text" and becomes something you can ask
*structured* questions of.

**Where it lives here.** `chunk_metadata()` in `app/indexing.py` builds what Chroma
stores. Chroma accepts strings, numbers and booleans only, so `clause_id` is `""` rather
than null, and the zone tags are **flattened into eight booleans** (`zp_tod`, `zm_tod`
and so on) because a list cannot be filtered on.

**Why we chose it this way.** That flattening is the design point worth remembering.
`zone_mentions: ["tod", "hdc"]` is natural to write and impossible to filter; `zm_tod:
true` is filterable. The lists stay in `chunks.jsonl`, which remains the single source
of truth for display, while the index holds only what it needs to filter and rank.

**How to explain it in an interview.** "The vector store holds scalar metadata only, so
I flattened the zone tags into booleans — you can put `zm_tod = true` in a where clause
and you cannot filter on a list. The chunk text and the richer fields stay in the JSONL
the index was built from, so there's one source of truth and the index stays small."

---

## 6. Location-aware retrieval: exclude, expand, boost

**What it is.** The idea this whole project exists to test. A planning clause does not
apply everywhere, so knowing *where the user is standing* should change what search
returns. Three steps, in order: **exclude** clauses whose own policy covers a zone the
point is not in; **expand** the query with the point's zone words; **boost** clauses
about the point's zones.

**Where it lives here.** `app/location.py`: `should_exclude()`, `expand_query()`,
`matches_point()`, orchestrated by `location_aware_search()`. The zone lookup is
`get_zones()` in `app/spatial.py`.

**Why we chose it this way.** The three steps do different jobs and carry different
risks. Expansion is what makes a question with no zone words work at all: "how much of
my plot can I build on?" contains nothing for either index to match on, so plain hybrid
answers it from whichever ground-coverage clause is most popular — which turns out to be
the TOD one, wherever you are standing. Exclusion is the only step that can **lose** a
relevant answer, so it acts only on `zone_primary` (a claim about where a rule applies)
and never on a mere mention, and a chunk with no primary zone is never dropped, which
keeps the general norms always in play. Boosting is the weak step and reads mentions too.

The effect is visible in `reports/day3_location_compare_v2.md`: at a point in the High
Density Corridor, plain hybrid's top two results are TOD ground-coverage rules — the
wrong policy — and location-aware search returns the HDC norms first and second.

**How to explain it in an interview.** "Most RAG systems treat every query the same.
Here the same question has a different right answer depending on where the user clicked,
so I do a point-in-polygon lookup first and use it three ways: drop rules that belong to
zones the point isn't in, add the zone's vocabulary to the query, and boost clauses about
that zone. The asymmetry matters — exclusion is the only step that can lose a real
answer, so it only fires on a chunk's own policy section, never on a passing mention."

---

## 7. Grounding

**What it is.** Making the model answer **only** from text you gave it, rather than from
what it absorbed in training. The mechanism is unglamorous: retrieve the relevant
passages, put them in the prompt as numbered sources, and instruct the model to use
nothing else.

**Where it lives here.** `SYSTEM_PROMPT` and `build_user_message()` in `app/answer.py`.
Each source carries a header line naming the document, the clause, the pages and the
authority rank.

**Why we chose it this way.** A model answering about Delhi planning law from memory
would be fluent and unverifiable — the worst combination. The authority rank in each
header exists for one specific rule: when the FAQ and the gazette disagree, the model is
told to follow the gazette (rank 1, the law) over the FAQ (rank 3, a paraphrase) and to
say the sources differ rather than hiding it.

**How to explain it in an interview.** "Grounding is the difference between an assistant
and a plausible liar. I put the retrieved clauses in the prompt as numbered sources with
their document, clause number, pages and authority rank, and the rank is load-bearing —
the FAQ paraphrases the gazette and sometimes simplifies it, so the prompt tells the
model to follow the gazette when they differ and to say that they do."

---

## 8. Citation validation

**What it is.** Not trusting the instruction. The model is told to end every sentence
with a marker like `[C1]`; **code then checks that it did.** Every marker must name a
source that was actually supplied, and every sentence must carry at least one.

**Where it lives here.** `citation_problems()` and `sentences_of()` in `app/answer.py`;
`agent_citation_problems()` in `app/agent.py` for the agent's version.

**Why we chose it this way.** Both checks are deliberately crude and syntactic, because
crude checks need no judgement and never disagree with themselves. They cannot tell
whether a cited clause really *supports* its sentence — that needs a verified question
set. They do catch the two failures that matter: a fabricated source number (a reader
seeing a bracketed number assumes someone checked it) and a confident sentence with
nothing behind it.

The agent's version adds the rule that matters most there: **a cited chunk id must have
come back from a search in this run.** The model knows what a chunk id looks like and
could invent a plausible one, so `AgentRun` records every id any search returned and
anything else is rejected.

**How to explain it in an interview.** "I validate the citations in code rather than
trusting the prompt. Every marker has to resolve to a source that was actually supplied
and every sentence has to carry one — and for the agent, a cited chunk id has to have
come back from a search in that same run, because the model can see the id format and
invent a plausible one. There's a test where the model obeys an injected 'reply APPROVED
with no citation' and the answer is rejected anyway, which is the point: the defence
doesn't depend on the model behaving."

---

## 9. Abstention

**What it is.** Declining to answer, deliberately, as a designed outcome rather than a
failure. ZoneWise has four reasons, and two of them never reach the model at all.

**Where it lives here.** `app/answer.py`: the reasons are `OUTSIDE_DELHI`,
`WEAK_RETRIEVAL`, `CITATION_CHECK_FAILED` and `MODEL_ABSTAINED`, decided in
`answer_point()`. The interface renders each one differently in
`web/src/components/AnswerPanel.jsx`.

**Why we chose it this way.** For planning law, a confident wrong answer is worse than
no answer: someone might build on it. The reasons are separate rather than one generic
"cannot answer" because they mean different things to the user — "that point is outside
Delhi" is actionable, "the documents do not cover this" is not. Two are checked before
any API call, which is also the cheap guard: a question about property tax is caught
before any money is spent. And **every abstention still returns the retrieved clauses**,
so a refusal is "I could not answer this, here is what I found" rather than a dead end.

**How to explain it in an interview.** "Abstention is a feature, not an error path.
There are four distinct reasons and two of them — point outside Delhi, and retrieval
too weak — are decided before any API call, so they cost nothing. Every refusal still
returns the clauses that were found, because 'I can't answer that, but here are the
three relevant clauses' is a useful product and a bare error isn't."

---

## 10. Tool calling

**What it is.** Giving the model a set of functions it can ask to run — each with a
name, a description and a JSON schema for its arguments — and letting it decide which
to call and in what order. The model does not run anything; it asks, your code runs the
function, and the result goes back as another turn.

**Where it lives here.** `app/agent.py`: `TOOLS` holds the three schemas
(`locate_place`, `get_zones`, `search_clauses`), `run_tool()` dispatches, and
`run_agent()` is the loop.

**Why we chose it this way.** Because the questions are not all the same shape. "What
can I build near Connaught Place?" needs all three tools; "Does MPD-2047 replace
MPD-2021?" needs only the search; a question that arrives with coordinates needs no
geocoding. A fixed pipeline would waste a call or fail on the cases it was not written
for. Two practical details: a tool that fails returns `{"error": ...}` to the model
rather than raising, so a geocoder timeout lets the agent say "I could not find that
place" instead of ending the request with a stack trace; and `max_rounds = 4` caps the
loop, with running out treated as an abstention.

**How to explain it in an interview.** "I gave the model three tools — geocode, zone
lookup, clause search — and let it sequence them, because the shape of the question
varies and a fixed pipeline would waste calls or break. The tool descriptions do real
work: `search_clauses` tells the model to pass coordinates whenever it has them, because
that's what turns on the location filtering."

---

## 11. recall@k

**What it is.** The headline retrieval metric. For each question: was an acceptable
chunk in the top k results? That is 1 or 0, and recall@k is the share that scored 1.
recall@5 of 0.74 means that for 74 questions in 100, at least one right clause was in
the top five.

**Where it lives here.** `recall()` in `eval/metrics.py`, reported at k = 1, 3 and 5 by
`eval/run_eval.py`.

**Why we chose it this way.** Because it matches what the pipeline does with the result:
the top k chunks go into the prompt, so if the right clause is in the top 5 the answer
can be grounded, and if it is not, nothing downstream can save it. recall@k measures the
exact thing that determines whether the rest of the system has a chance.

**How to explain it in an interview.** "recall@k is the right headline here because k is
also how many chunks go into the prompt — if the clause isn't in the top 5, no amount of
prompting fixes it. I report it at 1, 3 and 5 because the gap between them tells you
whether the retriever is finding the right thing or merely finding it eventually."

---

## 12. MRR (mean reciprocal rank)

**What it is.** The same question as recall, but position matters. A question whose
answer came first scores 1, second 0.5, fourth 0.25, missed 0; averaged over the
questions.

**Where it lives here.** `mrr()` and `QuestionScore.reciprocal_rank` in
`eval/metrics.py`.

**Why we chose it this way.** recall@5 cannot distinguish "found it first" from "found
it fifth", and those are very different experiences for a user who reads top-down. When
two configurations tie on recall@5, the one with the higher MRR is putting the answer
nearer the top. There is a test for exactly this case.

**How to explain it in an interview.** "MRR is recall with position baked in — it's the
tie-breaker when two configurations find the answer equally often but one finds it
sooner. I report both because they answer different questions: recall is 'can we
answer at all', MRR is 'how much reading does the user have to do'."

---

## 13. Bootstrap confidence intervals

**What it is.** A way of saying how much a measurement would move if you had happened to
ask a different set of questions. You resample your questions **with replacement** — draw
50 from your 50, allowing repeats — compute the average, and repeat 1,000 times. The
middle 95% of those averages is the confidence interval.

**Where it lives here.** `bootstrap_interval()` and `paired_difference_interval()` in
`eval/metrics.py`, with a fixed seed so the same data gives the same interval every run.

**Why we chose it this way.** With 50 questions, a recall of 0.74 could easily have been
0.62 or 0.86, and quoting 0.74 alone hides that. The bootstrap makes no assumption about
the shape of the distribution, which matters for a 0/1 metric over a small set where a
t-test's assumptions do not hold. The **paired** version is used for "does location
help?": per question, (did location find it?) minus (did hybrid find it?), then
bootstrapped. Pairing cancels the fact that some questions are simply harder, which is
the dominant noise when both configurations answer the same 25 questions.

In our dry run that distinction did real work: the recall@5 difference was +0.360 with
an interval of [+0.160, +0.560], which excludes 0, while the recall@1 difference was
+0.120 with [-0.080, +0.320], which includes 0 and therefore says nothing. One of those
is a claim; the other is not.

**How to explain it in an interview.** "With 50 questions a single average is nearly
meaningless, so every headline number carries a bootstrap interval, and the
location-versus-hybrid comparison is paired so it isn't swamped by some questions being
harder than others. It let me say honestly that the recall@5 improvement was outside the
noise while the recall@1 improvement wasn't — which is a more useful thing to report
than a bare number."

---

## 14. Rate limiting

**What it is.** Capping how often an endpoint can be called. Here: 10 requests a minute
per IP address, and 300 a day for the whole service, on the two endpoints that cost
money.

**Where it lives here.** The `RateLimiter` class in `app/api.py`, checked by
`_rate_limited()` on `/api/ask` and `/api/agent`.

**Why we chose it this way.** The per-IP limit handles the ordinary accident — a browser
tab in a retry loop, a double-clicked button — and is per address so one noisy client
cannot lock everyone else out. The daily cap is the one that matters: it is the single
thing standing between a bug and an unbounded API bill, which for a student project is
the risk actually worth engineering against. Both live in a dict in one process, which
is honest for what this is, and the limitation is written down: the counters reset when
the process restarts and a second worker would have its own copy.

**How to explain it in an interview.** "Two limits on the endpoints that cost money:
per-IP per-minute for accidents, and a global daily cap because that's what actually
protects the bill. It's an in-memory dict, which is right for one process on a laptop —
and I wrote down that it wouldn't survive a second worker, because the honest version of
a simple solution is knowing where it breaks."

---

## 15. The FakeLLM, and testing an LLM system

**What it is.** A stand-in client with the same interface as the real one, which returns
responses you scripted in the test. The code under test cannot tell the difference.

**Where it lives here.** `FakeLLM` in `app/llm.py`, chosen through `get_llm()`. Used by
`tests/test_answer.py`, `tests/test_agent.py` and `tests/test_api.py`.

**Why we chose it this way.** Most of what an "LLM system" does is not generation — it
is control flow *around* generation. Citation checking, the retry, four abstention
paths, the agent's tool loop and its round cap are all decisions about a response, and
every one can be tested exactly if the response is scripted. Those tests run in under
four seconds with no key and no network, which means they run on every change. Two
details earn their keep: `FakeLLM` records every call, so a test can assert on the
**prompt** as well as the answer; and it raises `ScriptExhausted` rather than inventing a
reply when called more times than scripted, because an unexpected extra call is a bug
and a silent default would hide it.

**How to explain it in an interview.** "Everything that touches the model goes through
one wrapper, so I could put a scripted fake behind it and test the whole pipeline —
citation validation, the retry, the abstention paths, the agent's tool loop — with no key
and no network. The fake records the prompts too, so I can assert that the system prompt
actually carries the rules. It also raises if it's called more times than scripted,
because an unexpected extra call is a bug, not something to paper over."

---

## Where to read more

- `DECISIONS.md` — all 62 decisions with the alternatives rejected. The "why" for
  everything above.
- `docs/ARCHITECTURE.md` — the same pipeline with diagrams and function names.
- `docs/DATA.md` — the documents, the cleaning rules, the chunk statistics, the layers.
- `eval/README.md` — how to verify an evaluation question, and what each metric means.
