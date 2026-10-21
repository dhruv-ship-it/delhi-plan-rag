"""Re-score the top results with a cross-encoder, when one is available and turned on.

The two indexes in `app/retrieval.py` are both **bi-encoders** in the loose sense: the
query and the chunk are turned into numbers separately and then compared. That is what
makes them fast enough to search the whole corpus — the chunk vectors are computed once, at
index time — and it is also their limit, because the chunk's vector was computed without
knowing the question. "What is the maximum ground coverage?" and "What is the minimum
ground coverage?" have nearly the same embedding, and BM25 sees the same tokens.

A **cross-encoder** reads the query and the chunk together, as one input, and returns one
relevance score. It cannot be precomputed, so it cannot search a corpus — 653 chunks
would be 653 forward passes per query. It can rescore a shortlist, which is what this
module does: fusion picks the top 20, the cross-encoder reorders them, and the top k of
that is returned.

Two things about it are deliberate:

**It is off by default** (`settings.use_reranker`). Measured on this laptop's CPU it
costs **2.4 s a query against 0.031 s without it** — reranking 20 chunks is about 77
times the cost of the entire search that produced them, because 20 cross-encoder
forward passes over 400-word chunks is simply more arithmetic than one query embedding
and a BM25 scan. There is no verified question set yet to say whether it earns that, so
`eval/run_eval.py` scores `hybrid+location+rerank` as a fourth configuration and the
answer gets measured rather than assumed (D-070).

**Its score is a better abstention signal than the fused score.** An RRF score only says
where a chunk sat in two rank orders, so the best chunk for an off-topic question scores
exactly what the best chunk for a good question scores. A cross-encoder score is an
absolute judgement about this query and this chunk, which is the kind of number a
threshold can be set on (D-071).

`available()` is checked rather than assumed, because `fastembed.rerank.cross_encoder`
arrived in a later fastembed than the one this project pinned first. It is now asked
**without importing that module**: `find_spec` says whether it is installed, and the
import — which brings in the cross-encoder machinery and its own onnxruntime session
factory — happens only when something actually reranks, which with `USE_RERANKER=0` is
never. See D-110.
"""

from functools import lru_cache
from importlib.util import find_spec

from app.config import settings

#: The module the cross-encoder lives in. Named once, because three functions ask about
#: it and one of them must not import it.
CROSS_ENCODER_MODULE = "fastembed.rerank.cross_encoder"

#: Set when importing the cross-encoder module was tried and failed, so a health check
#: can say what went wrong rather than only that it is off.
_IMPORT_ERROR: str | None = None


@lru_cache(maxsize=1)
def available() -> bool:
    """True when the installed fastembed can build a cross-encoder.

    Answered with `find_spec`, which locates the module without executing it. The old
    version imported it at module import time, so every process that touched
    `app/rerank.py` — including `app/api.py`, which imports it for `/api/health` —
    paid for the cross-encoder machinery whether or not it was turned on (D-110).
    `fastembed.rerank` has no `__init__.py`, so locating the leaf costs the parent
    package only, and that is loaded anyway by the embedding model.
    """
    try:
        return find_spec(CROSS_ENCODER_MODULE) is not None
    except (ImportError, ValueError):  # pragma: no cover - a broken fastembed install
        return False


def _cross_encoder_class():
    """`TextCrossEncoder`, imported on first use, or None when it cannot be imported."""
    global _IMPORT_ERROR
    try:  # fastembed 0.7 and later
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except Exception as exc:  # pragma: no cover - depends on the installed version
        _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return None
    return TextCrossEncoder


def unavailable_reason() -> str:
    """Why the reranker cannot be used, for a report or a health check."""
    if available():
        return _IMPORT_ERROR or ""
    return _IMPORT_ERROR or f"{CROSS_ENCODER_MODULE} is not installed"


def supported_models() -> list[dict]:
    """Every cross-encoder the installed fastembed offers, with its size."""
    encoder = _cross_encoder_class()
    if encoder is None:
        return []
    return list(encoder.list_supported_models())


@lru_cache(maxsize=1)
def reranker():
    """The cross-encoder, loaded once and kept.

    Weights go to `data/index/models`, the same cache as the embedding model, so a
    container image carries them and the first request does not download 80 MB.
    """
    encoder = _cross_encoder_class()
    if encoder is None:
        raise RuntimeError(f"the reranker is not available: {unavailable_reason()}")
    settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
    return encoder(
        model_name=settings.rerank_model, cache_dir=str(settings.model_cache_dir)
    )


def rerank_scores(query: str, documents: list[str]) -> list[float]:
    """One relevance score per document, in the order the documents were given."""
    if not documents:
        return []
    return [float(score) for score in reranker().rerank(query, documents)]
