"""Measure answer quality, not just retrieval, against the human-verified questions.

    uv run python eval/answer_eval.py                 # the real run, against Groq
    uv run python eval/answer_eval.py --resume        # continue a run that stopped
    uv run python eval/answer_eval.py --dry-run        # prove the harness works, no tokens spent

Reads  eval/questions_verified.jsonl - only records with verified: true. Never the
       draft file and never a rejected or skipped record: those carry verified: false
       and must never be scored (see eval/README.md).
Writes eval/results/answers_<timestamp>.md and .json
       eval/results/answer_eval_state.json - a resumable record of every question run

`eval/run_eval.py` answers "was the right clause in the top k?" - retrieval only, no
LLM call, five configurations compared. This script answers a different question: "was
the thing the model actually wrote any good?", on the one configuration ZoneWise ships
with today, each question run exactly once. It changes nothing about retrieval, the
prompts, the claim checker, the thresholds or the questions themselves - this is a
tooling addition, not a tuning run (D-116).

**A location question runs through `app.answer.answer_point`, unmodified** - the exact
function `/api/ask` calls, with the question's own lat/lon and `app.spatial.get_zones`.

**A question with no point runs through `app.agent.run_agent`, unmodified** - the exact
function `/api/agent` calls, with the same round cap, the same structural and claim
checks, and no pin (D-117). Roughly half the verified set (the "general" category
carries no coordinates by design - see eval/README.md) and any should-abstain question
with no point take this path; a should-abstain question with a point still goes through
`answer_point`. Earlier, a no-point question ran through this script's own stand-in,
`answer_general`, because D-116 reasoned the agent would waste its tool-calling rounds
on a question that names no place. That stand-in's prompt called
`app.location.describe_zones({})`, which has no way to say "no point was given" - every
value it can be handed reads as either a zone description or "outside NCT Delhi" - so a
general question was told it was about a place outside Delhi, which biases the model
toward declining. `run_agent` has no such line, because it never calls `describe_zones`
for a point it never established; a question naming no place just skips
`locate_place`/`get_zones` and searches directly. Every record, and the report, say
which mode ran: `"map"` or `"agent"`.

Every LLM call made for one question is counted through `_MeteredLLM`, a thin wrapper
around whichever client was passed in (`GroqLLM`, `AnthropicLLM` or `FakeLLM` in a
test) that reads `app.llm.usage_of` on every reply. That is what lets the same counting
code work for a real provider and for a scripted test.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import run_agent  # noqa: E402
from app.answer import answer_point  # noqa: E402
from app.config import settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402
from app.llm import (  # noqa: E402
    LLM,
    FakeLLM,
    get_llm,
    is_rate_limited,
    provider_error_line,
    usage_of,
)
from app.retrieval import SearchIndex, get_index  # noqa: E402
from eval.metrics import percentile, wilson_interval  # noqa: E402

#: Nobody may run this against fewer than this many verified questions. 40 is the same
#: floor eval/README.md asks a person to reach before trusting any retrieval number;
#: the same reasoning applies here with more force, because an answer-level run spends
#: real tokens (D-116).
MIN_VERIFIED = 40

#: Where the verified questions live. This script reads only this file - never
#: questions_draft.jsonl, and never a record with verified: false in this file either.
VERIFIED_PATH = settings.project_root / "eval" / "questions_verified.jsonl"

DEFAULT_STATE_PATH = settings.project_root / "eval" / "results" / "answer_eval_state.json"
DEFAULT_BUDGET_TOKENS = 180_000
DEFAULT_MAX_CALLS = 300


class InsufficientQuestions(RuntimeError):
    """Raised when there are not enough verified questions to run on."""


# --- loading the verified questions ----------------------------------------------


def load_verified_questions(path: Path = VERIFIED_PATH) -> list[dict]:
    """Every record in `path` with `verified: true`. [] when the file does not exist yet."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return [row for row in rows if row.get("verified")]


def ensure_enough(questions: list[dict], minimum: int = MIN_VERIFIED) -> None:
    """Raise `InsufficientQuestions` unless there are at least `minimum` of them."""
    if len(questions) < minimum:
        raise InsufficientQuestions(
            f"only {len(questions)} verified question(s) in "
            f"{VERIFIED_PATH.relative_to(settings.project_root).as_posix()}; need at "
            f"least {minimum}. Verify more with the Verify screen (see eval/README.md) "
            "before running this for real."
        )


# --- counting tokens and calls, whatever the provider -----------------------------


class _MeteredLLM:
    """Wraps any LLM client and counts the calls and tokens made through it.

    One of these is built fresh for every question, so its counters are that
    question's cost and nothing else's. It works the same way for `GroqLLM`,
    `AnthropicLLM` and `FakeLLM`, because it reads `usage_of` on the reply rather than
    a provider-specific counter - `FakeLLM` has no `.input_tokens` attribute at all,
    which is what rules out reusing `scripts/live_run.py`'s approach of diffing the
    client's own counters.
    """

    def __init__(self, inner: LLM) -> None:
        self.inner = inner
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def chat(self, **kwargs: Any) -> Any:
        response = self.inner.chat(**kwargs)
        self.calls += 1
        input_tokens, output_tokens = usage_of(response)
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        return response


# --- running one question ----------------------------------------------------------


def run_one(question: dict, llm: LLM, index: SearchIndex) -> dict:
    """Run one verified question through the production answer path, and record it.

    A question with a point runs through `answer_point`, exactly as `/api/ask` does. A
    question with none runs through `app.agent.run_agent`, exactly as `/api/agent` does
    - with no pin, the same round cap, and the same checks - not a location-free
    stand-in (D-117).
    """
    has_point = question.get("lat") is not None and question.get("lon") is not None
    mode = "map" if has_point else "agent"
    metered = _MeteredLLM(llm)

    if has_point:
        result = answer_point(
            question["question"], question["lat"], question["lon"], llm=metered, index=index
        )
    else:
        result = run_agent(question["question"], llm=metered, index=index)

    cited = [citation.chunk_id for citation in result.citations]
    wanted = set(question.get("expected_chunk_ids") or []) | set(
        question.get("acceptable_chunk_ids") or []
    )
    support = result.support_check or {}

    return {
        "id": question["id"],
        "category": question["category"],
        "should_abstain": bool(question.get("should_abstain")),
        "mode": mode,
        "has_point": has_point,
        "answered": not result.abstained,
        "abstained": result.abstained,
        "abstain_reason": result.abstain_reason,
        "cited_chunk_ids": cited,
        # "at least one cited chunk is in expected_chunk_ids or acceptable_chunk_ids" -
        # only meaningful for an answered question; an abstention cites nothing.
        "cites_verified_clause": bool(cited and wanted & set(cited)),
        # No retry was needed, which the structural check guarantees means every
        # citation named a real source; and the claim check found nothing to drop.
        # Both have to hold for "every citation passed validation" to be true.
        "citations_valid_first_attempt": not result.validation_failures,
        "validation_retries": len(result.validation_failures),
        "support_mode": support.get("mode"),
        "support_ran": bool(support.get("ran")),
        "support_counts": dict(support.get("counts") or {}),
        "support_dropped": list(support.get("dropped") or []),
        "support_enforced": bool(support.get("enforced")),
        "llm_calls": metered.calls,
        "input_tokens": metered.input_tokens,
        "output_tokens": metered.output_tokens,
        "tokens_total": metered.input_tokens + metered.output_tokens,
        "latency_ms": result.latency_ms,
        "answer_words": len((result.answer_markdown or "").split()),
    }


def citations_fully_valid(record: dict) -> bool:
    """True when nothing had to be retried and the claim check dropped nothing."""
    return bool(record.get("citations_valid_first_attempt")) and not record.get(
        "support_enforced"
    )


# --- the resumable run --------------------------------------------------------------


def now() -> str:
    """The time, to the second."""
    return datetime.now().isoformat(timespec="seconds")


def fresh_state(total: int, budget_tokens: int, max_calls: int) -> dict:
    """A new run's state."""
    return {
        "started_at": now(),
        "updated_at": now(),
        "total_questions": total,
        "budget_tokens": budget_tokens,
        "max_calls": max_calls,
        "tokens_used_total": 0,
        "calls_made_total": 0,
        "runs": 0,
        "last_run_tokens": 0,
        "last_run_calls": 0,
        "stopped_because": None,
        "last_rate_limit_error": "",
        "records": [],
    }


def load_state(path: Path) -> dict:
    """The state file, or {} when it does not exist or will not parse."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict, path: Path) -> None:
    """Write the state file. Called after every question, which is what makes --resume work."""
    state["updated_at"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_questions(
    questions: list[dict],
    llm: LLM,
    index: SearchIndex,
    state: dict,
    budget_tokens: int,
    max_calls: int,
    state_path: Path | None = None,
) -> None:
    """Run every question not already in `state`, stopping cleanly on a cap or a 429.

    Mutates `state` in place and saves it after every question when `state_path` is
    given, which is what lets a run stopped by its own cap or by Groq's daily limit be
    continued later with `--resume` and lose nothing but the time spent. Never sleeps
    and never retries a rate limit itself - the provider client already does that
    (`app/llm.py`'s `GroqLLM._send_with_retries`); what reaches here is the point a
    whole day's quota is gone, and the only sane response to that is to stop.
    """
    state["runs"] = state.get("runs", 0) + 1
    state["last_run_tokens"] = 0
    state["last_run_calls"] = 0
    state["stopped_because"] = None

    done_ids = {record["id"] for record in state["records"]}
    todo = [question for question in questions if question["id"] not in done_ids]

    for question in todo:
        if state["last_run_tokens"] >= budget_tokens:
            state["stopped_because"] = "token_budget"
            break
        if state["last_run_calls"] >= max_calls:
            state["stopped_because"] = "call_cap"
            break

        try:
            record = run_one(question, llm, index)
        except Exception as exc:
            if is_rate_limited(exc):
                state["stopped_because"] = "rate_limited"
                state["last_rate_limit_error"] = provider_error_line(exc)
                break
            has_point = question.get("lat") is not None and question.get("lon") is not None
            record = {
                "id": question["id"],
                "category": question["category"],
                "should_abstain": bool(question.get("should_abstain")),
                "mode": "map" if has_point else "agent",
                "error": provider_error_line(exc),
            }

        state["records"].append(record)
        spent_tokens = record.get("tokens_total", 0)
        spent_calls = record.get("llm_calls", 0)
        state["last_run_tokens"] += spent_tokens
        state["last_run_calls"] += spent_calls
        state["tokens_used_total"] = state.get("tokens_used_total", 0) + spent_tokens
        state["calls_made_total"] = state.get("calls_made_total", 0) + spent_calls
        if state_path is not None:
            save_state(state, state_path)
    else:
        state["stopped_because"] = "finished"

    if state["stopped_because"] is None:
        state["stopped_because"] = "finished" if len(state["records"]) >= len(questions) else "stopped"
    if state_path is not None:
        save_state(state, state_path)


# --- the report ----------------------------------------------------------------


def git_commit() -> str:
    """The current commit's short hash, or "unknown" when git cannot say."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=settings.project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def git_tag() -> str:
    """A tag exactly on the current commit, or "" when there is none."""
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=settings.project_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def rate_cell(successes: int, n: int) -> str:
    """"x/n (NN%, [lo, hi])" - a count, its rate and the Wilson 95% interval."""
    if n == 0:
        return "n/a (n=0)"
    low, high = wilson_interval(successes, n)
    return f"{successes}/{n} ({successes / n:.0%}, [{low:.0%}, {high:.0%}])"


def ok_records(state: dict) -> list[dict]:
    """Every record that actually ran, excluding one a provider failure broke."""
    return [record for record in state["records"] if "error" not in record]


def failed_records(state: dict) -> list[dict]:
    """Every record a provider failure broke outright."""
    return [record for record in state["records"] if "error" in record]


def group_lines(records: list[dict], label: str) -> list[str]:
    """The four answer-level rates for one group of answerable records."""
    n = len(records)
    answered = [r for r in records if r["answered"]]
    cites_verified = sum(1 for r in answered if r["cites_verified_clause"])
    fully_valid = sum(1 for r in answered if citations_fully_valid(r))
    supported = sum((r.get("support_counts") or {}).get("supported", 0) for r in answered)
    partly = sum((r.get("support_counts") or {}).get("partly", 0) for r in answered)
    unsupported = sum((r.get("support_counts") or {}).get("unsupported", 0) for r in answered)
    checked = [r for r in answered if r.get("support_ran")]
    total_sentences = sum(sum((r.get("support_counts") or {}).values()) for r in checked)

    lines = [
        f"### {label}",
        "",
        markdown_table(
            ("metric", "value"),
            [
                ["n (answerable)", str(n)],
                ["answered", rate_cell(len(answered), n)],
                [
                    "...of those, cites a verified clause",
                    rate_cell(cites_verified, len(answered)),
                ],
                [
                    "...of those, citations all passed validation",
                    rate_cell(fully_valid, len(answered)),
                ],
                ["sentences checked by the claim check", str(total_sentences)],
                [
                    "...of those, rated supported",
                    rate_cell(supported, total_sentences),
                ],
                ["...rated partly", f"{partly}/{total_sentences}" if total_sentences else "n/a"],
                [
                    "...rated unsupported",
                    f"{unsupported}/{total_sentences}" if total_sentences else "n/a",
                ],
            ],
        ),
        "",
    ]
    return lines


def detail_rows(state: dict) -> list[list[str]]:
    """One row per question, in the order it ran."""
    rows = []
    for record in state["records"]:
        if "error" in record:
            rows.append(
                [
                    record["id"],
                    record.get("category", ""),
                    record.get("mode", ""),
                    "yes" if record.get("should_abstain") else "no",
                    f"FAILED: {record['error'][:60]}",
                    "-",
                    "-",
                    "-",
                    "-",
                ]
            )
            continue
        outcome = (
            f"abstained ({record['abstain_reason']})" if record["abstained"] else "answered"
        )
        rows.append(
            [
                record["id"],
                record["category"],
                record["mode"],
                "yes" if record["should_abstain"] else "no",
                outcome,
                "yes" if record["cites_verified_clause"] else ("-" if record["abstained"] else "no"),
                "yes" if citations_fully_valid(record) else "no",
                str(record["tokens_total"]),
                f"{record['latency_ms']} ms",
            ]
        )
    return rows


HEADER_TEMPLATE = """\
> **One run on the frozen system, not a tuning run.** Commit `{commit}`{tag_clause}. \
`SUPPORT_CHECK={support_check}`, `ABSTAIN_SIGNAL={abstain_signal}`, \
`ABSTAIN_THRESHOLD={abstain_threshold}` - whatever `app/config.py` currently resolves \
to, read and reported, never overridden by this script (unlike `eval/run_eval.py`, \
which deliberately swaps configurations to compare them).
>
> **The claim-check rows are a model judging a model.** `run_support_check` is itself \
an LLM call, scored here exactly as it is used in production: evidence about the \
answers, not proof, and never free of the judge's own blind spots.
>
> **Nothing here was tuned on these questions.** No prompt, threshold, retrieval \
setting or claim-check rule was changed because of what this run found; a number that \
looked wrong is a finding for a future round, not a reason to edit this one.
"""


def build_report(
    state: dict,
    questions: list[dict],
    dry_run: bool,
    generated_at: str,
    commit: str,
    tag: str,
) -> tuple[str, dict]:
    """The Markdown report and the matching JSON record."""
    records = ok_records(state)
    failed = failed_records(state)

    answerable = [r for r in records if not r["should_abstain"]]
    should_abstain = [r for r in records if r["should_abstain"]]
    declined = sum(1 for r in should_abstain if r["abstained"]) if should_abstain else 0

    by_category: dict[str, list[dict]] = {}
    for record in answerable:
        by_category.setdefault(record["category"], []).append(record)

    tag_clause = f", tag `{tag}`" if tag else " (no tag on this commit)"
    lines: list[str] = []
    if dry_run:
        lines += [
            "> # DRY RUN - FakeLLM, no tokens spent",
            "> This run proves the harness executes end to end. It is not a measurement "
            "of answer quality: every reply came from a scripted stand-in, not a model.",
            "",
        ]
    lines += [
        "# Answer-level evaluation",
        "",
        f"Generated {generated_at} by `eval/answer_eval.py`.",
        "",
        HEADER_TEMPLATE.format(
            commit=commit,
            tag_clause=tag_clause,
            support_check=settings.support_check,
            abstain_signal=settings.abstention_signal,
            abstain_threshold=settings.abstain_threshold,
        ),
        "",
        f"{len(state['records'])} of {len(questions)} verified question(s) run, "
        f"{len(failed)} failed outright (a provider error, not an abstention).",
        "",
        "A question with a point ran through `answer_point`, exactly as `/api/ask` "
        "does. A question with no point ran through `app.agent.run_agent`, exactly as "
        "`/api/agent` does - the same round cap, the same checks, no pin (D-117). The "
        "`mode` column in the per-question table below says which one ran.",
        "",
        "## Answerable questions",
        "",
    ]
    lines += group_lines(answerable, "Overall")
    for category in sorted(by_category):
        lines += group_lines(by_category[category], category)

    lines += [
        "## Should-abstain questions",
        "",
        f"**{declined} of {len(should_abstain)} declined.** A count, not a rate: "
        "eval/README.md asks that this one never be reported as a percentage, because "
        "a handful of should-abstain questions makes any percentage of them unstable.",
        "",
    ]

    all_tokens = [r["tokens_total"] for r in records]
    all_latency = [r["latency_ms"] for r in records]
    sorted_latency = sorted(all_latency)
    lines += [
        "## Cost",
        "",
        markdown_table(
            ("metric", "value"),
            [
                ["tokens, mean per question", f"{(sum(all_tokens) / len(all_tokens)):,.0f}" if all_tokens else "n/a"],
                ["tokens, total", f"{sum(all_tokens):,}"],
                [
                    "latency, median (includes free-tier throttling)",
                    f"{percentile(sorted_latency, 0.5) / 1000:.1f} s" if sorted_latency else "n/a",
                ],
                [
                    "latency, p95 (includes free-tier throttling)",
                    f"{percentile(sorted_latency, 0.95) / 1000:.1f} s" if sorted_latency else "n/a",
                ],
            ],
        ),
        "",
        "Latency is wall clock around the whole question, exactly as `app/answer.py` "
        "measures it: it includes the enforced gap between calls and any time a "
        "provider's free tier spends holding a request back, not just model think "
        "time.",
        "",
    ]

    if failed:
        lines += [
            "## Failed outright",
            "",
            markdown_table(
                ("id", "category", "mode", "error"),
                [
                    [r["id"], r.get("category", ""), r.get("mode", ""), r["error"][:120]]
                    for r in failed
                ],
            ),
            "",
        ]

    lines += [
        "## Every question",
        "",
        markdown_table(
            (
                "id",
                "category",
                "mode",
                "should abstain",
                "outcome",
                "cites verified clause",
                "citations fully valid",
                "tokens",
                "latency",
            ),
            detail_rows(state),
        ),
        "",
    ]

    record = {
        "generated_at": generated_at,
        "dry_run": dry_run,
        "commit": commit,
        "tag": tag,
        "support_check": settings.support_check,
        "abstain_signal": settings.abstention_signal,
        "abstain_threshold": settings.abstain_threshold,
        "questions_total": len(questions),
        "questions_run": len(state["records"]),
        "failed": len(failed),
        "answerable": {
            "n": len(answerable),
            "answered": sum(1 for r in answerable if r["answered"]),
            "cites_verified_clause": sum(
                1 for r in answerable if r["answered"] and r["cites_verified_clause"]
            ),
            "citations_fully_valid": sum(
                1 for r in answerable if r["answered"] and citations_fully_valid(r)
            ),
            "per_category": {
                category: {
                    "n": len(items),
                    "answered": sum(1 for r in items if r["answered"]),
                }
                for category, items in sorted(by_category.items())
            },
        },
        "should_abstain": {"n": len(should_abstain), "declined": declined},
        "tokens_total": sum(all_tokens),
        "tokens_mean": (sum(all_tokens) / len(all_tokens)) if all_tokens else 0.0,
        "latency_median_ms": percentile(sorted_latency, 0.5) if sorted_latency else 0.0,
        "latency_p95_ms": percentile(sorted_latency, 0.95) if sorted_latency else 0.0,
        "records": state["records"],
    }
    return "\n".join(lines).rstrip() + "\n", record


# --- the CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run every verified question once through the production answer path."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Evaluate ZoneWise answer quality.")
    parser.add_argument(
        "--budget-tokens",
        type=int,
        default=DEFAULT_BUDGET_TOKENS,
        help=f"token budget for this run (default {DEFAULT_BUDGET_TOKENS:,})",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_CALLS,
        help=f"the most LLM calls this run may make (default {DEFAULT_MAX_CALLS})",
    )
    parser.add_argument(
        "--state",
        default=str(DEFAULT_STATE_PATH),
        help=f"state file (default {DEFAULT_STATE_PATH.as_posix()})",
    )
    parser.add_argument("--resume", action="store_true", help="continue a run that stopped")
    parser.add_argument("--restart", action="store_true", help="discard a partial run and start over")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="use FakeLLM instead of a real provider; spends no tokens, report marked DRY RUN",
    )
    args = parser.parse_args(argv)

    questions = load_verified_questions(VERIFIED_PATH)
    try:
        ensure_enough(questions)
    except InsufficientQuestions as exc:
        print(str(exc))
        return 1

    state_path = Path(args.state)
    state = load_state(state_path)
    if state.get("records") and not args.resume and not args.restart:
        print(
            f"{state_path.as_posix()} already holds {len(state['records'])} of "
            f"{state.get('total_questions')} question(s)."
        )
        print("Pass --resume to carry on, or --restart to throw it away and begin again.")
        return 1
    if args.restart or not state or state.get("records") is None:
        state = fresh_state(len(questions), args.budget_tokens, args.max_calls)
    else:
        state["budget_tokens"] = args.budget_tokens
        state["max_calls"] = args.max_calls
        state["total_questions"] = len(questions)

    if args.dry_run:

        def scripted(**call: Any) -> str:
            """A well-formed reply for whatever this call was: an answer or a claim check."""
            content = call["messages"][-1]["content"] if call.get("messages") else ""
            if isinstance(content, str) and "Check these sentences" in content:
                count = content.count("Sentence ")
                verdicts = [
                    {"i": i, "verdict": "supported", "reason": "dry run"}
                    for i in range(1, count + 1)
                ]
                return json.dumps({"verdicts": verdicts})
            text = content if isinstance(content, str) else ""
            labels = sorted(set(re.findall(r"\[([A-Za-z]\d+)\]", text)))
            if not labels:
                return json.dumps({"abstain": "dry run: no sources", "sentences": []})
            return json.dumps(
                {
                    "abstain": None,
                    "sentences": [{"text": "Dry run placeholder answer.", "citations": [labels[0]]}],
                }
            )

        llm: LLM = FakeLLM(responses=[scripted] * (len(questions) * 6 + 10))
    else:
        if settings.llm_provider != "groq":
            print(f"LLM_PROVIDER is {settings.llm_provider!r}, not 'groq'.")
        llm = get_llm()

    index = get_index()
    print(
        f"{len(questions)} verified question(s); "
        f"{len(state.get('records', []))} already done"
    )
    if args.dry_run:
        print("DRY RUN: FakeLLM, no tokens will be spent.")
    print()

    run_questions(
        questions, llm, index, state, args.budget_tokens, args.max_calls, state_path
    )

    generated_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report, record = build_report(
        state, questions, args.dry_run, generated_at, git_commit(), git_tag()
    )

    out_dir = settings.project_root / "eval" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "DRYRUN_" if args.dry_run else ""
    report_path = out_dir / f"{prefix}answers_{stamp}.md"
    json_path = out_dir / f"{prefix}answers_{stamp}.json"
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    done = len(state["records"])
    answered = sum(1 for r in ok_records(state) if r["answered"])
    abstained = sum(1 for r in ok_records(state) if r["abstained"])
    failed = len(failed_records(state))
    print(f"state: {state['stopped_because']}")
    print(f"{done} of {len(questions)} question(s) run: {answered} answered, {abstained} abstained, {failed} failed")
    print(
        f"this run: {state['last_run_tokens']:,} of {args.budget_tokens:,} tokens, "
        f"{state['last_run_calls']} of {args.max_calls} calls"
    )
    print(f"wrote {report_path.relative_to(settings.project_root).as_posix()} and "
          f"{json_path.relative_to(settings.project_root).as_posix()}")
    if state["stopped_because"] in ("token_budget", "call_cap", "rate_limited"):
        if state["stopped_because"] == "rate_limited":
            print(f"stopped on Groq's rate limit: {state['last_rate_limit_error']}")
        print(f"Continue with: uv run python eval/answer_eval.py --resume --state {state_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
