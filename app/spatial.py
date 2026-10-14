"""Answer "which planning zones is this point in?" from the downloaded DDA map layers.

This is the half of ZoneWise that makes it location-aware. A user clicks a point on the
map; `get_zones(lat, lon)` says whether it is in Delhi at all, which of the 17 planning
zones it falls in, and which of the location-dependent policies cover it. Retrieval then
uses that to drop, boost and expand (see app/location.py).

The layers are loaded once into an STRtree per layer and reused, because a point-in-
polygon test against 208 low-density-area polygons is cheap but reading and parsing the
GeoJSON is not. Everything is stored and queried in EPSG:4326; areas are the only thing
computed in metres, and that happens in the fetch script, not here.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from app.config import settings

#: The layers `get_zones` answers from.
CORE_LAYERS = (
    "nctd_boundary",
    "planning_zones",
    "tod_zone",
    "high_density_corridor",
    "land_pooling_area",
)
#: Downloaded as well, and reported, but no policy is wired to them yet.
EXTRA_LAYERS = ("regional_park", "low_density_area", "yamuna_river")
ALL_LAYERS = CORE_LAYERS + EXTRA_LAYERS

#: The keys `get_zones` returns for a point inside Delhi.
ZONE_KEYS = (
    "inside_delhi",
    "planning_zone",
    "tod",
    "hdc",
    "land_pooling",
    "land_pooling_zone",
    "zone_o",
    "regional_park",
    "lda",
)


class LayersMissing(RuntimeError):
    """Raised when the GeoJSON layers have not been downloaded yet."""


@dataclass(frozen=True)
class Layer:
    """One map layer: its polygons, their properties, and an index over them."""

    name: str
    geometries: tuple
    properties: tuple[dict, ...]
    tree: STRtree

    def hits(self, point: Point) -> list[int]:
        """Indexes of the polygons that contain the point.

        The STRtree narrows by bounding box first, which is what makes 208 polygons as
        cheap as one; `covers` rather than `contains` so a point exactly on a shared
        boundary belongs to a zone instead of to none.
        """
        found = []
        for index in self.tree.query(point):
            if self.geometries[int(index)].covers(point):
                found.append(int(index))
        return found

    def contains(self, point: Point) -> bool:
        """True when any polygon in this layer contains the point."""
        return bool(self.hits(point))


def layer_path(name: str, folder: Path | None = None) -> Path:
    """Where a layer's GeoJSON lives."""
    return (folder or settings.dda_layers_dir) / f"{name}.geojson"


def load_layer(name: str, folder: Path | None = None) -> Layer:
    """Read one GeoJSON layer and build its spatial index.

    Invalid geometries were repaired when the layer was downloaded, but a repair can
    turn a polygon into a collection, so anything without an area is dropped here
    rather than being allowed to fail a point test later.
    """
    path = layer_path(name, folder)
    if not path.exists():
        raise LayersMissing(
            f"{path.as_posix()} is missing. Run: uv run python scripts/06_fetch_layers.py"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    geometries, properties = [], []
    for feature in data.get("features", []):
        if not feature.get("geometry"):
            continue
        geometry = shape(feature["geometry"])
        if geometry.is_empty or geometry.area == 0:
            continue
        geometries.append(geometry)
        properties.append(feature.get("properties") or {})
    return Layer(
        name=name,
        geometries=tuple(geometries),
        properties=tuple(properties),
        tree=STRtree(geometries),
    )


@lru_cache(maxsize=1)
def load_layers(folder: str | None = None) -> dict[str, Layer]:
    """Load every layer once and keep it. Cached, so repeated searches pay nothing."""
    base = Path(folder) if folder else None
    return {name: load_layer(name, base) for name in ALL_LAYERS}


def clean_zone_name(value: object) -> str | None:
    """Tidy a zone name from the layer: 'P- I' -> 'P-I', a blank cell -> None."""
    if value is None:
        return None
    name = "".join(str(value).split())
    return name or None


def outside() -> dict:
    """What `get_zones` returns for a point that is not in NCT Delhi."""
    return {"inside_delhi": False}


def get_zones(lat: float, lon: float, layers: dict[str, Layer] | None = None) -> dict:
    """Which planning zones the point (lat, lon) falls in.

    Returns `{"inside_delhi": False}` and nothing else for a point outside NCT Delhi,
    because none of the other answers mean anything there. Inside Delhi it returns:

      planning_zone       the zone letter, "A" to "P", or None if no polygon covers it
      tod                 in a TOD zone (the band along the metro and RRTS corridors)
      hdc                 in the High Density Corridor (the UER-II corridor)
      land_pooling        in a land pooling area
      land_pooling_zone   which land pooling zone, where the layer names one
      zone_o              planning_zone == "O", the River Yamuna / Riverfront zone
      regional_park       in a Regional Park polygon
      lda                 in a Low Density Area polygon
    """
    layers = layers or load_layers()
    point = Point(lon, lat)  # GeoJSON and shapely are (x, y) = (lon, lat)

    if not layers["nctd_boundary"].contains(point):
        return outside()

    planning = layers["planning_zones"]
    zone_hits = planning.hits(point)
    planning_zone = clean_zone_name(planning.properties[zone_hits[0]].get("zone_name")) if zone_hits else None

    pooling = layers["land_pooling_area"]
    pooling_hits = pooling.hits(point)
    pooling_zone = None
    for index in pooling_hits:
        pooling_zone = clean_zone_name(pooling.properties[index].get("zone"))
        if pooling_zone:
            break

    return {
        "inside_delhi": True,
        "planning_zone": planning_zone,
        "tod": layers["tod_zone"].contains(point),
        "hdc": layers["high_density_corridor"].contains(point),
        "land_pooling": bool(pooling_hits),
        "land_pooling_zone": pooling_zone,
        "zone_o": planning_zone == "O",
        "regional_park": layers["regional_park"].contains(point),
        "lda": layers["low_density_area"].contains(point),
    }


def in_water(lat: float, lon: float, layers: dict[str, Layer] | None = None) -> bool:
    """True when the point sits inside the Yamuna river polygon.

    Not part of `get_zones` — the river layer is downloaded but not wired to any
    policy. It is used when picking a test point inside zone O that is on land.
    """
    layers = layers or load_layers()
    return layers["yamuna_river"].contains(Point(lon, lat))


def topics_for(zones: dict) -> list[str]:
    """The zone topics from app.tagging that this point is in, in a fixed order."""
    if not zones.get("inside_delhi"):
        return []
    found = []
    for topic, key in (("tod", "tod"), ("hdc", "hdc"), ("zone_o", "zone_o"), ("land_pooling", "land_pooling")):
        if zones.get(key):
            found.append(topic)
    return found
