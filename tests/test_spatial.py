"""Tests for app/spatial.py against toy polygons written into a temporary folder.

A square "Delhi" with a few overlapping squares inside it is enough to check every
branch of get_zones, including the one that matters most: a point outside the boundary
gets one answer and no guesses about anything else.
"""

import json
from pathlib import Path

import pytest

from app.spatial import (
    ALL_LAYERS,
    CORE_LAYERS,
    TOPIC_LAYERS,
    clean_zone_name,
    distance_to_topic,
    get_zones,
    in_water,
    load_layer,
    load_layers,
    metric_shapes,
    topics_for,
)
from app.tagging import TOPICS


def square(x0: float, y0: float, x1: float, y1: float) -> dict:
    """A rectangular polygon as GeoJSON geometry, in (lon, lat) order."""
    return {
        "type": "Polygon",
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


#: A toy Delhi from (77.0, 28.5) to (77.4, 28.8), with policy zones laid over it.
TOY_LAYERS: dict[str, list[tuple[dict, dict]]] = {
    "nctd_boundary": [(square(77.0, 28.5, 77.4, 28.8), {"zone_name": "NCTD"})],
    "planning_zones": [
        (square(77.0, 28.5, 77.2, 28.8), {"zone_name": "G"}),
        (square(77.2, 28.5, 77.3, 28.8), {"zone_name": "O"}),
        (square(77.3, 28.5, 77.4, 28.8), {"zone_name": "P- I"}),
    ],
    "tod_zone": [(square(77.05, 28.55, 77.10, 28.60), {})],
    "high_density_corridor": [(square(77.12, 28.55, 77.16, 28.60), {})],
    "land_pooling_area": [(square(77.05, 28.70, 77.10, 28.75), {"zone": "L"})],
    "regional_park": [(square(77.30, 28.70, 77.35, 28.75), {})],
    "low_density_area": [(square(77.36, 28.70, 77.39, 28.75), {"type": "village"})],
    # the river runs down the middle of planning zone O
    "yamuna_river": [(square(77.24, 28.5, 77.26, 28.8), {})],
}


@pytest.fixture
def toy_folder(tmp_path: Path) -> Path:
    """Write the toy layers out as GeoJSON files, named the way spatial.py expects."""
    for name, features in TOY_LAYERS.items():
        (tmp_path / f"{name}.geojson").write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "geometry": geometry, "properties": properties}
                        for geometry, properties in features
                    ],
                }
            ),
            encoding="utf-8",
        )
    return tmp_path


@pytest.fixture
def toy(toy_folder: Path):
    """The toy layers loaded, with the cache cleared so the real ones are never used."""
    load_layers.cache_clear()
    layers = load_layers(str(toy_folder), ALL_LAYERS)
    yield layers
    load_layers.cache_clear()


def test_every_layer_name_is_loaded(toy) -> None:
    """A missing layer would silently answer False for its zone, so all eight are required."""
    assert set(toy) == set(ALL_LAYERS)


def test_the_default_load_leaves_out_the_layer_no_policy_uses(toy_folder: Path) -> None:
    """D-110. `load_layers()` loads the seven core layers and not the river.

    The river polygon answers one question — is this zone O test point in the water —
    and `scripts/07_test_points.py` is the only caller, so a server that parsed it and
    built an STRtree over it at every startup was paying for nothing.
    """
    load_layers.cache_clear()
    try:
        assert set(load_layers(str(toy_folder))) == set(CORE_LAYERS)
        assert "yamuna_river" not in load_layers(str(toy_folder))
        # ...and `in_water` still works, because it asks for the layer by name.
        assert in_water(28.6, 77.25, load_layers(str(toy_folder), ALL_LAYERS))
    finally:
        load_layers.cache_clear()


def test_a_point_outside_delhi_answers_only_that(toy) -> None:
    """"Is this plot in a TOD zone?" has no honest answer in Gurugram (D-031)."""
    assert get_zones(28.49, 76.90, toy) == {"inside_delhi": False}
    assert get_zones(28.90, 77.20, toy) == {"inside_delhi": False}


def test_a_plain_point_inside_delhi_is_in_no_policy_zone(toy) -> None:
    """The P_PLAIN case: in Delhi, in a planning zone, in none of the four policies."""
    zones = get_zones(28.65, 77.18, toy)
    assert zones["inside_delhi"] is True
    assert zones["planning_zone"] == "G"
    assert not any(zones[key] for key in ("tod", "hdc", "land_pooling", "zone_o"))
    assert topics_for(zones) == []


def test_a_point_in_the_tod_square_is_tod_and_nothing_else(toy) -> None:
    """The P_TOD case."""
    zones = get_zones(28.57, 77.07, toy)
    assert zones["tod"] is True
    assert zones["hdc"] is False
    assert zones["land_pooling"] is False
    assert topics_for(zones) == ["tod"]


def test_a_point_in_the_corridor_is_hdc(toy) -> None:
    """The P_HDC case."""
    zones = get_zones(28.57, 77.14, toy)
    assert zones["hdc"] is True
    assert zones["tod"] is False
    assert topics_for(zones) == ["hdc"]


def test_zone_o_comes_from_the_planning_zone_letter(toy) -> None:
    """zone_o is not a layer of its own: it is planning zone O (D-024)."""
    zones = get_zones(28.65, 77.22, toy)
    assert zones["planning_zone"] == "O"
    assert zones["zone_o"] is True
    assert topics_for(zones) == ["zone_o"]


def test_a_land_pooling_point_reports_which_pooling_zone(toy) -> None:
    """The P_LP case, with the layer's own zone label."""
    zones = get_zones(28.72, 77.07, toy)
    assert zones["land_pooling"] is True
    assert zones["land_pooling_zone"] == "L"
    assert topics_for(zones) == ["land_pooling"]


def test_the_park_and_lda_layers_are_policy_topics(toy) -> None:
    """Both became policy topics in D-069, and the Ridge's topic is not its layer's name.

    The layer and the `get_zones` key are both `regional_park`, because that is what
    DDA calls the polygons. The tagging topic is `ridge`, because that is what
    MPD-2047 calls the thing. `TOPIC_KEYS` is where the two meet.
    """
    park = get_zones(28.72, 77.32, toy)
    assert park["regional_park"] is True
    assert topics_for(park) == ["ridge"]
    lda = get_zones(28.72, 77.37, toy)
    assert lda["lda"] is True
    assert topics_for(lda) == ["lda"]


def test_the_river_is_separate_from_zone_o(toy) -> None:
    """A point can be in planning zone O and on land, which is what P_ZONEO needs."""
    on_land = (28.65, 77.22)
    in_river = (28.65, 77.25)
    assert get_zones(*on_land, toy)["zone_o"] is True
    assert not in_water(*on_land, toy)
    assert get_zones(*in_river, toy)["zone_o"] is True
    assert in_water(*in_river, toy)


def test_a_point_on_a_shared_boundary_still_belongs_to_a_zone(toy) -> None:
    """The planning zones tile Delhi, so `covers` is used rather than `contains` (D-031)."""
    zones = get_zones(28.65, 77.2, toy)  # exactly on the G/O edge
    assert zones["inside_delhi"] is True
    assert zones["planning_zone"] in {"G", "O"}


def test_a_point_on_the_delhi_boundary_counts_as_inside(toy) -> None:
    """A click on the city edge should not read as "not in Delhi"."""
    assert get_zones(28.5, 77.0, toy)["inside_delhi"] is True


def test_zone_names_are_tidied(toy) -> None:
    """The layer stores 'P- I' and blank cells; neither should reach the caller raw."""
    assert get_zones(28.65, 77.35, toy)["planning_zone"] == "P-I"
    assert clean_zone_name(" ") is None
    assert clean_zone_name(None) is None
    assert clean_zone_name("K- II") == "K-II"


def test_a_missing_layer_file_says_what_to_run(toy_folder: Path) -> None:
    """The error has to name the script, because this is the first thing to go wrong."""
    (toy_folder / "tod_zone.geojson").unlink()
    with pytest.raises(Exception) as caught:
        load_layer("tod_zone", toy_folder)
    assert "06_fetch_layers.py" in str(caught.value)


# --- how far away is a zone the point is not in? (D-094) ------------------------


@pytest.fixture
def toy_distances(toy_folder: Path):
    """The toy layers, with both caches cleared so nothing real is measured."""
    load_layers.cache_clear()
    metric_shapes.cache_clear()
    folder = str(toy_folder)
    load_layers(folder)
    yield folder
    load_layers.cache_clear()
    metric_shapes.cache_clear()


def test_a_point_inside_a_zone_is_zero_metres_from_it(toy_distances) -> None:
    """A distance, not a "how far outside": inside is 0.0 and not None."""
    inside_tod = (28.57, 77.07)
    assert distance_to_topic(*inside_tod, "tod", toy_distances) == pytest.approx(0.0)


def test_a_point_outside_a_zone_gets_its_distance_in_metres(toy_distances) -> None:
    """The toy TOD square runs to 77.10, so a point at 77.15 is about 5 km east of it.

    Asserted as a range rather than a figure: the value is a real UTM distance and
    pinning it would make the test about pyproj's arithmetic.
    """
    metres = distance_to_topic(28.57, 77.15, "tod", toy_distances)
    assert metres is not None
    assert 4_000 < metres < 6_000


def test_zone_o_is_measured_from_the_planning_zone_and_not_a_layer(toy_distances) -> None:
    """Zone O has no layer of its own, so planning_zones is filtered on its name.

    The toy zone O runs from 77.2 to 77.3. A point at 77.07 is west of it, and a point
    inside it is 0 m away — which is the check that the filter kept the right polygon
    and not all three planning zones.
    """
    assert distance_to_topic(28.6, 77.25, "zone_o", toy_distances) == pytest.approx(0.0)
    metres = distance_to_topic(28.6, 77.07, "zone_o", toy_distances)
    assert metres is not None and metres > 10_000
    # planning zone G covers 77.07, so a point there is in *a* planning zone already
    assert get_zones(28.6, 77.07, load_layers(toy_distances))["planning_zone"] == "G"


def test_every_policy_topic_has_a_layer_to_measure_against() -> None:
    """A topic with no entry would silently answer None and the note would lose its
    distance, so the mapping has to cover all six (D-094)."""
    assert set(TOPIC_LAYERS) == set(TOPICS)
    assert all(name for name, _ in TOPIC_LAYERS.values())


def test_an_unknown_topic_has_no_distance(toy_distances) -> None:
    """None rather than an exception: the note drops the distance clause and goes on."""
    assert distance_to_topic(28.6, 77.1, "not_a_topic", toy_distances) is None
