# Third real-model run (v3)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-20T10:44:39+00:00 / 2026-10-21T09:29:13+00:00 |
| Cases done | **23 of 23** |
| Answered | **17** |
| Abstained | **6** |
| Failed outright | 0 |
| Citation retries | 0 |
| Latency p50 / p95 | 33.9 s / 160.7 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 123,276 |
| Tokens used, last run | 54,876 of a 150,000 per-run budget |
| LLM calls, all runs | 57 |
| LLM calls, last run | 29 of a 120 per-run cap |
| Runs so far | 2 |
| 429s / rate-limit waits | 3 / 3 |
| Gap between calls | 2.5 s |
| State | **finished** |

Abstentions by reason:

| reason | n |
| --- | --- |
| `model_abstained` | 5 |
| `outside_delhi` | 1 |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '971', 'x-ratelimit-reset-requests': '41m45.6s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '83', 'x-ratelimit-reset-tokens': '59.377s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

## v1 against v2 against v3

The 21 case(s) every run recorded, read off the state files. The same questions at the same points with the same budget each time; what changed between v2 and v3 is D-092 to D-096 - the caveat moved out of the prompt into a field, the scoped four-list fusion, the named-zone mismatch note, the fuller-answer rule and the claim check in shadow mode. **Still nobody has read these answers.**

| case | question | v1 | v2 | v3 | retries | citations | note? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [demo-01](#demo-01) | How much of my plot can I build on? | answered, 132 words | answered, 71 words | answered, 37 words | 1 → 0 → 0 | 3 → 1 → 1 | no |
| [demo-02](#demo-02) | How much of my plot can I build on? | answered, 166 words | answered, 52 words | answered, 116 words | 1 → 0 → 0 | 2 → 1 → 1 | no |
| [demo-03](#demo-03) | Is construction allowed here? | answered, 118 words | answered, 36 words | answered, 60 words | 1 → 0 → 0 | 2 → 1 → 3 | no |
| [demo-04](#demo-04) | What are the rules for the active floodpla… | answered, 92 words | answered, 112 words | answered, 137 words | 1 → 0 → 0 | 2 → 1 → 1 | no |
| [demo-05](#demo-05) | What is the maximum ground coverage here? | answered, 114 words | answered, 37 words | answered, 15 words | 1 → 0 → 0 | 1 → 1 → 1 | no |
| [demo-06](#demo-06) | Can I build a house here? | answered, 77 words | answered, 65 words | answered, 74 words | 1 → 0 → 0 | 2 → 2 → 2 | no |
| [demo-07](#demo-07) | Is construction allowed here? | answered, 134 words | answered, 60 words | answered, 103 words | 1 → 0 → 0 | 4 → 2 → 2 | no |
| [demo-08](#demo-08) | Is construction allowed here? | abstained `outside_delhi` | abstained `outside_delhi` | abstained `outside_delhi` | 0 → 0 → 0 | 0 → 0 → 0 | no |
| [demo-09](#demo-09) | What is my property tax? | abstained `model_abstained` | abstained `model_abstained` | abstained `model_abstained` | 0 → 0 → 0 | 0 → 0 → 0 | no |
| [demo-10](#demo-10) | Can a fuel station be built here? | answered, 50 words | answered, 31 words | answered, 39 words | 0 → 0 → 0 | 1 → 1 → 2 | no |
| [demo-11](#demo-11) | Can a fuel station be built in Zone O? | answered, 106 words | answered, 24 words | answered, 20 words | 1 → 0 → 0 | 2 → 1 → 1 | no |
| [demo-12](#demo-12) | Can I build a house here? | abstained `citation_check_failed` | abstained `model_abstained` | abstained `model_abstained` | 1 → 0 → 0 | 0 → 0 → 0 | no |
| [demo-13](#demo-13) | How much of my plot can I build on? | answered, 215 words | answered, 50 words | answered, 129 words | 1 → 0 → 0 | 4 → 2 → 3 | no |
| [demo-14](#demo-14) | What is the permissible FAR for plotted ho… | answered, 182 words | answered, 45 words | answered, 34 words | 1 → 0 → 0 | 2 → 1 → 1 | no |
| [demo-15](#demo-15) | What is clause 4.2.1? | answered, 86 words | answered, 34 words | answered, 23 words | 0 → 0 → 0 | 1 → 1 → 1 | no |
| [demo-16](#demo-16) | How do I get my land included in a scheme? | abstained `citation_check_failed` | answered, 64 words | answered, 107 words | 1 → 0 → 0 | 0 → 2 → 3 | no |
| [agent-01](#agent-01) | What can be built near Hauz Khas metro? | answered, 188 words | answered, 97 words | answered, 103 words | — → 0 → 0 | 3 → 2 → 3 | no |
| [agent-02](#agent-02) | Can I build a house on the Yamuna floodpla… | abstained `model_abstained` | answered, 31 words | abstained `model_abstained` | — → 0 → 0 | 0 → 1 → 0 | yes |
| [agent-03](#agent-03) | How much of my plot can I build on near Ra… | abstained `citation_check_failed` | answered, 24 words | answered, 17 words | — → 0 → 0 | 0 → 1 → 1 | no |
| [agent-04](#agent-04) | What are the ground coverage rules for a p… | answered, 12 words | answered, 36 words | answered, 22 words | — → 0 → 0 | 1 → 1 → 1 | no |
| [agent-05](#agent-05) | Is construction allowed in the Ridge near … | abstained `model_abstained` | answered, 39 words | abstained `model_abstained` | — → 0 → 0 | 0 → 2 → 0 | yes |

2 case(s) are new in v3 and have no earlier column: [probe-01](#probe-01), [probe-02](#probe-02).

### Totals, over those 21 cases only

The pass rate counts only the cases whose answer actually reached the citation check: a point outside Delhi never calls the model, and a case the model declined under rule 3 has nothing to check. It is split by mode because v1 could not count an agent retry, so an agent case is missing from its denominator and present in later ones. A **dash** means the run predates the field, not that the number is zero.

| | v1 | v2 | v3 |
| --- | --- | --- | --- |
| answered / abstained | 14 / 7 | 18 / 3 | 16 / 5 |
| first-attempt pass rate, map mode | 14% (2 of 14) | 100% (13 of 13) | 100% (13 of 13) |
| first-attempt pass rate, agent mode | — | 100% (5 of 5) | 100% (3 of 3) |
| citation retries | 12 | 0 | 0 |
| `citation_check_failed` | 3 | 0 | 0 |
| should-abstain handled right | 3 of 4 | 3 of 4 | 3 of 4 |
| agent location within tolerance | 4 of 4 | 5 of 5 | 5 of 5 |
| median words, answered cases | 116 | 42 | 50 |
| median citations, answered cases | 2.0 | 1.0 | 1.0 |
| location notes shown | — | — | 2 |
| claim check ran on | — | — | 16 |
| sentences `supported` | — | — | 34 |
| sentences `partly` | — | — | 4 |
| sentences `unsupported` | — | — | 1 |
| cases `enforce` would change | — | — | [demo-10](#demo-10) |
| … of those, would abstain | — | — | none |
| tokens per case (mean) | 5,354 | 3,610 | 5,294 |
| … of which, the answer | — | — | 3,917 |
| … of which, the claim check | — | — | 1,377 |

**How to read the retry column.** In v1 the agent's retries could not be counted at all — the field was `llm_calls - 1`, which only works when a case makes one call, and an agent run's calls include its tool rounds. From v2 one problems list is recorded per rejected attempt (D-087), so the number is read rather than inferred. A v1 agent row therefore shows a dash and not `0`.

**What the claim-check rows are and are not.** `SUPPORT_CHECK=shadow`, so every verdict in this run was recorded and **none of them changed an answer** (D-096). The `enforce` rows say what the other mode would have done to these same answers, which is the question a reader has to settle before that mode is turned on. They are a model's judgement of a model, so they are evidence and not a verdict.

**`demo-07`, explicitly.** It is the should-abstain beat at P_RIDGE that answered in v1 (134 words) and again in v2 (60 words), citing clauses that do not say it, and it is the case the claim check exists for. In this run `enforce` would **not** have changed it, which is the more interesting outcome of the two: the structural check passed it, the semantic check passed it, and a reader still has to decide whether the answer is right. The cases `enforce` would have changed are [demo-10](#demo-10).

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| abstained on an answerable question | **2** | [agent-02](#agent-02), [agent-05](#agent-05) |
| answered a should-abstain question | **1** | [demo-07](#demo-07) |
| the claim check called 1 sentence(s) unsupported | **1** | [demo-10](#demo-10) |
| enforce mode would have changed this answer | **1** | [demo-10](#demo-10) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-01

**How much of my plot can I build on?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (beat 1)
- **Answered** in 37 words
- **Cost:** 3.5 s, 1 llm call(s), 3712 in / 338 out tokens, 0 rate-limit retr(y/ies)

> On a TOD Plot the maximum ground coverage permitted is 40% of the plot area, subject to any relaxations the TOD Committee may grant for height‑restricted private land, provided fire, safety and green‑space norms are met [C3].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2.4@p755:0`</sub>

### demo-02

**How much of my plot can I build on?**

- **Where:** P_HDC (28.659532, 77.006649)
- **Zones:** planning zone K-I; in high density corridor
- **Mode:** map   **Expected:** answer   (beat 2)
- **Answered** in 116 words
- **Cost:** 20.3 s, 1 llm call(s), 5872 in / 863 out tokens, 0 rate-limit retr(y/ies)

> An HDC Plot must have a minimum final plot size of 4,000 sqm after surrendering 50 % of an original plot of at least 8,000 sqm [C5].
> The plot must be accessible from a road with a minimum right‑of‑way width of 18 m [C5].
> For residential, commercial or PSP uses, the maximum permissible floor‑area ratio (FAR) is 400 [C5].
> Twenty percent of the permissible FAR must be allocated to affordable housing units of less than 60 sqm carpet area [C5].
> If the plot is used for warehousing or logistics, the maximum permissible FAR is 120 [C5].
> Ground‑coverage relaxations may be permitted by the TOD Committee if the FAR cannot be achieved due to site constraints [C5].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.3.3@p758:0` | 4.3.3 | Master Plan for Delhi 2047 gazette notification (English) | 758-759 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.3@p757:0`, `MPD47_FAQ:Q1@p15:0`, `MPD47_GAZETTE_EN:1.7.1@p666:0`, `MPD47_GAZETTE_EN:4.3.1:0`, `MPD47_GAZETTE_EN:4.3.3@p758:0`, `MPD47_GAZETTE_EN:4.3.3@p760:0`</sub>

### demo-03

**Is construction allowed here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3)
- **Answered** in 60 words
- **Cost:** 34.9 s, 1 llm call(s), 4046 in / 362 out tokens, 0 rate-limit retr(y/ies)

> Zone O, which lies within the active Yamuna floodplain, is designated as a ‘no construction zone’ where only recreational uses are permitted and all unauthorised construction must be demolished [C2].
> The Delhi High Court has ordered the demolition of unauthorised constructions on the Yamuna river bank and floodplain and seeks directions to prevent further illegal building in the area [C4][C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `DHC_YAMUNA_20240708:1:0` | 1 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2 |
| `DHC_YAMUNA_20240708:2:0` | 2 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2 |

<sub>Retrieved: `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:9.2:0`, `DHC_YAMUNA_20240708:1:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`</sub>

### demo-04

**What are the rules for the active floodplain?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3, sharper)
- **Answered** in 137 words
- **Cost:** 47.3 s, 1 llm call(s), 5586 in / 784 out tokens, 0 rate-limit retr(y/ies)

> The active floodplain is designated as a ‘no construction zone’ where only recreational uses are permitted and any unauthorised construction, including religious structures, must be demolished by the concerned agency on priority [C1].
> Essential government utilities, socio‑cultural and recreational activities, public infrastructure development and conservation of floodplains are allowed in the active floodplain only with the approval or NOC of the competent authority or statutory body [C1].
> Area outside the active floodplain is subject to restricted development; existing authorised and planned constructions and essential government utilities may continue as per permissible norms and with approval or NOC from the statutory body [C1].
> Further developments in the zone outside the active floodplain are limited to socio‑cultural and recreational uses, essential utilities and public infrastructure, and also require approval or NOC of the competent authority or statutory body [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `DHC_YAMUNA_20240708:3:0`, `NGT_OA572_GNCTD_REPORT:5@p8:0`, `NGT_OA572_GNCTD_REPORT:7@p9:0`</sub>

### demo-05

**What is the maximum ground coverage here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4)
- **Answered** in 15 words
- **Cost:** 29.1 s, 1 llm call(s), 3411 in / 196 out tokens, 0 rate-limit retr(y/ies)

> In the Low Density Area, the highest permissible ground coverage is 70% for Godowns/Warehouses [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.4.3:0` | 4.4.3 | Master Plan for Delhi 2047 gazette notification (English) | 766-767 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_FAQ:Q3@p18:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_GAZETTE_EN:4.4.2:0`</sub>

### demo-06

**Can I build a house here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4, alternative)
- **Answered** in 74 words
- **Cost:** 27.4 s, 1 llm call(s), 3330 in / 462 out tokens, 0 rate-limit retr(y/ies)

> In a Low Density Area the residential use permits a single dwelling unit with a floor area ratio of 10, maximum ground coverage of 15%, maximum building height of 10 m and a minimum rear‑of‑plot setback of 18 m on a plot of at least 10,000 sq m [C1].
> The Master Plan further states that housing in Low Density Areas shall continue as low‑density residential development with limited dwelling units and public facilities [C4].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.4.3:0` | 4.4.3 | Master Plan for Delhi 2047 gazette notification (English) | 766-767 |
| `MPD47_GAZETTE_EN:3.4.2:0` | 3.4.2 | Master Plan for Delhi 2047 gazette notification (English) | 708 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_FAQ:Q4@p18:0`, `MPD47_FAQ:Q8@p3:0`</sub>

### demo-07

**Is construction allowed here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (beat 5, the should-abstain beat)
- **Answered** in 103 words
- **Cost:** 39.9 s, 1 llm call(s), 4718 in / 684 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question

> In the Ridge/Regional Park (planning zone J), the Master Plan classifies it as an environmentally sensitive area where development is restricted to socio‑cultural, recreational uses, essential government utilities and public infrastructure with approval/NOC of the competent authority [C1]
> The Master Plan further states that any development in forest land within a Regional Park must be in accordance with the Forest Department and related statutory approvals [C3]
> Construction of permanent built structures in a Biodiversity Park is limited to 1 % of the park area or 10,000 sqm whichever is less, indicating a very limited allowance for built‑up area in such sensitive zones [C3]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `MPD47_GAZETTE_EN:10.2.1@p846:0` | 10.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 846 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.2.1@p846:0`, `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:3.1.2@p683:0`</sub>

### demo-08

**Is construction allowed here?**

- **Where:** P_OUT (28.495, 77.089)
- **Zones:** outside NCT Delhi
- **Mode:** map   **Expected:** abstain   (beat 6, outside Delhi)
- **Abstained:** `outside_delhi`
- **Cost:** 0.0 s, 0 llm call(s), 0 in / 0 out tokens, 0 rate-limit retr(y/ies)

### demo-09

**What is my property tax?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** abstain   (the added beat: unanswerable)
- **Abstained:** `model_abstained: insufficient information`
- **Cost:** 15.0 s, 1 llm call(s), 1922 in / 47 out tokens, 0 rate-limit retr(y/ies)

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.5:0`</sub>

### demo-10

**Can a fuel station be built here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3b; was cut, fixed by D-086)
- **Answered** in 39 words
- **Cost:** 33.9 s, 1 llm call(s), 4811 in / 335 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** the claim check called 1 sentence(s) unsupported; enforce mode would have changed this answer

> Fuel stations may be permitted in all Use Zones except Recreational zones and Zone O [C1].
> Zone O is part of the active Yamuna floodplain, which is designated a ‘no construction zone’ where only recreational uses are allowed [C4].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1.1 | Master Plan for Delhi 2047 gazette notification (English) | 854-855 |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:11.1.1@p854:0`, `NGT_OA572_GNCTD_REPORT:3@p18:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `MPD47_GAZETTE_EN:Annexure 18:0`</sub>

### demo-11

**Can a fuel station be built in Zone O?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3b, explicit wording)
- **Answered** in 20 words
- **Cost:** 29.5 s, 1 llm call(s), 4003 in / 226 out tokens, 0 rate-limit retr(y/ies)

> Fuel stations may be permitted in all Use Zones except Recreational (Regional Park, District Park, etc.) and Zone O [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1.1 | Master Plan for Delhi 2047 gazette notification (English) | 854-855 |

<sub>Retrieved: `MPD47_GAZETTE_EN:11.1.1@p854:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:11:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`</sub>

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; D-086 left it weaker still)
- **Abstained:** `model_abstained: Insufficient information on residential construction in Regional Park zone`
- **Cost:** 26.0 s, 1 llm call(s), 2977 in / 59 out tokens, 0 rate-limit retr(y/ies)

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:p911:1`, `MPD47_GAZETTE_EN:5.1.3@p796:0`</sub>

### demo-13

**How much of my plot can I build on?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** either   (cut; wanders at ranks 2-3)
- **Answered** in 129 words
- **Cost:** 52.6 s, 1 llm call(s), 6600 in / 919 out tokens, 0 rate-limit retr(y/ies)

> For plotted housing, the maximum floor area ratio (FAR) varies by plot size, ranging from 350 for plots up to 100 sqm to 200 for plots above 750 sqm [C6]
> The maximum ground coverage for plotted housing is 90 % for plots up to 100 sqm and 75 % for plots above 100 sqm up to 750 sqm, falling to 50 % for larger plots [C6]
> The minimum plot size for residential development is 32 sqm [C6]
> A general provision in the Master Plan states a permissible FAR of 200 irrespective of plot size [C2]
> Under the ISR scheme, the FAR can be as high as 500 and the rehabilitation plot must be at least 40 % of the total plot area, with no height or ground‑coverage restrictions [C5]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |
| `MPD47_GAZETTE_EN:4.6.5@p785:0` | 4.6.5 | Master Plan for Delhi 2047 gazette notification (English) | 785 |
| `MPD47_GAZETTE_EN:4.6.4@p781:0` | 4.6.4 | Master Plan for Delhi 2047 gazette notification (English) | 781-782 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:4.6.5@p785:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:4.6.4@p781:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`</sub>

### demo-14

**What is the permissible FAR for plotted housing?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (the demo's replacement)
- **Answered** in 34 words
- **Cost:** 34.7 s, 1 llm call(s), 4327 in / 459 out tokens, 0 rate-limit retr(y/ies)

> For plotted housing the maximum permissible FAR is 350 for plots up to 250 sqm, 225 for plots above 250 sqm up to 750 sqm, and 200 for plots larger than 750 sqm [C2].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:9.1.3:0`, `MPD47_GAZETTE_EN:11.1.3@p859:0`, `MPD47_FAQ:Q6@p3:0`</sub>

### demo-15

**What is clause 4.2.1?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (in your pocket: BM25 earning its place)
- **Answered** in 23 words
- **Cost:** 160.7 s, 1 llm call(s), 2786 in / 208 out tokens, 1 rate-limit retr(y/ies)

> Clause 4.2.1 provides definitions for terms used in the TOD policy, including “TOD Zone”, “TOD Plot”, “Carpet Area”, and “Developer Entity (DE)” [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.1:0` | 4.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 750-751 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.2:0`</sub>

### demo-16

**How do I get my land included in a scheme?**

- **Where:** P_LP (28.676901, 77.027085)
- **Zones:** planning zone K-I; in land pooling area L
- **Mode:** map   **Expected:** answer   (in your pocket)
- **Answered** in 107 words
- **Cost:** 1941.6 s, 1 llm call(s), 3750 in / 607 out tokens, 2 rate-limit retr(y/ies)

> Landowners with any size of land parcel in the designated land‑pooling area may register and participate according to the application process specified in the Regulations [C6]
> The land parcels offered for pooling must be free from all encumbrances and the owner must have valid lawful ownership and physical possession of the parcel [C1]
> Land parcels of any size can be brought under pooling provided they fall within the area notified by DDA or the Government under the Land Pooling Policy [C5]
> For schemes developed through assembly of land by a group of landowners, the minimum area for each scheme shall not be less than 20 ha [C1]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_FAQ:Q4@p8:0` | Q4 | FAQs on MPD-2047 | 8 |
| `MPD47_GAZETTE_EN:4.1.2:0` | 4.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 747-748 |
| `MPD47_FAQ:Q5@p8:0` | Q5 | FAQs on MPD-2047 | 8 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_FAQ:Q8@p9:0`, `MPD47_FAQ:Q13@p9:0`, `MPD47_FAQ:Q16@p10:0`, `MPD47_FAQ:Q5@p8:0`, `MPD47_FAQ:Q4@p8:0`</sub>

## b. agent mode, a place named in words

### agent-01

**What can be built near Hauz Khas metro?**

- **Where:** no pin — the agent found 28.54381, 77.20588
- **Zones:** planning zone F; in TOD zone
- **Mode:** agent   **Expected:** answer   (interchange, D-084)
- **Answered** in 103 words
- **Cost:** 13.5 s, 4 llm call(s), 8602 in / 969 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Hauz Khas metro"} -> found Hauz Khas (Delhi Metro interchange, 2 lines) at 28.54381, 77.20588
1. `get_zones` {"lat": 28.543813, "lon": 77.205876} -> planning zone F; in TOD zone
1. `search_clauses` {"k": 6, "lat": 28.543813, "lon": 77.205876, "query": "building near metro F zone TOD"} -> 6 clause(s): S1 MPD47_GAZETTE_EN:4.2.1:0, S2 MPD47_GAZETTE_EN:4.2.4@p755:0, S3 MPD47_FAQ:Q1@p11:0...

> In the 500 m corridor on either side of the Hauz Khas metro corridor, which is a TOD zone, development is governed by the Transit‑Oriented Development (TOD) policy [S4]
> A TOD plot is defined as a plot of at least 2000 sqm that meets all eligibility criteria set out in the policy [S1]
> TOD projects must comply with the mandatory sustainability and green‑building provisions of the Master Plan and UBBL, including water conservation, solar energy use and waste management [S2]
> Developers must pay TOD charges and any additional FAR charges required for floor‑area‑ratio beyond 400, deposited through the OBPS after plot sanction [S2]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.2:0` | 4.2.2 | Master Plan for Delhi 2047 gazette notification (English) | 751 |
| `MPD47_GAZETTE_EN:4.2.1:0` | 4.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 750-751 |
| `MPD47_GAZETTE_EN:4.2.4@p755:0` | 4.2.4 | Master Plan for Delhi 2047 gazette notification (English) | 755-756 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_FAQ:Q1@p11:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2@p750:0`</sub>

### agent-02

**Can I build a house on the Yamuna floodplain near ITO?**

- **Where:** no pin — the agent found 28.62819, 77.24104
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (the floodplain, named in words)
- **Abstained:** `model_abstained: Insufficient clause information to determine house construction rules for the Yamuna floodplain near ITO`
- **Cost:** 56.8 s, 4 llm call(s), 6991 in / 299 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 13 m from the expected place (tolerance 3000 m)
- **Suspected:** abstained on an answerable question (model_abstained: Insufficient clause information to determine house construction rules for the Yamuna floodplain near ITO)

Tool trace:

1. `locate_place` {"query": "ITO"} -> found ITO (Delhi Metro) at 28.62819, 77.24104
1. `get_zones` {"lat": 28.628191, "lon": 77.241044} -> planning zone D; in TOD zone — This point is not inside Zone O (Yamuna floodplain) on DDA's map; the nearest Zone O boundary is about 600 m away.
1. `search_clauses` {"k": 5, "lat": 28.628191, "lon": 77.241044, "query": "Yamuna floodplain construction house"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.2:0, S2 MPD47_GAZETTE_EN:4.2.4@p754:0, S3 MPD47_GAZETTE_EN:3.1.2@p681:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.4@p754:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:1:0`, `DHC_YAMUNA_20240708:3:0`</sub>

### agent-03

**How much of my plot can I build on near Rajiv Chowk metro station?**

- **Where:** no pin — the agent found 28.63271, 77.21931
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, a plain station)
- **Answered** in 17 words
- **Cost:** 45.7 s, 4 llm call(s), 8460 in / 312 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 1 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Rajiv Chowk metro station"} -> found Rajiv Chowk (Delhi Metro) at 28.63271, 77.21931
1. `get_zones` {"lat": 28.632706, "lon": 77.219312} -> planning zone D; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.632706, "lon": 77.219312, "query": "maximum ground coverage plot"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.3@p753:0, S2 MPD47_FAQ:Q13@p13:0, S3 MPD47_GAZETTE_EN:4.2.1:0...

> For a TOD Plot near Rajiv Chowk metro station, the maximum ground coverage permitted is 40% [S1]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`</sub>

### agent-04

**What are the ground coverage rules for a plot near Dwarka Sector 21 metro station?**

- **Where:** no pin — the agent found 28.55192, 77.05856
- **Zones:** planning zone K-II; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, the D-049 query)
- **Answered** in 22 words
- **Cost:** 66.7 s, 4 llm call(s), 8211 in / 371 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 5 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Dwarka Sector 21 metro station"} -> found Dwarka Sector 21, Dwarka Sector 21 Underpass, Najafgarh, Delhi, South West Delhi, Delhi, 110061, India at 28.55192, 77.05856
1. `get_zones` {"lat": 28.5519218, "lon": 77.0585605} -> planning zone K-II; in TOD zone
1. `search_clauses` {"k": 6, "lat": 28.5519218, "lon": 77.0585605, "query": "ground coverage"} -> 6 clause(s): S1 MPD47_GAZETTE_EN:4.2.3@p753:0, S2 MPD47_GAZETTE_EN:4.2@p750:0, S3 MPD47_GAZETTE_EN:4.2.1:0...

> For a TOD Plot near Dwarka Sector 21 metro station, the maximum ground coverage permitted is 40% of the plot area [S1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.5:0`</sub>

### agent-05

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin — the agent found 28.50672, 77.17500
- **Zones:** planning zone J; in none of the six policy zones
- **Mode:** agent   **Expected:** answer   (a Ridge question with no pin)
- **Abstained:** `model_abstained: No clause directly addresses construction permission in the Ridge near Chhatarpur`
- **Cost:** 51.9 s, 4 llm call(s), 8291 in / 275 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 4000 m)
- **Suspected:** abstained on an answerable question (model_abstained: No clause directly addresses construction permission in the Ridge near Chhatarpur)

Tool trace:

1. `locate_place` {"query": "Chhatarpur"} -> found Chhatarpur (Delhi Metro) at 28.50672, 77.17500
1. `get_zones` {"lat": 28.506724, "lon": 77.175002} -> planning zone J; in none of the six policy zones — This point is not inside the Ridge / a Regional Park on DDA's map; the nearest Ridge / Regional Park boundary is about 100 m away.
1. `search_clauses` {"lat": 28.506724, "lon": 77.175002, "query": "Ridge construction allowed"} -> 6 clause(s): S1 MPD47_GAZETTE_EN:3.1.2@p681:0, S2 MPD47_GAZETTE_EN:10.1@p843:0, S3 MPD47_GAZETTE_EN:10.1@p842:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:10.2.3:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`, `MPD47_GAZETTE_EN:9.2:0`</sub>

## d. probes for the location note

### probe-01

**Can I build on the Yamuna floodplain here?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** either   (probe: names Zone O at a point get_zones puts in a TOD zone, 2.7 km away (D-094))
- **Answered** in 23 words
- **Cost:** 27.7 s, 1 llm call(s), 3076 in / 277 out tokens, 0 rate-limit retr(y/ies)

> Active floodplain areas are designated as ‘no construction zones’ where only recreational uses are permitted and all unauthorised construction must be demolished [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:3:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.2:0`</sub>

### probe-02

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin — the agent found 28.50672, 77.17500
- **Zones:** planning zone J; in none of the six policy zones
- **Mode:** agent   **Expected:** either   (probe: the same question as agent-05, re-asked with the note in place (D-094))
- **Abstained:** `model_abstained: Insufficient specific clause on construction permissions in the Ridge near the queried location.`
- **Cost:** 32.8 s, 4 llm call(s), 8508 in / 234 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 4000 m)

Tool trace:

1. `locate_place` {"query": "Chhatarpur"} -> found Chhatarpur (Delhi Metro) at 28.50672, 77.17500
1. `get_zones` {"lat": 28.506724, "lon": 77.175002} -> planning zone J; in none of the six policy zones — This point is not inside the Ridge / a Regional Park on DDA's map; the nearest Ridge / Regional Park boundary is about 100 m away.
1. `search_clauses` {"k": 5, "lat": 28.506724, "lon": 77.175002, "query": "Ridge construction allowed"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:3.1.2@p681:0, S2 MPD47_GAZETTE_EN:10.1@p843:0, S3 MPD47_GAZETTE_EN:10.1@p842:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:10.2.3:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`</sub>

