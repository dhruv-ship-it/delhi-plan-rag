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

**What it is.** Not trusting the instruction. The model is told where its sentences
came from; **code then checks that it said so.** Every citation must name a source that
was actually supplied, and every sentence must carry at least one.

**Where it lives here.** `structural_problems()` in `app/answer.py` and
`agent_problems()` in `app/agent.py`. The prose versions — `citation_problems()` and
`sentences_of()` — are still there and now check the *rendered* markdown rather than the
model, which is a story of its own: see **note 21**, where the check stopped reading
prose because against a real model it was rejecting 18 first attempts in 22.

**Why we chose it this way.** Both checks are deliberately crude and syntactic, because
crude checks need no judgement and never disagree with themselves. They cannot tell
whether a cited clause really *supports* its sentence — that needs a verified question
set. They do catch the two failures that matter: a fabricated source number (a reader
seeing a bracketed number assumes someone checked it) and a confident sentence with
nothing behind it.

The agent's version adds the rule that matters most there: **a cited source must have
come back from a search in this run.** The model knows what a ZoneWise identifier looks
like and could invent a plausible one, so `AgentRun` records what every search returned
and anything else is rejected. What the agent cites is now a short label rather than a
whole chunk id, for reasons in **note 22** — the rule is identical, the string is
shorter.

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

## 16. Cross-encoder reranking, and why it is not the search

**What it is.** The two indexes in this project are **bi-encoders** in the loose sense:
the question and the chunk are turned into numbers *separately* and then compared. That
separation is what makes search possible at all — the 700 chunk vectors were computed
once, at index time, so a query costs one embedding and a dot product against a stored
matrix. It is also the limit: the chunk's vector was computed without any knowledge of
the question. "What is the **maximum** ground coverage?" and "What is the **minimum**
ground coverage?" have nearly the same embedding, and BM25 sees the same tokens in both.

A **cross-encoder** reads the query and the chunk together, as one concatenated input,
and returns a single relevance score. Because the two halves attend to each other, it
can tell those two questions apart. The price is that nothing can be precomputed: there
is no chunk vector to store, so scoring a corpus means one forward pass per chunk. That
is why a cross-encoder cannot *search* — it can only **rerank** a shortlist something
cheaper already found. The standard shape is therefore two stages: retrieve 20 with the
fast method, reorder those 20 with the accurate one.

**Where it lives here.** `app/rerank.py` — `available()`, `reranker()` and
`rerank_scores()`, wrapping fastembed's `TextCrossEncoder` with
`Xenova/ms-marco-MiniLM-L-6-v2`. It is applied by `apply_reranker()` in
`app/retrieval.py`, which rescores the top `settings.rerank_pool` (20) results after
fusion and returns the best k. The switch is `settings.use_reranker`
(`USE_RERANKER` in `.env`), and `settings.reranker_on` is the one the code reads —
it is `use_reranker and available()`, because `fastembed.rerank.cross_encoder` arrived
in a later fastembed than this project first pinned, so availability is **asked** rather
than assumed.

**Why we chose it this way: measured, and off.** On this laptop's CPU reranking costs
**2.4 seconds a query against 0.031 seconds without it** — about 77 times the cost of
the entire search that produced the shortlist, because 20 cross-encoder passes over
400-word chunks is simply more arithmetic than one query embedding and a BM25 scan. The
first guess was 0.4 s; measuring it changed the decision. On the drafted questions it
lifts recall@1 from 0.340 to 0.460, but those questions were written by Claude *from the
chunks*, and a cross-encoder is precisely the component that flatters itself on
questions phrased like their answers — so that number is not evidence. There is also a
visible counter-example in `reports/day2_queries_v3.md`: for "Can a fuel station be built
in Zone O?" the reranker demotes the correct clause from rank 1 to rank 2. So it stays
**off** (D-070), `eval/run_eval.py` scores `hybrid+location+rerank` as a fourth
configuration, and the decision waits on human-verified questions.

**How to explain it in an interview.** "My retrievers are bi-encoders — the chunk
vectors are precomputed, which is what makes search fast and also means the chunk was
embedded without knowing the question, so 'maximum FAR' and 'minimum FAR' look almost
identical. A cross-encoder reads query and chunk together so it can tell those apart,
but it can't be precomputed, so it only reranks a shortlist. I measured it at 2.4
seconds a query versus 0.031 — 77× the search it reranks — and left it off, because the
only recall gain I have is on questions I generated from my own chunks, which is exactly
the setup a cross-encoder looks best on."

---

## 17. Why a fused score cannot drive abstention, and what can

**What it is.** Abstention needs a number that answers "is this evidence any good?".
The tempting one is the score the retriever already produced. For reciprocal rank
fusion that is a mistake, and it is worth understanding exactly why: **RRF throws the
scores away and keeps only the positions** (see entry 4). A chunk's fused score is
`1/(k + rank)` summed over the lists it appears in. So a chunk that both indexes ranked
first scores `2/61 = 0.0328` — *whatever the question was*. Ask about property tax in
Mumbai, and if some chunk happens to come first in both lists, the pre-check sees the
same confident 0.0328 it sees for a question the gazette answers in full. The number is
a statement about the shape of the result list, not about relevance.

What **can** work is a score that is an absolute judgement about this query against this
chunk: a **dense cosine similarity** (how close are these two vectors, on a fixed 0-1
scale) or a **cross-encoder score** (a model's direct verdict, roughly -11 to +11). Both
mean something on their own, so a threshold can be set on them.

**Where it lives here.** `is_weak()` in `app/answer.py` is the pre-check — step 3 of the
five-step answer path, before any API call. It reads one raw score through
`signal_value()` in `app/retrieval.py`, so the pre-check, the API's score breakdown and
the evaluation's percentile tables all read the same field by the same name. The choice
is `settings.abstain_signal` (`dense_cosine` or `rerank_score`) and the cut-off is
`settings.abstain_threshold`. `Settings.abstention_signal` falls back to
`dense_cosine` when `rerank_score` is asked for with the reranker off, because that
field would be `None` on every result. `scripts/tune_abstention.py` sweeps the
thresholds and prints the percentile table. Every `Result` carries its raw
`dense_cosine`, `bm25_score` and `rerank_score` alongside the fused score precisely so
this is possible (D-071).

**Why we chose it this way, and the honest finding.** Measured over the 60 drafted
questions, the answerable and should-abstain groups overlap almost completely on *every*
signal:

| signal | answerable p5 / p50 / p95 | should-abstain p5 / p50 / p95 |
| --- | --- | --- |
| `fused_score` | 0.0301 / 0.0328 / 0.0488 | 0.0285 / 0.0310 / 0.0488 |
| `dense_cosine` | 0.6371 / 0.7349 / 0.8303 | 0.5834 / 0.6765 / 0.7655 |
| `rerank_score` | -8.479 / 1.344 / 8.022 | -9.680 / -4.451 / 4.172 |

So the configured value — `ABSTAIN_SIGNAL=dense_cosine`,
`ABSTAIN_THRESHOLD=0.5804` — is deliberately set a hair below the lowest top-1 cosine
any answerable draft produced. It refuses none of the 50 answerable questions and
catches none of the 10 should-abstain ones, and it is labelled **provisional**
everywhere it appears. That is the most conservative honest choice: the alternative was
a threshold fitted to questions Claude wrote about chunks Claude could see.

**The finding is bigger than the number: no single retrieval score separates those two
groups cleanly, so the pre-check is a cost guard, not a correctness guard.** What
actually stands between an unanswerable question and a confident wrong answer is rule 3
of the system prompt and the citation check (entries 7, 8, 9). A bug found while
building the sweep makes the same point twice: the first `provisional()` clamped its
result at zero, which is harmless for a cosine and turned "refuse nothing" into a
threshold of 0.0 on the cross-encoder scale — a value that would have refused 40% of the
answerable questions.

**How to explain it in an interview.** "I tried to use the fused retrieval score as an
abstention signal and it can't work, which took measuring to see: an RRF score only
encodes rank position, so the top chunk for a question about Mumbai property tax scores
exactly what the top chunk for a real question scores — 2/61. I switched the pre-check to
a raw dense cosine, which is an absolute judgement about this query and this chunk. The
real result was negative though: the answerable and should-abstain distributions overlap
on every signal I had, so I set the most conservative threshold, labelled it provisional,
and was explicit that the pre-check is a cost guard and the citation check is the
correctness guard."

---

## 18. Fuzzy matching and gazetteers

**What it is.** A **gazetteer** is a local list of place names with their coordinates.
Instead of asking a geocoding service what "Dwarka Sector 21 metro station" means, you
hold the ~290 Delhi Metro station names yourself and match against them. The matching
cannot be exact, because people type "Dwarka Sec 21", "dwarka sector-21" or "near
Dwarka Sector 21 metro" — so it is **fuzzy**: score how similar two strings are and
accept the best one if it is similar enough. `difflib.SequenceMatcher` scores on the
longest matching subsequences, returning a ratio from 0 to 1; the cut-off decides how
much mangling you forgive. Too high and real variants miss; too low and "Dwarka Sector
21" quietly matches "Dwarka Sector 12", which is a different place and a wrong answer
rather than a missing one.

**Where it lives here.** `app/geocode.py`. `normalise()` lower-cases and strips the
noise words ("near", "metro station", "metro", "station") and punctuation — and strips
station words **from the end only**, because the first version turned "Station Road"
into "road". `gazetteer()` loads `data/gazetteer/metro_stations.json`, keyed by every
normalised name a station has, and returns `{}` when the file is absent.
`gazetteer_match()` does the matching: an exact key hit wins outright, otherwise
`difflib.get_close_matches(..., n=3, cutoff=settings.gazetteer_cutoff)` with the cut-off
at **0.85**, and the match is accepted **only when the best candidate is uniquely best**
— if a second name ties on ratio, it returns `None` and lets Nominatim decide.
`scripts/build_gazetteer.py` builds the file from one OpenStreetMap Overpass query.
It is step 2 of the four in `locate_place()`, tried before Nominatim.

**Why we chose it this way.** Night 2 found that Nominatim returns **nothing** for
"Dwarka Sector 21 metro station" with `bounded=1` and `limit=1` (D-049) — close to the
phrase the agent's own example suggests typing. One geocoder's indexing of one naming
convention should not be the only thing between a user and an answer. A metro station is
the most likely way a Delhi resident describes where they are, there are only a few
hundred, so holding them locally turns the commonest case into a string match with **no
network call at all**: free, instant, and not rate-limited. The tie rule is the
conservative half of the design — a unique-best requirement means an ambiguous query
falls through to a real geocoder instead of guessing between two sector numbers.

**It is built, and it works.** The Overpass request that failed at the TCP level from
two earlier sandboxes succeeded on 19 October: **278 stations**. Verified with no network
at all, `"Dwarka Sector 21 metro station"` resolves from the gazetteer to the identical
coordinate Nominatim gave, and `"dwarka sec 21"` — a contraction no geocoder indexed —
resolves too, which is the fuzzy cutoff doing the job it was chosen for (D-081).

**An absent gazetteer stays a supported state, and that is now tested against a real
absent file** rather than a stubbed empty dict: `gazetteer()` returns `{}`,
`gazetteer_match()` returns `None` immediately, and `locate_place()` falls through to
Nominatim. A corrupt half-written file behaves the same way. The suite was run with the
file hidden and with it present — 383 both times — because the data is gitignored and a
fresh clone has none of it.

**The limitation found by building it** is worth more than the feature: `"Hauz Khas"`
**misses**, because OSM names interchange stations per line, so the list holds
`Hauz Khas (Magenta Line)` and `Hauz Khas (Yellow Line)` and no plain `Hauz Khas` — which
score 0.58 and 0.60 against `hauz khas`, well under the cutoff. It falls through to
Nominatim and the user still gets the right point. Lowering the cutoff to admit it would
also admit "Dwarka Sector 21" matching "Dwarka Sector 12", and stripping the suffix would
make the loader silently pick one of two platforms 150 m apart. So it is recorded and not
fixed (D-081): **a fuzzy matcher's cutoff is a trade between a missed match and a wrong
one, and those two failures are not equally bad.**

**How to explain it in an interview.** "My geocoder missed the single most likely phrasing
a user would type — a Delhi Metro station name — so I added a local gazetteer of the ~290
stations and fuzzy-match against it with difflib at a 0.85 cut-off, which costs no network
call. The part I'd point at is the tie rule: I only accept a fuzzy match when it is
*uniquely* best, because 'Dwarka Sector 21' matching 'Dwarka Sector 12' is a confidently
wrong coordinate, and a wrong answer is worse than falling through to the real geocoder.
The whole thing is also optional — if the file
isn't there the code degrades to Nominatim, and I proved that by hiding the file and
re-running the suite rather than by reading the code. Building it also found the real
limitation: OpenStreetMap names interchanges per line, so 'Hauz Khas' doesn't match
'Hauz Khas (Yellow Line)' at any cutoff I'd be willing to use, and I left that as a
miss rather than guessing a platform."

---

## 19. Docker multi-stage builds

**What it is.** A Dockerfile can contain several `FROM` lines. Each one starts a new
**stage** with its own base image, and a later stage can copy files out of an earlier one
with `COPY --from=`. Everything else in that earlier stage — its compilers, its
`node_modules`, its source — is discarded. The reason to want this is that the tools
needed to *build* software are almost never the tools needed to *run* it. The classic
case is exactly ours: building the frontend needs Node and 200 MB of npm packages;
serving it needs a directory of static files.

The second idea in the same file is **layer caching**. Each instruction is a layer, and
Docker reuses a layer when neither the instruction nor the files it copied have changed —
so the *order* of instructions decides how much a rebuild costs. Copying dependency
manifests and installing before copying source means editing a Python file does not
re-resolve the dependency tree.

**Where it lives here.** The `Dockerfile` at the repo root, two stages:

- **`FROM node:20-slim AS web`** — copies `web/package.json` and the lockfile, runs
  `npm install`, *then* copies the source and runs `npm run build`.
- **`FROM python:3.12-slim AS server`** — the image that ships. It brings `uv` in with
  `COPY --from=ghcr.io/astral-sh/uv:0.5.11`, so the version is pinned by a tag and
  nothing needs a compiler; runs `uv sync --frozen --no-install-project --no-dev` before
  copying `app/`; and takes the built frontend with
  `COPY --from=web /build/dist ./web/dist`. Node never exists in the final image.

Three other decisions in that file are worth knowing (D-079). It **bakes the built data
in** — the Chroma store, the BM25 pickle, the cached model weights, the layers — rather
than building at startup, because embedding 700 chunks takes about 160 seconds on a CPU
and a self-building container would pay that on every restart and every replica; the
cost is that `docker build` must run on a machine where the pipeline has already run,
which `docs/DEPLOY.md` says first and in bold. It runs as a **non-root** user (uid
10001) and creates `data/logs` with the right owner first, because `app/api.py` logs
best-effort and a container that could not write its log would swallow the failure
silently. And its `HEALTHCHECK` asks for `status == "ok"` from `/api/health` rather than
a 200, because a container with no index serves 503s from a perfectly healthy process.

**Why we chose it this way.** One image, one process, no build step at run time — the
smallest thing that can be deployed and the smallest thing that can go wrong at 3am. The
build itself **could not be run** in the sessions that wrote it: `docker pull` returns
zero bytes from the sandbox. So it was verified the other way — all sixteen `COPY` paths
exist, no `.dockerignore` pattern excludes anything copied, `uv sync --frozen` is
consistent, and the exact `CMD` was run outside a container and smoke-tested against
`/api/health`, `/api/zones` and `/api/layers`. What remains untested is the layer
caching, the two `uv sync` steps and the non-root log directory.

**How to explain it in an interview.** "Two stages: Node builds the frontend, the Python
image copies just the `dist` out of it, so Node and `node_modules` never ship. I ordered
the instructions so dependencies install before source gets copied — editing a Python
file shouldn't re-resolve the lockfile. The decision I'd actually defend is baking the
search index into the image instead of building it at startup: embedding the corpus is
~160 seconds, and paying that on every restart and every replica to avoid a build-time
prerequisite is the wrong trade."

---

## 20. Continuous integration, and marking the tests that need data

**What it is.** CI runs the checks automatically on a fresh machine on every push. The
value is not that it runs the tests — you can do that locally — it is that it runs them
**on a clean clone**, which catches the whole class of bug where something passes only
because of a file sitting on your laptop.

That is also the problem it creates here. Three directories this project needs are
deliberately not committed (D-014): `data/processed`, `data/index` and
`data/layers/dda` — the PDFs are 109 MB, the indexes are generated, and the DDA states
no licence for its layers. A CI runner has none of them, so the tests that read them
cannot pass there. The fix is a **pytest marker**: a label on a test that lets you
select or deselect it by name, so one suite can be run two ways instead of maintaining
two suites.

**Where it lives here.** `.github/workflows/ci.yml`, two jobs: `python` (uv,
`uv sync --frozen`, `uv run pytest -m "not needs_data" -q`) and `web` (`npm ci`,
`npm run build`, then an assertion that `dist/index.html` and a JS bundle exist). The
marker is declared in `pyproject.toml` under `[tool.pytest.ini_options]`, applied
module-wide in `tests/test_api.py` with `pytestmark = pytest.mark.needs_data` and on one
case in `tests/test_web_build.py`. **31 tests are marked; 348 of the 379 run with no data
at all.**

Two details carry most of the value. `concurrency` with `cancel-in-progress` means a
second push to a branch cancels the first run, because on a branch being iterated the
only result anyone reads is the latest. And the second step of the Python job asserts
that **the deselected set is non-empty** — if a `needs_data` marker is ever deleted by
accident, the main suite would silently start trying to read data that is not there, so
the marker going missing is a CI failure rather than a surprise.

**Why we chose it this way, and how the set was proved.** The membership of
`needs_data` was **not reasoned about** — it was established by experiment. `data/index`,
`data/processed` and `data/layers/dda` were moved aside, the suite was re-run — **348
passed, 31 deselected, nothing failed** — and then restored, 379 pass (D-078). The first
attempt at that found a case in `test_web_build.py` that no reading of test names would
have caught: it mounts the frontend and asserts `status == "ok"`, which is an assertion
about the index, not the bundle. `npm ci` rather than `npm install` for the same family
of reason: `ci` installs exactly what the committed lockfile says and fails if it
disagrees with `package.json`, where `install` would quietly resolve something newer and
leave CI testing a dependency tree nobody has run locally.

**How to explain it in an interview.** "My indexes and source PDFs aren't committed, so a
CI runner can't run every test. I marked the 31 that need built data with a pytest marker
and CI runs `-m 'not needs_data'` — 348 tests on a clean clone. Two things I'd point at:
I found the membership of that set by actually hiding the data directories and re-running,
which caught a test whose name gave no hint it depended on the index; and CI asserts the
deselected set is non-empty, so if someone deletes the marker it fails loudly instead of
quietly trying to read data that isn't there."

---

## 21. Structured output, and why free-text citation markers lose

**What it is.** Two ways of getting a model to say which source each sentence came from.

The **free-text** way is a convention: "end every sentence with a marker like `[C1]`".
Code then splits the answer into sentences and checks each one has a marker. The
**structured** way is a data shape: the model returns

```json
{"abstain": null, "sentences": [{"text": "...", "citations": ["C1", "C3"]}]}
```

so a sentence and its sources are **one record**. Validation stops being "did the model
follow the convention" and becomes "is this object the right shape".

**Where it lives here.** `app/answer.py`: `JSON_CONTRACT` in the prompt,
`parse_answer_object()`, `structural_problems()` and `render_markdown()`. The published
output is unchanged — `answer_markdown` is rendered from the sentences with the same
`[C#]` markers — so the API, the frontend and the citations table never knew.

**Why we chose it this way, and this is the interesting part: because the free-text
version was measured and it was losing.** Against a real model, **18 of the 22 map-mode
answers that reached the citation check failed on the first attempt** — a first-attempt
pass rate of 18% (D-087). Almost all were rescued by the single retry, so the user saw
good answers; the cost was that **two calls, not one, was the normal path**.

The reason is worth internalising, because it generalises past citations. **A convention
about formatting competes with the model's writing.** A marker belongs at the end of a
sentence, but what counts as a sentence is a judgement: a thought spanning two
sentences, a bullet list, a parenthetical "(e.g. a 4,000 sqm plot)", a heading. Our
splitter had a hand-tuned regular expression, a list-prefix stripper and a
minimum-letters rule to stop punctuation debris reading as an uncited sentence — three
patches, all of them guessing at where a sentence ends. A JSON array has no splitter to
disagree with, because the author decided the boundaries.

The trade-offs are real and worth naming. Structured output costs tokens (field names
are tokens), it needs defensive parsing anyway — JSON mode is **a request, not a
contract**: Anthropic's Messages API has no `response_format` at all, Groq's is
per-model, and a model that ignores it wraps its object in a code fence — and it moves
the formatting decision from the model to your renderer, which is more code you own.
What it buys is that the thing you check is the thing the model produced, rather than a
reconstruction of it.

**What it does not buy, which is the honest half.** Structure proves a citation is
*present* and *real*. It cannot prove the clause *says* the sentence. The clearest
evidence here is that our own prompt was asking for the defect: **rule 6 tells the model
to say official DDA documents should be checked — a sentence no clause supports — while
rule 2 demands a citation on every sentence**, so 7 of 17 real answers carry that line
with a marker bolted onto it. No schema catches that. Only reading the answers does.

**How to explain it in an interview.** "I had the model end every sentence with `[C1]`
and validated it in code, and against a real model 18 of 22 first attempts failed — not
because the citations were wrong, but because my sentence splitter and the model's
writing disagreed about where sentences end. So I moved to a JSON contract where each
sentence carries its own citations array, and validation became structural. I still
render the same markdown, so nothing downstream changed. The thing I'd flag is what it
didn't fix: structure proves a citation exists, not that the clause supports the
sentence — and I found my own prompt asking for a sentence that no clause could
support, which no schema would ever catch."

---

## 22. Why short labels help a model cite

**What it is.** Giving the model a short name for each retrieved source instead of the
real identifier. Map mode numbers its sources `C1` to `C6`. The agent chooses what to
retrieve, so it gets labels `S1`, `S2`, … issued as searches return clauses, numbered
across the whole run, and a clause it has seen before keeps the label it was first
given. The label-to-clause map lives on the server.

**Where it lives here.** `AgentRun.label_for()` and `run_search_clauses()` in
`app/agent.py`; `citations_from()` in `app/answer.py` resolves a label back to a chunk.

**Why we chose it this way.** The agent used to cite the whole chunk id —
`MPD47_GAZETTE_EN:4.2.3@p753:0` — because that is the only globally unique name a clause
has (clause numbers repeat across this corpus, so `4.2.3` is ambiguous). Measured
against a real model, that was the single biggest difference between the two answering
paths: **5 of 11 agent cases failed the citation check twice against 5 of 26 in map
mode**. The cleanest comparison is one question asked both ways — "How much of my plot
can I build on near Rajiv Chowk metro station?" failed twice as an agent run, while the
same question at the same point in map mode, where the marker is `[C3]`, answered after
one retry (D-085).

**Why it is harder, mechanically.** A model does not copy a string, it generates it
token by token, and a thirty-character identifier made of a document prefix, a dotted
clause number, a page anchor and an ordinal is a long way to go without a slip — in a
format where one wrong character makes the citation resolve to nothing. `S1` is one
token. Shorter names are also easier to *choose* between while writing, which is why the
retry prompt lists each label with its clause number and document.

**The part that matters more than the win.** Nothing was relaxed to make this easier.
The guarantee is still that a cited source must have come back from a search *in this
run*, and `S9` after one search of six clauses is rejected exactly as an invented chunk
id was. The same fact is checked through a shorter name. Two supporting choices follow
from that: labels are numbered **across the run** and not per call, because `S1` meaning
a different clause after the second search would be worse than a long identifier; and
the chunk id is **not shown to the model at all**, because offering two names for one
thing invites using the wrong one.

**How to explain it in an interview.** "My agent had to cite a thirty-character chunk id
exactly as retrieved, and it failed the citation check twice on 5 of 11 cases against 5
of 26 in map mode, where the marker is `[C3]`. Same validation rule, same model — the
difference was the length of the string. So search results now get short labels, `S1`,
`S2`, numbered across the run, and the server keeps the map back to the real ids. The
part I'd want to be asked about is that I didn't weaken the check to get that: a label
the run never issued is still rejected, so an invented citation still can't resolve. I
just stopped asking the model to do something it is bad at for no benefit."

---

## Where to read more

- `DECISIONS.md` — all 79 decisions with the alternatives rejected. The "why" for
  everything above.
- `docs/ARCHITECTURE.md` — the same pipeline with diagrams and function names.
- `docs/DATA.md` — the documents, the cleaning rules, the chunk statistics, the layers.
- `eval/README.md` — how to verify an evaluation question, and what each metric means.
