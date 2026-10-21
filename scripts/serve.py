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

from app.config import PROVIDER_ANTHROPIC, PROVIDER_GROQ, env_int, settings
from app.extract import use_utf8_output

#: Which environment variable holds each provider's key, so the message names the one
#: that is actually missing rather than always naming Anthropic's (D-082).
KEY_VARIABLES = {
    PROVIDER_ANTHROPIC: "ANTHROPIC_API_KEY=sk-ant-",
    PROVIDER_GROQ: "GROQ_API_KEY=gsk_",
}


def main(argv: list[str] | None = None) -> int:
    """Start uvicorn, after printing what the server will and will not be able to do."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Run the ZoneWise API.")
    parser.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    # $PORT, when it is set, because that is how a container platform says which port
    # to listen on: App Service sets it from WEBSITES_PORT, and a container that ignored
    # it would fail the platform's own health probe whatever the Dockerfile said (D-113).
    parser.add_argument(
        "--port",
        type=int,
        default=env_int("PORT", 8000),
        help="port to bind (default $PORT, or 8000)",
    )
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
        print(f"  answers: enabled ({settings.llm_provider}/{settings.llm_model})")
    else:
        print(f"  answers: DISABLED, no {settings.llm_provider} key set, so /api/ask and")
        print("           /api/agent return 503. Search, zones, layers and clauses all")
        print("           work. Put a key in .env and restart to enable answers:")
        print(f"           {KEY_VARIABLES[settings.llm_provider]}=... (LLM_PROVIDER={settings.llm_provider})")
    if settings.web_dist_dir.is_dir():
        print(f"  app:    http://{args.host}:{args.port}/ (serving web/dist)")
    else:
        print("  app:    web/dist not built; run: cd web && npm run build")
        print(f"          or use the dev server at {settings.cors_origins[0]}")
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
