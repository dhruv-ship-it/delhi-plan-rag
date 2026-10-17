"""Use the point's zones to change what search returns.

A question asked on a map is not the same question everywhere. "What is the maximum
ground coverage allowed on my plot?" has one answer inside a TOD zone (40%), another in
the High Density Corridor, and another on an ordinary plot governed by chapter 7. Plain
hybrid search cannot tell them apart, because the question contains no zone words.

Three steps close that gap, in this order:

  1. Exclusion       drop a chunk whose own policy is a zone the point is not in
  2. Query expansion add the point's zone names to the query text, for both indexes
  3. Boost           multiply the fused score of a chunk about the point's zones

Exclusion and boosting are deliberately asymmetric. Exclusion acts only on
`zone_primary`, which is a claim about where a rule applies (D-023); a chunk with no
primary zone is never dropped, so the general norms in chapters 7 to 13 always stay in
play. Boosting acts on `zone_primary` or `zone_mentions`, so merely naming the zone is
enough to be ranked higher but never enough to push anything out.
"""

from app.config import settings
from app.retrieval import Result, SearchIndex, SearchReport, reciprocal_rank_fusion
from app.spatial import topics_for
from app.tagging import TOPICS

#: What gets appended to the query for each zone the point is in. These are the words a
#: planner would use, so the dense index has something to match on and the keyword index
#: gets the exact short forms the gazette prints.
EXPANSION_TERMS: dict[str, str] = {
    "tod": "transit oriented development TOD zone",
    "hdc": "high density corridor HDC UER-II",
    "zone_o": "Zone O Yamuna floodplain",
    "land_pooling": "land pooling",
    "ridge": "Ridge regional park Aravalli forest",
    "lda": "low density area LDA farmhouse",
}

#: How a point's zones are described back to a reader.
ZONE_LABELS: dict[str, str] = {
    "tod": "TOD zone",
    "hdc": "high density corridor",
    "zone_o": "Zone O (Yamuna floodplain)",
    "land_pooling": "land pooling area",
    "ridge": "Ridge / regional park",
    "lda": "low density area",
}


def expand_query(query: str, topics: list[str]) -> tuple[str, list[str]]:
    """Add the point's zone words to the query. Returns (query sent, terms added)."""
    terms = [EXPANSION_TERMS[topic] for topic in topics if topic in EXPANSION_TERMS]
    if not terms:
        return query, []
    return f"{query} {' '.join(terms)}", terms


def excluded_topics_for(topics: list[str]) -> set[str]:
    """The zone topics the point is **not** in, whose own policy sections can be dropped."""
    return set(TOPICS) - set(topics)


def should_exclude(chunk: dict, excluded: set[str]) -> bool:
    """True when this chunk is a rule for a zone the point is not in.

    Only `zone_primary` counts. A chunk that merely mentions a zone — 4.6.1 listing
    Zone O among the areas it does not cover, 11.1.1 saying fuel stations are allowed
    "in all Use Zones except ... Zone O" — is exactly what a user standing in that zone
    needs, so a mention must never cause a drop.
    """
    primary = chunk.get("zone_primary") or ""
    return bool(primary) and primary in excluded


def matches_point(chunk: dict, topics: list[str]) -> bool:
    """True when the chunk is about at least one of the zones the point is in."""
    if not topics:
        return False
    if (chunk.get("zone_primary") or "") in topics:
        return True
    return any(topic in chunk.get("zone_mentions", []) for topic in topics)


def describe_zones(zones: dict) -> str:
    """One readable line for a get_zones result."""
    if not zones.get("inside_delhi"):
        return "outside NCT Delhi"
    parts = [f"planning zone {zones.get('planning_zone') or 'unknown'}"]
    found = [ZONE_LABELS[topic] for topic in topics_for(zones)]
    if zones.get("land_pooling") and zones.get("land_pooling_zone"):
        found = [
            f"{label} {zones['land_pooling_zone']}" if label == "land pooling area" else label
            for label in found
        ]
    parts.append("in " + ", ".join(found) if found else "in none of the six policy zones")
    return "; ".join(parts)


def _filtered(
    pool: list[tuple[str, float]], index: SearchIndex, excluded: set[str], depth: int
) -> tuple[list[tuple[str, float]], set[str]]:
    """Drop excluded chunks from a pool and keep the first `depth` that are left.

    Returns the kept pool and the ids that were dropped. Filtering happens before the
    ranks are read, so a dropped chunk does not use up a rank slot and nothing further
    down loses fusion points for its presence. The pool is fetched twice as deep as it
    needs to be for the same reason: after dropping, there should still be a full pool
    to fuse.
    """
    dropped: set[str] = set()
    kept: list[tuple[str, float]] = []
    for chunk_id, score in pool:
        chunk = index.chunks.get(chunk_id)
        if chunk is None:
            continue
        if should_exclude(chunk, excluded):
            dropped.add(chunk_id)
            continue
        if len(kept) < depth:
            kept.append((chunk_id, score))
    return kept, dropped


def location_aware_search(
    query: str,
    k: int,
    mode: str,
    zones: dict,
    index: SearchIndex,
    report: SearchReport | None = None,
) -> list[Result]:
    """Search with the point's zones taken into account. See the module docstring.

    A point outside NCT Delhi gets a plain search. None of the three steps mean anything
    there: MPD-2047 does not apply outside Delhi, so dropping its TOD and land pooling
    sections would be answering a different question than the one asked. Saying that the
    point is outside Delhi is the answering step's job, not retrieval's.
    """
    from app.retrieval import rank

    topics = topics_for(zones)
    if not zones.get("inside_delhi"):
        results = rank(query, k=k, mode=mode, index=index)
        if report is not None:
            report.zones = zones
            report.expanded_query = query
        return results

    expanded, terms = expand_query(query, topics) if settings.zone_query_expansion else (query, [])
    excluded = excluded_topics_for(topics) if settings.zone_exclusion else set()
    depth = settings.retrieval_pool

    dense_pool = index.dense_pool(expanded, depth * 2)
    keyword_pool = index.bm25_pool(expanded, depth * 2)
    dense, dense_dropped = _filtered(dense_pool, index, excluded, depth)
    keyword, keyword_dropped = _filtered(keyword_pool, index, excluded, depth)

    dense_rank = {chunk_id: position for position, (chunk_id, _) in enumerate(dense, start=1)}
    bm25_rank = {chunk_id: position for position, (chunk_id, _) in enumerate(keyword, start=1)}
    distance = dict(dense)

    if mode == "dense":
        rankings = [[chunk_id for chunk_id, _ in dense]]
    elif mode == "bm25":
        rankings = [[chunk_id for chunk_id, _ in keyword]]
    else:
        rankings = [
            [chunk_id for chunk_id, _ in dense],
            [chunk_id for chunk_id, _ in keyword],
        ]
    scores = reciprocal_rank_fusion(rankings)

    boosted_ids = set()
    for chunk_id in list(scores):
        chunk = index.chunks.get(chunk_id)
        if chunk is not None and matches_point(chunk, topics):
            scores[chunk_id] *= settings.zone_boost
            boosted_ids.add(chunk_id)

    if report is not None:
        report.zones = zones
        report.expanded_query = expanded
        report.expansion_terms = terms
        report.excluded_topics = sorted(excluded)
        report.excluded = len(dense_dropped | keyword_dropped)
        report.boosted = len(boosted_ids)

    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    results: list[Result] = []
    for chunk_id, score in ordered[:k]:
        chunk = index.chunks.get(chunk_id)
        if chunk is None:
            continue
        results.append(
            Result(
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
                dense_rank=dense_rank.get(chunk_id),
                bm25_rank=bm25_rank.get(chunk_id),
                dense_distance=distance.get(chunk_id),
                fused_score=score,
                boosted=chunk_id in boosted_ids,
            )
        )
    return results
