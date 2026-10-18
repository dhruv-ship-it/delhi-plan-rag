# ZoneWise, in two stages: node builds the frontend, python serves everything.
#
# The image carries the **built data** — the Chroma store, the BM25 pickle, the cached
# embedding and reranker weights, the map layers and the gazetteer — rather than building
# it at startup. Embedding 700 chunks takes about 160 seconds on a CPU and downloading
# the model takes longer, so a container that built its own index would spend three
# minutes before its first request and do it again on every restart and every replica.
# That means `docker build` has to run on a machine where the pipeline has already been
# run: see docs/DEPLOY.md, which says so first and in bold.
#
# What is deliberately NOT in the image:
#   - data/raw — 109 MB of source PDFs that nothing needs once the chunks exist
#   - .env and any API key — the key arrives as an environment variable at run time
#   - data/logs — written by the running container, never baked in
#
# See D-079.

# --- stage 1: the frontend ------------------------------------------------------
FROM node:20-slim AS web

WORKDIR /build

# package.json first, so a source-only change does not reinstall node_modules
COPY web/package.json web/package-lock.json* ./
RUN npm install

COPY web/ ./
RUN npm run build


# --- stage 2: the server --------------------------------------------------------
FROM python:3.12-slim AS server

# uv, copied from its own published image rather than installed with pip, so the
# version is pinned by the tag and nothing needs a compiler
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies before source, so editing a Python file does not re-resolve them.
# --frozen means uv.lock is used exactly as committed and the build fails rather than
# quietly resolving something newer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY eval/ ./eval/

# the built data. Each of these is gitignored and has to exist on the build machine.
COPY data/processed/ ./data/processed/
COPY data/index/ ./data/index/
COPY data/layers/ ./data/layers/
COPY data/gazetteer/ ./data/gazetteer/

# committed data files the code reads by name
COPY data/sources.csv data/chapter_map.json data/zone_sections.json data/test_points.json ./data/

COPY --from=web /build/dist ./web/dist

# install the project itself now that its source is in place
RUN uv sync --frozen --no-dev

# The log directory is created here with the right owner, because the server runs as a
# non-root user and a container that cannot write its log would otherwise swallow the
# failure (app/api.py logs best-effort) and lose every request record.
RUN mkdir -p data/logs \
    && useradd --create-home --uid 10001 zonewise \
    && chown -R zonewise:zonewise /app/data/logs
USER zonewise

EXPOSE 8000

# Both answering endpoints and the search endpoint need the index, and /api/health
# reports whether it loaded. A health check that only asked for a 200 would call a
# container healthy while it was serving 503s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import json,urllib.request;\
b=json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health'));\
raise SystemExit(0 if b['status']=='ok' else 1)"

# One worker on purpose. The rate limiter and the daily cap are in-memory (D-051), so a
# second worker would have its own counters and the cap that protects the API bill would
# silently double. The index is also about 80 MB per process.
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
