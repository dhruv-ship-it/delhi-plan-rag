# Decisions log
Each entry: what we decided, why, and what we rejected.

## D-001 · 2026-10-14 · Standalone repo
ZoneWise lives in its own repo, separate from the TerraTime capstone. Why: keeps the resume project clean. TerraTime can call ZoneWise's API later instead of merging code. Rejected: building inside the TerraTime repo.

## D-002 · 2026-10-14 · Python + FastAPI backend, React frontend, no MERN
Why: all the AI and map libraries we need are Python. There is nothing to store in MongoDB (no users; vectors live in Chroma), and Express would only add an extra hop. Rejected: MERN.

## D-003 · 2026-10-14 · No RAG frameworks
We write chunking, hybrid search, fusion and citation checks ourselves. Why: every step stays visible and explainable, and the codebase stays small. Rejected: LangChain, LlamaIndex.

## D-004 · 2026-10-14 · Documents downloaded by hand
Source PDFs are downloaded manually and listed in data/sources.csv with URL and download date. Why: government sites are slow and change often, there are only about 12 files, and the CSV keeps the work reproducible. Rejected: scraping scripts.

## D-005 · 2026-10-14 · Python 3.12 via uv
Why: one tool manages the Python version and the dependencies, with the same commands on Windows, Mac and Linux. Rejected: system Python + pip + venv.
