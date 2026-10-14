"""Turn a place name into coordinates, so a user can ask "near Dwarka Sector 21" instead of clicking.

The map interface gives ZoneWise a point. The agent (app/agent.py) does not have one: it
is given plain text like "near Dwarka Sector 21 metro station" and has to find the point
itself before anything else can happen. This module is that step, and it is the only
place in the project that talks to a service other than Anthropic.

It uses Nominatim, OpenStreetMap's free geocoder, under the terms Nominatim asks for:
one request a second at most, an honest User-Agent naming the project, and results
cached so the same place is never looked up twice. The search is bounded to a box around
NCT Delhi, so "Mumbai Central" comes back as not found rather than as a point 1,200 km
away that `get_zones` would then report as outside Delhi.
"""

import json
import threading
import time
from dataclasses import dataclass

import requests

from app.config import settings

#: A box around NCT Delhi: left, top, right, bottom in longitude/latitude.
#: Delhi runs about 76.84 to 77.35 east and 28.40 to 28.89 north; this is a little wider
#: so a place on the boundary is still found.
DELHI_VIEWBOX = (76.80, 28.92, 77.40, 28.36)

#: Nominatim is asked to stay inside the box (bounded=1) and inside India.
COUNTRY_CODES = "in"


@dataclass(frozen=True)
class Place:
    """One geocoding result, or a miss."""

    query: str
    found: bool
    lat: float | None = None
    lon: float | None = None
    display_name: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        """The result as plain JSON, which is what the agent's tool returns."""
        if not self.found:
            return {"query": self.query, "found": False, "reason": self.reason or "not_found"}
        return {
            "query": self.query,
            "found": True,
            "lat": self.lat,
            "lon": self.lon,
            "display_name": self.display_name,
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


def locate_place(query: str, use_cache: bool = True, session=None) -> Place:
    """Find one place inside NCT Delhi by name.

    Returns a `Place` with `found=False` rather than raising, for anything that goes
    wrong — an unknown name, a place outside the box, a timeout, a server error. The
    agent has to be able to carry on and say it could not find the place.
    """
    cleaned = " ".join(query.split())
    if not cleaned:
        return Place(query=query, found=False, reason="empty_query")

    key = cache_key(cleaned)
    cache = load_cache() if use_cache else {}
    if key in cache:
        stored = cache[key]
        return Place(
            query=cleaned,
            found=bool(stored.get("found")),
            lat=stored.get("lat"),
            lon=stored.get("lon"),
            display_name=stored.get("display_name"),
            reason=stored.get("reason"),
        )

    left, top, right, bottom = DELHI_VIEWBOX
    params = {
        "q": cleaned,
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
        # not cached: a network failure now says nothing about the name
        return Place(query=cleaned, found=False, reason=f"lookup_failed: {exc}")

    if not found:
        place = Place(query=cleaned, found=False, reason="not_found_in_delhi")
    else:
        best = found[0]
        place = Place(
            query=cleaned,
            found=True,
            lat=float(best["lat"]),
            lon=float(best["lon"]),
            display_name=best.get("display_name"),
        )

    if use_cache:
        cache[key] = {
            key_name: value
            for key_name, value in place.to_dict().items()
            if key_name != "query"
        }
        save_cache(cache)
    return place
