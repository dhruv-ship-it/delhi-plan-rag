"""Turn a place name into coordinates, so a user can ask "near Dwarka Sector 21" instead of clicking.

The map interface gives ZoneWise a point. The agent (app/agent.py) does not have one: it
is given plain text like "near Dwarka Sector 21 metro station" and has to find the point
itself before anything else can happen. This module is that step, and it is the only
place in the project that talks to a service other than Anthropic.

Night 2 found the obvious failure (D-049): Nominatim returns **nothing** for "Dwarka
Sector 21 metro station" with `bounded=1` and `limit=1`, which is close to the phrase
the agent's own example suggests typing. One geocoder's indexing of one naming
convention should not be the only thing between a user and an answer, so `locate_place`
now tries four things in order and reports which one worked:

  1. **normalise**   lower case, strip "near", "metro station", "metro", "station",
                     punctuation -> "dwarka sector 21"
  2. **gazetteer**   fuzzy-match the normalised query against the local metro station
                     list with difflib, cutoff 0.85, and accept only a unique best match
  3. **Nominatim**   the original query + ", Delhi", then the normalised query + ", Delhi"
  4. **not_found**   and say so, rather than returning a point somewhere else

Every result carries `path`, naming the step that produced it, and every result is
cached. The point of recording the path is that a miss is then diagnosable from the
cache alone, without spending more live requests to find out what happened.

Nominatim's usage policy is honoured rather than approximated: one request a second,
enforced by a lock so it holds when two requests arrive together; a 30 second timeout;
an honest User-Agent naming the project; and the search bounded to a box around NCT
Delhi, so "Mumbai Central" comes back as not found rather than as a point 1,200 km away
that `get_zones` would then report as outside Delhi.
"""

import difflib
import json
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

import requests

from app.config import settings

#: A box around NCT Delhi: left, top, right, bottom in longitude/latitude.
#: Delhi runs about 76.84 to 77.35 east and 28.40 to 28.89 north; this is a little wider
#: so a place on the boundary is still found.
DELHI_VIEWBOX = (76.80, 28.92, 77.40, 28.36)

#: Nominatim is asked to stay inside the box (bounded=1) and inside India.
COUNTRY_CODES = "in"

#: Which step produced a result. Reported so a miss can be diagnosed from the cache.
PATH_GAZETTEER = "gazetteer"
PATH_NOMINATIM_ORIGINAL = "nominatim_original"
PATH_NOMINATIM_NORMALISED = "nominatim_normalised"
PATH_CACHE = "cache"
PATH_NOT_FOUND = "not_found"

#: Words that mean "somewhere near here" rather than naming a place. No Delhi place
#: name contains one, so these are removed wherever they appear.
PROXIMITY_WORDS = (
    "near to",
    "close to",
    "closest to",
    "nearest to",
    "nearest",
    "closest",
    "around",
    "near",
)

#: Qualifiers that follow a place name: "Rajiv Chowk metro station", "Saket, New Delhi".
#: These are stripped only from the **end** of the query, repeatedly, because every one
#: of them can also be part of a name: Station Road is a road, Metro Vihar is a colony,
#: and Delhi Gate is a gate (D-073). Longest first, so "metro station" is matched before
#: "metro" and "station".
TRAILING_QUALIFIERS = (
    "metro station",
    "railway station",
    "metro stn",
    "new delhi",
    "metro",
    "station",
    "delhi",
    "ncr",
    "india",
)

#: A preposition left stranded at either end once the other words are gone: "near the
#: Yamuna in Delhi" loses "Delhi" from the end and would otherwise keep the "in". Never
#: the only word, so a query of "the" still normalises to something.
LEADING_WORDS = ("to", "in", "at", "the", "a", "of", "from", "on", "by")

#: What a suffix like ", Delhi" is added to, for Nominatim's benefit.
DELHI_SUFFIX = ", Delhi"

#: Punctuation goes; everything else is collapsed to single spaces.
PUNCTUATION = re.compile(r"[^\w\s]+")


@dataclass(frozen=True)
class Place:
    """One geocoding result, or a miss."""

    query: str
    found: bool
    lat: float | None = None
    lon: float | None = None
    display_name: str | None = None
    reason: str | None = None
    #: Which of the four steps produced this result. See the module docstring.
    path: str | None = None

    def to_dict(self) -> dict:
        """The result as plain JSON, which is what the agent's tool returns."""
        if not self.found:
            return {
                "query": self.query,
                "found": False,
                "reason": self.reason or "not_found",
                "path": self.path or PATH_NOT_FOUND,
            }
        return {
            "query": self.query,
            "found": True,
            "lat": self.lat,
            "lon": self.lon,
            "display_name": self.display_name,
            "path": self.path,
        }


class RateLimiter:
    """Lets one call through at a time, never faster than `interval` seconds apart.

    Nominatim's usage policy is one request a second from a single source. The lock
    makes that hold even if two requests arrive together, which they will once the
    agent runs behind the API.
    """

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        """Block until it is polite to send the next request."""
        with self._lock:
            gap = time.monotonic() - self._last
            if gap < self.interval:
                time.sleep(self.interval - gap)
            self._last = time.monotonic()


_LIMITER = RateLimiter(settings.geocode_min_interval_s)


# --- normalising a query --------------------------------------------------------


def _strip_trailing(text: str) -> str:
    """Remove every trailing qualifier, repeatedly.

    Repeatedly because they stack: "rajiv chowk metro station new delhi" has to lose
    "new delhi" before "metro station" is at the end to be found.
    """
    changed = True
    while changed and text:
        changed = False
        for phrase in TRAILING_QUALIFIERS:
            if text == phrase or text.endswith(" " + phrase):
                text = text[: len(text) - len(phrase)].strip()
                changed = True
                break
    return text


def normalise(query: str) -> str:
    """Reduce a place name to the part that identifies the place.

    "near Rajiv Chowk metro station!" becomes "rajiv chowk", and
    "Rajiv Chowk Metro Station, New Delhi" becomes the same thing.

    The two kinds of word are treated differently, because they have to be.
    Proximity words ("near", "nearest") never appear in a Delhi place name, so they
    go wherever they are. Station words do appear in place names — Station Road,
    Metro Vihar — so they are only stripped from the end of the query, which is
    where a qualifier sits and where a name does not. The first version of this
    function stripped them anywhere and turned "Station Road" into "road" (D-073).
    """
    text = PUNCTUATION.sub(" ", query.lower())
    text = " ".join(text.split())
    for phrase in PROXIMITY_WORDS:
        text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text)
        text = " ".join(text.split())
    text = _strip_trailing(text)
    words = text.split()
    while len(words) > 1 and words[0] in LEADING_WORDS:
        words.pop(0)
    while len(words) > 1 and words[-1] in LEADING_WORDS:
        words.pop()  # "near the Yamuna in Delhi" leaves a trailing "in" once Delhi goes
    return " ".join(words)


# --- the local gazetteer --------------------------------------------------------


@lru_cache(maxsize=1)
def gazetteer() -> dict[str, dict]:
    """The metro station gazetteer, keyed by every normalised name a station has.

    Empty when `scripts/build_gazetteer.py` has not been run. That is a supported
    state, not an error: the gazetteer is an optimisation over Nominatim and the
    remaining steps work without it (D-073).
    """
    path = settings.gazetteer_path
    if not path.exists():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    found: dict[str, dict] = {}
    for station in document.get("stations", []):
        names = [station.get("name") or ""] + list(station.get("alt_names") or [])
        for name in names:
            key = normalise(name)
            if key and key not in found:
                found[key] = station
    return found


def gazetteer_match(normalised: str, names: dict[str, dict] | None = None) -> dict | None:
    """The one gazetteer station a normalised query names, or None.

    An exact key hit wins outright. Otherwise difflib's `get_close_matches` is asked
    for the best candidates above `settings.gazetteer_cutoff`, and the match is taken
    **only when it is unique** — when two station names are equally close, the query
    has not identified either of them, and guessing between "Civil Lines" and "Civic
    Centre" is worse than falling through to Nominatim (D-073).
    """
    names = gazetteer() if names is None else names
    if not normalised or not names:
        return None
    if normalised in names:
        return names[normalised]

    close = difflib.get_close_matches(
        normalised, list(names), n=3, cutoff=settings.gazetteer_cutoff
    )
    if not close:
        return None
    best = close[0]
    best_ratio = difflib.SequenceMatcher(None, normalised, best).ratio()
    for other in close[1:]:
        if names[other] is names[best]:
            continue  # the same station under two of its own names is not ambiguous
        if difflib.SequenceMatcher(None, normalised, other).ratio() == best_ratio:
            return None
    return names[best]


# --- the cache ------------------------------------------------------------------


def load_cache() -> dict[str, dict]:
    """Read the geocode cache, which is gitignored and may not exist yet."""
    path = settings.geocode_cache_path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}  # a corrupt cache is not worth failing a request over


def save_cache(cache: dict[str, dict]) -> None:
    """Write the geocode cache back."""
    path = settings.geocode_cache_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cache_key(query: str) -> str:
    """The key a query is remembered under: trimmed and lower case."""
    return " ".join(query.split()).lower()


def is_stale_miss(stored: dict) -> bool:
    """True for a remembered miss that an older version of this module recorded.

    This matters more than it looks. Night 2 cached "dwarka sector 21 metro station"
    as not found, which was true of the lookup it had. Tonight's lookup can answer it —
    but the cached miss would be returned first, and the fix would appear not to work
    while being perfectly correct. A remembered **hit** stays valid, because a place
    does not move; a remembered **miss** is a statement about the algorithm as much as
    about the name, so a miss recorded without a `path` field predates the four-step
    lookup and is thrown away (D-073).
    """
    return not stored.get("found") and "path" not in stored


# --- Nominatim ------------------------------------------------------------------


def ask_nominatim(query: str, session=None) -> tuple[dict | None, str | None]:
    """One bounded Nominatim search. Returns (the best result, the reason there was none).

    A `reason` of "not_found_in_delhi" is an answer about the name. Anything else is a
    failure of the lookup, and the difference matters to the caller: a miss is worth
    caching and a timeout is not.
    """
    left, top, right, bottom = DELHI_VIEWBOX
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": COUNTRY_CODES,
        "viewbox": f"{left},{top},{right},{bottom}",
        "bounded": 1,
    }
    headers = {"User-Agent": settings.geocode_user_agent}

    _LIMITER.wait()
    try:
        getter = session.get if session is not None else requests.get
        response = getter(
            settings.geocode_url,
            params=params,
            headers=headers,
            timeout=settings.geocode_timeout_s,
        )
        response.raise_for_status()
        found = response.json()
    except Exception as exc:
        return None, f"lookup_failed: {exc}"
    if not found:
        return None, "not_found_in_delhi"
    return found[0], None


# --- the four steps -------------------------------------------------------------


def locate_place(query: str, use_cache: bool = True, session=None) -> Place:
    """Find one place inside NCT Delhi by name, by whichever of the four steps works.

    Returns a `Place` with `found=False` rather than raising, for anything that goes
    wrong — an unknown name, a place outside the box, a timeout, a server error. The
    agent has to be able to carry on and say it could not find the place.

    The gazetteer is tried before Nominatim because it is free, instant, and not
    subject to how one geocoder happens to index one naming convention. Nominatim is
    then asked twice at most: once with the user's own words plus ", Delhi", and once
    with the normalised form plus ", Delhi". Two requests, not five, because each one
    costs a second of someone else's donated capacity and the second phrasing is the
    one most likely to differ in result (D-073).
    """
    cleaned = " ".join(query.split())
    if not cleaned:
        return Place(query=query, found=False, reason="empty_query", path=PATH_NOT_FOUND)

    key = cache_key(cleaned)
    cache = load_cache() if use_cache else {}
    if key in cache and not is_stale_miss(cache[key]):
        stored = cache[key]
        return Place(
            query=cleaned,
            found=bool(stored.get("found")),
            lat=stored.get("lat"),
            lon=stored.get("lon"),
            display_name=stored.get("display_name"),
            reason=stored.get("reason"),
            path=stored.get("path") or PATH_CACHE,
        )

    place = _locate_uncached(cleaned, session=session)
    cacheable = place.found or (place.reason or "").startswith("not_found")
    if use_cache and cacheable:
        cache[key] = {
            name: value for name, value in place.to_dict().items() if name != "query"
        }
        save_cache(cache)
    return place


def _locate_uncached(cleaned: str, session=None) -> Place:
    """Steps 1 to 4 for a query the cache does not know."""
    normalised = normalise(cleaned)

    station = gazetteer_match(normalised)
    if station is not None:
        return Place(
            query=cleaned,
            found=True,
            lat=station["lat"],
            lon=station["lon"],
            display_name=f"{station['name']} (Delhi Metro)",
            path=PATH_GAZETTEER,
        )

    attempts = [(cleaned + DELHI_SUFFIX, PATH_NOMINATIM_ORIGINAL)]
    if normalised and normalised != cleaned.lower():
        attempts.append((normalised + DELHI_SUFFIX, PATH_NOMINATIM_NORMALISED))

    last_reason = "not_found_in_delhi"
    for text, path in attempts:
        best, reason = ask_nominatim(text, session=session)
        if best is not None:
            return Place(
                query=cleaned,
                found=True,
                lat=float(best["lat"]),
                lon=float(best["lon"]),
                display_name=best.get("display_name"),
                path=path,
            )
        last_reason = reason or last_reason
        if not reason or not reason.startswith("not_found"):
            # a timeout or a 500 says nothing about the name, so stop rather than
            # spend another request on a service that is currently unhappy
            return Place(query=cleaned, found=False, reason=last_reason, path=path)

    return Place(query=cleaned, found=False, reason=last_reason, path=PATH_NOT_FOUND)
