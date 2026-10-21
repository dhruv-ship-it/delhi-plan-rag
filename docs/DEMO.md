# A three-minute demo

For an interview, a screen recording, or showing someone what this does. Two versions:

- **[Search-only mode](#search-only-mode-works-today)** — works right now, with no API key.
  Every beat below was run and the observed results are printed beside it.
- **[Full answer mode](#full-answer-mode-after-the-api-key)** — the same route once
  `ANTHROPIC_API_KEY` is set, where the written answer and the citation chips appear.
- **[The 10-second GIF](#the-10-second-gif)** — what to record for the top of the README.

Every clause id below was observed, not predicted: each question was run through
`/api/search` at its own point, and the ones whose top results were wrong were cut rather
than written up. What was cut and why is in [Questions that did not make it](#questions-that-did-not-make-it).

---

## Before you start

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
# then open http://localhost:5173
```

Give the backend a few seconds — the indexes and the embedding model load before the
first request. `http://localhost:8000/api/health` should say `status: ok` and
`chunks: 653`.

The points are in `data/test_points.json`. Have them to hand, because clicking a precise
coordinate on a map is the one thing that will make you fumble on camera:

| Point | Coordinates | What it is |
| --- | --- | --- |
| **P_TOD** | 28.6328, 77.2197 | Rajiv Chowk — a TOD zone, planning zone D |
| **P_HDC** | 28.6595, 77.0066 | the High Density Corridor along UER-II, zone K-I |
| **P_ZONEO** | 28.6729, 77.2435 | the Yamuna floodplain, planning zone O |
| **P_LDA** | 28.6080, 76.9038 | a Low Density Area on the NCT border, zone L |
| **P_RIDGE** | 28.4279, 77.2077 | a Regional Park — the Ridge, zone J |
| **P_OUT** | 28.4950, 77.0890 | Gurugram — outside Delhi |

Two optional extras, worth having if the conversation goes there: **P_LP**
(28.6769, 77.0271) a land pooling area, and **P_PLAIN** (28.6400, 77.0890) an ordinary
plot in none of the six policy zones.

---

## Search-only mode (works today)

Six beats, about 25 seconds each, plus an optional beat 3b if you are asked how you
debug retrieval. The spine of the demo is **one question asked at three
different points**, because that is the thing no plain RAG demo can show.

### Beat 1 — Rajiv Chowk, and what the system knows before it searches (0:00–0:30)

**Click P_TOD (28.6328, 77.2197).** Ask:

> **How much of my plot can I build on?**

**What the viewer should notice, in this order:**

1. **The zone chips appear before the question is asked.** Planning zone **D**, and a
   **TOD** chip. That lookup is `get_zones(lat, lon)` against DDA's own GIS layers — it
   is not something the model inferred.
2. **The query was rewritten.** The screen shows the expanded query:
   `How much of my plot can I build on? transit oriented development TOD zone` — the
   user typed no zone words, and the search got them anyway.
3. **15 chunks were excluded and 37 boosted** before ranking.
4. **All five results are from chapter 4.2, the TOD policy:**

   | rank | clause | heading |
   | --- | --- | --- |
   | 1 | `MPD47_GAZETTE_EN:4.2.1:0` | 4.2 TRANSIT ORIENTED DEVELOPMENT → 4.2.1 Definitions |
   | 2 | `MPD47_GAZETTE_EN:4.2.3@p751:0` | 4.2.3 TOD Norms |
   | 3 | `MPD47_GAZETTE_EN:4.2.3@p753:0` | 4.2.3 TOD Norms |
   | 4 | `MPD47_GAZETTE_EN:4.2@p750:0` | 4.2 TRANSIT ORIENTED DEVELOPMENT (TOD) |
   | 5 | `MPD47_GAZETTE_EN:4.2.3@p752:1` | 4.2.3 TOD Norms |

**Say:** "The point came first. Before any searching happened, the system knew this is a
TOD zone, so it added the policy's own vocabulary to the query and dropped the clauses
that belong to policies this point is not in."

### Beat 2 — the same question, 18 km west (0:30–1:00)

**Click P_HDC (28.6595, 77.0066).** Ask **the identical question**:

> **How much of my plot can I build on?**

**What the viewer should notice:** the chips changed to planning zone **K-I** and
**HDC** — and **every top result changed with them**, from chapter 4.2 to chapter 4.3:

| rank | clause | heading |
| --- | --- | --- |
| 1 | `MPD47_GAZETTE_EN:4.3@p757:0` | 4.3 HIGH DENSITY CORRIDOR DEVELOPMENT |
| 2 | `MPD47_FAQ:Q1@p15:0` | FAQs on HDC Policy → Q1. What is a High Density Corridor (HDC) Zone? |
| 3 | `MPD47_GAZETTE_EN:1.7.1@p666:0` | 1.7 Land Use Plan → 1.7.1 Land Use Plan |
| 4 | `MPD47_GAZETTE_EN:4.3.1:0` | 4.3.1 Definitions |
| 5 | `MPD47_GAZETTE_EN:4.3.3@p758:0` | 4.3.3 HDC Norms |

**This is the beat the whole project exists for, so land it.** Same words typed, 4.2.x
became 4.3.x, and nothing about the question told it to. Be honest about rank 3: 1.7.1 is
the general land use plan, not an HDC clause — it is a reasonable neighbour, not a bug,
and saying so is better than hoping nobody reads it.

### Beat 3 — the floodplain, where the answer is in a court order (1:00–1:30)

**Click P_ZONEO (28.6729, 77.2435).** Ask:

> **Is construction allowed here?**

| rank | clause | heading |
| --- | --- | --- |
| 1 | `DHC_YAMUNA_20240708:2:0` | **Delhi High Court order, 8 July 2024** |
| 2 | `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1 ENVIRONMENT → 3.1.2 Green-Blue Infrastructure |
| 3 | `MPD47_GAZETTE_EN:9.2:0` | 9.2 Household Industries |

**What the viewer should notice:** the corpus is **not one document**, and the document
at rank 1 is **not the Master Plan**. A High Court order comes first — authority rank 2,
a different document, retrieved by the same search — and the clause carrying "active
floodplain shall be a *no construction zone*" is behind it at rank 2. Top-1 cosine
**0.6813**. Be honest about rank 3: 9.2 Household Industries is there because it
mentions Zone O in passing, and it is not an answer to the question.

**If you have 10 seconds more**, ask the sharper version: **"What are the rules for the
active floodplain?"** puts 3.1.2 back at rank 1 with cosine **0.7854**, the highest at
this point. It used to be followed by two chunks of the GNCTD report to the NGT, which
was removed from the index on 21 October because its text layer is unreadable OCR
(D-105); expect usable clauses in those slots now.

**Say, and this is the interesting part:** "Zone O is the one zone with *no policy
section* in the Master Plan. The plan defines it and then only ever names it in other
policies' exclusion lists. So for this zone the system boosts clauses that mention it,
but it is **never** allowed to exclude anything — there is no heading that means 'this
rule is about the floodplain' — and since 20 October it does not expand the query here
either, because appending 'Zone O Yamuna floodplain' to a question about something else
replaced the question instead of qualifying it (D-086)."

**If you are asked what that cost:** this beat used to open on 3.1.2 with a cosine of
0.8489, and the NGT report was at rank 3 (it is no longer indexed at all, D-105). Both numbers were higher because the query
itself had the floodplain words appended to it. The trade is written up in
`reports/diagnosis_fuel_station.md` § 5, and the question it bought back is in beat 3b
below.

### Beat 3b — the fuel station, and a rule that says no (optional, 20 seconds)

**Stay on P_ZONEO.** Ask:

> **Can a fuel station be built here?**

| rank | clause | heading |
| --- | --- | --- |
| 1 | `MPD47_GAZETTE_EN:11.1.1@p854:0` | 11.1 Transportation → 11.1.1 Development Control Norms |
| 2 | `MPD47_GAZETTE_EN:11.1.1@p855:0` | 11.1.1 — the fuel-station norms |
| 3 | `MPD47_GAZETTE_EN:Annexure 18:0` | Annexure 18: Residential Use Zone — permitted use premises |

Rank 1 is the sentence *"Fuel stations may be permitted in all Use Zones except
Recreational (Regional Park, District Park, etc.) and **Zone O**"*, and rank 2 is the
norms that go with it, so the viewer gets the permission rule and the controls together.

**Worth saying if you want one war story:** this question was **cut from this demo on 19
October**, because the clause sat at rank 14. The cause was not the embedding model or
the chunking: it was query expansion appending the zone's own name to a question that was
about something else. `reports/diagnosis_fuel_station.md` is the whole investigation, and
the fix was four lines. Use it if you are asked "how do you debug retrieval".

### Beat 4 — the Low Density Area, and what exclusion is worth (1:30–2:00)

**Click P_LDA (28.6080, 76.9038).** Ask:

> **What is the maximum ground coverage here?**

| rank | clause | heading |
| --- | --- | --- |
| 1 | `MPD47_GAZETTE_EN:4.4.3:0` | 4.4 LOW DENSITY AREA → **4.4.3 Development Control Norms for plots in LDA** |
| 2 | `MPD47_FAQ:Q3@p18:0` | FAQs on LDA → Q3. Permissible FAR, ground coverage and height |
| 3 | `MPD47_GAZETTE_EN:4.4@p764:0` | 4.4 LOW DENSITY AREA (LDA) |

**What the viewer should notice:** **20 chunks excluded.** Point at that number. Without
the location step, a question phrased this generally at this point returns TOD and HDC
material — the wrong policy entirely — which is recorded in
`reports/location_compare_v3.md`, comparison E. With it, the LDA's own norms clause is
rank 1 and its FAQ on exactly ground coverage is rank 2.

**"Can I build a house here?"** works here too, same rank-1 clause, if you prefer a
question a normal person would ask.

### Beat 5 — the Ridge, and the question the documents do not answer (2:00–2:30)

**Click P_RIDGE (28.4279, 77.2077).** Ask:

> **Is construction allowed here?**

| rank | clause | heading | cosine |
| --- | --- | --- | --- |
| 1 | `MPD47_GAZETTE_EN:10.1@p843:0` | 10.1 Use Premises and Definitions | 0.6766 |
| 2 | `MPD47_GAZETTE_EN:3.1.2@p681:0` | 3.1.2 Green-Blue Infrastructure | 0.6590 |
| 3 | `MPD47_GAZETTE_EN:9.2:0` | 9.2 Household Industries | 0.6629 |

**Do not skip this beat, and do not dress it up.** The chips say Regional Park and
planning zone J. What comes back is chapter 10's **definition** of a Regional Park — and
what does *not* come back is a clause saying you may not build there, **because the
Master Plan does not phrase it that way.** The Ridge, like Zone O, has no policy section
of its own: 37 chunks mention it and every one sits in a section about something else.
The cosines are lower than they were before 20 October (0.6766 against 0.7419) for the
same reason as in beat 3: the query is no longer padded with the zone's own vocabulary
(D-086), so the numbers are a more honest measure of how well the question matches the
corpus — and the answer is "not very well", which is the point of the beat.

**Say:** "This is a should-abstain question, and I'd rather show you one than only show
you the ones that work. The honest output here is the definition of what this land is,
not a permission rule — and the right behaviour from the answering layer is to decline
rather than to assemble something that sounds like a rule out of a definition."

That is a stronger interview beat than any of the first four, because it is the one that
shows you know what your system does not know.

### Beat 6 — outside Delhi (2:30–2:50)

**Click P_OUT (28.4950, 77.0890)** — Gurugram, just over the border. Ask anything.

**What the viewer should notice:** the chips say **not inside Delhi**, and
`/api/ask` returns **zero clauses** — not a few weak ones. The code checks the point
before it retrieves: outside NCT Delhi there is no Master Plan for Delhi answer, so it
does not go looking for one, and in full answer mode it abstains before spending an API
call.

### Close (2:50–3:00)

**Click a citation chip** on any earlier result to open the clause drawer: the clause
text, its chapter, and its **1-based page number in the original gazette PDF**. One line
to finish on: "Every sentence of an answer carries one of those, and an answer whose
citations do not check out is retried once and then refused."

---

## Full answer mode (after the API key)

The route is identical; three things are different.

**What is added at each beat.** A written answer appears above the clause list, each
sentence carrying a **citation chip**. Clicking a chip opens that clause in the drawer.
Follow one through on camera — it is the single most convincing five seconds in the demo,
because it shows the answer is *attached* to the source rather than asserted next to it.

**Beat 5 becomes the best beat.** At P_RIDGE, the answering layer should **decline**:
there is no clause saying you may not build in a Regional Park, so a grounded system has
to say so. If it instead produces a confident answer assembled out of chapter 10's
definitions, that is a finding worth knowing about, and it is the first thing to check
when the key goes in.

**Beat 6 shows the abstention path explicitly.** At P_OUT the result is an abstention
with reason `outside_delhi`, reached **before any model call** — the point check is step
1 of five, so an off-map click costs nothing.

**Add one beat, about 15 seconds, after beat 6.** Click any point inside Delhi and ask
something the documents cannot answer:

> **What is my property tax?**

It should decline. Worth knowing before you record: at P_OUT this question's top-1 cosine
is **0.6082**, which is *above* the configured `ABSTAIN_THRESHOLD` of 0.5804 — so the
cheap pre-check does **not** catch it, and the refusal has to come from the model
following rule 3 of the system prompt and from the citation check. That is the designed
division of labour, not a gap: the threshold is a cost guard, the citation check is the
correctness guard. If you are asked how you set the threshold, the honest answer is in
D-071 and it is that **no retrieval score separated the answerable from the
should-abstain questions**, so the value only catches total retrieval failure.

**One thing to do before recording in this mode:** set a hard spend limit in the
Anthropic console. It is the only control that cannot be defeated by a bug in this
repository.

---

## The 10-second GIF

For the top of the README. No audio, 10–15 seconds, and it has to make sense with no
narration — so it is beats 1 and 2 only, which is the whole idea in two clicks.

1. **Click P_TOD.** Let the zone chips land. (2s)
2. **Type the question** — or have it pre-filled and press Enter, which looks better than
   watching someone type. (2s)
3. **Results appear.** Hold still long enough to read `4.2.1` and `4.2.3 TOD Norms`. (3s)
4. **Click P_HDC.** Chips change. (2s)
5. **Same question, Enter.** Results are now `4.3`, `4.3.1`, `4.3.3`. Hold. (4s)

The viewer who reads nothing else should come away with: *clicking a different place
changed which law applies.* Do not try to fit a written answer, a citation chip or the
clause drawer into the GIF — each is worth its own few seconds and all three at this
speed read as flicker.

---

## Questions that did not make it

Cut after being run, which is why the list is here:

| Question | Point | Why it was cut |
| --- | --- | --- |
| ~~"Can a fuel station be built here?"~~ | P_ZONEO | **No longer cut — it is beat 3b above.** It was cut on 19 October because 11.1.1 sat at rank 14; it was diagnosed on 20 October (query expansion, `reports/diagnosis_fuel_station.md`) and fixed the same day (D-086). It is now rank 1, under both wordings. |
| "Can I build a house here?" | P_RIDGE | Still cut, and now for a stronger reason. It used to be a weaker version of "Is construction allowed here?" (top cosine 0.6907 against 0.7419); after D-086 its top 5 is Group Housing norms and a slum FAQ rather than anything about the Ridge, because this is a question whose subject *is* the place and those are the ones the expansion was helping. The cost table in `reports/diagnosis_fuel_station.md` § 5 has the ranks. |
| "How much of my plot can I build on?" | P_PLAIN | Honest but unexciting: 35 chunks excluded, 0 boosted, and ranks 2 and 3 wander to non-conforming industrial areas and slum ISR norms. Use **"What is the permissible FAR for plotted housing?"** instead if you want this point — 7.2.1 Plotted Housing lands at ranks 2 and 3. |

Two that **do** work and were left out only for time, worth keeping in your pocket:

- **"What is clause 4.2.1?"** at P_TOD returns `4.2.1` at rank 1 — the BM25 half of the
  hybrid earning its place, since an embedding blurs a dotted number into a general sense
  of planning-ness.
- **"How do I get my land included in a scheme?"** at **P_LP** returns `4.1.2 Guiding
  Principles` at rank 1 and four Land Pooling FAQs behind it.

---

## If something goes wrong on camera

| Symptom | Cause | Fix |
| --- | --- | --- |
| `503` on a question | no API key — expected in search-only mode | the clause list below it is the demo |
| No chips, no results | backend still loading, or no index | check `http://localhost:8000/api/health` for `status: ok` and `chunks: 653` |
| No map overlays | `data/layers/dda` is missing | `uv run python scripts\06_fetch_layers.py` |
| Verify tab missing | `ZONEWISE_DEV` not set | restart with `scripts\dev.ps1 -Verify` |
| Blank page at :5173 | Vite not running | look at the second PowerShell window |

The numbers in this file were observed on **19 October 2026** against 700 chunks with the
reranker off, except beats 3, 3b and 5, which were re-run on **20 October** after D-086
scoped query expansion to the four topics that have a policy section. If the pipeline is rebuilt, re-run the questions before trusting the clause
ids — `reports/README.md` explains why a chunk count dates a report. **The corpus is now 653
chunks** (D-105), so every rank and cosine in this file is from before that change.
