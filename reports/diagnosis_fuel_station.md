# Why clause 11.1.1 does not come back for the fuel-station question at P_ZONEO

**20 October 2026. 700 chunks, reranker off. Diagnosis only — no retrieval code was
changed, and the fix at the end is proposed rather than applied.**

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
fuel-station norms on p855, at rank 1). Asked at the point, it falls to **rank 14** —
eight ranks below what a user ever sees. `docs/DEMO.md` cut the question for this reason
and `docs/PROJECT_STATUS.md` carries it as limitation 4.

**It is the location path, and specifically it is step 2 of three: query expansion.**

---

## 2. Where the clause lands, measured

`11.1.1@p854` only. `dense` and `BM25` are its rank inside each index's own pool after
filtering; the raw-pool note says where it sat before filtering, which is how
"exclusion dropped it" is told apart from "the query stopped finding it".

| configuration | query actually searched | fused rank | dense | BM25 |
| --- | --- | --- | --- | --- |
| no point at all | `Can a fuel station be built here?` | **3** | 10 | 2 |
| the point, everything on (ships) | `…built here? Zone O Yamuna floodplain` | **14** | — (absent from a 60-deep raw pool) | 2 |
| the point, no exclusion | `…built here? Zone O Yamuna floodplain` | **14** | — (absent) | 2 |
| the point, no boost | `…built here? Zone O Yamuna floodplain` | **15** | — (absent) | 2 |
| the point, **no query expansion** | `Can a fuel station be built here?` | **1** | 8 | 2 |
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

## 5. Proposed fix (not applied)

**Apply query expansion only for topics that have a policy section of their own** — the
same four that are already allowed to exclude. `zone_o` and `ridge` keep the other two
steps: they are still boosted, and exclusion is unaffected.

In `app/location.py` that is a few lines: a constant naming the four topics, and
`expand_query` skipping the others. Measured, with the terms for the two topics removed:

| | fuel station, "here" | fuel station, "in Zone O" |
| --- | --- | --- |
| ships | rank 14 | rank 11 |
| proposed | **rank 1** | **rank 1** |

and `11.1.1@p855`, the fuel-station norms, follows at rank 2 in both — so the user gets
the permission rule *and* the controls.

**What it does to the five published demo beats**, which is the test that matters,
because these are the answers the project already shows people:

| beat | top 3, ships | top 3, proposed | |
| --- | --- | --- | --- |
| 1 P_TOD | `4.2.1`, `4.2.3@p751`, `4.2.3@p753` | identical | **unchanged** |
| 2 P_HDC | `4.3@p757`, `Q1@p15`, `1.7.1@p666` | identical | **unchanged** |
| 4 P_LDA | `4.4.3`, `Q3@p18`, `4.4@p764` | identical | **unchanged** |
| 3 P_ZONEO | `3.1.2@p681`, `2:0`, `3@p25:1` | `2:0`, `3.1.2@p681`, `9.2` | changed |
| 5 P_RIDGE | `10.1@p842`, `3.1.2@p681`, `3.1.2@p683` | `10.1@p843`, `3.1.2@p681`, `9.2` | changed |

Three are **bit-identical**, not similar — the three whose topics keep their expansion.
The two that change are exactly the two the fix is about:

- **Beat 3** keeps both of its best sources and swaps their order: the High Court order
  (`DHC_YAMUNA_20240708:2:0`) moves to rank 1 and the Green-Blue Infrastructure clause to
  rank 2. Arguably better — the court order is the document that actually prohibits
  construction — but it is a change, and the demo's cosine figure would need re-running.
  The sharper wording the demo also offers, *"What are the rules for the active
  floodplain?"*, still puts `3.1.2@p681` at rank 1.
- **Beat 5** stays in chapter 10's definitions and moves one chunk along, `10.1@p842` to
  `10.1@p843`. The demo's point about that beat — that what comes back is a *definition*
  and not a permission rule — survives, but the clause ids in the table change.

### Three alternatives, measured and rejected

| alternative | fuel station | what it costs |
| --- | --- | --- |
| **Fuse a third list**: add `dense(original query)` to the RRF alongside `dense(expanded)` and `bm25(expanded)` | rank 1 | Breaks beats 2 and 4: the un-expanded dense list votes for the FAQ's conversational phrasing, so `Q5@p15` and `Q18@p16` displace the gazette's `4.3@p757`, putting **authority rank 3 above authority rank 1**. Beat 1 loses `4.2.1` from the top 3. |
| **The same at half weight** (`0.5/(k+rank)`) | rank 8 — still invisible | The worst of both: the FAQ promotion on beats 2 and 4 happens anyway and the fuel-station clause does not reach the top 6. |
| **Expand the keyword query only**, leaving the dense query plain | rank 1 | Same FAQ-over-gazette problem on beats 2 and 4, and it throws away the dense half of the location effect at *every* point, not just the two that need it. |

The common failure in all three is worth stating, because it is the reason the scoped fix
is the right shape: any change that re-admits the **un-expanded** dense ranking at every
point re-admits plain semantic search, and plain semantic search over this corpus likes
the FAQ's short conversational chunks. The expansion is what keeps the gazette on top.
It should therefore be removed only where it has nothing to aim at, which is the two
topics with no policy section — and not weakened everywhere.

A fourth option, **turning expansion off entirely**, is the same measurement as row 5 of
§ 2 and is rejected for the same reason: it would discard the effect that beats 1, 2 and
4 exist to show.

---

## 6. What has to happen before this is applied

Not tonight, and not unattended. Three reasons, in order of weight:

1. **There is still no verified question set.** Every retrieval change in this project
   waits on the same thing (D-070 for the reranker, D-071 for the threshold), and this one
   is no different: two questions at one point is a finding, not evidence. The honest
   version of this fix ships as a setting that is **off by default** and as a fifth
   configuration in `eval/run_eval.py`, scored against `questions_verified.jsonl`
   alongside `hybrid`, `hybrid+location` and `hybrid+location+rerank`.
2. **It changes two published demo beats.** `docs/DEMO.md` prints observed clause ids and
   says they were observed. If the fix is switched on, those two tables have to be re-run
   and the beat-3 narrative re-read, because a court order at rank 1 is a different story
   to tell than an environment clause at rank 1.
3. **The `ridge` half is untested against a question that needs it.** The fix is justified
   by a mechanism that applies to both topics, but it is only *measured* on `zone_o`. A
   Ridge question whose subject is not the Ridge — "what is the parking norm here?" at
   P_RIDGE — would be the matching test, and there is not one in the draft set.

**What should happen now, and costs nothing:** `docs/PROJECT_STATUS.md` limitation 4 can
stop saying "not diagnosed". It is diagnosed. The step is query expansion, the mechanism
is that a place name acts as a subject rather than a qualifier, and the scope is the two
zones that have no policy section — which is the same pair, for the same underlying
reason, as the pair that cannot exclude.
