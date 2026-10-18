"""Summarise data/logs/requests.jsonl: what was asked, how fast, and how often refused.

    uv run python scripts/summarize_logs.py
    uv run python scripts/summarize_logs.py --out reports/requests_summary.md
    uv run python scripts/summarize_logs.py --since 2026-10-18

Prints request counts per endpoint, p50 and p95 latency, the abstention rate broken down
by reason, and the questions asked most often. Writes the same as Markdown when `--out`
is given.

This is the operations view of a deployed ZoneWise, and the three numbers worth watching
are not the obvious ones:

  * **the abstention rate by reason.** A rising `weak_retrieval` share means the corpus
    is being asked things it does not cover; a rising `citation_check_failed` share means
    the model cannot ground answers from what retrieval is giving it. Those need
    opposite responses, which is why D-045 made them separate reasons.
  * **p95 rather than the mean.** One 9-second request among a hundred 200ms ones barely
    moves a mean and is the only thing a user remembers.
  * **the daily count against the cap.** The cap is what stands between a bug and an API
    bill (D-051), and a day that hits it is a day someone got a 429 instead of an answer.

The log holds every question anyone asked this server, so it is gitignored (D-052) and
this script never prints an API key, because nothing in the log has ever contained one.

Safe to re-run: it only reads.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402

#: How many of the most-asked questions to list.
TOP_QUESTIONS = 10
#: How much of a question to print, so a long one does not wrap the table.
QUESTION_CHARS = 72


def read_log(path: Path, since: str | None) -> tuple[list[dict], int]:
    """Every readable line of the log, and how many lines could not be parsed.

    A log is appended to by a running server, so the last line can be half-written. A
    summariser that dies on one bad line is useless exactly when it is needed.
    """
    if not path.exists():
        return [], 0
    records, broken = [], 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                broken += 1
                continue
            if since and str(record.get("time", "")) < since:
                continue
            records.append(record)
    return records, broken


def percentile(values: list[float], share: float) -> float | None:
    """The value at `share` through the sorted list, by nearest rank."""
    if not values:
        return None
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, round(share * (len(ordered) - 1))))
    return ordered[position]


def latency_rows(records: list[dict]) -> list[list[str]]:
    """Per endpoint: how many requests, and p50 and p95 latency in milliseconds."""
    by_endpoint: dict[str, list[float]] = defaultdict(list)
    counts: Counter = Counter()
    for record in records:
        endpoint = record.get("endpoint", "?")
        counts[endpoint] += 1
        latency = record.get("latency_ms")
        if isinstance(latency, (int, float)):
            by_endpoint[endpoint].append(float(latency))

    rows = []
    for endpoint, count in counts.most_common():
        timings = by_endpoint.get(endpoint, [])
        p50 = percentile(timings, 0.50)
        p95 = percentile(timings, 0.95)
        rows.append(
            [
                endpoint,
                str(count),
                str(len(timings)),
                "-" if p50 is None else f"{p50:.0f}",
                "-" if p95 is None else f"{p95:.0f}",
            ]
        )
    return rows


def abstention_rows(records: list[dict]) -> tuple[list[list[str]], int, int]:
    """Per reason: how many abstentions. Returns (rows, abstained, answerable).

    Only the two answering endpoints can abstain, so `/api/search` is left out of the
    denominator — including it would make the rate look better the more people searched.
    """
    answering = [record for record in records if record.get("endpoint") in ("ask", "agent")]
    abstained = [record for record in answering if record.get("abstained")]
    reasons: Counter = Counter()
    for record in abstained:
        reason = str(record.get("abstain_reason") or "unknown")
        # "model_abstained: the sources do not cover ..." is one reason with a comment
        reasons[reason.split(":")[0]] += 1

    rows = [
        [
            reason,
            str(count),
            f"{count / len(answering):.1%}" if answering else "-",
        ]
        for reason, count in reasons.most_common()
    ]
    return rows, len(abstained), len(answering)


def question_rows(records: list[dict]) -> list[list[str]]:
    """The most frequently asked questions."""
    asked = Counter(
        " ".join(str(record.get("question", "")).split())
        for record in records
        if record.get("question")
    )
    return [
        [
            str(count),
            question[:QUESTION_CHARS] + ("..." if len(question) > QUESTION_CHARS else ""),
        ]
        for question, count in asked.most_common(TOP_QUESTIONS)
    ]


def build(records: list[dict], broken: int, path: Path, since: str | None) -> str:
    """The whole summary as Markdown."""
    lines = [
        "# ZoneWise request log summary",
        "",
        f"`{path.as_posix()}` — **{len(records)} request(s)**"
        + (f" since {since}" if since else "")
        + (f", {broken} unreadable line(s)" if broken else ""),
        "",
    ]
    if not records:
        lines += [
            "Nothing to summarise. The log is written by `app/api.py` when a request is "
            "answered, so an empty log means the server has not been asked anything yet.",
            "",
        ]
        return "\n".join(lines) + "\n"

    times = sorted(str(record.get("time", "")) for record in records if record.get("time"))
    if times:
        lines += [f"First: `{times[0]}`  Last: `{times[-1]}`", ""]

    by_day = Counter(str(record.get("time", ""))[:10] for record in records if record.get("time"))
    lines += [
        "## Requests per endpoint, and latency",
        "",
        "`timed` is how many of those requests recorded a latency; `/api/search` does "
        "not, because it is not an answering endpoint.",
        "",
        markdown_table(("endpoint", "requests", "timed", "p50 ms", "p95 ms"), latency_rows(records)),
        "",
        "## Requests per day",
        "",
        f"The daily cap is {settings.rate_limit_per_day} answering requests (D-051). A day "
        "at the cap is a day someone was refused.",
        "",
        markdown_table(
            ("day", "requests"),
            [[day, str(count)] for day, count in sorted(by_day.items())],
        ),
        "",
    ]

    rows, abstained, answering = abstention_rows(records)
    lines += [
        "## Abstentions, by reason",
        "",
        f"{abstained} of {answering} answering request(s) were declined"
        + (f" — {abstained / answering:.1%}." if answering else ".")
        + " Each reason means something different and wants a different response: see "
        "D-045.",
        "",
    ]
    lines += [markdown_table(("reason", "count", "share of answering"), rows) if rows else "None.", ""]

    lines += [
        "## Most asked",
        "",
        markdown_table(("times", "question"), question_rows(records)) or "None.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    """Summarise the log and print it."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="also write the summary here as Markdown")
    parser.add_argument(
        "--since", default=None, help="only requests at or after this ISO time, e.g. 2026-10-18"
    )
    args = parser.parse_args()

    path = settings.requests_log_path
    records, broken = read_log(path, args.since)
    summary = build(records, broken, path, args.since)
    print(summary)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(summary, encoding="utf-8")
        print(f"wrote {out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
