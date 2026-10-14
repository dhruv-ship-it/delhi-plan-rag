"""Build eval/points.json: the named points the evaluation questions are asked at.

Reads  data/test_points.json, data/layers/dda/*.geojson
Writes eval/points.json

The six points from `data/test_points.json` are reused as they are, then about three
more are found inside each of the four policy zones, so a location question can be asked
at several places in the same zone rather than always the same one. Every point is
stored with its full `get_zones` result, which is what `eval/run_eval.py` passes to the
location-aware search.

Points are computed from the polygons, never typed in, so they stay correct if the
layers are downloaded again.

Safe to re-run. Run with: uv run python scripts/08_eval_points.py
"""

import json
import sys

from shapely.geometry import Point

from app.config import settings
from app.extract import markdown_table, use_utf8_output
from app.spatial import LayersMissing, get_zones, in_water, load_layers

#: How many extra points to find in each policy zone.
EXTRA_PER_ZONE = 3
#: How finely each polygon is sampled when looking for points inside it.
GRID_STEPS = 18
#: Points closer together than this (in degrees, about 2 km) count as the same place.
MIN_SEPARATION = 0.02

#: Which layer to search for each zone topic, and what to call the points.
ZONE_SOURCES = (
    ("tod", "tod_zone", "P_TOD"),
    ("hdc", "high_density_corridor", "P_HDC"),
    ("land_pooling", "land_pooling_area", "P_LP"),
    ("zone_o", "planning_zones", "P_ZONEO"),
)


def far_enough(lat: float, lon: float, taken: list[tuple[float, float]]) -> bool:
    """True when a candidate point is not effectively the same place as one already kept."""
    return all(
        abs(lat - other_lat) > MIN_SEPARATION or abs(lon - other_lon) > MIN_SEPARATION
        for other_lat, other_lon in taken
    )


def grid_points(bounds: tuple[float, float, float, float], steps: int):
    """Points on a grid inside a bounding box, walked from the middle outwards."""
    min_x, min_y, max_x, max_y = bounds
    order = sorted(range(steps), key=lambda index: abs(index - (steps - 1) / 2))
    for row in order:
        for column in order:
            yield (
                min_y + (max_y - min_y) * (row + 0.5) / steps,
                min_x + (max_x - min_x) * (column + 0.5) / steps,
            )


def find_in_zone(layers, topic: str, layer_name: str, wanted: int, taken: list) -> list[dict]:
    """Find up to `wanted` points inside a zone, spread out rather than clustered.

    Zone O is the awkward one: it is a planning zone rather than a policy layer, and
    half of it is the river, so a point there has to be on land as well as in the zone.
    """
    layer = layers[layer_name]
    found: list[dict] = []
    ordered = sorted(range(len(layer.geometries)), key=lambda i: -layer.geometries[i].area)

    for index in ordered:
        if len(found) >= wanted:
            break
        geometry = layer.geometries[index]
        if topic == "zone_o":
            name = str(layer.properties[index].get("zone_name", "")).replace(" ", "")
            if name != "O":
                continue
        for lat, lon in grid_points(geometry.bounds, GRID_STEPS):
            if len(found) >= wanted:
                break
            if not geometry.covers(Point(lon, lat)):
                continue
            zones = get_zones(lat, lon, layers)
            if not zones.get("inside_delhi") or not zones.get(topic):
                continue
            if topic == "zone_o" and in_water(lat, lon, layers):
                continue
            if not far_enough(lat, lon, taken):
                continue
            taken.append((lat, lon))
            found.append({"lat": round(lat, 6), "lon": round(lon, 6), "zones": zones})
    return found


def main() -> int:
    """Build the point set and write eval/points.json."""
    use_utf8_output()
    try:
        layers = load_layers()
    except LayersMissing as exc:
        print(exc)
        return 1

    base_path = settings.project_root / "data" / "test_points.json"
    if not base_path.exists():
        print(f"{base_path.as_posix()} is missing. Run: uv run python scripts/07_test_points.py")
        return 1

    records: list[dict] = []
    taken: list[tuple[float, float]] = []

    for point in json.loads(base_path.read_text(encoding="utf-8")):
        records.append(
            {
                "name": point["name"],
                "lat": point["lat"],
                "lon": point["lon"],
                "source": "data/test_points.json",
                "wanted": point["wanted"],
                "zones": point["zones"],
            }
        )
        if point["zones"].get("inside_delhi"):
            taken.append((point["lat"], point["lon"]))

    print(f"{len(records)} points reused from data/test_points.json")
    for topic, layer_name, prefix in ZONE_SOURCES:
        found = find_in_zone(layers, topic, layer_name, EXTRA_PER_ZONE, taken)
        for number, point in enumerate(found, start=2):
            records.append(
                {
                    "name": f"{prefix}_{number}",
                    "lat": point["lat"],
                    "lon": point["lon"],
                    "source": f"computed from the {layer_name} layer",
                    "wanted": f"in {topic}",
                    "zones": point["zones"],
                }
            )
        print(f"  {topic:<13} {len(found)} extra point(s) found in {layer_name}")

    out_path = settings.project_root / "eval" / "points.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    rows = [
        [
            record["name"],
            f"{record['lat']:.5f}, {record['lon']:.5f}",
            "yes" if record["zones"].get("inside_delhi") else "no",
            str(record["zones"].get("planning_zone") or "-"),
            "yes" if record["zones"].get("tod") else "-",
            "yes" if record["zones"].get("hdc") else "-",
            "yes" if record["zones"].get("land_pooling") else "-",
            "yes" if record["zones"].get("zone_o") else "-",
        ]
        for record in records
    ]
    print()
    print(
        markdown_table(
            ("point", "lat, lon", "in Delhi", "zone", "tod", "hdc", "pooling", "zone O"), rows
        )
    )
    print()
    print(f"{len(records)} points written to {out_path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
