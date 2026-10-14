"""Build both search indexes from the chunks: dense vectors in Chroma, keywords in BM25.

Reads  data/processed/chunks.jsonl
Writes data/index/chroma/   the Chroma collection "chunks" (cosine distance)
       data/index/bm25.pkl  the BM25 model and the chunk order its scores are in
       data/index/models/   the downloaded embedding model weights (first run only)

Safe to re-run: the Chroma collection is dropped and recreated through the client, and
the pickle is overwritten. The first run downloads about 130 MB of model weights.

Run with: uv run python scripts/05_build_index.py
"""

import sys

from app.config import settings
from app.extract import use_utf8_output
from app.indexing import (
    build_bm25_index,
    build_dense_index,
    chroma_client,
    folder_size,
    human_size,
    open_collection,
    read_chunks,
    save_bm25,
    tokenize,
)


def main() -> int:
    """Build both indexes and print what was built, how long it took and how big it is."""
    use_utf8_output()
    chunks_path = settings.processed_dir / "chunks.jsonl"
    if not chunks_path.exists():
        print(f"{chunks_path.as_posix()} is missing. Run: uv run python scripts/03_chunk.py")
        return 1

    chunks = read_chunks(chunks_path)
    if not chunks:
        print(f"{chunks_path.as_posix()} is empty. Nothing to index.")
        return 1
    if "zone_primary" not in chunks[0]:
        print("The chunks carry no zone tags. Run: uv run python scripts/04_tag_zones.py")
        return 1

    print(f"{len(chunks)} chunks to index from {chunks_path.relative_to(settings.project_root).as_posix()}")
    print()

    print(f"dense: embedding with {settings.embedding_model} (first run downloads the model)")
    model_was_cached = settings.model_cache_dir.exists()
    written, embed_seconds = build_dense_index(chunks)
    print(
        f"  {written} vectors in Chroma collection {settings.collection_name!r} "
        f"in {embed_seconds:.1f}s ({written / max(embed_seconds, 0.001):.0f} chunks/s)"
    )
    if not model_was_cached:
        print(f"  model cached in {settings.model_cache_dir.relative_to(settings.project_root).as_posix()}")

    print("keyword: BM25Okapi over embed_text")
    bm25, chunk_ids, bm25_seconds = build_bm25_index(chunks)
    save_bm25(bm25, chunk_ids, settings.bm25_path)
    vocabulary = len({token for chunk in chunks for token in tokenize(chunk["embed_text"])})
    print(
        f"  {len(chunk_ids)} documents, {vocabulary:,} distinct tokens, "
        f"built in {bm25_seconds:.1f}s"
    )

    client = chroma_client()
    stored = open_collection(client).count()
    print()
    print("index sizes on disk:")
    for label, path in (
        ("chroma", settings.chroma_dir),
        ("bm25.pkl", settings.bm25_path),
        ("model weights", settings.model_cache_dir),
    ):
        print(f"  {label:<14} {human_size(folder_size(path)):>9}  {path.relative_to(settings.project_root).as_posix()}")

    print()
    print(f"{stored} chunks indexed in both indexes.")
    if stored != len(chunks):
        print(f"WARNING: Chroma holds {stored} vectors but there are {len(chunks)} chunks.")
        return 1
    print("Next: uv run python scripts/search.py \"minimum plot size for a TOD project\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
