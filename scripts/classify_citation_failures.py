"""Classify the citation-check failures of a live run, by the rule that rejected them.

    uv run python scripts/classify_citation_failures.py
    uv run python scripts/classify_citation_failures.py --state reports/live_run_state_v2.json

`reports/live_answers_v1.md` says 18 of the map-mode cases needed the single citation
retry (D-085), which made the retry part of the normal path rather than a safety margin.
This script asks the next question: **which rule kept firing.** There are only three
(D-043) — an unknown marker, a sentence with no marker, and an empty answer — and they
point at different fixes, so the count matters before anything is changed.

**v1 cannot answer it directly, and that is the first finding.** `scripts/live_run.py`
records the *final* answer and a retry *count*; it never recorded the rejected attempt or
the problems list that `citation_problems()` produced. So for a v1 state file this script
reports the first-attempt outcome of every map case exactly, and then measures the
**fingerprint** the surviving answers carry — which is evidence about the rule, not the
rule itself, and is labelled as such.

A v2 state file carries `validation_failures` per case, one problems list per rejected
attempt, so for those the classification is read rather than inferred.

Safe to re-run: reads one JSON file, writes one report, makes no model call.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.answer import MARKER, sentences_of  # noqa: E402
from app.extract import use_utf8_output  # noqa: E402

#: The three rules `citation_problems()` can report, by the opening of their message.
RULES = {
    "unknown marker": "does not refer to a source you were given",
    "uncited sentence": "carry no citation marker at all",
    "empty answer": "The answer is empty.",
}

#: Prompt rule 6 asks for this sentence, and no clause in the corpus supports it. It is
#: the one sentence the prompt itself guarantees will be uncitable.
#:
#: Both halves are required — the authority *and* the advice to go and check it —
#: because a sentence that merely names DDA is usually a real clause being summarised
#: ("DDA shall act as main anchor for preparation of schemes"), and "the FAQs confirm
#: that DDA will prepare the schemes" is a reporting verb rather than advice.
DDA_ADVICE = re.compile(
    r"\b(official|dda)\b.*\b(should|must|may|can)\s+(?:\w+\s+)?be\s+"
    r"(check|consult|confirm|verif)",
    re.IGNORECASE,
)

#: How many examples of each rule to print.
EXAMPLES = 2


def rule_of(problem: str) -> str:
    """Which of the three rules a problems-list entry is."""
    for name, needle in RULES.items():
        if needle in problem:
            return name
    return "other"


def map_cases(records: list[dict]) -> list[dict]:
    """The map-mode cases, in the order they ran."""
    return [record for record in records if record.get("mode") == "map"]


def first_attempt_outcome(record: dict) -> str:
    """What happened to this case's first answer, as far as the state file knows."""
    if record.get("error"):
        return "the call failed"
    reason = record.get("abstain_reason") or ""
    if reason.startswith("outside_delhi"):
        return "never reached the model"
    if reason.startswith("model_abstained"):
        return "the model declined, so there was nothing to check"
    if record.get("citation_retry"):
        return "failed the check"
    return "passed the check"


def marker_numbers(text: str) -> list[int]:
    """The source numbers cited in a piece of text."""
    return [int(number) for number in MARKER.findall(text or "")]


def fingerprint(record: dict) -> dict:
    """Structural facts about a final answer that bear on which rule fired.

    None of this is the rejected attempt. It is what the model wrote *while being told*
    to put a marker on every sentence, which is informative about what it does when it
    is not: an answer whose markers repeat sentence by sentence inside one line is an
    answer that had to be made marker-dense to get past the splitter.
    """
    answer = record.get("answer") or ""
    lines = [line for line in answer.split("\n") if line.strip()]
    per_line = [len(sentences_of(line)) for line in lines]
    sentences = sentences_of(answer)

    repeated = 0
    for line in lines:
        previous: tuple[int, ...] | None = None
        for sentence in sentences_of(line):
            current = tuple(sorted(set(marker_numbers(sentence))))
            if current and current == previous:
                repeated += 1
            previous = current

    advice = [sentence for sentence in sentences if DDA_ADVICE.search(sentence)]
    numbers = marker_numbers(answer)
    return {
        "lines": len(lines),
        "sentences": len(sentences),
        "multi_sentence_lines": sum(1 for count in per_line if count > 1),
        "max_sentences_in_a_line": max(per_line) if per_line else 0,
        "markers": len(numbers),
        "distinct_markers": len(set(numbers)),
        "highest_marker": max(numbers) if numbers else 0,
        "repeated_marker_sentences": repeated,
        "has_dda_advice_sentence": bool(advice),
        "dda_advice_cited": bool(advice) and all(marker_numbers(s) for s in advice),
    }


def lines_for(state: dict, path: Path) -> list[str]:
    """The whole report."""
    records = state.get("records") or []
    cases = map_cases(records)
    outcomes = Counter(first_attempt_outcome(record) for record in cases)
    checked = [
        record
        for record in cases
        if first_attempt_outcome(record) in ("failed the check", "passed the check")
    ]
    failed = [r for r in checked if first_attempt_outcome(r) == "failed the check"]
    twice = [r for r in failed if (r.get("abstain_reason") or "").startswith("citation_check_failed")]

    # v2 and later record the problems of every rejected attempt.
    recorded: Counter = Counter()
    examples: dict[str, list[tuple[str, str]]] = {}
    for record in cases:
        for attempt in record.get("validation_failures") or []:
            for problem in attempt:
                name = rule_of(problem)
                recorded[name] += 1
                examples.setdefault(name, []).append((record["id"], problem))

    out = [
        "# Why the citation retries happened (v1)",
        "",
        f"Read from `{path.as_posix()}`, {len(records)} recorded case(s), "
        f"{len(cases)} of them map mode. Regenerate with "
        "`uv run python scripts\\classify_citation_failures.py`.",
        "",
    ]

    if not recorded:
        out += [
            "## The question this file was asked, and why it cannot be answered exactly",
            "",
            "The task was to classify **every first-attempt validation failure by rule** —",
            "unknown marker, uncited sentence, a sentence-splitting artefact, or something",
            "else. That cannot be done from a v1 state file, and the reason is worth stating",
            "plainly rather than worked around:",
            "",
            "- `app/answer.py` built the problems list, put it in the retry prompt, and threw",
            "  it away. Nothing returned it to the caller.",
            "- `scripts/live_run.py` recorded the **final** answer and the retry **count**. The",
            "  rejected attempt was never written down, and neither was the problems list.",
            "- `data/logs/requests.jsonl` is written by `app/api.py`; the live run called",
            "  `answer_point` directly, so none of it is in there either.",
            "",
            "So the 18 retries are a number without a breakdown. Two things follow. The",
            "structured-answer change this file was written to sanity-check **adds",
            "`validation_failures` to `AnswerResult`**, one problems list per rejected",
            "attempt, so a v2 state file answers the question by being read rather than",
            "inferred from. And what *can* be derived from v1 is derived below, labelled for",
            "what it is.",
            "",
        ]
    else:
        out += [
            "## First-attempt failures by rule, as recorded",
            "",
            "| rule | n | examples |",
            "| --- | --- | --- |",
        ]
        for name, count in recorded.most_common():
            shown = "; ".join(
                f"`{case_id}`" for case_id, _ in examples.get(name, [])[:EXAMPLES]
            )
            out.append(f"| {name} | **{count}** | {shown} |")
        out.append("")
        for name, count in recorded.most_common():
            out += [f"**{name}**, {count} time(s). First {EXAMPLES}:", ""]
            for case_id, problem in examples.get(name, [])[:EXAMPLES]:
                out.append(f"- `{case_id}` — {problem}")
            out.append("")

    out += [
        "## What the first attempt did, per case (exact)",
        "",
        "This part needs no inference: a map-mode case made one call unless the check",
        "rejected it, so the retry count is the first-attempt verdict.",
        "",
        "| first-attempt outcome | n |",
        "| --- | --- |",
    ]
    for outcome, count in outcomes.most_common():
        out.append(f"| {outcome} | **{count}** |")
    out += [
        "",
        f"So of the **{len(checked)}** map-mode answers that actually reached the citation",
        f"check, **{len(failed)} failed** and **{len(checked) - len(failed)} passed** — a "
        f"first-attempt pass rate of "
        f"**{(len(checked) - len(failed)) / len(checked):.0%}**" if checked else "",
        f"({len(checked) - len(failed)} of {len(checked)}). "
        f"{len(failed) - len(twice)} were rescued by the single retry and **{len(twice)}** "
        "failed twice and abstained.",
        "",
        "| | cases |",
        "| --- | --- |",
        "| passed first time | "
        + (", ".join(f"`{r['id']}`" for r in checked if r not in failed) or "(none)")
        + " |",
        "| failed, then passed | "
        + (", ".join(f"`{r['id']}`" for r in failed if r not in twice) or "(none)")
        + " |",
        "| failed twice | " + (", ".join(f"`{r['id']}`" for r in twice) or "(none)") + " |",
        "",
    ]

    answered = [record for record in cases if record.get("answer")]
    prints = [fingerprint(record) for record in answered]
    if prints:
        multi = sum(1 for p in prints if p["multi_sentence_lines"])
        repeated = sum(1 for p in prints if p["repeated_marker_sentences"])
        advice = sum(1 for p in prints if p["has_dda_advice_sentence"])
        advice_cited = sum(1 for p in prints if p["dda_advice_cited"])
        top_marker = sum(1 for p in prints if p["highest_marker"] >= 6)
        out += [
            "## What the surviving answers suggest about the rule (inference, not record)",
            "",
            f"Measured over the **{len(answered)}** map-mode answers that were shown. Every",
            "one of them passed, so none of these numbers is a failure; they describe the",
            "shape the model had to reach, which is evidence about what it had to be told.",
            "",
            "| measurement | n of " + str(len(answered)) + " |",
            "| --- | --- |",
            f"| answers with at least one line holding more than one sentence | **{multi}** |",
            f"| answers where a marker is repeated sentence-by-sentence inside one line | **{repeated}** |",
            f"| answers carrying prompt rule 6's “check official DDA documents” sentence | **{advice}** |",
            f"| … and that sentence carries a citation marker | **{advice_cited}** |",
            f"| answers that cite the last source available to them (`[C6]`) | **{top_marker}** |",
            "",
            "Read the third and fourth rows together, because they are the sharpest thing in",
            "this file. **The prompt's own rules 2 and 6 conflict.** Rule 6 asks the model to",
            "say that official DDA documents should be checked; no clause in the corpus says",
            "that, so the sentence has no source. Rule 2 says every sentence must carry a",
            "marker. The only way to satisfy both is to attach a marker to a sentence the",
            "marker does not support — which is what the surviving answers do, and which the",
            "citation check cannot detect, because it checks that a marker is *present* and",
            "*valid*, never that the clause *says* the sentence.",
            "",
            "That is consistent with `uncited sentence` being the rule that fired, and with",
            "the splitter being how it fired: a model writing ordinary prose puts one marker",
            "at the end of a thought, and a thought is often two sentences. It is **not**",
            "proof. The alternative — `unknown marker` — cannot be ruled out from here,",
            "though it is the less likely of the two: the sources are printed to the model as",
            "`[C1]` to `[C6]` immediately above the question, and an out-of-range marker",
            "means inventing a seventh.",
            "",
        ]

    out += [
        "## What this says about the structured-answer change",
        "",
        "It supports it, and it also moves the target.",
        "",
        "1. **If the rule was `uncited sentence`, structure removes the rule.** The model",
        "   returns `{\"sentences\": [{\"text\": …, \"citations\": […]}]}`, so there is no",
        "   splitter to disagree with and no way to write a sentence without a citation",
        "   field — the pairing is the data structure rather than a convention about where",
        "   to put brackets. A list item, a heading and a parenthetical stop being hazards.",
        "2. **If the rule was `unknown marker`, structure still helps**, because a citation",
        "   is now one array element to check rather than a token inside prose, and the",
        "   retry can name it exactly.",
        "3. **Neither fixes the thing this file actually found.** A marker attached to a",
        "   sentence it does not support passes every structural check there is. That is",
        "   why the no-synthesis prompt rule ships alongside the JSON contract, and it is",
        "   the same limitation `docs/ARCHITECTURE.md` already states and that `demo-07`",
        "   demonstrated live (D-085).",
        "",
    ]
    return out


def main() -> int:
    """Read a state file, classify what it can, and write the report."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        default="reports/live_run_state.json",
        help="the live-run state file to read (default reports/live_run_state.json)",
    )
    parser.add_argument(
        "--out",
        default="reports/citation_failures_v1.md",
        help="where to write (default reports/citation_failures_v1.md)",
    )
    args = parser.parse_args()

    path = Path(args.state)
    if not path.exists():
        print(f"{path.as_posix()} does not exist. Nothing to classify.")
        return 1
    state = json.loads(path.read_text(encoding="utf-8"))

    lines = lines_for(state, path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    cases = map_cases(state.get("records") or [])
    outcomes = Counter(first_attempt_outcome(record) for record in cases)
    print(f"{len(state.get('records') or [])} case(s) read, {len(cases)} in map mode")
    for outcome, count in outcomes.most_common():
        print(f"  {count:>3}  {outcome}")
    recorded = sum(
        len(attempt)
        for record in cases
        for attempt in (record.get("validation_failures") or [])
    )
    if recorded:
        print(f"{recorded} recorded problem(s) classified by rule")
    else:
        print("no per-attempt problems recorded in this state file (v1); see the report")
    print(f"wrote {out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
