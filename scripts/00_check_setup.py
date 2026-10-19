"""Check that the ZoneWise development setup is complete.

Safe to re-run at any time. Reads nothing secret and prints nothing secret.
Run with: uv run python scripts/00_check_setup.py
"""

import csv
import importlib
import sys
from pathlib import Path

from app.config import settings


def check_python() -> list[str]:
    """Print the Python version and complain if it is not 3.12."""
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Python version: {version}")
    if sys.version_info[:2] != (3, 12):
        return [f"Python 3.12 expected, found {version}"]
    return []


def check_imports() -> list[str]:
    """Print whether each required package imports."""
    problems = []
    for module in ("anthropic", "openai", "dotenv"):
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"import {module}: FAILED")
            problems.append(f"cannot import {module} (try: uv sync)")
        else:
            print(f"import {module}: ok")
    return problems


def check_env() -> list[str]:
    """Print whether .env exists and whether the API key is set. Never print the key."""
    env_file = settings.project_root / ".env"
    if env_file.exists():
        print(".env file: found")
    else:
        print(".env file: not found (expected until Day 4; copy .env.example to .env)")
    print(f"LLM_PROVIDER: {settings.llm_provider}   LLM_MODEL: {settings.llm_model}")
    for variable, present, usable in (
        ("ANTHROPIC_API_KEY", bool(settings.anthropic_api_key), settings.has_anthropic_key),
        ("GROQ_API_KEY", bool(settings.groq_api_key), settings.has_groq_key),
    ):
        if not present:
            print(f"{variable}: missing")
        elif usable:
            print(f"{variable}: set")
        else:
            print(f"{variable}: set but not usable (a placeholder, or the wrong prefix)")
    if settings.has_api_key:
        print(f"answers: enabled, using {settings.llm_provider}")
    else:
        print(f"answers: disabled, no usable {settings.llm_provider} key (search still works)")
    return []


def check_folders() -> list[str]:
    """Print whether each data folder exists."""
    problems = []
    folders = {
        "data/raw": settings.raw_dir,
        "data/reference": settings.reference_dir,
        "data/processed": settings.processed_dir,
        "data/layers": settings.layers_dir,
        "data/index": settings.index_dir,
    }
    for name, path in folders.items():
        if path.is_dir():
            print(f"{name}: ok")
        else:
            print(f"{name}: MISSING")
            problems.append(f"folder {name} does not exist")
    return problems


def check_sources() -> list[str]:
    """Print how many document rows sources.csv holds."""
    path: Path = settings.sources_csv
    if not path.exists():
        print("data/sources.csv: MISSING")
        return ["data/sources.csv does not exist"]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    print(f"data/sources.csv: {len(rows)} document rows")
    return [] if rows else ["data/sources.csv has no document rows"]


def main() -> int:
    """Run every check, then print 'Setup OK' or the list of problems."""
    print("ZoneWise setup check")
    print("-" * 20)
    problems = (
        check_python()
        + check_imports()
        + check_env()
        + check_folders()
        + check_sources()
    )
    print("-" * 20)
    if problems:
        print(f"{len(problems)} problem(s) found:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Setup OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
