"""Check `locate_place` against the live Nominatim service, within a request budget.

    uv run python scripts/check_geocoding.py
    uv run python scripts/check_geocoding.py --budget 4

Prints one row per query: whether the place was found, which of the four steps found it,
and the coordinates. Results are cached, so a second run of the same queries costs
nothing and the budget only limits requests that actually go out.

**The budget is a hard stop, not a warning.** Nominatim is a free service run on donated
hardware and its usage policy asks for restraint; a script that loops over place names
is exactly what the policy exists to prevent. `--budget` counts real requests and the
run stops when it is reached, reporting which queries were not attempted.

Safe to re-run. With a warm cache it makes no requests at all.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.geocode as geocode  # noqa: E402
from app.config import settings  # noqa: E402
from app.extract import markdown_table, use_utf8_output  # noqa: E402
from app.spatial import LayersMissing, get_zones  # noqa: E402

#: The queries from the night-3 brief. The last one must stay not found, or at least
#: come back outside Delhi: it is the check that the bounding box still works.
QUERIES = (
    "Dwarka Sector 21 metro station",
    "near Rajiv Chowk",
    "Hauz Khas",
    "Connaught Place",
    "Mumbai Central",
)

#: How many live requests a run may make by default.
DEFAULT_BUDGET = 8


class BudgetExceeded(RuntimeError):
    """Raised instead of making a request that would go over the budget."""


class CountingSession:
    """Passes requests through to `requests.get` and counts them, up to a limit."""

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.used = 0

    def get(self, url, params=None, headers=None, timeout=None):
        if self.used >= self.budget:
            raise BudgetExceeded(f"{self.budget} live request(s) already made")
        self.used += 1
        import requests

        return requests.get(url, params=params, headers=headers, timeout=timeout)


def inside_delhi(place) -> str:
    """Whether the found point is in NCT Delhi, when the layers are available."""
    if not place.found:
        return "-"
    try:
        zones = get_zones(place.lat, place.lon)
    except LayersMissing:
        return "layers missing"
    return "yes" if zones.get("inside_delhi") else "NO"


def main() -> int:
    """Run the live check and print the table."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budget", type=int, default=DEFAULT_BUDGET, help="how many live requests are allowed"
    )
    args = parser.parse_args()

    stations = len(geocode.gazetteer())
    print(f"gazetteer: {stations} station name(s) loaded from {settings.gazetteer_path.as_posix()}")
    if not stations:
        print("  (empty: scripts/build_gazetteer.py has not run, so every query needs Nominatim)")
    print(f"budget: {args.budget} live request(s)")
    print()

    session = CountingSession(args.budget)
    rows = []
    for query in QUERIES:
        try:
            place = geocode.locate_place(query, session=session)
        except BudgetExceeded as exc:
            rows.append([query, "not attempted", str(exc), "-", "-"])
            continue
        rows.append(
            [
                query,
                "found" if place.found else "not found",
                place.path or "-",
                f"{place.lat:.5f}, {place.lon:.5f}" if place.found else (place.reason or "-"),
                inside_delhi(place),
            ]
        )

    print(markdown_table(("query", "result", "path", "point or reason", "in Delhi"), rows))
    print()
    print(f"{session.used} live request(s) made of {args.budget} allowed.")
    found = sum(1 for row in rows if row[1] == "found")
    print(f"{found} of {len(QUERIES)} found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
