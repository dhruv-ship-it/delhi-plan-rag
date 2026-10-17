"""Find eight test points from the map layers and build a preview map to check them on.

Reads  data/layers/dda/*.geojson
Writes data/test_points.json          the eight points and their get_zones result (committed)
       data/layers/dda/preview.html   a standalone Leaflet page (gitignored)

The points are computed from the polygons, not typed in from memory, so they stay right
if the layers are re-downloaded. Rajiv Chowk is tried first for the TOD point because a
known landmark is easier to sanity-check than a point found by searching, but it is only
kept if the layers agree it qualifies.

Safe to re-run. Run with: uv run python scripts/07_test_points.py
"""

import json
import sys
from dataclasses import dataclass

from shapely.geometry import Point

from app.config import settings
from app.extract import markdown_table, use_utf8_output
from app.spatial import ALL_LAYERS, CORE_LAYERS, LayersMissing, get_zones, in_water, load_layers

#: Rajiv Chowk metro station: the first candidate for the TOD point.
RAJIV_CHOWK = (28.6328, 77.2197)
#: A point in Gurugram, outside NCT Delhi, for the "not in Delhi" case.
GURUGRAM = (28.4950, 77.0890)
#: How finely a polygon is sampled when its representative point will not do.
GRID_STEPS = 24
#: How finely the whole of Delhi is sampled when looking for a point in no policy zone.
DELHI_GRID_STEPS = 60


@dataclass(frozen=True)
class TestPoint:
    """One named test point and why it was chosen."""

    name: str
    lat: float
    lon: float
    wanted: str
    how: str


def grid_points(bounds: tuple[float, float, float, float], steps: int):
    """Points on a regular grid inside a bounding box, walked from the middle outwards.

    Starting in the middle matters: the first point found inside a long thin corridor
    should be somewhere in the body of it, not clinging to a corner of its bounding box.
    """
    min_x, min_y, max_x, max_y = bounds
    order = sorted(range(steps), key=lambda i: abs(i - (steps - 1) / 2))
    for row in order:
        for column in order:
            yield (
                min_y + (max_y - min_y) * (row + 0.5) / steps,
                min_x + (max_x - min_x) * (column + 0.5) / steps,
            )


def find_point(
    layers, layer_name: str, accept, candidates=(), fallback=None
) -> tuple[float, float] | None:
    """A point inside one of a layer's polygons that `accept(lat, lon)` agrees with.

    Tries the given candidates first, then each polygon's representative point (which
    shapely guarantees is inside it), then a grid over each polygon's bounding box. When
    nothing satisfies `accept` and a looser `fallback` test is given, the whole search
    runs again against that, so a point that is merely good enough is still returned.
    """
    for test in (accept, fallback):
        if test is None:
            continue
        for lat, lon in candidates:
            if test(lat, lon):
                return lat, lon
        layer = layers[layer_name]
        ordered = sorted(range(len(layer.geometries)), key=lambda i: -layer.geometries[i].area)
        for index in ordered:
            spot = layer.geometries[index].representative_point()
            if test(spot.y, spot.x):
                return spot.y, spot.x
        for index in ordered:
            geometry = layer.geometries[index]
            for lat, lon in grid_points(geometry.bounds, GRID_STEPS):
                if geometry.covers(Point(lon, lat)) and test(lat, lon):
                    return lat, lon
    return None


def choose_points(layers) -> list[TestPoint]:
    """Work out the eight test points from the layers."""
    def zones(lat, lon):
        return get_zones(lat, lon, layers)

    found: list[TestPoint] = []

    def add(name: str, wanted: str, how: str, spot: tuple[float, float] | None) -> None:
        if spot is None:
            print(f"  {name}: no point found")
            return
        found.append(TestPoint(name, round(spot[0], 6), round(spot[1], 6), wanted, how))

    add(
        "P_TOD",
        "in a TOD zone, not in HDC, land pooling or zone O",
        "Rajiv Chowk if it qualifies, otherwise the largest TOD polygon",
        find_point(
            layers,
            "tod_zone",
            lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"]
                and z["tod"]
                and not z["hdc"]
                and not z["land_pooling"]
                and not z["zone_o"]
            ),
            candidates=(RAJIV_CHOWK,),
        ),
    )
    add(
        "P_HDC",
        "in the High Density Corridor, and in nothing else if possible",
        "a point inside the single HDC polygon; the HDC follows UER-II through the "
        "land pooling areas and crosses TOD corridors, so a point in HDC alone is "
        "preferred to keep the location comparison readable",
        find_point(
            layers,
            "high_density_corridor",
            lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"]
                and z["hdc"]
                and not z["tod"]
                and not z["land_pooling"]
                and not z["zone_o"]
            ),
            fallback=lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"] and z["hdc"]
            ),
        ),
    )
    add(
        "P_ZONEO",
        "in planning zone O, on land rather than in the river",
        "a point in the zone O polygon that the Yamuna river layer does not cover",
        find_point(
            layers,
            "planning_zones",
            lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"]
                and z["zone_o"]
                and not in_water(lat, lon, layers)
            ),
        ),
    )
    add(
        "P_LP",
        "in a land pooling area",
        "a point inside the largest land pooling polygon",
        find_point(
            layers,
            "land_pooling_area",
            lambda lat, lon: zones(lat, lon)["inside_delhi"] and zones(lat, lon)["land_pooling"],
        ),
    )

    add(
        "P_RIDGE",
        "in a Regional Park (the Ridge), and in nothing else if possible",
        "a point inside the largest regional park polygon; the Ridge is asked for on "
        "its own because the ridge topic has no policy section of its own and works "
        "only through boosting and query expansion (D-069)",
        find_point(
            layers,
            "regional_park",
            lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"]
                and z["regional_park"]
                and not z["tod"]
                and not z["hdc"]
                and not z["land_pooling"]
                and not z["zone_o"]
                and not z["lda"]
            ),
            fallback=lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"] and z["regional_park"]
            ),
        ),
    )
    add(
        "P_LDA",
        "in a Low Density Area, and in nothing else if possible",
        "a point inside the largest low density area polygon; the LDAs sit along the "
        "NCT border, where the land pooling areas also are, so a point in the LDA "
        "alone is preferred to keep the comparison readable",
        find_point(
            layers,
            "low_density_area",
            lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"]
                and z["lda"]
                and not z["tod"]
                and not z["hdc"]
                and not z["land_pooling"]
                and not z["zone_o"]
                and not z["regional_park"]
            ),
            fallback=lambda lat, lon: (
                (z := zones(lat, lon))["inside_delhi"] and z["lda"]
            ),
        ),
    )

    plain = None
    for lat, lon in grid_points(layers["nctd_boundary"].geometries[0].bounds, DELHI_GRID_STEPS):
        candidate = zones(lat, lon)
        if candidate["inside_delhi"] and not any(
            candidate[key] for key in ("tod", "hdc", "land_pooling", "zone_o", "regional_park", "lda")
        ):
            plain = (lat, lon)
            break
    add(
        "P_PLAIN",
        "in Delhi but in none of the six policy zones",
        f"found by walking a {DELHI_GRID_STEPS}x{DELHI_GRID_STEPS} grid over Delhi from the middle out",
        plain,
    )
    add("P_OUT", "outside NCT Delhi", "a point in Gurugram, given in the brief", GURUGRAM)
    return found


def preview_html(points: list[TestPoint], layers) -> str:
    """A standalone Leaflet page: the core layers as toggleable overlays, plus the points.

    The geometry is simplified before it goes in, because the raw layers are 20 MB of
    coordinates and a browser does not need that to show the shape of a zone.
    """
    overlays = []
    for name in CORE_LAYERS:
        layer = layers[name]
        features = []
        for geometry, properties in zip(layer.geometries, layer.properties):
            simple = geometry.simplify(0.0005, preserve_topology=True)
            if simple.is_empty:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": json.loads(json.dumps(simple.__geo_interface__)),
                    "properties": {
                        key: properties.get(key)
                        for key in ("zone_name", "zone", "id", "area")
                        if properties.get(key) is not None
                    },
                }
            )
        overlays.append(
            {
                "name": name,
                "colour": COLOURS.get(name, "#3388ff"),
                "data": {"type": "FeatureCollection", "features": features},
            }
        )

    markers = [
        {
            "name": point.name,
            "lat": point.lat,
            "lon": point.lon,
            "wanted": point.wanted,
            "zones": get_zones(point.lat, point.lon, layers),
        }
        for point in points
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ZoneWise layer preview</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
  html, body {{ margin: 0; height: 100%; font: 14px/1.5 system-ui, sans-serif; }}
  #map {{ height: 100%; }}
  .note {{ position: absolute; z-index: 1000; top: 10px; left: 60px; max-width: 22rem;
           background: #fff; padding: .6rem .8rem; border-radius: 6px;
           box-shadow: 0 1px 6px rgba(0,0,0,.3); }}
  .note h1 {{ font-size: 1rem; margin: 0 0 .3rem; }}
  .note p {{ margin: .3rem 0 0; color: #444; }}
  table.z {{ border-collapse: collapse; }}
  table.z td {{ padding: 1px 6px 1px 0; vertical-align: top; }}
  table.z td:first-child {{ color: #666; }}
</style>
</head>
<body>
<div class="note">
  <h1>ZoneWise layer preview</h1>
  <p>DDA layers, simplified for drawing. Use the control top right to toggle them.
     Click a marker to see what <code>get_zones</code> returns for it.</p>
  <p><strong>Not committed:</strong> DDA states no licence for this data.</p>
</div>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const OVERLAYS = {json.dumps(overlays)};
const POINTS = {json.dumps(markers)};

const map = L.map('map').setView([28.63, 77.22], 10);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 18,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

const controls = {{}};
for (const overlay of OVERLAYS) {{
  const style = {{ color: overlay.colour, weight: 1, fillOpacity: 0.18 }};
  const group = L.geoJSON(overlay.data, {{
    style,
    onEachFeature: (feature, layer) => {{
      const rows = Object.entries(feature.properties || {{}})
        .map(([k, v]) => `<tr><td>${{k}}</td><td>${{v}}</td></tr>`).join('');
      layer.bindPopup(`<strong>${{overlay.name}}</strong><table class="z">${{rows}}</table>`);
    }}
  }});
  const label = `${{overlay.name}} (${{overlay.data.features.length}})`;
  controls[label] = group;
  group.addTo(map);
}}
L.control.layers(null, controls, {{ collapsed: false }}).addTo(map);

for (const point of POINTS) {{
  const rows = Object.entries(point.zones)
    .map(([k, v]) => `<tr><td>${{k}}</td><td><strong>${{v}}</strong></td></tr>`).join('');
  L.marker([point.lat, point.lon]).addTo(map).bindPopup(
    `<strong>${{point.name}}</strong><br>${{point.wanted}}<br>` +
    `<code>${{point.lat}}, ${{point.lon}}</code>` +
    `<table class="z">${{rows}}</table>`
  );
}}
</script>
</body>
</html>
"""


COLOURS = {
    "nctd_boundary": "#222222",
    "planning_zones": "#777777",
    "high_density_corridor": "#e6550d",
    "tod_zone": "#3182bd",
    "land_pooling_area": "#31a354",
}


def main() -> int:
    """Find the points, print their zones, and write the JSON and the preview page."""
    use_utf8_output()
    try:
        layers = load_layers()
    except LayersMissing as exc:
        print(exc)
        return 1

    print(f"{len(ALL_LAYERS)} layers loaded: " + ", ".join(
        f"{name} ({len(layers[name].geometries)})" for name in ALL_LAYERS
    ))
    print()
    print("choosing test points from the polygons:")
    points = choose_points(layers)
    print()

    records = []
    for point in points:
        zones = get_zones(point.lat, point.lon, layers)
        records.append(
            {
                "name": point.name,
                "lat": point.lat,
                "lon": point.lon,
                "wanted": point.wanted,
                "how_it_was_found": point.how,
                "zones": zones,
            }
        )

    rows = [
        [
            record["name"],
            f"{record['lat']:.5f}, {record['lon']:.5f}",
            "yes" if record["zones"]["inside_delhi"] else "no",
            str(record["zones"].get("planning_zone") or "-"),
            "yes" if record["zones"].get("tod") else "-",
            "yes" if record["zones"].get("hdc") else "-",
            ("yes " + (record["zones"].get("land_pooling_zone") or "")).strip()
            if record["zones"].get("land_pooling")
            else "-",
            "yes" if record["zones"].get("zone_o") else "-",
            "yes" if record["zones"].get("regional_park") else "-",
            "yes" if record["zones"].get("lda") else "-",
        ]
        for record in records
    ]
    print(
        markdown_table(
            ("point", "lat, lon", "in Delhi", "zone", "tod", "hdc", "pooling", "zone O", "park", "lda"),
            rows,
        )
    )

    points_path = settings.project_root / "data" / "test_points.json"
    points_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    preview_path = settings.dda_layers_dir / "preview.html"
    preview_path.write_text(preview_html(points, layers), encoding="utf-8")

    print()
    print(f"{len(records)} test points.")
    for path in (points_path, preview_path):
        print(f"wrote {path.relative_to(settings.project_root).as_posix()}")
    print(f"open the map with: start {preview_path.relative_to(settings.project_root)}")
    return 0 if len(records) == 6 else 1


if __name__ == "__main__":
    sys.exit(main())
