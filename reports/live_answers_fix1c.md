# Fix round 1, control: all of task 5 removed (fix1c)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-21T17:24:14+00:00 / 2026-10-21T17:24:20+00:00 |
| Cases done | **1 of 1** |
| Answered | **1** |
| Abstained | **0** |
| Failed outright | 0 |
| Citation retries | 0 |
| Latency p50 / p95 | 4.7 s / 4.7 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 6,239 |
| Tokens used, last run | 6,239 of a 10,000 per-run budget |
| LLM calls, all runs | 2 |
| LLM calls, last run | 2 of a 120 per-run cap |
| Runs so far | 1 |
| 429s / rate-limit waits | 0 / 0 |
| Gap between calls | 2.5 s |
| State | **finished** |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '963', 'x-ratelimit-reset-requests': '53m16.799s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '2029', 'x-ratelimit-reset-tokens': '44.782s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| answered a should-abstain question | **1** | [demo-12](#demo-12) |
| the claim check called 1 sentence(s) unsupported | **1** | [demo-12](#demo-12) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; D-086 left it weaker still)
- **Answered** in 50 words
- **Cost:** 4.7 s, 1 llm call(s), 5637 in / 602 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** answered a should-abstain question; the claim check called 1 sentence(s) unsupported

> The Ridge is designated as a Regional Park, which is a type of recreational land use (P1) under the Master Plan for Delhi 2047 [C1].
> Regional Parks are listed only under the Recreational land‑use category and are not included in any residential use zones such as RD or RF [C6].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 842 |
| `MPD47_GAZETTE_EN:5.1.3@p796:0` | 5.1.3 | Master Plan for Delhi 2047 gazette notification (English) | 796-797 |

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:Annexure 22@p984:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:p911:1`, `MPD47_GAZETTE_EN:5.1.3@p796:0`</sub>

