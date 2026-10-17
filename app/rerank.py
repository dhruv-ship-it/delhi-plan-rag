"""Re-score the top results with a cross-encoder, when one is available and turned on.

The two indexes in `app/retrieval.py` are both **bi-encoders** in the loose sense: the
query and the chunk are turned into numbers separately and then compared. That is what
makes them fast enough to search 700 chunks — the chunk vectors are computed once, at
index time — and it is also their limit, because the chunk's vector was computed without
knowing the question. "What is the maximum ground coverage?" and "What is the minimum
ground coverage?" have nearly the same embedding, and BM25 sees the same tokens.

A **cross-encoder** reads the query and the chunk together, as one input, and returns one
relevance score. It cannot be precomputed, so it cannot search a corpus — 700 chunks
would be 700 forward passes per query. It can rescore a shortlist, which is what this
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
arrived in a later fastembed than the one this project pinned first.
"""

from functools import lru_cache

from app.config import settings

#: Set when the installed fastembed has no cross-encoder module, so the rest of the
#: code can ask rather than catching ImportError in four places.
_IMPORT_ERROR: str | None = None

try:  # fastembed 0.7 and later
    from fastembed.rerank.cross_encoder import TextCrossEncoder
except Exception as exc:  # pragma: no cover - depends on the installed version
    TextCrossEncoder = None  # type: ignore[assignment]
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


def available() -> bool:
    """True when the installed fastembed can build a cross-encoder."""
    return TextCrossEncoder is not None


def unavailable_reason() -> str:
    """Why the reranker cannot be used, for a report or a health check."""
    if available():
        return ""
    return _IMPORT_ERROR or "fastembed.rerank.cross_encoder is not installed"


def supported_models() -> list[dict]:
    """Every cross-encoder the installed fastembed offers, with its size."""
    if not available():
        return []
    return list(TextCrossEncoder.list_supported_models())


@lru_cache(maxsize=1)
def reranker():
    """The cross-encoder, loaded once and kept.

    Weights go to `data/index/models`, the same cache as the embedding model, so a
    container image carries them and the first request does not download 80 MB.
    """
    if not available():
        raise RuntimeError(f"the reranker is not available: {unavailable_reason()}")
    settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
    return TextCrossEncoder(
        model_name=settings.rerank_model, cache_dir=str(settings.model_cache_dir)
    )


def rerank_scores(query: str, documents: list[str]) -> list[float]:
    """One relevance score per document, in the order the documents were given."""
    if not documents:
        return []
    return [float(score) for score in reranker().rerank(query, documents)]
