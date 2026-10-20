# Why clause 11.1.1 did not come back for the fuel-station question at P_ZONEO

**20 October 2026. 700 chunks, reranker off. The diagnosis in §§ 1-4 is unchanged.
§ 5 was a proposal when this file was first written; it was applied later the same day
as D-086, and § 5 now records what it did and what it cost.**

Regenerate every number here with:

```powershell
uv run python scripts\diagnose_fuel_station.py
```

which writes the full tables to
[diagnosis_fuel_station_tables.md](diagnosis_fuel_station_tables.md). The decisive ones
are reproduced below.

---

## 1. The finding, restated

At **P_ZONEO** (28.672913, 77.243545 — the Yamuna floodplain, planning zone O), the
question

> Can a fuel station be built here?

does not return `MPD47_GAZETTE_EN:11.1.1@p854:0`, the chunk that contains:

> *Fuel stations may be permitted in all Use Zones except Recreational (Regional Park,
> District Park, etc.) and Zone O.*

That is the clause that answers the question, and it answers it with a **no**. Asked
with no point at all, hybrid search puts it at rank 3 (with another chunk of 11.1.1, the
fuel-station norms on p855, at rank 1). Asked at the point, it fell to **rank 14** —
eight ranks below what a user ever sees. `docs/DEMO.md` cut the question for this reason
and `docs/PROJECT_STATUS.md` carried it as limitation 4. **Both have since been updated:
the clause is now rank 1 at the point** (§ 5), and everything in §§ 1-4 below describes
the behaviour as it was when the fault was found.

**It is the location path, and specifically it is step 2 of three: query expansion.**

---

## 2. Where the clause lands, measured

`11.1.1@p854` only. `dense` and `BM25` are its rank inside each index's own pool after
filtering; the raw-pool note says where it sat before filtering, which is how
"exclusion dropped it" is told apart from "the query stopped finding it".

| configuration | query actually searched | fused rank | dense | BM25 |
| --- | --- | --- | --- | --- |
| no point at all | `Can a fuel station be built here?` | **3** | 10 | 2 |
| the point, everything on (**as it shipped before D-086**) | `…built here? Zone O Yamuna floodplain` | **14** | — (absent from a 60-deep raw pool) | 2 |
| the point, no exclusion | `…built here? Zone O Yamuna floodplain` | **14** | — (absent) | 2 |
| the point, no boost | `…built here? Zone O Yamuna floodplain` | **15** | — (absent) | 2 |
| the point, **no query expansion** (**what ships now**, § 5) | `Can a fuel station be built here?` | **1** | 8 | 2 |
| the point, all three off | `Can a fuel station be built here?` | **3** | 10 | 2 |

The explicit wording behaves the same way: *"Can a fuel station be built in Zone O?"*
goes rank 2 with no point, **rank 11** as shipped, **rank 1** with expansion off.

Four things fall straight out of that table.

**Exclusion is innocent.** Turning it off changes the rank by nothing at all — 14 either
way. It was never a plausible suspect once the chunk's tags are read: `11.1.1@p854` has
`zone_primary: ''` and `zone_mentions: ['zone_o', 'ridge']`, and `should_exclude` acts
only on `zone_primary`. The docstring of that function names this exact clause as the
reason it works that way (D-023). It does what it says.

**The boost is innocent, and is in fact helping.** The clause mentions `zone_o`, so
`matches_point` is true and its fused score is multiplied by 1.5. Turning the boost off
makes things *worse* (14 → 15). The clearest evidence is the fifth row: with expansion
off, the boost lifts the clause from rank 3 (where no point at all puts it) to **rank
1**. The location path, minus one step, is better than no location path.

**BM25 never loses it.** Rank 2 in every single configuration. The keyword index is
indifferent to the expansion, because adding four tokens to a bag of tokens does not
move the tokens that were already there: "fuel" and "station" still dominate.

**The dense index loses it completely.** This is the whole defect. With the plain
question the chunk is at dense rank 10; with the expanded query it is **not in the
60-deep pool at all**.

---

## 3. The mechanism, and it is not what it looks like

The obvious story would be "the expansion made the clause look less like the query". The
measurement says the opposite. Probing the dense index over all 700 chunks:

| query sent to the embedder | cosine of `11.1.1@p854` | its dense rank |
| --- | --- | --- |
| `Can a fuel station be built here?` | 0.6143 | **11** of 700 |
| `Can a fuel station be built here? Zone O Yamuna floodplain` | **0.6519** | **173** of 700 |
| `Can a fuel station be built in Zone O?` | 0.6453 | 5 of 700 |
| `Can a fuel station be built in Zone O? Zone O Yamuna floodplain` | **0.6631** | 134 of 700 |

**The clause's similarity went up and its rank collapsed.** Appending
`Zone O Yamuna floodplain` made the clause a slightly *better* match — it does mention
Zone O — and made about 160 other chunks a *much* better one. The top of the dense list
stops being about fuel stations and becomes about the floodplain: `3.1.2@p681`
(Green-Blue Infrastructure) takes rank 1, followed by FAQ and NGT-report chunks.

So the expansion does not damage the clause. It changes the question. A dense query is a
single point in embedding space, and appending a topic **moves** that point; a BM25 query
is a set of tokens, and appending a topic **adds** to it. Half of a seven-word question
plus a four-word topic is a query about the topic.

And then fusion finishes the job. With only one index finding it, the clause scores
`1/(60+2) = 0.01613`, times 1.5 for the boost = **0.0242**. A floodplain chunk that both
indexes rank highly scores about `0.0328 × 1.5 = 0.0492`. RRF is working exactly as
designed — "agreement should count for more than one index's confidence" (D-028) — but
one of the two voters has been handed a different question.

*A note on precision: Chroma's HNSW index is approximate, so a deep dense rank wobbles
between runs — the no-point rank of this chunk came back as 10 and as 11 on two
consecutive runs. Nothing in the diagnosis turns on one place; the effect being measured
is a move of about 160 ranks.*

---

## 4. Why this is a Zone O problem and not a bug in expansion

The expansion terms are not all the same kind of thing:

| topic | terms appended | has its own policy section? |
| --- | --- | --- |
| `tod` | transit oriented development TOD zone | **yes**, chapter 4.2 |
| `hdc` | high density corridor HDC UER-II | **yes**, chapter 4.3 |
| `land_pooling` | land pooling | **yes**, chapter 4.1 |
| `lda` | low density area LDA farmhouse | **yes**, chapter 4.4 |
| `zone_o` | Zone O Yamuna floodplain | **no** |
| `ridge` | Ridge regional park Aravalli forest | **no** |

For the first four, the appended words are the **heading vocabulary of a chapter**, so
moving the dense query towards them moves it towards the right chapter — which is
precisely the effect `docs/DEMO.md` beats 1, 2 and 4 demonstrate, and precisely what
`reports/location_compare_v3.md` comparison E credits.

For `zone_o` and `ridge` there is no chapter to move towards. These are the two topics
that **may not exclude**, because MPD-2047 gives them no policy section (D-023, D-069,
limitation 3 of `docs/PROJECT_STATUS.md`). So their terms name a *place* instead, and the
only text in the corpus that is about that place is chapter 3.1 Environment, the High
Court order and the NGT report. Those are the right answer to *"is construction allowed
here?"* — beat 3 of the demo — and the wrong answer to any question about a different
subject asked in the same place.

**So the defect has a one-line statement, and it generalises past fuel stations:** for a
zone with no policy section, query expansion supplies a new *subject* rather than a
*qualifier*, and every question asked in Zone O or on the Ridge is partly replaced by
"tell me about the Yamuna floodplain". The same failure should be expected for "how tall
can I build here?", "what is the parking norm here?" or any other subject at those two
points. The two zones already known to be unable to exclude turn out to be the two that
cannot safely expand either — which makes it the same asymmetry showing up a second
time, in a second step.

---

## 5. The fix, applied (D-086)

**Query expansion now runs only for topics that have a policy section of their own** —
the same four that are already allowed to exclude. `zone_o` and `ridge` keep the other
two steps: they are still boosted, and exclusion is unaffected.

In `app/location.py` that is one tuple and one filter:

```python
EXPANDS_QUERY: tuple[str, ...] = ("tod", "hdc", "land_pooling", "lda")
```

and `expand_query` skipping every topic outside it. Measured, as shipped:

| | fuel station, "here" | fuel station, "in Zone O" |
| --- | --- | --- |
| before D-086 | rank 14 | rank 11 |
| now | **rank 1** | **rank 1** |

and `11.1.1@p855`, the fuel-station norms, follows at rank 2 in both — so the user gets
the permission rule *and* the controls.

**What it did to the five published demo beats.** Three come back **bit-identical**, not
similar — the three whose topics keep their expansion — and the two that change are
exactly the two the fix is about:

| beat | top 3, before | top 3, now | |
| --- | --- | --- | --- |
| 1 P_TOD | `4.2.1`, `4.2.3@p751`, `4.2.3@p753` | identical | **unchanged** |
| 2 P_HDC | `4.3@p757`, `Q1@p15`, `1.7.1@p666` | identical | **unchanged** |
| 4 P_LDA | `4.4.3`, `Q3@p18`, `4.4@p764` | identical | **unchanged** |
| 3 P_ZONEO | `3.1.2@p681`, `2:0`, `3@p25:1` | `2:0`, `3.1.2@p681`, `9.2` | changed |
| 5 P_RIDGE | `10.1@p842`, `3.1.2@p681`, `3.1.2@p683` | `10.1@p843`, `3.1.2@p681`, `9.2` | changed |

`docs/DEMO.md` has been re-run and updated for those two beats, and the fuel-station
question has moved out of its "did not make it" list.

### What it cost, which is the part worth reading

The fix is **not free**, and the same mechanism that explains the win explains the loss.
Appending `Zone O Yamuna floodplain` supplies a new *subject*; that is a defect when the
question's subject is something else (a fuel station) and an *advantage* when the
question's subject **is** the place. Both kinds of question exist at these two points,
and the second kind now does worse. Measured over a 200-deep list, with
`reports/location_compare_v4.md` carrying the generated tables:

| point | question | clause | before | now |
| --- | --- | --- | --- | --- |
| P_ZONEO | Can a fuel station be built here? | `11.1.1@p854` | 14 | **1** |
| P_ZONEO | Is construction allowed here? | `DHC_YAMUNA_20240708:2` | 2 | **1** |
| P_ZONEO | Is construction allowed here? | `3.1.2@p681` | 1 | 2 |
| P_ZONEO | Is construction allowed here? | `NGT…:3@p25:1` | 3 | **>200** |
| P_ZONEO | Can I construct a building here? | `3.1.2@p681` | 1 | **>200** |
| P_ZONEO | Can I construct a building here? | `DHC_YAMUNA_20240708:2` | 2 | 9 |
| P_ZONEO | What are the rules for the active floodplain? | `3.1.2@p681` | 1 | 1 |
| P_RIDGE | Is construction allowed here? | `10.1@p843` | 8 | **1** |
| P_RIDGE | Can I build a house here? | `10.1@p842` | 1 | **>200** |

Read the two P_ZONEO construction rows together, because they are the uncomfortable
pair. *"Is construction allowed here?"* survives — it keeps the court order and the
no-construction clause at ranks 1 and 2, and loses only the NGT report — while *"Can I
construct a building here?"*, which is the same question in different words, loses all
three and comes back with chapter 13 utilities and a slum FAQ. The top 5 at P_RIDGE for
*"Can I build a house here?"* is now Group Housing norms rather than the Regional Park
definition. Of the three, only *"Is construction allowed here?"* was asked live in v1.

**Why it still ships.** The questions it helps are the ones the product is for: a user
clicks a point and asks about a *subject* — a fuel station, a height, a parking norm —
and expects the point to qualify the question rather than replace it. A user whose
question is already about the floodplain has typed the floodplain words themselves, and
that case still works: *"What are the rules for the active floodplain?"* keeps `3.1.2` at
rank 1 either way. It is a trade of the narrower case for the broader one, made
deliberately and on a lead decision, and it is recorded here so that the next person
reading these two beats knows what was given up rather than discovering it.

### Three alternatives, measured and rejected

| alternative | fuel station | what it costs |
| --- | --- | --- |
| **Fuse a third list**: add `dense(original query)` to the RRF alongside `dense(expanded)` and `bm25(expanded)`, **at every point** | rank 1 | Breaks beats 2 and 4: the un-expanded dense list votes for the FAQ's conversational phrasing, so `Q5@p15` and `Q18@p16` displace the gazette's `4.3@p757`, putting **authority rank 3 above authority rank 1**. Beat 1 loses `4.2.1` from the top 3. |
| **The same at half weight** (`0.5/(k+rank)`) | rank 8 — still invisible | The worst of both: the FAQ promotion on beats 2 and 4 happens anyway and the fuel-station clause does not reach the top 6. |
| **Expand the keyword query only**, leaving the dense query plain | rank 1 | Same FAQ-over-gazette problem on beats 2 and 4, and it throws away the dense half of the location effect at *every* point, not just the two that need it. |

The common failure in all three is worth stating, because it is the reason the scoped fix
is the right shape: any change that re-admits the **un-expanded** dense ranking at every
point re-admits plain semantic search, and plain semantic search over this corpus likes
the FAQ's short conversational chunks. The expansion is what keeps the gazette on top.
It should therefore be removed only where it has nothing to aim at, which is the two
topics with no policy section — and not weakened everywhere.

A fourth option, **turning expansion off entirely**, is the same measurement as row 6 of
§ 2 and is rejected for the same reason: it would discard the effect that beats 1, 2 and
4 exist to show.

### A fifth option, measured after the fix and not applied

The cost table above prompted one more measurement, recorded because it is the obvious
next move rather than because it is being made. **Fuse four lists instead of two, scoped
to `zone_o` and `ridge` only** — `dense(plain)`, `bm25(plain)`, `dense(expanded)`,
`bm25(expanded)`. Scoping is what makes it different from the rejected row above: the
other four topics never reach this code path, so beats 1, 2 and 4 cannot move, by
construction and for the same reason the shipped fix cannot move them.

| point | question | clause | before | shipped | 4-list |
| --- | --- | --- | --- | --- | --- |
| P_ZONEO | fuel station, "here" | `11.1.1@p854` | 14 | **1** | **1** |
| P_ZONEO | Can I construct a building here? | `3.1.2@p681` | 1 | >200 | **2** |
| P_ZONEO | Can I construct a building here? | `DHC…:2` | 2 | 9 | **1** |
| P_ZONEO | Is construction allowed here? | `DHC…:2` | 2 | **1** | **1** |
| P_RIDGE | Can I build a house here? | `10.1@p842` | 1 | >200 | **1** |
| P_RIDGE | Is construction allowed here? | `3.1.2@p681` | 2 | 2 | **1** |

On these six questions it is better than both the old behaviour and the shipped fix: it
keeps every win and gives back every loss. It is **not applied** for the three reasons
D-083 gave and that have not changed — there is still no verified question set, six
questions at two points is a finding and not evidence, and it is a second embedding call
and a second BM25 pass for those points. It belongs in `eval/run_eval.py` as a
configuration to score once `eval/questions_verified.jsonl` exists, which is where the
reranker and the abstention threshold are already waiting.

---

## 6. What was waiting on this, and what still is

When this file was first written, § 6 listed three things that had to happen before the
fix was applied. Two are now done and one is unchanged:

1. **~~There is still no verified question set.~~** Still true, and it is still the
   reason every *other* retrieval change waits (D-070 for the reranker, D-071 for the
   threshold, and the 4-list option above). This one was applied anyway, on a lead
   decision, because the failure it fixes is a mechanism that generalises past the one
   question rather than a score that might be noise.
2. **~~It changes two published demo beats.~~** Done: `docs/DEMO.md` beats 3 and 5 have
   been re-run and rewritten, including the cosine figures, and the beat-3 narrative now
   leads with the High Court order.
3. **The `ridge` half is still untested against a question that needs it.** The fix is
   justified by a mechanism that applies to both topics, but it is *measured* on
   `zone_o`. A Ridge question whose subject is not the Ridge — "what is the parking norm
   here?" at P_RIDGE — is the matching test, and there is still no draft or verified
   question of that shape. The P_RIDGE rows of the cost table are the other half of the
   same gap: they show the fix hurting the Ridge questions that *are* about the Ridge,
   with nothing yet showing it helping one that is not.

`docs/PROJECT_STATUS.md` limitation 4 is now a record of a fix rather than of a miss.
