"""Tag each chunk with the planning-zone topics it is about, so a point can filter search.

ZoneWise answers questions about a point on the map, and four of the plan's policies are
the ones that depend on where you are standing:

  tod            Transit Oriented Development, the 500 m band along metro corridors
  hdc            the High Density Corridor, including the UER-II corridor
  zone_o         the Yamuna floodplain: planning zone O, and O-1 / O-2
  land_pooling   the land pooling areas

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
from pathlib import Path

#: The four topics, in the order they are reported.
TOPICS = ("tod", "hdc", "zone_o", "land_pooling")

#: How each topic is named back to a reader, and in a query expansion.
TOPIC_NAMES = {
    "tod": "Transit Oriented Development (TOD)",
    "hdc": "High Density Corridor (HDC)",
    "zone_o": "Zone O (Yamuna floodplain)",
    "land_pooling": "Land Pooling",
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

#: Which gazette sections are each topic's own policy. Written to data/zone_sections.json.
#: zone_o is empty on purpose: MPD-2047 has no Zone O policy section (see D-023).
DEFAULT_ZONE_SECTIONS: dict[str, list[str]] = {
    "tod": ["4.2"],
    "hdc": ["4.3"],
    "zone_o": [],
    "land_pooling": ["4.1"],
}

#: A heading path entry starts with its section number: "4.2.1 Definitions".
HEADING_NUMBER = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\s")


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


def primary_zone(chunk: dict, zone_sections: dict[str, list[str]]) -> str:
    """The topic whose own policy section this chunk sits in, or "" for none.

    Only the plan's numbered chapters are considered. The nine service plans in the back
    of the gazette number their own sections from 1.1 as well, so a sewerage section
    numbered "4.2" there would otherwise be read as the TOD policy.
    """
    if not chunk["chapter"].isdigit():
        return ""
    numbers = heading_numbers(chunk["heading_path"])
    for topic in TOPICS:
        for section in zone_sections.get(topic, []):
            if any(number == section or number.startswith(section + ".") for number in numbers):
                return topic
    return ""


def tag_chunk(chunk: dict, zone_sections: dict[str, list[str]]) -> dict:
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


def tag_chunks(chunks: list[dict], zone_sections: dict[str, list[str]]) -> list[dict]:
    """Add the zone fields to every chunk, in place, and return the list."""
    for chunk in chunks:
        chunk.update(tag_chunk(chunk, zone_sections))
    return chunks


def load_zone_sections(path: Path) -> dict[str, list[str]]:
    """Read data/zone_sections.json, falling back to the mapping built into this module."""
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        return {topic: list(stored.get(topic, [])) for topic in TOPICS}
    return {topic: list(sections) for topic, sections in DEFAULT_ZONE_SECTIONS.items()}


def write_zone_sections(path: Path, zone_sections: dict[str, list[str]]) -> None:
    """Write data/zone_sections.json."""
    path.write_text(
        json.dumps(zone_sections, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
