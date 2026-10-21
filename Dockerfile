# ZoneWise, in two stages: node builds the frontend, python serves everything.
#
# The image carries **code only**. That is the change from the first version of this
# file, which copied the built indexes, the map layers and the gazetteer in and
# therefore only built on a machine where the pipeline had already run (D-079). It is
# now built by GitHub Actions from a clean checkout, where none of that data exists and
# none of it can be regenerated — the source PDFs are gitignored and the DDA layers have
# no stated licence — so the data arrives at startup instead, as one zip from a private
# blob container, fetched and checked by `python -m app.data_bootstrap` (D-112, D-114).
#
# What IS baked in, and why: the fastembed weights for BAAI/bge-small-en-v1.5, 65 MB,
# downloaded at build time into the cache directory the code already reads. They are a
# public Hugging Face model with no licence question, and having them here means a
# container start needs no Hugging Face access and no 65 MB download before the first
# question.
#
# What is deliberately NOT in the image:
#   - any built data: chunks, the Chroma store, the BM25 pickle, the DDA layers
#   - the reranker's 88 MB of weights, which USE_RERANKER=0 never loads (D-110)
#   - .env and any API key — keys arrive as App Service settings at run time
#   - data/logs — written by the running container, never baked in
#
# Size: about 1.0 GB uncompressed, roughly 500 MB compressed, estimated rather than
# measured (see reports/deploy_prep.md). The parts: ~130 MB for python:3.12-slim,
# ~45 MB for the uv binaries, ~600 MB for the dependency environment (onnxruntime,
# chromadb and its kubernetes client, pymupdf, pyogrio, pandas, numpy, pyproj), 65 MB of
# model weights and ~1 MB of built frontend.

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

# Production defaults, every one of them overridable by an App Service setting (D-065).
# ZONEWISE_DEV=0 keeps the question verification endpoints and the Verify tab 404,
# because they read and write the evaluation files (D-075). SUPPORT_CHECK=enforce is
# already the code's default and is set here so the image states it. LLM_PROVIDER=groq
# is the provider this deployment has a key for (D-082).
#
# CORS_ORIGINS is deliberately NOT set: it is the one setting that depends on the
# hostname the app ends up on, so it comes from the environment
# (CORS_ORIGINS=https://<app>.azurewebsites.net). Unset, the code's default allows only
# the Vite dev server, which costs the deployment nothing — the frontend is served from
# the same origin as the API, so it needs no CORS permission at all.
ENV ZONEWISE_DEV=0 \
    SUPPORT_CHECK=enforce \
    LLM_PROVIDER=groq

WORKDIR /app

# Dependencies before source, so editing a Python file does not re-resolve them.
# --frozen means uv.lock is used exactly as committed and the build fails rather than
# quietly resolving something newer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app/ ./app/
COPY scripts/ ./scripts/

# install the project itself now that its source is in place
RUN uv sync --frozen --no-dev

COPY --from=web /build/dist ./web/dist

# The embedding model, downloaded once here instead of on every container start. This
# also proves at build time that onnxruntime works in this image: `embed_query` loads
# the ONNX session and runs one inference, so a broken wheel fails the build rather
# than the first question. The weights land in `settings.model_cache_dir`, which is
# /app/data/index/models, exactly where `app/indexing.py` looks for them.
RUN python -c "from app.indexing import embed_query; embed_query('warmup')"

# The directories the startup bootstrap and the request log write into. They have to
# exist and be owned by the non-root user: the bundle is extracted into data/processed,
# data/index and data/layers at startup, and a container that cannot write them would
# fail at the one step that has no fallback.
RUN mkdir -p data/processed data/index/chroma data/layers/dda data/gazetteer data/logs \
    && useradd --create-home --uid 10001 zonewise \
    && chown -R zonewise:zonewise /app/data
USER zonewise

# 8000 is the default and what WEBSITES_PORT should be set to on App Service. The
# command below honours $PORT when the platform sets one, because a container that
# listens on a fixed port fails a platform's routing whatever this line says (D-113).
EXPOSE 8000

# Both answering endpoints and the search endpoint need the index, and /api/health
# reports whether it loaded. A health check that only asked for a 200 would call a
# container healthy while it was serving 503s.
#
# The start period covers the bundle download, the extraction and the model load: on one
# B1 core that is tens of seconds, and a probe that fired before it finished would
# restart the container in a loop. App Service's own health check is configured
# separately, in the portal, and is pointed at the same path.
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import json,os,urllib.request;\
port=os.environ.get('PORT','8000');\
body=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/api/health'));\
raise SystemExit(0 if body['status']=='ok' else 1)"

# Two steps, in one command, in this order on purpose.
#
# `python -m app.data_bootstrap` puts the runtime data in place: nothing to do when it
# is already there, otherwise download DATA_BUNDLE_URL, check it against
# DATA_BUNDLE_SHA256, extract it and verify its manifest. It exits non-zero when there
# is no data and no URL, and `&&` then stops the server from starting at all — a
# container that answers 503 to every question while reporting itself up is worse than
# one that says in its log why it cannot run (D-114).
#
# `exec` replaces the shell, so uvicorn is the process that receives SIGTERM when App
# Service restarts or stops the container.
#
# One worker on purpose. The rate limiter and the daily cap are in-memory (D-051), so a
# second worker would have its own counters and the cap that protects the API bill would
# silently double. The index is also about 80 MB per process, against 1.75 GB of RAM.
CMD ["sh", "-c", "python -m app.data_bootstrap && exec uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
