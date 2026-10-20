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

from shapely import transform
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from app.config import settings

#: The layers a policy topic is wired to, and so the ones the browser is served.
#: `regional_park` and `low_density_area` joined this list in D-069, when the ridge
#: and lda topics were added to tagging; before that they were downloaded and loaded
#: but nothing used them.
CORE_LAYERS = (
    "nctd_boundary",
    "planning_zones",
    "tod_zone",
    "high_density_corridor",
    "land_pooling_area",
    "regional_park",
    "low_density_area",
)
#: Downloaded as well, and reported, but no policy is wired to it. The river polygon
#: is used when picking a zone O test point that is on land, and nowhere else.
EXTRA_LAYERS = ("yamuna_river",)
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
      regional_park       in a Regional Park polygon (the `ridge` policy topic)
      lda                 in a Low Density Area polygon (the `lda` policy topic)
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


#: Which `get_zones` key says the point is in each topic. The topic names come from
#: app.tagging and the keys from `get_zones`, and the two differ for the Ridge:
#: the layer is called regional_park, the policy topic is called ridge.
TOPIC_KEYS: tuple[tuple[str, str], ...] = (
    ("tod", "tod"),
    ("hdc", "hdc"),
    ("zone_o", "zone_o"),
    ("land_pooling", "land_pooling"),
    ("ridge", "regional_park"),
    ("lda", "lda"),
)


def topics_for(zones: dict) -> list[str]:
    """The zone topics from app.tagging that this point is in, in a fixed order."""
    if not zones.get("inside_delhi"):
        return []
    return [topic for topic, key in TOPIC_KEYS if zones.get(key)]


# --- how far away is a zone the point is not in? --------------------------------
#
# `get_zones` answers "is the point in this zone?". A question that *names* a zone the
# point is not in needs the other half of that answer: how far off it is. One kilometre
# from the Yamuna floodplain and one metre from it are the same `zone_o: false`, and
# only the first of those is honest to describe as "not in the floodplain" without
# qualification (D-094).

#: Metres, which is what a distance has to be measured in. UTM zone 43N covers Delhi
#: and is the projection the rest of this project measures in (scripts/06_fetch_layers.py,
#: and the buffers CLAUDE.md pins).
METRIC_CRS = "EPSG:32643"

#: Which layer holds each policy topic's polygons, and the `zone_name` a feature must
#: carry to count. `zone_o` has no layer of its own — it *is* planning zone "O" — so the
#: planning_zones layer is filtered, exactly as `get_zones` does it. The topic names
#: come from app.tagging and the layer names from DDA, and they differ for the Ridge.
TOPIC_LAYERS: dict[str, tuple[str, str | None]] = {
    "tod": ("tod_zone", None),
    "hdc": ("high_density_corridor", None),
    "zone_o": ("planning_zones", "O"),
    "land_pooling": ("land_pooling_area", None),
    "ridge": ("regional_park", None),
    "lda": ("low_density_area", None),
}


@lru_cache(maxsize=1)
def to_metres():
    """The EPSG:4326 -> EPSG:32643 transform, built once.

    `always_xy=True` so it takes (lon, lat) in and gives (easting, northing) out, which
    is the order shapely uses and the order the GeoJSON is stored in.
    """
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:4326", METRIC_CRS, always_xy=True).transform


def in_metres(geometry):
    """One geometry, reprojected into EPSG:32643.

    `shapely.transform` hands the whole coordinate array over at once, which pyproj
    takes as-is, so a 200-vertex polygon is one call rather than 200. The array is
    copied and written through its own columns so that nothing here has to import numpy
    to build a new one — shapely brings it, but this project does not declare it.
    """

    def project(coordinates):
        moved = coordinates.copy()
        moved[:, 0], moved[:, 1] = to_metres()(coordinates[:, 0], coordinates[:, 1])
        return moved

    return transform(geometry, project)


@lru_cache(maxsize=32)
def metric_shapes(topic: str, folder: str | None = None) -> tuple[tuple, STRtree] | None:
    """One topic's polygons projected into metres, with an index over them.

    Cached, and keyed the same way `load_layers` is keyed, because projecting 208 low
    density area polygons is not something to do per question. None when the topic has
    no polygons at all, which a filtered layer can legitimately produce.
    """
    name, keep = TOPIC_LAYERS[topic]
    layer = load_layers(folder)[name]
    shapes = [
        in_metres(geometry)
        for geometry, properties in zip(layer.geometries, layer.properties)
        if keep is None or clean_zone_name(properties.get("zone_name")) == keep
    ]
    if not shapes:
        return None
    return tuple(shapes), STRtree(shapes)


def distance_to_topic(
    lat: float, lon: float, topic: str, folder: str | None = None
) -> float | None:
    """Metres from the point to the nearest polygon of `topic`, in EPSG:32643.

    0.0 when the point is inside one, so this is a distance and not a "how far outside";
    None when the topic is not one of the six, or has no polygons in the layers.

    `folder` rather than a loaded `layers` dict, unlike `get_zones`, because the
    projected shapes are cached and a cache has to be keyed by something hashable —
    the same string `load_layers` is already keyed by.
    """
    if topic not in TOPIC_LAYERS:
        return None
    found = metric_shapes(topic, folder)
    if found is None:
        return None
    shapes, tree = found
    point = in_metres(Point(lon, lat))
    nearest = tree.nearest(point)
    if nearest is None:
        return None
    return float(shapes[int(nearest)].distance(point))
