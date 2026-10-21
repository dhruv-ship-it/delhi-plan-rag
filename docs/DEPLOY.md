# Deploying ZoneWise

For someone deploying this for the first time. It assumes a laptop with the repository
on it, a GitHub account, and an Azure account with nothing set up yet.

**What you are building:** one Docker container on **Azure App Service for Containers**
(Linux, Basic B1). GitHub Actions builds the image and pushes it to the GitHub Container
Registry. The runtime data — the chunks, the indexes and the map layers — is **not** in
the image and **not** in the repository: you build a zip of it on your laptop, upload it
to a private Azure Blob container, and the container downloads it at startup through a
read-only link. See D-111, D-112 and D-114 in `DECISIONS.md` for why.

```
   browser ──HTTPS──▶  App Service (Linux, B1)  ──HTTPS──▶  api.groq.com
                       ghcr.io/<owner>/zonewise              (only when answering)
                       one uvicorn worker on $PORT
                              │
                              └── at startup ──▶ Azure Blob Storage (private)
                                                 zonewise-data-<date>.zip
```

**Cost.** B1 is about **13 USD a month**, from the 100 USD Azure for Students credit,
with no card on file. Blob storage for an 8 MB zip is a few cents. The Groq free tier is
free. The [cost safety checklist](#cost-safety-checklist) is still not optional.

**Time.** About 90 minutes the first time, most of it waiting for the image build.

---

## The order of things

| | step | where |
| --- | --- | --- |
| A | Activate Azure for Students and find your allowed regions | portal |
| B | Build the data bundle, upload it, make a read-only link | laptop + portal |
| C | Build the image in GitHub Actions and make the package public | GitHub |
| D | Create the Web App and set the app settings | portal |
| E | Check it works | browser |
| F | Update it later | laptop + GitHub |

Do them in order. B before D, because two of the app settings come out of B.

---

## A. Azure for Students, and which regions you may use

1. Go to <https://azure.microsoft.com/free/students> and sign in with your university
   email. You get **100 USD of credit for 12 months** and no card is asked for.
2. In the portal, search for **Subscriptions** and confirm you see one called
   *Azure for Students*.

**Now find the regions you are allowed to deploy in.** A student subscription restricts
them, and picking a region that is not allowed fails at the very last click with a
policy error that does not name the allowed list.

1. In the portal search bar, type **Policy** and open it.
2. In the left menu, **Assignments**.
3. Find the assignment named **"Allowed resource deployment regions"** (it may be listed
   under your subscription's scope). Click it.
4. Click **Parameters**. The list of region names there is the list you may use.
5. **Write down one region** from that list and use the same one for everything below.
   Something like `Central India`, `East US` or `West Europe`, depending on what yours
   says. A region near you makes the site feel faster; a region near nothing is fine too.

> Everything below says "your allowed region". Use the one you wrote down.

---

## B. The data bundle

The container starts with no data at all. This is the step that gives it some.

### B1. Build the zip, on your laptop

```powershell
# with the pipeline already run, so data/ has the indexes and the layers
uv run python scripts\make_data_bundle.py
```

It prints something like:

```
Wrote D:\projects\delhi-plan-rag\dist\zonewise-data-20261022.zip
  files     40 gazetteer 1, index 30, layers 8, processed 1
  chunks    653
  commit    409c310
  unpacked  20.9 MB
  zip       8.4 MB (8756153 bytes)
  sha256    81e900de5b67221f11769a40a6be27cce6df6747ae944712a80cd0ccbcefee12
```

**Copy that `sha256` line somewhere.** You will paste it into an app setting in step D,
and it is what stops the container starting on a bundle that is not the one you built.

If it says *"Nothing to pack"* or warns that the data is incomplete, run the pipeline
first:

```powershell
uv run python scripts\05_build_index.py      # about 3 minutes
uv run python scripts\06_fetch_layers.py     # about 1 minute, talks to DDA's server
uv run python scripts\build_gazetteer.py     # one Overpass request, optional
```

### B2. A storage account with a private container

1. Portal → **Create a resource** → search **Storage account** → **Create**.
2. Fill in:
   - **Subscription**: Azure for Students
   - **Resource group**: **Create new** → `zonewise-rg`. Use this group for everything,
     so deleting it later deletes the whole deployment.
   - **Storage account name**: something globally unique and lower case, e.g.
     `zonewisedata<your initials>`
   - **Region**: your allowed region
   - **Primary service**: *Azure Blob Storage*
   - **Performance**: Standard
   - **Redundancy**: **Locally-redundant storage (LRS)** — the cheapest, and this file
     is rebuildable in ten minutes from your laptop
3. **Review + create** → **Create**. Wait, then **Go to resource**.
4. Left menu → **Containers** → **+ Container**.
   - **Name**: `bundles`
   - **Anonymous access level**: **Private (no anonymous access)** ← this is the point
   - **Create**

### B3. Upload the zip

1. Open the `bundles` container → **Upload**.
2. Browse to `dist\zonewise-data-<date>.zip` → **Upload**.

### B4. A read-only link that expires in a year

1. In the container, click the blob you just uploaded.
2. Top menu → **Generate SAS** (the tab beside *Overview*).
3. Set:
   - **Signing method**: Account key
   - **Permissions**: **Read** only. Untick everything else — no Write, no Delete, no
     List.
   - **Start**: now. **Expiry**: **12 months from today** (type the date).
   - **Allowed protocols**: HTTPS only
4. Click **Generate SAS token and URL**.
5. Copy the **Blob SAS URL** — the long one ending in `&sig=...`.

> **That URL is a secret.** Anyone who has it can download the bundle. It goes in an App
> Service setting in step D and **nowhere else**: not in the repository, not in a commit,
> not in a screenshot. ZoneWise never logs it — only its host name appears in the log
> (D-114).

---

## C. The image

### C1. Push the code, then run the workflow

```powershell
git push            # the workflow lives in the repository, so it has to be there
```

1. GitHub → your repository → **Actions**.
2. In the left list, click **Image**.
3. Click **Run workflow** → **Run workflow** (the branch is `main`).
4. Wait. The first run takes **5 to 15 minutes**: it installs the whole dependency
   environment and downloads the embedding model. Later runs reuse the layer cache.
5. When it is green, open the run. Its summary prints the two image names:

   ```
   ghcr.io/<owner>/zonewise:latest
   ghcr.io/<owner>/zonewise:<short sha>
   ```

**If the build fails**, this is the first time the Dockerfile has ever been built — it
was written without access to a container registry and verified by reading
(`reports/deploy_prep.md` says exactly what that means). Read the failing step's log; it
will be a `COPY` path, a dependency wheel or the model download.

### C2. Make the package public

The package is private until you say otherwise, and App Service cannot pull a private
GHCR package without credentials.

1. GitHub → your **profile** (not the repository) → **Packages**.
2. Click **zonewise** → **Package settings** (right side, or the gear).
3. Scroll to **Danger Zone** → **Change visibility** → **Public** → type the package
   name to confirm.

The image contains code only — no data, no keys — so making it public publishes nothing
that the repository does not already publish.

**If you would rather keep it private:** leave it private, create a GitHub personal
access token (classic) with the single scope **`read:packages`**, and in step D fill in
App Service's *Registry* fields — server `ghcr.io`, username your GitHub name, password
that token — instead of leaving them blank.

---

## D. The Web App

### D1. Create it

1. Portal → **Create a resource** → **Web App** (under *Web*, or search for it).
2. **Basics** tab:
   - **Resource group**: `zonewise-rg` (the one from step B2)
   - **Name**: `zonewise-<something>` — this becomes
     `https://zonewise-<something>.azurewebsites.net`, so it has to be globally unique
   - **Publish**: **Container** ← not Code
   - **Operating System**: **Linux**
   - **Region**: your allowed region
   - **Linux Plan** → **Create new** → `zonewise-plan`
   - **Pricing plan**: click **Change size** → **Basic B1** (1 core, 1.75 GB). Not Free
     F1: 1 GB with no Always On, and this app loads the embedding model at startup.
3. **Container** tab:
   - **Image Source**: **Other container registries**
   - **Access Type**: **Public** (or **Private** with the token from C2)
   - **Registry server URL**: `https://ghcr.io`
   - **Image and tag**: `<owner>/zonewise:latest` — all lower case
4. **Review + create** → **Create**. Wait for *Your deployment is complete*, then
   **Go to resource**.

It will not work yet. It has no data and no key.

### D2. The app settings

Left menu → **Settings** → **Environment variables** → **App settings** tab. Add each of
these with **+ Add**, then click **Apply** at the bottom and confirm the restart.

| name | value | why |
| --- | --- | --- |
| `GROQ_API_KEY` | `gsk_...` | your key from <https://console.groq.com/keys> |
| `LLM_PROVIDER` | `groq` | which service answers (D-082) |
| `LLM_MODEL` | `openai/gpt-oss-120b` | the small open model this project runs on |
| `SUPPORT_CHECK` | `enforce` | drop a sentence its own clause does not state (D-103) |
| `ZONEWISE_DEV` | `0` | keeps the verification endpoints 404 (D-075) |
| `DATA_BUNDLE_URL` | the SAS URL from B4 | **secret.** Paste the whole thing, `?sig=` and all |
| `DATA_BUNDLE_SHA256` | the sha256 from B1 | refuses to start on the wrong bundle |
| `TRUSTED_PROXY_HOPS` | `1` | App Service is one proxy, so the rate limit means one visitor (D-113) |
| `WEBSITES_PORT` | `8000` | tells App Service which port to route to |
| `CORS_ORIGINS` | `https://<your app>.azurewebsites.net` | your own site and nothing else (D-076) |
| `RATE_LIMIT_PER_MINUTE` | `10` | one browser tab in a loop |
| `RATE_LIMIT_PER_DAY` | `300` | the cap that bounds the API usage |

Nothing else. In particular **do not add `ZONEWISE_DEV=1`** — it would expose the
endpoints that read and write the evaluation files.

### D3. Always On, and the health check

Two switches that matter on this app:

1. Left menu → **Settings** → **Configuration** → **General settings** tab →
   **Always on**: **On** → **Save**.
   Without it the container is idled and every visitor after a quiet hour waits for the
   embedding model to load again.
2. Left menu → **Monitoring** → **Health check** → **Enable** →
   **Path**: `/api/health` → **Save**.
   App Service then restarts the container if that path stops answering. It is a
   different mechanism from the Dockerfile's own `HEALTHCHECK`, which a plain Docker
   daemon reads and App Service does not.

### D4. Watch the first start

Left menu → **Monitoring** → **Log stream**. Leave it open. You should see, in order:

```
INFO zonewise.data: runtime data missing (processed/chunks.jsonl, index/bm25.pkl, ...);
                    fetching the bundle from <account>.blob.core.windows.net
INFO zonewise.data: data bundle in place: 40 files, 653 chunks, built from commit ...
INFO zonewise.api:  startup complete: peak RSS 480.0 MB, 653 chunks
INFO:     Uvicorn running on http://0.0.0.0:8000
```

The whole of that takes a minute or two on one B1 core. **The first line names only the
storage host, never the SAS token** — that is deliberate (D-114).

If instead you see *"No runtime data and no DATA_BUNDLE_URL set"*, the setting did not
save. If you see *"does not match DATA_BUNDLE_SHA256"*, you uploaded one bundle and
pasted another bundle's hash: re-run `make_data_bundle.py`, re-upload, and paste the new
hash.

---

## E. Check it works

In this order, because each one tells you a different thing.

1. **`https://<your app>.azurewebsites.net/api/health`**

   ```json
   {
     "status": "ok",
     "chunks": 653,
     "layers_loaded": ["high_density_corridor", "land_pooling_area", "low_density_area",
                       "nctd_boundary", "planning_zones", "regional_park", "tod_zone"],
     "llm_available": true,
     "provider": "groq",
     "model": "openai/gpt-oss-120b",
     "startup_errors": [],
     "dev_mode": false,
     "support_check": "enforce",
     "peak_rss_mb": 486.2
   }
   ```

   - `"status": "degraded"` means the data did not arrive — read `startup_errors`.
   - `"llm_available": false` means the Groq key is missing or malformed. The site still
     works as a clause search; questions return the clauses instead of an answer.
   - **`peak_rss_mb` is the number to watch.** It is the highest the process has
     reached. B1 gives 1.75 GB, so anything under about 900 MB is comfortable. If it
     creeps towards 1.4 GB, that is the signal to look at it rather than wait for a
     restart.

2. **The site itself.** Open `https://<your app>.azurewebsites.net`. The map of Delhi
   should draw with its zone overlays. If the page loads but the map is blank, the
   **tiles** are failing — they come from OpenStreetMap directly to the browser, not
   through the server, so check the browser console rather than the log stream.

3. **One map question.** Click a point in central Delhi, type *"How much can I build
   here?"*, ask. Expect an answer of a few sentences with clause chips you can click, or
   an honest abstention. Either is a pass; a 500 is not.

4. **One agent question.** Switch to the question-only box and ask *"What can be built
   near Hauz Khas metro?"*. Watch the tool trace appear: `locate_place`, `get_zones`,
   `search_clauses`. This is the path that needs Nominatim, so it is also the slowest.

5. **`/api/dev/eval/questions` must be a 404.** If it is not, `ZONEWISE_DEV` is set.

---

## F. Updating it

**Code changed:**

1. `git push` (and run `scripts\check.ps1` first — the image build does not run the
   tests).
2. GitHub → Actions → **Image** → **Run workflow**.
3. When it is green: portal → your web app → **Restart** (top bar). App Service pulls
   `:latest` on restart.

**Data changed** (you re-ran the pipeline, or the corpus changed):

1. `uv run python scripts\make_data_bundle.py` → note the new sha256.
2. Upload the new zip to the `bundles` container.
3. Generate a SAS URL for the **new blob** (B4 again).
4. Update **both** `DATA_BUNDLE_URL` and `DATA_BUNDLE_SHA256` → **Apply**.
5. **Restart**.

The old bundle can stay in the container; a few megabytes cost nothing, and it is what a
rollback uses.

**Rolling back the code:** set *Image and tag* to `<owner>/zonewise:<short sha>` of the
earlier build and restart. That is what the short-SHA tag is for.

---

## G. Cost, and how to stop paying

| what | cost |
| --- | --- |
| App Service Basic B1, Linux | ~13 USD a month |
| Blob storage, 8 MB + a few requests | a few cents a month |
| Groq free tier | 0 |
| GitHub Actions on a public repository | 0 |

All of it comes out of the **100 USD student credit**, and **there is no card on file**,
so the worst case is that the credit runs out and the app stops — not a bill.

**To take everything down:** portal → **Resource groups** → `zonewise-rg` → **Delete
resource group** → type the name. That removes the web app, the plan and the storage
account in one go. Nothing else was created anywhere.

To pause instead: web app → **Stop**. A stopped app still costs the plan's hourly rate,
so to stop paying you delete it.

### Cost safety checklist

- [ ] **Confirm `RATE_LIMIT_PER_DAY` is set** and is a number you would be happy to
      serve every day. This is the counter that bounds how many LLM calls the service
      can make.
- [ ] **Check `LLM_MODEL`.** `openai/gpt-oss-120b` on Groq's free tier is what this
      project was measured on. A larger model on a paid provider is where a surprise
      would come from.
- [ ] **Set a budget alert**: portal → **Cost Management** → **Budgets** → **+ Add**,
      25 USD a month with an email alert. So an app you forgot about tells you about
      itself.
- [ ] **Watch the request log for a week.** `scripts/summarize_logs.py` reads it. A
      rising `weak_retrieval` share means people are asking things the corpus does not
      cover; a rising `citation_check_failed` share means the model cannot ground
      answers from what retrieval returns. Those want opposite responses.
- [ ] **Remember the app works with no key at all.** Five of the seven endpoints need
      none (D-050), so if you want the map, the zone lookup and clause search in public
      with no API usage at all, leave `GROQ_API_KEY` unset. Questions return the clauses
      to read, and the interface says so.

---

## Where things are, once it is running

| what | where |
| --- | --- |
| the site | `https://<your app>.azurewebsites.net` |
| what loaded, and peak memory | `/api/health` |
| the live log | portal → web app → **Log stream** |
| a shell in the container | portal → web app → **Development Tools** → **SSH** |
| the request log | `/app/data/logs/requests.jsonl` **inside the container** |
| the indexes and the layers | `/app/data`, extracted at startup |
| the model weights | `/app/data/index/models`, baked into the image |
| the image | `ghcr.io/<owner>/zonewise` |
| the data bundle | the `bundles` container in your storage account |

**The request log does not survive a restart.** App Service's container filesystem is
ephemeral, and the log is written inside it. To read it before it goes, use the SSH
console:

```bash
python scripts/summarize_logs.py
```

Keeping it permanently would mean mounting an Azure Files share at `/app/data/logs`
(web app → **Configuration** → **Path mappings**), which is a separate decision and is
not part of this plan.

---

## Rate limits

Two, both in memory, both from the environment:

| variable | default | what it protects |
| --- | --- | --- |
| `RATE_LIMIT_PER_MINUTE` | 10 | one browser tab in a loop |
| `RATE_LIMIT_PER_DAY` | 300 | the API usage |

The daily cap is one counter for the whole service, it resets at midnight in the
container's timezone, and a request over it gets a 429 with a plain-English message.

Both counters live in the process, so **they reset when the container restarts**, and a
second worker would have its own copy. That is why the image runs one worker. If you ever
need two, the counters have to move to something shared first, or the cap stops being a
cap.

**The per-minute limit needs `TRUSTED_PROXY_HOPS=1` to mean anything here.** Behind App
Service's proxy, the address the server sees is the proxy's for every request, so without
that setting ten requests a minute from anyone would throttle every visitor at once
(D-113).

---

## Alternatives, with the same image

**Azure Container Apps.** Same image, same app settings, and it has a monthly free grant
that can make it cost nothing. The trade-off is **scale-to-zero**: after a quiet period
the container is stopped, and the next visitor waits for the data download and the model
load — a minute or so. For a portfolio project someone opens once, that first impression
is the reason App Service with Always On was chosen instead (D-111). Create it with
*Container Apps* → *Create*, point it at `ghcr.io/<owner>/zonewise:latest`, set the same
environment variables, and set the ingress target port to 8000.

**Any Docker host** — a VM, a home server, a Raspberry Pi with enough RAM. Two commands,
once Docker is installed:

```bash
docker pull ghcr.io/<owner>/zonewise:latest
docker run -d --name zonewise --restart unless-stopped \
  -p 8000:8000 \
  -e GROQ_API_KEY=gsk_... \
  -e DATA_BUNDLE_URL='https://...?sig=...' \
  -e DATA_BUNDLE_SHA256=81e9... \
  -e CORS_ORIGINS=https://your.domain \
  -e TRUSTED_PROXY_HOPS=1 \
  -v zonewise-logs:/app/data/logs \
  ghcr.io/<owner>/zonewise:latest
```

Put a reverse proxy in front of it for HTTPS — [Caddy](https://caddyserver.com) gets a
Let's Encrypt certificate from two lines of configuration (`your.domain { reverse_proxy
localhost:8000 }`) and renews it without being asked. Bind the container to
`127.0.0.1:8000` rather than `0.0.0.0` so only the proxy can reach it, and set
`TRUSTED_PROXY_HOPS=1` because the proxy is the hop. Unlike App Service, a volume for
`/app/data/logs` keeps the request log across restarts.

---

## Licences and attribution

Both are already in the interface and the README; this is the deployment-time summary.

**OpenStreetMap** — map tiles, the Nominatim geocoder and the metro station gazetteer are
all OSM data, © OpenStreetMap contributors, under the
[ODbL](https://opendatacommons.org/licenses/odbl/). The map carries the attribution. If
you ever serve the gazetteer as a file, the ODbL's share-alike terms apply to it.

**Nominatim** — a free service with a
[usage policy](https://operations.osmfoundation.org/policies/nominatim/). ZoneWise honours
it: one request a second enforced by a lock, an identifying User-Agent, every result
cached, the search bounded to Delhi, and at most two requests per place name (D-073). **Do
not raise those limits on a public deployment.** A geocoding-heavy deployment should run
its own Nominatim or use a paid provider.

**DDA GIS portal** — the zone boundaries. DDA states no licence or terms of use anywhere
on the service, so ZoneWise **displays** the layers and does not redistribute them: the
layer endpoints serve simplified geometry for drawing, and there is no bulk download
endpoint. This is also why the layers travel in a **private** blob container rather than
inside a public image or a public release asset (D-112). The map credits "Boundaries: DDA
GIS portal" beside the OSM credit. Do not add a download route (D-030).

**MPD-2047 and the court documents** — public records of the Government of India and the
courts, quoted with document, clause and page number on every answer.

**The answers themselves** — the interface carries a standing "Not legal advice" banner
and the system prompt forbids telling anyone what they may build (D-041). Keep both.
