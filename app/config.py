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

`SUPPORT_CHECK` picks what the semantic claim check does with its verdicts — `off`,
`shadow` or `enforce`. `enforce` is the default since the human checks read a run of
shadow verdicts and found no sentence wrongly dropped (D-096, D-103).

There are two providers. `LLM_PROVIDER` picks one — `anthropic` or `groq` — and the
key check, the default model and `has_api_key` all follow it, so a Groq key with
`LLM_PROVIDER=anthropic` reads as no key rather than as a key that will 401 (D-082).

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

#: Groq keys start with this. Same length floor, same reason (D-082).
GROQ_KEY_PREFIX = "gsk_"
GROQ_KEY_MIN_LENGTH = 40

#: Which service answers. `anthropic` is the original; `groq` serves open models
#: through an OpenAI-compatible endpoint. See D-082.
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GROQ = "groq"
LLM_PROVIDERS = (PROVIDER_ANTHROPIC, PROVIDER_GROQ)
DEFAULT_LLM_PROVIDER = PROVIDER_ANTHROPIC


def looks_like_api_key(key: str | None) -> bool:
    """True only for something that could be a real Anthropic key.

    `.env.example` ships `ANTHROPIC_API_KEY=your-key-here`, and a copied-but-unedited
    `.env` is the normal state of this repo before Day 4. A truthiness check would read
    that placeholder as a key, build a client with it, and turn an honest "no key yet"
    into a confusing 401 from a call that never had a chance (see D-040).
    """
    text = (key or "").strip()
    return text.startswith(API_KEY_PREFIX) and len(text) >= API_KEY_MIN_LENGTH


def looks_like_groq_key(key: str | None) -> bool:
    """True only for something that could be a real Groq key.

    The same guard as `looks_like_api_key` and for the same reason: `.env.example`
    ships `GROQ_API_KEY=your-key-here`, and a placeholder that reads as a key turns
    "no key yet" into a 401 nobody can interpret. Groq keys are prefixed `gsk_`.
    """
    text = (key or "").strip()
    return text.startswith(GROQ_KEY_PREFIX) and len(text) >= GROQ_KEY_MIN_LENGTH


def env_choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    """An environment variable restricted to a fixed set of words, lower-cased.

    Anything outside the set falls back to `default`, which is this file's house style
    for a malformed value (D-065): `SUPPORT_CHECK=enfroce` is a typo, and booting with
    the default beats refusing to boot. The fallback is visible, because
    `/api/health` reports the mode actually in use.
    """
    text = env_str(name, default).lower()
    return text if text in allowed else default


def env_provider(name: str, default: str) -> str:
    """An environment variable as a provider name, or `default` when it is not one.

    Forgiving in the same way the readers above are (D-065): `LLM_PROVIDER=grok` is a
    typo, and falling back to the default beats refusing to boot. The fallback is
    visible, because `/api/health` reports the provider actually in use.
    """
    text = env_str(name, default).lower()
    return text if text in LLM_PROVIDERS else default


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

#: The default Groq model. `openai/gpt-oss-120b` is an open-weights reasoning model
#: served on Groq's free tier, which is what makes a live run possible on this project
#: at all (D-082). `LLM_MODEL` overrides it, exactly as it does for Anthropic.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

#: The model each provider uses when `LLM_MODEL` is unset. A key and a model id from
#: two different services would be the easiest mistake to make here, so the default
#: follows the provider rather than being one value for both.
DEFAULT_MODELS = {
    PROVIDER_ANTHROPIC: DEFAULT_LLM_MODEL,
    PROVIDER_GROQ: DEFAULT_GROQ_MODEL,
}

#: The smallest gap between two LLM calls, in seconds. 0 means no pacing, which is the
#: right default for a one-question interface; a batch run sets it to stay under a
#: provider's requests-per-minute limit (D-082).
DEFAULT_LLM_MIN_INTERVAL_S = 0.0


def default_model_for(provider: str) -> str:
    """The model id a provider uses when `LLM_MODEL` is unset."""
    return DEFAULT_MODELS.get(provider, DEFAULT_LLM_MODEL)

#: Which retrieval score the abstention pre-check reads. See D-071.
DENSE_COSINE = "dense_cosine"
RERANK_SCORE = "rerank_score"
ABSTAIN_SIGNALS = (DENSE_COSINE, RERANK_SCORE)
DEFAULT_ABSTAIN_SIGNAL = DENSE_COSINE

#: What the claim checker does with its verdicts (D-096).
#:   off      no second call at all
#:   shadow   the verdicts are recorded in the response and the log; the answer is
#:            untouched, whatever they say
#:   enforce  a sentence judged `unsupported` is dropped, and the whole answer is
#:            thrown away when the first sentence goes or nothing is left
SUPPORT_OFF = "off"
SUPPORT_SHADOW = "shadow"
SUPPORT_ENFORCE = "enforce"
SUPPORT_CHECK_MODES = (SUPPORT_OFF, SUPPORT_SHADOW, SUPPORT_ENFORCE)
#: `enforce`, since Phase C. The verdicts of a full shadow run have now been read by a
#: person: 1 of 39 sentences was called `unsupported` and the call was correct, and no
#: correct sentence was flagged (D-096, D-103).
DEFAULT_SUPPORT_CHECK = SUPPORT_ENFORCE

#: The **PROVISIONAL** cut-off for `DENSE_COSINE`, measured by
#: `scripts/tune_abstention.py` over the 60 drafted questions: it is a hair below the
#: lowest top-1 cosine similarity any answerable draft question produced, so it refuses
#: none of them. It also catches none of the ten should-abstain questions, which is the
#: honest state of affairs and not a failure of the guard — the two distributions
#: overlap almost completely on this signal, and the most conservative value that can
#: be chosen without verified questions is therefore one that only catches a total
#: retrieval failure. The final value comes from the same sweep over
#: `eval/questions_verified.jsonl`. See D-071.
DEFAULT_ABSTAIN_THRESHOLD = 0.5804
#: The provisional cut-off for `RERANK_SCORE`, measured the same way. Cross-encoder
#: scores run from about -11 to +11, so a threshold for one signal is meaningless for
#: the other and `ABSTAIN_THRESHOLD` must be set whenever `ABSTAIN_SIGNAL` changes.
PROVISIONAL_RERANK_THRESHOLD = -10.2377


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
    groq_api_key: str | None
    llm_provider: str
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

    # --- the reranker ---------------------------------------------------------
    #: Rescore the top `rerank_pool` results with a cross-encoder after fusion.
    #: Off until the evaluation says it earns its 0.4 s a query. See D-070.
    use_reranker: bool = False
    #: The smallest MS-MARCO cross-encoder fastembed offers, 80 MB.
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    #: How many fused results the cross-encoder rescores.
    rerank_pool: int = 20

    # --- answering ------------------------------------------------------------
    #: Which score decides that retrieval was too weak to ask the model at all:
    #: "dense_cosine" (top-1 dense cosine similarity) or "rerank_score" (top-1
    #: cross-encoder score, only meaningful when `use_reranker` is on). See D-071.
    abstain_signal: str = "dense_cosine"
    #: Below this value of `abstain_signal` we do not ask the model, we abstain.
    #: **PROVISIONAL** (D-071): set so that it refuses none of the drafted answerable
    #: questions, which is the most conservative value available before the questions
    #: are verified. The final value comes from the sweep in eval/run_eval.py.
    abstain_threshold: float = DEFAULT_ABSTAIN_THRESHOLD
    #: The old fused-score threshold, kept only so the reason it was replaced is
    #: documented in one place. Nothing reads it. See D-042 and D-071.
    legacy_fused_threshold: float = 0.02
    #: How many words the model may use for an answer.
    answer_max_tokens: int = 900
    #: Answers are deterministic: the same sources and question give the same words.
    answer_temperature: float = 0.0
    #: One retry with a stricter reminder when the citation check fails. See D-044.
    citation_retries: int = 1
    #: What the semantic claim check does with its verdicts: "off", "shadow" or
    #: "enforce". `enforce` by default: it costs one call per answer and drops a
    #: sentence its own clause does not state. See D-096 and D-103.
    support_check: str = DEFAULT_SUPPORT_CHECK
    #: True forces the FakeLLM everywhere, even if a real key is present.
    use_fake_llm: bool = False
    #: The smallest gap between two LLM calls, in seconds. See D-082.
    llm_min_interval_s: float = DEFAULT_LLM_MIN_INTERVAL_S

    # --- the agent ------------------------------------------------------------
    #: How many rounds of tool calling the agent may take before it has to answer.
    agent_max_rounds: int = 4
    #: Nominatim asks for no more than one request a second, and we identify ourselves.
    geocode_url: str = "https://nominatim.openstreetmap.org/search"
    geocode_user_agent: str = "ZoneWise/0.1 (student project)"
    geocode_min_interval_s: float = 1.0
    geocode_timeout_s: int = 30
    #: How close a normalised query has to be to a gazetteer name to count as a match.
    #: difflib's ratio, 0 to 1. See D-073 for why 0.85 and why the match must be unique.
    gazetteer_cutoff: float = 0.85

    # --- the API --------------------------------------------------------------
    #: Which browser origins may call the API. See D-076.
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    #: Asks per IP per minute, and for the whole service per day. See D-049.
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 300
    #: The longest question the API accepts, and the largest request body. See D-075.
    max_question_chars: int = 500
    max_request_bytes: int = 65536
    #: True enables the dev-only question verification endpoints. See D-073.
    dev_mode: bool = False
    #: How much a map layer is simplified before it is sent to the browser, in degrees.
    layer_simplify_tolerance: float = 0.0005

    @property
    def bm25_path(self) -> Path:
        """Where the pickled BM25 model lives."""
        return self.index_dir / "bm25.pkl"

    @property
    def gazetteer_dir(self) -> Path:
        """Where locally built place-name lists live. Gitignored: see D-073."""
        return DATA_DIR / "gazetteer"

    @property
    def gazetteer_path(self) -> Path:
        """The Delhi Metro station gazetteer, built by scripts/build_gazetteer.py."""
        return self.gazetteer_dir / "metro_stations.json"

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
    def has_anthropic_key(self) -> bool:
        """True only when a real-looking Anthropic key is configured. See D-040."""
        return looks_like_api_key(self.anthropic_api_key)

    @property
    def has_groq_key(self) -> bool:
        """True only when a real-looking Groq key is configured. See D-082."""
        return looks_like_groq_key(self.groq_api_key)

    @property
    def has_api_key(self) -> bool:
        """True when the **configured provider** has a usable key.

        Provider-aware on purpose: with `LLM_PROVIDER=groq` an Anthropic key is not a
        key at all, and reporting one would make `/api/ask` promise an answer it
        cannot produce. Everything that gates on a key — `llm_available`, the 503 in
        `app/api.py`, the banner in the web app — reads this one property, so switching
        provider cannot leave half the app thinking answers are possible (D-082).
        """
        if self.llm_provider == PROVIDER_GROQ:
            return self.has_groq_key
        return self.has_anthropic_key

    @property
    def reranker_on(self) -> bool:
        """True when results should actually be reranked: asked for, and available."""
        from app.rerank import available

        return self.use_reranker and available()

    @property
    def abstention_signal(self) -> str:
        """The abstention signal actually in use.

        `rerank_score` means nothing with the reranker off — every result would have
        `None` for it and the pre-check would let everything through — so the request
        falls back to the dense signal rather than silently disabling the guard.
        """
        if self.abstain_signal == RERANK_SCORE and not self.reranker_on:
            return DENSE_COSINE
        return self.abstain_signal if self.abstain_signal in ABSTAIN_SIGNALS else DENSE_COSINE

    @property
    def llm_available(self) -> bool:
        """True when an answer can actually be produced: a real key, or the fake client."""
        return self.use_fake_llm or self.has_api_key


#: Resolved before `settings` is built, because the default model depends on it.
LLM_PROVIDER = env_provider("LLM_PROVIDER", DEFAULT_LLM_PROVIDER)

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
    groq_api_key=os.getenv("GROQ_API_KEY"),
    llm_provider=LLM_PROVIDER,
    llm_model=env_str("LLM_MODEL", default_model_for(LLM_PROVIDER)),
    llm_min_interval_s=env_float("LLM_MIN_INTERVAL_S", DEFAULT_LLM_MIN_INTERVAL_S),
    use_fake_llm=env_bool("ZONEWISE_USE_FAKE_LLM", False),
    use_reranker=env_bool("USE_RERANKER", False),
    abstain_signal=env_str("ABSTAIN_SIGNAL", DEFAULT_ABSTAIN_SIGNAL),
    abstain_threshold=env_float("ABSTAIN_THRESHOLD", DEFAULT_ABSTAIN_THRESHOLD),
    support_check=env_choice("SUPPORT_CHECK", DEFAULT_SUPPORT_CHECK, SUPPORT_CHECK_MODES),
    dev_mode=env_bool("ZONEWISE_DEV", False),
    cors_origins=tuple(env_list("CORS_ORIGINS", ["http://localhost:5173"])),
    rate_limit_per_minute=env_int("RATE_LIMIT_PER_MINUTE", 10),
    rate_limit_per_day=env_int("RATE_LIMIT_PER_DAY", 300),
    max_question_chars=env_int("MAX_QUESTION_CHARS", 500),
    max_request_bytes=env_int("MAX_REQUEST_BYTES", 65536),
)
