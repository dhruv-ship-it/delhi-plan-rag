"""Use the point's zones to change what search returns.

A question asked on a map is not the same question everywhere. "What is the maximum
ground coverage allowed on my plot?" has one answer inside a TOD zone (40%), another in
the High Density Corridor, and another on an ordinary plot governed by chapter 7. Plain
hybrid search cannot tell them apart, because the question contains no zone words.

Three steps close that gap, in this order:

  1. Exclusion       drop a chunk whose own policy is a zone the point is not in
  2. Query expansion add the point's zone names to the query text, for both indexes
  3. Boost           multiply the fused score of a chunk about the point's zones
  4. Rerank          optionally rescore the shortlist with a cross-encoder (D-070)

Exclusion and boosting are deliberately asymmetric. Exclusion acts only on
`zone_primary`, which is a claim about where a rule applies (D-023); a chunk with no
primary zone is never dropped, so the general norms in chapters 7 to 13 always stay in
play. Boosting acts on `zone_primary` or `zone_mentions`, so merely naming the zone is
enough to be ranked higher but never enough to push anything out.

**Expansion is asymmetric in the same way, and for the same reason (D-086).** Only the
four topics that have a policy section of their own expand the query — the same four
that are allowed to exclude. `zone_o` and `ridge` have no section in MPD-2047, so their
terms name a *place* rather than a policy, and appending them replaces the subject of
the question instead of qualifying it: at P_ZONEO the clause that answers "can a fuel
station be built here?" fell from rank 1 to rank 14 because ~160 floodplain chunks rose
past it. Those two topics still boost, and exclusion is unchanged.

**Those two topics fuse four lists instead of two (D-093).** Dropping their expansion
fixed the fuel-station miss and cost the questions whose subject *is* the place: at
P_ZONEO "Can I construct a building here?" lost `3.1.2@p681` from rank 1 to outside a
200-deep list. Fusing both wordings keeps both — `dense(plain)`, `bm25(plain)`,
`dense(expanded)`, `bm25(expanded)`, all four into one RRF — because a clause only
needs to be found by *one* of them to earn fusion points. It is **scoped** to `zone_o`
and `ridge`: the other four topics never reach this path, so the published demo beats
cannot move, by construction. Re-admitting the un-expanded dense list at *every* point
was measured and rejected, because plain semantic search over this corpus prefers the
FAQ's short conversational chunks and put authority rank 3 above rank 1
(`reports/diagnosis_fuel_station.md`).

So the three asymmetries all come from one fact about the corpus — MPD-2047 has no
Zone O chapter and no Ridge chapter — and they line up: the four topics with a policy
section exclude, expand and fuse two lists; the two without never exclude, and fuse
four lists so that their place words are an *extra* vote rather than a replacement.

One more thing lives here, and it is not a retrieval step: `location_note` (D-094). A
question can *name* a zone the point is not in, and retrieval will answer it well and
about the wrong place. The note is a deterministic sentence built from `get_zones` and
the layers — "this point is not inside Zone O … the nearest Zone O boundary is about
600 m away" — which the API returns as its own field, the interface shows above the
answer, and the model is given as context with an instruction to answer for the point.
It is written in code and is never one of the sentences the citation check validates,
for the same reason the disclaimer is not (D-092): nothing in the corpus states it.
"""

from app.config import settings
from app.retrieval import (
    Result,
    SearchIndex,
    SearchReport,
    apply_reranker,
    reciprocal_rank_fusion,
)
from app.spatial import distance_to_topic, topics_for
from app.tagging import TOPICS, mentions_of

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

#: The topics whose terms may be appended to the query: the four that have a policy
#: section of their own in MPD-2047, which is the same four `should_exclude` acts on.
#: A dense query is one point in embedding space and appending a topic *moves* it, so
#: the move is only safe when there is a chapter to move towards (D-086).
EXPANDS_QUERY: tuple[str, ...] = ("tod", "hdc", "land_pooling", "lda")

#: The topics whose terms go into a **second** query, fused alongside the first, rather
#: than into the one query both indexes search: exactly the topics `EXPANDS_QUERY`
#: leaves out, which is exactly the two with no policy section (D-093). A test asserts
#: that relationship rather than trusting this comment.
FUSES_FOUR_LISTS: tuple[str, ...] = ("zone_o", "ridge")

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
    """Add the point's zone words to the query. Returns (query sent, terms added).

    Only the topics in `EXPANDS_QUERY` contribute. A point in Zone O or on the Ridge
    therefore searches with the user's own words, unexpanded, and relies on the boost
    instead (D-086).
    """
    terms = [
        EXPANSION_TERMS[topic]
        for topic in topics
        if topic in EXPANDS_QUERY and topic in EXPANSION_TERMS
    ]
    if not terms:
        return query, []
    return f"{query} {' '.join(terms)}", terms


def place_query(query: str, topics: list[str]) -> tuple[str, list[str]]:
    """The second query: the first one plus the place words of the no-policy topics.

    Returns (query, terms added), and the query unchanged with no terms when the point
    is in neither `zone_o` nor `ridge` — which is how `location_aware_search` decides
    whether there is a second pair of lists to fetch at all.

    `query` is whatever `expand_query` produced, not the user's raw words, so a point
    in both a TOD zone and Zone O searches "…TOD zone" and "…TOD zone Zone O Yamuna
    floodplain". The TOD expansion is never thrown away; the place words are only ever
    added on top of it (D-093).
    """
    terms = [
        EXPANSION_TERMS[topic]
        for topic in topics
        if topic in FUSES_FOUR_LISTS and topic in EXPANSION_TERMS
    ]
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


# --- the named-zone mismatch note (D-094) ---------------------------------------
#
# A question can name a zone the point is not in: "can I build a house on the Yamuna
# floodplain near ITO?" asked at a point `get_zones` says is in a TOD zone, 620 m from
# the nearest Zone O polygon. Retrieval answers that question well — the floodplain
# words are in the query, so the no-construction clause comes back — and the answer is
# then about a zone the user is not standing in. v2's `agent-02` did exactly this and
# `docs/PROJECT_STATUS.md` called it "a regression dressed as a win".
#
# The fix is a sentence written **here**, in code, from `get_zones` and the layers: the
# point is not in that zone, and here is how far away it is. It is deterministic, it is
# never part of the validated sentences, and the model is told to answer for the point
# rather than for the zone the question named.

#: How each zone is named in a note. Longer than `ZONE_LABELS` because a note is a
#: sentence and needs its articles: "a TOD zone", "the Ridge".
NOTE_LABELS: dict[str, str] = {
    "tod": "a TOD zone",
    "hdc": "the High Density Corridor",
    "zone_o": "Zone O (Yamuna floodplain)",
    "land_pooling": "a land pooling area",
    "ridge": "the Ridge / a Regional Park",
    "lda": "a Low Density Area",
}

#: The short form, for the second half of the note. "the nearest Zone O boundary" reads
#: and "the nearest Zone O (Yamuna floodplain) boundary" does not.
NOTE_SHORT_LABELS: dict[str, str] = {
    "tod": "TOD zone",
    "hdc": "High Density Corridor",
    "zone_o": "Zone O",
    "land_pooling": "land pooling area",
    "ridge": "Ridge / Regional Park",
    "lda": "Low Density Area",
}

#: Below this many metres a note says "less than" rather than a rounded figure, because
#: "about 0 m away" is wrong and "about 50 m away" would be invented precision.
NEAREST_FLOOR_M = 50
#: Metres are rounded to this, so a note never implies the layers are survey-accurate.
METRE_STEP = 50


def describe_distance(metres: float) -> str:
    """One readable distance: "less than 50 m", "about 600 m", "about 1.1 km".

    Rounded hard on purpose. The layers are DDA's published GIS shapes simplified for a
    browser, so a note that said "613 m" would claim an accuracy nothing here has.
    """
    if metres < NEAREST_FLOOR_M:
        return f"less than {NEAREST_FLOOR_M} m"
    if metres < 1000:
        return f"about {int(round(metres / METRE_STEP)) * METRE_STEP} m"
    return f"about {metres / 1000:.1f} km"


def named_zone_topics(question: str) -> list[str]:
    """The zone topics the question's own words name, in `TOPICS` order.

    The same regexes that tag the chunks (`app.tagging.mentions_of`), used on the
    question instead of on a clause. Reusing them is the point: a question that says
    "Yamuna floodplain" and a clause that says it are recognised by one rule, so the
    note cannot disagree with the tagging about what counts as naming a zone.
    """
    return list(mentions_of(question))


def mismatched_topics(question: str, zones: dict) -> list[str]:
    """The zone topics the question names that the point is **not** in."""
    if not zones.get("inside_delhi"):
        return []
    inside = set(topics_for(zones))
    return [topic for topic in named_zone_topics(question) if topic not in inside]


def note_for_topic(topic: str, lat: float, lon: float) -> str:
    """One sentence: the point is not in this zone, and how far away the zone is.

    The distance clause is dropped rather than guessed when the layers cannot answer.
    A note is a convenience, so losing the distance has to cost the distance and not
    the answer.
    """
    try:
        metres = distance_to_topic(lat, lon, topic)
    except Exception:  # pragma: no cover - needs the layers or pyproj to be broken
        metres = None
    tail = ""
    if metres is not None:
        tail = (
            f"; the nearest {NOTE_SHORT_LABELS[topic]} boundary is "
            f"{describe_distance(metres)} away"
        )
    return f"This point is not inside {NOTE_LABELS[topic]} on DDA's map{tail}."


def location_note(question: str, lat: float | None, lon: float | None, zones: dict) -> str:
    """The whole note for one question at one point, or "" when there is nothing to say.

    One sentence per zone the question names and the point is not in, in `TOPICS` order.
    Empty — which is the common case — when the question names no zone, when it names
    only zones the point is in, or when there is no point at all.
    """
    if lat is None or lon is None:
        return ""
    return " ".join(
        note_for_topic(topic, lat, lon) for topic in mismatched_topics(question, zones)
    )


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
        results = rank(query, k=k, mode=mode, index=index, report=report)
        if report is not None:
            report.zones = zones
            report.expanded_query = query
        return results

    expanded, terms = expand_query(query, topics) if settings.zone_query_expansion else (query, [])
    second, place_terms = (
        place_query(expanded, topics) if settings.zone_query_expansion else (expanded, [])
    )
    excluded = excluded_topics_for(topics) if settings.zone_exclusion else set()
    depth = settings.retrieval_pool

    # One pair of pools per query. The second pair only exists for a point in Zone O or
    # on the Ridge, so every other point pays nothing for this (D-093).
    queries = [expanded] + ([second] if place_terms else [])
    pairs = []
    dropped: set[str] = set()
    for one in queries:
        dense, dense_dropped = _filtered(
            index.dense_pool(one, depth * 2), index, excluded, depth
        )
        keyword, keyword_dropped = _filtered(
            index.bm25_pool(one, depth * 2), index, excluded, depth
        )
        pairs.append((dense, keyword))
        dropped |= dense_dropped | keyword_dropped

    # The score breakdown is **first-pair-first**: a chunk the original pair already
    # found keeps exactly the rank, cosine and BM25 score it had before this change, so
    # the abstention pre-check reads the same number for it as it always did (D-071).
    # A chunk only the second pair found reports that pair's numbers, because the
    # alternative is reporting nothing about a result we are showing.
    dense_rank: dict[str, int] = {}
    bm25_rank: dict[str, int] = {}
    distance: dict[str, float] = {}
    keyword_score: dict[str, float] = {}
    for one_dense, one_keyword in pairs:
        for position, (chunk_id, value) in enumerate(one_dense, start=1):
            dense_rank.setdefault(chunk_id, position)
            if value is not None:
                distance.setdefault(chunk_id, value)
        for position, (chunk_id, value) in enumerate(one_keyword, start=1):
            bm25_rank.setdefault(chunk_id, position)
            keyword_score.setdefault(chunk_id, value)

    if mode == "dense":
        rankings = [[chunk_id for chunk_id, _ in one_dense] for one_dense, _ in pairs]
    elif mode == "bm25":
        rankings = [[chunk_id for chunk_id, _ in one_keyword] for _, one_keyword in pairs]
    else:
        rankings = []
        for one_dense, one_keyword in pairs:
            rankings.append([chunk_id for chunk_id, _ in one_dense])
            rankings.append([chunk_id for chunk_id, _ in one_keyword])
    scores = reciprocal_rank_fusion(rankings)

    boosted_ids = set()
    for chunk_id in list(scores):
        chunk = index.chunks.get(chunk_id)
        if chunk is not None and matches_point(chunk, topics):
            scores[chunk_id] *= settings.zone_boost
            boosted_ids.add(chunk_id)

    if report is not None:
        report.zones = zones
        report.expanded_query = queries[-1]
        report.expansion_terms = terms + place_terms
        report.queries = list(queries)
        report.place_terms = list(place_terms)
        report.fused_lists = len(rankings)
        report.excluded_topics = sorted(excluded)
        report.excluded = len(dropped)
        report.boosted = len(boosted_ids)

    ordered = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    # Deeper than k when the reranker is on, so it has a shortlist to reorder. The
    # reranker reads the fullest query — the text the last pair of lists searched with.
    # With four lists there is no single text every pool saw, and the reranker is off by
    # default (D-070), so this keeps one rule rather than adding a branch nothing runs.
    depth = max(k, settings.rerank_pool) if settings.reranker_on else k
    results: list[Result] = []
    for chunk_id, score in ordered[:depth]:
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
                bm25_score=keyword_score.get(chunk_id),
            )
        )
    return apply_reranker(queries[-1], results, k, report)
