"""Tests for the deployment files themselves: the Dockerfile, .dockerignore, the workflow.

These are text assertions, which is unusual for this repository and is here for one
reason: **the image cannot be built where this code is written.** The sandbox that wrote
the Dockerfile has no access to a container registry, so the normal way to find out
whether it is right — build it — was not available (see reports/deploy_prep.md). What a
test can still do is pin the handful of facts the deployment turns on, so that a future
edit which breaks one of them fails here rather than in Azure's log stream:

  - the data directories are created and owned by the non-root user, because the startup
    bootstrap writes the bundle into them (D-114);
  - the container listens on $PORT, because App Service routes to the port it assigned
    (D-113);
  - the bootstrap runs before uvicorn, and `&&` stops the server when it fails;
  - no built data is copied into the image, which is the whole of D-112;
  - the production defaults are set, and CORS is left to the environment;
  - the image workflow pushes to ghcr.io with a lower-cased owner, which is the one
    thing about GHCR that silently fails for a capitalised GitHub account.

None of this proves the image builds. It proves the parts that were decided on purpose
are still there.
"""


import pytest

from app.config import PROJECT_ROOT

DOCKERFILE = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
DOCKERIGNORE = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
WORKFLOW_DIR = PROJECT_ROOT / ".github" / "workflows"


# --- the Dockerfile -------------------------------------------------------------


def test_the_image_copies_no_built_data() -> None:
    """D-112. The image is code only; the data arrives at startup as a bundle."""
    copies = [
        line.strip()
        for line in DOCKERFILE.splitlines()
        if line.strip().upper().startswith("COPY")
    ]
    for line in copies:
        assert " data/" not in line, line
        assert not line.upper().startswith("COPY DATA/"), line
    # and the one directory that IS baked in is the model cache, built not copied
    assert "embed_query" in DOCKERFILE


def test_the_data_directories_exist_and_belong_to_the_non_root_user() -> None:
    """The bundle is extracted at startup, so these have to be writable by uid 10001."""
    assert "mkdir -p data/processed data/index/chroma data/layers/dda" in DOCKERFILE
    assert "data/gazetteer" in DOCKERFILE
    assert "data/logs" in DOCKERFILE
    assert "chown -R zonewise:zonewise /app/data" in DOCKERFILE
    assert "USER zonewise" in DOCKERFILE


def test_the_container_listens_on_the_port_it_is_given() -> None:
    """D-113. A fixed port fails App Service's routing whatever EXPOSE says."""
    assert "${PORT:-8000}" in DOCKERFILE
    assert "EXPOSE 8000" in DOCKERFILE


def test_the_bootstrap_runs_before_the_server_and_can_stop_it() -> None:
    """D-114. `&&`, not `;`: no data means no server, and a log line saying why."""
    command = [line for line in DOCKERFILE.splitlines() if line.startswith("CMD ")][-1]
    assert "python -m app.data_bootstrap &&" in command
    assert command.index("app.data_bootstrap") < command.index("uvicorn")
    # exec, so uvicorn receives the platform's SIGTERM rather than the shell
    assert "exec uvicorn" in command


def test_one_worker_only() -> None:
    """D-051. Two workers would double the daily cap that protects the API bill."""
    assert "--workers 1" in DOCKERFILE


def test_the_health_check_asks_for_ok_and_not_merely_a_200() -> None:
    """A 503-serving container answers 200 at /api/health; `status` is what matters."""
    assert "HEALTHCHECK" in DOCKERFILE
    assert "/api/health" in DOCKERFILE
    assert "body['status']=='ok'" in DOCKERFILE


def test_the_production_defaults_are_in_the_image() -> None:
    """The three settings that must not be wrong, and the one that must come from outside."""
    assert "ZONEWISE_DEV=0" in DOCKERFILE
    assert "SUPPORT_CHECK=enforce" in DOCKERFILE
    assert "LLM_PROVIDER=groq" in DOCKERFILE
    # CORS depends on the hostname, so the image must not pin it
    assert "ENV CORS_ORIGINS" not in DOCKERFILE


def test_no_key_is_ever_baked_in() -> None:
    """An API key in a layer stays in that layer forever, even if a later layer deletes it."""
    for secret in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "DATA_BUNDLE_URL"):
        assert f"ENV {secret}" not in DOCKERFILE
        assert f"{secret}=" not in DOCKERFILE


# --- .dockerignore --------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    ["data/", "dist/", ".env", ".env.*", ".venv/", "web/node_modules/", "reports/", "eval/", "tests/"],
)
def test_the_build_context_excludes_what_it_should(pattern) -> None:
    lines = [line.strip() for line in DOCKERIGNORE.splitlines()]
    assert pattern in lines


def test_the_example_env_file_is_still_allowed_through() -> None:
    """`.env.*` would otherwise take `.env.example` with it, and that one is committed."""
    assert "!.env.example" in DOCKERIGNORE


# --- the workflows --------------------------------------------------------------


def test_both_workflows_exist() -> None:
    names = sorted(path.name for path in WORKFLOW_DIR.glob("*.yml"))
    assert names == ["ci.yml", "image.yml"]


def test_the_image_workflow_pushes_to_ghcr_with_a_lower_cased_owner() -> None:
    """GHCR rejects a capitalised owner in an image name, and `dhruv-ship-it` is lucky.

    Pinned anyway, because the failure is a push that 403s at the end of a five-minute
    build, and the fix is one expression nobody remembers.
    """
    workflow = (WORKFLOW_DIR / "image.yml").read_text(encoding="utf-8")
    assert "ghcr.io" in workflow
    assert "tr '[:upper:]' '[:lower:]'" in workflow or "lowercase" in workflow.lower()
    assert "packages: write" in workflow
    assert "docker/build-push-action" in workflow
    assert "workflow_dispatch" in workflow
    assert "GITHUB_TOKEN" in workflow


def test_the_image_workflow_builds_on_a_version_tag() -> None:
    """The freeze tags (v1.0-rc2 and whatever follows) are what gets deployed."""
    workflow = (WORKFLOW_DIR / "image.yml").read_text(encoding="utf-8")
    assert "tags:" in workflow
    assert '"v*"' in workflow or "'v*'" in workflow or "- v*" in workflow


def test_the_ci_workflow_still_runs_the_tests_without_data() -> None:
    """Task 6 says leave CI alone. This fails if it was changed by accident."""
    workflow = (WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")
    assert 'uv run pytest -m "not needs_data" -q' in workflow
    assert "uv run ruff check ." in workflow
