"""Every path and tuning value in one place, resolved once when this module is imported.

Nothing else in ZoneWise builds a path by hand or hard-codes a threshold. That matters
most for the numbers that will need tuning later: `abstain_threshold` is a placeholder
(D-042) that Day 5 will replace from the evaluation sweep, and `zone_boost`,
`retrieval_pool` and `rrf_k` are the knobs the retrieval experiments turn. Having them
here means an experiment changes one file and a report can state exactly what was set.

The API key is read from `.env`, which is never committed. `looks_like_api_key()` is
deliberately stricter than a truthiness check: `.env.example` ships the placeholder
`your-key-here`, so a copied-but-unedited `.env` would otherwise read as a configured
key and turn an honest "no key yet" into a confusing 401 (D-040).

Every setting a deployment might need to change is read from the environment through the
four `env_*` readers below, each with the value in this file as its default, so a
container is configured with variables and nothing has to be edited inside the image
(D-063, D-065). A malformed value falls back to the default rather than stopping the
process: a typo in `RATE_LIMIT_PER_MINUTE` should not take the server down.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

load_dotenv(PROJECT_ROOT / ".env")

#: Anthropic keys start with this and are far longer than any placeholder.
API_KEY_PREFIX = "sk-ant-"
API_KEY_MIN_LENGTH = 40


def looks_like_api_key(key: str | None) -> bool:
    """True only for something that could be a real Anthropic key.

    `.env.example` ships `ANTHROPIC_API_KEY=your-key-here`, and a copied-but-unedited
    `.env` is the normal state of this repo before Day 4. A truthiness check would read
    that placeholder as a key, build a client with it, and turn an honest "no key yet"
    into a confusing 401 from a call that never had a chance (see D-040).
    """
    text = (key or "").strip()
    return text.startswith(API_KEY_PREFIX) and len(text) >= API_KEY_MIN_LENGTH


def env_str(name: str, default: str) -> str:
    """An environment variable as text, or `default` when it is unset or blank."""
    return (os.getenv(name) or "").strip() or default


def env_int(name: str, default: int) -> int:
    """An environment variable as a whole number, or `default` when it will not parse."""
    try:
        return int(env_str(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    """An environment variable as a number, or `default` when it will not parse."""
    try:
        return float(env_str(name, str(default)))
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    """An environment variable as a flag. "1", "true" and "yes" are true, anything else false."""
    text = (os.getenv(name) or "").strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str]) -> list[str]:
    """An environment variable as a comma-separated list, trimmed, blanks dropped."""
    text = (os.getenv(name) or "").strip()
    if not text:
        return list(default)
    return [part.strip() for part in text.split(",") if part.strip()]


#: The default Anthropic model. Haiku because the answering job is short, extractive and
#: bounded by the retrieved sources, so the smallest current model is the right one to
#: pay for; `LLM_MODEL` in .env overrides it without a code change (D-063).
DEFAULT_LLM_MODEL = "claude-haiku-5-5"


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

    # --- location-aware search ------------------------------------------------
    #: How much a chunk about the point's own zone has its fused score multiplied by.
    zone_boost: float = 1.5
    #: Whether a chunk whose primary zone the point is not in is dropped.
    zone_exclusion: bool = True
    #: Whether the point's zone names are appended to the query text.
    zone_query_expansion: bool = True

    # --- answering ------------------------------------------------------------
    #: Below this fused score we do not ask the model at all, we abstain.
    #: PLACEHOLDER, to be tuned on Day 5 against the verified question set — the value
    #: here is a guess, not a measurement. See D-042.
    abstain_threshold: float = 0.02
    #: How many words the model may use for an answer.
    answer_max_tokens: int = 900
    #: Answers are deterministic: the same sources and question give the same words.
    answer_temperature: float = 0.0
    #: One retry with a stricter reminder when the citation check fails. See D-044.
    citation_retries: int = 1
    #: True forces the FakeLLM everywhere, even if a real key is present.
    use_fake_llm: bool = False

    # --- the agent ------------------------------------------------------------
    #: How many rounds of tool calling the agent may take before it has to answer.
    agent_max_rounds: int = 4
    #: Nominatim asks for no more than one request a second, and we identify ourselves.
    geocode_url: str = "https://nominatim.openstreetmap.org/search"
    geocode_user_agent: str = "ZoneWise/0.1 (student project)"
    geocode_min_interval_s: float = 1.0
    geocode_timeout_s: int = 30

    # --- the API --------------------------------------------------------------
    #: Where the web dev server runs, which is the only origin CORS allows.
    cors_origin: str = "http://localhost:5173"
    #: Asks per IP per minute, and for the whole service per day. See D-049.
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 300
    #: How much a map layer is simplified before it is sent to the browser, in degrees.
    layer_simplify_tolerance: float = 0.0005

    @property
    def bm25_path(self) -> Path:
        """Where the pickled BM25 model lives."""
        return self.index_dir / "bm25.pkl"

    @property
    def geocode_cache_path(self) -> Path:
        """Where geocoded place names are remembered between runs."""
        return self.index_dir / "geocode_cache.json"

    @property
    def requests_log_path(self) -> Path:
        """Where every ask, agent and search request is logged."""
        return DATA_DIR / "logs" / "requests.jsonl"

    @property
    def web_dist_dir(self) -> Path:
        """The built frontend, served at / when it exists."""
        return self.project_root / "web" / "dist"

    @property
    def has_api_key(self) -> bool:
        """True only when a real-looking Anthropic key is configured. See D-040."""
        return looks_like_api_key(self.anthropic_api_key)

    @property
    def llm_available(self) -> bool:
        """True when an answer can actually be produced: a real key, or the fake client."""
        return self.use_fake_llm or self.has_api_key


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
    llm_model=env_str("LLM_MODEL", DEFAULT_LLM_MODEL),
    use_fake_llm=os.getenv("ZONEWISE_USE_FAKE_LLM", "").strip().lower()
    in {"1", "true", "yes"},
)
