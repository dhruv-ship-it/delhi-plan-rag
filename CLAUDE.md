# ZoneWise: instructions for Claude Code

## What this project is
ZoneWise is a location-aware RAG assistant for Delhi planning law (Master Plan for Delhi 2047 plus related court orders). A user clicks a point on a map of Delhi and asks a question. The system finds which planning zones contain the point, retrieves only the relevant clauses with hybrid search (BM25 + embeddings), and answers with clause-level citations, or declines when no clause supports an answer.
The developer is learning AI engineering. Architecture decisions are made by the project lead outside this repo. Follow this file; do not redesign.

## Fixed stack (do not change without asking)
- Python 3.12 managed with uv. Run everything with `uv run`.
- PDF: PyMuPDF. Embeddings: fastembed with BAAI/bge-small-en-v1.5. Keyword search: rank_bm25. Vector store: Chroma (local, persistent). Fusion: reciprocal rank fusion, k = 60.
- Geo: GeoPandas + Shapely. Buffers computed in EPSG:32643 (UTM 43N), stored as EPSG:4326 GeoJSON.
- LLM: Anthropic API through one wrapper, app/llm.py. Model name lives in app/config.py.
- API: FastAPI. Frontend: React (Vite) + react-leaflet in web/, built files served by FastAPI.
- Not allowed: LangChain, LlamaIndex, Haystack or any other RAG/agent framework; MongoDB; Express; any new dependency without asking first.

## Repo layout
- app/        Python package: config, llm, extract, chunking, retrieval, spatial, answer, agent, api
- scripts/    numbered pipeline scripts, run in order (00_, 01_, 02_ ...)
- data/sources.csv   every document: id, title, type, issuer, date, url, download date, authority rank
- data/raw/          source PDFs, named <doc_id>.pdf (not committed)
- data/reference/    maps and images used by hand, not indexed
- data/processed/    generated files: pages, chunks (not committed)
- data/layers/       GeoJSON map layers (committed), plus manifest.json describing them
- data/layers/dda/   layers downloaded from gis.dda.org.in (not committed: DDA states no licence)
- data/index/        search indexes (not committed)
- eval/       evaluation questions, scripts, results
- reports/    run reports written for a human to read (committed)
- web/        React frontend
- tests/      pytest tests

## Rules
1. Every script in scripts/ runs on its own with `uv run python scripts/NN_name.py`, is safe to re-run, and ends by printing a short summary (counts, warnings, output paths).
2. Put reusable logic in app/ and keep scripts thin, so logic can be tested.
3. Never commit .env, data/raw, data/processed or data/index. Never print the API key.
4. Small functions with type hints and short docstrings. Prefer plain, readable Python over clever abstractions.
5. After any design choice (a library option, a threshold, a file format), add an entry to DECISIONS.md: number, date, decision, why, alternatives considered. Plain English a beginner can follow.
6. If an instruction conflicts with what you think is better, stop and explain the trade-off before changing anything.
7. When a task is done, list the files created or changed, the commands to run, and the output to expect.

## Git workflow
1. Commit after every step that works: a script that runs, a test that passes, a document added. Small commits with plain messages, e.g. "add chunking script" or "fix 1-based page numbers in extract".
2. Run the script or the tests before committing. Never commit a half-broken step just to save progress.
3. Every commit is authored by the repo owner's own account: Dhruv Ranjan <irldhruv196@gmail.com>, which is the dhruv-ship-it GitHub account. Never commit or push from a Claude or any other assistant account, and do not add a Co-Authored-By: Claude trailer to commit messages.
4. Do not push to origin unless asked.

## Data conventions
- doc_id is UPPER_SNAKE_CASE, e.g. MPD47_GAZETTE_EN. Raw file: data/raw/<doc_id>.pdf.
- Page numbers are 1-based everywhere.
- authority_rank: 1 = gazette or legal text, 2 = court order, 3 = FAQ, explainer or report.
- Records are JSONL (one JSON object per line). Map layers are GeoJSON. CSV is used only for sources.csv.
