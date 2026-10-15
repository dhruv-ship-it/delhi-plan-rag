"""Check that the built frontend is there and that FastAPI serves it at /.

The mount in app/api.py is conditional on web/dist existing, so this is the test that
catches "I changed the build output directory and the app silently stopped being
served". Everything here skips cleanly on a checkout where `npm run build` has not been
run, because the Python side must not depend on node being installed.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings

DIST = settings.web_dist_dir
WEB = settings.project_root / "web"

needs_build = pytest.mark.skipif(
    not (DIST / "index.html").exists(),
    reason="web/dist is not built; run: cd web && npm run build",
)


def test_the_web_project_files_are_present() -> None:
    """The app is written by hand, so these files are source, not generated."""
    for name in ("package.json", "vite.config.js", "index.html"):
        assert (WEB / name).exists(), name
    for name in ("main.jsx", "App.jsx", "api.js", "styles.css", "layers.js"):
        assert (WEB / "src" / name).exists(), name


def test_only_the_approved_npm_dependencies_are_declared() -> None:
    """CLAUDE.md forbids adding a dependency without asking, frontend included."""
    package = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    assert set(package["dependencies"]) == {"react", "react-dom", "react-leaflet", "leaflet"}
    assert set(package["devDependencies"]) == {"vite", "@vitejs/plugin-react"}


def test_the_dev_server_proxies_the_api_to_the_backend() -> None:
    """Without this the browser would hit Vite's port for /api and get a 404."""
    config = (WEB / "vite.config.js").read_text(encoding="utf-8")
    assert "'/api'" in config
    assert "http://localhost:8000" in config


@needs_build
def test_the_built_page_is_served_at_the_root() -> None:
    """`npm run build` then uvicorn should give a working app on one port."""
    with TestClient(__import__("app.api", fromlist=["app"]).app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert '<div id="root"></div>' in response.text
        assert "/assets/index-" in response.text


@needs_build
def test_the_api_still_works_when_the_frontend_is_mounted() -> None:
    """The static mount is at /, so it must not shadow /api."""
    with TestClient(__import__("app.api", fromlist=["app"]).app) as client:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["chunks"] > 0


@needs_build
def test_the_build_output_has_its_assets() -> None:
    assets = list((DIST / "assets").glob("*.js"))
    styles = list((DIST / "assets").glob("*.css"))
    assert assets, "no javascript bundle in web/dist/assets"
    assert styles, "no stylesheet in web/dist/assets"
