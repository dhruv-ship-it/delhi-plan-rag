"""Write eval/questions_draft.jsonl: 60 candidate evaluation questions, drafted by Claude.

Reads  data/processed/chunks.jsonl, eval/points.json
Writes eval/questions_draft.jsonl

These questions are a **draft**. Every one was written by reading the chunks it points
at, but nothing here has been checked by a person, so `verified` is false on all 60 and
`eval/run_eval.py` ignores them unless asked for them explicitly. See eval/README.md for
how to verify one.

Two rules shaped the wording, and both are enforced below rather than trusted:

  * No run of four or more consecutive words may be copied from any chunk the question
    expects. A question that quotes its own answer tests nothing: BM25 would find it by
    string overlap and the score would say the retriever works when it does not.
  * A location question must not name its zone or topic. "How much of my plot can I
    build on?" asked at a point in a TOD zone is the real test, because only the
    location step can supply the word TOD.

Safe to re-run; it overwrites the file. Any question Dhruv has already verified should be
edited in `eval/questions.jsonl` instead, which this script never touches.

Run with: uv run python scripts/09_draft_questions.py
"""

import json
import re
import sys

from app.config import settings
from app.extract import markdown_table, use_utf8_output
from app.indexing import read_chunks

#: The longest run of words a question may share with a chunk it expects.
MAX_SHARED_WORDS = 3

GAZETTE = "MPD47_GAZETTE_EN"
FAQ = "MPD47_FAQ"
DHC = "DHC_YAMUNA_20240708"
NGT = "NGT_OA572_GNCTD_REPORT"


def q(
    id_: str,
    question: str,
    category: str,
    expected: list[str],
    acceptable: list[str] | None = None,
    point: str | None = None,
    short: str = "",
    should_abstain: bool = False,
    notes: str = "",
) -> dict:
    """One draft question record."""
    return {
        "id": id_,
        "question": question,
        "point_name": point,
        "category": category,
        "expected_chunk_ids": expected,
        "acceptable_chunk_ids": acceptable or [],
        "expected_answer_short": short,
        "should_abstain": should_abstain,
        "verified": False,
        "drafted_by": "claude_code",
        "notes": notes,
    }


# --- 25 location questions: the zone is never named -----------------------------

LOCATION = [
    # --- in a TOD zone ---------------------------------------------------------
    q(
        "loc-01",
        "I own a 2,500 sqm plot here. How much of the land am I allowed to cover with building?",
        "location",
        [f"{GAZETTE}:4.2.3@p753:0"],
        [f"{FAQ}:Q13@p13:0", f"{FAQ}:Q12@p13:0"],
        "P_TOD",
        "Up to 40% of the plot, with relaxations possible from the TOD Committee.",
        notes="Only the location step can know this is a TOD plot rather than ordinary housing.",
    ),
    q(
        "loc-02",
        "What is the most floor space I could put up on a site at this spot?",
        "location",
        [f"{GAZETTE}:4.2.3@p752:0"],
        [f"{FAQ}:Q8@p12:0", f"{FAQ}:Q9@p12:0"],
        "P_TOD",
        "Base 400, rising to a maximum of 500 once extra charges are paid.",
    ),
    q(
        "loc-03",
        "My piece of land measures about 1,500 sqm. Is that big enough to join the scheme that covers this address?",
        "location",
        [f"{GAZETTE}:4.2.1:0"],
        [f"{FAQ}:Q3@p11:0"],
        "P_TOD_2",
        "No: the minimum is 2,000 sqm.",
    ),
    q(
        "loc-04",
        "Am I obliged to sign up to the development scheme covering this land, or may I stay on my old approvals?",
        "location",
        [f"{GAZETTE}:4.2.3@p751:0"],
        [f"{FAQ}:Q6@p11:0"],
        "P_TOD_2",
        "Taking part is voluntary; existing approvals continue if you do not.",
    ),
    q(
        "loc-05",
        "How many car spaces would I have to provide for a building at this location?",
        "location",
        [f"{FAQ}:Q14@p13:0", f"{GAZETTE}:4.2.3@p753:0"],
        [],
        "P_TOD_3",
        "One equivalent car space for every 100 sqm of floor area.",
    ),
    q(
        "loc-06",
        "If I build flats here, how much of the building has to be homes rather than shops or offices?",
        "location",
        [f"{GAZETTE}:4.2.3@p752:1"],
        [f"{FAQ}:Q10@p12:0"],
        "P_TOD_3",
        "At least 65% of the permitted floor area has to be residential.",
    ),
    q(
        "loc-07",
        "How long should the authority take to clear a building proposal for a site like this?",
        "location",
        [f"{GAZETTE}:4.2.4@p754:0"],
        [f"{FAQ}:Q16@p13:0"],
        "P_TOD_4",
        "Up to 60 days from a complete submission.",
    ),
    # --- in the high density corridor -----------------------------------------
    q(
        "loc-08",
        "How far back from the big new highway do the special building rules reach at this spot?",
        "location",
        [f"{GAZETTE}:4.3.1:0"],
        [f"{FAQ}:Q1@p15:0"],
        "P_HDC",
        "A 250 m band measured from the edge of the road's right of way.",
    ),
    q(
        "loc-09",
        "What width of road does my plot need to front onto before I can build under the rules here?",
        "location",
        [f"{GAZETTE}:4.3.3@p758:0"],
        [f"{FAQ}:Q9@p15:0"],
        "P_HDC",
        "A road with a right of way of at least 18 m.",
    ),
    q(
        "loc-10",
        "Can my brother and I put our two adjoining plots together to build one project at this address?",
        "location",
        [f"{FAQ}:Q11@p16:0"],
        [f"{GAZETTE}:4.3.3@p758:0"],
        "P_HDC_2",
        "Yes, plots may be amalgamated and reconstituted under the corridor policy.",
    ),
    q(
        "loc-11",
        "Is affordable housing something I must include in a project at this location?",
        "location",
        [f"{FAQ}:Q15@p16:0"],
        [f"{GAZETTE}:4.3.3@p759:0"],
        "P_HDC_3",
        "Yes, it is a requirement of the corridor policy.",
    ),
    q(
        "loc-12",
        "Only part of my land falls inside the area with the better building rules. Does it still count?",
        "location",
        [f"{GAZETTE}:4.3.3@p758:0"],
        [f"{FAQ}:Q6@p15:0"],
        "P_HDC_4",
        "Yes, if at least 75% of the plot lies inside the zone.",
    ),
    # --- in a land pooling area ------------------------------------------------
    q(
        "loc-13",
        "Once my farmland here is built up, how much floor space will each plot be allowed?",
        "location",
        [f"{GAZETTE}:4.1.3:0"],
        [f"{FAQ}:Q15@p10:0"],
        "P_LP",
        "An FAR of 200 on each plot in the scheme.",
    ),
    q(
        "loc-14",
        "If I hand over my land here for development, what proportion do I get back?",
        "location",
        [f"{GAZETTE}:4.1.3:0"],
        [f"{FAQ}:Q13@p9:0"],
        "P_LP",
        "Landowners keep up to 60%, with at least 40% going to DDA.",
    ),
    q(
        "loc-15",
        "How much land would a group of us need to gather before we can start a scheme here?",
        "location",
        [f"{GAZETTE}:4.1.2:0"],
        [f"{FAQ}:Q10@p9:0", f"{FAQ}:Q5@p8:0"],
        "P_LP_2",
        "At least 20 hectares of contiguous land.",
    ),
    q(
        "loc-16",
        "My plot here sits inside the old village settlement. Do these rules reach it?",
        "location",
        [f"{GAZETTE}:4.1.1:0"],
        [f"{FAQ}:Q6@p8:0"],
        "P_LP_3",
        "No: Lal Dora and extended Lal Dora land is left out.",
    ),
    q(
        "loc-17",
        "Who is responsible for putting in the roads and parks when my land here gets developed?",
        "location",
        [f"{GAZETTE}:4.1.2:0"],
        [f"{FAQ}:Q9@p9:0", f"{FAQ}:Q14@p10:0"],
        "P_LP_4",
        "DDA acts as the main anchor for roads, parks and services.",
    ),
    # --- in planning zone O, the floodplain ------------------------------------
    q(
        "loc-18",
        "Can I put up a house on this piece of land?",
        "location",
        [f"{GAZETTE}:3.1.2@p681:0"],
        [f"{DHC}:6:0"],
        "P_ZONEO",
        "No: on the active floodplain nothing may be built, and only recreational use is allowed.",
        notes="The hardest location question: nothing in the wording hints at the river.",
    ),
    q(
        "loc-19",
        "Someone has thrown up a wall and a shed on the land next to mine here. Who has to act?",
        "location",
        [f"{DHC}:6:0"],
        [f"{GAZETTE}:3.1.2@p681:0", f"{DHC}:3:0"],
        "P_ZONEO_2",
        "The Vice Chairman of DDA was directed by the High Court to clear encroachments.",
    ),
    q(
        "loc-20",
        "Is a petrol pump something that could be allowed at this spot?",
        "location",
        [f"{GAZETTE}:11.1.1@p854:0"],
        [f"{GAZETTE}:11.1.1@p855:0"],
        "P_ZONEO_3",
        "No: fuel stations are allowed in all use zones except recreational ones and Zone O.",
    ),
    q(
        "loc-21",
        "What, if anything, is this land allowed to be used for?",
        "location",
        [f"{GAZETTE}:3.1.2@p681:0"],
        [f"{GAZETTE}:1.7.2:0"],
        "P_ZONEO_4",
        "Recreational use only on the active floodplain, with limited public uses by permission.",
    ),
    # --- an ordinary plot in none of the four policy zones ---------------------
    q(
        "loc-22",
        "I have a 250 sqm plot here and want to rebuild my house. How much can I cover and how high?",
        "location",
        [f"{GAZETTE}:7.2.1@p813:0"],
        [f"{FAQ}:Q1@p5:0"],
        "P_PLAIN",
        "Plotted housing norms in chapter 7 set coverage, FAR and dwelling units by plot size.",
        notes="Checks the opposite case: no policy zone, so the general norms should win.",
    ),
    q(
        "loc-23",
        "What is the smallest site I would need here to build a block of flats?",
        "location",
        [f"{GAZETTE}:7.2.2@p815:0"],
        [f"{FAQ}:Q1@p5:0"],
        "P_PLAIN",
        "3,000 sqm for group housing, on a road of at least 18 m right of way.",
    ),
    q(
        "loc-24",
        "My building here is forty years old. What is the least land I need to redevelop the whole thing?",
        "location",
        [f"{GAZETTE}:4.5.3:0"],
        [f"{FAQ}:Q5@p2:0"],
        "P_PLAIN",
        "3,000 sqm for residential, 1,000 sqm for commercial, industrial and PSP.",
    ),
    q(
        "loc-25",
        "Could I run a small workshop out of my home at this address?",
        "location",
        [f"{GAZETTE}:9.2:0"],
        [f"{GAZETTE}:13.4.6@p890:0"],
        "P_PLAIN",
        "Household industries from the annexure lists are allowed in residential premises.",
    ),
]

# --- 25 general questions: no location ------------------------------------------

GENERAL = [
    q(
        "gen-01",
        "Does the 2047 plan take over from the 2021 one?",
        "general",
        [f"{FAQ}:Q2@p2:0"],
        [f"{FAQ}:Q1@p2:0"],
        None,
        "Yes, but plans approved earlier stay approved.",
    ),
    q(
        "gen-02",
        "From what date is the new master plan in force?",
        "general",
        [f"{FAQ}:Q1@p2:0"],
        [],
        None,
        "From the date it was notified in the official gazette, 20 August 2026.",
    ),
    q(
        "gen-03",
        "How wide is the band along a metro line where the transit development rules apply?",
        "general",
        [f"{GAZETTE}:4.2.1:0"],
        [f"{FAQ}:Q1@p11:0"],
        None,
        "500 m either side of the centre line, plus a 500 m radius around major stations.",
    ),
    q(
        "gen-04",
        "What is the smallest plot that can be developed under the transit oriented policy?",
        "general",
        [f"{GAZETTE}:4.2.1:0"],
        [f"{FAQ}:Q3@p11:0"],
        None,
        "2,000 sqm.",
    ),
    q(
        "gen-05",
        "Where does the transit oriented development policy not apply?",
        "general",
        [f"{GAZETTE}:4.2.2:0"],
        [f"{FAQ}:Q2@p11:0"],
        None,
        "Zone O and buffers, low density areas, monument prohibited areas and other sensitive areas.",
    ),
    q(
        "gen-06",
        "Which road is the high density corridor built along?",
        "general",
        [f"{GAZETTE}:4.3.1:0"],
        [f"{FAQ}:Q1@p15:0", f"{GAZETTE}:1.7.1@p666:0"],
        None,
        "Urban Extension Road II.",
    ),
    q(
        "gen-07",
        "What floor area ratio can a residential project get in the high density corridor?",
        "general",
        [f"{FAQ}:Q13@p16:0"],
        [f"{GAZETTE}:4.3.3@p758:0"],
        None,
        "The FAQ gives the permissible FAR by use for HDC plots.",
    ),
    q(
        "gen-08",
        "Which planning zones does the land pooling policy cover?",
        "general",
        [f"{GAZETTE}:4.1.1:0"],
        [f"{FAQ}:Q3@p8:0"],
        None,
        "K-I, L, N, P-II, part of J and part of P-I.",
    ),
    q(
        "gen-09",
        "What charges does a landowner pay under land pooling?",
        "general",
        [f"{FAQ}:Q11@p9:0"],
        [f"{GAZETTE}:4.1.2:0"],
        None,
        "Development charges, plus other applicable charges.",
    ),
    q(
        "gen-10",
        "May anything at all be built on the active floodplain of the river?",
        "general",
        [f"{GAZETTE}:3.1.2@p681:0"],
        [],
        None,
        "No construction; recreational use only, with limited public uses by permission.",
    ),
    q(
        "gen-11",
        "Which planning zone covers the river and its banks?",
        "general",
        [f"{GAZETTE}:1.7.2:0"],
        [],
        None,
        "Zone O, named River Yamuna / Riverfront.",
    ),
    q(
        "gen-12",
        "What did the High Court tell DDA to do about illegal building on the river bank?",
        "general",
        [f"{DHC}:6:0"],
        [f"{DHC}:7:0"],
        None,
        "The Vice Chairman was made nodal officer and told to remove all encroachments.",
    ),
    q(
        "gen-13",
        "Who was appointed to coordinate the agencies on the Yamuna encroachment case?",
        "general",
        [f"{DHC}:6:0"],
        [],
        None,
        "The Vice Chairman of DDA, as nodal officer.",
    ),
    q(
        "gen-14",
        "What is the smallest plot that can be redeveloped in a commercial area?",
        "general",
        [f"{GAZETTE}:4.5.3:0"],
        [f"{FAQ}:Q5@p2:0"],
        None,
        "1,000 sqm for commercial, industrial and PSP; 3,000 sqm for residential.",
    ),
    q(
        "gen-15",
        "By how much can the floor area ratio go up when an area is regenerated?",
        "general",
        [f"{GAZETTE}:4.5.3:0"],
        [],
        None,
        "Up to 1.5 times the base FAR.",
    ),
    q(
        "gen-16",
        "Is rebuilding allowed on a plotted residential property?",
        "general",
        [f"{FAQ}:Q6@p3:0"],
        [],
        None,
        "Only reconstruction at the permitted FAR; redevelopment is not allowed.",
    ),
    q(
        "gen-17",
        "What is the permitted floor area ratio and smallest plot for a group housing scheme?",
        "general",
        [f"{GAZETTE}:7.2.2@p815:0"],
        [f"{FAQ}:Q1@p5:0", f"{GAZETTE}:7.1:0"],
        None,
        "FAR 200 and 3,000 sqm, or 2,000 sqm in Lal Dora, on an 18 m road.",
    ),
    q(
        "gen-18",
        "What is a studio apartment under this plan?",
        "general",
        [f"{GAZETTE}:7.1:0"],
        [],
        None,
        "A residential unit with a carpet area of 40 to 60 sqm.",
    ),
    q(
        "gen-19",
        "How big does a local shopping centre site have to be?",
        "general",
        [f"{GAZETTE}:8.1.2@p823:0"],
        [],
        None,
        "3,000 sqm with an 18 m right of way; a convenience centre needs 1,000 sqm.",
    ),
    q(
        "gen-20",
        "Can a hotel be built on a commercial plot, and what are its limits?",
        "general",
        [f"{GAZETTE}:8.3.2@p830:0"],
        [f"{GAZETTE}:8.3.1:0"],
        None,
        "Yes; chapter 8 sets hotel coverage, FAR and height.",
    ),
    q(
        "gen-21",
        "Can an industrial plot be switched to commercial use?",
        "general",
        [f"{GAZETTE}:9.1.3:0"],
        [],
        None,
        "Yes, use conversion to commercial and PSP use is possible on conditions.",
    ),
    q(
        "gen-22",
        "Is extra floor space available for housing factory workers?",
        "general",
        [f"{GAZETTE}:9.1.2@p836:0"],
        [],
        None,
        "Yes: plots of 5,000 sqm and above can take an extra 15% FAR for worker housing.",
    ),
    q(
        "gen-23",
        "Where do I look up which activities are allowed on a particular kind of premise?",
        "general",
        [f"{FAQ}:Q7@p3:0"],
        [f"{GAZETTE}:Annexure 21@p966:0", f"{FAQ}:Q3@p2:0"],
        None,
        "Annexures 18 to 22 of the plan list permitted use premises and activities.",
    ),
    q(
        "gen-24",
        "What rules govern a petrol pump: plot size, coverage and road width?",
        "general",
        [f"{GAZETTE}:11.1.1@p855:0"],
        [f"{GAZETTE}:11.1.1@p854:0"],
        None,
        "At least a 24 m road, 20% coverage, FAR 40, and a plot of at least 30 m by 36 m.",
    ),
    q(
        "gen-25",
        "How many planning zones is Delhi divided into?",
        "general",
        [f"{GAZETTE}:1.7.2:0"],
        [],
        None,
        "17, lettered A to P with no zone I.",
    ),
]

# --- 10 that should be abstained on ---------------------------------------------

ABSTAIN = [
    q(
        "abs-01",
        "How much property tax will I owe on a flat in Rohini?",
        "abstain",
        [],
        [],
        None,
        "Not in the corpus: property tax is a municipal matter, not the master plan.",
        should_abstain=True,
        notes="Topic outside the corpus.",
    ),
    q(
        "abs-02",
        "What is the permitted floor space index in Mumbai?",
        "abstain",
        [],
        [],
        None,
        "Not in the corpus: these documents cover Delhi only.",
        should_abstain=True,
        notes="Another city.",
    ),
    q(
        "abs-03",
        "Can my landlord raise my rent this year?",
        "abstain",
        [],
        [],
        None,
        "Not in the corpus: rent control is separate legislation.",
        should_abstain=True,
        notes="Topic outside the corpus.",
    ),
    q(
        "abs-04",
        "What can I build on my plot here?",
        "abstain",
        [],
        [],
        "P_OUT",
        "The point is outside Delhi, so this plan does not apply to it.",
        should_abstain=True,
        notes="Point outside Delhi; should abstain with reason outside_delhi before any LLM call.",
    ),
    q(
        "abs-05",
        "How much would a 200 sqm plot here sell for?",
        "abstain",
        [],
        [],
        "P_TOD",
        "Not in the corpus: the plan sets rules, not prices.",
        should_abstain=True,
        notes="Inside Delhi but the documents do not settle it.",
    ),
    q(
        "abs-06",
        "Which bank will give me a loan to build on this land?",
        "abstain",
        [],
        [],
        "P_LP",
        "Not in the corpus: nothing in these documents is about finance.",
        should_abstain=True,
    ),
    q(
        "abs-07",
        "How long will the authority actually take to answer my file in practice?",
        "abstain",
        [],
        [],
        "P_TOD_2",
        "Not settled: the plan gives a 60 day limit but says nothing about real waiting times.",
        should_abstain=True,
        notes="A stated limit exists but the question asks about practice, which the documents do not cover.",
    ),
    q(
        "abs-08",
        "Will my building plan be approved?",
        "abstain",
        [],
        [],
        "P_PLAIN",
        "Not answerable: no document can say whether a particular application will succeed.",
        should_abstain=True,
    ),
    q(
        "abs-09",
        "What are the rules for building in Gurugram just across the border?",
        "abstain",
        [],
        [],
        None,
        "Not in the corpus: Gurugram is in Haryana and outside this plan.",
        should_abstain=True,
    ),
    q(
        "abs-10",
        "Who won the court case about the Yamuna floodplain in the end?",
        "abstain",
        [],
        [],
        None,
        "Not settled: the order gives directions and disposes of the petition, it names no winner.",
        should_abstain=True,
        notes="Adjacent to the corpus but the documents do not answer it.",
    ),
]

ALL_QUESTIONS = LOCATION + GENERAL + ABSTAIN


# --- the checks -----------------------------------------------------------------

WORD = re.compile(r"[a-z0-9]+")


def words_of(text: str) -> list[str]:
    """The words of a piece of text, lower case, punctuation dropped."""
    return WORD.findall(text.lower())


def ngrams(words: list[str], size: int) -> set[tuple[str, ...]]:
    """Every run of `size` consecutive words."""
    return {tuple(words[index : index + size]) for index in range(len(words) - size + 1)}


def leakage(question: str, chunk_texts: list[str], size: int = MAX_SHARED_WORDS + 1) -> list[str]:
    """Runs of `size` words the question shares with any of its chunks."""
    asked = ngrams(words_of(question), size)
    if not asked:
        return []
    shared: set[tuple[str, ...]] = set()
    for text in chunk_texts:
        shared |= asked & ngrams(words_of(text), size)
    return sorted(" ".join(run) for run in shared)


#: Words that would give a location question away. A location question that contains
#: one of these is not testing the location step, it is just a keyword search.
ZONE_WORDS = (
    "tod",
    "transit oriented",
    "transit-oriented",
    "high density",
    "high-density",
    "hdc",
    "uer",
    "urban extension",
    "land pooling",
    "pooled land",
    "zone o",
    "yamuna",
    "floodplain",
    "flood plain",
)


def names_a_zone(question: str) -> list[str]:
    """Zone words a location question gives away, which should be none."""
    lowered = question.lower()
    return [word for word in ZONE_WORDS if word in lowered]


def main() -> int:
    """Draft the questions, check them, and write the file."""
    use_utf8_output()
    chunks = {chunk["chunk_id"]: chunk for chunk in read_chunks(settings.processed_dir / "chunks.jsonl")}
    points_path = settings.project_root / "eval" / "points.json"
    if not points_path.exists():
        print(f"{points_path.as_posix()} is missing. Run: uv run python scripts/08_eval_points.py")
        return 1
    points = {point["name"]: point for point in json.loads(points_path.read_text(encoding="utf-8"))}

    problems: list[str] = []
    records: list[dict] = []
    seen_ids: set[str] = set()

    for item in ALL_QUESTIONS:
        record = dict(item)

        if record["id"] in seen_ids:
            problems.append(f"{record['id']}: duplicate id")
        seen_ids.add(record["id"])

        # attach the coordinates of the named point
        name = record["point_name"]
        if name is None:
            record["lat"], record["lon"] = None, None
        elif name not in points:
            problems.append(f"{record['id']}: unknown point {name!r}")
            record["lat"], record["lon"] = None, None
        else:
            record["lat"] = points[name]["lat"]
            record["lon"] = points[name]["lon"]

        # every expected and acceptable id has to exist
        for field in ("expected_chunk_ids", "acceptable_chunk_ids"):
            for chunk_id in record[field]:
                if chunk_id not in chunks:
                    problems.append(f"{record['id']}: {field} names a missing chunk {chunk_id!r}")

        # a non-abstain question needs 1 to 3 expected chunks
        if record["category"] != "abstain":
            if not 1 <= len(record["expected_chunk_ids"]) <= 3:
                problems.append(
                    f"{record['id']}: has {len(record['expected_chunk_ids'])} expected chunk ids, "
                    "which should be 1 to 3"
                )
        elif record["expected_chunk_ids"]:
            problems.append(f"{record['id']}: an abstain question should expect no chunks")

        # a location question needs a point and must not name its zone
        if record["category"] == "location":
            if record["lat"] is None:
                problems.append(f"{record['id']}: a location question needs a point")
            given_away = names_a_zone(record["question"])
            if given_away:
                problems.append(
                    f"{record['id']}: names its zone ({', '.join(given_away)}), so the "
                    "location step is not being tested"
                )

        # the leakage rule
        texts = [
            chunks[chunk_id]["text"]
            for chunk_id in record["expected_chunk_ids"] + record["acceptable_chunk_ids"]
            if chunk_id in chunks
        ]
        shared = leakage(record["question"], texts)
        record["shared_word_runs"] = shared
        if shared:
            problems.append(
                f"{record['id']}: shares {MAX_SHARED_WORDS + 1}+ words with its chunks: "
                + "; ".join(f'"{run}"' for run in shared)
            )

        records.append(record)

    out_path = settings.project_root / "eval" / "questions_draft.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    counts: dict[str, int] = {}
    for record in records:
        counts[record["category"]] = counts.get(record["category"], 0) + 1
    print(
        markdown_table(
            ("category", "questions", "with a point", "should abstain"),
            [
                [
                    category,
                    str(counts[category]),
                    str(sum(1 for r in records if r["category"] == category and r["lat"] is not None)),
                    str(sum(1 for r in records if r["category"] == category and r["should_abstain"])),
                ]
                for category in ("location", "general", "abstain")
            ],
        )
    )
    print()
    print(f"{len(records)} questions drafted, all with verified=false.")
    print(
        f"leakage check: no run of {MAX_SHARED_WORDS + 1} or more words may be copied "
        "from an expected or acceptable chunk."
    )
    if problems:
        print(f"{len(problems)} PROBLEM(S) to fix:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("All checks passed.")
    print(f"wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
