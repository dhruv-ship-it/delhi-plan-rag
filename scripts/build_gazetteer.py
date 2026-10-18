"""Download the Delhi Metro stations from OpenStreetMap into a local gazetteer.

    uv run python scripts/build_gazetteer.py
    uv run python scripts/build_gazetteer.py --force     # ignore the existing file

Writes data/gazetteer/metro_stations.json: name, alternate names, lat and lon per
station. The folder is gitignored — the data is OpenStreetMap's, published under the
ODbL, and this script rebuilds it in one request — and the attribution
**© OpenStreetMap contributors** is recorded in README.md and docs/DATA.md.

Why a gazetteer at all. Night 2's live check found that Nominatim returns nothing for
"Dwarka Sector 21 metro station" with `bounded=1` and `limit=1` (D-049), which is close
to the phrase the agent's own example suggests typing. A metro station name is the most
likely thing a Delhi resident will use to describe where they are, and there are only
about 290 of them, so holding the list locally turns the commonest case into a string
match with no network call at all — faster, free, and not subject to one geocoder's
indexing of one naming convention (D-073).

**One request.** Overpass is a free service run on donated hardware, so this script
makes exactly one query, bounded to the NCT Delhi bounding box, and refuses to run
again if the file already exists unless `--force` is passed.

Safe to re-run: without `--force` it does nothing when the gazetteer is already there.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.extract import use_utf8_output  # noqa: E402
from app.geocode import DELHI_VIEWBOX  # noqa: E402

#: Overpass takes (south, west, north, east), which is not the order a viewbox uses.
LEFT, TOP, RIGHT, BOTTOM = DELHI_VIEWBOX
BBOX = f"{BOTTOM},{LEFT},{TOP},{RIGHT}"

#: Any OSM element tagged as a subway station, or as a station on a network whose name
#: mentions Delhi Metro. Three element types because OSM models a station sometimes as
#: a node, sometimes as the building's way, sometimes as a relation over both.
OVERPASS_QUERY = f"""
[out:json][timeout:90];
(
  node["railway"="station"]["station"="subway"]({BBOX});
  way["railway"="station"]["station"="subway"]({BBOX});
  relation["railway"="station"]["station"="subway"]({BBOX});
  node["railway"="station"]["network"~"Delhi Metro",i]({BBOX});
  way["railway"="station"]["network"~"Delhi Metro",i]({BBOX});
  relation["railway"="station"]["network"~"Delhi Metro",i]({BBOX});
);
out center tags;
"""

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

#: The tags that can carry a station's name, in the order they are preferred.
NAME_TAGS = ("name", "name:en", "official_name", "alt_name", "old_name", "short_name")


def station_names(tags: dict) -> tuple[str, list[str]]:
    """The station's main name and its alternates, deduplicated, blanks dropped.

    `alt_name` and `old_name` can hold several names separated by semicolons, which is
    OSM's convention for a multi-valued tag.
    """
    found: list[str] = []
    for tag in NAME_TAGS:
        raw = (tags.get(tag) or "").strip()
        for part in raw.split(";"):
            name = " ".join(part.split())
            if name and name not in found:
                found.append(name)
    if not found:
        return "", []
    return found[0], found[1:]


def element_point(element: dict) -> tuple[float, float] | None:
    """A station's coordinates, from the node itself or from a way's centre."""
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    centre = element.get("center") or {}
    if centre.get("lat") is not None and centre.get("lon") is not None:
        return float(centre["lat"]), float(centre["lon"])
    return None


def stations_from_overpass(payload: dict) -> list[dict]:
    """Turn an Overpass response into station records, one per distinct name.

    OSM frequently holds the same station as a node and as a way, and an interchange
    as several elements with the same name, so records are keyed by lower-case name and
    the first one with coordinates wins. That is the right level of detail here: the
    gazetteer answers "roughly where is Rajiv Chowk", not "where is platform 3".
    """
    found: dict[str, dict] = {}
    for element in payload.get("elements", []):
        name, alternates = station_names(element.get("tags") or {})
        point = element_point(element)
        if not name or point is None:
            continue
        key = name.lower()
        if key in found:
            for alternate in alternates:
                if alternate not in found[key]["alt_names"]:
                    found[key]["alt_names"].append(alternate)
            continue
        found[key] = {
            "name": name,
            "alt_names": alternates,
            "lat": round(point[0], 6),
            "lon": round(point[1], 6),
        }
    return sorted(found.values(), key=lambda record: record["name"])


def fetch(session=None) -> dict:
    """Make the one Overpass request."""
    getter = session.post if session is not None else requests.post
    response = getter(
        OVERPASS_URL,
        data={"data": OVERPASS_QUERY},
        headers={"User-Agent": settings.geocode_user_agent},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    """Download the stations and write the gazetteer."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="download again even if the file exists"
    )
    args = parser.parse_args()

    out_path = settings.gazetteer_path
    if out_path.exists() and not args.force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"{out_path.as_posix()} already has {len(existing.get('stations', []))} stations.")
        print("Nothing downloaded. Pass --force to fetch it again.")
        return 0

    print(f"one Overpass request for Delhi Metro stations inside {BBOX}...")
    try:
        payload = fetch()
    except Exception as exc:
        print(f"Overpass request failed: {type(exc).__name__}: {exc}")
        print("Nothing written. The gazetteer is optional: locate_place falls back to Nominatim.")
        return 1

    stations = stations_from_overpass(payload)
    if not stations:
        print("Overpass returned no stations, which is not plausible. Nothing written.")
        return 1

    document = {
        "_source": "OpenStreetMap via the Overpass API",
        "_licence": "Open Database License (ODbL). Attribution: (c) OpenStreetMap contributors",
        "_query_bbox": BBOX,
        "_fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "_elements_returned": len(payload.get("elements", [])),
        "stations": stations,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    with_alternates = sum(1 for station in stations if station["alt_names"])
    print()
    print(f"{len(payload.get('elements', []))} OSM elements -> {len(stations)} distinct stations")
    print(f"  {with_alternates} have at least one alternate name")
    print(f"  first: {stations[0]['name']}   last: {stations[-1]['name']}")
    print(f"wrote {out_path.as_posix()}")
    print("Attribution: (c) OpenStreetMap contributors, ODbL. The folder is gitignored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
