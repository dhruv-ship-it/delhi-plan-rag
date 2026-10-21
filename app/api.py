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

Four more endpoints live under `/api/dev/eval/` and serve the question verification
screen. They exist only when `ZONEWISE_DEV=1`: with the flag off every one of them is a
404, because they read and write the evaluation files and have no business being
reachable on a deployed server (D-075).

Every request is size-checked and every response carries a small set of security headers
(D-077), and a validation failure comes back as one readable sentence rather than
pydantic's error list. Nothing here is configured in the file: the rate limits, the
allowed origins, the question length and the body limit all come from `app/config.py`
and therefore from the environment (D-065).
"""

import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.agent import run_agent
from app.answer import answer_point
from app.config import settings
from app.dev_eval import (
    Decision,
    DevEvalError,
    check_leakage,
    question_detail,
    question_list,
    save_decision,
)
from app.llm import LLM, get_llm, is_provider_error, provider_error_line
from app.rerank import available as reranker_available
from app.retrieval import SearchReport, get_index, rank, search
from app.spatial import CORE_LAYERS, get_zones, load_layers

#: What the interface may ask for. The extra layers are downloaded but not exposed,
#: because nothing in the product uses them yet.
SERVABLE_LAYERS = CORE_LAYERS

#: The message the two answering endpoints return when the provider itself failed:
#: rate limited, refusing the request, or down. Short on purpose — a user can only do
#: one thing about it, and the detail belongs in the log (D-100).
PROVIDER_BUSY_MESSAGE = (
    "The AI service is busy or returned an error. Please try again in a minute."
)

#: The message the two answering endpoints return when there is no key.
NO_LLM_MESSAGE = (
    "Answers need an Anthropic API key, which is not configured yet. "
    "Put one in .env as ANTHROPIC_API_KEY=sk-ant-... and restart the server. "
    "Clause search works without a key, and the clauses retrieved for this question "
    "are included below."
)


# --- what comes in and goes out -------------------------------------------------


class DecisionRequest(BaseModel):
    """POST /api/dev/eval/decision. One verification decision from the screen."""

    question: str = Field(default="", max_length=settings.max_question_chars)
    status: str = Field(pattern="^(accepted|edited|rejected|skipped)$")
    expected_chunk_ids: list[str] = Field(default_factory=list, max_length=3)
    acceptable_chunk_ids: list[str] = Field(default_factory=list, max_length=10)
    should_abstain: bool = False
    notes: str = Field(default="", max_length=1000)


class LeakageRequest(BaseModel):
    """POST /api/dev/eval/leakage. A rewritten question to check while typing."""

    question: str = Field(default="", max_length=settings.max_question_chars)


class SearchRequest(BaseModel):
    """POST /api/search."""

    query: str = Field(min_length=1, max_length=settings.max_question_chars)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    k: int = Field(default=settings.default_k, ge=1, le=20)
    mode: str = Field(default="hybrid", pattern="^(dense|bm25|hybrid)$")


class AskRequest(BaseModel):
    """POST /api/ask.

    The latitude and longitude bounds are the valid ranges for the coordinate
    system, not a Delhi bounding box. A point in Gurugram is a legitimate request
    with an honest answer -- `outside_delhi`, no LLM call (D-045) -- and rejecting
    it at the edge would turn a useful reply into a validation error.
    """

    question: str = Field(min_length=1, max_length=settings.max_question_chars)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    k: int = Field(default=settings.default_k, ge=1, le=20)


class AgentRequest(BaseModel):
    """POST /api/agent."""

    question: str = Field(min_length=1, max_length=settings.max_question_chars)


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


def failure_log_payload(question: str, error: Exception) -> dict:
    """The log line for a request that failed, with the exception named in `error`.

    A failed request used to leave no trace at all, so the only record of the agent's
    500s was a screenshot (Phase A). One line, one flattened message, no stack trace
    and no key (D-100).
    """
    return {
        "question": question,
        "abstained": True,
        "abstain_reason": "request_failed",
        "error": provider_error_line(error),
    }


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
        # "" for most questions. Worth a line in the log when it is not, because it
        # says the answer is about a point the question did not quite describe (D-094).
        "location_note": result.location_note,
        # The claim check's own record: the mode, the verdict counts and its cost. In
        # shadow mode this log line is the only place its verdicts are kept (D-096).
        "support_check": result.support_check,
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
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

#: Headers added to every response. Modest on purpose: this is a read-only API and
#: a map, so the headers worth setting are the ones that cost nothing and close a
#: real hole (D-077).
SECURITY_HEADERS = {
    # the browser must not guess that a JSON body is HTML and run it
    "X-Content-Type-Options": "nosniff",
    # nothing here should ever be framed by another site
    "X-Frame-Options": "DENY",
    # a question is in the URL of nothing, but a referrer still leaks the origin
    "Referrer-Policy": "no-referrer",
    # no part of this app needs a camera, a microphone or a location permission
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add the security headers, and refuse a body larger than the configured limit.

    The size check reads `Content-Length` rather than the body itself, so an
    oversized request is refused before it is parsed or read into memory. A client
    that sends no `Content-Length` (a chunked upload) is not refused here: there is
    nothing to check yet, and the field limits on the request models catch it a
    moment later (D-077).
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "detail": {
                    "error": "request_too_large",
                    "message": (
                        f"The request body is {declared} bytes, over the "
                        f"{settings.max_request_bytes} byte limit. A question may be at "
                        f"most {settings.max_question_chars} characters."
                    ),
                }
            },
            headers=SECURITY_HEADERS,
        )
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


@app.exception_handler(RequestValidationError)
async def validation_message(request: Request, exc: RequestValidationError):
    """Turn pydantic's validation report into one sentence a person can act on.

    FastAPI's default 422 body is a list of dicts with `loc`, `type` and `ctx`,
    which is precise and unreadable. The interface shows `detail.message`, so the
    message has to say which field and what the limit is -- and the raw errors are
    still included under `errors` for anyone debugging a client (D-077).
    """
    problems = []
    for error in exc.errors():
        where = ".".join(str(part) for part in error.get("loc", ()) if part != "body")
        problems.append(f"{where or 'request'}: {error.get('msg', 'is not valid')}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error": "invalid_request",
                "message": "; ".join(problems) or "The request could not be read.",
                "errors": jsonable_encoder(exc.errors()),
            }
        },
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
    """What is loaded, and whether answers are possible at all.

    Reports the provider and the model, never a key (D-082).
    """
    index = request.app.state.index
    layers = request.app.state.layers
    return {
        "status": "ok" if index is not None and layers is not None else "degraded",
        "chunks": len(index) if index is not None else 0,
        "layers_loaded": sorted(layers) if layers else [],
        "llm_available": settings.llm_available,
        "provider": settings.llm_provider,
        "model": settings.llm_model if settings.llm_available else None,
        "startup_errors": request.app.state.startup_errors,
        "dev_mode": settings.dev_mode,
        "reranker": {
            "available": reranker_available(),
            "enabled": settings.reranker_on,
            "model": settings.rerank_model if settings.reranker_on else None,
        },
        "abstention": {
            "signal": settings.abstention_signal,
            "threshold": settings.abstain_threshold,
            "provisional": True,
        },
        # The one setting the freeze leaves open, so /api/health is where you check
        # which mode a deployment is actually running (D-096).
        "support_check": settings.support_check,
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


def _provider_failed(endpoint: str, question: str, error: Exception) -> JSONResponse:
    """The 503 for a provider that failed, having logged what went wrong.

    `/api/ask` and `/api/agent` are the only endpoints that call a provider, and a
    provider that is rate limited, refusing the request or down is not a bug in
    ZoneWise: it is a condition the user can retry out of. It gets the same status as
    "no key configured" with its own `error` code, so the interface shows the message
    rather than "Request failed (500)" (D-100).
    """
    log_request(endpoint, failure_log_payload(question, error))
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "error": "provider_error",
                "message": PROVIDER_BUSY_MESSAGE,
                "zones": None,
                "results": [],
            }
        },
    )


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

    try:
        result = answer_point(
            body.question, body.lat, body.lon, k=body.k, llm=llm, index=index
        )
    except Exception as exc:
        if not is_provider_error(exc):
            # Our own bug. Logged like any other failure, then re-raised: a 500 is the
            # honest answer, and calling it "the AI service is busy" would hide it.
            log_request("ask", failure_log_payload(body.question, exc))
            raise
        return _provider_failed("ask", body.question, exc)
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

    try:
        result = run_agent(body.question, llm=llm, index=index)
    except Exception as exc:
        if not is_provider_error(exc):
            log_request("agent", failure_log_payload(body.question, exc))
            raise
        return _provider_failed("agent", body.question, exc)
    log_request("agent", answer_log_payload(body.question, result))
    return result.to_dict()


# --- the question verification screen, dev only ---------------------------------


def require_dev_mode() -> None:
    """404 unless ZONEWISE_DEV=1.

    A 404 rather than a 403, because a 403 confirms the endpoint exists. With the
    flag off these routes should be indistinguishable from paths that were never
    written, which is also what the frontend keys off: it asks /api/health whether
    dev mode is on and only then shows the Verify tab (D-075).
    """
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail={"error": "not_found"})


@app.get("/api/dev/eval/questions")
def dev_questions(_: None = Depends(require_dev_mode)) -> dict:
    """Every drafted question with its verification status, and the progress count."""
    return question_list()


@app.get("/api/dev/eval/questions/{question_id}")
def dev_question(
    question_id: str,
    index=Depends(require_index),
    _: None = Depends(require_dev_mode),
) -> dict:
    """One question: its point, its expected chunks in full, and the current top 5."""
    try:
        return question_detail(question_id, index)
    except DevEvalError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "unknown_question", "message": str(exc)}
        ) from exc


@app.post("/api/dev/eval/questions/{question_id}/leakage")
def dev_leakage(
    question_id: str,
    body: LeakageRequest,
    index=Depends(require_index),
    _: None = Depends(require_dev_mode),
) -> dict:
    """The 4-consecutive-word leakage check on a rewritten question (D-055)."""
    try:
        return check_leakage(question_id, body.question, index)
    except DevEvalError as exc:
        raise HTTPException(
            status_code=404, detail={"error": "unknown_question", "message": str(exc)}
        ) from exc


@app.post("/api/dev/eval/questions/{question_id}/decision")
def dev_decision(
    question_id: str,
    body: DecisionRequest,
    index=Depends(require_index),
    _: None = Depends(require_dev_mode),
) -> dict:
    """Save a decision into eval/questions_verified.jsonl, by id.

    A 422 for a decision that breaks one of the guards — a question quoting its own
    answer, a should-abstain question with expected chunks — with the reason in
    words, because the person typing is the one who has to fix it.
    """
    decision = Decision(
        id=question_id,
        status=body.status,
        question=body.question,
        expected_chunk_ids=list(body.expected_chunk_ids),
        acceptable_chunk_ids=list(body.acceptable_chunk_ids),
        should_abstain=body.should_abstain,
        notes=body.notes,
    )
    try:
        return save_decision(decision, index)
    except DevEvalError as exc:
        raise HTTPException(
            status_code=422, detail={"error": "bad_decision", "message": str(exc)}
        ) from exc


# --- the built frontend ---------------------------------------------------------

if settings.web_dist_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(settings.web_dist_dir), html=True),
        name="web",
    )
