"""Tag each chunk with the planning-zone topics it is about, so a point can filter search.

ZoneWise answers questions about a point on the map, and six of the plan's policies are
the ones that depend on where you are standing:

  tod            Transit Oriented Development, the 500 m band along metro corridors
  hdc            the High Density Corridor, including the UER-II corridor
  zone_o         the Yamuna floodplain: planning zone O, and O-1 / O-2
  land_pooling   the land pooling areas
  ridge          the Ridge and the Regional Parks: Delhi's Aravalli forest
  lda            the Low Density Areas along the border of the NCT

A chunk gets two different kinds of tag, and the difference matters at search time.

`zone_primary` is the one topic whose own policy section the chunk sits in, decided by
its heading path, not by its words. It is a strong claim: a chunk with
`zone_primary = "tod"` is a rule that applies inside the TOD zone and nowhere else, so
it can be excluded outright for a point that is not in a TOD zone.

`zone_mentions` is every topic the chunk's text names. It is a weak claim: section
4.6.1 lists Zone O among the areas it does *not* apply to, so mentioning a topic is a
reason to rank a chunk higher for a point in that zone, never a reason to drop it for a
point outside.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

#: The six topics, in the order they are reported. The order also decides which topic
#: a heading takes when it could belong to two, and nothing in this corpus does.
TOPICS = ("tod", "hdc", "zone_o", "land_pooling", "ridge", "lda")

#: How each topic is named back to a reader, and in a query expansion.
TOPIC_NAMES = {
    "tod": "Transit Oriented Development (TOD)",
    "hdc": "High Density Corridor (HDC)",
    "zone_o": "Zone O (Yamuna floodplain)",
    "land_pooling": "Land Pooling",
    "ridge": "the Ridge / Regional Park",
    "lda": "Low Density Area (LDA)",
}

#: The phrases that count as a mention of each topic.
#:
#: Case matters. "TOD" and "HDC" are only those short forms in capitals, because the
#: lower-case letters appear inside ordinary words. "Zone O" has to be capital Z and a
#: standalone capital O, so that "zone of", "Zone of" and "TOD Zone or" do not match
#: while "Zone O", "Zone 'O'", "Zone O-1" and "Zone O-2" do.
MENTION_PATTERNS: dict[str, tuple[tuple[str, int], ...]] = {
    "tod": (
        (r"\bTOD\b", 0),
        (r"transit[- ]oriented\s+development", re.I),
    ),
    "hdc": (
        (r"high[- ]density\s+corridor", re.I),
        (r"\bHDC\b", 0),
        (r"\bUER[- ]?II\b", 0),
        (r"urban\s+extension\s+road", re.I),
    ),
    "zone_o": (
        (r"\bZone\s*[‘’'\"]?O\b", 0),
        (r"\bZone\s*[‘’'\"]?O-[12]\b", 0),
        (r"Yamuna\s+flood\s?plain", re.I),
    ),
    "land_pooling": (
        (r"\bland\s+pooling\b", re.I),
        (r"\bpooled\s+land\b", re.I),
    ),
    "ridge": (
        (r"\bridge\b", re.I),
        (r"regional\s+park", re.I),
        (r"\bAravalli", re.I),
    ),
    "lda": (
        (r"\bLDA\b", 0),
        (r"low\s+density\s+(?:area|residential)", re.I),
        (r"\bfarm\s?house", re.I),
    ),
}

#: zone_o also counts when a chunk talks about the river and about flooding together.
#: Kept apart from the patterns above because it is two conditions, not one phrase:
#: "flood plain zone of river" matches neither on its own and must not be tagged.
RIVER_YAMUNA = re.compile(r"\briver\s+Yamuna\b", re.I)
FLOOD = re.compile(r"\bflood", re.I)

COMPILED: dict[str, tuple[re.Pattern[str], ...]] = {
    topic: tuple(re.compile(pattern, flags) for pattern, flags in patterns)
    for topic, patterns in MENTION_PATTERNS.items()
}

#: Which gazette sections are each topic's own policy, by section number.
#: zone_o and ridge are empty on purpose: MPD-2047 has a policy section for neither
#: (D-023, D-037, D-069), so both may boost and expand but never exclude.
DEFAULT_GAZETTE_SECTIONS: dict[str, list[str]] = {
    "tod": ["4.2"],
    "hdc": ["4.3"],
    "zone_o": [],
    "land_pooling": ["4.1"],
    "ridge": [],
    "lda": ["4.4"],
}

#: Phrases that, when they appear in a FAQ section heading, make that section a topic's
#: own policy. The FAQ has no section numbers, so a heading has to be matched on its
#: words (D-038). Only an explicit topic name counts: "FAQs - GENERIC", "FAQs on LDA"
#: and "FAQs - Slum and JJ Clusters" name no topic of ours and stay untagged.
DEFAULT_FAQ_SECTIONS: dict[str, list[str]] = {
    "tod": ["Transit Oriented Development", "TOD Policy"],
    "hdc": ["High Density Corridor", "HDC Policy"],
    "zone_o": [],
    "land_pooling": ["Land Pooling"],
    "ridge": [],
    "lda": ["LDA", "Low Density Area"],
}

#: The doc_id whose sections are matched by heading words rather than section number.
FAQ_DOC_ID = "MPD47_FAQ"

#: A heading path entry starts with its section number: "4.2.1 Definitions".
HEADING_NUMBER = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\s")


@dataclass(frozen=True)
class ZoneSections:
    """Which sections of which document are each topic's own policy.

    Two mappings, because the two documents are numbered differently. The gazette has
    decimal section numbers, so a topic is "4.2" and everything under it. The FAQ has
    none, so a topic is a phrase that has to appear in the section heading.
    """

    gazette: dict[str, list[str]]
    faq: dict[str, list[str]]


def default_zone_sections() -> ZoneSections:
    """The mapping built into this module, used when the JSON file is absent."""
    return ZoneSections(
        gazette={topic: list(sections) for topic, sections in DEFAULT_GAZETTE_SECTIONS.items()},
        faq={topic: list(phrases) for topic, phrases in DEFAULT_FAQ_SECTIONS.items()},
    )


def matches_for(topic: str, text: str) -> list[str]:
    """Every distinct phrase in `text` that counts as a mention of `topic`."""
    found: list[str] = []
    for pattern in COMPILED[topic]:
        for match in pattern.finditer(text):
            phrase = " ".join(match.group(0).split())
            if phrase not in found:
                found.append(phrase)
    if topic == "zone_o" and not found and RIVER_YAMUNA.search(text) and FLOOD.search(text):
        found.append("river Yamuna + flood")
    return found


def mentions_of(text: str) -> dict[str, list[str]]:
    """The topics `text` mentions, each with the phrases that matched."""
    return {topic: found for topic in TOPICS if (found := matches_for(topic, text))}


def heading_numbers(heading_path: list[str]) -> list[str]:
    """The section numbers in a heading path: ["4.2 TOD", "4.2.1 Definitions"] -> ["4.2", "4.2.1"]."""
    numbers = []
    for heading in heading_path:
        match = HEADING_NUMBER.match(heading)
        if match:
            numbers.append(match.group(1))
    return numbers


def primary_zone(chunk: dict, zone_sections: ZoneSections) -> str:
    """The topic whose own policy section this chunk sits in, or "" for none.

    In the gazette, only the plan's numbered chapters are considered. The nine service
    plans in the back number their own sections from 1.1 as well, so a sewerage section
    numbered "4.2" there would otherwise be read as the TOD policy.

    In the FAQ there are no section numbers, so the section heading is matched on its
    words instead: "FAQs - Transit Oriented Development (TOD) Policy" is the TOD policy,
    while "FAQs - GENERIC" names no topic and stays untagged (D-038).

    Topics are checked in a fixed order, so a heading that named two topics would take
    the first; nothing in this corpus does.
    """
    if chunk.get("doc_id") == FAQ_DOC_ID:
        heading = chunk["heading_path"][0] if chunk["heading_path"] else ""
        for topic in TOPICS:
            phrases = zone_sections.faq.get(topic, [])
            if any(phrase.lower() in heading.lower() for phrase in phrases):
                return topic
        return ""
    if not chunk["chapter"].isdigit():
        return ""
    numbers = heading_numbers(chunk["heading_path"])
    for topic in TOPICS:
        for section in zone_sections.gazette.get(topic, []):
            if any(number == section or number.startswith(section + ".") for number in numbers):
                return topic
    return ""


def tag_chunk(chunk: dict, zone_sections: ZoneSections) -> dict:
    """Return the zone fields for one chunk: the primary zone, the mentions, the flags.

    `zm_*` is true when the topic is mentioned **or** is the chunk's primary zone, so a
    search can ask one question — "is this chunk about my zone at all?" — with one field.
    """
    primary = primary_zone(chunk, zone_sections)
    found = mentions_of(chunk["text"])
    fields: dict = {
        "zone_primary": primary,
        "zone_mentions": [topic for topic in TOPICS if topic in found],
    }
    for topic in TOPICS:
        fields[f"zp_{topic}"] = primary == topic
        fields[f"zm_{topic}"] = topic in found or primary == topic
    return fields


def tag_chunks(chunks: list[dict], zone_sections: ZoneSections) -> list[dict]:
    """Add the zone fields to every chunk, in place, and return the list."""
    for chunk in chunks:
        chunk.update(tag_chunk(chunk, zone_sections))
    return chunks


def load_zone_sections(path: Path) -> ZoneSections:
    """Read data/zone_sections.json, falling back to the mapping built into this module.

    A file written before the FAQ mapping existed held one topic -> sections map at the
    top level. It is read as the gazette half, with the FAQ half taken from the
    defaults, so an old file still loads.
    """
    if not path.exists():
        return default_zone_sections()
    stored = json.loads(path.read_text(encoding="utf-8"))
    if "gazette_sections" in stored:
        phrases = stored.get("faq_section_phrases", {})
        return ZoneSections(
            gazette={topic: list(stored["gazette_sections"].get(topic, [])) for topic in TOPICS},
            faq={topic: list(phrases.get(topic, [])) for topic in TOPICS},
        )
    return ZoneSections(
        gazette={topic: list(stored.get(topic, [])) for topic in TOPICS},
        faq={topic: list(found) for topic, found in DEFAULT_FAQ_SECTIONS.items()},
    )


ZONE_SECTIONS_NOTE = (
    "Which sections are each zone topic's own policy. zone_primary is set from this, "
    "and it is the only tag search may exclude on, so a section listed here has to be "
    "a rule that applies inside that zone and nowhere else. gazette_sections are "
    "section numbers, and a number also covers everything under it, so 4.2 covers "
    "4.2.1. faq_section_phrases are matched against a FAQ section heading, "
    "case-insensitively, and only an explicit topic name counts. zone_o and ridge are "
    "empty in both halves: MPD-2047 has a policy section for neither, so both boost a "
    "result and expand a query but never exclude. The Ridge is named in chapter 10's "
    "recreational norms and in 3.1.2 Green-Blue Infrastructure, and both of those are "
    "about every park or green asset in Delhi rather than about the Ridge, so listing "
    "either would let search drop general park norms for an ordinary plot. "
    "See D-023, D-024, D-037, D-038 and D-069."
)


def write_zone_sections(path: Path, zone_sections: ZoneSections) -> None:
    """Write data/zone_sections.json, with a note saying what each half is for."""
    document = {
        "_note": ZONE_SECTIONS_NOTE,
        "gazette_sections": zone_sections.gazette,
        "faq_section_phrases": zone_sections.faq,
    }
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
