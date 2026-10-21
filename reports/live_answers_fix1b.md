# Fix round 1, after the revert (fix1b)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-21T17:22:00+00:00 / 2026-10-21T17:23:11+00:00 |
| Cases done | **3 of 3** |
| Answered | **1** |
| Abstained | **2** |
| Failed outright | 0 |
| Citation retries | 0 |
| Latency p50 / p95 | 30.7 s / 35.3 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 18,092 |
| Tokens used, last run | 18,092 of a 25,000 per-run budget |
| LLM calls, all runs | 8 |
| LLM calls, last run | 8 of a 120 per-run cap |
| Runs so far | 1 |
| 429s / rate-limit waits | 0 / 0 |
| Gap between calls | 2.5 s |
| State | **finished** |

Abstentions by reason:

| reason | n |
| --- | --- |
| `model_abstained` | 1 |
| `unsupported_claims` | 1 |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '965', 'x-ratelimit-reset-requests': '50m24s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '181', 'x-ratelimit-reset-tokens': '58.642s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

## v1 against v2 against v3

The 3 case(s) every run recorded, read off the state files. The same questions at the same points with the same budget each time; what changed between v2 and v3 is the named-zone instruction reverted (D-107); everything else from fix round 1 kept. **Still nobody has read these answers.**

| case | question | v1 | v2 | v3 | retries | citations | note? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [demo-12](#demo-12) | Can I build a house here? | abstained `model_abstained` | answered, 53 words | answered, 55 words | 0 → 0 → 0 | 0 → 2 → 2 | no |
| [agent-02](#agent-02) | Can I build a house on the Yamuna floodpla… | abstained `model_abstained` | abstained `model_abstained` | abstained `model_abstained` | 0 → 0 → 0 | 0 → 0 → 0 | yes |
| [probe-01](#probe-01) | Can I build on the Yamuna floodplain here? | answered, 23 words | abstained `unsupported_claims` | abstained `unsupported_claims` | 0 → 0 → 0 | 1 → 0 → 0 | yes |

### Totals, over those 3 cases only

The pass rate counts only the cases whose answer actually reached the citation check: a point outside Delhi never calls the model, and a case the model declined under rule 3 has nothing to check. It is split by mode because v1 could not count an agent retry, so an agent case is missing from its denominator and present in later ones. A **dash** means the run predates the field, not that the number is zero.

| | v1 | v2 | v3 |
| --- | --- | --- | --- |
| answered / abstained | 1 / 2 | 1 / 2 | 1 / 2 |
| first-attempt pass rate, map mode | 100% (1 of 1) | 100% (2 of 2) | 100% (2 of 2) |
| first-attempt pass rate, agent mode | — | — | — |
| citation retries | 0 | 0 | 0 |
| `citation_check_failed` | 0 | 0 | 0 |
| should-abstain handled right | 1 of 1 | 0 of 1 | 0 of 1 |
| agent location within tolerance | 1 of 1 | 1 of 1 | 1 of 1 |
| median words, answered cases | 23 | 53 | 55 |
| median citations, answered cases | 1 | 2 | 2 |
| location notes shown | 2 | 2 | 2 |
| claim check ran on | 1 | 2 | 2 |
| sentences `supported` | 1 | 3 | 3 |
| sentences `partly` | 0 | 1 | 1 |
| sentences `unsupported` | 0 | 1 | 1 |
| cases `enforce` would change | none | [probe-01](#probe-01) | [probe-01](#probe-01) |
| … of those, would abstain | none | [probe-01](#probe-01) | [probe-01](#probe-01) |
| tokens per case (mean) | 4,560 | 6,281 | 6,031 |
| … of which, the answer | 4,196 | 5,033 | 4,902 |
| … of which, the claim check | 363 | 1,249 | 1,129 |

**How to read the retry column.** In v1 the agent's retries could not be counted at all — the field was `llm_calls - 1`, which only works when a case makes one call, and an agent run's calls include its tool rounds. From v2 one problems list is recorded per rejected attempt (D-087), so the number is read rather than inferred. A v1 agent row therefore shows a dash and not `0`.

**What the claim-check rows are and are not.** `SUPPORT_CHECK=shadow`, so every verdict in this run was recorded and **none of them changed an answer** (D-096). The `enforce` rows say what the other mode would have done to these same answers, which is the question a reader has to settle before that mode is turned on. They are a model's judgement of a model, so they are evidence and not a verdict.

**`demo-07`, explicitly.** It is the should-abstain beat at P_RIDGE that answered in v1 (134 words) and again in v2 (60 words), citing clauses that do not say it, and it is the case the claim check exists for. In this run `enforce` would **not** have changed it, which is the more interesting outcome of the two: the structural check passed it, the semantic check passed it, and a reader still has to decide whether the answer is right. The cases `enforce` would have changed are [probe-01](#probe-01).

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| answered a should-abstain question | **1** | [demo-12](#demo-12) |
| abstained on an answerable question | **1** | [agent-02](#agent-02) |
| the claim check called 1 sentence(s) unsupported | **1** | [probe-01](#probe-01) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; D-086 left it weaker still)
- **Answered** in 55 words
- **Cost:** 4.0 s, 1 llm call(s), 4346 in / 464 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question

> The Ridge, which includes the Northern, Central, Nanakpura, South‑Central and Southern Ridge, is designated as a Regional Park under the Master Plan for Delhi 2047 [C1].
> The Ridge is a reserved forest covering about 7,784 ha, constituting nearly 6 % of the NCT of Delhi, and is not listed under any residential use zone [C4].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 842 |
| `MPD47_GAZETTE_EN:1.6.2@p657:0` | 1.6.2 | Master Plan for Delhi 2047 gazette notification (English) | 657 |

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:p911:1`, `MPD47_GAZETTE_EN:5.1.3@p796:0`</sub>

## b. agent mode, a place named in words

### agent-02

**Can I build a house on the Yamuna floodplain near ITO?**

- **Where:** no pin — the agent found 28.62819, 77.24104
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (the floodplain, named in words)
- **Abstained:** `model_abstained: No applicable clause found for construction on Yamuna floodplain near ITO`
- **Cost:** 30.7 s, 4 llm call(s), 7605 in / 230 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 13 m from the expected place (tolerance 3000 m)
- **Suspected:** abstained on an answerable question (model_abstained: No applicable clause found for construction on Yamuna floodplain near ITO)

Tool trace:

1. `locate_place` {"query": "ITO"} -> found ITO (Delhi Metro) at 28.62819, 77.24104
1. `get_zones` {"lat": 28.628191, "lon": 77.241044} -> planning zone D; in TOD zone — This point is not inside Zone O (Yamuna floodplain) on DDA's map; the nearest Zone O boundary is about 600 m away.
1. `search_clauses` {"k": 5, "lat": 28.628191, "lon": 77.241044, "query": "Yamuna floodplain construction house"} -> 5 clause(s): S1 MPD47_GAZETTE_EN:4.2.2:0, S2 MPD47_GAZETTE_EN:4.2.4@p755:0, S3 MPD47_GAZETTE_EN:4.2.5:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p754:0`</sub>

## d. probes for the location note

### probe-01

**Can I build on the Yamuna floodplain here?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** either   (probe: names Zone O at a point get_zones puts in a TOD zone, 2.7 km away (D-094))
- **Abstained:** `unsupported_claims`
- **Cost:** 35.3 s, 1 llm call(s), 4821 in / 626 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** the claim check called 1 sentence(s) unsupported

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p754:0`, `MPD47_GAZETTE_EN:p642:0`</sub>

