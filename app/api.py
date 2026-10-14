"""The HTTP interface: the map, the search and the answers, behind one FastAPI app.

Everything expensive is loaded once when the server starts and reused for every request:
the embedding model, the Chroma collection, the BM25 corpus and the eight GeoJSON map
layers. Loading them per request would make a search take seconds instead of
milliseconds, and the simplified map layers are cached in memory for the same reason.

The endpoints, and which of them need an API key:

  GET  /api/health             no key    what is loaded, and whether answers are possible
  GET  /api/zones             no key    which planning zones contain a point
  GET  /api/layers/{name}     no key    a simplified map layer for the browser
  POST /api/search            no key    retrieval results
  GET  /api/chunks/{id}       no key    one clause in full, for clicking a citation
  POST /api/ask               KEY       a cited answer about a point
  POST /api/agent             KEY       a cited answer about a place named in the question

That split is deliberate: without a key the app is a working clause search over Delhi
planning law with a map, and the two endpoints that need one return 503 **with the
retrieval results included**, so the interface can still show the user the clauses it
found and say that answers need a key (see D-050).
"""

import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import run_agent
from app.answer import answer_point
from app.config import settings
from app.llm import LLM, get_llm
from app.retrieval import SearchReport, get_index, rank, search
from app.spatial import CORE_LAYERS, get_zones, load_layers

#: What the interface may ask for. The extra layers are downloaded but not exposed,
#: because nothing in the product uses them yet.
SERVABLE_LAYERS = CORE_LAYERS

#: The message the two answering endpoints return when there is no key.
NO_LLM_MESSAGE = (
    "Answers need an Anthropic API key, which is not configured yet. "
    "Put one in .env as ANTHROPIC_API_KEY=sk-ant-... and restart the server. "
    "Clause search works without a key, and the clauses retrieved for this question "
    "are included below."
)


# --- what comes in and goes out -------------------------------------------------


class SearchRequest(BaseModel):
    """POST /api/search."""

    query: str = Field(min_length=1, max_length=1000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    k: int = Field(default=settings.default_k, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(dense|bm25|hybrid)$")


class AskRequest(BaseModel):
    """POST /api/ask."""

    question: str = Field(min_length=1, max_length=1000)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    k: int = Field(default=settings.default_k, ge=1, le=20)


class AgentRequest(BaseModel):
    """POST /api/agent."""

    question: str = Field(min_length=1, max_length=1000)


# --- rate limiting --------------------------------------------------------------


class RateLimiter:
    """Per-IP requests a minute, plus one cap for the whole service per day.

    In memory, which is the right size for this: one process, one laptop, no users to
    speak of. The per-IP limit stops one browser tab looping; the daily cap is the one
    that matters, because it is what stands between a bug and an API bill (D-051).
    """

    def __init__(self, per_minute: int, per_day: int) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self._recent: dict[str, deque[float]] = defaultdict(deque)
        self._day = date.today()
        self._today = 0

    def reset(self) -> None:
        """Forget everything. Used between tests."""
        self._recent.clear()
        self._day = date.today()
        self._today = 0

    def check(self, client: str) -> str | None:
        """None when the request may proceed, otherwise why it may not."""
        if date.today() != self._day:
            self._day = date.today()
            self._today = 0

        if self._today >= self.per_day:
            return (
                f"ZoneWise has answered its daily limit of {self.per_day} questions. "
                "This cap keeps a student project's API bill predictable. Try again "
                "tomorrow, or raise rate_limit_per_day in app/config.py."
            )

        now = time.monotonic()
        seen = self._recent[client]
        while seen and now - seen[0] > 60:
            seen.popleft()
        if len(seen) >= self.per_minute:
            return (
                f"That is more than {self.per_minute} questions in a minute from one "
                "address. Please wait a moment and try again."
            )

        seen.append(now)
        self._today += 1
        return None


limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day)


def client_address(request: Request) -> str:
    """The caller's address, for rate limiting. Unknown callers share one bucket."""
    return request.client.host if request.client else "unknown"


# --- request logging ------------------------------------------------------------


def log_request(endpoint: str, payload: dict) -> None:
    """Append one line to data/logs/requests.jsonl.

    The question, the zones, which clauses came back and whether we answered. No API
    key is ever in scope here, and nothing reads the settings object (D-052). A logging
    failure must never fail a request, so every error is swallowed.
    """
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "endpoint": endpoint, **payload}
    try:
        path = settings.requests_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def answer_log_payload(question: str, result: Any) -> dict:
    """The fields of an answer worth keeping in the log."""
    return {
        "question": question,
        "zones": result.zones,
        "chunk_ids": [item["chunk_id"] for item in result.retrieval],
        "abstained": result.abstained,
        "abstain_reason": result.abstain_reason,
        "llm_calls": result.llm_calls,
        "latency_ms": result.latency_ms,
    }


# --- startup --------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the indexes, the layers and the embedding model once, before serving.

    A failure is recorded rather than raised, so the server still starts and
    /api/health can say what is wrong. A server that refuses to boot tells the user
    nothing; one that boots and reports "no index, run scripts/05_build_index.py" tells
    them exactly what to do.
    """
    app.state.index = None
    app.state.layers = None
    app.state.startup_errors = []
    app.state.layer_cache = {}

    try:
        app.state.index = get_index()
    except Exception as exc:
        app.state.startup_errors.append(
            f"search index not loaded ({exc}); run: uv run python scripts/05_build_index.py"
        )
    try:
        app.state.layers = load_layers()
    except Exception as exc:
        app.state.startup_errors.append(
            f"map layers not loaded ({exc}); run: uv run python scripts/06_fetch_layers.py"
        )
    yield


app = FastAPI(
    title="ZoneWise",
    description="Location-aware question answering over the Master Plan for Delhi 2047.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def require_index(request: Request):
    """The loaded SearchIndex, or a 503 saying how to build it."""
    index = request.app.state.index
    if index is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_index",
                "message": "The search index is not loaded.",
                "startup_errors": request.app.state.startup_errors,
            },
        )
    return index


def llm_provider() -> LLM | None:
    """The client to answer with, or None when no key is configured.

    A FastAPI dependency so tests can override it with a scripted FakeLLM. It returns
    None rather than raising, because the endpoint has to retrieve the clauses first
    and send them back with the 503.
    """
    if not settings.llm_available:
        return None
    try:
        return get_llm()
    except Exception:
        return None


# --- endpoints ------------------------------------------------------------------


@app.get("/api/health")
def health(request: Request) -> dict:
    """What is loaded, and whether answers are possible at all."""
    index = request.app.state.index
    layers = request.app.state.layers
    return {
        "status": "ok" if index is not None and layers is not None else "degraded",
        "chunks": len(index) if index is not None else 0,
        "layers_loaded": sorted(layers) if layers else [],
        "llm_available": settings.llm_available,
        "model": settings.llm_model if settings.llm_available else None,
        "startup_errors": request.app.state.startup_errors,
    }


@app.get("/api/zones")
def zones(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
) -> dict:
    """Which planning zones contain a point."""
    try:
        return get_zones(lat, lon)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "no_layers", "message": str(exc)},
        ) from exc


@app.get("/api/layers/{name}")
def layer(name: str, request: Request) -> dict:
    """One map layer as simplified GeoJSON, cached in memory after the first call.

    The raw layers are 4.8 MB of coordinates, which a browser does not need to draw the
    shape of a zone. Simplifying costs a second once and saves it on every page load.
    """
    if name not in SERVABLE_LAYERS:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_layer",
                "message": f"No layer named {name!r}.",
                "available": list(SERVABLE_LAYERS),
            },
        )
    cache = request.app.state.layer_cache
    if name in cache:
        return cache[name]

    layers = request.app.state.layers
    if layers is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_layers",
                "message": "Map layers are not loaded.",
                "startup_errors": request.app.state.startup_errors,
            },
        )

    loaded = layers[name]
    features = []
    for geometry, properties in zip(loaded.geometries, loaded.properties):
        simple = geometry.simplify(settings.layer_simplify_tolerance, preserve_topology=True)
        if simple.is_empty:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(json.dumps(simple.__geo_interface__)),
                "properties": {
                    key: properties.get(key)
                    for key in ("zone_name", "zone", "id", "area", "type")
                    if properties.get(key) is not None
                },
            }
        )
    collection = {"type": "FeatureCollection", "name": name, "features": features}
    cache[name] = collection
    return collection


@app.get("/api/chunks/{chunk_id:path}")
def chunk(chunk_id: str, index=Depends(require_index)) -> dict:
    """One clause in full, with its metadata. This is what a citation chip opens."""
    found = index.chunks.get(chunk_id)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_chunk", "message": f"No chunk with id {chunk_id!r}."},
        )
    return found


@app.post("/api/search")
def search_endpoint(body: SearchRequest, index=Depends(require_index)) -> dict:
    """Retrieval results. Works with no API key, which is the point."""
    zones_found = None
    if body.lat is not None and body.lon is not None:
        try:
            zones_found = get_zones(body.lat, body.lon)
        except Exception:
            zones_found = None

    report = SearchReport(query=body.query, expanded_query=body.query)
    if zones_found:
        results = search(
            body.query, k=body.k, mode=body.mode, zones=zones_found, index=index, report=report
        )
    else:
        results = rank(body.query, k=body.k, mode=body.mode, index=index, report=report)

    log_request(
        "search",
        {
            "question": body.query,
            "zones": zones_found,
            "chunk_ids": [result.chunk_id for result in results],
            "mode": body.mode,
        },
    )
    return {
        "query": body.query,
        "mode": body.mode,
        "zones": zones_found,
        "expanded_query": report.expanded_query,
        "excluded": report.excluded,
        "boosted": report.boosted,
        "results": [result.to_dict() for result in results],
    }


def _rate_limited(request: Request) -> JSONResponse | None:
    """A 429 response when the caller has had enough, otherwise None."""
    reason = limiter.check(client_address(request))
    if reason is None:
        return None
    return JSONResponse(
        status_code=429,
        content={"detail": {"error": "rate_limited", "message": reason}},
    )


@app.post("/api/ask")
def ask(
    body: AskRequest,
    request: Request,
    index=Depends(require_index),
    llm: LLM | None = Depends(llm_provider),
):
    """A cited answer about one point, or an honest refusal. Needs a key."""
    limited = _rate_limited(request)
    if limited is not None:
        return limited

    if llm is None:
        report = SearchReport(query=body.question, expanded_query=body.question)
        zones_found = get_zones(body.lat, body.lon)
        results = (
            search(
                body.question,
                k=body.k,
                mode="hybrid",
                zones=zones_found,
                index=index,
                report=report,
            )
            if zones_found.get("inside_delhi")
            else []
        )
        log_request(
            "ask",
            {
                "question": body.question,
                "zones": zones_found,
                "chunk_ids": [result.chunk_id for result in results],
                "abstained": True,
                "abstain_reason": "no_llm",
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "error": "no_llm",
                    "message": NO_LLM_MESSAGE,
                    "zones": zones_found,
                    "results": [result.to_dict() for result in results],
                }
            },
        )

    result = answer_point(body.question, body.lat, body.lon, k=body.k, llm=llm, index=index)
    log_request("ask", answer_log_payload(body.question, result))
    return result.to_dict()


@app.post("/api/agent")
def agent(
    body: AgentRequest,
    request: Request,
    index=Depends(require_index),
    llm: LLM | None = Depends(llm_provider),
):
    """A cited answer about a place named in the question. Needs a key."""
    limited = _rate_limited(request)
    if limited is not None:
        return limited

    if llm is None:
        log_request(
            "agent",
            {
                "question": body.question,
                "zones": None,
                "chunk_ids": [],
                "abstained": True,
                "abstain_reason": "no_llm",
            },
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "error": "no_llm",
                    "message": NO_LLM_MESSAGE,
                    "zones": None,
                    "results": [],
                }
            },
        )

    result = run_agent(body.question, llm=llm, index=index)
    log_request("agent", answer_log_payload(body.question, result))
    return result.to_dict()


# --- the built frontend ---------------------------------------------------------

if settings.web_dist_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.web_dist_dir), html=True),
        name="web",
    )
