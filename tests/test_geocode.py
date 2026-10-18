"""Tests for app/geocode.py: normalisation, the gazetteer, and every Nominatim path.

No test here touches the network. Nominatim is a stub session whose scripted replies
are asserted against, and the gazetteer is written into a tmp folder by the test, so
the suite passes on a clone where `scripts/build_gazetteer.py` has never run.
"""

import json
import pytest

from app.geocode import (
    PATH_GAZETTEER,
    PATH_NOMINATIM_NORMALISED,
    PATH_NOMINATIM_ORIGINAL,
    PATH_NOT_FOUND,
    gazetteer,
    gazetteer_match,
    locate_place,
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
