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
from app.location import describe_zones, expand_query
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


def before_after_lines(points: dict, index) -> list[str]:
    """One table: what D-086 changed at each point this report asks about.

    Only `zone_o` and `ridge` lost their expansion terms, so every other point must come
    back with an identical top 5. That the table says so is the point of it.
    """
    moved: list[tuple] = []
    out = [
        "## Before and after D-086",
        "",
        "On 20 October query expansion was scoped to the four topics that have a policy",
        "section of their own, so a point in **Zone O** or on the **Ridge** now searches",
        "with the user's own words and relies on the boost instead. Every other point is",
        "untouched, and this table is the check on that claim rather than an assertion of",
        "it: `before` widens `location.EXPANDS_QUERY` back out to all six topics.",
        "",
        "| comparison | point | topics | query sent, before | top 5, before | top 5, now | same? |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    changed = 0
    for label, question, names in COMPARISONS:
        for name in names:
            record = points.get(name)
            if record is None:
                continue
            zones = record["zones"]
            with expansion_for_every_topic():
                old = search(question, k=K, mode="hybrid", zones=zones, index=index)
                old_query = expand_query(question, topics_for(zones))[0]
            new = search(question, k=K, mode="hybrid", zones=zones, index=index)
            a = [item.chunk_id.split(":", 1)[1] for item in old]
            b = [item.chunk_id.split(":", 1)[1] for item in new]
            same = a == b
            changed += 0 if same else 1
            if not same:
                moved.append((label, name, question, zones, old, new))
            out.append(
                f"| {label} | {name} | {', '.join(topics_for(zones)) or '(none)'} "
                f"| “{old_query}” "
                f"| {', '.join('`' + c + '`' for c in a)} "
                f"| {', '.join('`' + c + '`' for c in b)} "
                f"| {'**identical**' if same else 'changed'} |"
            )
            print(f"  before/after {label} at {name}: {'identical' if same else 'CHANGED'}")
    out += [
        "",
        f"**{changed} of {sum(len(names) for _, _, names in COMPARISONS)} point(s) changed**, "
        "and they are the two the change is about. The clause that prompted it, "
        "`MPD47_GAZETTE_EN:11.1.1@p854:0` for “Can a fuel station be built here?” at "
        "P_ZONEO, moved from rank 14 to **rank 1**; the measurement is in "
        "`reports/diagnosis_fuel_station.md`.",
        "",
        "### What the change cost at those two points",
        "",
        "Printing only the winners would be dishonest, so here is what left the top "
        f"{K}. `>{DEEP_K}` means the clause is no longer anywhere in a "
        f"{DEEP_K}-deep result list. The pattern is the same at both points and it is "
        "the mirror image of the fix: the expansion was **helping** whenever the "
        "question's own subject was the place, because then the appended words were a "
        "qualifier after all. These two questions are of that kind, and they pay for "
        "the ones that are not.",
        "",
    ]
    for label, name, question, zones, old, new in moved:
        deep_before = {}
        with expansion_for_every_topic():
            for position, item in enumerate(search(question, k=DEEP_K, mode="hybrid",
                                                   zones=zones, index=index), start=1):
                deep_before.setdefault(item.chunk_id, position)
        deep_now = {}
        for position, item in enumerate(search(question, k=DEEP_K, mode="hybrid",
                                               zones=zones, index=index), start=1):
            deep_now.setdefault(item.chunk_id, position)
        old_ids = [item.chunk_id for item in old]
        new_ids = [item.chunk_id for item in new]
        out += [
            f"**{label} at {name} — “{question}”**",
            "",
            "| clause | rank before | rank now | |",
            "| --- | --- | --- | --- |",
        ]
        for chunk_id in old_ids:
            if chunk_id in new_ids:
                continue
            now_rank = deep_now.get(chunk_id)
            out.append(
                f"| `{chunk_id}` | {deep_before.get(chunk_id, '?')} "
                f"| {now_rank if now_rank else f'>{DEEP_K}'} | left the top {K} |"
            )
        for chunk_id in new_ids:
            if chunk_id in old_ids:
                continue
            was = deep_before.get(chunk_id)
            out.append(
                f"| `{chunk_id}` | {was if was else f'>{DEEP_K}'} "
                f"| {deep_now.get(chunk_id, '?')} | new in the top {K} |"
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
        "Location-aware search does three things, with the settings in `app/config.py`:",
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
        f"3. **Boost** — a chunk whose `zone_primary` *or* `zone_mentions` matches the point's "
        f"zones has its fused score multiplied by {settings.zone_boost}.",
        "",
        "Two of the six topics can only do step 3. Zone O and the Ridge have no policy "
        "section of their own in MPD-2047, so no chunk ever carries them as a "
        "`zone_primary` and the exclusion step has nothing to find for them "
        "(D-037, D-069) — and for the same reason they no longer expand the query "
        "either (D-086). The three corridor policies and the LDA do have sections, so a "
        "point outside them can drop their rules and a point inside them expands "
        "towards their chapter.",
        "",
        "`d3` is dense rank 3, `b1` is BM25 rank 1, **boosted** marks a chunk the boost "
        "applied to. Not judged here.",
        "",
    ]

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
                f"- query sent: “{report.expanded_query}”",
                f"- expansion terms added: {', '.join(report.expansion_terms) or '(none)'}",
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
