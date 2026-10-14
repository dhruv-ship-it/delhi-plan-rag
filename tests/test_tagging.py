"""Tests for app/tagging.py, with the false positives the zone regexes have to survive.

The dangerous one is Zone O. "zone of", "Zone of the river", "TOD Zone or" and "flood
plain zone of river" all look like it and none of them is it, and a wrong zone_o tag is
not harmless: it is what decides whether a chunk can be dropped from a search.
"""

from app.tagging import (
    TOPICS,
    default_zone_sections,
    heading_numbers,
    matches_for,
    mentions_of,
    primary_zone,
    tag_chunk,
)


#: The committed mapping, loaded once; every test below uses it rather than a literal.
SECTIONS = default_zone_sections()


def chunk(
    text: str = "",
    chapter: str = "4",
    heading_path=None,
    doc_id: str = "MPD47_GAZETTE_EN",
) -> dict:
    """A minimal chunk record, enough for the tagging functions."""
    return {
        "text": text,
        "chapter": chapter,
        "heading_path": heading_path or [],
        "doc_id": doc_id,
    }


# --- the false positives --------------------------------------------------------


def test_zone_o_does_not_match_zone_of_or_zone_or() -> None:
    """Capital O as a standalone word is the whole defence here."""
    for text in (
        "TOD Zone or any other zone",
        "the flood plain zone of river",
        "Zone of the river",
        "the zone of influence",
        "zone one and zone two",
    ):
        assert "zone_o" not in mentions_of(text), text


def test_tod_zone_or_is_still_tagged_tod() -> None:
    """Rejecting the zone_o reading must not cost the tod reading."""
    assert mentions_of("TOD Zone or any other zone") == {"tod": ["TOD"]}


def test_zone_o_matches_every_form_the_gazette_uses() -> None:
    """Plain, quoted, hyphenated, and the floodplain wording."""
    for text, expected in (
        ("all Use Zones except Regional park/Ridge, Zone O Lutyens", "Zone O"),
        ("shall not apply to Zone ‘O’ and buffers", "Zone ‘O"),
        ("Zone O-1 and Zone O-2", "Zone O"),
        ("Yamuna floodplain encroachment", "Yamuna floodplain"),
        ("demarcation of the Yamuna flood plain", "Yamuna flood plain"),
    ):
        assert expected in matches_for("zone_o", text), text


def test_river_yamuna_plus_flood_is_the_only_two_part_condition() -> None:
    """The court documents never write "Zone O"; they write about the river and flooding."""
    assert matches_for("zone_o", "demarcation of the flood plain zone of river Yamuna") == [
        "river Yamuna + flood"
    ]
    # the river alone is not enough, and flooding alone is not enough
    assert matches_for("zone_o", "the river Yamuna has a historic connect with the city") == []
    assert matches_for("zone_o", "storm water drainage reduces flooding") == []


def test_the_short_forms_are_case_sensitive() -> None:
    """"TOD" and "HDC" in capitals only; the spelled-out forms either way."""
    assert "tod" in mentions_of("TOD Plot")
    assert "tod" not in mentions_of("the tod of the matter")
    assert "hdc" in mentions_of("an HDC Plot")
    assert "hdc" not in mentions_of("hdc in lower case")
    assert "tod" in mentions_of("transit-oriented development")
    assert "tod" in mentions_of("Transit Oriented Development")


def test_hdc_covers_the_uer_two_corridor_both_ways_round() -> None:
    """The gazette writes UER-II and UER II, and spells out Urban Extension Road."""
    assert matches_for("hdc", "UER-II corridor and UER II") == ["UER-II", "UER II"]
    assert "hdc" in mentions_of("along the Urban Extension Road")
    assert "hdc" in mentions_of("high-density corridor")


def test_land_pooling_matches_both_phrasings() -> None:
    """"land pooling" and "pooled land"."""
    assert matches_for("land_pooling", "the land pooling policy covers pooled land") == [
        "land pooling",
        "pooled land",
    ]


# --- primary zones --------------------------------------------------------------


def test_heading_numbers_are_read_off_the_heading_path() -> None:
    """"4.2.1 Definitions" contributes the number 4.2.1."""
    assert heading_numbers(["4.2 TRANSIT ORIENTED DEVELOPMENT (TOD)", "4.2.1 Definitions"]) == [
        "4.2",
        "4.2.1",
    ]
    assert heading_numbers(["Annexure 21: Use Premises"]) == []


def test_a_section_and_every_section_under_it_get_the_primary_zone() -> None:
    """4.2 is the TOD policy, so 4.2.1 and 4.2.3.1 are TOD rules too."""
    for path in (["4.2 TOD"], ["4.2 TOD", "4.2.1 Definitions"], ["4.2.3.1 Norms"]):
        assert primary_zone(chunk(heading_path=path), SECTIONS) == "tod"
    assert primary_zone(chunk(heading_path=["4.3 HDC"]), SECTIONS) == "hdc"
    assert primary_zone(chunk(heading_path=["4.1 LAND POOLING"]), SECTIONS) == "land_pooling"


def test_a_neighbouring_section_does_not_inherit_the_primary_zone() -> None:
    """4.20 starts with "4.2" as a string but is not under it."""
    assert primary_zone(chunk(heading_path=["4.20 Something Else"]), SECTIONS) == ""
    assert primary_zone(chunk(heading_path=["4.4 LOW DENSITY AREA"]), SECTIONS) == ""


def test_the_service_plans_cannot_claim_a_primary_zone() -> None:
    """A Delhi Jal Board section numbered 4.2 is not the TOD policy (D-023)."""
    sewerage = chunk(chapter="service_plans", heading_path=["4.2 Rehabilitation of peripheral sewers"])
    assert primary_zone(sewerage, SECTIONS) == ""


def test_zone_o_has_no_primary_section() -> None:
    """MPD-2047 has no Zone O policy, so nothing can be primary for it (D-024, D-037)."""
    assert SECTIONS.gazette["zone_o"] == []
    assert SECTIONS.faq["zone_o"] == []
    tagged = tag_chunk(chunk(text="shall not apply to Zone O", heading_path=["3.1.2 Green-Blue"]),
                       SECTIONS)
    assert tagged["zone_primary"] == ""
    assert tagged["zm_zone_o"] is True


# --- the flat fields ------------------------------------------------------------


def test_the_flat_fields_are_booleans_and_zm_includes_the_primary() -> None:
    """Chroma can only filter scalars, and zm_* answers "about my zone at all?" (D-023)."""
    tagged = tag_chunk(
        chunk(text="Grievance redressal for the policy.", heading_path=["4.1 LAND POOLING", "4.1.4 Grievance Redressal"]),
        SECTIONS,
    )
    assert tagged["zone_primary"] == "land_pooling"
    assert tagged["zone_mentions"] == []  # the text never says "land pooling"
    assert tagged["zp_land_pooling"] is True
    assert tagged["zm_land_pooling"] is True  # primary counts as being about the zone
    for topic in TOPICS:
        assert isinstance(tagged[f"zp_{topic}"], bool)
        assert isinstance(tagged[f"zm_{topic}"], bool)
    assert tagged["zp_tod"] is False


# --- the FAQ's own policy sections (D-038) ---------------------------------------


def faq_chunk(heading: str, question: str = "Q1. What is the permissible FAR?") -> dict:
    """A FAQ chunk, whose heading_path is [section heading, question]."""
    return chunk(
        text=question,
        chapter="",
        heading_path=[heading, question],
        doc_id="MPD47_FAQ",
    )


def test_a_faq_section_that_names_a_topic_gets_that_primary_zone() -> None:
    """The FAQ has no section numbers, so its headings are matched on words."""
    cases = {
        "FAQs - Transit Oriented Development (TOD) Policy": "tod",
        "FAQs on High Density Corridor (HDC) Policy": "hdc",
        "FAQs \u2013 Land Pooling Policy": "land_pooling",
    }
    for heading, topic in cases.items():
        assert primary_zone(faq_chunk(heading), SECTIONS) == topic, heading


def test_a_generic_faq_section_stays_untagged() -> None:
    """Only an explicit topic name counts; everything else keeps an empty primary zone."""
    for heading in (
        "FAQs - GENERIC",
        "FAQs \u2013 Development Control Norms (DCN) for already existing developed areas",
        "FAQs \u2013 Heritage, Culture & Public Spaces",
        "FAQs on LDA",
        "FAQs - Slum and JJ Clusters",
        "FREQUENTLY ASKED QUESTIONS (FAQs)",
    ):
        assert primary_zone(faq_chunk(heading), SECTIONS) == "", heading


def test_the_low_density_area_faq_is_not_read_as_high_density() -> None:
    """"LDA" and "Low Density Area" must not match the high density corridor phrases."""
    assert primary_zone(faq_chunk("FAQs on LDA"), SECTIONS) == ""
    assert primary_zone(faq_chunk("FAQs on Low Density Area (LDA)"), SECTIONS) == ""


def test_the_faq_heading_is_matched_whatever_its_case() -> None:
    """The document is inconsistent about case and dashes; the mapping should not care."""
    assert primary_zone(faq_chunk("faqs - transit oriented development policy"), SECTIONS) == "tod"


def test_a_question_inside_a_tagged_faq_section_can_now_be_excluded() -> None:
    """This is the point of D-038: the TOD FAQ answer is a TOD rule, so it can be dropped."""
    tagged = tag_chunk(
        faq_chunk(
            "FAQs - Transit Oriented Development (TOD) Policy",
            "Q13. What is the maximum ground coverage permissible for a TOD Plot?",
        ),
        SECTIONS,
    )
    assert tagged["zone_primary"] == "tod"
    assert tagged["zp_tod"] is True
