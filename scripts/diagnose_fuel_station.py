"""Find out why clause 11.1.1 does not come back for the fuel-station question at P_ZONEO.

    uv run python scripts/diagnose_fuel_station.py
    uv run python scripts/diagnose_fuel_station.py --out somewhere/else.md

The finding this script investigates is limitation 4 of docs/PROJECT_STATUS.md. At
P_ZONEO, "Can a fuel station be built here?" does not return
`MPD47_GAZETTE_EN:11.1.1@p854:0` — the clause that says fuel stations "may be permitted
in all Use Zones except Recreational ... and Zone O" — while the same question asked
with **no point** has it at rank 1 in hybrid mode. So the location path is costing it,
and this script says which of the three location steps is responsible.

It changes nothing. It runs the real `search()` through the real indexes and only turns
the three location settings off one at a time, by swapping `app.location`'s settings for
a copy, so every number below comes from the code that ships rather than from a
re-implementation of it.

Safe to re-run: it reads the indexes, makes no network call and writes one report.
"""

import argparse
import contextlib
import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import location as location_module  # noqa: E402
from app.config import settings  # noqa: E402
from app.extract import use_utf8_output  # noqa: E402
from app.location import expand_query  # noqa: E402
from app.retrieval import SearchReport, get_index, search  # noqa: E402
from app.spatial import get_zones, topics_for  # noqa: E402
from app.tagging import TOPICS  # noqa: E402

#: The clause the question is about, and the one chunk of it that carries the permission
#: sentence. The other four chunks of 11.1.1 are reported too, because "11.1.1 came back"
#: is only a useful claim if it names which part.
TARGET = "MPD47_GAZETTE_EN:11.1.1@p854:0"
TARGET_FAMILY = (
    "MPD47_GAZETTE_EN:11.1.1@p851:0",
    "MPD47_GAZETTE_EN:11.1.1@p852:0",
    "MPD47_GAZETTE_EN:11.1.1@p853:0",
    "MPD47_GAZETTE_EN:11.1.1@p854:0",
    "MPD47_GAZETTE_EN:11.1.1@p855:0",
)

#: The two wordings docs/DEMO.md records as failing.
QUESTIONS = (
    "Can a fuel station be built here?",
    "Can a fuel station be built in Zone O?",
)

#: How deep to look. Far deeper than the six a user sees, because "where did it go" is
#: the question and `k=6` can only answer "not here".
DEEP_K = 200


@contextlib.contextmanager
def location_settings(**changes):
    """Run a block with `app.location`'s settings replaced by a copy.

    The three location knobs are read from `settings` inside `location_aware_search`
    and nowhere else, so swapping the name that module looks them up under is enough
    to turn one step off without touching a file or an environment variable.
    """
    original = location_module.settings
    location_module.settings = dataclasses.replace(original, **changes)
    try:
        yield
    finally:
        location_module.settings = original


@contextlib.contextmanager
def expansion_for_every_topic():
    """Run a block with the **pre-D-086** behaviour: all six topics expand the query.

    The fix shipped on 20 October scopes expansion to `location.EXPANDS_QUERY`, the four
    topics with a policy section of their own. Widening that tuple back out to every
    tagged topic reproduces exactly what the first version of this diagnosis measured,
    so the before/after columns below are still a real comparison and not a memory.
    """
    original = location_module.EXPANDS_QUERY
    location_module.EXPANDS_QUERY = TOPICS
    try:
        yield
    finally:
        location_module.EXPANDS_QUERY = original


def point_of(name: str) -> tuple[float, float]:
    """One named test point from data/test_points.json."""
    records = json.loads((settings.project_root / "data" / "test_points.json").read_text("utf-8"))
    for record in records:
        if record.get("name") == name or record.get("id") == name:
            return float(record["lat"]), float(record["lon"])
    raise SystemExit(f"{name} is not in data/test_points.json")


def positions(results: list, chunk_ids) -> dict[str, dict]:
    """Where each chunk id landed: fused rank, the two pool ranks, score, boosted."""
    found: dict[str, dict] = {}
    for position, result in enumerate(results, start=1):
        if result.chunk_id in chunk_ids:
            found[result.chunk_id] = {
                "fused_rank": position,
                "dense_rank": result.dense_rank,
                "bm25_rank": result.bm25_rank,
                "dense_cosine": result.dense_cosine,
                "bm25_score": result.bm25_score,
                "fused_score": result.fused_score,
                "boosted": result.boosted,
            }
    return found


def pool_positions(index, query: str, depth: int, chunk_ids) -> dict[str, dict]:
    """Where each chunk id sits in the two **raw** pools, before any filtering.

    This is the measurement that separates "exclusion dropped it" from "the query no
    longer finds it": a chunk missing from the raw pool was never there to drop.
    """
    dense = index.dense_pool(query, depth)
    keyword = index.bm25_pool(query, depth)
    dense_at = {chunk_id: n for n, (chunk_id, _) in enumerate(dense, start=1)}
    bm25_at = {chunk_id: n for n, (chunk_id, _) in enumerate(keyword, start=1)}
    return {
        chunk_id: {
            "dense_pool_rank": dense_at.get(chunk_id),
            "bm25_pool_rank": bm25_at.get(chunk_id),
            "dense_pool_size": len(dense),
            "bm25_pool_size": len(keyword),
        }
        for chunk_id in chunk_ids
    }


#: The configurations compared, in the order the report prints them. Each is a label
#: and the settings changes that produce it; `None` means no point at all.
CONFIGURATIONS = (
    ("no point at all (plain hybrid)", None),
    ("**before D-086**: the point, expansion for every topic", "all_six"),
    ("the point, everything on (what ships now)", {}),
    ("the point, no exclusion", {"zone_exclusion": False}),
    ("the point, no boost", {"zone_boost": 1.0}),
    ("the point, no query expansion at all", {"zone_query_expansion": False}),
    ("the point, all three steps off", {
        "zone_exclusion": False,
        "zone_boost": 1.0,
        "zone_query_expansion": False,
    }),
)


def run_one(index, question: str, lat: float, lon: float, changes: dict | None) -> dict:
    """One configuration: the query sent, where 11.1.1 landed, and the top six."""
    report = SearchReport(query=question, expanded_query=question)
    if changes is None:
        results = search(question, k=DEEP_K, mode="hybrid", index=index, report=report)
        query_sent = question
    elif changes == "all_six":
        zones = get_zones(lat, lon)
        with expansion_for_every_topic():
            results = search(
                question, k=DEEP_K, mode="hybrid", zones=zones, index=index, report=report
            )
            query_sent = expand_query(question, topics_for(zones))[0]
    else:
        zones = get_zones(lat, lon)
        with location_settings(**changes):
            results = search(
                question, k=DEEP_K, mode="hybrid", zones=zones, index=index, report=report
            )
            expansion_on = location_module.settings.zone_query_expansion
            query_sent = (
                expand_query(question, topics_for(zones))[0] if expansion_on else question
            )
    return {
        "query_sent": query_sent,
        "excluded": report.excluded,
        "boosted": report.boosted,
        "returned": len(results),
        "where": positions(results, set(TARGET_FAMILY)),
        "pools": pool_positions(index, query_sent, settings.retrieval_pool * 2, [TARGET]),
        "top": [
            (n, item.chunk_id, item.clause_id, round(item.fused_score, 5), item.boosted)
            for n, item in enumerate(results[:6], start=1)
        ],
    }


def rank_cell(where: dict, chunk_id: str) -> str:
    """One table cell: the fused rank, or why there is none."""
    found = where.get(chunk_id)
    if found is None:
        return "**not returned**"
    mark = " (boosted)" if found["boosted"] else ""
    return f"{found['fused_rank']}{mark}"


def lines_for(question: str, runs: list[tuple[str, dict]]) -> list[str]:
    """The report section for one question."""
    out = [f"## {question}", ""]
    out.append("| configuration | query actually searched | 11.1.1@p854 | dense | BM25 | excluded | boosted |")
    out.append("| --- | --- | --- | --- | --- | --- | --- |")
    for label, run in runs:
        found = run["where"].get(TARGET, {})
        dense = found.get("dense_rank")
        keyword = found.get("bm25_rank")
        pool = run["pools"][TARGET]
        dense_text = str(dense) if dense else f"— (raw pool: {pool['dense_pool_rank'] or 'absent'})"
        bm25_text = str(keyword) if keyword else f"— (raw pool: {pool['bm25_pool_rank'] or 'absent'})"
        out.append(
            f"| {label} | `{run['query_sent']}` | {rank_cell(run['where'], TARGET)} "
            f"| {dense_text} | {bm25_text} | {run['excluded']} | {run['boosted']} |"
        )
    out.append("")

    out.append("All five chunks of clause 11.1.1, by fused rank:")
    out.append("")
    out.append("| configuration | " + " | ".join(c.split(":")[-2] for c in TARGET_FAMILY) + " |")
    out.append("| --- | " + " | ".join("---" for _ in TARGET_FAMILY) + " |")
    for label, run in runs:
        cells = " | ".join(rank_cell(run["where"], chunk_id) for chunk_id in TARGET_FAMILY)
        out.append(f"| {label} | {cells} |")
    out.append("")

    for label, run in runs:
        out.append(f"**Top 6, {label}:**")
        out.append("")
        out.append("| rank | chunk | clause | fused | boosted |")
        out.append("| --- | --- | --- | --- | --- |")
        for position, chunk_id, clause, score, boosted in run["top"]:
            out.append(
                f"| {position} | `{chunk_id}` | {clause or '—'} | {score} | "
                f"{'yes' if boosted else 'no'} |"
            )
        out.append("")
    return out


#: The DEMO script's five beats, so the proposal can be checked against the questions
#: this project already publishes answers to. The point of the table is that three of
#: the five must come back **bit-identical**, because their topics keep their expansion.
BEATS = (
    ("beat 1 P_TOD", "P_TOD", "How much of my plot can I build on?"),
    ("beat 2 P_HDC", "P_HDC", "How much of my plot can I build on?"),
    ("beat 3 P_ZONEO", "P_ZONEO", "Is construction allowed here?"),
    ("beat 4 P_LDA", "P_LDA", "What is the maximum ground coverage here?"),
    ("beat 5 P_RIDGE", "P_RIDGE", "Is construction allowed here?"),
)


def beat_lines(index) -> list[str]:
    """What the proposal would do to the five published DEMO beats."""
    out = [
        "## What the fix did to the five DEMO beats",
        "",
        "`before` is expansion for every topic, which is what `docs/DEMO.md` was first",
        "written against. `now` is what ships after D-086, with `zone_o` and `ridge` no",
        "longer expanding. Three of the five are expected to be **identical**, because",
        "`tod`, `hdc` and `lda` keep their expansion.",
        "",
        "| beat | question | top 3, before | top 3, now | same? |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, point_name, question in BEATS:
        lat, lon = point_of(point_name)
        zones = get_zones(lat, lon)
        with expansion_for_every_topic():
            before = search(question, k=3, mode="hybrid", zones=zones, index=index)
        shipped = search(question, k=3, mode="hybrid", zones=zones, index=index)
        a = [item.chunk_id.split(":", 1)[1] for item in before]
        b = [item.chunk_id.split(":", 1)[1] for item in shipped]
        out.append(
            f"| {label} | {question} | {', '.join('`' + c + '`' for c in a)} "
            f"| {', '.join('`' + c + '`' for c in b)} "
            f"| {'**identical**' if a == b else 'changed'} |"
        )
        print(f"  {label:<16} {'identical' if a == b else 'CHANGED'}")
    out.append("")
    return out


def main() -> int:
    """Run every configuration for both wordings and write the report."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="reports/diagnosis_fuel_station_tables.md",
        help="where to write the tables (default reports/diagnosis_fuel_station_tables.md)",
    )
    parser.add_argument("--point", default="P_ZONEO", help="the test point id (default P_ZONEO)")
    args = parser.parse_args()

    lat, lon = point_of(args.point)
    index = get_index()
    zones = get_zones(lat, lon)

    print(f"{args.point} at {lat}, {lon}")
    print(f"zones: {location_module.describe_zones(zones)}")
    print(f"topics: {topics_for(zones)}")
    print(f"{len(index)} chunks; reranker {'on' if settings.reranker_on else 'off'}")
    print()

    sections: list[str] = []
    for question in QUESTIONS:
        runs: list[tuple[str, dict]] = []
        for label, changes in CONFIGURATIONS:
            run = run_one(index, question, lat, lon, changes)
            runs.append((label, run))
            found = run["where"].get(TARGET)
            where = f"rank {found['fused_rank']}" if found else "NOT RETURNED"
            print(f"  {question[:40]:<42} {label:<40} {where}")
        sections.extend(lines_for(question, runs))
        print()

    print("the five DEMO beats, before D-086 against what ships now:")
    sections.extend(beat_lines(index))
    print()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "<!-- generated by scripts/diagnose_fuel_station.py; the prose below it is written by hand -->",
        "",
        f"# Appendix: the measurements ({args.point} at {lat}, {lon})",
        "",
        f"- {len(index)} chunks, reranker {'on' if settings.reranker_on else 'off'}, "
        f"`retrieval_pool` {settings.retrieval_pool}, `rrf_k` {settings.rrf_k}, "
        f"`zone_boost` {settings.zone_boost}",
        f"- zones at the point: {location_module.describe_zones(zones)}",
        f"- the target clause: `{TARGET}` — \"fuel stations may be permitted in all Use "
        "Zones except Recreational (Regional Park, District Park, etc.) and Zone O\"",
        "",
    ]
    out_path.write_text("\n".join(header + sections) + "\n", encoding="utf-8")

    print(f"wrote {out_path.as_posix()}")
    print(f"{len(QUESTIONS)} question(s) x {len(CONFIGURATIONS)} configuration(s) measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
