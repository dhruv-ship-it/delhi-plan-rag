"""The one testable piece of scripts/live_run.py: which cases a run selects.

The script itself is a recorder — it makes real LLM calls and writes a report — so
nothing else in it is unit-testable without a key. `--cases` is different: it decides
what a verification run actually checks, and a silent miss there would mean a run that
proves nothing. Added with the option in fix round 1, task 8 (D-106).

The module is loaded by path because `scripts/` is not a package: every script puts the
repo root on `sys.path` itself and is meant to be run, not imported.
"""

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_run.py"


def load_live_run():
    """Import scripts/live_run.py as a module, by path."""
    spec = importlib.util.spec_from_file_location("live_run_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASES = [
    {"id": "demo-03"},
    {"id": "demo-04"},
    {"id": "agent-02"},
    {"id": "agent-05"},
    {"id": "probe-02"},
]


def test_cases_selects_exactly_the_ids_it_is_given() -> None:
    chosen, unknown = load_live_run().select_cases(CASES, wanted="demo-04,agent-05")

    assert [case["id"] for case in chosen] == ["demo-04", "agent-05"]
    assert unknown == []


def test_the_order_is_the_case_sets_own_not_the_order_typed() -> None:
    """So a run's numbering and report order do not depend on how the flag was typed."""
    chosen, _ = load_live_run().select_cases(CASES, wanted="probe-02, demo-03")

    assert [case["id"] for case in chosen] == ["demo-03", "probe-02"]


def test_an_unknown_id_is_reported_rather_than_dropped() -> None:
    """A typo must stop the run, not quietly shrink it."""
    chosen, unknown = load_live_run().select_cases(CASES, wanted="demo-03,demo-99")

    assert [case["id"] for case in chosen] == ["demo-03"]
    assert unknown == ["demo-99"]


def test_cases_wins_over_only_and_no_filter_keeps_everything() -> None:
    live_run = load_live_run()

    chosen, _ = live_run.select_cases(CASES, only="agent", wanted="demo-03")
    assert [case["id"] for case in chosen] == ["demo-03"]

    chosen, _ = live_run.select_cases(CASES, only="agent")
    assert [case["id"] for case in chosen] == ["agent-02", "agent-05"]

    chosen, unknown = live_run.select_cases(CASES)
    assert len(chosen) == len(CASES) and unknown == []


@pytest.mark.needs_data
def test_the_two_ridge_cases_expect_either(monkeypatch) -> None:
    """agent-05 and probe-02 are not answerable from the index (D-106).

    `build_cases()` reads `data/test_points.json` and the drafted questions, hence the
    marker: on a clean clone there is nothing to build the DEMO cases from.
    """
    live_run = load_live_run()
    cases = {case["id"]: case for case in live_run.build_cases()}

    for case_id in ("agent-05", "probe-02"):
        assert cases[case_id]["expect"] == "either", case_id
        assert "cycling connector" in cases[case_id]["note"], case_id
    # the other four agent cases are unchanged
    for case_id in ("agent-01", "agent-02", "agent-03", "agent-04"):
        assert cases[case_id]["expect"] == "answer", case_id
