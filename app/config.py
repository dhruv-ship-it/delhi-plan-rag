"""Project settings: where things live on disk, and the few values other modules need."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Paths and config values for ZoneWise, resolved once when this module is imported."""

    project_root: Path
    raw_dir: Path
    reference_dir: Path
    processed_dir: Path
    layers_dir: Path
    dda_layers_dir: Path
    index_dir: Path
    model_cache_dir: Path
    chroma_dir: Path
    reports_dir: Path
    sources_csv: Path
    anthropic_api_key: str | None
    llm_model: str

    # --- search ---------------------------------------------------------------
    #: The embedding model. Small (133 MB), fast on a laptop CPU, 384 dimensions.
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    #: The Chroma collection holding the chunk vectors.
    collection_name: str = "chunks"
    #: How many results dense and keyword search each contribute before fusion.
    retrieval_pool: int = 30
    #: How many results a search returns by default.
    default_k: int = 6
    #: Reciprocal rank fusion's smoothing constant (see D-028).
    rrf_k: int = 60

    # --- location-aware search (Stage 6) --------------------------------------
    #: How much a chunk about the point's own zone has its fused score multiplied by.
    zone_boost: float = 1.5
    #: Whether a chunk whose primary zone the point is not in is dropped.
    zone_exclusion: bool = True
    #: Whether the point's zone names are appended to the query text.
    zone_query_expansion: bool = True

    @property
    def bm25_path(self) -> Path:
        """Where the pickled BM25 model lives."""
        return self.index_dir / "bm25.pkl"


settings = Settings(
    project_root=PROJECT_ROOT,
    raw_dir=DATA_DIR / "raw",
    reference_dir=DATA_DIR / "reference",
    processed_dir=DATA_DIR / "processed",
    layers_dir=DATA_DIR / "layers",
    dda_layers_dir=DATA_DIR / "layers" / "dda",
    index_dir=DATA_DIR / "index",
    model_cache_dir=DATA_DIR / "index" / "models",
    chroma_dir=DATA_DIR / "index" / "chroma",
    reports_dir=PROJECT_ROOT / "reports",
    sources_csv=DATA_DIR / "sources.csv",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    llm_model="claude-haiku-5-5",
)
