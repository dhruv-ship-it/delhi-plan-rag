"""Build and open the two search indexes: dense vectors in Chroma, keywords in BM25.

ZoneWise searches twice for every question and fuses the results, because the two
indexes fail in different places. The dense index matches meaning, so "how wide is the
TOD zone" reaches a clause that says "area under 500m wide corridor on either side of
centreline" without sharing a word with it. The keyword index matches exact strings, so
"4.2.1", "FAR", "2000 sqm" and "UER-II" land on the clause that carries them, which an
embedding blurs away.

Both indexes are built over `embed_text`, which is the chunk text with one breadcrumb
line above it (see D-022), so both see the same thing.

Nothing here ranks or fuses; that is app/retrieval.py.
"""

import json
import pickle
import re
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from app.config import settings
from app.tagging import TOPICS

# --- the keyword tokenizer ------------------------------------------------------

#: A run of letters and digits, which may carry dots inside it so that a clause number
#: survives as one token. The dotted form is only kept when every part is digits.
RAW_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")
CLAUSE_NUMBER = re.compile(r"^\d+(?:\.\d+)+$")

#: A short English stopword list, written out rather than pulled from a library so the
#: project gains no dependency for 40 words (see D-027).
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been
    before being below between both but by can cannot could did do does doing down
    during each few for from further had has have having he her here hers herself him
    himself his how i if in into is it its itself me more most my myself no nor not of
    off on once only or other ought our ours ourselves out over own same she should so
    some such than that the their theirs them themselves then there these they this
    those through to too under until up very was we were what when where which while
    who whom why will with would you your yours yourself yourselves
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Split text into keyword-search tokens: lower case, stopwords removed.

    A clause number stays whole, so a search for "4.2.1" finds the clause numbered
    4.2.1 and not every chunk that happens to contain a 4, a 2 and a 1. Anything else
    that picked up a dot is split on it, because "policy.The" at a sentence join is two
    words, not one.
    """
    tokens: list[str] = []
    for raw in RAW_TOKEN.findall(text.lower()):
        if CLAUSE_NUMBER.match(raw):
            tokens.append(raw)
        else:
            tokens.extend(part for part in raw.split(".") if part)
    return [token for token in tokens if token not in STOPWORDS]


# --- reading the chunks --------------------------------------------------------


def read_chunks(path: Path) -> list[dict]:
    """Read data/processed/chunks.jsonl."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def chunk_metadata(chunk: dict) -> dict:
    """The scalar fields Chroma stores next to a vector, so results can be filtered.

    Chroma metadata takes strings, numbers and booleans only, so `clause_id` becomes ""
    when there is none, and the lists (`heading_path`, `clause_ids`, `zone_mentions`)
    are left out — they are read back from chunks.jsonl at search time.
    """
    metadata = {
        "doc_id": chunk["doc_id"],
        "doc_type": chunk["doc_type"],
        "authority_rank": int(chunk["authority_rank"]),
        "chapter": chunk["chapter"],
        "clause_id": chunk["clause_id"] or "",
        "page_start": int(chunk["page_start"]),
        "page_end": int(chunk["page_end"]),
        "has_table": bool(chunk["has_table"]),
        "zone_primary": chunk["zone_primary"],
    }
    for topic in TOPICS:
        metadata[f"zp_{topic}"] = bool(chunk[f"zp_{topic}"])
        metadata[f"zm_{topic}"] = bool(chunk[f"zm_{topic}"])
    return metadata


# --- the dense index -----------------------------------------------------------


def embedder():
    """Open the fastembed model, caching its weights under data/index/models.

    Imported lazily: fastembed pulls in onnxruntime and tokenizers, which take a couple
    of seconds, and nothing that only needs the keyword index should pay for that.
    """
    from fastembed import TextEmbedding

    settings.model_cache_dir.mkdir(parents=True, exist_ok=True)
    return TextEmbedding(
        model_name=settings.embedding_model,
        cache_dir=str(settings.model_cache_dir),
    )


def chroma_client() -> chromadb.ClientAPI:
    """Open the persistent Chroma store at data/index/chroma, with telemetry off."""
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )


def fresh_collection(client: chromadb.ClientAPI):
    """Delete and recreate the chunks collection, cosine distance, no embedding function.

    The collection is dropped through the client rather than by deleting the folder:
    on Windows the SQLite file is locked while the client is open, so removing the
    directory from under it fails or leaves a half-written store behind.
    """
    try:
        client.delete_collection(settings.collection_name)
    except Exception:
        pass  # nothing to delete on a first run
    return client.create_collection(
        name=settings.collection_name,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )


def open_collection(client: chromadb.ClientAPI):
    """Open the existing chunks collection for searching."""
    return client.get_collection(settings.collection_name, embedding_function=None)


#: How many chunks are embedded and written to Chroma at a time.
#:
#: 32, not 128, and the reason is arithmetic rather than taste. onnxruntime runs a batch
#: as one tensor, and the attention node for BAAI/bge-small-en-v1.5 needs
#: batch x 12 heads x 512 tokens x 512 tokens x 4 bytes. At 128 that is 1.5 GiB in one
#: allocation, which this laptop refused outright once the chunks got long enough to
#: reach the 512-token cap ("Failed to allocate memory for requested buffer of size
#: 1610612736"). At 32 the same tensor is 402 MiB and the whole build still takes about
#: the same time, because the model is CPU-bound rather than batch-bound here (D-066).
BATCH_SIZE = 32


def build_dense_index(chunks: list[dict], batch_size: int = BATCH_SIZE) -> tuple[int, float]:
    """Embed every chunk's embed_text and store it in Chroma. Returns (count, seconds).

    `passage_embed` is used here and `query_embed` at search time, because BGE models
    are trained with different instructions for the two sides.
    """
    model = embedder()
    client = chroma_client()
    collection = fresh_collection(client)

    started = time.perf_counter()
    written = 0
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = [vector.tolist() for vector in model.passage_embed([c["embed_text"] for c in batch])]
        collection.add(
            ids=[chunk["chunk_id"] for chunk in batch],
            embeddings=vectors,
            documents=[chunk["embed_text"] for chunk in batch],
            metadatas=[chunk_metadata(chunk) for chunk in batch],
        )
        written += len(batch)
    return written, time.perf_counter() - started


def embed_query(text: str) -> list[float]:
    """Embed one query with the query-side instruction."""
    model = embedder()
    return next(iter(model.query_embed([text]))).tolist()


# --- the keyword index ---------------------------------------------------------


def build_bm25_index(chunks: list[dict]) -> tuple[BM25Okapi, list[str], float]:
    """Build the BM25 model over embed_text. Returns (model, chunk ids in order, seconds)."""
    started = time.perf_counter()
    corpus = [tokenize(chunk["embed_text"]) for chunk in chunks]
    model = BM25Okapi(corpus)
    return model, [chunk["chunk_id"] for chunk in chunks], time.perf_counter() - started


def save_bm25(model: BM25Okapi, chunk_ids: list[str], path: Path) -> None:
    """Pickle the BM25 model together with the chunk order its scores are in.

    The order has to travel with the model: BM25Okapi scores by corpus position, so a
    score array means nothing without the list that says which chunk each slot is.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(
            {"model": model, "chunk_ids": chunk_ids, "embedding_model": settings.embedding_model},
            handle,
            protocol=pickle.HIGHEST_PROTOCOL,
        )


def load_bm25(path: Path) -> tuple[BM25Okapi, list[str]]:
    """Read the pickled BM25 model and its chunk order back."""
    with path.open("rb") as handle:
        stored = pickle.load(handle)
    return stored["model"], stored["chunk_ids"]


# --- sizes on disk -------------------------------------------------------------


def folder_size(path: Path) -> int:
    """Total bytes of every file under a folder, 0 when it does not exist."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def human_size(size: int) -> str:
    """Bytes as a short string a person can read."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
