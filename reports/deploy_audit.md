# Deployment readiness audit: a Render free web service

**21 October 2026. Read-only.** No code was changed to produce this; it answers whether
ZoneWise, as it exists right now, can run on **one free container service** — a Render
free web service, which builds the Dockerfile straight from the GitHub repo and runs the
result with 512 MB RAM, 0.1 CPU, an ephemeral disk, and a sleep when idle. Everything
below is "describe", not "decide" — the fixes, if any are wanted, are the project lead's
call, outside this report.

---

## a. What the app reads, at startup and per request

| path | read by | when | size | gitignored? |
| --- | --- | --- | --- | --- |
| `data/index/chroma/` | `get_index()` → `SearchIndex` (`app/retrieval.py`) | startup | 14 MB | yes |
| `data/index/bm25.pkl` | `get_index()` | startup | 904 KB | yes |
| `data/processed/chunks.jsonl` | `get_index()` (`app/retrieval.py:147`) — clause text and metadata are read back from it at search time, not just at index-build time | startup | part of 3.9 MB `data/processed/` | yes |
| `data/index/models/models--Qdrant--bge-small-en-v1.5-onnx-Q/` | the embedding model, loaded inside `SearchIndex` | startup | 65 MB | yes |
| `data/index/models/models--Xenova--ms-marco-MiniLM-L-6-v2/` | the reranker (`app/rerank.py:reranker()`) | **lazy** — only if `USE_RERANKER=1`; off by default, so never in the shipped configuration | 88 MB | yes |
| `data/layers/dda/*.geojson` (8 files, `ALL_LAYERS` in `app/spatial.py`) | `load_layers()` | startup | 4.9 MB | yes |
| `data/layers/manifest.json` | nothing at runtime — a record for humans | — | 8 KB | **no**, committed |
| `data/gazetteer/metro_stations.json` | `app/geocode.py` (`gazetteer_path`) | per geocode call (`locate_place`), not startup | 36 KB | yes |
| `data/index/geocode_cache.json` | `app/geocode.py` (`geocode_cache_path`) | read and written per geocode call | a few KB, grows | yes |
| `data/sources.csv`, `data/chapter_map.json`, `data/zone_sections.json`, `data/test_points.json` | `app/tagging.py`, `app/cleaning.py`, `app/chunking.py` — **pipeline scripts, not the running server** | build time only | small | **no**, committed |
| `data/logs/requests.jsonl` | written per request (`log_request`); nothing reads it at runtime | per request | grows | yes |

**The running server needs five gitignored things to exist before it will answer anything
useful**: `data/processed/chunks.jsonl`, `data/index/chroma/`, `data/index/bm25.pkl`, the
embedding model under `data/index/models/`, and `data/layers/dda/`. All five are absent
from a clean clone. The gazetteer is the one optional absence (D-074: falls back to
Nominatim).

---

## b. Where each gitignored item comes from

| item | script | source | network? | time |
| --- | --- | --- | --- | --- |
| `data/processed/*` (pages, chunks) | `scripts/02_extract.py`, `build_chapter_map.py`, `scripts/03_chunk.py`, `scripts/04_tag_zones.py` | `data/raw/*.pdf` — **itself gitignored, 109 MB, not in any clone** | no (once the PDFs exist) | a few seconds to a couple of minutes |
| `data/index/chroma/`, `data/index/bm25.pkl`, `data/index/models/` | `scripts/05_build_index.py` | embeds `chunks.jsonl`; the embedding model downloads from Hugging Face (`huggingface_hub`, confirmed in `fastembed`'s own import) | yes, to download the model on a clean machine; no thereafter | ~3 minutes, per `docs/DEPLOY.md` — "about 3 minutes, downloads the model" |
| `data/layers/dda/*.geojson` | `scripts/06_fetch_layers.py` | DDA's ArcGIS FeatureServer, `gis.dda.org.in`, one request a second, eight layers | yes, every run (no cache) | ~25 seconds, measured (`reports/overnight_run.md`) |
| `data/gazetteer/metro_stations.json` | `scripts/build_gazetteer.py` | OpenStreetMap via the Overpass API, `overpass-api.de`, one request | yes | ~48 seconds, measured (`reports/night4_run.md`) — optional; app works without it |

**The raw PDFs are the real blocker.** `data/raw/` is gitignored (109 MB, CLAUDE.md rule
3) and nothing else in the repository can produce it — the thirteen source documents in
`data/sources.csv` were downloaded by hand from `dda.gov.in`, `indiankanoon.org` and
`greentribunal.gov.in`. A clean clone has no way to regenerate `data/processed/` at all,
let alone the index built from it. This is the central fact the rest of this audit turns
on; see §g and the recommendation at the end.

---

## c. The current Dockerfile against this target

**What it does.** Two stages: `node:20-slim` builds `web/dist`; `python:3.12-slim` runs
`uv sync --frozen`, copies `app/`, `scripts/`, `eval/`, the four gitignored data
directories (`data/processed/`, `data/index/`, `data/layers/`, `data/gazetteer/`), the
four committed data files, and the built frontend. It creates a non-root user
(`zonewise`, uid 10001), owns `data/logs` to that user, `EXPOSE`s 8000, declares a Docker
`HEALTHCHECK` against `/api/health`, and runs one `uvicorn` worker on `0.0.0.0:8000`.

**Gaps against a Render free web service, specifically:**

| gap | detail |
| --- | --- |
| **Listens on a fixed port, not `$PORT`** | `CMD` hardcodes `--port 8000`. Render injects a `PORT` environment variable and routes to whatever port the container actually listens on; a container that ignores it and only listens on 8000 fails Render's own health probe regardless of the Docker `HEALTHCHECK`. |
| **Running as non-root — already done** | `USER zonewise` is already in the Dockerfile. Not a gap. |
| **A healthcheck exists, but it is Docker's, not Render's** | The `HEALTHCHECK` instruction is read by a plain Docker daemon; Render's own health check is configured separately (a path Render polls over HTTP on the port it was told about) and does not consult the Dockerfile's `HEALTHCHECK` directive. The check itself — asking `/api/health` for `status: ok` rather than just a 200 — is the right design to carry over either way. |
| **Building or fetching the gitignored data** | This is the big one, covered in §b: Render builds the image **from the GitHub repo**, which is a clean clone. None of `data/processed/`, `data/index/`, `data/layers/dda/`, `data/gazetteer/` exist in it, and the Dockerfile's `COPY` lines for them would copy next to nothing (the directories exist as empty, via `.gitkeep`, so the build would not fail — it would succeed and produce a container that reports `"status": "degraded"` and 503s every question, exactly as `docs/DEPLOY.md` §2 warns for a skipped build step). |
| **The model cache location** | Already sensible: `settings.model_cache_dir` is `data/index/models`, the same directory the Dockerfile copies, so *if* the data existed on the build machine, the model would not be re-downloaded at container start. The gap is upstream of this (§b), not here. |
| **Image size** | `docs/DEPLOY.md` already measures it: **about 1.2 GB uncompressed, ~600 MB compressed.** Of that, roughly 152 MB is `data/index/models/`, and 88 MB of that is the reranker's weights, which are never loaded at runtime in the shipped configuration (`USE_RERANKER=0`). That is the one easy trim available without touching behaviour — excluding the reranker cache from what gets baked in would save that 88 MB from a Render build/pull, though Render's free tier does not meter image size directly the way it meters RAM and build minutes. |

---

## d. Client IP behind a proxy

**Today:** `client_address()` in `app/api.py` (line 192-194) returns `request.client.host`
directly — the TCP peer address Starlette sees. Behind any reverse proxy (Render's edge
is one), that is the proxy's own address for every request, not the visitor's. The
per-IP rate limiter (`RATE_LIMIT_PER_MINUTE`, in-memory, keyed by `client_address()`)
would then see all traffic as coming from one address and apply its limit globally
across every visitor rather than per visitor — the daily cap still works as intended
(it is already global), but the per-minute guard against "one browser tab in a loop"
would instead throttle the whole service after ten requests a minute from anyone.

**What would make it read `X-Forwarded-For` safely, described only:**
1. Run `uvicorn` with `--proxy-headers` and a `--forwarded-allow-ips` value naming
   Render's edge, not `*`. `--proxy-headers` makes uvicorn parse `X-Forwarded-For` /
   `X-Forwarded-Proto` from a request and populate `request.client.host` with the
   left-most address in that header *only when the request's actual peer address is in
   `--forwarded-allow-ips`* — which is the safety property: trusting the header from an
   untrusted peer lets any caller claim any IP and defeat the rate limiter entirely by
   rotating a forged header value.
2. The open question for Render specifically is what `--forwarded-allow-ips` should be
   set to — Render's platform-level documentation would need to say whether its edge
   proxy's address is fixed, in a published range, or whether the recommended value on
   Render is `*` because the container is not otherwise reachable except through that
   edge (some PaaS targets do say this safely, because no path to the container bypasses
   their proxy). That is a platform fact to confirm before setting the flag, not a code
   change.

Nothing was changed to produce this section — `client_address()` and the `uvicorn`
command in the Dockerfile are exactly as they are today.

---

## e. Memory: what is actually resident

`docs/DEPLOY.md` already carries the project's own estimate, made when choosing an EC2
size: **"about 400 MB with the ONNX runtime"** for the embedding model, the Chroma
collection, the BM25 corpus and eight GeoJSON layers loaded at startup, which is why that
guide picked a 2 GB instance over a 1 GB one ("`t3.micro` ... will survive right up until
it does not"). Render's free tier offers 512 MB — a quarter of what the project's own
prior sizing decision already called too tight at 1 GB. The breakdown, roughly, from the
on-disk sizes above plus the project's own figure:

| component | on disk | in memory (rough) | loaded |
| --- | --- | --- | --- |
| embedding model (ONNX runtime + weights) | 65 MB | the bulk of the ~400 MB figure above — an ONNX session plus runtime overhead typically runs several times its weight size | always, at startup |
| Chroma collection (653 vectors × 384 dims) | 14 MB | tens of MB | always, at startup |
| BM25 corpus | 904 KB | comparable to disk size | always, at startup |
| 8 GeoJSON layers + their STRtrees | 4.9 MB | some multiple of disk size for the parsed shapely geometries and the tree index | always, at startup — **including `yamuna_river`, which `get_zones()` does not use for any policy** (`EXTRA_LAYERS` in `app/spatial.py`); small (3 features), so a minor finding rather than a real saving |
| reranker (cross-encoder) | 88 MB | **0 — not loaded** | only if `USE_RERANKER=1`; off by default, so not resident in the shipped configuration |
| uvicorn / FastAPI / Python baseline | — | typical for a small Python async service | always |

**Dhruv is measuring the real process separately**, so the numbers above are the
project's own prior estimate plus what the code shows is or is not loaded, not a fresh
profile. The one load-bearing fact for this target: the project already concluded 1 GB
was an uncomfortable fit for this working set, and 512 MB is half of that.

---

## f. Runtime environment variables and secrets

From `.env.example` and `app/config.py`, with the safe production defaults already named
in `docs/DEPLOY.md`'s own cost-safety checklist and `.env.example`'s comments:

| variable | default | production value |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | whichever provider has a budget set; `anthropic` or `groq` |
| `ANTHROPIC_API_KEY` / `GROQ_API_KEY` | unset | the real key, passed as an environment variable only — never baked into the image (`.dockerignore` already excludes `.env*`) |
| `LLM_MODEL` | follows the provider | leave at the small default (`claude-haiku-5-5` or `openai/gpt-oss-120b`); an accidental larger model is the cost risk `docs/DEPLOY.md` flags |
| `ZONEWISE_DEV` | `0` / unset | **must stay unset** — it 404s the dev eval endpoints and the Verify tab when off (D-075); `docs/DEPLOY.md` already says this in bold |
| `CORS_ORIGINS` | `http://localhost:5173` | the deployed site's own origin, nothing else |
| `RATE_LIMIT_PER_MINUTE` | 10 | fine as shipped |
| `RATE_LIMIT_PER_DAY` | 300 | the number that actually caps the API bill; fine as shipped, reviewed per `docs/DEPLOY.md`'s checklist |
| `SUPPORT_CHECK` | `enforce` (as of D-103) | already the production default; no change needed |
| `ABSTAIN_SIGNAL`, `ABSTAIN_THRESHOLD` | `dense_cosine`, `0.5804` | provisional (D-071); unrelated to deployment readiness |
| `USE_RERANKER` | `0` | leave off — it is also the one lever that would shrink the image if its weights were excluded from what gets copied in (§c) |
| `MAX_QUESTION_CHARS`, `MAX_REQUEST_BYTES` | 500, 65536 | fine as shipped |

No variable here is new; this section only says which of the existing ones matter for a
public deployment and confirms their already-documented safe values.

---

## g. External hosts a build or a running container would need to reach

**At container runtime** (not build time): `api.anthropic.com` or `api.groq.com` (only
when answering a question — five of seven endpoints need neither, D-050);
`nominatim.openstreetmap.org` (geocoding fallback, 1 request/second, already
rate-limited and cached, D-073); OpenStreetMap's tile servers (reached by the *browser*,
not the server, for the map background).

**At build time, only if the gitignored data were built inside the Render build step**
(§b) rather than carried in some other way: Hugging Face's CDN, for the embedding model
and (if included) the reranker weights; `gis.dda.org.in`, for the eight map layers;
`overpass-api.de`, for the metro gazetteer; and, to regenerate `data/processed/` at all,
`dda.gov.in`, `indiankanoon.org` and `greentribunal.gov.in` for the raw PDFs themselves.

**Flagging the two DDA hosts specifically, as asked:** `dda.gov.in` and
`gis.dda.org.in` are Indian government services with no stated SLA or CDN presence
documented anywhere in this repository's research, and `scripts/06_fetch_layers.py`'s own
docstring already calls the ArcGIS server "a public government service we do not rush" —
language chosen because it has been observed to be slow, not just out of politeness. A
build server outside India reaching either host carries a real risk of timeouts or
throttling that a build server inside India would not see, and Render's free-tier build
infrastructure's location is not something this audit can confirm from inside the repo.

---

## h. Licence notes for each data source

From `data/sources.csv` and `docs/DATA.md` / `docs/DEPLOY.md`'s own "Licences and
attribution" section:

| source | licence note on record |
| --- | --- |
| MPD-2047 gazette, FAQs, the Delhi High Court order (the three indexed documents) | No licence field in `sources.csv`; `docs/DEPLOY.md` calls them "public records of the Government of India and the courts, quoted with document, clause and page number on every answer." No explicit redistribution licence is recorded anywhere in this repository for these three. |
| The six scanned explainer PDFs, the land-use plan map, the superseded publication PDF, the dead NGT order, the excluded NGT/GNCTD report | `include=no` or `reference` in `sources.csv`; not indexed, not shipped in any built artifact. No licence question arises for what is not redistributed. |
| DDA map layers (`data/layers/dda/`) | **"Not stated by DDA anywhere on the service or the portal"** — quoted directly from `data/layers/manifest.json`'s own `licence` field. This is exactly why the layers are gitignored and only the manifest is committed (D-014, D-030): the project's own conclusion is "we do not know we may redistribute them," so it displays them and does not serve a bulk download. |
| OpenStreetMap-derived data (the metro gazetteer; map tiles and Nominatim, both reached directly by the browser or by the server, not stored) | © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/). `docs/DEPLOY.md` notes that if the gazetteer were ever served as a downloadable file, the ODbL's share-alike terms would apply to it; today it is used internally by `locate_place`, not served as a file. |

Nothing here changes with the deployment target — a Render free service redistributes
the same baked-in layers and gazetteer a laptop or an EC2 instance would, so the same
constraints (display, don't bulk-download; carry the OSM attribution) apply unchanged.

---

## Top risks, most serious first

1. **The build cannot reproduce the data it needs.** Render builds the Dockerfile from
   the GitHub repo — a clean clone. `data/raw/`, `data/processed/`, `data/index/` and
   `data/layers/dda/` are all gitignored by CLAUDE.md's own rule, and `data/raw/` cannot
   be rebuilt from anything in the repository at all. The Dockerfile as written would
   build successfully and serve a container that is permanently in search-only "degraded"
   mode with zero chunks. This is not a Render-specific gap — it is the same fact
   `docs/DEPLOY.md` leads with for EC2 ("skipping it produces an image that starts...
   and returns 503 for every question") — but EC2's `docker build` runs on a laptop that
   already has the data; Render's does not, and has no equivalent step.
2. **512 MB may not be enough.** The project's own prior sizing decision (`docs/DEPLOY.md`
   §3) measured roughly 400 MB for the embedding model, Chroma, BM25 and the map layers
   together and chose a 2 GB instance over 1 GB specifically because 1 GB felt too close
   to the edge. 512 MB is half of the instance size the project already rejected as risky.
3. **The container does not listen on `$PORT`.** A fixed `--port 8000` will not satisfy
   Render's routing, which expects the app to bind to the port Render assigns at runtime.
4. **The rate limiter would misbehave behind Render's proxy.** Every visitor would share
   one per-minute bucket unless `request.client.host` is corrected for the proxy (§d);
   the daily cap, already global, is unaffected.
5. **A cold start after Render's idle sleep pays the full startup cost again** — loading
   the embedding model, Chroma, BM25 and eight GeoJSON layers — on every wake, not just
   on first deploy, because the free tier's disk is ephemeral and the process is killed
   and restarted rather than paused.

---

## A recommended deployment plan, stated and not implemented

1. **Settle how the gitignored data reaches the build**, before anything else — this is
   risk 1 and nothing downstream matters until it is answered. Three shapes exist,
   described only: (a) run the pipeline inside the Render build step, which needs the
   raw PDFs to be reachable from *somewhere* at build time — committing them would break
   CLAUDE.md's rule 3 and is not proposed; (b) publish the already-built
   `data/processed/`, `data/index/` and `data/layers/dda/` as a downloadable artifact
   (for instance a GitHub Release asset) and have the build step fetch and unpack it —
   this keeps the data out of git history while still letting Render's build retrieve it
   over plain HTTPS from GitHub; or (c) use a target with a persistent volume or a
   pre-built registry image instead of a from-repo build, which is a different hosting
   decision than "one free Render web service." This is the project lead's call.
2. **Measure real resident memory** against the free tier's 512 MB before trusting it —
   Dhruv is already doing this separately — and treat risk 2 as a possible hard blocker
   rather than a tuning problem if the number comes in close to the limit.
3. **Make the container honour `$PORT`** and confirm what Render's own health check
   expects, separately from the Docker `HEALTHCHECK` already in place.
4. **Decide the `--forwarded-allow-ips` value** once Render's edge behaviour is confirmed,
   and apply it alongside `--proxy-headers` so the per-minute rate limiter means what it
   says.
5. **Set `CORS_ORIGINS` to the deployed origin and leave `ZONEWISE_DEV` unset**, exactly
   as `docs/DEPLOY.md`'s existing checklist already says for any public deployment.
6. **Consider trimming the reranker's 88 MB from the image** if it is never turned on —
   a size saving with no behaviour change, since it is already lazy-loaded and would
   simply need excluding from what the Dockerfile copies.

Nothing above was implemented. No file other than this report was changed to produce it.
