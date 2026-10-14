"""Download the DDA map layers ZoneWise needs to say which zones a point is in.

Reads  nothing (the layer list is below)
Writes data/layers/dda/<name>.geojson   the layers themselves (gitignored, see D-014)
       data/layers/manifest.json        what was fetched, when, and what is in it (committed)
       data/layers/dda/preview.html     a Leaflet page for looking at it all (gitignored)
       data/test_points.json            six points computed from the data (committed)

The layers come from DDA's own ArcGIS server, which states no licence anywhere we could
find, so the downloaded GeoJSON is never committed; the manifest records exactly what was
fetched so the repo still says what the project is built on.

Polite by default: one request a second, a 30 second timeout, three retries.

Safe to re-run; every file is rewritten. Run with: uv run python scripts/06_fetch_layers.py
"""

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import settings
from app.extract import markdown_table, use_utf8_output

BASE = (
    "https://gis.dda.org.in/server/rest/services/Hosted/"
    "MAP_4_SPATIAL_DEVELOPMENT_POLICIES_UPDATED/FeatureServer"
)
LDA_URL = "https://gis.dda.org.in/server/rest/services/Hosted/LDA/FeatureServer/0"

USER_AGENT = "ZoneWise/0.1 (student project)"
TIMEOUT = 30
RETRIES = 3
#: Seconds between requests. The server is a public government service; we do not rush it.
POLITE_PAUSE = 1.0
#: How many features to ask for at a time. The server's own maxRecordCount is 2000.
PAGE_SIZE = 1000


@dataclass(frozen=True)
class LayerSpec:
    """One layer to download: what to call it, where it is, and whether we wire it up."""

    name: str
    url: str
    title: str
    core: bool
    #: The colour the preview map draws it in.
    colour: str = "#3388ff"


LAYERS: tuple[LayerSpec, ...] = (
    LayerSpec("nctd_boundary", f"{BASE}/5", "NCTD BOUNDARY", True, "#222222"),
    LayerSpec("planning_zones", f"{BASE}/6", "ZONE_BOUNDARY_TEXT", True, "#777777"),
    LayerSpec("high_density_corridor", f"{BASE}/13", "HIGH DENSITY CORRIDOR", True, "#e6550d"),
    LayerSpec("tod_zone", f"{BASE}/14", "TOD ZONE", True, "#3182bd"),
    LayerSpec("land_pooling_area", f"{BASE}/17", "LAND POOLING AREA", True, "#31a354"),
    # Downloaded but not wired into retrieval yet.
    LayerSpec("regional_park", f"{BASE}/18", "REGIONAL PARK", False, "#74c476"),
    LayerSpec("yamuna_river", f"{BASE}/20", "YAMUNA_RIVER", False, "#2171b5"),
    LayerSpec("low_density_area", LDA_URL, "LOW DENSITY AREA (separate service)", False, "#fdae6b"),
)


@dataclass
class FetchResult:
    """What came back for one layer."""

    spec: LayerSpec
    geojson: dict | None = None
    geometry_type: str = ""
    max_record_count: int | None = None
    fields: list[str] = field(default_factory=list)
    server_count: int | None = None
    pages: int = 0
    area_km2: float | None = None
    repaired: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def features(self) -> list[dict]:
        return (self.geojson or {}).get("features", []) or []


def get_json(url: str, params: dict) -> dict:
    """One GET that returns JSON, retried up to three times with a growing pause."""
    headers = {"User-Agent": USER_AGENT}
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last = exc
            if attempt < RETRIES:
                time.sleep(POLITE_PAUSE * attempt * 2)
    raise RuntimeError(f"{url} failed after {RETRIES} attempts: {last}")


def read_metadata(result: FetchResult) -> None:
    """Read a layer's own description: geometry type, page limit, field names, count."""
    meta = get_json(result.spec.url, {"f": "json"})
    result.geometry_type = meta.get("geometryType", "")
    result.max_record_count = meta.get("maxRecordCount")
    result.fields = [item["name"] for item in meta.get("fields", [])]
    time.sleep(POLITE_PAUSE)
    counted = get_json(
        f"{result.spec.url}/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    )
    result.server_count = counted.get("count")


def fetch_features(result: FetchResult) -> None:
    """Download every feature of a layer as GeoJSON, paging while the server says there is more."""
    features: list[dict] = []
    offset = 0
    while True:
        time.sleep(POLITE_PAUSE)
        page = get_json(
            f"{result.spec.url}/query",
            {
                "where": "1=1",
                "outFields": "*",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            },
        )
        batch = page.get("features", []) or []
        features += batch
        result.pages += 1
        more = page.get("exceededTransferLimit") or page.get("properties", {}).get(
            "exceededTransferLimit"
        )
        if not more or not batch:
            break
        offset += len(batch)
    result.geojson = {"type": "FeatureCollection", "features": features}


def repair_and_measure(result: FetchResult) -> None:
    """Fix invalid geometries and work out the layer's total area in km².

    Areas are computed in EPSG:32643 (UTM zone 43N), which is metres, because an area
    in degrees is meaningless. NCT Delhi should come out near 1,480 km²; that number is
    the check that the download, the projection and the repair all worked.
    """
    import geopandas as gpd
    from shapely.validation import make_valid

    if not result.features:
        result.area_km2 = 0.0
        return
    frame = gpd.GeoDataFrame.from_features(result.features, crs="EPSG:4326")
    broken = ~frame.geometry.is_valid
    result.repaired = int(broken.sum())
    if result.repaired:
        frame.loc[broken, "geometry"] = frame.loc[broken, "geometry"].apply(make_valid)
    result.area_km2 = float(frame.to_crs("EPSG:32643").geometry.area.sum() / 1e6)
    result.geojson = json.loads(frame.to_json())


def write_layer(result: FetchResult, folder: Path) -> Path:
    """Write one layer's GeoJSON to data/layers/dda/<name>.geojson."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{result.spec.name}.geojson"
    path.write_text(json.dumps(result.geojson, ensure_ascii=False), encoding="utf-8")
    return path


def build_manifest(results: list[FetchResult], fetched_at: str) -> dict:
    """The committed record of what was downloaded."""
    return {
        "fetched_at": fetched_at,
        "source": "DDA ArcGIS FeatureServer, gis.dda.org.in",
        "licence": (
            "Not stated by DDA anywhere on the service or the portal. The layers are "
            "therefore not committed to this repository (see D-014 and D-030); this "
            "manifest records what was fetched so the work stays reproducible."
        ),
        "crs": "EPSG:4326 as stored; areas computed in EPSG:32643 (UTM 43N)",
        "layers": [
            {
                "name": result.spec.name,
                "title": result.spec.title,
                "url": result.spec.url,
                "core": result.spec.core,
                "fetched_at": fetched_at,
                "feature_count": len(result.features),
                "server_count": result.server_count,
                "geometry_type": result.geometry_type,
                "max_record_count": result.max_record_count,
                "pages_fetched": result.pages,
                "fields": result.fields,
                "area_km2": round(result.area_km2, 2) if result.area_km2 is not None else None,
                "geometries_repaired": result.repaired,
                "errors": result.errors,
            }
            for result in results
        ],
    }


def main() -> int:
    """Download every layer, repair it, measure it, and write the files."""
    use_utf8_output()
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results: list[FetchResult] = []

    for spec in LAYERS:
        result = FetchResult(spec=spec)
        results.append(result)
        try:
            read_metadata(result)
            print(
                f"{spec.name:<22} {result.geometry_type:<20} "
                f"maxRecordCount={result.max_record_count} count={result.server_count}"
            )
            fetch_features(result)
            repair_and_measure(result)
            path = write_layer(result, settings.dda_layers_dir)
            print(
                f"  {len(result.features)} features in {result.pages} page(s), "
                f"{result.area_km2:,.1f} km², {result.repaired} geometry/geometries repaired "
                f"-> {path.relative_to(settings.project_root).as_posix()}"
            )
        except Exception as exc:
            result.errors.append(str(exc))
            print(f"  FAILED: {exc}")

    manifest_path = settings.layers_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(build_manifest(results, fetched_at), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    ok = [result for result in results if result.features and not result.errors]
    print()
    rows = [
        [
            result.spec.name,
            "core" if result.spec.core else "extra",
            str(len(result.features)),
            result.geometry_type.replace("esriGeometry", ""),
            f"{result.area_km2:,.1f}" if result.area_km2 is not None else "-",
            str(result.repaired),
            "; ".join(result.errors) or "-",
        ]
        for result in results
    ]
    print(
        markdown_table(
            ("layer", "role", "features", "geometry", "area km2", "repaired", "errors"), rows
        )
    )
    print()
    delhi = next((r for r in results if r.spec.name == "nctd_boundary"), None)
    if delhi and delhi.area_km2:
        print(
            f"NCT Delhi comes out at {delhi.area_km2:,.1f} km² "
            f"(the published figure is about 1,480 km²)."
        )
    print(f"{len(ok)} of {len(LAYERS)} layers downloaded.")
    print(f"wrote {manifest_path.relative_to(settings.project_root).as_posix()}")
    print("Next: uv run python scripts/07_test_points.py")
    return 0 if len(ok) == len(LAYERS) else 1


if __name__ == "__main__":
    sys.exit(main())
