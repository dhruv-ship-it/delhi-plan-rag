"""Smoke test: settings import and the data paths stay inside the repo."""

from app.config import settings


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
