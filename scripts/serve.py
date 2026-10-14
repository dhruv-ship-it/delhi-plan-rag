"""Run the ZoneWise API on http://localhost:8000.

    uv run python scripts/serve.py
    uv run python scripts/serve.py --reload --port 8001

The indexes, the map layers and the embedding model load before the first request, which
takes a few seconds. Once it is up:

    http://localhost:8000/api/health   what is loaded and whether answers are possible
    http://localhost:8000/docs         the generated API documentation, clickable

With the frontend built (cd web && npm run build), the app itself is served at
http://localhost:8000/ as well. During development run the Vite dev server instead
(cd web && npm run dev) and use http://localhost:5173, which proxies /api to this.
"""

import argparse
import sys

from app.config import settings
from app.extract import use_utf8_output


def main(argv: list[str] | None = None) -> int:
    """Start uvicorn, after printing what the server will and will not be able to do."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Run the ZoneWise API.")
    parser.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port to bind (default 8000)")
    parser.add_argument(
        "--reload", action="store_true", help="restart when a source file changes"
    )
    args = parser.parse_args(argv)

    if not settings.bm25_path.exists():
        print("No search index found. Run: uv run python scripts/05_build_index.py")
        return 1
    if not settings.dda_layers_dir.exists() or not any(settings.dda_layers_dir.glob("*.geojson")):
        print("No map layers found. Run: uv run python scripts/06_fetch_layers.py")
        return 1

    print(f"ZoneWise API on http://{args.host}:{args.port}")
    print(f"  health: http://{args.host}:{args.port}/api/health")
    print(f"  docs:   http://{args.host}:{args.port}/docs")
    if settings.llm_available:
        print(f"  answers: enabled ({settings.llm_model})")
    else:
        print("  answers: DISABLED, no API key set, so /api/ask and /api/agent return 503.")
        print("           Search, zones, layers and clauses all work. Put a key in .env")
        print("           as ANTHROPIC_API_KEY=sk-ant-... and restart to enable answers.")
    if settings.web_dist_dir.is_dir():
        print(f"  app:    http://{args.host}:{args.port}/ (serving web/dist)")
    else:
        print("  app:    web/dist not built; run: cd web && npm run build")
        print(f"          or use the dev server at {settings.cors_origin}")
    print()

    import uvicorn

    uvicorn.run(
        "app.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
