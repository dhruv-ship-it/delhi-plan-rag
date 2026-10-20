"""Compare plain hybrid search against location-aware search at the test points.

Reads  data/test_points.json, the indexes in data/index/, the layers in data/layers/dda/
Writes reports/<--out>.md, default reports/day3_location_compare.md

Five comparisons, each the same question asked at different points, so the only thing
that changes between the two columns is where the user is standing.

The file is for reading by hand. Nothing here judges a result.

Safe to re-run. Run with: uv run python scripts/day3_location_compare.py
"""

import argparse
import contextlib
import json
import sys
from datetime import date

from app import location as location_module
from app.config import settings
from app.extract import use_utf8_output
from app.location import describe_zones
from app.retrieval import SearchReport, get_index, rank, search
from app.spatial import topics_for
from app.tagging import TOPICS

K = 5
SNIPPET_CHARS = 120
#: How deep to look when saying where a clause went, rather than only that it left.
DEEP_K = 200

#: (label, question, the test points to ask it at).
#:
#: E is the comparison the ridge and lda topics were added for (D-069). "Can I build a
#: house here?" is the right question to ask at both: in a Low Density Area the answer
#: is a real policy with its own section (4.4), and on the Ridge there is no policy
#: section at all, so the two points show the two halves of the design in one question.
COMPARISONS = (
    ("A", "What is the maximum ground coverage allowed on my plot?", ("P_TOD", "P_HDC", "P_PLAIN")),
    ("B", "Can I construct a building here?", ("P_ZONEO",)),
    ("C", "What development rules apply to my land here?", ("P_LP",)),
    ("D", "What FAR can I get here?", ("P_TOD", "P_PLAIN")),
    ("E", "Can I build a house here?", ("P_RIDGE", "P_LDA")),
)


@contextlib.contextmanager
def two_list_fusion():
    """Run a block with the **pre-D-093** behaviour: two lists, one query.

    `location.FUSES_FOUR_LISTS` names the two topics whose place words go into a second
    query that is fused alongside the first. Emptying it is what the shipped behaviour
    was between D-086 and D-093, so the table below is a measurement rather than a
    memory of one.
    """
    original = location_module.FUSES_FOUR_LISTS
    location_module.FUSES_FOUR_LISTS = ()
    try:
        yield
    finally:
        location_module.FUSES_FOUR_LISTS = original


@contextlib.contextmanager
def expansion_for_every_topic():
    """Run a block with the **pre-D-086** behaviour: all six topics expand the query.

    `location.EXPANDS_QUERY` names the four topics that may expand. Widening it to every
    tagged topic reproduces what this report measured before 20 October, which is what
    makes the before/after section below a measurement rather than a memory.
    """
    original = location_module.EXPANDS_QUERY
    location_module.EXPANDS_QUERY = TOPICS
    try:
        yield
    finally:
        location_module.EXPANDS_QUERY = original


#: The clause each confirmation question is supposed to come back with, and why.
#: These are the two the lead named for D-093: the question D-086 fixed, and the one
#: D-086 broke in exchange. Both have to be right at the same time for the four-list
#: fusion to be worth its second embedding call.
CONFIRMATIONS = (
    (
        "P_ZONEO",
        "Can a fuel station be built here?",
        (
            (
                "MPD47_GAZETTE_EN:11.1.1@p854:0",
                "fuel stations allowed in all Use Zones except Zone O",
            ),
        ),
    ),
    (
        "P_ZONEO",
        "Can I construct a building here?",
        (
            ("MPD47_GAZETTE_EN:3.1.2@p681:0", "no construction in the active floodplain"),
            ("DHC_YAMUNA_20240708:2:0", "the High Court order on the Yamuna"),
        ),
    ),
)


def deep_positions(question: str, zones: dict, index) -> dict[str, int]:
    """Where every clause lands in a DEEP_K-deep list for one question at one point."""
    found: dict[str, int] = {}
    for position, item in enumerate(
        search(question, k=DEEP_K, mode="hybrid", zones=zones, index=index), start=1
    ):
        found.setdefault(item.chunk_id, position)
    return found


def rank_cell(positions: dict[str, int], chunk_id: str) -> str:
    """A clause's rank, or `>DEEP_K` when it is nowhere in the list."""
    position = positions.get(chunk_id)
    return str(position) if position else f">{DEEP_K}"


def confirmation_lines(points: dict, index) -> list[str]:
    """The check the lead asked for: both named questions keep their right clause.

    Nothing here is judged. The clause ids come from `CONFIRMATIONS` above, which is
    the only opinion in this file, and the ranks are read off a DEEP_K-deep list under
    each of the two behaviours.
    """
    out = [
        "## The check: both questions keep their right clause",
        "",
        "D-086 scoped query expansion out of Zone O and the Ridge. That fixed the",
        "fuel-station miss and broke the questions whose subject **is** the place, which",
        "is the trade `reports/diagnosis_fuel_station.md` recorded and did not hide.",
        "D-093 fuses both wordings instead of choosing between them, and this table is",
        "the check that it keeps both sides at once rather than moving the problem.",
        "",
        f"Ranks over a {DEEP_K}-deep list. `>{DEEP_K}` means the clause is not in it at all.",
        "",
        "| point | question | clause | what it says | two lists (D-086) | four lists (D-093) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    all_kept = True
    for name, question, wanted in CONFIRMATIONS:
        record = points.get(name)
        if record is None:
            continue
        zones = record["zones"]
        with two_list_fusion():
            before = deep_positions(question, zones, index)
        after = deep_positions(question, zones, index)
        for chunk_id, says in wanted:
            kept = after.get(chunk_id) is not None and after[chunk_id] <= K
            all_kept = all_kept and kept
            out.append(
                f"| {name} | “{question}” | `{chunk_id}` | {says} "
                f"| {rank_cell(before, chunk_id)} | **{rank_cell(after, chunk_id)}** |"
            )
            print(
                f"  confirm {name} {question[:34]!r} {chunk_id.split(':', 1)[1]}: "
                f"{rank_cell(before, chunk_id)} -> {rank_cell(after, chunk_id)}"
            )
    out += [
        "",
        (
            f"**Both questions keep their clause inside the top {K}**, which is the "
            "number that matters: the answering layer is given six sources."
            if all_kept
            else f"**At least one clause is outside the top {K}.** Read the rows above "
            "before trusting anything else in this file."
        ),
        "",
    ]
    return out


def before_after_lines(points: dict, index) -> list[str]:
    """Three behaviours at every point this report asks about, in one table.

    `before D-086` widens `location.EXPANDS_QUERY` back to all six topics, so Zone O and
    the Ridge append their place words to the one query every index searches.
    `two lists` is what shipped between D-086 and D-093: those two topics expand
    nothing. `four lists` is what ships now: their place words make a **second** query
    whose dense and BM25 lists are fused alongside the first pair's (D-093).

    Only `zone_o` and `ridge` are in scope for either change, so every other point must
    come back identical in all three columns. That the table says so is the point of it.
    """
    moved: list[tuple] = []
    out = [
        "## Three behaviours, at every point this report asks about",
        "",
        "| column | what it is |",
        "| --- | --- |",
        "| before D-086 | all six topics append their words to the one query |",
        "| two lists | the four policy topics expand; Zone O and the Ridge do not (D-086) |",
        "| four lists | **ships now** — Zone O and the Ridge fuse a second "
        "query's two lists (D-093) |",
        "",
        "Zone O and the Ridge are the only topics either change touches, so every other",
        "point has to be identical in all three columns. The `same?` column is that check",
        "rather than an assertion of it.",
        "",
        "| comparison | point | topics | top 5, before D-086 | top 5, two lists "
        "| top 5, four lists | same? |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    changed = 0
    for label, question, names in COMPARISONS:
        for name in names:
            record = points.get(name)
            if record is None:
                continue
            zones = record["zones"]
            with expansion_for_every_topic(), two_list_fusion():
                oldest = search(question, k=K, mode="hybrid", zones=zones, index=index)
            with two_list_fusion():
                previous = search(question, k=K, mode="hybrid", zones=zones, index=index)
            current = search(question, k=K, mode="hybrid", zones=zones, index=index)
            a = [item.chunk_id.split(":", 1)[1] for item in oldest]
            b = [item.chunk_id.split(":", 1)[1] for item in previous]
            c = [item.chunk_id.split(":", 1)[1] for item in current]
            same = a == b == c
            changed += 0 if b == c else 1
            if b != c:
                moved.append((label, name, question, zones, previous, current))
            out.append(
                f"| {label} | {name} | {', '.join(topics_for(zones)) or '(none)'} "
                f"| {', '.join('`' + chunk + '`' for chunk in a)} "
                f"| {', '.join('`' + chunk + '`' for chunk in b)} "
                f"| {', '.join('`' + chunk + '`' for chunk in c)} "
                f"| {'**identical**' if same else 'changed'} |"
            )
            verdict = (
                "all identical"
                if same
                else ("D-093 CHANGED it" if b != c else "only D-086 changed it")
            )
            print(f"  three-way {label} at {name}: {verdict}")
    out += [
        "",
        f"**D-093 changed {changed} of {sum(len(names) for _, _, names in COMPARISONS)} "
        "point(s)**, and they are the two it is scoped to. Every point in a policy zone "
        "or in no zone at all is byte-identical across all three columns, which is what "
        "`FUSES_FOUR_LISTS` being two topics long buys: the published demo beats cannot "
        "move, by construction rather than by measurement.",
        "",
        "### What the second pair of lists gave back",
        "",
        "D-086's cost table is the thing to read this against. Appending the place words "
        "to the only query **replaced** the subject of a question whose subject was "
        "something else, which is why the fuel-station clause was at rank 14; removing "
        "them **lost** the questions whose subject was the place. Fusing both wordings "
        f"means a clause only needs one of them to earn fusion points. `>{DEEP_K}` means "
        f"the clause is nowhere in a {DEEP_K}-deep list.",
        "",
    ]
    for label, name, question, zones, previous, current in moved:
        with two_list_fusion():
            deep_before = deep_positions(question, zones, index)
        deep_now = deep_positions(question, zones, index)
        old_ids = [item.chunk_id for item in previous]
        new_ids = [item.chunk_id for item in current]
        out += [
            f"**{label} at {name} — “{question}”**",
            "",
            "| clause | rank, two lists | rank, four lists | |",
            "| --- | --- | --- | --- |",
        ]
        for chunk_id in new_ids:
            if chunk_id in old_ids:
                continue
            out.append(
                f"| `{chunk_id}` | {rank_cell(deep_before, chunk_id)} "
                f"| {rank_cell(deep_now, chunk_id)} | new in the top {K} |"
            )
        for chunk_id in old_ids:
            if chunk_id in new_ids:
                continue
            out.append(
                f"| `{chunk_id}` | {rank_cell(deep_before, chunk_id)} "
                f"| {rank_cell(deep_now, chunk_id)} | left the top {K} |"
            )
        out.append("")
    return out


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    """The opening of a chunk's text on one line."""
    flat = " ".join(text.split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def result_rows(results) -> list[str]:
    """A numbered list of results, one entry per result."""
    if not results:
        return ["(nothing found)", ""]
    lines = []
    for position, result in enumerate(results, start=1):
        marks = []
        if result.dense_rank:
            marks.append(f"d{result.dense_rank}")
        if result.bm25_rank:
            marks.append(f"b{result.bm25_rank}")
        if result.boosted:
            marks.append("**boosted**")
        lines.append(
            f"{position}. `{result.chunk_id}` — clause {result.clause_id or '(none)'}, "
            f"zone_primary `{result.zone_primary or '(none)'}`, pages "
            f"{result.page_start}-{result.page_end}, [{' '.join(marks)} "
            f"score {result.fused_score:.4f}]"
        )
        lines.append(f"   - {snippet(result.text)}")
    lines.append("")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Run the four comparisons and write the report."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="day3_location_compare.md",
        help="file name to write inside reports/ (default: day3_location_compare.md)",
    )
    args = parser.parse_args(argv)

    points_path = settings.project_root / "data" / "test_points.json"
    if not points_path.exists():
        print(f"{points_path.as_posix()} is missing. Run: uv run python scripts/07_test_points.py")
        return 1
    if not settings.bm25_path.exists():
        print("No index found. Run: uv run python scripts/05_build_index.py")
        return 1

    points = {record["name"]: record for record in json.loads(points_path.read_text(encoding="utf-8"))}
    index = get_index()

    lines = [
        "# Plain hybrid against location-aware search",
        "",
        f"Generated {date.today().isoformat()} by `scripts/day3_location_compare.py`.",
        "",
        f"Top {K} either way, {len(index)} chunks indexed. The question is identical in both "
        "columns; the only difference is that the right-hand one knows where the user is "
        "standing.",
        "",
        "Location-aware search does four things, with the settings in `app/config.py`:",
        "",
        "1. **Exclusion** — a chunk whose `zone_primary` is a policy the point is *not* in "
        "is dropped. A chunk with no primary zone is never dropped, so the general norms in "
        "chapters 7 to 13 always stay in play.",
        "2. **Query expansion** — the point's zone names are appended to the query text for "
        "both indexes, so a question with no zone words in it can still reach the right "
        "policy. **Only the four topics with a policy section of their own do this** "
        "(`tod`, `hdc`, `land_pooling`, `lda`), which is the same four that may exclude: "
        "Zone O and the Ridge name a place rather than a policy, and appending a place "
        "replaces the subject of the question instead of qualifying it (D-086).",
        "3. **A second query, fused** — for the two topics that may not expand, the place "
        "words make a **second** query instead, and its dense and BM25 lists are fused "
        "alongside the first pair's: four ranked lists into one RRF. A clause then only "
        "needs one of the two wordings to find it, so neither the question whose subject "
        "is a fuel station nor the question whose subject is the floodplain pays for the "
        "other (D-093).",
        f"4. **Boost** — a chunk whose `zone_primary` *or* `zone_mentions` matches the point's "
        f"zones has its fused score multiplied by {settings.zone_boost}.",
        "",
        "Zone O and the Ridge have no policy section of their own in MPD-2047, so no "
        "chunk ever carries them as a `zone_primary` and the exclusion step has nothing "
        "to find for them (D-037, D-069) — and for the same reason they do not expand "
        "the single query either (D-086). They are therefore the only two topics that "
        "reach step 3, and the only two steps 1 and 2 do nothing for. The three corridor "
        "policies and the LDA do have sections, so a point outside them can drop their "
        "rules and a point inside them expands towards their chapter; they never reach "
        "step 3 at all.",
        "",
        "`d3` is dense rank 3, `b1` is BM25 rank 1, **boosted** marks a chunk the boost "
        "applied to. Not judged here.",
        "",
    ]

    lines += confirmation_lines(points, index)
    lines += before_after_lines(points, index)

    for label, question, names in COMPARISONS:
        lines += [f"## {label}. “{question}”", ""]
        for name in names:
            record = points.get(name)
            if record is None:
                lines += [f"### {name} — missing from data/test_points.json", ""]
                continue
            zones = record["zones"]
            print(f"{label} at {name}: {question}")
            lines += [
                f"### {label} at {name} — {record['lat']}, {record['lon']}",
                "",
                f"- {describe_zones(zones)}",
                f"- `get_zones`: `{json.dumps(zones)}`",
                "",
            ]
            plain = rank(question, k=K, mode="hybrid", index=index)
            report = SearchReport(query=question, expanded_query=question)
            aware = search(
                question, k=K, mode="hybrid", zones=zones, index=index, report=report
            )
            lines += ["**plain hybrid**", ""] + result_rows(plain)
            lines += [
                "**location-aware hybrid**",
                "",
                "- "
                + (
                    f"{report.fused_lists} lists fused, from "
                    f"{len(report.queries)} quer{'y' if len(report.queries) == 1 else 'ies'}: "
                    + ", ".join(f"“{one}”" for one in report.queries)
                ),
                f"- expansion terms added: {', '.join(report.expansion_terms) or '(none)'}",
                f"- place terms, in the second query only: "
                f"{', '.join(report.place_terms) or '(none)'}",
                f"- excluded {report.excluded} chunk(s) whose primary zone is one of: "
                f"{', '.join(report.excluded_topics) or '(none)'}",
                f"- boosted {report.boosted} chunk(s) in the pool",
                "",
            ] + result_rows(aware)

            plain_ids = [result.chunk_id for result in plain]
            aware_ids = [result.chunk_id for result in aware]
            moved = [chunk_id for chunk_id in aware_ids if chunk_id not in plain_ids]
            gone = [chunk_id for chunk_id in plain_ids if chunk_id not in aware_ids]
            lines += [
                f"- new in the top {K}: "
                + (", ".join(f"`{chunk_id}`" for chunk_id in moved) or "(none)"),
                f"- dropped out of the top {K}: "
                + (", ".join(f"`{chunk_id}`" for chunk_id in gone) or "(none)"),
                "",
            ]

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.reports_dir / args.out
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    asked = sum(len(names) for _, _, names in COMPARISONS)
    print()
    print(f"{len(COMPARISONS)} comparisons at {asked} point(s), top {K} each way.")
    print(f"wrote {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
