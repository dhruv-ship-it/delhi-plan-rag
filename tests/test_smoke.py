"""Smoke test: settings import and the data paths stay inside the repo."""

from app.config import (
    DEFAULT_LLM_MODEL,
    env_bool,
    env_float,
    env_int,
    env_list,
    env_str,
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
