"""What the running process actually loads — the memory trims of D-110.

A 1.75 GB container is the deployment target (D-111), so three things that were
resident for no reason are tested here rather than left to be noticed again:

  - the cross-encoder module, imported by `app/rerank.py` at import time although the
    shipped configuration never reranks (`USE_RERANKER=0`);
  - Chroma's default embedding function, which would load a second ONNX MiniLM beside
    the one fastembed already holds if the collection were ever opened without
    `embedding_function=None`;
  - the river polygon, loaded and indexed at startup for a question only a pipeline
    script asks (that one is in `tests/test_spatial.py`, beside the other layer tests).

The import tests run in a subprocess, because `sys.modules` is process-wide: a test
earlier in the same session that did load one of these modules would otherwise make
this one fail for the wrong reason.
"""

import json
import subprocess
import sys

import pytest

from app.api import peak_rss_mb
from app.indexing import fresh_collection, open_collection

#: What importing `app.api` must not drag in. `fastembed.rerank.cross_encoder` brings
#: `fastembed`, `onnxruntime` and `tokenizers` with it, and the old `app/rerank.py`
#: imported it at module scope, so every process that imported the API paid for all
#: four whether or not reranking was on.
#:
#: Chroma's own `onnx_mini_lm_l6_v2` module is **not** in this list: chromadb imports it
#: itself and nothing we do can stop it. What matters there is that the class is never
#: *instantiated*, which is where the 90 MB model and the onnxruntime session live —
#: `test_a_real_search_never_builds_chromas_own_embedding_model` checks that against the
#: real index, and the two recording-client tests above check the reason it cannot be.
UNWANTED_MODULES = (
    "fastembed.rerank.cross_encoder",
    "onnxruntime",
    "tokenizers",
)


class RecordingClient:
    """Stands in for a Chroma client and keeps the keyword arguments it was given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def get_collection(self, name, **kwargs):
        self.calls.append(("get", kwargs))
        return "collection"

    def create_collection(self, **kwargs):
        self.calls.append(("create", kwargs))
        return "collection"

    def delete_collection(self, name):
        self.calls.append(("delete", {}))


# --- Chroma's default embedding function ----------------------------------------


def test_opening_the_collection_passes_no_embedding_function() -> None:
    """`embedding_function=None` is the whole of the fix, so it is worth pinning.

    Chroma's `get_collection` has `DefaultEmbeddingFunction()` as its **default
    argument**, so leaving the parameter out binds one at import time and would load an
    ONNX MiniLM the first time anything passed documents instead of vectors. ZoneWise
    embeds its own query and passes `query_embeddings`, so the function would never be
    right — only resident.
    """
    client = RecordingClient()
    open_collection(client)
    assert client.calls == [("get", {"embedding_function": None})]


def test_a_rebuilt_collection_passes_no_embedding_function() -> None:
    """The same at index-build time: `scripts/05_build_index.py` embeds the chunks itself."""
    client = RecordingClient()
    fresh_collection(client)
    kinds = [kind for kind, _ in client.calls]
    assert kinds == ["delete", "create"]
    assert client.calls[-1][1]["embedding_function"] is None


# --- what importing the server loads --------------------------------------------


def test_importing_the_server_loads_no_onnx_runtime() -> None:
    """Importing `app.api` must not pull in the reranker, onnxruntime or tokenizers.

    This is the test that would have caught the old `app/rerank.py`, which imported
    `fastembed.rerank.cross_encoder` at module scope — and `app/api.py` imports
    `app.rerank` for `/api/health`, so every server paid for it (D-110). The real
    server does load fastembed a moment later, when the embedding model opens; what
    this pins is that nothing loads it by accident, and that a process which only
    needs the API's shape does not load it at all.
    """
    code = (
        "import sys, json; import app.api; "
        f"print(json.dumps({{name: name in sys.modules for name in {UNWANTED_MODULES!r}}}))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )
    assert done.returncode == 0, done.stderr
    loaded = json.loads(done.stdout.strip().splitlines()[-1])
    assert loaded == {name: False for name in UNWANTED_MODULES}


def test_asking_whether_the_reranker_is_available_does_not_import_it() -> None:
    """`available()` answers with `find_spec`, which locates without executing."""
    code = (
        "import sys, json; import app.rerank as r; "
        "print(json.dumps({'available': r.available(), "
        "'imported': 'fastembed.rerank.cross_encoder' in sys.modules}))"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=300
    )
    assert done.returncode == 0, done.stderr
    answer = json.loads(done.stdout.strip().splitlines()[-1])
    assert answer["available"] is True, "fastembed should offer a cross-encoder"
    assert answer["imported"] is False


@pytest.mark.needs_data
def test_a_real_search_never_builds_chromas_own_embedding_model(monkeypatch) -> None:
    """A full hybrid search against the built index, with the default model booby-trapped.

    `ONNXMiniLM_L6_V2.__init__` is replaced with something that fails, so if Chroma ever
    decided to embed on our behalf — which it would if a collection were opened without
    `embedding_function=None`, or if documents were passed where vectors belong — the
    search would raise instead of quietly loading a second 90 MB ONNX model beside the
    one fastembed already holds.
    """
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    from app.retrieval import get_index, search

    def refuse(self, *args, **kwargs):
        raise AssertionError("Chroma built its own default embedding model")

    monkeypatch.setattr(ONNXMiniLM_L6_V2, "__init__", refuse)
    results = search("maximum ground coverage TOD plot", k=3, index=get_index())
    assert results, "the search should return clauses, not nothing"


# --- peak resident memory -------------------------------------------------------


def test_peak_rss_is_a_number_on_posix_and_nothing_on_windows() -> None:
    """One field, two honest answers. `None` is why `/api/health` omits the key."""
    peak = peak_rss_mb()
    if sys.platform.startswith("win"):
        assert peak is None
    else:
        assert isinstance(peak, float)
        # This test process has loaded pytest and app.api, so anything under a few
        # megabytes would mean the unit conversion is wrong rather than that the
        # process is small.
        assert peak > 5.0


@pytest.mark.skipif(sys.platform.startswith("win"), reason="resource is POSIX-only")
def test_health_carries_the_peak_on_posix() -> None:
    """On the deployment target the number has to be in the health body, not only the log."""
    from fastapi.testclient import TestClient

    from app.api import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()
    assert isinstance(body["peak_rss_mb"], float)


def test_health_omits_the_peak_where_it_cannot_be_measured() -> None:
    """The Windows laptop's own answer: absent, not null (D-110)."""
    from fastapi.testclient import TestClient

    from app.api import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()
    if peak_rss_mb() is None:
        assert "peak_rss_mb" not in body
    else:
        assert body["peak_rss_mb"] == pytest.approx(peak_rss_mb(), rel=0.5)
