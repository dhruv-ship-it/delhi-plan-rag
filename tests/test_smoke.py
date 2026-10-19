"""Smoke test: settings import and the data paths stay inside the repo."""

import dataclasses

from app.config import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_LLM_MODEL,
    PROVIDER_ANTHROPIC,
    PROVIDER_GROQ,
    default_model_for,
    env_bool,
    env_float,
    env_int,
    env_list,
    env_provider,
    env_str,
    looks_like_api_key,
    looks_like_groq_key,
    settings,
)


def test_project_root_is_a_real_folder() -> None:
    """The project root should exist and hold CLAUDE.md."""
    assert settings.project_root.is_dir()
    assert (settings.project_root / "CLAUDE.md").exists()


def test_data_paths_are_inside_the_repo() -> None:
    """No data path should point outside the project root."""
    paths = [
        settings.raw_dir,
        settings.reference_dir,
        settings.processed_dir,
        settings.layers_dir,
        settings.index_dir,
        settings.sources_csv,
    ]
    for path in paths:
        assert path.is_relative_to(settings.project_root), f"{path} is outside the repo"


def test_llm_model_is_configured() -> None:
    """A model name should always be set, even before the API key exists."""
    assert settings.llm_model


def test_llm_model_default_is_the_current_haiku_id() -> None:
    """The default is Anthropic's current Haiku API model id (D-063)."""
    assert DEFAULT_LLM_MODEL == "claude-haiku-5-5"


def test_llm_model_can_be_overridden_from_the_environment(monkeypatch) -> None:
    """LLM_MODEL in .env picks the model without a code change (D-063)."""
    monkeypatch.setenv("LLM_MODEL", "claude-opus-4-5")
    assert env_str("LLM_MODEL", DEFAULT_LLM_MODEL) == "claude-opus-4-5"


def test_a_blank_llm_model_falls_back_to_the_default(monkeypatch) -> None:
    """An empty variable is not a model name; the default stands."""
    monkeypatch.setenv("LLM_MODEL", "   ")
    assert env_str("LLM_MODEL", DEFAULT_LLM_MODEL) == DEFAULT_LLM_MODEL


def test_env_readers_fall_back_when_a_value_will_not_parse(monkeypatch) -> None:
    """A typo in a number should not stop the server (D-065)."""
    monkeypatch.setenv("ZW_TEST_INT", "ten")
    monkeypatch.setenv("ZW_TEST_FLOAT", "lots")
    assert env_int("ZW_TEST_INT", 10) == 10
    assert env_float("ZW_TEST_FLOAT", 0.5) == 0.5


def test_env_bool_reads_the_usual_spellings(monkeypatch) -> None:
    """1, true, yes and on are true; anything else is false; unset keeps the default."""
    for text in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("ZW_TEST_FLAG", text)
        assert env_bool("ZW_TEST_FLAG", False) is True
    for text in ("0", "false", "no", "off", "maybe"):
        monkeypatch.setenv("ZW_TEST_FLAG", text)
        assert env_bool("ZW_TEST_FLAG", True) is False
    monkeypatch.delenv("ZW_TEST_FLAG", raising=False)
    assert env_bool("ZW_TEST_FLAG", True) is True


def test_env_list_splits_on_commas_and_drops_blanks(monkeypatch) -> None:
    """CORS_ORIGINS is a comma-separated list, trimmed (D-065)."""
    monkeypatch.setenv("ZW_TEST_LIST", " a.example , , b.example ")
    assert env_list("ZW_TEST_LIST", ["z"]) == ["a.example", "b.example"]
    monkeypatch.delenv("ZW_TEST_LIST", raising=False)
    assert env_list("ZW_TEST_LIST", ["z"]) == ["z"]


# --- the provider (D-082) -------------------------------------------------------


def test_the_provider_is_one_of_the_two_names() -> None:
    """Whatever `.env` says, the resolved provider is a name the code knows."""
    assert settings.llm_provider in (PROVIDER_ANTHROPIC, PROVIDER_GROQ)


def test_a_misspelled_provider_falls_back_rather_than_stopping_the_server(monkeypatch) -> None:
    """A typo in LLM_PROVIDER should not take the server down (D-065)."""
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    assert env_provider("LLM_PROVIDER", PROVIDER_ANTHROPIC) == PROVIDER_ANTHROPIC
    monkeypatch.setenv("LLM_PROVIDER", "GROQ")
    assert env_provider("LLM_PROVIDER", PROVIDER_ANTHROPIC) == PROVIDER_GROQ
    monkeypatch.setenv("LLM_PROVIDER", "  ")
    assert env_provider("LLM_PROVIDER", PROVIDER_GROQ) == PROVIDER_GROQ


def test_the_default_model_follows_the_provider() -> None:
    """A key from one service and a model id from the other is the easy mistake."""
    assert default_model_for(PROVIDER_ANTHROPIC) == DEFAULT_LLM_MODEL
    assert default_model_for(PROVIDER_GROQ) == DEFAULT_GROQ_MODEL == "openai/gpt-oss-120b"
    assert default_model_for("nonsense") == DEFAULT_LLM_MODEL


def test_a_groq_key_is_checked_as_strictly_as_an_anthropic_one() -> None:
    """Prefix and length, so a placeholder cannot read as a key (D-040, D-082)."""
    good = "gsk_" + "a" * 44
    assert looks_like_groq_key(good) is True
    assert looks_like_groq_key("  " + good + " ") is True
    assert looks_like_groq_key("your-key-here") is False
    assert looks_like_groq_key("gsk_short") is False
    assert looks_like_groq_key(None) is False
    assert looks_like_groq_key("sk-ant-" + "a" * 50) is False
    assert looks_like_api_key(good) is False


def test_has_api_key_follows_the_configured_provider() -> None:
    """With LLM_PROVIDER=groq an Anthropic key is not a key at all (D-082)."""
    anthropic_key = "sk-ant-" + "a" * 50
    groq_key = "gsk_" + "a" * 44

    on_groq = dataclasses.replace(
        settings,
        llm_provider=PROVIDER_GROQ,
        anthropic_api_key=anthropic_key,
        groq_api_key=None,
    )
    assert on_groq.has_anthropic_key is True
    assert on_groq.has_api_key is False
    assert on_groq.llm_available is False

    on_anthropic = dataclasses.replace(
        settings,
        llm_provider=PROVIDER_ANTHROPIC,
        anthropic_api_key=None,
        groq_api_key=groq_key,
    )
    assert on_anthropic.has_groq_key is True
    assert on_anthropic.has_api_key is False

    configured = dataclasses.replace(
        settings, llm_provider=PROVIDER_GROQ, groq_api_key=groq_key
    )
    assert configured.has_api_key is True
    assert configured.llm_available is True


def test_the_call_gap_defaults_to_no_pacing(monkeypatch) -> None:
    """0 is right for a one-question interface; a batch run sets its own (D-082)."""
    assert settings.llm_min_interval_s >= 0
    monkeypatch.setenv("LLM_MIN_INTERVAL_S", "2.5")
    assert env_float("LLM_MIN_INTERVAL_S", 0.0) == 2.5
    monkeypatch.setenv("LLM_MIN_INTERVAL_S", "slowly")
    assert env_float("LLM_MIN_INTERVAL_S", 0.0) == 0.0
