"""Tag every chunk with the planning-zone topics it is about, and write it back.

Reads  data/processed/chunks.jsonl, data/zone_sections.json (written if absent)
Writes data/processed/chunks.jsonl   the same chunks, with the zone fields added
       data/processed/tag_report.md  counts per topic, primary against mentions
       data/processed/tag_sample.md  30 random tagged chunks for hand review

Safe to re-run: the zone fields are recomputed from scratch each time, so running this
twice gives the same file.

Run with: uv run python scripts/04_tag_zones.py
"""

import json
import random
import sys
from datetime import date

from app.config import settings
from app.extract import markdown_table, use_utf8_output
from app.tagging import (
    FAQ_DOC_ID,
    TOPIC_NAMES,
    TOPICS,
    load_zone_sections,
    matches_for,
    tag_chunks,
    write_zone_sections,
)

SAMPLE_SEED = 7
SAMPLE_SIZE = 30
#: How many of the sample must come from each topic, where there are that many.
PER_TOPIC_MINIMUM = 5
#: How much of a chunk's text the sample shows.
SAMPLE_CHARS = 300


def choose_sample(chunks: list[dict]) -> list[dict]:
    """Pick 30 tagged chunks at random, with at least 5 per topic where possible.

    Each topic's quota is filled first, from the chunks that mention it, then the rest
    is filled from everything else that carries any tag.
    """
    rng = random.Random(SAMPLE_SEED)
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    for topic in TOPICS:
        pool = [
            chunk
            for chunk in chunks
            if chunk[f"zm_{topic}"] and chunk["chunk_id"] not in chosen_ids
        ]
        for chunk in rng.sample(pool, min(PER_TOPIC_MINIMUM, len(pool))):
            chosen.append(chunk)
            chosen_ids.add(chunk["chunk_id"])

    rest = [
        chunk
        for chunk in chunks
        if chunk["zone_mentions"] or chunk["zone_primary"]
        if chunk["chunk_id"] not in chosen_ids
    ]
    rng.shuffle(rest)
    for chunk in rest:
        if len(chosen) >= SAMPLE_SIZE:
            break
        chosen.append(chunk)
        chosen_ids.add(chunk["chunk_id"])

    chosen.sort(key=lambda chunk: chunk["chunk_id"])
    return chosen


def build_report(
    chunks: list[dict], zone_sections, generated_on: str
) -> str:
    """The tag report: the section mapping, then counts per topic and per document."""
    tagged = [chunk for chunk in chunks if chunk["zone_primary"] or chunk["zone_mentions"]]
    lines = [
        "# Zone tag report",
        "",
        f"Generated {generated_on} by `scripts/04_tag_zones.py`.",
        "",
        f"{len(chunks)} chunks, of which {len(tagged)} "
        f"({len(tagged) / max(1, len(chunks)):.1%}) carry at least one zone tag.",
        "",
        "## The two kinds of tag",
        "",
        "`zone_primary` is the one topic whose own policy section a chunk sits in, taken "
        "from its heading path. It is a strong claim, and it is the only tag search is "
        "allowed to **exclude** on: a chunk whose primary zone is TOD is a rule that "
        "applies inside the TOD zone and nowhere else.",
        "",
        "`zone_mentions` is every topic a chunk's text names. It is a weak claim, used "
        "only to **boost**: section 4.6.1 lists Zone O among the areas it does not apply "
        "to, so a mention is a reason to rank a chunk higher for a point in that zone and "
        "never a reason to drop it for a point outside.",
        "",
        "## Sections that are each topic's own policy (data/zone_sections.json)",
        "",
        "The gazette is matched by section number, and a number covers everything under "
        "it, so 4.2 covers 4.2.1. The FAQ has no section numbers, so its section "
        "headings are matched on words, and only an explicit topic name counts (D-038).",
        "",
    ]

    rows = []
    for topic in TOPICS:
        sections = zone_sections.gazette.get(topic, [])
        phrases = zone_sections.faq.get(topic, [])
        rows.append(
            [
                topic,
                TOPIC_NAMES[topic],
                ", ".join(sections) if sections else "(none)",
                ", ".join(f'"{phrase}"' for phrase in phrases) if phrases else "(none)",
            ]
        )
    lines += [
        markdown_table(("topic", "name", "gazette sections", "FAQ heading phrases"), rows),
        "",
    ]

    faq_headings: dict[str, str] = {}
    for item in chunks:
        if item["doc_id"] == FAQ_DOC_ID and item["heading_path"]:
            faq_headings.setdefault(item["heading_path"][0], item["zone_primary"])
    lines += [
        "Every FAQ section heading in the indexed range, and what it was tagged as:",
        "",
        markdown_table(
            ("FAQ section heading", "zone_primary"),
            [
                [heading, primary or "(none)"]
                for heading, primary in sorted(faq_headings.items())
            ],
        ),
        "",
    ]
    lines += [
        "`zone_o` has no sections. MPD-2047 has no Zone O policy: planning zone O is "
        "defined in 1.7.2 as \"River Yamuna / Riverfront\", one of the 17 planning zones, "
        "and from there on the plan names it only in the exclusion list of other "
        "policies — \"this shall not apply to ... Zone 'O'\" in 4.2.2, 4.5.1 and 4.6.1, "
        "and \"all Use Zones except ... Zone O\" in 11.1.1. The nearest thing to a "
        "floodplain policy is 3.1.2 Green-Blue Infrastructure, which carries the "
        "\"active floodplain shall be a no construction zone\" rule, but that section is "
        "about every green and blue asset in Delhi, not about Zone O, so claiming it "
        "would let search drop it for any point outside the floodplain. Zone O therefore "
        "works through mentions alone, which can only help a result and never lose one.",
        "",
        "## Counts per topic",
        "",
    ]

    rows = []
    for topic in TOPICS:
        primary = sum(1 for chunk in chunks if chunk[f"zp_{topic}"])
        mentions = sum(1 for chunk in chunks if topic in chunk["zone_mentions"])
        either = sum(1 for chunk in chunks if chunk[f"zm_{topic}"])
        rows.append([topic, TOPIC_NAMES[topic], str(primary), str(mentions), str(either)])
    lines += [
        markdown_table(
            ("topic", "name", "zone_primary", "mentioned in text", "either (zm_*)"), rows
        ),
        "",
        "## Where the tagged chunks are",
        "",
    ]

    rows = []
    for doc_id in dict.fromkeys(chunk["doc_id"] for chunk in chunks):
        mine = [chunk for chunk in chunks if chunk["doc_id"] == doc_id]
        rows.append(
            [doc_id, str(len(mine))]
            + [str(sum(1 for chunk in mine if chunk[f"zm_{topic}"])) for topic in TOPICS]
        )
    lines += [
        markdown_table(("doc_id", "chunks") + tuple(f"zm_{topic}" for topic in TOPICS), rows),
        "",
    ]

    rows = []
    gazette = [chunk for chunk in chunks if chunk["doc_id"] == "MPD47_GAZETTE_EN"]
    for chapter in dict.fromkeys(chunk["chapter"] for chunk in gazette):
        mine = [chunk for chunk in gazette if chunk["chapter"] == chapter]
        counts = [sum(1 for chunk in mine if chunk[f"zm_{topic}"]) for topic in TOPICS]
        if any(counts):
            rows.append([chapter, str(len(mine))] + [str(count) for count in counts])
    lines += [
        "Chapters of MPD47_GAZETTE_EN with at least one tagged chunk:",
        "",
        markdown_table(("chapter", "chunks") + tuple(f"zm_{topic}" for topic in TOPICS), rows),
        "",
        "## Chunks carrying a primary zone",
        "",
    ]
    for topic in TOPICS:
        primary = [chunk for chunk in chunks if chunk[f"zp_{topic}"]]
        if not primary:
            continue
        lines.append(f"**{topic}** — {len(primary)} chunks:")
        lines.append("")
        for chunk in primary:
            lines.append(
                f"- `{chunk['chunk_id']}` pages {chunk['page_start']}-{chunk['page_end']}: "
                f"{' › '.join(chunk['heading_path'])}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_sample(chunks: list[dict], generated_on: str) -> str:
    """30 tagged chunks with their tags, the phrases that matched, and the text opening."""
    chosen = choose_sample(chunks)
    lines = [
        "# Zone tag sample",
        "",
        f"Generated {generated_on} by `scripts/04_tag_zones.py`: {len(chosen)} tagged "
        f"chunks drawn at random with seed {SAMPLE_SEED}, at least "
        f"{PER_TOPIC_MINIMUM} per topic where there are that many.",
        "",
        "Check two things by hand. Is every matched phrase a real mention of that zone, "
        "or did a regex fire on something else? And where a chunk has a `zone_primary`, "
        "is it really a rule that applies only inside that zone — because search is "
        "allowed to drop it for a point outside.",
        "",
    ]
    for index, chunk in enumerate(chosen, start=1):
        matched = {
            topic: matches_for(topic, chunk["text"])
            for topic in TOPICS
            if topic in chunk["zone_mentions"]
        }
        text = chunk["text"].replace("\n", " ")
        lines += [
            f"## {index}. `{chunk['chunk_id']}`",
            "",
            f"- {chunk['doc_id']}, chapter {chunk['chapter'] or '(none)'}, "
            f"pages {chunk['page_start']}-{chunk['page_end']}",
            f"- heading path: {' › '.join(chunk['heading_path']) or '(none)'}",
            f"- zone_primary: **{chunk['zone_primary'] or '(none)'}**",
            f"- zone_mentions: {', '.join(chunk['zone_mentions']) or '(none)'}",
            "- matched phrases: "
            + (
                "; ".join(f"{topic}: {', '.join(repr(p) for p in found)}" for topic, found in matched.items())
                or "(none)"
            ),
            "",
            "> " + (text[:SAMPLE_CHARS] + ("..." if len(text) > SAMPLE_CHARS else "")),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    """Tag the chunks, write them back, write the two reports and print a summary."""
    use_utf8_output()
    chunks_path = settings.processed_dir / "chunks.jsonl"
    if not chunks_path.exists():
        print(f"{chunks_path.as_posix()} is missing. Run: uv run python scripts/03_chunk.py")
        return 1

    sections_path = settings.project_root / "data" / "zone_sections.json"
    first_time = not sections_path.exists()
    zone_sections = load_zone_sections(sections_path)
    write_zone_sections(sections_path, zone_sections)
    if first_time:
        print(f"wrote {sections_path.relative_to(settings.project_root).as_posix()} "
              "(the mapping built into app/tagging.py)")

    with chunks_path.open(encoding="utf-8") as handle:
        chunks = [json.loads(line) for line in handle if line.strip()]
    tag_chunks(chunks, zone_sections)

    with chunks_path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    generated_on = date.today().isoformat()
    report_path = settings.processed_dir / "tag_report.md"
    report_path.write_text(build_report(chunks, zone_sections, generated_on), encoding="utf-8")
    sample_path = settings.processed_dir / "tag_sample.md"
    sample_path.write_text(build_sample(chunks, generated_on), encoding="utf-8")

    print()
    print(f"{len(chunks)} chunks tagged.")
    rows = []
    for topic in TOPICS:
        rows.append(
            (
                topic,
                sum(1 for chunk in chunks if chunk[f"zp_{topic}"]),
                sum(1 for chunk in chunks if topic in chunk["zone_mentions"]),
                ", ".join(zone_sections.gazette[topic] + zone_sections.faq[topic])
                or "(no policy section)",
            )
        )
    width = max(len(topic) for topic, *_ in rows)
    print(f"{'topic'.ljust(width)} | primary | mentions | sections")
    for topic, primary, mentions, sections in rows:
        print(f"{topic.ljust(width)} | {primary:>7} | {mentions:>8} | {sections}")
    tagged = sum(1 for chunk in chunks if chunk["zone_primary"] or chunk["zone_mentions"])
    print(f"{tagged} chunks carry at least one tag ({tagged / len(chunks):.1%}).")
    for path in (chunks_path, sections_path, report_path, sample_path):
        print(f"wrote {path.relative_to(settings.project_root).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
