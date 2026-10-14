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
    index_dir: Path
    sources_csv: Path
    anthropic_api_key: str | None
    llm_model: str


settings = Settings(
    project_root=PROJECT_ROOT,
    raw_dir=DATA_DIR / "raw",
    reference_dir=DATA_DIR / "reference",
    processed_dir=DATA_DIR / "processed",
    layers_dir=DATA_DIR / "layers",
    index_dir=DATA_DIR / "index",
    sources_csv=DATA_DIR / "sources.csv",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    llm_model="claude-haiku-5-5",
)
