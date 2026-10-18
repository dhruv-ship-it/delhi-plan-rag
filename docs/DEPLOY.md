# Deploying ZoneWise

For someone putting this on a server for the first time. It assumes a laptop with the
repository on it, and an AWS account with nothing set up yet.

**The one thing to get right before anything else:** the data and the indexes are built
**on your laptop** and copied into the image. The container does not build them. See
[Build the data first](#1-build-the-data-first) — skipping it produces an image that
starts, reports `"status": "degraded"`, and returns 503 for every question.

**Cost.** An EC2 `t3.small` with an Elastic IP is roughly **$20 a month**. The Anthropic
API is the variable part and the one that can surprise you; the
[cost safety checklist](#cost-safety-checklist) is not optional.

---

## What you are deploying

One container. Inside it: a FastAPI server on port 8000 that serves the API and the built
React frontend from the same port, with the search indexes, the embedding model weights
and the map layers baked in. No database, no second service, no object storage.

```
                                    EC2 t3.small
   browser ──HTTPS──▶  Caddy  ──HTTP──▶  zonewise container  ──HTTPS──▶ api.anthropic.com
                      :443              :8000                            (only when
                   (gets the cert)   (one uvicorn worker)              answering)
```

Caddy is there for one reason: it gets and renews a TLS certificate from Let's Encrypt
without being configured to. Two lines in a Caddyfile and HTTPS works.

---

## 1. Build the data first

On your laptop, with the source PDFs in `data/raw/`:

```powershell
uv sync
uv run python scripts\02_extract.py
uv run python scripts\03_chunk.py
uv run python scripts\04_tag_zones.py
uv run python scripts\05_build_index.py      # about 3 minutes, downloads the model
uv run python scripts\06_fetch_layers.py     # about 1 minute, talks to DDA's server
uv run python scripts\07_test_points.py
uv run python scripts\build_gazetteer.py     # one Overpass request
```

Check that all four exist and are not empty:

```powershell
Get-ChildItem data\processed\chunks.jsonl, data\index\chroma, data\layers\dda, data\gazetteer
```

If `data/gazetteer` is empty the app still works — geocoding falls back to Nominatim
(D-073) — but the Dockerfile `COPY` needs the directory to exist, so run
`New-Item -ItemType Directory -Force data\gazetteer` if the script could not reach
Overpass.

Then run the tests and build the frontend, because the image build will not tell you
that your code is broken:

```powershell
uv run pytest
cd web; npm install; npm run build; cd ..
```

---

## 2. Build the image

```powershell
docker build -t zonewise:latest .
```

The build is two stages: node builds `web/dist`, then a `python:3.12-slim` stage runs
`uv sync --frozen` and copies `app/`, `scripts/`, the built frontend, `data/processed`,
`data/index` (including the cached model weights), `data/layers` and `data/gazetteer`.

`data/raw` and `.env` are **never** copied — `.dockerignore` excludes both, and the
Dockerfile copies data directories by name rather than copying everything. A key baked
into an image layer stays in that layer forever, even if a later layer deletes it.

Check it locally before sending it anywhere:

```powershell
docker run --rm -p 8000:8000 --name zonewise-test zonewise:latest
# in another terminal:
curl http://localhost:8000/api/health
```

Expect `"status": "ok"` and a non-zero `chunks`. `"degraded"` means step 1 was skipped or
incomplete, and `startup_errors` names the script to run.

---

## 3. The EC2 instance

**Why `t3.small` and not `t3.micro`.** The server loads the embedding model, the Chroma
collection, the BM25 corpus and eight GeoJSON layers into memory at startup — about
400 MB with the ONNX runtime. `t3.micro` has 1 GB and will survive right up until it
does not. `t3.small` has 2 GB.

1. **Launch**: Ubuntu 24.04 LTS, `t3.small`, 20 GB gp3 disk, a new key pair. Save the
   `.pem` file somewhere you will find it.
2. **Security group** — three inbound rules and no more:
   | port | source | why |
   | --- | --- | --- |
   | 22 | **your IP only** | SSH. Never `0.0.0.0/0`. |
   | 80 | `0.0.0.0/0` | Let's Encrypt's HTTP challenge, and the redirect to HTTPS |
   | 443 | `0.0.0.0/0` | the site |

   Port 8000 is **not** open. Caddy reaches the container over the Docker network.
3. **Elastic IP**: allocate one and associate it, or the address changes on every stop
   and your DNS record goes stale.
4. **DNS**: an A record from your domain to that IP. Caddy cannot get a certificate
   without a name that resolves.

Install Docker:

```bash
ssh -i zonewise.pem ubuntu@YOUR_IP
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
exit   # and reconnect, so the group membership applies
```

---

## 4. Move the image across

No registry needed for one server. The image is about 1.2 GB, mostly model weights, and
compresses to roughly 600 MB.

```powershell
docker save zonewise:latest | gzip > zonewise.tar.gz
scp -i zonewise.pem zonewise.tar.gz ubuntu@YOUR_IP:~
```

```bash
gunzip -c zonewise.tar.gz | docker load
rm zonewise.tar.gz
```

If you would rather use a registry — which you will, the second time — push to ECR or
GHCR and `docker pull` on the instance instead. The only reason this guide does not is
that `docker save` needs no account.

---

## 5. Run it

Put the key in a file on the instance, not in the run command. A key in the command line
is in your shell history and in `docker inspect` output.

```bash
mkdir -p ~/zonewise
cat > ~/zonewise/zonewise.env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-haiku-5-5
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_DAY=300
CORS_ORIGINS=https://zonewise.example.com
ABSTAIN_SIGNAL=dense_cosine
ABSTAIN_THRESHOLD=0.5804
USE_RERANKER=0
EOF
chmod 600 ~/zonewise/zonewise.env
```

**`ZONEWISE_DEV` is not in that file and must not be.** It enables the question
verification endpoints, which read and write the evaluation files (D-075).

```bash
docker run -d --name zonewise --restart unless-stopped \
  --env-file ~/zonewise/zonewise.env \
  -p 127.0.0.1:8000:8000 \
  -v ~/zonewise/logs:/app/data/logs \
  --memory 1500m \
  zonewise:latest
```

Four things in that command earn their place:

- **`-p 127.0.0.1:8000:8000`** binds to localhost, so the container is reachable from
  Caddy and not from the internet. Without the `127.0.0.1`, Docker opens the port in the
  host firewall and your security group rules will not save you.
- **`-v ~/zonewise/logs:/app/data/logs`** keeps the request log across restarts, which is
  what `scripts/summarize_logs.py` reads.
- **`--restart unless-stopped`** survives a reboot.
- **`--memory 1500m`** means a leak kills the container, which then restarts, instead of
  the kernel killing sshd.

Check it:

```bash
curl -s localhost:8000/api/health
docker logs zonewise --tail 20
```

---

## 6. HTTPS with Caddy

```bash
cat > ~/zonewise/Caddyfile <<'EOF'
zonewise.example.com {
	encode gzip
	reverse_proxy localhost:8000
}
EOF

sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update && sudo apt-get install -y caddy

sudo cp ~/zonewise/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

That is all of it. Caddy obtains the certificate on first request, redirects HTTP to
HTTPS, and renews automatically. Open `https://zonewise.example.com`.

If the certificate does not arrive: `sudo journalctl -u caddy -n 50`. It is almost always
DNS not pointing at the instance yet, or port 80 closed.

---

## Alternative: Lightsail containers

If you would rather not manage an instance, **Amazon Lightsail Containers** runs the
same image with HTTPS and a domain included, from about **$10 a month** for the `micro`
size (512 MB) or **$20** for `small` (1 GB). Push the image with
`aws lightsail push-container-image`, set the environment variables in the console or in
a deployment JSON, and point the public endpoint at port 8000.

The trade-off is worth knowing: Lightsail gives you HTTPS, a load balancer and
deployment history for roughly the price of the EC2 setup above, and takes away shell
access and the persistent volume — so **the request log does not survive a deployment**.
For a portfolio project that is usually the right trade. If you want the logs, use EC2.

Do not use the `nano` size: 512 MB is below what the embedding model and the layers need.

---

## Updating

```powershell
# on the laptop, after changing code or rebuilding the data
uv run pytest
cd web; npm run build; cd ..
docker build -t zonewise:latest .
docker save zonewise:latest | gzip > zonewise.tar.gz
scp -i zonewise.pem zonewise.tar.gz ubuntu@YOUR_IP:~
```

```bash
gunzip -c zonewise.tar.gz | docker load
docker stop zonewise && docker rm zonewise
# then the same docker run command as above
```

There is a few seconds of downtime. For a project with one reader that is fine; the fix
is two containers and a Caddy upstream switch, and it is not worth it yet.

---

## Where things are on the server

| what | where |
| --- | --- |
| the request log | `~/zonewise/logs/requests.jsonl` on the host |
| the environment file | `~/zonewise/zonewise.env`, mode 600 |
| container logs | `docker logs zonewise` |
| Caddy's logs and certificates | `journalctl -u caddy`, `/var/lib/caddy` |
| the indexes and model weights | inside the image, at `/app/data` |

To read the request log:

```bash
docker exec zonewise python scripts/summarize_logs.py
```

It prints requests per endpoint, p50 and p95 latency, the abstention rate by reason and
the most asked questions. **Watch the abstention breakdown**: a rising `weak_retrieval`
share means people are asking things the corpus does not cover, and a rising
`citation_check_failed` share means the model cannot ground answers from what retrieval
returns. Those want opposite responses.

---

## Rate limits

Two, both in memory, both from the environment:

| variable | default | what it protects |
| --- | --- | --- |
| `RATE_LIMIT_PER_MINUTE` | 10 | one browser tab in a loop |
| `RATE_LIMIT_PER_DAY` | 300 | **the API bill** |

The daily cap is the one that matters. It is a single counter for the whole service, it
resets at midnight server time, and a request over it gets a 429 with a plain-English
message rather than an error.

Both counters live in the process, so **they reset when the container restarts** and a
second worker would have its own copy. That is why the Dockerfile runs one worker. If you
ever need two, the counters have to move to Redis first, or the cap stops being a cap.

---

## Cost safety checklist

Work through all five. The first two are the ones that matter.

- [ ] **Set a spend limit in the Anthropic console.** Not a budget alert — a hard limit.
      This is the only control that cannot be defeated by a bug in this repository.
- [ ] **Confirm `RATE_LIMIT_PER_DAY` is set** and that it is a number you would be happy
      to pay for every day. 300 Haiku answers with six retrieved clauses each is a few
      tens of cents; 300 Opus answers is not.
- [ ] **Check `LLM_MODEL`.** The default is `claude-haiku-5-5` because the answering job
      is short and extractive (D-063). An accidental Opus is roughly 50 times the cost
      per answer.
- [ ] **Set an AWS Budget** with an email alert at $25 a month, so an instance you forgot
      about tells you about itself.
- [ ] **Watch the log for a week.** `summarize_logs.py` shows requests per day against
      the cap. A day at the cap means someone was refused.

One more, less obvious: **the app is useful with no key at all.** Five of the seven
endpoints need none (D-050), so if you want the map, the zone lookup and clause search in
public without any spend, deploy with `ANTHROPIC_API_KEY` unset. Questions return the
clauses to read rather than a written answer, and the interface says so.

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
endpoint. The map credits "Boundaries: DDA GIS portal" beside the OSM credit. Do not add a
download route (D-030).

**MPD-2047 and the court documents** — public records of the Government of India and the
courts, quoted with document, clause and page number on every answer.

**The answers themselves** — the interface carries a standing "Not legal advice" banner
and the system prompt forbids telling anyone what they may build (D-041). Keep both.
