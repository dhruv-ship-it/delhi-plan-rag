"""Ask ZoneWise real questions through a real LLM, and record what came back.

    uv run python scripts/live_run.py              # start a run
    uv run python scripts/live_run.py --resume     # continue one that stopped
    uv run python scripts/live_run.py --restart    # throw away a partial run and start again

    # the v2 run: the same 21 DEMO and agent cases, after D-086 to D-090
    uv run python scripts/live_run.py --state reports/live_run_state_v2.json \
        --out reports/live_answers_v2.md --label "Second real-model run (v2)" \
        --groups ab --compare reports/live_run_state.json

    # the v3 run: the same 21 cases plus 2 probes, after D-092 to D-096
    uv run python scripts/live_run.py --state reports/live_run_state_v3.json \
        --out reports/live_answers_v3.md --label "Third real-model run (v3)" \
        --groups abd --compare reports/live_run_state.json,reports/live_run_state_v2.json

Until now every answer this project has produced came from `FakeLLM` and a scripted
reply (D-040). This script produces the first real ones, and its only job is to
**record** them: it changes no prompt, no threshold and no retrieval setting, and
nothing in it reacts to what the model says.

**It is resumable, because a free tier runs out.** Every case is written to
`reports/live_run_state.json` as soon as it finishes and the report is rewritten from
that file, so a run that stops halfway leaves a readable report and
`--resume` picks up at the next case — the next day, after the daily token limit
resets, if that is what it takes.

**Two caps, both of which stop the run cleanly.** `LIVE_TOKEN_BUDGET` (default 150,000)
is checked before each case, and no more than `CALL_CAP` LLM calls are made. Both are
**per run, not per state file**: a resumed run gets its own budget, which is the whole
point of being resumable — the lifetime totals are reported separately. Neither is a
cost control — Groq's free tier is the cost control — they are there so an unattended
run cannot spend a day's quota on a bug.

**The state file, the report and the case set are all arguments**, so the same script
produces v1 and v2 without a copy of itself. `--groups ab` runs the DEMO and agent cases
only, which is the comparable set; `--compare` points at an earlier state file and adds a
case-by-case v1-against-v2 table and the totals to the top of the report. Nothing about
the questions, the prompts or the retrieval settings is changed by either flag.

**Three groups of cases, in this order:**

  a. every question `docs/DEMO.md` lists, at its own point, in map mode (`answer_point`)
  b. five agent-mode questions that name a place in plain text (`run_agent`)
  c. thirty questions from `eval/questions_draft.jsonl` — 10 location, 10 general,
     10 should-abstain, seed 11 — **for answer-quality review only, not for metrics**

Group c is not a measurement and the report says so in those words: the draft questions
are `verified: false` and were written by Claude from the chunks, which is the one setup
that flatters retrieval (D-054). What they are good for is reading thirty real answers
and noticing what is wrong with them.

Safe to re-run. It refuses to start over a partial run unless told which way to go.
"""

import argparse
import json
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: Set before `app.config` is imported, so `settings.llm_min_interval_s` reports the
#: value the run actually used. 2.5 s is 24 requests a minute against Groq's free-tier
#: 30 (D-082). `.env` or `--interval` still win.
os.environ.setdefault("LLM_MIN_INTERVAL_S", "2.5")

from app.agent import run_agent  # noqa: E402
from app.answer import answer_point  # noqa: E402
from app.config import PROVIDER_GROQ, settings  # noqa: E402
from app.extract import use_utf8_output  # noqa: E402
from app.geocode import metres_between  # noqa: E402
from app.llm import GroqLLM  # noqa: E402
from app.location import describe_zones  # noqa: E402
from app.retrieval import get_index  # noqa: E402

#: Set from the command line in `main`. The defaults are v1's, so a bare invocation
#: still means what it meant on 20 October.
STATE_PATH = Path("reports/live_run_state.json")
REPORT_PATH = Path("reports/live_answers_v1.md")
REPORT_LABEL = "First real-model run (v1)"
#: Earlier state files to compare against, oldest first. Empty for a standalone run.
COMPARE_PATHS: list[Path] = []
#: One phrase naming what changed since the previous run, for the comparison's opening
#: paragraph. Set from `--changes`, because the script cannot know and must not guess.
CHANGES = ""

#: Which case groups to run. "a" is the DEMO questions, "b" agent mode, "c" the drafts,
#: "d" the two location-note probes (D-094).
GROUP_LETTERS = {
    "a": "a. docs/DEMO.md, map mode",
    "b": "b. agent mode, a place named in words",
    "d": "d. probes for the location note",
}

#: The group label the probes are filed under. Its first letter is what `--groups d`
#: matches, the same way the other groups work.
PROBE_GROUP = "d. probes for the location note"

#: The most LLM calls one run may make, whatever the token budget says.
CALL_CAP = 120
#: The default token budget for one run, overridable with LIVE_TOKEN_BUDGET.
DEFAULT_TOKEN_BUDGET = 150000
#: The seed for the draft-question sample, so the same thirty come back every time.
SAMPLE_SEED = 11
#: How many of each draft category to take. There are only ten should-abstain drafts.
SAMPLE_PER_CATEGORY = 10
#: Prompt rule 7 asks for under 200 words. Longer than this is worth a human look.
LONG_ANSWER_WORDS = 200

# --- group a: every question docs/DEMO.md lists ---------------------------------
#
# `expect` is what docs/DEMO.md says *should* happen, and it is the only opinion in
# this file: "answer" where the demo prints clause ids it is happy with, "abstain" where
# the demo says the answering layer should decline, and "either" where the demo itself
# says the retrieval is wrong so both outcomes are defensible.

DEMO_CASES = (
    ("P_TOD", "How much of my plot can I build on?", "answer", "beat 1"),
    ("P_HDC", "How much of my plot can I build on?", "answer", "beat 2"),
    ("P_ZONEO", "Is construction allowed here?", "answer", "beat 3"),
    ("P_ZONEO", "What are the rules for the active floodplain?", "answer", "beat 3, sharper"),
    ("P_LDA", "What is the maximum ground coverage here?", "answer", "beat 4"),
    ("P_LDA", "Can I build a house here?", "answer", "beat 4, alternative"),
    ("P_RIDGE", "Is construction allowed here?", "abstain", "beat 5, the should-abstain beat"),
    ("P_OUT", "Is construction allowed here?", "abstain", "beat 6, outside Delhi"),
    ("P_TOD", "What is my property tax?", "abstain", "the added beat: unanswerable"),
    # These two were "either" in v1, because docs/DEMO.md recorded the retrieval as
    # wrong and both outcomes were therefore defensible. D-086 fixed it: 11.1.1@p854 is
    # rank 1 under both wordings and the question is beat 3b of the demo, so the
    # expectation is now "answer" — and the answer should be a **no**.
    ("P_ZONEO", "Can a fuel station be built here?", "answer", "beat 3b; was cut, fixed by D-086"),
    ("P_ZONEO", "Can a fuel station be built in Zone O?", "answer", "beat 3b, explicit wording"),
    ("P_RIDGE", "Can I build a house here?", "abstain", "cut; D-086 left it weaker still"),
    ("P_PLAIN", "How much of my plot can I build on?", "either", "cut; wanders at ranks 2-3"),
    ("P_PLAIN", "What is the permissible FAR for plotted housing?", "answer", "the demo's replacement"),
    ("P_TOD", "What is clause 4.2.1?", "answer", "in your pocket: BM25 earning its place"),
    ("P_LP", "How do I get my land included in a scheme?", "answer", "in your pocket"),
)

# --- group b: five agent-mode questions that name a place -----------------------
#
# `near` is roughly where the place is, and `radius_m` is generous: the check is "did
# the agent land in the right part of Delhi", not a precision test. Two of the five go
# through the gazetteer and one of those is an interchange, which is the live test of
# D-084.

AGENT_CASES = (
    ("What can be built near Hauz Khas metro?", 28.5438, 77.2059, 2000, "interchange, D-084"),
    (
        "Can I build a house on the Yamuna floodplain near ITO?",
        28.6283,
        77.2410,
        3000,
        "the floodplain, named in words",
    ),
    (
        "How much of my plot can I build on near Rajiv Chowk metro station?",
        28.6327,
        77.2193,
        2000,
        "gazetteer, a plain station",
    ),
    (
        "What are the ground coverage rules for a plot near Dwarka Sector 21 metro station?",
        28.5519,
        77.0586,
        2000,
        "gazetteer, the D-049 query",
    ),
    (
        "Is construction allowed in the Ridge near Chhatarpur?",
        28.5067,
        77.1750,
        4000,
        "a Ridge question with no pin",
    ),
)


# --- group d: two probes for the named-zone mismatch note -----------------------
#
# Both name a zone and are asked where that zone is **not**, which is what D-094's note
# exists for. `expect` is "either" for both, and deliberately: the right answer is one
# about the located point, or an abstention, and no mechanical rule can tell those from
# an answer about the named zone. These two cases are here to be read.

PROBE_MAP_CASES = (
    (
        "P_TOD",
        "Can I build on the Yamuna floodplain here?",
        "either",
        "probe: names Zone O at a point get_zones puts in a TOD zone, 2.7 km away (D-094)",
    ),
)

PROBE_AGENT_CASES = (
    (
        "Is construction allowed in the Ridge near Chhatarpur?",
        28.5067,
        77.1750,
        4000,
        "probe: the same question as agent-05, re-asked with the note in place (D-094)",
    ),
)


def now() -> str:
    """The time, to the second, in UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def points() -> dict[str, dict]:
    """The named test points, keyed by name."""
    path = settings.project_root / "data" / "test_points.json"
    return {record["name"]: record for record in json.loads(path.read_text(encoding="utf-8"))}


def draft_questions() -> list[dict]:
    """The thirty sampled draft questions: 10 location, 10 general, 10 should-abstain.

    Sorted by id before sampling and seeded, so the same thirty come back on every
    machine and a resumed run picks up the same list.
    """
    path = settings.project_root / "eval" / "questions_draft.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    chosen: list[dict] = []
    for category in ("location", "general", "abstain"):
        pool = sorted(
            (row for row in rows if row.get("category") == category), key=lambda row: row["id"]
        )
        rng = random.Random(SAMPLE_SEED)
        take = min(SAMPLE_PER_CATEGORY, len(pool))
        chosen.extend(rng.sample(pool, take))
    return chosen


def build_cases() -> list[dict]:
    """Every case this run will do, in order, each with a stable id."""
    named = points()
    cases: list[dict] = []

    for number, (point_name, question, expect, note) in enumerate(DEMO_CASES, start=1):
        point = named[point_name]
        cases.append(
            {
                "id": f"demo-{number:02d}",
                "group": "a. docs/DEMO.md, map mode",
                "mode": "map",
                "question": question,
                "point_name": point_name,
                "lat": point["lat"],
                "lon": point["lon"],
                "expect": expect,
                "note": note,
            }
        )

    for number, (question, lat, lon, radius, note) in enumerate(AGENT_CASES, start=1):
        cases.append(
            {
                "id": f"agent-{number:02d}",
                "group": "b. agent mode, a place named in words",
                "mode": "agent",
                "question": question,
                "point_name": None,
                "lat": None,
                "lon": None,
                "near": [lat, lon],
                "radius_m": radius,
                "expect": "answer",
                "note": note,
            }
        )

    number = 0
    for point_name, question, expect, note in PROBE_MAP_CASES:
        number += 1
        point = named[point_name]
        cases.append(
            {
                "id": f"probe-{number:02d}",
                "group": PROBE_GROUP,
                "mode": "map",
                "question": question,
                "point_name": point_name,
                "lat": point["lat"],
                "lon": point["lon"],
                "expect": expect,
                "note": note,
            }
        )
    for question, lat, lon, radius, note in PROBE_AGENT_CASES:
        number += 1
        cases.append(
            {
                "id": f"probe-{number:02d}",
                "group": PROBE_GROUP,
                "mode": "agent",
                "question": question,
                "point_name": None,
                "lat": None,
                "lon": None,
                "near": [lat, lon],
                "radius_m": radius,
                "expect": "either",
                "note": note,
            }
        )

    for row in draft_questions():
        has_point = row.get("lat") is not None and row.get("lon") is not None
        cases.append(
            {
                "id": f"draft-{row['id']}",
                "group": "c. eval/questions_draft.jsonl, for reading not for scoring",
                # A draft question with no point has no map-mode path: /api/ask requires
                # lat and lon, so the shipped route for a question without one is the
                # agent. Nothing new was written for this (D-085).
                "mode": "map" if has_point else "agent",
                "question": row["question"],
                "point_name": row.get("point_name"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "expect": "abstain" if row.get("should_abstain") else "answer",
                "note": f"{row.get('category')}, should_abstain={bool(row.get('should_abstain'))}",
                "expected_chunk_ids": list(row.get("expected_chunk_ids") or []),
                "acceptable_chunk_ids": list(row.get("acceptable_chunk_ids") or []),
                "expected_answer_short": row.get("expected_answer_short") or "",
            }
        )
    return cases


def load_state() -> dict:
    """The state file, or a fresh one."""
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def fresh_state(total: int, budget: int) -> dict:
    """A new run's state."""
    return {
        "started_at": now(),
        "updated_at": now(),
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "min_interval_s": settings.llm_min_interval_s,
        "token_budget": budget,
        "call_cap": CALL_CAP,
        "total_cases": total,
        "tokens_used": 0,
        "calls_made": 0,
        "runs": 0,
        "last_run_tokens": 0,
        "last_run_calls": 0,
        "rate_limit_events": 0,
        "api_retries": 0,
        "stopped_because": None,
        "last_rate_limit": {},
        "records": [],
    }


def save_state(state: dict) -> None:
    """Write the state file. Called after every case, which is what makes --resume work."""
    state["updated_at"] = now()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def citation_records(result) -> list[dict]:
    """The citations of a result, flattened for the report."""
    return [
        {
            "chunk_id": citation.chunk_id,
            "clause_id": citation.clause_id,
            "doc_title": citation.doc_title,
            "pages": (
                str(citation.page_start)
                if citation.page_start == citation.page_end
                else f"{citation.page_start}-{citation.page_end}"
            ),
        }
        for citation in result.citations
    ]


def run_case(case: dict, client: GroqLLM, index) -> dict:
    """Run one case and return its record. An exception becomes a recorded error."""
    before_calls = client.calls
    before_in, before_out = client.input_tokens, client.output_tokens
    before_retries, before_limits = client.retries, client.rate_limit_events
    started = time.perf_counter()

    record = dict(case)
    record["ran_at"] = now()
    try:
        if case["mode"] == "map":
            result = answer_point(
                case["question"], case["lat"], case["lon"], llm=client, index=index
            )
        else:
            result = run_agent(case["question"], llm=client, index=index)
    except Exception as exc:
        record.update(
            {
                "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "api_calls": client.calls - before_calls,
                "input_tokens": client.input_tokens - before_in,
                "output_tokens": client.output_tokens - before_out,
                "api_retries": client.retries - before_retries,
                "rate_limit_events": client.rate_limit_events - before_limits,
            }
        )
        return record

    retrieved = [item["chunk_id"] for item in result.retrieval]
    cited = [citation.chunk_id for citation in result.citations]
    record.update(
        {
            "error": None,
            "zones_text": describe_zones(result.zones) if result.zones else "no point",
            "located_lat": result.lat,
            "located_lon": result.lon,
            "answer": result.answer_markdown,
            "answer_words": len((result.answer_markdown or "").split()),
            "citations": citation_records(result),
            "cited_chunk_ids": cited,
            "retrieved_chunk_ids": retrieved,
            "abstained": result.abstained,
            "abstain_reason": result.abstain_reason,
            # One problems list per rejected attempt (D-087). v1 recorded only a count,
            # so `reports/citation_failures_v1.md` could not say which rule fired.
            "validation_failures": [list(attempt) for attempt in result.validation_failures],
            # The deterministic note, when the question named a zone the point is not
            # in (D-094), and what the claim check said about the answer (D-096).
            "location_note": result.location_note,
            "support_check": dict(result.support_check or {}),
            "llm_calls": result.llm_calls,
            "latency_ms": result.latency_ms,
            "tool_trace": list(result.tool_trace),
            "api_calls": client.calls - before_calls,
            "input_tokens": client.input_tokens - before_in,
            "output_tokens": client.output_tokens - before_out,
            "api_retries": client.retries - before_retries,
            "rate_limit_events": client.rate_limit_events - before_limits,
        }
    )
    # The number of rejected attempts, read off the record rather than inferred from the
    # call count. Before D-087 this was `llm_calls - 1`, which only worked in map mode:
    # an agent run's calls include its tool rounds, so the field had to be left unset.
    record["citation_retry"] = len(result.validation_failures)

    # The claim check goes through the same client, so its tokens are inside the deltas
    # above. Split them out, because "what did the answer cost" and "what did checking
    # it cost" are two different questions and v3 reports both (D-096).
    support = record["support_check"]
    record["support_calls"] = int(support.get("calls") or 0)
    record["support_tokens"] = int(support.get("input_tokens") or 0) + int(
        support.get("output_tokens") or 0
    )
    record["answer_tokens"] = (
        record["input_tokens"] + record["output_tokens"] - record["support_tokens"]
    )

    expected = list(case.get("expected_chunk_ids") or [])
    if expected:
        record["expected_cited"] = sorted(set(expected) & set(cited))
        record["expected_retrieved"] = sorted(set(expected) & set(retrieved))
        record["expected_hit"] = bool(record["expected_cited"])
    if case.get("near") and result.lat is not None and result.lon is not None:
        record["located_metres_off"] = round(
            metres_between(result.lat, result.lon, case["near"][0], case["near"][1])
        )
    return record


# --- the suspected-problem rules ------------------------------------------------
#
# Each returns a short label when the record trips it. They are mechanical on purpose:
# a rule a script can apply is one a human can check, and the whole point of this run
# is to hand a person a list to look at rather than a verdict.


def problems_of(record: dict) -> list[str]:
    """Every suspected problem one record trips."""
    found: list[str] = []
    if record.get("error"):
        found.append("the call failed")
        return found

    abstained = bool(record.get("abstained"))
    expect = record.get("expect")
    reason = record.get("abstain_reason") or ""

    if abstained and expect == "answer":
        found.append(f"abstained on an answerable question ({reason})")
    if not abstained and expect == "abstain":
        found.append("answered a should-abstain question")
    if reason.startswith("citation_check_failed"):
        found.append("the citation check failed twice")
    if record.get("citation_retry"):
        found.append("needed a citation retry")
    if (record.get("answer_words") or 0) > LONG_ANSWER_WORDS:
        found.append(f"very long answer ({record['answer_words']} words, rule 7 asks for <200)")

    cited = record.get("cited_chunk_ids") or []
    retrieved = record.get("retrieved_chunk_ids") or []
    if cited and all(chunk_id.startswith("MPD47_FAQ") for chunk_id in cited):
        if any(chunk_id.startswith("MPD47_GAZETTE_EN") for chunk_id in retrieved):
            found.append("cited only the FAQ although a gazette clause was retrieved")

    off = record.get("located_metres_off")
    if off is not None and off > (record.get("radius_m") or 0):
        found.append(f"the agent placed the location {off} m from where it should be")
    if record["mode"] == "agent" and not abstained and record.get("located_lat") is None:
        found.append("the agent answered without ever establishing a point")

    support = record.get("support_check") or {}
    counts = support.get("counts") or {}
    if counts.get("unsupported"):
        found.append(
            f"the claim check called {counts['unsupported']} sentence(s) unsupported"
        )
    if support.get("would_change") and not support.get("enforced"):
        found.append("enforce mode would have changed this answer")
    if support.get("mode") not in (None, "off") and support.get("error"):
        found.append("the claim check could not run")

    if record.get("expected_hit") is False:
        if record.get("expected_retrieved"):
            found.append("the expected clause was retrieved but not cited")
        elif not abstained:
            found.append("answered without citing any expected clause")
    return found


# --- the report -----------------------------------------------------------------


def percentile(values: list[float], fraction: float) -> float:
    """A simple nearest-rank percentile. Fine for fifty numbers."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def summary_lines(state: dict, total: int) -> list[str]:
    """The summary at the top of the report."""
    records = state["records"]
    done = len(records)
    ok = [item for item in records if not item.get("error")]
    answered = [item for item in ok if not item.get("abstained")]
    abstained = [item for item in ok if item.get("abstained")]
    failed = [item for item in records if item.get("error")]
    latencies = [item["latency_ms"] for item in ok if item.get("latency_ms")]

    reasons: dict[str, int] = {}
    for item in abstained:
        key = (item.get("abstain_reason") or "unknown").split(":")[0]
        reasons[key] = reasons.get(key, 0) + 1

    retries = sum(item.get("citation_retry") or 0 for item in records)
    stopped = state.get("stopped_because") or "running"

    out = [
        f"# {REPORT_LABEL}",
        "",
        "> **Nobody has read these answers yet.** This file is a recording, not a review.",
        "> It was written by `scripts/live_run.py`, which changes no prompt, no threshold",
        "> and no retrieval setting, and nothing in it reacts to what the model said. The",
        "> \"suspected problems\" below are mechanical rules, not judgements.",
        "",
        "| | |",
        "| --- | --- |",
        f"| Provider / model | `{state['provider']}` / `{state['model']}` |",
        f"| Started / last updated | {state['started_at']} / {state['updated_at']} |",
        f"| Cases done | **{done} of {total}** |",
        f"| Answered | **{len(answered)}** |",
        f"| Abstained | **{len(abstained)}** |",
        f"| Failed outright | {len(failed)} |",
        f"| Citation retries | {retries} |",
        f"| Latency p50 / p95 | {percentile(latencies, 0.5) / 1000:.1f} s / "
        f"{percentile(latencies, 0.95) / 1000:.1f} s — **wall clock, not model speed**; see below |",
        f"| Tokens used, all runs | {state['tokens_used']:,} |",
        f"| Tokens used, last run | {state.get('last_run_tokens', 0):,} of a "
        f"{state['token_budget']:,} per-run budget |",
        f"| LLM calls, all runs | {state['calls_made']} |",
        f"| LLM calls, last run | {state.get('last_run_calls', 0)} of a "
        f"{state['call_cap']} per-run cap |",
        f"| Runs so far | {state.get('runs', 1)} |",
        f"| 429s / rate-limit waits | {state['rate_limit_events']} / {state['api_retries']} |",
        f"| Gap between calls | {state['min_interval_s']} s |",
        f"| State | **{stopped}** |",
        "",
    ]
    if reasons:
        out.append("Abstentions by reason:")
        out.append("")
        out.append("| reason | n |")
        out.append("| --- | --- |")
        for reason, count in sorted(reasons.items(), key=lambda pair: -pair[1]):
            out.append(f"| `{reason}` | {count} |")
        out.append("")
    if state.get("last_rate_limit"):
        out.append(f"Last rate-limit headers seen: `{state['last_rate_limit']}`")
        out.append("")
    out += [
        "**What the latency figure is and is not.** It is wall clock around the whole "
        "case, measured by `app/answer.py` itself, so it includes the enforced "
        f"{state['min_interval_s']} s gap between calls, any wait for a 429, and the "
        "time Groq's free tier spends holding a request back when the "
        "8,000-tokens-a-minute bucket is low. A map-mode case costs about 5-6k tokens, "
        "so from the second case onwards that bucket — not the model — sets the pace. "
        "The one figure here that is close to model latency is the **first** case of a "
        "run, against a full bucket. Nothing in this file should be quoted as a latency "
        "for ZoneWise.",
        "",
    ]
    if stopped in ("token_budget", "call_cap", "stopped_by_hand"):
        why = {
            "token_budget": "stopped on its own token budget",
            "call_cap": "stopped on its own call cap",
            "stopped_by_hand": "was stopped by hand",
        }[stopped]
        out.append(
            f"**This run {why}, not on an error.** Every case below ran to completion; "
            "the rest were never started. Continue with "
            "`uv run python scripts\\live_run.py --resume` — the next day if the daily "
            "token limit is what ran out."
        )
        out.append("")
    return out


def problem_lines(state: dict) -> list[str]:
    """The suspected-problems section, grouped by rule with examples."""
    buckets: dict[str, list[dict]] = {}
    for record in state["records"]:
        for problem in problems_of(record):
            key = problem.split(" (")[0]
            buckets.setdefault(key, []).append(record)

    out = ["## Suspected problems", ""]
    if not buckets:
        out += ["None of the mechanical rules fired on the cases run so far.", ""]
        return out
    out += [
        "Each row is a mechanical rule, not a verdict. The examples link to the full case",
        "below, which is where the judgement has to happen.",
        "",
        "| suspected problem | n | examples |",
        "| --- | --- | --- |",
    ]
    for problem, records in sorted(buckets.items(), key=lambda pair: -len(pair[1])):
        examples = ", ".join(f"[{item['id']}](#{item['id']})" for item in records[:4])
        more = f" +{len(records) - 4} more" if len(records) > 4 else ""
        out.append(f"| {problem} | **{len(records)}** | {examples}{more} |")
    out.append("")
    return out


def case_lines(record: dict) -> list[str]:
    """One case, in full."""
    out = [f"### {record['id']}", "", f"**{record['question']}**", ""]

    where = record.get("point_name") or "no pin"
    if record.get("lat") is not None:
        where += f" ({record['lat']}, {record['lon']})"
    elif record.get("located_lat") is not None:
        where += f" — the agent found {record['located_lat']:.5f}, {record['located_lon']:.5f}"
    out.append(f"- **Where:** {where}")
    out.append(f"- **Zones:** {record.get('zones_text', '—')}")
    out.append(f"- **Mode:** {record['mode']}   **Expected:** {record.get('expect')}   "
               f"({record.get('note', '')})")

    if record.get("error"):
        out += ["", f"**The call failed:** `{record['error']}`", ""]
        return out

    if record.get("abstained"):
        out.append(f"- **Abstained:** `{record.get('abstain_reason')}`")
    else:
        out.append(f"- **Answered** in {record.get('answer_words', 0)} words")
    out.append(
        f"- **Cost:** {record.get('latency_ms', 0) / 1000:.1f} s, "
        f"{record.get('llm_calls', 0)} llm call(s), "
        f"{record.get('input_tokens', 0)} in / {record.get('output_tokens', 0)} out tokens, "
        f"{record.get('api_retries', 0)} rate-limit retr(y/ies)"
    )
    if record.get("citation_retry"):
        out.append(f"- **Citation retries:** {record['citation_retry']}")
    if record.get("located_metres_off") is not None:
        out.append(
            f"- **Location:** {record['located_metres_off']} m from the expected place "
            f"(tolerance {record.get('radius_m')} m)"
        )
    if record.get("expected_chunk_ids"):
        out.append(f"- **Expected clauses:** {', '.join('`' + c + '`' for c in record['expected_chunk_ids'])}")
        out.append(
            f"- **Expected clause cited?** "
            f"{'yes' if record.get('expected_hit') else 'no'}"
            + (
                f" — retrieved but not cited: {', '.join('`' + c + '`' for c in record['expected_retrieved'])}"
                if record.get("expected_retrieved") and not record.get("expected_hit")
                else ""
            )
        )
    if record.get("expected_answer_short"):
        out.append(f"- **The draft's own short answer:** {record['expected_answer_short']}")

    problems = problems_of(record)
    if problems:
        out.append("- **Suspected:** " + "; ".join(problems))
    out.append("")

    if record.get("tool_trace"):
        out.append("Tool trace:")
        out.append("")
        for step in record["tool_trace"]:
            out.append(f"1. `{step['tool']}` {json.dumps(step['input'], ensure_ascii=False)} -> {step['summary']}")
        out.append("")

    if record.get("answer"):
        out.append("> " + record["answer"].replace("\n", "\n> "))
        out.append("")
    if record.get("citations"):
        out.append("| marker | clause | document | pages |")
        out.append("| --- | --- | --- | --- |")
        for citation in record["citations"]:
            out.append(
                f"| `{citation['chunk_id']}` | {citation['clause_id'] or '—'} "
                f"| {citation['doc_title']} | {citation['pages']} |"
            )
        out.append("")
    elif not record.get("abstained"):
        out.append("*No citations were resolved, which should not happen for an answer.*")
        out.append("")

    retrieved = record.get("retrieved_chunk_ids") or []
    if retrieved:
        out.append(f"<sub>Retrieved: {', '.join('`' + c + '`' for c in retrieved[:8])}</sub>")
        out.append("")
    return out


# --- the v1-against-v2 comparison -----------------------------------------------
#
# Everything here is read off two state files. No case is re-run and nothing is
# recomputed from the answers, so the comparison says what the two runs recorded and
# not what this script thinks of it.


def reached_the_check(record: dict) -> bool:
    """True when the model wrote an answer that the citation check then read.

    A case that never reached the model (`outside_delhi`) and one the model declined
    under rule 3 both skip the check entirely, so neither belongs in a pass rate.
    """
    if record.get("error"):
        return False
    reason = record.get("abstain_reason") or ""
    if reason.startswith("outside_delhi") or reason.startswith("model_abstained"):
        return False
    return record.get("citation_retry") is not None


def first_attempt_passed(record: dict) -> bool:
    """True when the first answer this case produced survived the check."""
    return reached_the_check(record) and not record.get("citation_retry")


def outcome_of(record: dict) -> str:
    """One short phrase for what a case did, for the comparison table."""
    if record.get("error"):
        return "failed"
    if not record.get("abstained"):
        return f"answered, {record.get('answer_words', 0)} words"
    reason = (record.get("abstain_reason") or "unknown").split(":")[0]
    return f"abstained `{reason}`"


def median_of(values: list[float]) -> float | None:
    """The median, or None for an empty list. `statistics.median` raises on empty."""
    return statistics.median(values) if values else None


def totals_of(records: list[dict], mode: str | None = None) -> dict:
    """The run-level numbers the brief asks for, over one list of records.

    `mode` restricts the **pass-rate** numbers to one mode, which is what keeps them
    comparable across runs: v1 could not count an agent retry at all, so an agent case
    is absent from its denominator and present in v2's. The rate is therefore reported
    for map mode in every column, and for agent mode from v2 onwards.

    Three groups of fields arrived with v3 and are absent from older state files:
    `has_notes` and `has_support` say so, so the report can print an honest dash rather
    than a zero that reads like a measurement (D-094, D-096).
    """
    ok = [item for item in records if not item.get("error")]
    answered = [item for item in ok if not item.get("abstained")]
    checked = [
        item
        for item in ok
        if reached_the_check(item) and (mode is None or item.get("mode") == mode)
    ]
    passed = [item for item in checked if first_attempt_passed(item)]
    should_abstain = [item for item in ok if item.get("expect") == "abstain"]
    located = [item for item in ok if item.get("located_metres_off") is not None]
    close = [
        item
        for item in located
        if item["located_metres_off"] <= (item.get("radius_m") or 0)
    ]
    tokens = [
        (item.get("input_tokens") or 0) + (item.get("output_tokens") or 0) for item in ok
    ]

    # the claim check, summed across the cases that ran one
    support_counts: dict[str, int] = {"supported": 0, "partly": 0, "unsupported": 0}
    would_change: list[str] = []
    would_abstain: list[str] = []
    support_ran = 0
    support_tokens: list[int] = []
    answer_tokens: list[int] = []
    for item in ok:
        support = item.get("support_check") or {}
        if support.get("ran"):
            support_ran += 1
            for name, count in (support.get("counts") or {}).items():
                support_counts[name] = support_counts.get(name, 0) + int(count)
        if support.get("would_change"):
            would_change.append(item["id"])
        if support.get("would_abstain"):
            would_abstain.append(item["id"])
        if "support_tokens" in item:
            support_tokens.append(int(item.get("support_tokens") or 0))
            answer_tokens.append(int(item.get("answer_tokens") or 0))

    return {
        "cases": len(records),
        "answered": len(answered),
        "abstained": sum(1 for item in ok if item.get("abstained")),
        "reached_check": len(checked),
        "first_attempt_pass": len(passed),
        "first_attempt_rate": (len(passed) / len(checked)) if checked else None,
        "retries": sum(item.get("citation_retry") or 0 for item in records),
        "citation_check_failed": sum(
            1
            for item in ok
            if (item.get("abstain_reason") or "").startswith("citation_check_failed")
        ),
        "should_abstain": len(should_abstain),
        "should_abstain_right": sum(1 for item in should_abstain if item.get("abstained")),
        "located": len(located),
        "located_close": len(close),
        "tokens_mean": (sum(tokens) / len(tokens)) if tokens else 0.0,
        "tokens_total": sum(tokens),
        "words_median": median_of([item.get("answer_words") or 0 for item in answered]),
        "citations_median": median_of(
            [len(item.get("citations") or []) for item in answered]
        ),
        "has_notes": any("location_note" in item for item in ok),
        "location_notes": sum(1 for item in ok if item.get("location_note")),
        "has_support": any("support_check" in item for item in ok),
        "support_ran": support_ran,
        "support_counts": support_counts,
        "enforce_would_change": would_change,
        "enforce_would_abstain": would_abstain,
        "tokens_answer_mean": (
            (sum(answer_tokens) / len(answer_tokens)) if answer_tokens else None
        ),
        "tokens_support_mean": (
            (sum(support_tokens) / len(support_tokens)) if support_tokens else None
        ),
    }


def _rate(totals: dict) -> str:
    """The first-attempt pass rate as a readable cell."""
    if totals["first_attempt_rate"] is None:
        return "—"
    return (
        f"{totals['first_attempt_rate']:.0%} "
        f"({totals['first_attempt_pass']} of {totals['reached_check']})"
    )


def _cell(value) -> str:
    """One table cell: a dash for a run that had no such field."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.0f}" if value >= 10 else f"{value:.1f}"
    return str(value)


def _maybe(totals: dict, flag: str, value) -> str:
    """`value` when the run recorded that family of fields, a dash when it did not."""
    return _cell(value) if totals.get(flag) else "—"


def _ids(case_ids: list[str], flag: bool) -> str:
    """A list of case ids as links, "none" when empty, a dash for an older run."""
    if not flag:
        return "—"
    if not case_ids:
        return "none"
    return ", ".join(f"[{case_id}](#{case_id})" for case_id in case_ids)


def comparison_lines(runs: list[tuple[str, dict]]) -> list[str]:
    """The case-by-case table and the totals, one column per run.

    `runs` is (label, state) oldest first, with this run last. Everything here is read
    off the state files: no case is re-run and nothing is recomputed from an answer, so
    the comparison says what the runs recorded and not what this script thinks of it.
    """
    if len(runs) < 2:
        return []
    labels = [label for label, _ in runs]
    by_run = [
        {record["id"]: record for record in (state.get("records") or [])}
        for _, state in runs
    ]
    current = by_run[-1]
    shared = [case_id for case_id in current if all(case_id in found for found in by_run)]
    if not shared:
        return []

    heading = " against ".join(labels)
    out = [
        f"## {heading}",
        "",
        f"The {len(shared)} case(s) every run recorded, read off the state files. The "
        "same questions at the same points with the same budget each time; what changed "
        f"between {labels[-2]} and {labels[-1]} is "
        + (CHANGES or "recorded in `DECISIONS.md`")
        + ". **Still nobody has read these answers.**",
        "",
        "| case | question | " + " | ".join(labels) + " | retries | citations | note? |",
        "| --- | --- | " + " | ".join("---" for _ in labels) + " | --- | --- | --- |",
    ]
    for case_id in shared:
        rows = [found[case_id] for found in by_run]
        question = rows[0].get("question", "")
        retries = " → ".join(
            str(row.get("citation_retry")) if row.get("citation_retry") is not None else "—"
            for row in rows
        )
        citations = " → ".join(str(len(row.get("citations") or [])) for row in rows)
        latest = rows[-1]
        note = "yes" if latest.get("location_note") else ("no" if "location_note" in latest else "—")
        out.append(
            f"| [{case_id}](#{case_id}) | {question[:42]}"
            f"{'…' if len(question) > 42 else ''} | "
            + " | ".join(outcome_of(row) for row in rows)
            + f" | {retries} | {citations} | {note} |"
        )

    # the cases only this run has, which is where the probes show up
    extra = [case_id for case_id in current if case_id not in shared]
    if extra:
        out += [
            "",
            f"{len(extra)} case(s) are new in {labels[-1]} and have no earlier column: "
            + ", ".join(f"[{case_id}](#{case_id})" for case_id in extra)
            + ".",
        ]

    per_run = [[found[case_id] for case_id in shared] for found in by_run]
    totals = [totals_of(records, mode="map") for records in per_run]
    agents = [totals_of(records, mode="agent") for records in per_run]
    whole = [totals_of(records) for records in per_run]

    out += [
        "",
        f"### Totals, over those {len(shared)} cases only",
        "",
        "The pass rate counts only the cases whose answer actually reached the citation "
        "check: a point outside Delhi never calls the model, and a case the model "
        "declined under rule 3 has nothing to check. It is split by mode because v1 "
        "could not count an agent retry, so an agent case is missing from its "
        "denominator and present in later ones. A **dash** means the run predates the "
        "field, not that the number is zero.",
        "",
        "| | " + " | ".join(labels) + " |",
        "| --- | " + " | ".join("---" for _ in labels) + " |",
        "| answered / abstained | "
        + " | ".join(f"{one['answered']} / {one['abstained']}" for one in whole)
        + " |",
        "| first-attempt pass rate, map mode | "
        + " | ".join(_rate(one) for one in totals)
        + " |",
        "| first-attempt pass rate, agent mode | "
        + " | ".join(_rate(one) for one in agents)
        + " |",
        "| citation retries | " + " | ".join(str(one["retries"]) for one in totals) + " |",
        "| `citation_check_failed` | "
        + " | ".join(str(one["citation_check_failed"]) for one in whole)
        + " |",
        "| should-abstain handled right | "
        + " | ".join(
            f"{one['should_abstain_right']} of {one['should_abstain']}" for one in whole
        )
        + " |",
        "| agent location within tolerance | "
        + " | ".join(f"{one['located_close']} of {one['located']}" for one in whole)
        + " |",
        "| median words, answered cases | "
        + " | ".join(_cell(one["words_median"]) for one in whole)
        + " |",
        "| median citations, answered cases | "
        + " | ".join(_cell(one["citations_median"]) for one in whole)
        + " |",
        "| location notes shown | "
        + " | ".join(_maybe(one, "has_notes", one["location_notes"]) for one in whole)
        + " |",
        "| claim check ran on | "
        + " | ".join(_maybe(one, "has_support", one["support_ran"]) for one in whole)
        + " |",
        "| sentences `supported` | "
        + " | ".join(
            _maybe(one, "has_support", one["support_counts"].get("supported", 0))
            for one in whole
        )
        + " |",
        "| sentences `partly` | "
        + " | ".join(
            _maybe(one, "has_support", one["support_counts"].get("partly", 0))
            for one in whole
        )
        + " |",
        "| sentences `unsupported` | "
        + " | ".join(
            _maybe(one, "has_support", one["support_counts"].get("unsupported", 0))
            for one in whole
        )
        + " |",
        "| cases `enforce` would change | "
        + " | ".join(
            _ids(one["enforce_would_change"], one["has_support"]) for one in whole
        )
        + " |",
        "| … of those, would abstain | "
        + " | ".join(
            _ids(one["enforce_would_abstain"], one["has_support"]) for one in whole
        )
        + " |",
        "| tokens per case (mean) | "
        + " | ".join(f"{one['tokens_mean']:,.0f}" for one in whole)
        + " |",
        "| … of which, the answer | "
        + " | ".join(_cell(one["tokens_answer_mean"]) for one in whole)
        + " |",
        "| … of which, the claim check | "
        + " | ".join(_cell(one["tokens_support_mean"]) for one in whole)
        + " |",
        "",
        "**How to read the retry column.** In v1 the agent's retries could not be "
        "counted at all — the field was `llm_calls - 1`, which only works when a "
        "case makes one call, and an agent run's calls include its tool rounds. From v2 "
        "one problems list is recorded per rejected attempt (D-087), so the number is "
        "read rather than inferred. A v1 agent row therefore shows a dash and not `0`.",
        "",
        "**What the claim-check rows are and are not.** `SUPPORT_CHECK=shadow`, so every "
        "verdict in this run was recorded and **none of them changed an answer** "
        "(D-096). The `enforce` rows say what the other mode would have done to these "
        "same answers, which is the question a reader has to settle before that mode is "
        "turned on. They are a model's judgement of a model, so they are evidence and "
        "not a verdict.",
        "",
    ]

    latest = whole[-1]
    if latest["has_support"]:
        changed = latest["enforce_would_change"]
        out += [
            "**`demo-07`, explicitly.** It is the should-abstain beat at P_RIDGE that "
            "answered in v1 (134 words) and again in v2 (60 words), citing clauses "
            "that do not say it, and it is the case the claim check exists for. In this "
            "run "
            + (
                "`enforce` **would** have changed it."
                if "demo-07" in changed
                else "`enforce` would **not** have changed it, which is the more "
                "interesting outcome of the two: the structural check passed it, the "
                "semantic check passed it, and a reader still has to decide whether "
                "the answer is right."
            )
            + (
                f" The cases `enforce` would have changed are {_ids(changed, True)}."
                if changed
                else " It would have changed no case in this run at all."
            ),
            "",
        ]
    return out


def run_labels(count: int) -> list[str]:
    """Column labels for `count` runs, oldest first: v1, v2, ... and this run last."""
    return [f"v{number}" for number in range(1, count + 1)]


def compared_runs(state: dict) -> list[tuple[str, dict]]:
    """(label, state) for every earlier run that can be read, plus this one, in order.

    An earlier state file that is missing or unreadable is dropped rather than raised
    on: a comparison is a courtesy to the reader and must not stop the run that is
    producing the report.
    """
    earlier: list[dict] = []
    for path in COMPARE_PATHS:
        if not path.exists():
            continue
        try:
            earlier.append(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    runs = earlier + [state]
    return list(zip(run_labels(len(runs)), runs))


def write_report(state: dict, total: int) -> None:
    """Rewrite the whole report from the state file. Called after every case."""
    lines = summary_lines(state, total)
    lines += comparison_lines(compared_runs(state))
    lines += problem_lines(state)

    groups: dict[str, list[dict]] = {}
    for record in state["records"]:
        groups.setdefault(record["group"], []).append(record)

    lines += ["---", "", "## Every case, in full", ""]
    for group, records in groups.items():
        lines += [f"## {group}", ""]
        for record in records:
            lines += case_lines(record)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- the run --------------------------------------------------------------------


def print_comparison(state: dict) -> None:
    """The same totals the report carries, on stdout, one column per run.

    Printed rather than only written, because this is the figure the run is for and a
    reader should not have to open a 2,000-line markdown file to see it.
    """
    runs = compared_runs(state)
    if len(runs) < 2:
        return
    labels = [label for label, _ in runs]
    by_run = [
        {record["id"]: record for record in (one.get("records") or [])} for _, one in runs
    ]
    current = by_run[-1]
    shared = [case_id for case_id in current if all(case_id in found for found in by_run)]
    if not shared:
        return
    per_run = [[found[case_id] for case_id in shared] for found in by_run]
    maps = [totals_of(records, mode="map") for records in per_run]
    agents = [totals_of(records, mode="agent") for records in per_run]
    whole = [totals_of(records) for records in per_run]

    width = 22
    print()
    print(f"{' against '.join(labels)} over {len(shared)} shared case(s):")
    print("  " + " " * 34 + "".join(f"{label:>{width}}" for label in labels))

    def row(name: str, values: list[str]) -> None:
        print(f"  {name:<34}" + "".join(f"{value:>{width}}" for value in values))

    row("first-attempt pass, map", [_rate(one) for one in maps])
    row("first-attempt pass, agent", [_rate(one) for one in agents])
    row("citation retries", [str(one["retries"]) for one in maps])
    row("citation_check_failed", [str(one["citation_check_failed"]) for one in whole])
    row(
        "answered / abstained",
        [f"{one['answered']} / {one['abstained']}" for one in whole],
    )
    row(
        "should-abstain right",
        [f"{one['should_abstain_right']} of {one['should_abstain']}" for one in whole],
    )
    row(
        "agent location in range",
        [f"{one['located_close']} of {one['located']}" for one in whole],
    )
    row("median words", [_cell(one["words_median"]) for one in whole])
    row("median citations", [_cell(one["citations_median"]) for one in whole])
    row(
        "location notes shown",
        [_maybe(one, "has_notes", one["location_notes"]) for one in whole],
    )
    for verdict in ("supported", "partly", "unsupported"):
        row(
            f"sentences {verdict}",
            [
                _maybe(one, "has_support", one["support_counts"].get(verdict, 0))
                for one in whole
            ],
        )
    row(
        "cases enforce would change",
        [
            _maybe(one, "has_support", len(one["enforce_would_change"]))
            for one in whole
        ],
    )
    row("tokens per case", [f"{one['tokens_mean']:,.0f}" for one in whole])
    row("  of which, the answer", [_cell(one["tokens_answer_mean"]) for one in whole])
    row("  of which, the claim check", [_cell(one["tokens_support_mean"]) for one in whole])

    latest = whole[-1]
    if latest["has_support"]:
        changed = latest["enforce_would_change"]
        print()
        print(
            "  enforce would have changed: "
            + (", ".join(changed) if changed else "no case")
        )
        print(f"  demo-07: enforce would {'' if 'demo-07' in changed else 'NOT '}change it")


def main() -> int:
    """Run the cases that are not done yet, within the caps, then stop and report."""
    global STATE_PATH, REPORT_PATH, REPORT_LABEL, COMPARE_PATHS, CHANGES
    use_utf8_output()
    parser = argparse.ArgumentParser(description="The first real-model run.")
    parser.add_argument("--resume", action="store_true", help="continue a run that stopped")
    parser.add_argument("--restart", action="store_true", help="discard a partial run")
    parser.add_argument(
        "--budget",
        type=int,
        default=int(os.getenv("LIVE_TOKEN_BUDGET") or DEFAULT_TOKEN_BUDGET),
        help=f"token budget for this run (default {DEFAULT_TOKEN_BUDGET}, or LIVE_TOKEN_BUDGET)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=settings.llm_min_interval_s,
        help="seconds between LLM calls (default 2.5, from LLM_MIN_INTERVAL_S)",
    )
    parser.add_argument("--only", default="", help="run only cases whose id contains this")
    parser.add_argument(
        "--state", default=str(STATE_PATH), help=f"state file (default {STATE_PATH.as_posix()})"
    )
    parser.add_argument(
        "--out", default=str(REPORT_PATH), help=f"report file (default {REPORT_PATH.as_posix()})"
    )
    parser.add_argument("--label", default=REPORT_LABEL, help="the report's title")
    parser.add_argument(
        "--groups",
        default="abc",
        help=(
            "which case groups to run: a=DEMO, b=agent, c=drafts, d=the location-note "
            "probes (default abc, which is what v1 ran)"
        ),
    )
    parser.add_argument(
        "--compare",
        default="",
        help=(
            "earlier state file(s), comma separated and oldest first, to put a "
            "case-by-case comparison against at the top. The columns are labelled v1, "
            "v2, ... in that order, with this run last"
        ),
    )
    parser.add_argument(
        "--changes",
        default="",
        help="one phrase naming what changed since the previous run, for the comparison",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="rewrite the report from the state file and make no calls at all",
    )
    args = parser.parse_args()

    STATE_PATH = Path(args.state)
    REPORT_PATH = Path(args.out)
    REPORT_LABEL = args.label
    COMPARE_PATHS = [
        Path(part.strip()) for part in args.compare.split(",") if part.strip()
    ]
    CHANGES = args.changes.strip()

    if settings.llm_provider != PROVIDER_GROQ:
        print(f"LLM_PROVIDER is {settings.llm_provider!r}, not 'groq'.")
        print("This run is the Groq one. Set LLM_PROVIDER=groq in .env and try again.")
        return 1
    if not settings.has_api_key:
        print("No usable GROQ_API_KEY. Nothing was called.")
        print("Check it first with: uv run python -m app.llm")
        return 1

    cases = build_cases()
    if args.groups != "abcd":
        wanted = {letter for letter in args.groups.lower()}
        cases = [case for case in cases if case["group"][0] in wanted]
    if args.only:
        cases = [case for case in cases if args.only in case["id"]]
    total = len(cases)

    state = load_state()
    if args.report_only:
        if not state.get("records"):
            print(f"{STATE_PATH.as_posix()} holds no cases, so there is nothing to report.")
            return 1
        write_report(state, state.get("total_cases") or total)
        print(f"rewrote {REPORT_PATH.as_posix()} from {len(state['records'])} recorded case(s).")
        print("No API call was made.")
        return 0

    if state and state.get("records") is not None and not (args.resume or args.restart):
        done = len(state["records"])
        print(f"{STATE_PATH.as_posix()} already holds {done} of {state.get('total_cases')} case(s).")
        print("Pass --resume to carry on, or --restart to throw it away and begin again.")
        return 1
    if args.restart or not state or state.get("records") is None:
        state = fresh_state(total, args.budget)
    else:
        state["token_budget"] = args.budget
        state["stopped_because"] = None
        state["total_cases"] = total

    # Per-run counters. The budget and the cap apply to *this* run, so a resume gets
    # its own allowance; the lifetime totals above are what the report quotes for cost.
    state["runs"] = state.get("runs", 0) + 1
    state["last_run_tokens"] = 0
    state["last_run_calls"] = 0

    done_ids = {record["id"] for record in state["records"]}
    todo = [case for case in cases if case["id"] not in done_ids]

    print(f"provider {state['provider']} / model {state['model']}")
    print(f"{len(todo)} case(s) to run, {len(done_ids)} already done, {total} in total")
    print(f"budget {args.budget:,} tokens, cap {CALL_CAP} calls, {args.interval} s between calls")
    print(f"lifetime so far: {state['tokens_used']:,} tokens, {state['calls_made']} calls "
          f"over {state['runs'] - 1} earlier run(s)")
    print()

    client = GroqLLM(min_interval_s=args.interval)
    index = get_index()
    write_report(state, total)

    for case in todo:
        if state["last_run_tokens"] >= args.budget:
            state["stopped_because"] = "token_budget"
            break
        if state["last_run_calls"] >= CALL_CAP:
            state["stopped_because"] = "call_cap"
            break

        print(f"  {case['id']:<16} {case['question'][:58]}")
        record = run_case(case, client, index)
        state["records"].append(record)
        spent = record.get("input_tokens", 0) + record.get("output_tokens", 0)
        state["tokens_used"] += spent
        state["last_run_tokens"] += spent
        state["calls_made"] += record.get("api_calls", 0)
        state["last_run_calls"] += record.get("api_calls", 0)
        state["rate_limit_events"] += record.get("rate_limit_events", 0)
        state["api_retries"] += record.get("api_retries", 0)
        state["last_rate_limit"] = dict(client.last_rate_limit)
        save_state(state)
        write_report(state, total)

        if record.get("error"):
            print(f"      FAILED: {record['error'][:110]}")
        else:
            outcome = (
                f"abstained ({record['abstain_reason']})"
                if record["abstained"]
                else f"answered, {len(record['citations'])} citation(s), {record['answer_words']} words"
            )
            print(
                f"      {outcome}; {record['latency_ms'] / 1000:.1f}s, "
                f"{record['input_tokens']}+{record['output_tokens']} tokens"
            )
            for problem in problems_of(record):
                print(f"      ! {problem}")
    else:
        state["stopped_because"] = "finished" if not todo or len(state["records"]) >= total else None

    if state["stopped_because"] is None:
        state["stopped_because"] = "finished" if len(state["records"]) >= total else "stopped"
    save_state(state)
    write_report(state, total)

    records = state["records"]
    answered = sum(1 for item in records if not item.get("error") and not item.get("abstained"))
    abstained = sum(1 for item in records if not item.get("error") and item.get("abstained"))
    failed = sum(1 for item in records if item.get("error"))
    flagged = sum(1 for item in records if problems_of(item))
    latencies = [item["latency_ms"] for item in records if item.get("latency_ms")]

    print()
    print(f"state: {state['stopped_because']}")
    print(f"{len(records)} of {total} case(s) done: {answered} answered, {abstained} abstained, {failed} failed")
    print(f"{flagged} case(s) tripped at least one suspected-problem rule")
    print(
        f"this run: {state['last_run_tokens']:,} of {args.budget:,} tokens, "
        f"{state['last_run_calls']} of {CALL_CAP} calls"
    )
    print(f"all runs: {state['tokens_used']:,} tokens, {state['calls_made']} calls")
    print(f"429s: {state['rate_limit_events']}, rate-limit waits: {state['api_retries']}")
    if latencies:
        print(
            f"latency p50 {percentile(latencies, 0.5) / 1000:.1f}s, "
            f"p95 {percentile(latencies, 0.95) / 1000:.1f}s, "
            f"mean {statistics.mean(latencies) / 1000:.1f}s"
        )
    print_comparison(state)
    print(f"wrote {REPORT_PATH.as_posix()} and {STATE_PATH.as_posix()}")
    if state["stopped_because"] in ("token_budget", "call_cap"):
        print("Continue with: uv run python scripts\\live_run.py --resume")
    return 0


if __name__ == "__main__":
    sys.exit(main())
