"""Tests for the fusion arithmetic and the location steps, on toy lists and toy chunks.

Nothing here opens an index. Reciprocal rank fusion is arithmetic over rank orders, and
exclusion and boosting are decisions about chunk fields, so both can be checked exactly
without embedding anything.
"""

import pytest

from app.config import settings
from app.indexing import tokenize
from app.location import (
    EXPANDS_QUERY,
    EXPANSION_TERMS,
    describe_zones,
    excluded_topics_for,
    expand_query,
    matches_point,
    should_exclude,
)
from app.retrieval import reciprocal_rank_fusion
from app.tagging import TOPICS

K = settings.rrf_k


def toy(primary: str = "", mentions=None) -> dict:
    """A chunk record with only the zone fields the location steps read."""
    return {"zone_primary": primary, "zone_mentions": list(mentions or [])}


# --- reciprocal rank fusion -----------------------------------------------------


def test_one_list_gives_one_over_k_plus_rank() -> None:
    """The arithmetic, written out: rank 1 with k = 60 is 1/61."""
    scores = reciprocal_rank_fusion([["a", "b", "c"]])
    assert scores["a"] == pytest.approx(1 / (K + 1))
    assert scores["b"] == pytest.approx(1 / (K + 2))
    assert scores["c"] == pytest.approx(1 / (K + 3))


def test_a_chunk_in_both_lists_adds_its_two_contributions() -> None:
    """Appearing at rank 1 in one list and rank 3 in the other adds 1/61 + 1/63."""
    scores = reciprocal_rank_fusion([["a", "b"], ["c", "d", "a"]])
    assert scores["a"] == pytest.approx(1 / (K + 1) + 1 / (K + 3))
    assert scores["b"] == pytest.approx(1 / (K + 2))


def test_agreement_beats_one_index_being_certain() -> None:
    """This is why k is 60: a chunk both indexes like beats one index's favourite (D-028)."""
    agreed = reciprocal_rank_fusion([["x"] * 0 + ["p", "agreed"], ["q", "agreed"]])
    assert agreed["agreed"] > agreed["p"]
    assert agreed["agreed"] > agreed["q"]


def test_the_boost_decides_between_chunks_both_indexes_found() -> None:
    """Inside the 30-deep pool, a boosted two-list chunk beats an unboosted one (D-034)."""
    top = 2 / (K + 1)
    assert settings.zone_boost * (2 / (K + settings.retrieval_pool)) > top
    # break-even is rank 31.5, which is past the end of the pool
    break_even = settings.zone_boost * (K + 1) - K
    assert break_even > settings.retrieval_pool


def test_the_boost_does_not_let_one_index_overrule_agreement() -> None:
    """A boosted chunk only one index found still loses to one both indexes ranked first."""
    boosted_one_list = settings.zone_boost * (1 / (K + 1))
    unboosted_both_lists = 2 / (K + 1)
    assert boosted_one_list < unboosted_both_lists


def test_an_empty_list_fuses_to_nothing() -> None:
    """A keyword search that matched no token must not crash the fusion."""
    assert reciprocal_rank_fusion([[], ["a"]])["a"] == pytest.approx(1 / (K + 1))
    assert reciprocal_rank_fusion([[], []]) == {}


# --- exclusion ------------------------------------------------------------------


def test_the_excluded_topics_are_the_ones_the_point_is_not_in() -> None:
    """A point in a TOD zone can drop every other policy's own sections.

    Zone O and the Ridge appear in the set and it costs nothing: neither has a policy
    section, so no chunk ever carries them as a primary zone and there is nothing for
    the exclusion step to find (D-037, D-069).
    """
    assert excluded_topics_for(["tod"]) == {"hdc", "zone_o", "land_pooling", "ridge", "lda"}
    assert excluded_topics_for([]) == set(TOPICS)
    assert excluded_topics_for(list(TOPICS)) == set()


def test_a_chunk_with_no_primary_zone_is_never_dropped() -> None:
    """The general norms in chapters 7 to 13 must always stay in play (D-033)."""
    excluded = excluded_topics_for(["tod"])
    assert not should_exclude(toy(), excluded)
    assert not should_exclude(toy(mentions=["hdc", "zone_o"]), excluded)


def test_a_wrong_zone_policy_section_is_dropped() -> None:
    """At a plot in a TOD zone, the HDC norms are not the rules that apply."""
    excluded = excluded_topics_for(["tod"])
    assert should_exclude(toy(primary="hdc"), excluded)
    assert not should_exclude(toy(primary="tod"), excluded)


def test_a_mention_is_never_a_reason_to_drop() -> None:
    """11.1.1 says fuel stations are allowed "in all Use Zones except ... Zone O"."""
    excluded = excluded_topics_for([])  # a plot in none of the four zones
    fuel_stations = toy(primary="", mentions=["zone_o"])
    assert not should_exclude(fuel_stations, excluded)


# --- boosting -------------------------------------------------------------------


def test_the_boost_reads_primary_or_mentions() -> None:
    """Boosting is the weak step, so naming the zone is enough to be lifted (D-033)."""
    assert matches_point(toy(primary="tod"), ["tod"])
    assert matches_point(toy(mentions=["tod"]), ["tod"])
    assert not matches_point(toy(primary="hdc", mentions=["hdc"]), ["tod"])


def test_nothing_is_boosted_for_a_point_in_no_zone() -> None:
    """At P_PLAIN there is no zone to be about, so the boost does not fire."""
    assert not matches_point(toy(primary="tod", mentions=["tod"]), [])


# --- query expansion ------------------------------------------------------------


def test_expansion_appends_the_zone_words_for_each_zone_the_point_is_in() -> None:
    """A question with no zone words in it is what expansion exists for (D-033)."""
    expanded, terms = expand_query("What FAR can I get here?", ["tod"])
    assert expanded == "What FAR can I get here? transit oriented development TOD zone"
    assert terms == [EXPANSION_TERMS["tod"]]


def test_expansion_leaves_a_query_alone_when_the_point_is_in_no_zone() -> None:
    """Nothing to add, so nothing is added."""
    assert expand_query("What FAR can I get here?", []) == ("What FAR can I get here?", [])


def test_zone_o_boosts_but_does_not_expand() -> None:
    """D-086. Zone O has no policy section, so its words name a place, not a policy.

    Appending them moved the dense query to a different subject: the clause that answers
    "can a fuel station be built here?" fell from rank 1 to rank 14 while its own cosine
    *rose*, because ~160 floodplain chunks rose further.
    """
    assert expand_query("Can a fuel station be built here?", ["zone_o"]) == (
        "Can a fuel station be built here?",
        [],
    )


def test_the_ridge_boosts_but_does_not_expand() -> None:
    """The other half of D-086, and the same reason: no policy section to aim at."""
    assert expand_query("What is the parking norm here?", ["ridge"]) == (
        "What is the parking norm here?",
        [],
    )


def test_a_point_in_both_kinds_of_zone_expands_only_for_the_policy_one() -> None:
    """The scope is per topic, not per point, so a TOD plot inside Zone O still expands."""
    expanded, terms = expand_query("What FAR can I get here?", ["tod", "zone_o"])
    assert expanded == "What FAR can I get here? transit oriented development TOD zone"
    assert terms == [EXPANSION_TERMS["tod"]]


def test_the_two_topics_that_may_not_expand_are_the_two_that_may_not_exclude() -> None:
    """The asymmetry is the same one twice over, which is the whole argument for D-086.

    `zone_o` and `ridge` have no `zone_primary` anywhere in the corpus, so exclusion has
    nothing to find for them, and no chapter heading to move a dense query towards, so
    expansion has nothing to aim at. One cause, two steps.
    """
    assert set(EXPANDS_QUERY) == {"tod", "hdc", "land_pooling", "lda"}
    assert set(EXPANDS_QUERY) <= set(TOPICS)
    assert set(TOPICS) - set(EXPANDS_QUERY) == {"zone_o", "ridge"}
    # every topic that may expand still has terms to expand with
    assert all(topic in EXPANSION_TERMS for topic in EXPANDS_QUERY)


def test_the_unexpanded_topics_keep_their_terms_on_file() -> None:
    """The vocabulary is kept, so widening the scope back is one tuple and not research."""
    assert EXPANSION_TERMS["zone_o"] == "Zone O Yamuna floodplain"
    assert EXPANSION_TERMS["ridge"] == "Ridge regional park Aravalli forest"


def test_a_zone_o_chunk_is_still_boosted_and_still_never_excluded() -> None:
    """D-086 changed step 2 only. Steps 1 and 3 behave exactly as before.

    `11.1.1@p854` is the real shape of the clause this all started with: no primary zone,
    and `zone_o` among its mentions.
    """
    clause = toy(primary="", mentions=["zone_o", "ridge"])
    assert matches_point(clause, ["zone_o"])
    assert not should_exclude(clause, excluded_topics_for(["zone_o"]))


def test_the_expansion_terms_survive_the_keyword_tokenizer() -> None:
    """The short forms have to reach BM25 as tokens, or expansion only helps the dense side."""
    tokens = tokenize(EXPANSION_TERMS["hdc"])
    assert "hdc" in tokens
    assert "uer" in tokens and "ii" in tokens
    assert "tod" in tokenize(EXPANSION_TERMS["tod"])


def test_a_clause_number_survives_the_tokenizer_whole() -> None:
    """Searching for "4.2.1" has to find clause 4.2.1 (D-027)."""
    assert tokenize("see clause 4.2.1 onwards") == ["see", "clause", "4.2.1", "onwards"]
    assert tokenize("The policy.The next") == ["policy", "next"]
    assert tokenize("mixed-use development") == ["mixed", "use", "development"]


# --- describing a point ---------------------------------------------------------


def test_a_point_outside_delhi_says_so_and_nothing_else() -> None:
    """None of the other answers mean anything there (D-031)."""
    assert describe_zones({"inside_delhi": False}) == "outside NCT Delhi"


def test_a_point_in_delhi_is_described_by_its_zones() -> None:
    """The line the search CLI prints above its results."""
    described = describe_zones(
        {
            "inside_delhi": True,
            "planning_zone": "K-I",
            "tod": False,
            "hdc": True,
            "land_pooling": False,
            "land_pooling_zone": None,
            "zone_o": False,
            "regional_park": False,
            "lda": False,
        }
    )
    assert described == "planning zone K-I; in high density corridor"


def test_a_point_in_no_policy_zone_says_that_too() -> None:
    """P_PLAIN should read as a plain plot, not as an empty answer."""
    described = describe_zones(
        {
            "inside_delhi": True,
            "planning_zone": "G",
            "tod": False,
            "hdc": False,
            "land_pooling": False,
            "land_pooling_zone": None,
            "zone_o": False,
            "regional_park": False,
            "lda": False,
        }
    )
    assert "none of the six policy zones" in described
