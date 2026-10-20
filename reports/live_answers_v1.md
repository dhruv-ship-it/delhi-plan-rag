# First real-model run (v1)

> **Nobody has read these answers yet.** This file is a recording, not a review.
> It was written by `scripts/live_run.py`, which changes no prompt, no threshold
> and no retrieval setting, and nothing in it reacts to what the model said. The
> "suspected problems" below are mechanical rules, not judgements.

| | |
| --- | --- |
| Provider / model | `groq` / `openai/gpt-oss-120b` |
| Started / last updated | 2026-10-19T20:02:14+00:00 / 2026-10-20T04:19:22+00:00 |
| Cases done | **37 of 51** |
| Answered | **21** |
| Abstained | **16** |
| Failed outright | 0 |
| Citation retries | 18 |
| Latency p50 / p95 | 38.1 s / 54.0 s — **wall clock, not model speed**; see below |
| Tokens used, all runs | 197,200 |
| Tokens used, last run | 44,490 of a 150,000 per-run budget |
| LLM calls, all runs | 80 |
| LLM calls, last run | 19 of a 120 per-run cap |
| Runs so far | 2 |
| 429s / rate-limit waits | 0 / 0 |
| Gap between calls | 2.5 s |
| State | **stopped_by_hand** |

Abstentions by reason:

| reason | n |
| --- | --- |
| `citation_check_failed` | 10 |
| `model_abstained` | 5 |
| `outside_delhi` | 1 |

Last rate-limit headers seen: `{'x-ratelimit-limit-requests': '1000', 'x-ratelimit-remaining-requests': '981', 'x-ratelimit-reset-requests': '27m21.6s', 'x-ratelimit-limit-tokens': '8000', 'x-ratelimit-remaining-tokens': '60', 'x-ratelimit-reset-tokens': '59.55s'}`

**What the latency figure is and is not.** It is wall clock around the whole case, measured by `app/answer.py` itself, so it includes the enforced 2.5 s gap between calls, any wait for a 429, and the time Groq's free tier spends holding a request back when the 8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, so from the second case onwards that bucket — not the model — sets the pace. The one figure here that is close to model latency is the **first** case of a run, against a full bucket. Nothing in this file should be quoted as a latency for ZoneWise.

**This run was stopped by hand, not on an error.** Every case below ran to completion; the rest were never started. Continue with `uv run python scripts\live_run.py --resume` — the next day if the daily token limit is what ran out.

## Suspected problems

Each row is a mechanical rule, not a verdict. The examples link to the full case
below, which is where the judgement has to happen.

| suspected problem | n | examples |
| --- | --- | --- |
| needed a citation retry | **18** | [demo-01](#demo-01), [demo-02](#demo-02), [demo-03](#demo-03), [demo-04](#demo-04) +14 more |
| abstained on an answerable question | **13** | [demo-16](#demo-16), [agent-02](#agent-02), [agent-03](#agent-03), [agent-05](#agent-05) +9 more |
| the citation check failed twice | **10** | [demo-12](#demo-12), [demo-16](#demo-16), [agent-03](#agent-03), [draft-loc-07](#draft-loc-07) +6 more |
| the expected clause was retrieved but not cited | **7** | [draft-loc-15](#draft-loc-15), [draft-loc-07](#draft-loc-07), [draft-loc-06](#draft-loc-06), [draft-gen-18](#draft-gen-18) +3 more |
| the agent answered without ever establishing a point | **2** | [draft-gen-15](#draft-gen-15), [draft-gen-17](#draft-gen-17) |
| answered a should-abstain question | **1** | [demo-07](#demo-07) |
| very long answer | **1** | [demo-13](#demo-13) |
| cited only the FAQ although a gazette clause was retrieved | **1** | [draft-loc-15](#draft-loc-15) |
| answered without citing any expected clause | **1** | [draft-loc-19](#draft-loc-19) |

---

## Every case, in full

## a. docs/DEMO.md, map mode

### demo-01

**How much of my plot can I build on?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (beat 1)
- **Answered** in 132 words
- **Cost:** 3.6 s, 2 llm call(s), 5409 in / 472 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> The law permits a maximum ground coverage of 40 percent on a TOD Plot [C3].  
> For a plot of 2,000 sqm (the minimum size for a TOD Plot) this means you may cover up to 800 sqm of the site with building footprint, subject to the required front, rear and side setbacks (9 m front, 6 m rear and sides for plots up to 10,000 sqm) [C3].  
> The total floor‑area ratio (FAR) that can be built is not fixed in the sources; it is determined by the TOD Committee based on the plot’s location, road width and other policy provisions [C2][C5].  
> Thus, you can build on up to 40 % of the plot area, but the overall floor area you may achieve depends on the FAR awarded by the TOD Committee [C3][C2][C5].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |
| `MPD47_GAZETTE_EN:4.2.3@p751:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 751-752 |
| `MPD47_GAZETTE_EN:4.2.3@p752:1` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 752-753 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2.4@p755:0`</sub>

### demo-02

**How much of my plot can I build on?**

- **Where:** P_HDC (28.659532, 77.006649)
- **Zones:** planning zone K-I; in high density corridor
- **Mode:** map   **Expected:** answer   (beat 2)
- **Answered** in 166 words
- **Cost:** 37.5 s, 2 llm call(s), 4384 in / 660 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> - The HDC policy applies only to “Final HDC Plots” that are at least 4,000 sqm after surrendering 50 % of an “Original Plot” of 8,000 sqm [C5].  
> - For a qualifying HDC Plot, the maximum permissible Floor‑Area Ratio (FAR) is **400** for residential, commercial or PSP uses [C5].  
> - This FAR allows a total built‑up area equal to 400 times the final plot area (e.g., a 4,000 sqm plot could support up to 1,600,000 sqm of floor area) [C5].  
> - At least **20 %** of the permissible FAR must be used for affordable housing with units under 60 sqm carpet area [C5].  
> - The plot must be accessible from a road with a minimum Right‑of‑Way of 18 m [C5][C6].  
> - Ground‑coverage relaxations may be granted by the TOD Committee if the FAR cannot be achieved due to site constraints [C5].  
> - These provisions are set out in the Master Plan for Delhi 2047 gazette notification; official DDA documents should be consulted for exact calculations [C5].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.3.3@p758:0` | 4.3.3 | Master Plan for Delhi 2047 gazette notification (English) | 758-759 |
| `MPD47_GAZETTE_EN:4.3.3@p760:0` | 4.3.3 | Master Plan for Delhi 2047 gazette notification (English) | 760 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.3@p757:0`, `MPD47_FAQ:Q1@p15:0`, `MPD47_GAZETTE_EN:1.7.1@p666:0`, `MPD47_GAZETTE_EN:4.3.1:0`, `MPD47_GAZETTE_EN:4.3.3@p758:0`, `MPD47_GAZETTE_EN:4.3.3@p760:0`</sub>

### demo-03

**Is construction allowed here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3)
- **Answered** in 118 words
- **Cost:** 52.3 s, 2 llm call(s), 6287 in / 414 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> The Master Plan for Delhi 2047 states that the active Yamuna floodplain is a “no‑construction zone” and only recreational uses, essential government utilities, socio‑cultural activities or public‑infrastructure projects may be permitted with approval/NOC of the competent authority [C1]. It further requires that all unauthorised construction, including houses, dwellings or religious structures, be demolished on priority [C1]. The Delhi High Court has described building or dwelling houses in the floodplain as illegal and dangerous, especially during monsoon seasons [C2]. Thus, ordinary construction is not permitted in Zone O; only the narrowly defined uses listed in the gazette notification may be allowed with proper approval [C1]. Official DDA documents should be checked for the exact list of permissible activities [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `DHC_YAMUNA_20240708:2:0` | 2 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `DHC_YAMUNA_20240708:2:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:p1:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`</sub>

### demo-04

**What are the rules for the active floodplain?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (beat 3, sharper)
- **Answered** in 92 words
- **Cost:** 45.0 s, 2 llm call(s), 5842 in / 339 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> Active floodplain is a “no‑construction zone” and only recreational uses are permitted [C1]. All unauthorised construction, including religious structures, must be demolished on priority by the concerned agency [C1]. Essential government utilities, socio‑cultural and recreational activities, public‑infrastructure development and flood‑plain conservation are allowed only with approval or NOC of the competent statutory authority [C1]. Any further development in the zone is restricted to the same limited uses and requires statutory permission [C1]. The Tribunal has also directed that the floodplain corresponding to a 1‑in‑100‑year flood must be demarcated on the ground [C6].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `NGT_OA572_GNCTD_REPORT:4@p30:0` | 4 | GNCTD report to NGT on Yamuna floodplain demarcation (OA 572 of 2024) | 30 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:1@p29:0`, `NGT_OA572_GNCTD_REPORT:p1:0`, `NGT_OA572_GNCTD_REPORT:4@p30:0`</sub>

### demo-05

**What is the maximum ground coverage here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4)
- **Answered** in 114 words
- **Cost:** 35.9 s, 2 llm call(s), 4598 in / 515 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> The maximum ground‑coverage in a Low‑Density Area (LDA) varies by the permitted use‑premise [C1].  
> For Residential (farmhouse) plots the limit is **15 %** of the plot area [C1].  
> For PSP/Institutional uses such as schools, hospitals and universities the limit is **40 %** [C1].  
> For Recreational / Socio‑Cultural uses like parks and exhibition centres the limit is **20 %** [C1].  
> For Godowns / Warehouses the limit is **70 %** [C1].  
> For Commercial / Logistics Hubs the limit is **30 %** [C1].  
> These percentages represent the maximum ground‑coverage allowed under the Master Plan for Delhi 2047 for each activity in the LDA [C1].  
> Official DDA documents should be consulted for any site‑specific variations or updates [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.4.3:0` | 4.4.3 | Master Plan for Delhi 2047 gazette notification (English) | 766-767 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.4.3:0`, `MPD47_FAQ:Q3@p18:0`, `MPD47_GAZETTE_EN:4.4@p764:0`, `MPD47_FAQ:Q1@p18:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_GAZETTE_EN:4.4.2:0`</sub>

### demo-06

**Can I build a house here?**

- **Where:** P_LDA (28.608034, 76.903849)
- **Zones:** planning zone L; in low density area
- **Mode:** map   **Expected:** answer   (beat 4, alternative)
- **Answered** in 77 words
- **Cost:** 32.9 s, 2 llm call(s), 3898 in / 356 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> A house (one dwelling unit) is permitted on a plot in a Low‑Density Area, provided the plot is at least 10,000 sq m and the building follows the residential norms – FAR 10, ground coverage up to 15 %, height not exceeding 10 m and a minimum road‑width setback of 18 m from the plot edge [C1]. The Master Plan also states that housing in LDA shall remain low‑density with limited dwelling units and public facilities [C4].

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
- **Answered** in 134 words
- **Cost:** 43.1 s, 2 llm call(s), 5735 in / 510 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** answered a should-abstain question; needed a citation retry

> Construction in a Ridge that falls within a Regional Park is heavily restricted [C1]. The Ridge is designated as part of the Regional Park and any development on forest land inside a Regional Park must follow the Forest Department, GNCTD procedures [C4]. Built‑up structures in a park may not exceed 1 % of the park area or 10 000 sqm, whichever is less, which limits construction to a very small footprint [C4]. Buffers along natural drains and water bodies must remain active green areas with no construction or parking allowed, further constraining any new works [C3]. Thus, only minimal, forest‑department‑approved activities that respect the 1 % built‑up ceiling and buffer rules are permissible; most new construction would be prohibited [C1][C4][C3]. Official DDA and Forest Department approvals should be confirmed before any work proceeds [C5].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:10.1@p842:0` | 10.1 | Master Plan for Delhi 2047 gazette notification (English) | 842 |
| `MPD47_GAZETTE_EN:10.2.1@p846:0` | 10.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 846 |
| `MPD47_GAZETTE_EN:3.1.2@p683:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 683-684 |
| `MPD47_GAZETTE_EN:1.6.2@p657:0` | 1.6.2 | Master Plan for Delhi 2047 gazette notification (English) | 657 |

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `MPD47_GAZETTE_EN:3.1.2@p683:0`, `MPD47_GAZETTE_EN:10.2.1@p846:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:Annexure 3:0`</sub>

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
- **Abstained:** `model_abstained: The provided sources do not contain information on property tax.`
- **Cost:** 11.7 s, 1 llm call(s), 1659 in / 38 out tokens, 0 rate-limit retr(y/ies)

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.3@p752:0`, `MPD47_GAZETTE_EN:4.2.5:0`</sub>

### demo-10

**Can a fuel station be built here?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** either   (cut from the demo; D-083)
- **Answered** in 50 words
- **Cost:** 20.9 s, 1 llm call(s), 3226 in / 149 out tokens, 0 rate-limit retr(y/ies)

> A fuel station cannot be built in Zone O because the zone is part of the active Yamuna floodplain, which the Master Plan for Delhi 2047 declares a “no‑construction zone” where only recreational, essential government utilities, socio‑cultural and public‑infrastructure uses are permitted, and all unauthorised constructions must be demolished [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:3@p18:0`, `NGT_OA572_GNCTD_REPORT:3@p24:0`</sub>

### demo-11

**Can a fuel station be built in Zone O?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** either   (cut; the explicit wording)
- **Answered** in 106 words
- **Cost:** 55.1 s, 2 llm call(s), 7252 in / 424 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> A fuel station cannot be built in Zone O because Zone O is part of the “active floodplain,” which the Master Plan declares a ‘no‑construction zone’ and permits only recreational or essential public‑utility uses; all unauthorised construction must be demolished [C2].  
> 
> The reports on demarcation note that Zone O has been identified on maps but ground‑truthing and final boundary fixing have not yet been completed, confirming that it is still treated as flood‑plain land subject to the same restriction [C5].  
> 
> Therefore, under the current Delhi Master Plan, a fuel station is not allowed in Zone O; official DDA documents should be consulted for any updates [C2].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `NGT_OA572_GNCTD_REPORT:5@p8:0` | 5 | GNCTD report to NGT on Yamuna floodplain demarcation (OA 572 of 2024) | 8-9 |

<sub>Retrieved: `NGT_OA572_GNCTD_REPORT:3@p25:1`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:5@p8:0`, `MPD47_GAZETTE_EN:11.1.1@p855:0`</sub>

### demo-12

**Can I build a house here?**

- **Where:** P_RIDGE (28.427902, 77.207749)
- **Zones:** planning zone J; in Ridge / regional park
- **Mode:** map   **Expected:** abstain   (cut; works but a weaker beat 5)
- **Abstained:** `citation_check_failed`
- **Cost:** 54.0 s, 2 llm call(s), 6961 in / 416 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** the citation check failed twice; needed a citation retry

<sub>Retrieved: `MPD47_GAZETTE_EN:10.1@p842:0`, `MPD47_GAZETTE_EN:1.6.2@p657:0`, `MPD47_GAZETTE_EN:Annexure 1@p937:0`, `MPD47_GAZETTE_EN:10.2.1@p846:0`, `MPD47_GAZETTE_EN:Annexure 1@p919:0`, `MPD47_GAZETTE_EN:Annexure 3:0`</sub>

### demo-13

**How much of my plot can I build on?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** either   (cut; wanders at ranks 2-3)
- **Answered** in 215 words
- **Cost:** 53.6 s, 2 llm call(s), 6641 in / 762 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry; very long answer (215 words, rule 7 asks for <200)

> The amount you can build depends on the size of your plot [C6].  
> For plotted housing the Master Plan specifies the maximum ground‑coverage for each plot‑size category: up to 50 sqm – 90 %; 50‑100 sqm – 90 %; 100‑250 sqm – 75 %; 250‑750 sqm – 75 %; 750‑1 000 sqm – 50 %; and 50 % for plots larger than 1 000 sqm [C6].  
> The corresponding maximum FAR also varies: 350 for plots up to 250 sqm, 225 for 250‑750 sqm, and 200 for plots above 750 sqm [C6].  
> Minimum setbacks are prescribed by plot size: no front setback for plots up to 100 sqm; 3 m front for 100‑250 sqm; 3 m front and rear for 250‑500 sqm; 6 m front for 500‑2 000 sqm; 9 m front for 2 000‑10 000 sqm; and 15 m front for plots over 10 000 sqm, with side and rear setbacks as shown in the table [C5].  
> If a plot is larger than 100 sqm, a stilt may be required for parking, but the stilt area is not counted in FAR and only adds to building height [C4].  
> The minimum plot area for any residential development is 32 sqm [C6].  
> Official DDA documents should be consulted to confirm any additional conditions that may apply [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |
| `MPD47_GAZETTE_EN:4.6.4@p781:0` | 4.6.4 | Master Plan for Delhi 2047 gazette notification (English) | 781-782 |
| `MPD47_GAZETTE_EN:7.2.1@p814:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 814-815 |
| `MPD47_FAQ:Q1@p5:0` | Q1 | FAQs on MPD-2047 | 5-6 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:4.6.5@p785:0`, `MPD47_FAQ:Q4@p20:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:4.6.4@p781:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`</sub>

### demo-14

**What is the permissible FAR for plotted housing?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (the demo's replacement)
- **Answered** in 182 words
- **Cost:** 49.7 s, 2 llm call(s), 6472 in / 756 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** needed a citation retry

> The Master Plan Gazette lists the maximum FAR for plotted housing by plot‑size category [C2].  
> For plots up to 50 sqm the permissible FAR is 350 [C2].  
> For plots above 50 up to 100 sqm the permissible FAR remains 350 [C2].  
> For plots above 100 up to 250 sqm the permissible FAR is 300 [C2].  
> For plots above 250 up to 750 sqm the permissible FAR is 225 [C2].  
> For plots above 750 up to 1,000 sqm the permissible FAR is 200 [C2].  
> For plots above 1,000 up to 1,500 sqm the permissible FAR is 200 [C2].  
> For plots above 1,500 up to 2,250 sqm the permissible FAR is 200 [C2].  
> For plots above 2,250 up to 3,000 sqm the permissible FAR is 200 [C2].  
> For plots above 3,000 up to 3,750 sqm the permissible FAR is 200 [C2].  
> For plots above 3,750 sqm the permissible FAR is 200 [C2].  
> The FAQ summary also notes that plotted housing FAR ranges from 200 to 350 depending on plot size [C1].  
> Official DDA documents should be consulted for any updates or site‑specific conditions [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.1@p813:0` | 7.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 813-814 |
| `MPD47_FAQ:Q1@p5:0` | Q1 | FAQs on MPD-2047 | 5-6 |

<sub>Retrieved: `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:9.1.3:0`, `MPD47_GAZETTE_EN:11.1.3@p859:0`, `MPD47_FAQ:Q6@p3:0`</sub>

### demo-15

**What is clause 4.2.1?**

- **Where:** P_TOD (28.6328, 77.2197)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (in your pocket: BM25 earning its place)
- **Answered** in 86 words
- **Cost:** 15.9 s, 1 llm call(s), 1802 in / 169 out tokens, 0 rate-limit retr(y/ies)

> Clause 4.2.1 of the Master Plan for Delhi 2047 defines key terms used in the TOD policy, including “TOD Zone” (the 500 m corridor on either side of metro or other mass‑transit corridors and a 500 m radius around transit stations), “TOD Plot” (a plot of at least 2,000 sqm meeting the policy’s eligibility criteria), “Carpet Area” (the net usable floor area of an apartment as per the RERA Act), and “Developer Entity (DE)” (the land/property owners who jointly plan and develop a TOD Plot) [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.1:0` | 4.2.1 | Master Plan for Delhi 2047 gazette notification (English) | 750-751 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.2:0`</sub>

### demo-16

**How do I get my land included in a scheme?**

- **Where:** P_LP (28.676901, 77.027085)
- **Zones:** planning zone K-I; in land pooling area L
- **Mode:** map   **Expected:** answer   (in your pocket)
- **Abstained:** `citation_check_failed`
- **Cost:** 26.4 s, 2 llm call(s), 3529 in / 659 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; needed a citation retry

<sub>Retrieved: `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_FAQ:Q8@p9:0`, `MPD47_FAQ:Q13@p9:0`, `MPD47_FAQ:Q16@p10:0`, `MPD47_FAQ:Q5@p8:0`, `MPD47_FAQ:Q4@p8:0`</sub>

## b. agent mode, a place named in words

### agent-01

**What can be built near Hauz Khas metro?**

- **Where:** no pin — the agent found 28.54381, 77.20588
- **Zones:** planning zone F; in TOD zone
- **Mode:** agent   **Expected:** answer   (interchange, D-084)
- **Answered** in 188 words
- **Cost:** 63.8 s, 5 llm call(s), 8797 in / 982 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 3 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Hauz Khas metro"} -> found Hauz Khas (Delhi Metro interchange, 2 lines) at 28.54381, 77.20588
1. `get_zones` {"lat": 28.543813, "lon": 77.205876} -> planning zone F; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.543813, "lon": 77.205876, "query": "building allowed TOD zone F"} -> 5 clause(s): MPD47_GAZETTE_EN:4.2.4@p755:0, MPD47_GAZETTE_EN:4.2.2:0, MPD47_GAZETTE_EN:4.2.1:0...

> Near the Hauz Khas metro interchange, which lies in a TOD Zone (Zone F), a Transit‑Oriented Development (TOD) plot can be used for compact mixed‑use projects as defined in the TOD policy [MPD47_GAZETTE_EN:4.2@p750:0]. The policy permits a maximum ground coverage of 40 % on a TOD plot [MPD47_GAZETTE_EN:4.2.3@p753:0]. For plot sizes from 2 000 sqm to 10 000 sqm the required setbacks are a minimum front setback of 9 m, rear setback of 6 m and side setbacks of 6 m; for plots larger than 10 000 sqm the front setback must be at least 15 m, rear 12 m and side 12 m [MPD47_GAZETTE_EN:4.2.3@p753:0]. At least 10 % of the TOD project area must be retained as green space, with a possible 2 % relaxation for private land [MPD47_GAZETTE_EN:4.2.3@p753:0]. Parking must provide one equivalent car space per 100 sqm of FAR, and a minimum of 30 % of all parking must be public parking for schemes larger than 1 ha [MPD47_GAZETTE_EN:4.2.3@p753:0]. All TOD projects must also comply with the mandatory sustainability and green‑building norms, including water‑conservation, zero‑discharge, dual‑piping, solar energy utilization, energy efficiency and waste management [MPD47_GAZETTE_EN:4.2.4@p755:0].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2@p750:0` | 4.2 | Master Plan for Delhi 2047 gazette notification (English) | 750 |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |
| `MPD47_GAZETTE_EN:4.2.4@p755:0` | 4.2.4 | Master Plan for Delhi 2047 gazette notification (English) | 755-756 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.3@p753:0`</sub>

### agent-02

**Can I build a house on the Yamuna floodplain near ITO?**

- **Where:** no pin — the agent found 28.62819, 77.24104
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (the floodplain, named in words)
- **Abstained:** `model_abstained: No relevant clauses on house construction in the Yamuna floodplain were found.`
- **Cost:** 33.6 s, 4 llm call(s), 5479 in / 192 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 13 m from the expected place (tolerance 3000 m)
- **Suspected:** abstained on an answerable question (model_abstained: No relevant clauses on house construction in the Yamuna floodplain were found.)

Tool trace:

1. `locate_place` {"query": "ITO"} -> found ITO (Delhi Metro) at 28.62819, 77.24104
1. `get_zones` {"lat": 28.628191, "lon": 77.241044} -> planning zone D; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.628191, "lon": 77.241044, "query": "house construction floodplain"} -> 5 clause(s): MPD47_GAZETTE_EN:4.2.1:0, MPD47_GAZETTE_EN:4.2.4@p755:0, MPD47_GAZETTE_EN:4.2@p750:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:p642:0`</sub>

### agent-03

**How much of my plot can I build on near Rajiv Chowk metro station?**

- **Where:** no pin — the agent found 28.63271, 77.21931
- **Zones:** planning zone D; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, a plain station)
- **Abstained:** `citation_check_failed`
- **Cost:** 52.6 s, 5 llm call(s), 8197 in / 392 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 1 m from the expected place (tolerance 2000 m)
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice

Tool trace:

1. `locate_place` {"query": "Rajiv Chowk metro station"} -> found Rajiv Chowk (Delhi Metro) at 28.63271, 77.21931
1. `get_zones` {"lat": 28.632706, "lon": 77.219312} -> planning zone D; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.632706, "lon": 77.219312, "query": "maximum ground coverage"} -> 5 clause(s): MPD47_GAZETTE_EN:4.2.3@p753:0, MPD47_FAQ:Q13@p13:0, MPD47_GAZETTE_EN:4.2@p750:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_FAQ:Q13@p13:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`</sub>

### agent-04

**What are the ground coverage rules for a plot near Dwarka Sector 21 metro station?**

- **Where:** no pin — the agent found 28.55192, 77.05856
- **Zones:** planning zone K-II; in TOD zone
- **Mode:** agent   **Expected:** answer   (gazetteer, the D-049 query)
- **Answered** in 12 words
- **Cost:** 33.5 s, 4 llm call(s), 5828 in / 219 out tokens, 0 rate-limit retr(y/ies)
- **Location:** 5 m from the expected place (tolerance 2000 m)

Tool trace:

1. `locate_place` {"query": "Dwarka Sector 21 metro station"} -> found Dwarka Sector 21, Dwarka Sector 21 Underpass, Najafgarh, Delhi, South West Delhi, Delhi, 110061, India at 28.55192, 77.05856
1. `get_zones` {"lat": 28.5519218, "lon": 77.0585605} -> planning zone K-II; in TOD zone
1. `search_clauses` {"k": 5, "lat": 28.5519218, "lon": 77.0585605, "query": "ground coverage"} -> 5 clause(s): MPD47_GAZETTE_EN:4.2.3@p753:0, MPD47_GAZETTE_EN:4.2@p750:0, MPD47_GAZETTE_EN:4.2.1:0...

> The maximum ground coverage allowed on a TOD Plot is 40% [MPD47_GAZETTE_EN:4.2.3@p753:0].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 | Master Plan for Delhi 2047 gazette notification (English) | 753-754 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2@p750:0`, `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:3.6.1@p721:1`, `MPD47_GAZETTE_EN:4.2.4@p755:0`</sub>

### agent-05

**Is construction allowed in the Ridge near Chhatarpur?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (a Ridge question with no pin)
- **Abstained:** `model_abstained: location not found in Delhi.`
- **Cost:** 9.8 s, 2 llm call(s), 1936 in / 73 out tokens, 0 rate-limit retr(y/ies)
- **Suspected:** abstained on an answerable question (model_abstained: location not found in Delhi.)

Tool trace:

1. `locate_place` {"query": "Chhatarpur ridge"} -> not found (not_found_in_delhi)

## c. eval/questions_draft.jsonl, for reading not for scoring

### draft-loc-15

**How much land would a group of us need to gather before we can start a scheme here?**

- **Where:** P_LP_2 (28.672553, 77.058353)
- **Zones:** planning zone K-I; in land pooling area L
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Answered** in 26 words
- **Cost:** 13.7 s, 1 llm call(s), 1834 in / 82 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:4.1.2:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:4.1.2:0`
- **The draft's own short answer:** At least 20 hectares of contiguous land.
- **Suspected:** cited only the FAQ although a gazette clause was retrieved; the expected clause was retrieved but not cited

> A group of landowners can approach DDA for a scheme only when the assembled land parcels are contiguous and together cover at least 20 hectares [C3][C6].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_FAQ:Q12@p9:0` | Q12 | FAQs on MPD-2047 | 9 |
| `MPD47_FAQ:Q10@p9:0` | Q10 | FAQs on MPD-2047 | 9 |

<sub>Retrieved: `MPD47_FAQ:Q13@p9:0`, `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_FAQ:Q12@p9:0`, `MPD47_FAQ:Q7@p8:0`, `MPD47_GAZETTE_EN:4.1.3:0`, `MPD47_FAQ:Q10@p9:0`</sub>

### draft-loc-18

**Can I put up a house on this piece of land?**

- **Where:** P_ZONEO (28.672913, 77.243545)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Answered** in 66 words
- **Cost:** 47.0 s, 2 llm call(s), 6238 in / 288 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `MPD47_GAZETTE_EN:3.1.2@p681:0`
- **Expected clause cited?** yes
- **The draft's own short answer:** No: on the active floodplain nothing may be built, and only recreational use is allowed.
- **Suspected:** needed a citation retry

> The Master Plan for Delhi 2047 states that an active Yamuna floodplain is a “no‑construction zone” and only recreational uses are allowed; any unauthorised house or building must be demolished by the competent agency on priority [C2]. The Delhi High Court has observed that illegal construction on the floodplain is carried out without permission, endangers the ecologically fragile area and creates air‑pollution and health hazards [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `DHC_YAMUNA_20240708:2:0` | 2 | Delhi High Court order on Yamuna floodplain encroachments (8 Jul 2024) | 2 |

<sub>Retrieved: `DHC_YAMUNA_20240708:2:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:p1:0`</sub>

### draft-loc-25

**Could I run a small workshop out of my home at this address?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Abstained:** `model_abstained: Sources do not address running a workshop from a residential address in zone G.`
- **Cost:** 27.6 s, 1 llm call(s), 3613 in / 69 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:9.2:0`
- **Expected clause cited?** no
- **The draft's own short answer:** Household industries from the annexure lists are allowed in residential premises.
- **Suspected:** abstained on an answerable question (model_abstained: Sources do not address running a workshop from a residential address in zone G.)

<sub>Retrieved: `MPD47_GAZETTE_EN:Annexure 21@p969:0`, `MPD47_GAZETTE_EN:Annexure 21@p979:0`, `MPD47_GAZETTE_EN:Annexure 21@p968:0`, `MPD47_GAZETTE_EN:Annexure 21@p978:0`, `MPD47_GAZETTE_EN:Annexure 21@p977:0`, `MPD47_GAZETTE_EN:Annexure 21@p972:0`</sub>

### draft-loc-23

**What is the smallest site I would need here to build a block of flats?**

- **Where:** P_PLAIN (28.639973, 77.088994)
- **Zones:** planning zone G; in none of the six policy zones
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Abstained:** `model_abstained: The provided sources do not specify the minimum site area required for a block of flats.`
- **Cost:** 19.6 s, 1 llm call(s), 2601 in / 106 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:7.2.2@p815:0`
- **Expected clause cited?** no
- **The draft's own short answer:** 3,000 sqm for group housing, on a road of at least 18 m right of way.
- **Suspected:** abstained on an answerable question (model_abstained: The provided sources do not specify the minimum site area required for a block of flats.)

<sub>Retrieved: `MPD47_GAZETTE_EN:13.4.4:0`, `MPD47_GAZETTE_EN:3.4.2:0`, `MPD47_GAZETTE_EN:Annexure 1@p926:0`, `MPD47_FAQ:Q3@p20:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:4.6.2@p777:0`</sub>

### draft-loc-17

**Who is responsible for putting in the roads and parks when my land here gets developed?**

- **Where:** P_LP_4 (28.707682, 76.979762)
- **Zones:** planning zone N; in land pooling area L
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Answered** in 88 words
- **Cost:** 29.0 s, 2 llm call(s), 3718 in / 333 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `MPD47_GAZETTE_EN:4.1.2:0`
- **Expected clause cited?** yes
- **The draft's own short answer:** DDA acts as the main anchor for roads, parks and services.
- **Suspected:** needed a citation retry

> DDA is the agency that must design, notify and construct the roads, parks, playgrounds, utilities, services and other public‑infrastructure in a land‑pooling scheme, as the gazette notification states that “DDA shall act as main anchor for preparation of schemes and development of all roads, parks & playground, utilities, services, social infrastructure, social housing etc. as per the approved scheme” [C2]. The FAQs also confirm that DDA will prepare the land‑pooling schemes and specify the location of land required for city‑level physical infrastructure, including roads and recreational facilities [C3].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.1.2:0` | 4.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 747-748 |
| `MPD47_FAQ:Q9@p9:0` | Q9 | FAQs on MPD-2047 | 9 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.1@p746:0`, `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_FAQ:Q9@p9:0`, `MPD47_FAQ:Q14@p10:0`, `MPD47_FAQ:Q18@p10:0`, `MPD47_FAQ:Q13@p9:0`</sub>

### draft-loc-19

**Someone has thrown up a wall and a shed on the land next to mine here. Who has to act?**

- **Where:** P_ZONEO_2 (28.703937, 77.25267)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Answered** in 76 words
- **Cost:** 51.9 s, 2 llm call(s), 6809 in / 403 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `DHC_YAMUNA_20240708:6:0`
- **Expected clause cited?** no
- **The draft's own short answer:** The Vice Chairman of DDA was directed by the High Court to clear encroachments.
- **Suspected:** needed a citation retry; answered without citing any expected clause

> The Master Plan for Delhi 2047 states that the active Yamuna floodplain is a “no‑construction zone” and that any unauthorised construction, including walls or sheds, must be demolished by the competent authority such as the DDA or the Revenue Department after obtaining the required NOC [C3].  
> 
> NGT‑related reports record that the Delhi government has directed the DDA and the Revenue Department to carry out ground‑truthing, identify unauthorised structures and ensure their removal on the floodplain [C5][C6].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |
| `NGT_OA572_GNCTD_REPORT:3@p25:1` | 3 | GNCTD report to NGT on Yamuna floodplain demarcation (OA 572 of 2024) | 25-27 |
| `NGT_OA572_GNCTD_REPORT:5@p30:0` | 5 | GNCTD report to NGT on Yamuna floodplain demarcation (OA 572 of 2024) | 30-31 |

<sub>Retrieved: `NGT_OA572_GNCTD_REPORT:1@p29:0`, `NGT_OA572_GNCTD_REPORT:1@p15:0`, `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:5@p30:0`</sub>

### draft-loc-07

**How long should the authority take to clear a building proposal for a site like this?**

- **Where:** P_TOD_4 (28.650495, 77.11909)
- **Zones:** planning zone G; in TOD zone
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 38.1 s, 2 llm call(s), 5265 in / 212 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `MPD47_GAZETTE_EN:4.2.4@p754:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:4.2.4@p754:0`
- **The draft's own short answer:** Up to 60 days from a complete submission.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; needed a citation retry; the expected clause was retrieved but not cited

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.4@p754:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_GAZETTE_EN:4.2.4@p755:0`, `MPD47_GAZETTE_EN:4.2.5:0`, `MPD47_GAZETTE_EN:4.2.2:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`</sub>

### draft-loc-06

**If I build flats here, how much of the building has to be homes rather than shops or offices?**

- **Where:** P_TOD_3 (28.638699, 77.243775)
- **Zones:** planning zone D; in TOD zone
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 39.3 s, 2 llm call(s), 5087 in / 467 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `MPD47_GAZETTE_EN:4.2.3@p752:1`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:4.2.3@p752:1`
- **The draft's own short answer:** At least 65% of the permitted floor area has to be residential.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; needed a citation retry; the expected clause was retrieved but not cited

<sub>Retrieved: `MPD47_GAZETTE_EN:4.2.1:0`, `MPD47_GAZETTE_EN:4.2.3@p752:1`, `MPD47_GAZETTE_EN:4.2.3@p753:0`, `MPD47_GAZETTE_EN:4.2.3@p751:0`, `MPD47_FAQ:Q5@p11:0`, `MPD47_GAZETTE_EN:4.2.2:0`</sub>

### draft-loc-21

**What, if anything, is this land allowed to be used for?**

- **Where:** P_ZONEO_4 (28.724642, 77.25267)
- **Zones:** planning zone O; in Zone O (Yamuna floodplain)
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Answered** in 53 words
- **Cost:** 21.0 s, 1 llm call(s), 2990 in / 166 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:3.1.2@p681:0`
- **Expected clause cited?** yes
- **The draft's own short answer:** Recreational use only on the active floodplain, with limited public uses by permission.

> The Master Plan classifies the active Yamuna floodplain (Zone O) as a “no‑construction zone.” Only recreational activities are permitted by default, and any other use – such as essential government utilities, socio‑cultural facilities, or public‑infrastructure projects – may be allowed only with the prior approval or NOC of the competent statutory authority [C1].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 | Master Plan for Delhi 2047 gazette notification (English) | 681-682 |

<sub>Retrieved: `MPD47_GAZETTE_EN:3.1.2@p681:0`, `NGT_OA572_GNCTD_REPORT:3@p25:1`, `NGT_OA572_GNCTD_REPORT:p1:0`, `NGT_OA572_GNCTD_REPORT:5@p30:0`, `NGT_OA572_GNCTD_REPORT:7@p7:0`, `NGT_OA572_GNCTD_REPORT:4@p30:0`</sub>

### draft-loc-16

**My plot here sits inside the old village settlement. Do these rules reach it?**

- **Where:** P_LP_3 (28.654989, 77.032156)
- **Zones:** planning zone K-I; in land pooling area L
- **Mode:** map   **Expected:** answer   (location, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 3.8 s, 2 llm call(s), 3581 in / 416 out tokens, 0 rate-limit retr(y/ies)
- **Citation retries:** 1
- **Expected clauses:** `MPD47_GAZETTE_EN:4.1.1:0`
- **Expected clause cited?** no
- **The draft's own short answer:** No: Lal Dora and extended Lal Dora land is left out.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; needed a citation retry

<sub>Retrieved: `MPD47_FAQ:Q18@p10:0`, `MPD47_FAQ:Q4@p8:0`, `MPD47_GAZETTE_EN:4.1.2:0`, `MPD47_GAZETTE_EN:4.1@p746:0`, `MPD47_FAQ:Q5@p8:0`, `MPD47_FAQ:Q14@p10:0`</sub>

### draft-gen-15

**By how much can the floor area ratio go up when an area is regenerated?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Answered** in 19 words
- **Cost:** 4.9 s, 2 llm call(s), 3485 in / 132 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:4.5.3:0`
- **Expected clause cited?** yes
- **The draft's own short answer:** Up to 1.5 times the base FAR.
- **Suspected:** the agent answered without ever establishing a point

Tool trace:

1. `search_clauses` {"k": 5, "query": "floor area ratio increase regeneration"} -> 5 clause(s): MPD47_GAZETTE_EN:4.5.4:0, MPD47_GAZETTE_EN:4.6.2@p774:0, MPD47_GAZETTE_EN:3.4.3:0...

> When an area is regenerated, the permissible floor‑area‑ratio may be increased up to one‑and‑a‑half times the base FAR [MPD47_GAZETTE_EN:4.5.3:0].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:4.5.3:0` | 4.5.3 | Master Plan for Delhi 2047 gazette notification (English) | 770-771 |

<sub>Retrieved: `MPD47_GAZETTE_EN:4.5.4:0`, `MPD47_GAZETTE_EN:4.6.2@p774:0`, `MPD47_GAZETTE_EN:3.4.3:0`, `MPD47_GAZETTE_EN:4.5.3:0`, `MPD47_GAZETTE_EN:4.5.6:0`</sub>

### draft-gen-18

**What is a studio apartment under this plan?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 42.7 s, 3 llm call(s), 6872 in / 616 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:7.1:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:7.1:0`
- **The draft's own short answer:** A residential unit with a carpet area of 40 to 60 sqm.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; the expected clause was retrieved but not cited

Tool trace:

1. `search_clauses` {"query": "studio apartment definition"} -> 6 clause(s): MPD47_GAZETTE_EN:8.3.1:0, MPD47_GAZETTE_EN:7.1:0, MPD47_GAZETTE_EN:7.2.2@p818:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:8.3.1:0`, `MPD47_GAZETTE_EN:7.1:0`, `MPD47_GAZETTE_EN:7.2.2@p818:0`, `MPD47_GAZETTE_EN:7.2.2@p815:0`, `MPD47_FAQ:Q10@p12:0`, `MPD47_GAZETTE_EN:9.1.1:0`</sub>

### draft-gen-25

**How many planning zones is Delhi divided into?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 48.4 s, 3 llm call(s), 5983 in / 215 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:1.7.2:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:1.7.2:0`
- **The draft's own short answer:** 17, lettered A to P with no zone I.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; the expected clause was retrieved but not cited

Tool trace:

1. `search_clauses` {"k": 5, "query": "how many planning zones"} -> 5 clause(s): MPD47_GAZETTE_EN:1.7.2:0, MPD47_GAZETTE_EN:5.1.1:0, MPD47_FAQ:Q3@p8:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:1.7.2:0`, `MPD47_GAZETTE_EN:5.1.1:0`, `MPD47_FAQ:Q3@p8:0`, `MPD47_GAZETTE_EN:p909:0`, `MPD47_GAZETTE_EN:1.7.1@p665:0`</sub>

### draft-gen-23

**Where do I look up which activities are allowed on a particular kind of premise?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 48.8 s, 3 llm call(s), 6881 in / 549 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_FAQ:Q7@p3:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_FAQ:Q7@p3:0`
- **The draft's own short answer:** Annexures 18 to 22 of the plan list permitted use premises and activities.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; the expected clause was retrieved but not cited

Tool trace:

1. `search_clauses` {"k": 5, "query": "permitted activities premise"} -> 5 clause(s): MPD47_GAZETTE_EN:Annexure 21@p970:0, MPD47_GAZETTE_EN:Annexure 21@p981:0, MPD47_GAZETTE_EN:Annexure 21@p974:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:Annexure 21@p970:0`, `MPD47_GAZETTE_EN:Annexure 21@p981:0`, `MPD47_GAZETTE_EN:Annexure 21@p974:0`, `MPD47_GAZETTE_EN:Annexure 21@p969:0`, `MPD47_FAQ:Q7@p3:0`</sub>

### draft-gen-17

**What is the permitted floor area ratio and smallest plot for a group housing scheme?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Answered** in 65 words
- **Cost:** 53.2 s, 3 llm call(s), 7345 in / 514 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:7.2.2@p815:0`
- **Expected clause cited?** yes
- **The draft's own short answer:** FAR 200 and 3,000 sqm, or 2,000 sqm in Lal Dora, on an 18 m road.
- **Suspected:** the agent answered without ever establishing a point

Tool trace:

1. `search_clauses` {"k": 5, "query": "permitted floor area ratio smallest plot group housing"} -> 5 clause(s): MPD47_GAZETTE_EN:7.2.2@p815:0, MPD47_GAZETTE_EN:7.2.2@p818:0, MPD47_GAZETTE_EN:7.2.1@p814:0...

> The gazette notification permits a maximum floor‑area ratio of 200 % for Group Housing (rising to 300 % for an Affordable Rental Housing Complex) [MPD47_GAZETTE_EN:7.2.2@p815:0].  
> 
> The minimum plot area for Group Housing is 3 000 sqm with a required road‑right‑of‑way of 18 m; in Lal Dora or Extended Lal Dora the minimum may be reduced to 2 000 sqm with a 12 m ROW [MPD47_GAZETTE_EN:7.2.2@p815:0].

| marker | clause | document | pages |
| --- | --- | --- | --- |
| `MPD47_GAZETTE_EN:7.2.2@p815:0` | 7.2.2 | Master Plan for Delhi 2047 gazette notification (English) | 815-816 |

<sub>Retrieved: `MPD47_GAZETTE_EN:7.2.2@p815:0`, `MPD47_GAZETTE_EN:7.2.2@p818:0`, `MPD47_GAZETTE_EN:7.2.1@p814:0`, `MPD47_GAZETTE_EN:7.2.1@p813:0`, `MPD47_GAZETTE_EN:7.2.2@p817:0`</sub>

### draft-gen-19

**How big does a local shopping centre site have to be?**

- **Where:** no pin
- **Zones:** no point
- **Mode:** agent   **Expected:** answer   (general, should_abstain=False)
- **Abstained:** `citation_check_failed`
- **Cost:** 51.8 s, 3 llm call(s), 7644 in / 257 out tokens, 0 rate-limit retr(y/ies)
- **Expected clauses:** `MPD47_GAZETTE_EN:8.1.2@p823:0`
- **Expected clause cited?** no — retrieved but not cited: `MPD47_GAZETTE_EN:8.1.2@p823:0`
- **The draft's own short answer:** 3,000 sqm with an 18 m right of way; a convenience centre needs 1,000 sqm.
- **Suspected:** abstained on an answerable question (citation_check_failed); the citation check failed twice; the expected clause was retrieved but not cited

Tool trace:

1. `search_clauses` {"query": "minimum plot area local shopping centre"} -> 6 clause(s): MPD47_GAZETTE_EN:8.1.2@p823:0, MPD47_FAQ:Q1@p5:0, MPD47_GAZETTE_EN:11.1.3@p860:0...

<sub>Retrieved: `MPD47_GAZETTE_EN:8.1.2@p823:0`, `MPD47_FAQ:Q1@p5:0`, `MPD47_GAZETTE_EN:11.1.3@p860:0`, `MPD47_GAZETTE_EN:13.2:0`, `MPD47_GAZETTE_EN:8.1.1:0`, `MPD47_GAZETTE_EN:8.1.3:0`</sub>

