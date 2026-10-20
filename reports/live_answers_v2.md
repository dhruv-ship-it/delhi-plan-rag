# Second real-model run (v2)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-20T05:15:56+00:00 / 2026-10-20T05:23:38+00:00 |
| Cases done | **21 of 21** |
| Answered | **18** |
| Abstained | **3** |
| Failed outright | 0 |
| Citation retries | 0 |
| Latency p50 / p95 | 21.9 s / 52.2 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 75,808 |
| Tokens used, last run | 75,808 of a 150,000 per-run budget |
| LLM calls, all runs | 35 |
| LLM calls, last run | 35 of a 120 per-run cap |
| Runs so far | 1 |
| 429s / rate-limit waits | 0 / 0 |
| Gap between calls | 2.5 s |
| State | **finished** |

Abstentions by reason:

| reason | n |
| --- | --- |
| `model_abstained` | 2 |
| `outside_delhi` | 1 |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '961', 'x-ratelimit-reset-requests': '56m9.6s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '49', 'x-ratelimit-reset-tokens': '59.632s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

## v1 against v2

The 21 case(s) both runs recorded, read off the two state files. Both ran the same questions at the same points with the same budget; what changed between them is D-086 to D-090 — scoped query expansion, structured answers, agent labels and the geocoding fallback. **Still nobody has read these answers.**

| case | question | v1 | v2 | retries v1 → v2 | citations v1 → v2 |
| --- | --- | --- | --- | --- | --- |
| [demo-01](#demo-01) | How much of my plot can I build on? | answered, 132 words | answered, 71 words | 1 → 0 | 3 → 1 |
| [demo-02](#demo-02) | How much of my plot can I build on? | answered, 166 words | answered, 52 words | 1 → 0 | 2 → 1 |
| [demo-03](#demo-03) | Is construction allowed here? | answered, 118 words | answered, 36 words | 1 → 0 | 2 → 1 |
| [demo-04](#demo-04) | What are the rules for the active floodplain? | answered, 92 words | answered, 112 words | 1 → 0 | 2 → 1 |
| [demo-05](#demo-05) | What is the maximum ground coverage here? | answered, 114 words | answered, 37 words | 1 → 0 | 1 → 1 |
| [demo-06](#demo-06) | Can I build a house here? | answered, 77 words | answered, 65 words | 1 → 0 | 2 → 2 |
| [demo-07](#demo-07) | Is construction allowed here? | answered, 134 words | answered, 60 words | 1 → 0 | 4 → 2 |
| [demo-08](#demo-08) | Is construction allowed here? | abstained `outside_delhi` | abstained `outside_delhi` | 0 → 0 | 0 → 0 |
| [demo-09](#demo-09) | What is my property tax? | abstained `model_abstained` | abstained `model_abstained` | 0 → 0 | 0 → 0 |
| [demo-10](#demo-10) | Can a fuel station be built here? | answered, 50 words | answered, 31 words | 0 → 0 | 1 → 1 |
| [demo-11](#demo-11) | Can a fuel station be built in Zone O? | answered, 106 words | answered, 24 words | 1 → 0 | 2 → 1 |
| [demo-12](#demo-12) | Can I build a house here? | abstained `citation_check_failed` | abstained `model_abstained` | 1 → 0 | 0 → 0 |
| [demo-13](#demo-13) | How much of my plot can I build on? | answered, 215 words | answered, 50 words | 1 → 0 | 4 → 2 |
| [demo-14](#demo-14) | What is the permissible FAR for plotted housin… | answered, 182 words | answered, 45 words | 1 → 0 | 2 → 1 |
| [demo-15](#demo-15) | What is clause 4.2.1? | answered, 86 words | answered, 34 words | 0 → 0 | 1 → 1 |
| [demo-16](#demo-16) | How do I get my land included in a scheme? | abstained `citation_check_failed` | answered, 64 words | 1 → 0 | 0 → 2 |
| [agent-01](#agent-01) | What can be built near Hauz Khas metro? | answered, 188 words | answered, 97 words | — → 0 | 3 → 2 |
| [agent-02](#agent-02) | Can I build a house on the Yamuna floodplain n… | abstained `model_abstained` | answered, 31 words | — → 0 | 0 → 1 |
| [agent-03](#agent-03) | How much of my plot can I build on near Rajiv … | abstained `citation_check_failed` | answered, 24 words | — → 0 | 0 → 1 |
| [agent-04](#agent-04) | What are the ground coverage rules for a plot … | answered, 12 words | answered, 36 words | — → 0 | 1 → 1 |
| [agent-05](#agent-05) | Is construction allowed in the Ridge near Chha… | abstained `model_abstained` | answered, 39 words | — → 0 | 0 → 2 |

### Totals, over those cases only

The pass rate counts only the cases whose answer actually reached the citation check: a point outside Delhi never calls the model, and a case the model declined under rule 3 has nothing to check. It is split by mode because v1 could not count an agent retry, so an agent case is missing from its denominator and present in v2's. And it is over these cases only — `reports/citation_failures_v1.md` quotes 18% for v1 because it counts the 30 draft cases too.

| | v1 | v2 |
| --- | --- | --- |
| first-attempt pass rate, map mode | 14% (2 of 14) | 100% (13 of 13) |
| first-attempt pass rate, agent mode | — | 100% (5 of 5) |
| citation retries | 12 | 0 |
| `citation_check_failed` | 3 | 0 |
| should-abstain handled right | 3 of 4 | 3 of 4 |
| agent location within tolerance | 4 of 4 | 5 of 5 |
| tokens per case (mean) | 5,354 | 3,610 |
| answered / abstained | 14 / 7 | 18 / 3 |

**How to read the retry column.** In v1 the agent's retries could not be counted at all — the field was `llm_calls - 1`, which only works when a case makes one call, and an agent run's calls include its tool rounds. v2 records one problems list per rejected attempt (D-087), so the number is read rather than inferred and the agent rows carry one for the first time. A v1 agent row therefore shows `—` and not `0`.

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| answered a should-abstain question | **1** | [demo-07](#demo-07) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-01

**How much of my plot can I build on?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (beat 1)
- **Answered** in 71 words
- **Cost:** 2.0 s, 1 llm call(s), 2724 in / 198 out tokens, 0 rate-limit retr(y/ies)

> On a TOD Plot the maximum ground coverage permitted is 40% of the plot area, subject to fire and safety norms and any green‑space requirements [C3].
> For plots between 2,000 sqm and 10,000 sqm the minimum setbacks are 9 m front, 6 m rear and 6 m side, while for plots larger than 10,000 sqm the minimum setbacks increase to 15 m front, 12 m rear and 12 m side [C3].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2.4@p755:0`</sub>

### demo-02

**How much of my plot can I build on?**

- **Where:** P_HDC (28.659532, 77.006649)
- **Zones:** planning zone K-I; in high density corridor
- **Mode:** map   **Expected:** answer   (beat 2)
- **Answered** in 52 words
- **Cost:** 1.7 s, 1 llm call(s), 2185 in / 181 out tokens, 0 rate-limit retr(y/ies)

> For a plot in the K‑I High Density Corridor, the maximum permissible Floor Area Ratio (FAR) is 400 for residential, commercial or PSP uses, meaning you may construct floor space up to 400 times the final plot area, subject to the 4,000 sqm minimum final plot size and other policy conditions [C5]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.3.3@p758:0` | 4.3.3 | Master Plan for Delhi 2047 gazette notification (English) | 758-759 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.3@p757:0`, `MPD47_FAQ:Q1@p15:0`, `MPD47_GAZETTE_EN:1.7.1@p666:0`, `MPD47_GAZETTE_EN:4.3.1:0`, `MPD47_GAZETTE_EN:4.3.3@p758:0`, `MPD47_GAZETTE_EN:4.3.3@p760:0`</sub>

### demo-03

**Is construction allowed here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3)
- **Answered** in 36 words
- **Cost:** 2.2 s, 1 llm call(s), 2713 in / 160 out tokens, 0 rate-limit retr(y/ies)

> In Zone O, which is an active Yamuna floodplain, the Master Plan for Delhi 2047 designates it as a ‘no construction zone’ where only recreational uses are permitted and any unauthorised building must be removed [C2].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_FAQ:Q6@p3:0`, `MPD47_GAZETTE_EN:10.2.3:0`</sub>

### demo-04

**What are the rules for the active floodplain?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3, sharper)
- **Answered** in 112 words
- **Cost:** 17.0 s, 1 llm call(s), 2380 in / 234 out tokens, 0 rate-limit retr(y/ies)

> The active floodplain is designated as a ‘no construction zone’ where only recreational uses are permitted and any unauthorised construction, including religious structures, must be demolished by the concerned agency on priority [C1].
> Essential government utilities, socio‑cultural and recreational activities, public infrastructure development and conservation of floodplains are allowed only with the approval or NOC of the competent authority or statutory body [C1].
> Areas outside the active floodplain are subject to restricted development; existing authorised and planned constructions and essential government utilities may continue as per permissible norms and with approval or NOC, while further development is limited to socio‑cultural, recreational uses, essential utilities and public infrastructure with the same approvals [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:7@p9:0`, `NGT_OA572_GNCTD_REPORT:1@p27:0`, `DHC_YAMUNA_20240708:3:0`, `NGT_OA572_GNCTD_REPORT:13:0`, `NGT_OA572_GNCTD_REPORT:5@p8:0`</sub>

### demo-05

**What is the maximum ground coverage here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4)
- **Answered** in 37 words
- **Cost:** 16.1 s, 1 llm call(s), 2326 in / 195 out tokens, 0 rate-limit retr(y/ies)

> In the Low Density Area the maximum ground coverage depends on the use, with the gazette notification specifying 15% for residential, 40% for PSP/Institutional, 20% for recreational/socio‑cultural, 70% for godowns/warehouses and 30% for commercial/logistics hubs (C1) [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.4.3:0` | 4.4.3 | Master Plan for Delhi 2047 gazette notification (English) | 766-767 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_FAQ:Q3@p18:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_GAZETTE_EN:4.4.2:0`</sub>

### demo-06

**Can I build a house here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4, alternative)
- **Answered** in 65 words
- **Cost:** 16.0 s, 1 llm call(s), 2017 in / 166 out tokens, 0 rate-limit retr(y/ies)

> In Low Density Areas (LDA) residential development is permitted, with a maximum FAR of 10, ground coverage up to 15%, height up to 10 m and a minimum road width of 18 m for plots of at least 10,000 sq m [C1].
> The Master Plan states that housing in LDA shall continue to be low‑density residential development with limited dwelling units and public facilities [C4].

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
- **Answered** in 60 words
- **Cost:** 21.9 s, 1 llm call(s), 2709 in / 187 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question

> In the Ridge, which is identified as an environmentally sensitive or flood‑sink area, permanent construction is prohibited and only recreational or temporary uses are permitted subject to clearances [C6].
> Any development within a regional or archaeological park in the Ridge requires necessary clearances from all statutory bodies and is generally restricted to activities compatible with heritage and environmental objectives [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.2.3:0` | 10.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 847-849 |
| `MPD47_GAZETTE_EN:10.1@p843:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 843 |

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:9.2:0`, `DHC_YAMUNA_20240708:2:0`, `MPD47_FAQ:Q6@p3:0`, `MPD47_GAZETTE_EN:10.2.3:0`</sub>

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
- **Abstained:** `model_abstained: no information on property tax in provided sources`
- **Cost:** 14.2 s, 1 llm call(s), 1847 in / 40 out tokens, 0 rate-limit retr(y/ies)

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.5:0`</sub>

### demo-10

**Can a fuel station be built here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3b; was cut, fixed by D-086)
- **Answered** in 31 words
- **Cost:** 17.9 s, 1 llm call(s), 3043 in / 110 out tokens, 0 rate-limit retr(y/ies)

> According to the Master Plan, fuel stations may be permitted in all Use Zones except Recreational zones and Zone O, so a fuel station cannot be built in Zone O [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1.1 | Master Plan for Delhi 2047 gazette notification (English) | 854-855 |

<sub>Retrieved: `MPD47_GAZETTE_EN:11.1.1@p854:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`, `MPD47_GAZETTE_EN:Annexure 18:0`, `MPD47_GAZETTE_EN:5.1.7@p807:0`, `MPD47_GAZETTE_EN:3.6.1@p726:0`, `MPD47_GAZETTE_EN:11.2.1:0`</sub>

### demo-11

**Can a fuel station be built in Zone O?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3b, explicit wording)
- **Answered** in 24 words
- **Cost:** 24.9 s, 1 llm call(s), 3184 in / 100 out tokens, 0 rate-limit retr(y/ies)

> Fuel stations are not permitted in Zone O, as they may be permitted in all Use Zones except Recreational zones and Zone O [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1.1 | Master Plan for Delhi 2047 gazette notification (English) | 854-855 |

<sub>Retrieved: `MPD47_GAZETTE_EN:11.1.1@p854:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`, `MPD47_GAZETTE_EN:Annexure 18:0`, `MPD47_GAZETTE_EN:Annexure 19:0`, `MPD47_GAZETTE_EN:Annexure 20:0`, `MPD47_GAZETTE_EN:11.2.1:0`</sub>

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; D-086 left it weaker still)
- **Abstained:** `model_abstained: Insufficient information in provided sources to determine residential building permission in Ridge/regional park zone`
- **Cost:** 22.9 s, 1 llm call(s), 2894 in / 112 out tokens, 0 rate-limit retr(y/ies)

<sub>Retrieved: `MPD47_GAZETTE_EN:7.2.2@p815:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:9.2:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_GAZETTE_EN:p911:1`, `MPD47_GAZETTE_EN:5.1.3@p796:0`</sub>

### demo-13

**How much of my plot can I build on?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** either   (cut; wanders at ranks 2-3)
- **Answered** in 50 words
- **Cost:** 25.8 s, 1 llm call(s), 3286 in / 188 out tokens, 0 rate-limit retr(y/ies)

> The Master Plan Gazette notification permits a uniform permissible FAR of 200 for any plot size [C2]
> Ground coverage limits vary with plot size, ranging from 90% for plots up to 100 sqm down to 50% for plots above 750 sqm as detailed in the plotted‑housing development control norms [C6]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.6.5@p785:0` | 4.6.5 | Master Plan for Delhi 2047 gazette notification (English) | 785 |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:4.6.5@p785:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:4.6.4@p781:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`</sub>

### demo-14

**What is the permissible FAR for plotted housing?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (the demo's replacement)
- **Answered** in 45 words
- **Cost:** 25.1 s, 1 llm call(s), 3209 in / 149 out tokens, 0 rate-limit retr(y/ies)

> The permissible FAR for plotted housing varies with plot size, ranging from 350 for plots up to 100 sqm, 300 for plots between 100 sqm and 250 sqm, and 200 for plots larger than 250 sqm as specified in the Master Plan gazette notification [C2].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:9.1.3:0`, `MPD47_GAZETTE_EN:11.1.3@p859:0`, `MPD47_FAQ:Q6@p3:0`</sub>

### demo-15

**What is clause 4.2.1?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (in your pocket: BM25 earning its place)
- **Answered** in 34 words
- **Cost:** 14.8 s, 1 llm call(s), 1990 in / 129 out tokens, 0 rate-limit retr(y/ies)

> Clause 4.2.1 of the Master Plan for Delhi 2047 defines key terms for the TOD policy, including “TOD Zone”, “TOD Plot”, “Carpet Area”, and “Developer Entity (DE)”, each with specific criteria and meanings [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.1:0` | 4.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 750-751 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.2:0`</sub>

### demo-16

**How do I get my land included in a scheme?**

- **Where:** P_LP (28.676901, 77.027085)
- **Zones:** planning zone K-I; in land pooling area L
- **Mode:** map   **Expected:** answer   (in your pocket)
- **Answered** in 64 words
- **Cost:** 15.0 s, 1 llm call(s), 1747 in / 198 out tokens, 0 rate-limit retr(y/ies)

> Landowners must register and apply to the DDA according to the process specified in the Regulations, ensuring the parcel is within the notified land‑pooling area, free of encumbrances and that they have lawful ownership and physical possession [C1]
> Any size parcel can be brought into pooling provided it falls in the area notified by DDA or the Government under the Land Pooling Policy [C5]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.1.2:0` | 4.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 747-748 |
| `MPD47_FAQ:Q5@p8:0` | Q5 | FAQs on MPD-2047 | 8 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_FAQ:Q8@p9:0`, `MPD47_FAQ:Q13@p9:0`, `MPD47_FAQ:Q16@p10:0`, `MPD47_FAQ:Q5@p8:0`, `MPD47_FAQ:Q4@p8:0`</sub>

## b. agent mode, a place named in words

### agent-01

**What can be built near Hauz Khas metro?**

- **Where:** no pin — the agent found 28.54381, 77.20588
- **Zones:** planning zone F; in TOD zone
- **Mode:** agent   **Expected:** answer   (interchange, D-084)
- **Answered** in 97 words
- **Cost:** 52.2 s, 4 llm call(s), 6612 in / 395 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Hauz Khas metro"} -> found Hauz Khas (Delhi Metro interchange, 2 lines) at 28.54381, 77.20588
1. `get_zones` {"lat": 28.543813, "lon": 77.205876} -> planning zone F; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.543813, "lon": 77.205876, "query": "construction near metro"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.1:0, S2 MPD47_GAZETTE_EN:4.2@p750:0, S3 MPD47_GAZETTE_EN:4.2.4@p755:0...

> Near the Hauz Khas metro station, which lies within a TOD Zone, development is limited to Transit‑Oriented Development (TOD) projects on plots of at least 2000 sqm that meet the eligibility criteria set out in the policy [S1]
> These TOD projects must be compact mixed‑use developments that integrate land use with the transit node and comply with the sustainability and green‑building norms of the Master Plan, including water conservation, solar energy use and waste management [S3]
> Developers must also pay the prescribed TOD charges and any additional FAR charges beyond 400 as required by the DDA [S3]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.1:0` | 4.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 750-751 |
| `MPD47_GAZETTE_EN:4.2.4@p755:0` | 4.2.4 | Master Plan for Delhi 2047 gazette notification (English) | 755-756 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_FAQ:Q15@p13:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`</sub>

### agent-02

**Can I build a house on the Yamuna floodplain near ITO?**

- **Where:** no pin — the agent found 28.62819, 77.24104
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (the floodplain, named in words)
- **Answered** in 31 words
- **Cost:** 35.8 s, 4 llm call(s), 6460 in / 247 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 13 m from the expected place (tolerance 3000 m)

Tool trace:

1. `locate_place` {"query": "ITO"} -> found ITO (Delhi Metro) at 28.62819, 77.24104
1. `get_zones` {"lat": 28.628191, "lon": 77.241044} -> planning zone D; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.628191, "lon": 77.241044, "query": "Yamuna floodplain house construction"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.4@p754:0, S2 MPD47_GAZETTE_EN:3.1.2@p681:0, S3 DHC_YAMUNA_20240708:1:0...

> The active Yamuna floodplain is designated as a ‘no construction zone’ where only recreational uses are permitted, and any unauthorised building such as a house must not be constructed there [S2].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.4@p754:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:1:0`, `DHC_YAMUNA_20240708:3:0`, `DHC_YAMUNA_20240708:2:0`</sub>

### agent-03

**How much of my plot can I build on near Rajiv Chowk metro station?**

- **Where:** no pin — the agent found 28.63271, 77.21931
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, a plain station)
- **Answered** in 24 words
- **Cost:** 45.0 s, 4 llm call(s), 6765 in / 227 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 1 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Rajiv Chowk metro station"} -> found Rajiv Chowk (Delhi Metro) at 28.63271, 77.21931
1. `get_zones` {"lat": 28.632706, "lon": 77.219312} -> planning zone D; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.632706, "lon": 77.219312, "query": "maximum ground coverage plot"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.3@p753:0, S2 MPD47_FAQ:Q13@p13:0, S3 MPD47_GAZETTE_EN:4.2.1:0...

> For a TOD Plot near Rajiv Chowk metro station, the Master Plan permits a maximum ground coverage of 40% of the plot area [S1]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`</sub>

### agent-04

**What are the ground coverage rules for a plot near Dwarka Sector 21 metro station?**

- **Where:** no pin — the agent found 28.55192, 77.05856
- **Zones:** planning zone K-II; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, the D-049 query)
- **Answered** in 36 words
- **Cost:** 54.3 s, 4 llm call(s), 6948 in / 264 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 5 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Dwarka Sector 21 metro station"} -> found Dwarka Sector 21, Dwarka Sector 21 Underpass, Najafgarh, Delhi, South West Delhi, Delhi, 110061, India at 28.55192, 77.05856
1. `get_zones` {"lat": 28.5519218, "lon": 77.0585605} -> planning zone K-II; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.5519218, "lon": 77.0585605, "query": "ground coverage plot"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.3@p753:0, S2 MPD47_GAZETTE_EN:4.2.1:0, S3 MPD47_GAZETTE_EN:4.2.3@p751:0...

> For a TOD plot near Dwarka Sector 21 metro station, the maximum ground coverage permitted is 40% of the plot area, with possible relaxations allowed by the TOD Committee under fire, safety and green‑space requirements [S1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2@p750:0`</sub>

### agent-05

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin — the agent found 28.50672, 77.17500
- **Zones:** planning zone J; in none of the six policy zones
- **Mode:** agent   **Expected:** answer   (a Ridge question with no pin)
- **Answered** in 39 words
- **Cost:** 36.6 s, 4 llm call(s), 6976 in / 313 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 4000 m)

Tool trace:

1. `locate_place` {"query": "Chhatarpur"} -> found Chhatarpur (Delhi Metro) at 28.50672, 77.17500
1. `get_zones` {"lat": 28.506724, "lon": 77.175002} -> planning zone J; in none of the six policy zones
1. `search_clauses` {"k": 5, "lat": 28.506724, "lon": 77.175002, "query": "Ridge construction allowed"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:3.1.2@p681:0, S2 MPD47_GAZETTE_EN:10.1@p843:0, S3 MPD47_GAZETTE_EN:10.1@p842:0...

> The Ridge is designated as a Regional Park under the Master Plan for Delhi 2047 [S3]
> Recreational use is permitted in all use zones, and construction is allowed only for recreational purposes such as parks and sports centres [S4]

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 842 |
| `MPD47_GAZETTE_EN:10.2.3:0` | 10.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 847-849 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:10.1@p843:0`, `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:10.2.3:0`, `MPD47_GAZETTE_EN:5.1.6@p800:0`</sub>

