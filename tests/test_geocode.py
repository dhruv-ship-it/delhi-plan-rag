"""Tests for app/geocode.py: normalisation, the gazetteer, and every Nominatim path.

No test here touches the network. Nominatim is a stub session whose scripted replies
are asserted against, and the gazetteer is written into a tmp folder by the test, so
the suite passes on a clone where `scripts/build_gazetteer.py` has never run.
"""

import json

import pytest

from app.config import settings
from app.geocode import (
    PATH_GAZETTEER,
    PATH_GAZETTEER_INTERCHANGE,
    PATH_NOMINATIM_NORMALISED,
    PATH_NOMINATIM_ORIGINAL,
    PATH_NOT_FOUND,
    all_within,
    base_name,
    gazetteer,
    gazetteer_match,
    interchange_entries,
    locate_place,
    metres_between,
    normalise,
)

#: What Nominatim returns for a hit, trimmed to the fields we read.
RAJIV_CHOWK = {
    "lat": "28.63177",
    "lon": "77.21938",
    "display_name": "Connaught Place, New Delhi, Delhi, 110001, India",
}


class StubResponse:
    """Stands in for a requests.Response."""

    def __init__(self, payload, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class StubSession:
    """A session that replies from a script and records what it was asked.

    One entry per expected request. A reply may be a list (what Nominatim returns), or
    an exception instance to raise, which is how the timeout path is tested.
    """

    def __init__(self, replies) -> None:
        self.replies = list(replies)
        self.queries: list[str] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.queries.append((params or {}).get("q", ""))
        if not self.replies:
            raise AssertionError(f"unexpected extra request for {(params or {}).get('q')!r}")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return StubResponse(reply)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Take the one-request-a-second pause out, for tests only.

    The limiter is real and the policy it enforces is real (D-046), but sleeping a
    second per stubbed request put 12 seconds into a suite that otherwise runs in four
    — and a slow suite is one that stops being run on every change (D-036). The limiter
    has its own test; everything else gets the fast one.
    """
    monkeypatch.setattr("app.geocode._LIMITER.interval", 0.0, raising=False)
    gazetteer.cache_clear()
    yield
    gazetteer.cache_clear()


def test_the_rate_limiter_really_does_wait() -> None:
    """The policy is one request a second, so the limiter is tested on its own."""
    import time

    from app.geocode import RateLimiter

    limiter = RateLimiter(0.05)
    limiter.wait()
    started = time.monotonic()
    limiter.wait()
    assert time.monotonic() - started >= 0.04


# --- normalising ----------------------------------------------------------------


def test_the_station_words_come_off_the_end() -> None:
    assert normalise("Dwarka Sector 21 metro station") == "dwarka sector 21"
    assert normalise("Rajiv Chowk Metro Station, New Delhi") == "rajiv chowk"


def test_proximity_words_come_off_anywhere() -> None:
    assert normalise("near Rajiv Chowk") == "rajiv chowk"
    assert normalise("nearest Hauz Khas") == "hauz khas"


def test_a_station_word_inside_a_place_name_survives() -> None:
    """Station Road is a road and Metro Vihar is a colony (D-073)."""
    assert normalise("Station Road") == "station road"
    assert normalise("Metro Vihar") == "metro vihar"
    assert normalise("Delhi Gate") == "delhi gate"


def test_punctuation_and_case_go() -> None:
    assert normalise("  CONNAUGHT   PLACE!!  ") == "connaught place"


def test_a_stranded_preposition_goes() -> None:
    assert normalise("near the Yamuna in Delhi") == "yamuna"
    assert normalise("on Ring Road") == "ring road"


def test_a_query_of_nothing_but_qualifiers_normalises_to_nothing() -> None:
    """And `locate_place` then has only the original query to try."""
    assert normalise("metro station") == ""
    assert normalise("near") == ""


def test_normalising_leaves_a_place_outside_delhi_alone() -> None:
    """The box, not the normaliser, is what keeps Mumbai out."""
    assert normalise("Mumbai Central") == "mumbai central"


# --- the gazetteer --------------------------------------------------------------

NAMES = {
    "rajiv chowk": {"name": "Rajiv Chowk", "lat": 28.6328, "lon": 77.2197},
    "dwarka sector 21": {"name": "Dwarka Sector 21", "lat": 28.5522, "lon": 77.0587},
    "civil lines": {"name": "Civil Lines", "lat": 28.6769, "lon": 77.2250},
    "civic centre": {"name": "Civic Centre", "lat": 28.6400, "lon": 77.2300},
}


def test_an_exact_name_matches() -> None:
    assert gazetteer_match("rajiv chowk", NAMES)["name"] == "Rajiv Chowk"


def test_a_near_miss_matches_above_the_cutoff() -> None:
    """A typed name is rarely exact, which is the whole reason for difflib."""
    assert gazetteer_match("rajib chowk", NAMES)["name"] == "Rajiv Chowk"
    assert gazetteer_match("civil line", NAMES)["name"] == "Civil Lines"


def test_an_unrelated_query_matches_nothing() -> None:
    assert gazetteer_match("mumbai central", NAMES) is None
    assert gazetteer_match("nothing like this at all", NAMES) is None


def test_an_empty_query_matches_nothing() -> None:
    assert gazetteer_match("", NAMES) is None


def test_a_gazetteer_that_does_not_exist_is_empty_not_an_error() -> None:
    """A clone that has never run the build script still works (D-073)."""
    assert gazetteer_match("rajiv chowk", {}) is None


def test_an_ambiguous_match_is_refused() -> None:
    """Two names equally close means the query identified neither of them."""
    pair = {
        "sector 21": {"name": "Sector 21", "lat": 1.0, "lon": 1.0},
        "sector 22": {"name": "Sector 22", "lat": 2.0, "lon": 2.0},
    }
    assert gazetteer_match("sector 2x", pair) is None


def test_one_station_under_two_of_its_own_names_is_not_ambiguous() -> None:
    """An alternate name is the same place, so matching both is still one answer."""
    station = {"name": "Rajiv Chowk", "lat": 28.6328, "lon": 77.2197}
    names = {"rajiv chowk": station, "rajiv chowks": station}
    assert gazetteer_match("rajiv chowk", names) is station


# --- the four paths -------------------------------------------------------------


def test_the_gazetteer_answers_without_any_request(monkeypatch, tmp_path) -> None:
    """The case night 2 could not geocode at all (D-049) now needs no network."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: NAMES)
    session = StubSession([])  # any request would raise
    place = locate_place("Dwarka Sector 21 metro station", use_cache=False, session=session)

    assert place.found is True
    assert place.path == PATH_GAZETTEER
    assert place.lat == pytest.approx(28.5522)
    assert "Delhi Metro" in place.display_name
    assert session.queries == []


def test_nominatim_is_asked_with_the_original_query_first(monkeypatch) -> None:
    """The user's own words, plus ", Delhi", are the first thing tried."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([[RAJIV_CHOWK]])
    place = locate_place("Connaught Place", use_cache=False, session=session)

    assert place.found is True
    assert place.path == PATH_NOMINATIM_ORIGINAL
    assert session.queries == ["Connaught Place, Delhi"]


def test_the_normalised_query_is_the_second_attempt(monkeypatch) -> None:
    """When the user's phrasing finds nothing, the stripped form is tried once."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([[], [RAJIV_CHOWK]])
    place = locate_place("near Connaught Place metro station", use_cache=False, session=session)

    assert place.found is True
    assert place.path == PATH_NOMINATIM_NORMALISED
    assert session.queries == [
        "near Connaught Place metro station, Delhi",
        "connaught place, Delhi",
    ]


def test_at_most_two_nominatim_requests_are_made(monkeypatch) -> None:
    """Each one costs a second of someone else's donated capacity (D-073)."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([[], []])
    place = locate_place("near Somewhere metro station", use_cache=False, session=session)

    assert place.found is False
    assert place.reason == "not_found_in_delhi"
    assert place.path == PATH_NOT_FOUND
    assert len(session.queries) == 2


def test_only_one_request_when_normalising_changes_nothing(monkeypatch) -> None:
    """"Hauz Khas" normalises to itself, so asking twice would ask the same thing."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([[]])
    place = locate_place("hauz khas", use_cache=False, session=session)

    assert place.found is False
    assert session.queries == ["hauz khas, Delhi"]


def test_a_place_outside_the_box_is_not_found(monkeypatch) -> None:
    """Bounded search returns nothing for Mumbai, which is the useful answer (D-046)."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([[], []])
    place = locate_place("Mumbai Central", use_cache=False, session=session)

    assert place.found is False
    assert place.reason == "not_found_in_delhi"


def test_a_timeout_stops_rather_than_spending_a_second_request(monkeypatch) -> None:
    """A failing service says nothing about the name, so retrying it is waste."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    session = StubSession([TimeoutError("timed out"), [RAJIV_CHOWK]])
    place = locate_place("near Connaught Place metro", use_cache=False, session=session)

    assert place.found is False
    assert place.reason.startswith("lookup_failed")
    assert len(session.queries) == 1


def test_a_server_error_is_a_lookup_failure_not_a_miss(monkeypatch) -> None:
    """A 500 is about the service, not about whether the place exists."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    class Failing(StubSession):
        def get(self, url, params=None, headers=None, timeout=None):
            self.queries.append((params or {}).get("q", ""))
            return StubResponse(None, status=500)

    place = locate_place("Somewhere", use_cache=False, session=Failing([]))
    assert place.found is False
    assert place.reason.startswith("lookup_failed")


def test_an_empty_query_never_reaches_the_network() -> None:
    session = StubSession([])
    place = locate_place("   ", use_cache=False, session=session)
    assert place.found is False
    assert place.reason == "empty_query"
    assert session.queries == []


def test_the_path_is_reported_in_the_tool_result(monkeypatch) -> None:
    """The agent's tool returns to_dict, and a miss has to be diagnosable from it."""
    monkeypatch.setattr("app.geocode.gazetteer", lambda: NAMES)
    found = locate_place("Rajiv Chowk", use_cache=False, session=StubSession([])).to_dict()
    assert found["path"] == PATH_GAZETTEER

    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})
    missed = locate_place("Nowhere", use_cache=False, session=StubSession([[]])).to_dict()
    assert missed["path"] == PATH_NOT_FOUND
    assert missed["found"] is False


# --- the cache ------------------------------------------------------------------


def test_a_hit_is_cached_and_the_second_call_makes_no_request(monkeypatch, tmp_path) -> None:
    cache_file = tmp_path / "geocode_cache.json"
    monkeypatch.setattr("app.geocode.load_cache", lambda: _read(cache_file))
    monkeypatch.setattr("app.geocode.save_cache", lambda cache: _write(cache_file, cache))
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    first = locate_place("Connaught Place", session=StubSession([[RAJIV_CHOWK]]))
    assert first.found is True

    second = locate_place("Connaught Place", session=StubSession([]))
    assert second.found is True
    assert second.lat == pytest.approx(float(RAJIV_CHOWK["lat"]))


def test_a_miss_is_cached_but_a_timeout_is_not(monkeypatch, tmp_path) -> None:
    """An honest "no such place" is worth remembering; a network failure is not (D-046)."""
    cache_file = tmp_path / "geocode_cache.json"
    monkeypatch.setattr("app.geocode.load_cache", lambda: _read(cache_file))
    monkeypatch.setattr("app.geocode.save_cache", lambda cache: _write(cache_file, cache))
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    locate_place("Nowhere At All", session=StubSession([[], []]))
    assert "nowhere at all" in _read(cache_file)

    locate_place("Other Place", session=StubSession([TimeoutError("boom")]))
    assert "other place" not in _read(cache_file)


def _read(path):
    """The cache file as a dict, or {} when it is not there yet."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, cache):
    """Write the cache file."""
    path.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def test_a_remembered_miss_from_an_older_lookup_is_retried(monkeypatch, tmp_path) -> None:
    """Night 2 cached "dwarka sector 21 metro station" as not found (D-049, D-073).

    That entry was true of the lookup that wrote it and false of this one. A miss with
    no `path` field predates the four-step lookup, so it is thrown away and the query
    is tried again — otherwise the fix would appear not to work while being correct.
    """
    cache_file = tmp_path / "geocode_cache.json"
    _write(
        cache_file,
        {"dwarka sector 21 metro station": {"found": False, "reason": "not_found_in_delhi"}},
    )
    monkeypatch.setattr("app.geocode.load_cache", lambda: _read(cache_file))
    monkeypatch.setattr("app.geocode.save_cache", lambda cache: _write(cache_file, cache))
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    session = StubSession([[], [RAJIV_CHOWK]])
    place = locate_place("Dwarka Sector 21 metro station", session=session)

    assert place.found is True
    assert place.path == PATH_NOMINATIM_NORMALISED
    assert len(session.queries) == 2


def test_a_remembered_miss_from_this_lookup_is_trusted(monkeypatch, tmp_path) -> None:
    """Once the current lookup has recorded a miss, it is not re-asked."""
    cache_file = tmp_path / "geocode_cache.json"
    _write(
        cache_file,
        {
            "mumbai central": {
                "found": False,
                "reason": "not_found_in_delhi",
                "path": PATH_NOT_FOUND,
            }
        },
    )
    monkeypatch.setattr("app.geocode.load_cache", lambda: _read(cache_file))
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    session = StubSession([])  # any request would raise
    place = locate_place("Mumbai Central", session=session)
    assert place.found is False
    assert session.queries == []


def test_a_remembered_hit_is_always_trusted(monkeypatch, tmp_path) -> None:
    """A place does not move, so an old hit needs no re-checking."""
    cache_file = tmp_path / "geocode_cache.json"
    _write(cache_file, {"connaught place": {"found": True, "lat": 28.63, "lon": 77.22}})
    monkeypatch.setattr("app.geocode.load_cache", lambda: _read(cache_file))
    monkeypatch.setattr("app.geocode.gazetteer", lambda: {})

    place = locate_place("Connaught Place", session=StubSession([]))
    assert place.found is True
    assert place.lat == pytest.approx(28.63)


# --- the gazetteer file itself: absent, corrupt, or real ------------------------
#
# Everything above monkeypatches `gazetteer()` to a dict, which tests the matching but
# never the loading. These four go through the real loader with a real path, because
# "an absent gazetteer is a supported state" (D-074) is a claim about file handling and
# `scripts/build_gazetteer.py` needs a network host that has not always been reachable.


def _point_gazetteer_at(monkeypatch, path) -> None:
    """Make `settings.gazetteer_path` resolve to `path`, and drop the cached load.

    `gazetteer()` is `lru_cache`d and `settings` is a frozen dataclass whose
    `gazetteer_path` is a property, so the property is replaced on the type.
    """
    monkeypatch.setattr(
        type(settings), "gazetteer_path", property(lambda self: path), raising=True
    )
    gazetteer.cache_clear()


def test_a_gazetteer_file_that_is_not_there_loads_as_empty(monkeypatch, tmp_path) -> None:
    """The state of every clone that has never run the build script (D-074)."""
    missing = tmp_path / "never_built" / "metro_stations.json"
    _point_gazetteer_at(monkeypatch, missing)

    assert not missing.exists()
    assert gazetteer() == {}
    assert gazetteer_match("rajiv chowk") is None


def test_locate_place_falls_back_to_nominatim_with_no_gazetteer_file(
    monkeypatch, tmp_path
) -> None:
    """The whole point of D-074: no file, and the four-step path still answers.

    This is the end-to-end version. Nothing is stubbed except Nominatim itself, so the
    real `gazetteer()` runs, finds no file, returns `{}`, and step 3 answers.
    """
    _point_gazetteer_at(monkeypatch, tmp_path / "metro_stations.json")
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    session = StubSession([[RAJIV_CHOWK]])
    place = locate_place("Rajiv Chowk", use_cache=False, session=session)

    assert place.found is True
    assert place.path == PATH_NOMINATIM_ORIGINAL
    assert place.lat == pytest.approx(28.63177)
    assert session.queries == ["Rajiv Chowk, Delhi"]


def test_a_corrupt_gazetteer_file_is_empty_rather_than_an_error(monkeypatch, tmp_path) -> None:
    """A half-written file is the same supported state as no file.

    `build_gazetteer.py` writes in one go, but a disk that filled mid-write is exactly
    the kind of thing that happened on this project (night 3), and a geocoder that
    raises on startup is worse than one that falls back.
    """
    broken = tmp_path / "metro_stations.json"
    broken.write_text('{"stations": [{"name": "Rajiv Cho', encoding="utf-8")
    _point_gazetteer_at(monkeypatch, broken)

    assert gazetteer() == {}

    monkeypatch.setattr("app.geocode.load_cache", lambda: {})
    session = StubSession([[RAJIV_CHOWK]])
    place = locate_place("Rajiv Chowk", use_cache=False, session=session)
    assert place.found is True
    assert place.path == PATH_NOMINATIM_ORIGINAL


def test_a_real_gazetteer_file_is_loaded_and_answers_with_no_request(
    monkeypatch, tmp_path
) -> None:
    """The other half: a file in the shape build_gazetteer.py writes is actually read.

    Keyed by every normalised name a station has, so the alternate name answers too,
    and neither needs the network.
    """
    path = tmp_path / "metro_stations.json"
    path.write_text(
        json.dumps(
            {
                "stations": [
                    {
                        "name": "Dwarka Sector 21",
                        "alt_names": ["Yashobhoomi Dwarka Sector 21"],
                        "lat": 28.5519,
                        "lon": 77.0586,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _point_gazetteer_at(monkeypatch, path)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    assert set(gazetteer()) == {"dwarka sector 21", "yashobhoomi dwarka sector 21"}

    session = StubSession([])  # any request would raise
    for query in ("Dwarka Sector 21 metro station", "Yashobhoomi Dwarka Sector 21"):
        place = locate_place(query, use_cache=False, session=session)
        assert place.found is True, query
        assert place.path == PATH_GAZETTEER
        assert place.lat == pytest.approx(28.5519)
    assert session.queries == []


# --- interchanges: one entry per line, one answer for the bare name (D-084) -----
#
# OSM names an interchange once per line, so "Hauz Khas" matched nothing and fell
# through to Nominatim. These go through the real loader with a written file, because
# the grouping happens at load time and a monkeypatched dict would skip it entirely.


def _station(name: str, lat: float, lon: float, **extra) -> dict:
    """One station record in the shape build_gazetteer.py writes."""
    return {"name": name, "alt_names": [], "lat": lat, "lon": lon, **extra}


def _write_gazetteer(monkeypatch, tmp_path, stations: list[dict]):
    """Write a gazetteer file and point the loader at it."""
    path = tmp_path / "metro_stations.json"
    path.write_text(json.dumps({"stations": stations}), encoding="utf-8")
    _point_gazetteer_at(monkeypatch, path)
    return path


#: The real Hauz Khas platforms, to six decimals, 190 m apart.
HAUZ_KHAS = [
    _station("Hauz Khas (Magenta Line)", 28.543369, 77.205045),
    _station("Hauz Khas (Yellow Line)", 28.544256, 77.206707),
]


def test_the_base_name_is_the_name_without_its_parenthesised_suffix() -> None:
    assert base_name("Hauz Khas (Yellow Line)") == "Hauz Khas"
    assert base_name("Dilli Haat - INA (Pink Line)") == "Dilli Haat - INA"
    assert base_name("Rajiv Chowk") == "Rajiv Chowk"
    assert base_name("") == ""
    # not anchored anywhere but the end, so a bracket inside a name is left alone
    assert base_name("Some (Odd) Name") == "Some (Odd) Name"


def test_the_distance_helper_is_right_to_the_metre() -> None:
    """One degree of latitude is about 111 km, and the real pair is 190 m apart."""
    assert metres_between(28.0, 77.0, 29.0, 77.0) == pytest.approx(111195, rel=0.001)
    assert metres_between(28.5, 77.2, 28.5, 77.2) == 0.0
    gap = metres_between(28.543369, 77.205045, 28.544256, 77.206707)
    assert gap == pytest.approx(190, abs=5)


def test_hauz_khas_resolves_from_the_gazetteer(monkeypatch, tmp_path) -> None:
    """The finding D-081 recorded and left unfixed. No network call at all."""
    _write_gazetteer(monkeypatch, tmp_path, HAUZ_KHAS)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    assert "hauz khas" in gazetteer()

    session = StubSession([])  # any request would raise
    place = locate_place("Hauz Khas", use_cache=False, session=session)

    assert place.found is True
    assert place.path == PATH_GAZETTEER_INTERCHANGE
    assert session.queries == []
    # the centre of the two platforms, which is inside both of them
    assert place.lat == pytest.approx(28.5438, abs=0.0002)
    assert place.lon == pytest.approx(77.2059, abs=0.0002)
    assert "interchange" in place.display_name


def test_the_wordier_ways_of_asking_for_it_resolve_too(monkeypatch, tmp_path) -> None:
    """Normalisation runs first, so the qualifier is gone before the key is looked up."""
    _write_gazetteer(monkeypatch, tmp_path, HAUZ_KHAS)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    for query in ("Hauz Khas metro station", "near Hauz Khas", "hauz khas, new delhi"):
        place = locate_place(query, use_cache=False, session=StubSession([]))
        assert place.found is True, query
        assert place.path == PATH_GAZETTEER_INTERCHANGE, query


def test_each_platform_still_answers_under_its_own_name(monkeypatch, tmp_path) -> None:
    """The group is an extra entry, not a replacement: the line names still work."""
    _write_gazetteer(monkeypatch, tmp_path, HAUZ_KHAS)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    place = locate_place("Hauz Khas (Yellow Line)", use_cache=False, session=StubSession([]))
    assert place.found is True
    assert place.path == PATH_GAZETTEER  # the platform itself, not the centre
    assert place.lat == pytest.approx(28.544256)


def test_two_different_stations_with_similar_names_are_not_merged(monkeypatch, tmp_path) -> None:
    """The rule that matters most: never merge entries more than 300 m apart.

    Two real stations that share a base name and sit 2 km apart have not been
    identified by the bare name, so inventing a midpoint between them would be a wrong
    coordinate rather than a missing one. No bare-name entry is made, and the query
    falls through to Nominatim — the same call D-073 makes for an ambiguous match.
    """
    far_apart = [
        _station("Mayur Vihar (Phase I)", 28.6040, 77.2895),
        _station("Mayur Vihar (Phase III)", 28.6120, 77.3120),  # about 2.3 km away
    ]
    assert metres_between(28.6040, 77.2895, 28.6120, 77.3120) > 300
    _write_gazetteer(monkeypatch, tmp_path, far_apart)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    keys = set(gazetteer())
    assert "mayur vihar phase i" in keys
    assert "mayur vihar phase iii" in keys
    assert "mayur vihar" not in keys  # the thing being asserted

    session = StubSession([[RAJIV_CHOWK]])
    place = locate_place("Mayur Vihar", use_cache=False, session=session)
    assert place.path == PATH_NOMINATIM_ORIGINAL
    assert session.queries == ["Mayur Vihar, Delhi"]


def test_three_platforms_are_merged_only_if_every_pair_is_close(monkeypatch, tmp_path) -> None:
    """All-pairs, not a chain. A 250 m from B and B 250 m from C is 500 m A to C."""
    chained = [
        _station("Chain Street (Line One)", 28.60000, 77.20000),
        _station("Chain Street (Line Two)", 28.60225, 77.20000),  # ~250 m from the first
        _station("Chain Street (Line Three)", 28.60450, 77.20000),  # ~500 m from the first
    ]
    assert metres_between(28.60000, 77.20000, 28.60225, 77.20000) < 300
    assert metres_between(28.60000, 77.20000, 28.60450, 77.20000) > 300
    _write_gazetteer(monkeypatch, tmp_path, chained)

    assert "chain street" not in gazetteer()


def test_a_station_really_named_without_a_suffix_keeps_its_own_coordinate(
    monkeypatch, tmp_path
) -> None:
    """The Botanical Garden case, which is in the real data.

    OSM holds `Botanical Garden` **and** `Botanical Garden (Blue Line)` and
    `Botanical Garden (Magenta Line)`. A computed centre must not displace a name the
    source actually carries, so group entries are added last and never overwrite.
    """
    stations = [
        _station("Botanical Garden", 28.564100, 77.334500),
        _station("Botanical Garden (Blue Line)", 28.563943, 77.334400),
        _station("Botanical Garden (Magenta Line)", 28.563905, 77.333837),
    ]
    _write_gazetteer(monkeypatch, tmp_path, stations)
    monkeypatch.setattr("app.geocode.load_cache", lambda: {})

    place = locate_place("Botanical Garden", use_cache=False, session=StubSession([]))
    assert place.found is True
    assert place.path == PATH_GAZETTEER  # the real entry, not a computed centre
    assert place.lat == pytest.approx(28.564100)


def test_one_suffixed_entry_on_its_own_is_not_grouped(monkeypatch, tmp_path) -> None:
    """A single platform is already findable under its own name; a group adds nothing.

    It would also be a guess: with one member there is nothing to check a radius
    against.
    """
    _write_gazetteer(
        monkeypatch, tmp_path, [_station("Lonely Halt (Orange Line)", 28.60, 77.20)]
    )
    keys = set(gazetteer())
    assert keys == {"lonely halt orange line"}


def test_an_unsuffixed_gazetteer_gains_nothing(monkeypatch, tmp_path) -> None:
    """Grouping is inert on names that carry no parenthesised suffix."""
    stations = [
        _station("Rajiv Chowk", 28.6328, 77.2197),
        _station("Dwarka Sector 21", 28.5522, 77.0587),
    ]
    _write_gazetteer(monkeypatch, tmp_path, stations)
    assert set(gazetteer()) == {"rajiv chowk", "dwarka sector 21"}
    assert interchange_entries(stations) == []


def test_the_group_entry_records_which_platforms_it_came_from() -> None:
    """So a surprising coordinate can be traced back to the entries that produced it."""
    entries = interchange_entries(HAUZ_KHAS)
    assert len(entries) == 1
    assert entries[0]["name"] == "Hauz Khas"
    assert entries[0]["interchange_of"] == [
        "Hauz Khas (Magenta Line)",
        "Hauz Khas (Yellow Line)",
    ]


def test_a_station_with_no_coordinates_is_skipped(monkeypatch, tmp_path) -> None:
    """A malformed record should not take the loader down (D-073)."""
    stations = [
        {"name": "No Point (Blue Line)", "alt_names": [], "lat": None, "lon": None},
        _station("Hauz Khas (Magenta Line)", 28.543369, 77.205045),
        _station("Hauz Khas (Yellow Line)", 28.544256, 77.206707),
    ]
    _write_gazetteer(monkeypatch, tmp_path, stations)
    keys = set(gazetteer())
    assert "hauz khas" in keys
    assert "no point blue line" not in keys


def test_all_within_is_true_for_one_station_and_for_none() -> None:
    """There is no pair to be too far apart, which is vacuously fine."""
    assert all_within([], 300.0) is True
    assert all_within([_station("Only", 28.6, 77.2)], 300.0) is True
