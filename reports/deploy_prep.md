# Deployment preparation: what changed, and what Dhruv has to do

**22 October 2026.** The work that turns `reports/deploy_audit.md` from a list of
problems into a deployment. Eight tasks, eight commits, one agent fix and seven pieces of
plumbing. Nothing in retrieval, the prompts, the chunks, the tags, the thresholds or the
eval questions was touched, so **the `v1.0-rc2` freeze (D-108) still holds**.

**The three numbers to carry to the portal:**

| | |
| --- | --- |
| the image | `ghcr.io/<your github owner>/zonewise:latest` |
| the bundle | `dist/zonewise-data-20261022.zip`, 8,756,312 bytes (8.4 MB), 40 files, 653 chunks |
| its SHA-256 | `c7475ed38973efc43bee41e3319753ffe5cbad899d52cf031eb041a50e39907b` |

**The one thing that is not verified:** the Docker image has never been built. The
sandbox that rewrote it cannot reach a container registry, so `docker build` was not
available. [What was done instead](#what-was-verified-and-how) is listed below, and the
first real build is step C of `docs/DEPLOY.md`.

---

## 1. What changed, per task

| task | what | commit |
| --- | --- | --- |
| 1 | the agent's last round is asked for an answer | `c513fed` |
| 2 | memory trims, and `peak_rss_mb` in `/api/health` | `2fd6ff6` |
| 3 | `$PORT`, and the client address behind a proxy | `fe219da` |
| — | the lead's decisions recorded (D-111 to D-113) | `d28e640` |
| 4 | the data bundle and the startup bootstrap | `cb263b4` |
| 5 | the image rewritten to carry code only | `724b50f` |
| 6 | the image workflow, and tests for the deployment files | `f0bc8f2` |
| 7 | `docs/DEPLOY.md` rewritten; the AWS assumptions removed | `7766990` |
| 8 | this report | (this commit) |

New decisions: **D-109** (the agent's forced last round), **D-110** (the memory trims),
**D-111** (the host), **D-112** (the data as a bundle), **D-113** (`$PORT` and the proxy
hop count), **D-114** (the bundle and the bootstrap), **D-115** (the image).

### Task 1 — the agent's last round · `c513fed`

**The bug.** A manual re-check asked *"What can be built near Hauz Khas metro?"*. The
agent located the place, searched twice, ran out of rounds, and returned *"used all its
tool calls without reaching an answer"* — **while holding six retrieved clauses it had
never been asked to use.** The retrieval had worked; the only thing missing was a turn in
which answering was the model's only option.

**The fix.** On the last round `agent_max_rounds` allows, `run_agent` calls the model
with `tool_choice="none"`. The tool definitions still travel, because a conversation
carrying `tool_use` and `tool_result` blocks is rejected without them, but calling one is
forbidden. The reply is validated exactly as any final answer is: the JSON contract, the
structural check against the labels this run issued, the one retry, then the claim check.
A tool call that arrives anyway is ignored rather than run — the round has been spent.

**What did not change.** Not a word of any prompt (D-108). The cap is still four rounds,
still four model calls. `tool_choice` is a new parameter on the one `chat` signature in
`app/llm.py`, translated per provider — Anthropic takes `{"type": "none"}`, Groq the bare
string — so no provider knowledge reached `app/agent.py`.

`max_rounds_reached` is now reachable only with `max_rounds=0`, and a test pins that
case rather than leaving a dead constant lying about.

Three new tests with the FakeLLM, no key: a model that calls tools in rounds 1 and 2 and
answers in the forced round 3; a model that asks for a tool in **every** round, which
runs two tools and not three; and the zero-round case. One more in `test_llm_groq.py`
asserts the payload Groq receives.

### Task 2 — memory · `2fd6ff6`

Four things, none of which changes an answer.

1. **The cross-encoder is imported only when something reranks.** `app/rerank.py` used
   to `from fastembed.rerank.cross_encoder import TextCrossEncoder` at module scope, and
   `app/api.py` imports `app.rerank` for `/api/health` — so **every** server process
   loaded it, and it brings `fastembed`, `onnxruntime` and `tokenizers` with it, although
   `USE_RERANKER=0` means the class is never built. `available()` now answers with
   `importlib.util.find_spec`, which locates the module without executing it. Measured by
   a new test: after `import app.api`, none of those four modules is in `sys.modules`,
   where before the first of them pulled in the other three.
2. **Chroma never builds its default embedding function.** It already did not, and the
   reason is one keyword argument: chromadb's `get_collection` and `create_collection`
   take `DefaultEmbeddingFunction()` as a **default argument value**, so leaving the
   parameter out binds one. `app/indexing.py` passes `embedding_function=None` to both.
   Three tests now hold that in place, one of them a `needs_data` test that runs a real
   hybrid search with `ONNXMiniLM_L6_V2.__init__` replaced by something that raises.
3. **`load_layers()` loads seven layers, not eight.** `yamuna_river` answers one
   question — is this candidate zone O test point in the water — and
   `scripts/07_test_points.py` is its only caller. Three polygons and an STRtree over
   them, parsed at every startup for nothing. The audit itself calls this "a minor
   finding rather than a real saving", and that is the honest size of it.
4. **`/api/health` reports `peak_rss_mb`** from `resource.getrusage`, and the same number
   is logged once after startup. Peak rather than current, because the peak is what gets
   a process killed. On Windows `resource` does not exist, so the key is **omitted** — a
   null in a field whose name is a number reads as a measurement of zero.

### Task 3 — port and proxy · `fe219da`

**`$PORT`.** `scripts/serve.py` defaults to it, and the image's command does too. A
container that listens on a fixed port fails a platform's routing whatever `EXPOSE` says.

**`TRUSTED_PROXY_HOPS`**, default `0` — exactly today's behaviour, the socket peer. Above
0, the client address is read from `X-Forwarded-For` by **counting that many entries from
the right**. Each proxy appends the address it received the request from, so behind one
trusted proxy the last entry is the visitor, and everything to its left is whatever the
caller chose to send. A `:port` suffix is stripped (Azure App Service appends the client
port), IPv6 is read bracketed and bare, the address is normalised so one visitor is one
rate-limit bucket, and a missing or malformed header falls back to the peer.

Without it, every visitor behind App Service's proxy shares one address and ten requests
a minute from anyone throttles the whole service. Twenty tests, every case of the parser
plus one end-to-end check that two visitors through one proxy get their own budgets.

### Task 4 — the data bundle · `cb263b4`

`scripts/make_data_bundle.py` writes `dist/zonewise-data-<date>.zip`: the five runtime
reads from the audit's section (a) and nothing else. **No raw PDFs** (109 MB, nothing
reads them once the chunks exist), **no logs**, and **no model weights** — those are baked
into the image instead. A `manifest.json` rides inside with every file's size and
SHA-256, the git commit and the chunk count. `dist/` is gitignored.

`app/data_bootstrap.py` runs as its own step before uvicorn: `python -m
app.data_bootstrap && exec uvicorn ...`. Data on disk → do nothing. `DATA_BUNDLE_URL`
set → download (urllib, 60-second timeout, 3 attempts), check `DATA_BUNDLE_SHA256`
**before** unpacking anything, extract into a staging directory inside `data/`, check the
manifest against what came out, then move each file into place with `os.replace`.
Neither → one log line naming what is missing and both ways to fix it, and exit 1, which
`&&` turns into "no server".

A separate process rather than the API's lifespan on purpose: the server's own design is
to boot degraded and let `/api/health` explain (D-065), which is right for a laptop
halfway through the pipeline and wrong for a container that cannot fix itself.

**The URL is never logged** — it is a SAS URL and the token is in its query string, so
every line names the host only, and every error message is scrubbed of the URL in case a
library put it there. 21 tests, all over a `file://` URL so the real download path runs
with no network.

### Task 5 — the image · `724b50f`

The Dockerfile keeps its two stages and loses its data. It copies `app/` and `scripts/`,
installs the locked dependencies, takes `web/dist` from the node stage, **downloads the
fastembed weights at build time** — which is also the build's own smoke test, since
`embed_query("warmup")` loads the ONNX session and runs one inference — creates the data
directories owned by uid 10001, and starts the bootstrap before uvicorn with `exec` so
uvicorn gets the platform's `SIGTERM`.

Production defaults in the image: `ZONEWISE_DEV=0`, `SUPPORT_CHECK=enforce`,
`LLM_PROVIDER=groq`. `CORS_ORIGINS` is deliberately **not** set, because it depends on the
hostname; unset is safe, since the frontend is served from the same origin as the API and
needs no CORS permission at all.

`.dockerignore` now excludes the whole of `data/` in one line, plus `dist/` and `eval/`.
A build from a laptop therefore produces the same image as one from a clean checkout,
instead of silently baking in the indexes.

**Estimated size: about 1.0 GB uncompressed, roughly 500 MB compressed** — from the
measured parts (`python:3.12-slim` ~130 MB, the uv binaries ~45 MB, the dependency
environment ~600 MB, the model 65 MB, the frontend ~1 MB), not from an image. About
150 MB smaller than the old one, which carried the reranker's 88 MB of unused weights and
~25 MB of built data.

### Task 6 — the workflow · `f0bc8f2`

`.github/workflows/image.yml`: `workflow_dispatch` and `v*` tags, `docker/build-push-action`,
pushing `ghcr.io/<lower-cased owner>/zonewise` as `:latest` and `:<short sha>`, with
`GITHUB_TOKEN` and `packages: write`. The owner is lower-cased in a step rather than
typed, because GHCR rejects a capitalised owner **at push time, after the whole build**.
The layer cache lives in the Actions cache, and the run's summary prints the image names
to paste into App Service. `ci.yml` is untouched.

### Task 7 — the docs · `7766990`

`docs/DEPLOY.md` is now the Azure path as numbered steps with the portal clicks,
including where the allowed-regions list hides (Policy → Assignments → *Allowed resource
deployment regions* → Parameters). README, `docs/ARCHITECTURE.md` and
`docs/PROJECT_STATUS.md` no longer mention EC2, Caddy or Lightsail, and CLAUDE.md's
deployment line describes the bundle.

One thing found while doing it: the `X-Forwarded-For` parser tests had landed in
`tests/test_api.py`, which is marked `needs_data` as a whole module — so the twenty
tests that need no data at all were being **deselected in CI**, which is the one place
they matter. They moved to `tests/test_proxy_headers.py`. The test counts in README,
`check.ps1`, `ci.yml`, CLAUDE.md and `PROJECT_STATUS.md` were stale by that much and
more, and are now right: **629 tests, 591 of which need no data**.

---

## What was verified, and how

| | |
| --- | --- |
| `scripts\check.ps1` | **green**: ruff clean, **629 tests pass** (1 skipped on Windows — the `peak_rss_mb` health-body check needs POSIX), frontend built |
| the bundle | built on a clean tree at `7766990`: 40 files, 8,756,312 bytes, `c7475ed3…`, 653 chunks |
| the bundle, read back | extracted through `ensure_data` into a temporary directory: 653 chunks, 8 layers, status `downloaded`, 0.3 s from a local file; and a deliberately wrong hash refused with nothing extracted |
| the bootstrap as the image runs it | `python -m app.data_bootstrap` → `runtime data is already in place`, exit 0 |
| the build-time model step | `embed_query("warmup")` run locally: 384 dimensions |
| the health check's one-liner | run locally: valid Python, and a connection failure is a non-zero exit, which is the right answer for an unhealthy container |
| both workflows | parsed as YAML; jobs and triggers are what they should be |
| the Dockerfile | read line by line against the audit's section (c), and its instructions parsed with continuations joined, to see what the Docker parser will see |
| `tests/test_deploy_files.py` | 22 tests pinning the facts the deployment turns on: no data copied in, the data directories created and `chown`ed, `$PORT` honoured, the bootstrap before uvicorn with `&&`, the health check asking for `status == ok`, the production defaults set, no secret ever an `ENV`, `.dockerignore` excluding what it should, and the workflow lower-casing the owner |

**`docker build` was not run, and no image exists.** That is the honest state. The text
assertions in `tests/test_deploy_files.py` are unusual for this repository and are there
for exactly this reason: they cannot prove the image builds, but they make a later edit
that breaks one of the deliberate decisions fail in pytest rather than in Azure's log
stream.

**No LLM call was made** to produce any of this. Every test uses the FakeLLM.

---

## Dhruv's steps

In the order of `docs/DEPLOY.md`, which has the clicks. About 90 minutes, most of it
waiting for the first image build.

### A. Azure (10 min)

- [ ] Activate Azure for Students at <https://azure.microsoft.com/free/students>
- [ ] Portal → **Policy** → **Assignments** → **"Allowed resource deployment regions"** →
      **Parameters**, and write down one allowed region. Use the same one for everything.

### B. The data (20 min)

- [ ] `uv run python scripts\make_data_bundle.py` — or use the one already built:
      `dist\zonewise-data-20261022.zip`
- [ ] Copy its **SHA-256**:
      `c7475ed38973efc43bee41e3319753ffe5cbad899d52cf031eb041a50e39907b`
      (if you rebuild the bundle, this changes — use the one the script prints)
- [ ] Create a **Storage account**: resource group `zonewise-rg`, your allowed region,
      Standard, **LRS**
- [ ] Create a container named `bundles`, access level **Private**
- [ ] Upload the zip
- [ ] Click the blob → **Generate SAS** → permissions **Read** only, expiry **12 months**,
      HTTPS only → copy the **Blob SAS URL**
- [ ] Keep that URL out of git, out of screenshots and out of chat. It is the secret.

### C. The image (15 min, mostly waiting)

- [ ] `git push`
- [ ] GitHub → **Actions** → **Image** → **Run workflow**
- [ ] When green, copy the image name from the run summary:
      `ghcr.io/<owner>/zonewise:latest`
- [ ] GitHub → your **profile** → **Packages** → **zonewise** → **Package settings** →
      **Change visibility** → **Public**
      (or keep it private and give App Service a token with `read:packages`)

### D. The Web App (20 min)

- [ ] **Create a resource** → **Web App**: resource group `zonewise-rg`,
      **Publish: Container**, **Linux**, your allowed region, plan **Basic B1**
- [ ] Container tab: registry `https://ghcr.io`, image `<owner>/zonewise:latest`
- [ ] **Environment variables** → **App settings**, these twelve and nothing else:

| setting | value |
| --- | --- |
| `GROQ_API_KEY` | your `gsk_…` key |
| `LLM_PROVIDER` | `groq` |
| `LLM_MODEL` | `openai/gpt-oss-120b` |
| `SUPPORT_CHECK` | `enforce` |
| `ZONEWISE_DEV` | `0` |
| `DATA_BUNDLE_URL` | the SAS URL from B |
| `DATA_BUNDLE_SHA256` | `c7475ed38973efc43bee41e3319753ffe5cbad899d52cf031eb041a50e39907b` |
| `TRUSTED_PROXY_HOPS` | `1` |
| `WEBSITES_PORT` | `8000` |
| `CORS_ORIGINS` | `https://<your app>.azurewebsites.net` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `RATE_LIMIT_PER_DAY` | `300` |

- [ ] **Configuration** → **General settings** → **Always on: On** → Save
- [ ] **Monitoring** → **Health check** → Enable, path `/api/health` → Save
- [ ] **Log stream**, and watch for `data bundle in place: 40 files, 653 chunks` then
      `startup complete: peak RSS … MB, 653 chunks`

### E. Check it (10 min)

- [ ] `/api/health` says `"status": "ok"`, `"chunks": 653`, `"llm_available": true`,
      `"dev_mode": false`, `"support_check": "enforce"`, and carries `peak_rss_mb`
- [ ] **Write the `peak_rss_mb` number down.** It is the first real measurement of this
      app's memory on Linux, and B1 gives 1.75 GB.
- [ ] The map draws, with its zone overlays
- [ ] One map question: click central Delhi, *"How much can I build here?"*
- [ ] One agent question: *"What can be built near Hauz Khas metro?"* — and watch the
      tool trace. **This is the question task 1 fixed**, so it is worth watching: it
      should answer or decline, never "used all its tool calls".
- [ ] `/api/dev/eval/questions` is a **404**
- [ ] **Cost Management → Budgets** → 25 USD a month with an email alert

---

## What could still bite

1. **The image build is the first one ever.** If it fails, it will be in one of three
   places: a `COPY` path, a dependency wheel that has no manylinux build, or the model
   download. The build log names the step.
2. **`peak_rss_mb` on Linux is unknown.** The Windows measurement was 782 MB private /
   251 MB working set, and the audit's estimate was ~400 MB for the model, Chroma, BM25
   and the layers. B1 has 1.75 GB. Anything under about 900 MB is comfortable; if the
   number comes back near 1.4 GB, that is the signal to look rather than to wait.
3. **The first startup is slow** and the health check's `start-period` is 180 seconds for
   that reason: download, extract, then load the model, Chroma, BM25 and seven layers on
   one core. If App Service restarts the container in a loop, read the log stream before
   assuming the image is wrong.
4. **`fastembed` must find the baked-in weights offline.** The cache directory is the one
   `app/indexing.py` already reads (`data/index/models`), and the bundle deliberately does
   **not** carry weights that would overwrite it. If a start ever hangs on first use,
   that is where to look.
5. **The request log does not survive a restart.** App Service's container filesystem is
   ephemeral. `docs/DEPLOY.md` says how to read it through the SSH console and what
   mounting an Azure Files share would involve; that is a separate decision.
6. **The SAS URL expires in 12 months.** Put a note somewhere you will see it in
   October 2027, or the app will stop starting with a very clear log line.
