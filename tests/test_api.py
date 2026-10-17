"""Tests for app/api.py: every endpoint, the 503 path, the 429 path and a 404.

The app is started once per module with TestClient, which runs the real lifespan, so
these tests exercise the real index and the real map layers. The only thing replaced is
the LLM: `llm_provider` is overridden with a scripted FakeLLM, so the two answering
endpoints are tested without a key and without a network call.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.api import app, limiter, llm_provider
from app.config import settings
from app.llm import FakeLLM, tool_use_response

RAJIV_CHOWK = (28.6328, 77.2197)
GURUGRAM = (28.4950, 77.0890)


@pytest.fixture(scope="module")
def client():
    """One app, started once: the lifespan loads the index, the layers and the model."""
    with TestClient(app) as started:
        yield started


@pytest.fixture(autouse=True)
def clean_limits():
    """Every test starts with a fresh rate limiter and no LLM override."""
    limiter.reset()
    app.dependency_overrides.pop(llm_provider, None)
    yield
    limiter.reset()
    app.dependency_overrides.pop(llm_provider, None)


def use_llm(responses: list) -> FakeLLM:
    """Make the answering endpoints use a scripted FakeLLM for this test."""
    fake = FakeLLM(responses=responses)
    app.dependency_overrides[llm_provider] = lambda: fake
    return fake


# --- health ---------------------------------------------------------------------


def test_health_reports_what_is_loaded(client) -> None:
    """The first thing to check when something is wrong.

    The chunk count is asserted as "some chunks", not as a number. A test that pins
    702 goes red on every intentional change to the cleaning rules without saying what
    broke, which is the trap D-036 is about — and this one did exactly that the first
    time the chunking rules changed (D-066).
    """
    body = client.get("/api/health").json()
    assert body["status"] == "ok", body["startup_errors"]
    assert body["chunks"] > 0
    assert "planning_zones" in body["layers_loaded"]
    assert body["startup_errors"] == []


def test_health_says_answers_are_unavailable_without_a_key(client) -> None:
    """`.env` holds a placeholder tonight, so this is the honest answer (D-040)."""
    body = client.get("/api/health").json()
    assert body["llm_available"] is settings.llm_available
    if not settings.llm_available:
        assert body["model"] is None


# --- zones ----------------------------------------------------------------------


def test_zones_for_a_point_in_a_tod_zone(client) -> None:
    lat, lon = RAJIV_CHOWK
    body = client.get("/api/zones", params={"lat": lat, "lon": lon}).json()
    assert body["inside_delhi"] is True
    assert body["planning_zone"] == "D"
    assert body["tod"] is True


def test_zones_outside_delhi_says_only_that(client) -> None:
    lat, lon = GURUGRAM
    assert client.get("/api/zones", params={"lat": lat, "lon": lon}).json() == {
        "inside_delhi": False
    }


def test_zones_rejects_impossible_coordinates(client) -> None:
    """Pydantic validation, so a typo is a 422 rather than a confusing answer."""
    assert client.get("/api/zones", params={"lat": 999, "lon": 77}).status_code == 422
    assert client.get("/api/zones", params={"lat": 28.6}).status_code == 422


# --- layers ---------------------------------------------------------------------


def test_each_core_layer_is_served_as_geojson(client) -> None:
    for name in ("nctd_boundary", "planning_zones", "tod_zone", "high_density_corridor",
                 "land_pooling_area"):
        body = client.get(f"/api/layers/{name}").json()
        assert body["type"] == "FeatureCollection"
        assert body["name"] == name
        assert body["features"], name
        assert body["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_the_planning_zones_layer_carries_its_zone_names(client) -> None:
    """The map labels each zone, so the property has to survive simplification."""
    body = client.get("/api/layers/planning_zones").json()
    names = {feature["properties"].get("zone_name") for feature in body["features"]}
    assert "D" in names and "O" in names
    assert len(body["features"]) == 16  # DDA ships 16, not the 17 the plan lists (D-039)


def test_a_layer_is_simplified_before_it_is_sent(client) -> None:
    """The raw layers are 4.8 MB; the browser gets much less."""
    body = client.get("/api/layers/planning_zones").json()
    assert len(json.dumps(body)) < 1_500_000


def test_an_unknown_layer_is_a_404_that_lists_the_real_ones(client) -> None:
    response = client.get("/api/layers/atlantis")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["error"] == "unknown_layer"
    assert "planning_zones" in detail["available"]


def test_the_policy_layers_are_served(client) -> None:
    """The regional park and low density area layers back the ridge and lda topics."""
    for name in ("regional_park", "low_density_area"):
        body = client.get(f"/api/layers/{name}").json()
        assert body["type"] == "FeatureCollection"
        assert body["features"]


def test_the_river_layer_is_not_exposed(client) -> None:
    """Downloaded and loaded, but no policy is wired to it, so it is not served (D-030).

    The river polygon exists to keep the zone O test point out of the water, which is
    a job for `scripts/07_test_points.py` and not for the browser.
    """
    assert client.get("/api/layers/yamuna_river").status_code == 404


# --- search ---------------------------------------------------------------------


def test_search_works_with_no_api_key(client) -> None:
    """The whole point of the no-key split: this is a useful product already."""
    body = client.post(
        "/api/search", json={"query": "minimum plot size for a TOD project", "k": 5}
    ).json()
    assert len(body["results"]) == 5
    assert body["zones"] is None
    first = body["results"][0]
    assert first["chunk_id"] and first["text"]
    assert first["fused_score"] > 0


def test_search_with_a_point_becomes_location_aware(client) -> None:
    """Passing coordinates turns on exclusion, boosting and query expansion."""
    lat, lon = RAJIV_CHOWK
    body = client.post(
        "/api/search",
        json={"query": "What is the maximum ground coverage allowed?", "lat": lat, "lon": lon},
    ).json()
    assert body["zones"]["tod"] is True
    assert "transit oriented development" in body["expanded_query"]
    assert body["excluded"] > 0
    assert any(result["boosted"] for result in body["results"])


def test_search_modes_are_restricted(client) -> None:
    assert client.post("/api/search", json={"query": "x", "mode": "dense"}).status_code == 200
    assert client.post("/api/search", json={"query": "x", "mode": "magic"}).status_code == 422
    assert client.post("/api/search", json={"query": ""}).status_code == 422


# --- chunks ---------------------------------------------------------------------


def test_a_chunk_can_be_fetched_by_id(client) -> None:
    """This is what clicking a citation chip opens."""
    body = client.get("/api/chunks/MPD47_GAZETTE_EN:4.2.1:0").json()
    assert body["clause_id"] == "4.2.1"
    assert body["doc_title"].startswith("Master Plan for Delhi 2047")
    assert body["page_start"] == 750
    assert "TOD Zone" in body["text"]
    assert body["source_url"].startswith("https://")


def test_a_chunk_id_with_an_at_sign_still_resolves(client) -> None:
    """Ids carry @ and : after the collision fix (D-021), so the route must allow them."""
    body = client.get("/api/chunks/MPD47_FAQ:Q13@p13:0").json()
    assert body["doc_id"] == "MPD47_FAQ"
    assert body["clause_id"] == "Q13"


def test_an_unknown_chunk_id_is_a_404(client) -> None:
    response = client.get("/api/chunks/NOT_A_REAL_CHUNK:9.9:0")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "unknown_chunk"


# --- ask, with a key ------------------------------------------------------------

GOOD_ANSWER_TEMPLATE = "Ground coverage on a TOD plot is capped at 40% [C1]. Check DDA documents [C1]."


def test_ask_returns_a_cited_answer(client) -> None:
    fake = use_llm([GOOD_ANSWER_TEMPLATE])
    lat, lon = RAJIV_CHOWK
    body = client.post(
        "/api/ask",
        json={"question": "How much of my plot can be built on?", "lat": lat, "lon": lon},
    ).json()

    assert body["abstained"] is False
    assert body["answer_markdown"] == GOOD_ANSWER_TEMPLATE
    assert body["citations"][0]["marker"] == "C1"
    assert body["citations"][0]["chunk_id"]
    assert body["zones"]["tod"] is True
    assert body["llm_calls"] == 1
    assert fake.call_count == 1


def test_ask_outside_delhi_abstains_without_calling_the_model(client) -> None:
    fake = use_llm([])  # any call would raise ScriptExhausted
    lat, lon = GURUGRAM
    body = client.post(
        "/api/ask", json={"question": "What can I build?", "lat": lat, "lon": lon}
    ).json()

    assert body["abstained"] is True
    assert body["abstain_reason"] == "outside_delhi"
    assert body["answer_markdown"] is None
    assert fake.call_count == 0


def test_ask_passes_the_model_abstention_through(client) -> None:
    use_llm(["ABSTAIN: the clauses do not cover rent control"])
    lat, lon = RAJIV_CHOWK
    body = client.post(
        "/api/ask", json={"question": "What are the rent control rules?", "lat": lat, "lon": lon}
    ).json()
    assert body["abstained"] is True
    assert body["abstain_reason"].startswith("model_abstained")
    assert "rent control" in body["abstain_reason"]


def test_ask_validates_its_input(client) -> None:
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422
    assert (
        client.post("/api/ask", json={"question": "x", "lat": 999, "lon": 77}).status_code == 422
    )


# --- ask, without a key ---------------------------------------------------------


def test_ask_without_a_key_is_a_503_that_still_carries_the_clauses(client) -> None:
    """Search-only mode: the interface can show what it found and say why (D-050)."""
    app.dependency_overrides[llm_provider] = lambda: None
    lat, lon = RAJIV_CHOWK
    response = client.post(
        "/api/ask",
        json={"question": "How much of my plot can be built on?", "lat": lat, "lon": lon},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "no_llm"
    assert "ANTHROPIC_API_KEY" in detail["message"]
    assert detail["zones"]["tod"] is True
    assert detail["results"], "the clauses are included so the UI stays useful"
    assert detail["results"][0]["chunk_id"]


def test_ask_without_a_key_outside_delhi_returns_no_clauses(client) -> None:
    """Nothing to retrieve for a point MPD-2047 does not cover."""
    app.dependency_overrides[llm_provider] = lambda: None
    lat, lon = GURUGRAM
    detail = client.post(
        "/api/ask", json={"question": "What can I build?", "lat": lat, "lon": lon}
    ).json()["detail"]
    assert detail["zones"] == {"inside_delhi": False}
    assert detail["results"] == []


def test_agent_without_a_key_is_a_503(client) -> None:
    app.dependency_overrides[llm_provider] = lambda: None
    response = client.post("/api/agent", json={"question": "rules near Connaught Place?"})
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "no_llm"


# --- agent, with a key ----------------------------------------------------------


def test_agent_runs_its_tools_and_returns_a_trace(client) -> None:
    """A full tool conversation through HTTP, with the geocoder cache warm."""
    chunk_id = "MPD47_GAZETTE_EN:4.2.3@p753:0"
    use_llm(
        [
            tool_use_response("locate_place", {"query": "Connaught Place"}, "t1"),
            tool_use_response("get_zones", {"lat": 28.6317695, "lon": 77.2193804}, "t2"),
            tool_use_response(
                "search_clauses",
                {"query": "maximum ground coverage TOD", "lat": 28.6317695, "lon": 77.2193804},
                "t3",
            ),
            f"Ground coverage there is capped at 40% [{chunk_id}].",
        ]
    )
    body = client.post(
        "/api/agent", json={"question": "What ground coverage near Connaught Place?"}
    ).json()

    assert body["abstained"] is False
    assert [step["tool"] for step in body["tool_trace"]] == [
        "locate_place",
        "get_zones",
        "search_clauses",
    ]
    assert body["citations"][0]["chunk_id"] == chunk_id
    assert body["zones"]["planning_zone"] == "D"


# --- rate limiting --------------------------------------------------------------


def test_the_per_minute_limit_returns_a_friendly_429(client) -> None:
    """Ten in a minute from one address is enough (D-051)."""
    lat, lon = RAJIV_CHOWK
    use_llm([GOOD_ANSWER_TEMPLATE] * settings.rate_limit_per_minute)
    payload = {"question": "How much can I build?", "lat": lat, "lon": lon}

    for number in range(settings.rate_limit_per_minute):
        assert client.post("/api/ask", json=payload).status_code == 200, number

    response = client.post("/api/ask", json=payload)
    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["error"] == "rate_limited"
    assert "minute" in detail["message"]


def test_the_daily_cap_returns_a_429_explaining_itself(client) -> None:
    """The cap that actually protects the bill."""
    limiter.reset()
    limiter._today = settings.rate_limit_per_day
    use_llm([])
    lat, lon = RAJIV_CHOWK
    response = client.post(
        "/api/ask", json={"question": "How much can I build?", "lat": lat, "lon": lon}
    )
    assert response.status_code == 429
    assert "daily limit" in response.json()["detail"]["message"]


def test_the_limit_is_per_address(client) -> None:
    """One noisy client must not lock everyone else out of the per-minute budget."""
    limiter.reset()
    for number in range(settings.rate_limit_per_minute):
        assert limiter.check("10.0.0.1") is None, number
    assert limiter.check("10.0.0.1") is not None
    assert limiter.check("10.0.0.2") is None


def test_search_is_not_rate_limited(client) -> None:
    """Searching costs us nothing, so it is not capped."""
    limiter.reset()
    limiter._today = settings.rate_limit_per_day
    assert client.post("/api/search", json={"query": "TOD plot size"}).status_code == 200


# --- logging --------------------------------------------------------------------


def test_requests_are_logged_with_the_fields_that_matter(client) -> None:
    """One JSONL line per request, and never anything secret (D-052)."""
    path = settings.requests_log_path
    before = path.read_text(encoding="utf-8").count("\n") if path.exists() else 0

    use_llm([GOOD_ANSWER_TEMPLATE])
    lat, lon = RAJIV_CHOWK
    client.post("/api/ask", json={"question": "logging check", "lat": lat, "lon": lon})

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > before
    record = json.loads(lines[-1])
    assert record["endpoint"] == "ask"
    assert record["question"] == "logging check"
    assert record["chunk_ids"]
    assert record["abstained"] is False
    assert record["zones"]["tod"] is True
    assert "time" in record and "latency_ms" in record
    assert "key" not in json.dumps(record).lower()
