"""Search the two indexes and fuse their results.

Three modes:

  dense    nearest neighbours of the query's embedding, by cosine distance
  bm25     best keyword matches
  hybrid   both of the above, fused with reciprocal rank fusion

Both pools are always fetched, whatever the mode, so every result can show where each
index put it. That is the point of the score breakdown: when a hybrid result looks
wrong, the breakdown says which of the two indexes dragged it up.

Reciprocal rank fusion adds 1/(k + rank) over the lists a chunk appears in, with
k = 60 (see D-028). It uses only the ranks, never the scores, which is what makes it
safe here: a cosine distance and a BM25 score are not on the same scale and cannot be
added, but their rank orders can.
"""

from dataclasses import dataclass, field

from app.config import settings
from app.indexing import (
    chroma_client,
    embedder,
    load_bm25,
    open_collection,
    read_chunks,
    tokenize,
)

MODES = ("dense", "bm25", "hybrid")


@dataclass(frozen=True)
class Result:
    """One search result: where the chunk is, how it scored, and its text."""

    chunk_id: str
    doc_id: str
    clause_id: str | None
    heading_path: list[str]
    chapter: str
    page_start: int
    page_end: int
    zone_primary: str
    zone_mentions: list[str]
    text: str
    #: 1-based position in each pool, or None when the chunk was not in that pool.
    dense_rank: int | None
    bm25_rank: int | None
    #: Cosine distance from the query, when the dense pool returned this chunk.
    dense_distance: float | None
    #: The fused score the result is ranked by, after any zone boost.
    fused_score: float
    #: True when a zone boost multiplied this result's score.
    boosted: bool = False

    @property
    def path(self) -> str:
        """The heading path as one readable string."""
        return " › ".join(self.heading_path)


@dataclass
class SearchReport:
    """What a location-aware search did, beyond returning results."""

    query: str
    expanded_query: str
    zones: dict | None = None
    excluded: int = 0
    boosted: int = 0
    excluded_topics: list[str] = field(default_factory=list)
    expansion_terms: list[str] = field(default_factory=list)


class SearchIndex:
    """Both indexes and the chunk records, loaded once and reused for every query."""

    def __init__(self) -> None:
        chunks = read_chunks(settings.processed_dir / "chunks.jsonl")
        self.chunks: dict[str, dict] = {chunk["chunk_id"]: chunk for chunk in chunks}
        self.bm25, self.bm25_ids = load_bm25(settings.bm25_path)
        self._client = chroma_client()
        self._collection = open_collection(self._client)
        self._model = embedder()

    def __len__(self) -> int:
        return len(self.chunks)

    def dense_pool(self, query: str, n: int) -> list[tuple[str, float]]:
        """The n nearest chunks to the query, as (chunk_id, cosine distance)."""
        vector = next(iter(self._model.query_embed([query]))).tolist()
        found = self._collection.query(
            query_embeddings=[vector], n_results=min(n, len(self.chunks))
        )
        ids = found["ids"][0]
        distances = found["distances"][0] if found.get("distances") else [None] * len(ids)
        return list(zip(ids, distances))

    def bm25_pool(self, query: str, n: int) -> list[tuple[str, float]]:
        """The n best keyword matches for the query, as (chunk_id, BM25 score).

        A chunk with a score of zero shares no token with the query, so it is dropped
        rather than padded into the pool: an unrelated chunk sitting at rank 12 would
        still earn fusion points.
        """
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.bm25_ids, scores), key=lambda pair: -pair[1])
        return [(chunk_id, score) for chunk_id, score in ranked[:n] if score > 0]


_INDEX: SearchIndex | None = None


def get_index() -> SearchIndex:
    """The shared SearchIndex, opened on first use.

    Opening it loads the embedding model and the pickled BM25 corpus, which takes a
    second or two, so a script running eight queries opens it once.
    """
    global _INDEX
    if _INDEX is None:
        _INDEX = SearchIndex()
    return _INDEX


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = settings.rrf_k
) -> dict[str, float]:
    """Fuse ranked lists of chunk ids: each list adds 1/(k + rank), ranks 1-based.

    With k = 60 the gap between rank 1 and rank 2 is small (0.0164 against 0.0161), so
    a chunk that both indexes put in their top ten beats a chunk that one index put
    first and the other missed entirely. That is the behaviour we want from a fusion:
    agreement should count for more than one index's confidence.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)
    return scores


def _result(
    chunk: dict,
    dense_rank: int | None,
    bm25_rank: int | None,
    dense_distance: float | None,
    score: float,
    boosted: bool = False,
) -> Result:
    """Build one Result from a chunk record and its scores."""
    return Result(
        chunk_id=chunk["chunk_id"],
        doc_id=chunk["doc_id"],
        clause_id=chunk["clause_id"],
        heading_path=list(chunk["heading_path"]),
        chapter=chunk["chapter"],
        page_start=chunk["page_start"],
        page_end=chunk["page_end"],
        zone_primary=chunk.get("zone_primary", ""),
        zone_mentions=list(chunk.get("zone_mentions", [])),
        text=chunk["text"],
        dense_rank=dense_rank,
        bm25_rank=bm25_rank,
        dense_distance=dense_distance,
        fused_score=score,
        boosted=boosted,
    )


def search(
    query: str,
    k: int = settings.default_k,
    mode: str = "hybrid",
    zones: dict | None = None,
    index: SearchIndex | None = None,
    report: SearchReport | None = None,
) -> list[Result]:
    """Search for a query and return the best k chunks.

    `mode` is "dense", "bm25" or "hybrid". `zones` is the result of
    `app.spatial.get_zones` for the point the question was asked at; when it is given,
    the search becomes location-aware (see `app.location`). Pass a `SearchReport` to
    find out what the location steps did.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    index = index or get_index()

    if zones:
        from app.location import location_aware_search

        return location_aware_search(query, k=k, mode=mode, zones=zones, index=index, report=report)

    return rank(query, k=k, mode=mode, index=index, report=report)


def rank(
    query: str,
    k: int,
    mode: str,
    index: SearchIndex,
    pool: int = settings.retrieval_pool,
    report: SearchReport | None = None,
) -> list[Result]:
    """Fetch both pools, rank them the way `mode` asks, and return the top k."""
    dense = index.dense_pool(query, pool)
    keyword = index.bm25_pool(query, pool)

    dense_rank = {chunk_id: position for position, (chunk_id, _) in enumerate(dense, start=1)}
    bm25_rank = {chunk_id: position for position, (chunk_id, _) in enumerate(keyword, start=1)}
    distance = dict(dense)

    if mode == "dense":
        scores = reciprocal_rank_fusion([[chunk_id for chunk_id, _ in dense]])
    elif mode == "bm25":
        scores = reciprocal_rank_fusion([[chunk_id for chunk_id, _ in keyword]])
    else:
        scores = reciprocal_rank_fusion(
            [[chunk_id for chunk_id, _ in dense], [chunk_id for chunk_id, _ in keyword]]
        )

    if report is not None:
        report.expanded_query = query

    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    results = []
    for chunk_id, score in ordered[:k]:
        chunk = index.chunks.get(chunk_id)
        if chunk is None:
            continue  # the index holds a chunk id that chunks.jsonl no longer has
        results.append(
            _result(
                chunk,
                dense_rank.get(chunk_id),
                bm25_rank.get(chunk_id),
                distance.get(chunk_id),
                score,
            )
        )
    return results
