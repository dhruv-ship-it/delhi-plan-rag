# Fix round 1 verification run (fix1)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-21T17:10:14+00:00 / 2026-10-21T17:17:44+00:00 |
| Cases done | **12 of 12** |
| Answered | **8** |
| Abstained | **4** |
| Failed outright | 0 |
| Citation retries | 0 |
| Latency p50 / p95 | 40.0 s / 61.6 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 69,576 |
| Tokens used, last run | 69,576 of a 100,000 per-run budget |
| LLM calls, all runs | 30 |
| LLM calls, last run | 30 of a 120 per-run cap |
| Runs so far | 1 |
| 429s / rate-limit waits | 0 / 0 |
| Gap between calls | 2.5 s |
| State | **finished** |

Abstentions by reason:

| reason | n |
| --- | --- |
| `model_abstained` | 3 |
| `unsupported_claims` | 1 |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '970', 'x-ratelimit-reset-requests': '43m12s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '51', 'x-ratelimit-reset-tokens': '59.617s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

## v1 against v2 against v3 against v4

The 10 case(s) every run recorded, read off the state files. The same questions at the same points with the same budget each time; what changed between v3 and v4 is D-100 to D-106: the rejected-answer rescue, SUPPORT_CHECK=enforce, three prompt instructions, and the NGT report out of the index. **Still nobody has read these answers.**

| case | question | v1 | v2 | v3 | v4 | retries | citations | note? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [demo-03](#demo-03) | Is construction allowed here? | answered, 118 words | answered, 36 words | answered, 60 words | answered, 59 words | 1 → 0 → 0 → 0 | 2 → 1 → 3 → 2 | no |
| [demo-04](#demo-04) | What are the rules for the active floodpla… | answered, 92 words | answered, 112 words | answered, 137 words | answered, 59 words | 1 → 0 → 0 → 0 | 2 → 1 → 1 → 2 | no |
| [demo-06](#demo-06) | Can I build a house here? | answered, 77 words | answered, 65 words | answered, 74 words | answered, 72 words | 1 → 0 → 0 → 0 | 2 → 2 → 2 → 2 | no |
| [demo-07](#demo-07) | Is construction allowed here? | answered, 134 words | answered, 60 words | answered, 103 words | answered, 79 words | 1 → 0 → 0 → 0 | 4 → 2 → 2 → 2 | no |
| [demo-10](#demo-10) | Can a fuel station be built here? | answered, 50 words | answered, 31 words | answered, 39 words | answered, 9 words | 0 → 0 → 0 → 0 | 1 → 1 → 2 → 1 | no |
| [demo-12](#demo-12) | Can I build a house here? | abstained `citation_check_failed` | abstained `model_abstained` | abstained `model_abstained` | answered, 53 words | 1 → 0 → 0 → 0 | 0 → 0 → 0 → 2 | no |
| [demo-13](#demo-13) | How much of my plot can I build on? | answered, 215 words | answered, 50 words | answered, 129 words | answered, 98 words | 1 → 0 → 0 → 0 | 4 → 2 → 3 → 1 | no |
| [demo-14](#demo-14) | What is the permissible FAR for plotted ho… | answered, 182 words | answered, 45 words | answered, 34 words | answered, 60 words | 1 → 0 → 0 → 0 | 2 → 1 → 1 → 1 | no |
| [agent-02](#agent-02) | Can I build a house on the Yamuna floodpla… | abstained `model_abstained` | answered, 31 words | abstained `model_abstained` | abstained `model_abstained` | — → 0 → 0 → 0 | 0 → 1 → 0 → 0 | yes |
| [agent-05](#agent-05) | Is construction allowed in the Ridge near … | abstained `model_abstained` | answered, 39 words | abstained `model_abstained` | abstained `model_abstained` | — → 0 → 0 → 0 | 0 → 2 → 0 → 0 | yes |

2 case(s) are new in v4 and have no earlier column: [probe-01](#probe-01), [probe-02](#probe-02).

### Totals, over those 10 cases only

The pass rate counts only the cases whose answer actually reached the citation check: a point outside Delhi never calls the model, and a case the model declined under rule 3 has nothing to check. It is split by mode because v1 could not count an agent retry, so an agent case is missing from its denominator and present in later ones. A **dash** means the run predates the field, not that the number is zero.

| | v1 | v2 | v3 | v4 |
| --- | --- | --- | --- | --- |
| answered / abstained | 7 / 3 | 9 / 1 | 7 / 3 | 8 / 2 |
| first-attempt pass rate, map mode | 12% (1 of 8) | 100% (7 of 7) | 100% (7 of 7) | 100% (8 of 8) |
| first-attempt pass rate, agent mode | — | 100% (2 of 2) | — | — |
| citation retries | 7 | 0 | 0 | 0 |
| `citation_check_failed` | 1 | 0 | 0 | 0 |
| should-abstain handled right | 1 of 2 | 1 of 2 | 1 of 2 | 0 of 2 |
| agent location within tolerance | 1 of 1 | 2 of 2 | 2 of 2 | 2 of 2 |
| median words, answered cases | 118 | 45 | 74 | 60 |
| median citations, answered cases | 2 | 1 | 2 | 2.0 |
| location notes shown | — | — | 2 | 2 |
| claim check ran on | — | — | 7 | 8 |
| sentences `supported` | — | — | 15 | 9 |
| sentences `partly` | — | — | 3 | 5 |
| sentences `unsupported` | — | — | 1 | 1 |
| cases `enforce` would change | — | — | [demo-10](#demo-10) | [demo-10](#demo-10) |
| … of those, would abstain | — | — | none | none |
| tokens per case (mean) | 5,644 | 3,755 | 5,632 | 5,554 |
| … of which, the answer | — | — | 4,182 | 4,280 |
| … of which, the claim check | — | — | 1,450 | 1,274 |

**How to read the retry column.** In v1 the agent's retries could not be counted at all — the field was `llm_calls - 1`, which only works when a case makes one call, and an agent run's calls include its tool rounds. From v2 one problems list is recorded per rejected attempt (D-087), so the number is read rather than inferred. A v1 agent row therefore shows a dash and not `0`.

**What the claim-check rows are and are not.** `SUPPORT_CHECK=shadow`, so every verdict in this run was recorded and **none of them changed an answer** (D-096). The `enforce` rows say what the other mode would have done to these same answers, which is the question a reader has to settle before that mode is turned on. They are a model's judgement of a model, so they are evidence and not a verdict.

**`demo-07`, explicitly.** It is the should-abstain beat at P_RIDGE that answered in v1 (134 words) and again in v2 (60 words), citing clauses that do not say it, and it is the case the claim check exists for. In this run `enforce` would **not** have changed it, which is the more interesting outcome of the two: the structural check passed it, the semantic check passed it, and a reader still has to decide whether the answer is right. The cases `enforce` would have changed are [demo-10](#demo-10).

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| answered a should-abstain question | **2** | [demo-07](#demo-07), [demo-12](#demo-12) |
| the claim check called 1 sentence(s) unsupported | **2** | [demo-10](#demo-10), [probe-01](#probe-01) |
| abstained on an answerable question | **1** | [agent-02](#agent-02) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-03

**Is construction allowed here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3)
- **Answered** in 59 words
- **Cost:** 3.8 s, 1 llm call(s), 3702 in / 505 out tokens, 0 rate-limit retr(y/ies)

> Active floodplain, which includes Zone O as a Yamuna floodplain, is designated a ‘no construction zone’ where only recreational uses are permitted, and all unauthorised construction must be demolished [C2].
> The Delhi High Court has directed the removal of all encroachments and illegal construction on the Yamuna river bank and floodplain, reinforcing that such construction is not allowed [C3].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `DHC_YAMUNA_20240708:6:0` | 6 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2-3 |

<sub>Retrieved: `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:6:0`, `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:4.5.1:0`, `MPD47_GAZETTE_EN:p1013:1`</sub>

### demo-04

**What are the rules for the active floodplain?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3, sharper)
- **Answered** in 59 words
- **Cost:** 4.8 s, 1 llm call(s), 3706 in / 360 out tokens, 0 rate-limit retr(y/ies)

> Active floodplain is designated as a ‘no construction zone’ where only recreational uses are permitted and all unauthorised construction, including religious structures, must be demolished by the concerned agency on priority [C1].
> The zone is also described as a prohibited activity zone because encroachment diverts water and leads to floods, as acknowledged by respondents in the court proceedings [C5].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `DHC_YAMUNA_20240708:3:0` | 3 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:p1013:0`, `DHC_YAMUNA_20240708:6:0`, `DHC_YAMUNA_20240708:3:0`, `MPD47_GAZETTE_EN:3.1.2@p680:0`</sub>

### demo-06

**Can I build a house here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4, alternative)
- **Answered** in 72 words
- **Cost:** 27.9 s, 1 llm call(s), 3608 in / 430 out tokens, 0 rate-limit retr(y/ies)

> Low Density Area (LDA) comprises areas within the depth of one peripheral village revenue boundary along the border of NCTD and LDRA as defined in the Master Plan for Delhi 2047 [C2].
> For residential use in LDA, the minimum plot size is 10,000 sq m and the development control norms are FAR 10, maximum ground coverage 15%, maximum building height 10 m, and a minimum rear‑of‑site (RoW) setback of 18 m [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.4@p764:0` | 4.4 | Master Plan for Delhi 2047 gazette notification (English) | 764 |
| `MPD47_GAZETTE_EN:4.4.3:0` | 4.4.3 | Master Plan for Delhi 2047 gazette notification (English) | 766-767 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_FAQ:Q4@p18:0`, `MPD47_FAQ:Q8@p3:0`</sub>

### demo-07

**Is construction allowed here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (beat 5, the should-abstain beat)
- **Answered** in 79 words
- **Cost:** 38.7 s, 1 llm call(s), 4594 in / 655 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question

> In the Ridge/Regional Park area, new construction is generally restricted and may be permitted only for socio‑cultural, recreational uses or essential government utilities and public infrastructure, subject to approval/NOC of the competent authority or statutory body [C1].
> Any development within a Regional Park must comply with the specific controls set out for Regional Parks, including obtaining necessary approvals from the Forest Department and adhering to security and amenity provisions, and no general construction is allowed without such clearances [C3].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `MPD47_GAZETTE_EN:10.2.1@p846:0` | 10.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 846 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.2.1@p846:0`, `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:3.1.2@p683:0`</sub>

### demo-10

**Can a fuel station be built here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3b; was cut, fixed by D-086)
- **Answered** in 9 words
- **Cost:** 40.0 s, 1 llm call(s), 4660 in / 394 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** the claim check called 1 sentence(s) unsupported

> Fuel stations are not permitted in Zone O [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1.1 | Master Plan for Delhi 2047 gazette notification (English) | 854-855 |

<sub>Retrieved: `MPD47_GAZETTE_EN:11.1.1@p854:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:Annexure 18:0`, `MPD47_GAZETTE_EN:1.8@p670:0`</sub>

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; D-086 left it weaker still)
- **Answered** in 53 words
- **Cost:** 28.9 s, 1 llm call(s), 4729 in / 507 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question

> The Ridge is designated as a Regional Park, which is defined as a park of minimum area of 40 Ha of natural, semi‑natural or planted space set aside for recreation and/or protection/preservation [C1]
> Regional Park falls under Use Zone P1 in the Recreational land‑use category, which is not a residential use zone [C6]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 842 |
| `MPD47_GAZETTE_EN:5.1.3@p796:0` | 5.1.3 | Master Plan for Delhi 2047 gazette notification (English) | 796-797 |

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:p911:1`, `MPD47_GAZETTE_EN:5.1.3@p796:0`</sub>

### demo-13

**How much of my plot can I build on?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** either   (cut; wanders at ranks 2-3)
- **Answered** in 98 words
- **Cost:** 43.2 s, 1 llm call(s), 5264 in / 568 out tokens, 0 rate-limit retr(y/ies)

> For plotted housing the maximum ground coverage is 90% for plots up to 100 sqm and 75% for plots above 100 sqm up to 750 sqm, with the maximum FAR ranging from 350 for plots up to 250 sqm down to 200 for plots above 750 sqm as specified in clause 7.2.1 of the Master Plan (C6) [C6].
> The minimum plot size for residential development is 32 sqm, and the total ground coverage and floor area for any plot category shall not be less than that available to the largest plot in the next lower category (C6) [C6].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:4.6.5@p785:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:4.6.4@p781:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`</sub>

### demo-14

**What is the permissible FAR for plotted housing?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (the demo's replacement)
- **Answered** in 60 words
- **Cost:** 40.8 s, 1 llm call(s), 4599 in / 654 out tokens, 0 rate-limit retr(y/ies)

> For plotted housing the maximum permissible FAR is 350 for plots up to 100 sqm, 300 for plots above 100 sqm up to 250 sqm, and 225 – 200 for larger plots as detailed in the table (250‑750 sqm: 225; 750‑1000 sqm: 200; 1000‑1500 sqm: 200; 1500‑2250 sqm: 200; 2250‑3000 sqm: 200; 3000‑3750 sqm: 200; above 3750 sqm: 200) [C2]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:9.1.3:0`, `MPD47_GAZETTE_EN:11.1.3@p859:0`, `MPD47_FAQ:Q6@p3:0`</sub>

## b. agent mode, a place named in words

### agent-02

**Can I build a house on the Yamuna floodplain near ITO?**

- **Where:** no pin — the agent found 28.62819, 77.24104
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (the floodplain, named in words)
- **Abstained:** `model_abstained: No clause found addressing house construction on Yamuna floodplain at the specified location.`
- **Cost:** 61.6 s, 4 llm call(s), 7889 in / 240 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 13 m from the expected place (tolerance 3000 m)
- **Suspected:** abstained on an answerable question (model_abstained: No clause found addressing house construction on Yamuna floodplain at the specified location.)

Tool trace:

1. `locate_place` {"query": "ITO"} -> found ITO (Delhi Metro) at 28.62819, 77.24104
1. `get_zones` {"lat": 28.628191, "lon": 77.241044} -> planning zone D; in TOD zone — This point is not inside Zone O (Yamuna floodplain) on DDA's map; the nearest Zone O boundary is about 600 m away.
1. `search_clauses` {"k": 5, "lat": 28.628191, "lon": 77.241044, "query": "Yamuna floodplain house construction"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.2:0, S2 MPD47_GAZETTE_EN:4.2.4@p755:0, S3 MPD47_GAZETTE_EN:4.2.1:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.4@p754:0`</sub>

### agent-05

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin — the agent found 28.50672, 77.17500
- **Zones:** planning zone J; in none of the six policy zones
- **Mode:** agent   **Expected:** either   (a Ridge question with no pin; no indexed clause states a construction rule for the Ridge, and 3.1.2's only Ridge mention is the Ridge-Yamuna cycling connector (D-106))
- **Abstained:** `model_abstained: Insufficient clause information on construction rules for the Ridge near Chhatarpur`
- **Cost:** 63.4 s, 4 llm call(s), 8216 in / 259 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 4000 m)

Tool trace:

1. `locate_place` {"query": "Chhatarpur"} -> found Chhatarpur (Delhi Metro) at 28.50672, 77.17500
1. `get_zones` {"lat": 28.506724, "lon": 77.175002} -> planning zone J; in none of the six policy zones — This point is not inside the Ridge / a Regional Park on DDA's map; the nearest Ridge / Regional Park boundary is about 100 m away.
1. `search_clauses` {"k": 5, "lat": 28.506724, "lon": 77.175002, "query": "Ridge construction allowed"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:3.1.2@p681:0, S2 MPD47_GAZETTE_EN:10.1@p843:0, S3 MPD47_GAZETTE_EN:10.1@p842:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:10.2.3:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`</sub>

## d. probes for the location note

### probe-01

**Can I build on the Yamuna floodplain here?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** either   (probe: names Zone O at a point get_zones puts in a TOD zone, 2.7 km away (D-094))
- **Abstained:** `unsupported_claims`
- **Cost:** 39.5 s, 1 llm call(s), 4831 in / 648 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** the claim check called 1 sentence(s) unsupported

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p754:0`, `MPD47_GAZETTE_EN:p642:0`</sub>

### probe-02

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin — the agent found 28.50672, 77.17500
- **Zones:** planning zone J; in none of the six policy zones
- **Mode:** agent   **Expected:** either   (probe: the same question as agent-05, re-asked with the note in place (D-094); no indexed clause states a construction rule for the Ridge, and 3.1.2's only Ridge mention is the Ridge-Yamuna cycling connector (D-106))
- **Abstained:** `model_abstained: No clause directly addresses construction permission in the Ridge near Chhatarpur.`
- **Cost:** 55.7 s, 4 llm call(s), 8216 in / 342 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 4000 m)

Tool trace:

1. `locate_place` {"query": "Chhatarpur"} -> found Chhatarpur (Delhi Metro) at 28.50672, 77.17500
1. `get_zones` {"lat": 28.506724, "lon": 77.175002} -> planning zone J; in none of the six policy zones — This point is not inside the Ridge / a Regional Park on DDA's map; the nearest Ridge / Regional Park boundary is about 100 m away.
1. `search_clauses` {"k": 5, "lat": 28.506724, "lon": 77.175002, "query": "Ridge construction allowed"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:3.1.2@p681:0, S2 MPD47_GAZETTE_EN:10.1@p843:0, S3 MPD47_GAZETTE_EN:10.1@p842:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:10.2.3:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`</sub>

