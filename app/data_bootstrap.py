"""Make sure the runtime data is on disk before anything tries to read it.

ZoneWise needs five gitignored things to answer anything: `data/processed/chunks.jsonl`,
`data/index/bm25.pkl`, the Chroma store, the DDA map layers and — optionally, since
geocoding falls back to Nominatim (D-074) — the metro gazetteer. On a laptop they are
there because the pipeline built them. In a container they are not: the image carries
code only, because the raw PDFs are gitignored and the DDA layers have no stated licence
(D-112).

So this module is the step in between. It is run **as its own process, before uvicorn**:

    python -m app.data_bootstrap && uvicorn app.api:app ...

Three outcomes, and nothing else:

  the data is already there        do nothing, say so, exit 0 (every local run)
  DATA_BUNDLE_URL is set           download, verify, extract, check, exit 0
  neither                          one clear log line, exit 1

Running it as a separate process rather than inside `app/api.py`'s lifespan is
deliberate. The server's own design is to start even when something is missing and let
`/api/health` explain (D-065), which is right for a laptop halfway through the pipeline
and wrong for a container that will never fix itself — and putting an exit inside the
lifespan would also mean every test that builds a `TestClient` had to care about data.
Keeping the two apart means the container fails loudly at the step that can fail, and the
server keeps the behaviour it has always had.

**The URL is never logged.** It is a SAS URL: the token that authorises the download is
in its query string, so a log line carrying it would hand the bundle to anyone who can
read the log stream. Only the host is logged, and an error message is scrubbed of the URL
before it is printed, in case a library put it there.

The matching builder is `scripts/make_data_bundle.py`, which uses the same file list and
the same manifest shape from this module, so the thing that packs and the thing that
unpacks cannot disagree about what a bundle is.
"""

import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from app.config import DATA_DIR, settings

log = logging.getLogger("zonewise.data")

#: Which files a bundle carries, as glob patterns relative to `data/`. Exactly the
#: runtime reads from section (a) of reports/deploy_audit.md, and nothing else: no raw
#: PDFs (109 MB, nothing reads them once the chunks exist), no request logs (written by
#: the container, never shipped to it), and no model weights (baked into the image at
#: build time instead, D-112).
BUNDLE_PATTERNS = (
    "processed/chunks.jsonl",
    "index/bm25.pkl",
    "index/chroma/**/*",
    "layers/dda/*.geojson",
    "gazetteer/metro_stations.json",
)

#: The manifest's own name inside the zip. Not under `data/`, because it describes the
#: bundle rather than belonging to the application.
MANIFEST_NAME = "manifest.json"

#: What `ensure_data` returns, so a caller can tell the three outcomes apart.
PRESENT = "present"
DOWNLOADED = "downloaded"
MISSING = "missing"

#: How long one download attempt may take, and how many attempts there are. A bundle is
#: about 20 MB over HTTPS from blob storage; a minute is generous, and three attempts
#: cover a cold storage account or a dropped connection without turning a dead URL into
#: a five-minute startup.
DOWNLOAD_TIMEOUT_S = 60
DOWNLOAD_ATTEMPTS = 3
#: Seconds between attempts. Short: this is in front of the server starting.
RETRY_WAIT_S = 3.0

#: The line printed when there is no data and no way to get any. It names the two ways
#: out, because a container that says only "no data" tells nobody what to do.
NO_DATA_MESSAGE = (
    "No runtime data and no DATA_BUNDLE_URL set, so ZoneWise would answer nothing. "
    "Either set DATA_BUNDLE_URL to a bundle built by scripts/make_data_bundle.py, or "
    "run the pipeline locally (scripts/05_build_index.py and scripts/06_fetch_layers.py). "
    "Missing: "
)


class BootstrapError(RuntimeError):
    """The data could not be put in place, and the process should not continue."""


# --- what counts as "the data is there" ----------------------------------------


def missing_runtime_data(data_dir: Path | None = None) -> list[str]:
    """Which of the runtime reads are absent. An empty list means the server can answer.

    The gazetteer is deliberately not checked: `locate_place` falls back to Nominatim
    without it (D-074), so its absence is a slower geocode and not a broken server.
    """
    base = Path(data_dir) if data_dir else DATA_DIR
    missing: list[str] = []
    if not (base / "processed" / "chunks.jsonl").is_file():
        missing.append("processed/chunks.jsonl")
    if not (base / "index" / "bm25.pkl").is_file():
        missing.append("index/bm25.pkl")
    if not any((base / "index" / "chroma").glob("*.sqlite3")):
        missing.append("index/chroma")
    if not any((base / "layers" / "dda").glob("*.geojson")):
        missing.append("layers/dda")
    return missing


def data_present(data_dir: Path | None = None) -> bool:
    """True when every runtime read is on disk."""
    return not missing_runtime_data(data_dir)


# --- the file list and the manifest ---------------------------------------------


def bundle_members(data_dir: Path | None = None) -> list[str]:
    """Every runtime file under `data/`, as sorted posix paths relative to it.

    Sorted, and with the separators normalised, so a bundle built on Windows lists its
    files in the same order and under the same names as one built on Linux. A manifest
    that said `index\\chroma\\chroma.sqlite3` would not match anything after extraction.
    """
    base = Path(data_dir) if data_dir else DATA_DIR
    found: set[str] = set()
    for pattern in BUNDLE_PATTERNS:
        for path in base.glob(pattern):
            if path.is_file():
                found.add(path.relative_to(base).as_posix())
    return sorted(found)


def sha256_of(path: Path) -> str:
    """The SHA-256 of a file, read in chunks so a large one costs no memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    members: list[str],
    data_dir: Path,
    git_commit: str = "",
    chunk_count: int = 0,
) -> dict:
    """The manifest for a bundle: what is in it, how big, and what it was built from.

    The per-file hash is what makes a partial extraction detectable — a zip that lost a
    file, or a file that arrived truncated, fails the check rather than producing a
    server that answers from half an index.
    """
    base = Path(data_dir)
    files = [
        {
            "path": member,
            "size": (base / member).stat().st_size,
            "sha256": sha256_of(base / member),
        }
        for member in members
    ]
    return {
        "bundle": "zonewise-data",
        "version": 1,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_commit": git_commit,
        "chunk_count": chunk_count,
        "file_count": len(files),
        "total_bytes": sum(item["size"] for item in files),
        "files": files,
    }


def manifest_problems(manifest: dict, data_dir: Path) -> list[str]:
    """What the manifest promised and the extracted tree does not deliver.

    Checked by size first and then by hash, because a size mismatch is the cheap
    explanation and the hash is the one that cannot be fooled.
    """
    base = Path(data_dir)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return ["the manifest lists no files"]

    problems: list[str] = []
    for item in files:
        member = str(item.get("path", ""))
        if not member:
            problems.append("the manifest has an entry with no path")
            continue
        path = base / member
        if not path.is_file():
            problems.append(f"{member} is listed in the manifest but is not in the bundle")
            continue
        size = int(item.get("size", -1))
        if size >= 0 and path.stat().st_size != size:
            problems.append(
                f"{member} is {path.stat().st_size} bytes, the manifest says {size}"
            )
            continue
        expected = str(item.get("sha256", ""))
        if expected and sha256_of(path) != expected:
            problems.append(f"{member} does not match its sha256 in the manifest")
    return problems


# --- downloading ----------------------------------------------------------------


def host_of(url: str) -> str:
    """The host of a URL, which is the only part of it that may be logged (D-112)."""
    try:
        return urllib.parse.urlsplit(url).hostname or "(no host)"
    except ValueError:
        return "(unreadable url)"


def scrubbed(message: object, url: str) -> str:
    """A message with the URL taken out of it, in case a library put it there.

    Belt and braces: `urllib`'s own errors do not quote the URL, but this is the one
    place a secret token could leak into a log, so nothing is assumed about what a
    future exception's text contains.
    """
    text = str(message)
    if url:
        text = text.replace(url, f"<{host_of(url)}/...>")
        query = urllib.parse.urlsplit(url).query
        if query:
            text = text.replace(query, "...")
    return text


def download(
    url: str,
    destination: Path,
    timeout: int = DOWNLOAD_TIMEOUT_S,
    attempts: int = DOWNLOAD_ATTEMPTS,
    opener=urllib.request.urlopen,
) -> Path:
    """Fetch the bundle to `destination`, retrying a few times. Returns the path.

    `opener` is injectable so a test can drive the failure paths without a server;
    normal use is `urllib.request.urlopen`, and a `file://` URL works unchanged, which
    is how the tests build a bundle and read it back.
    """
    destination = Path(destination)
    last: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            with opener(url, timeout=timeout) as response, destination.open("wb") as out:
                shutil.copyfileobj(response, out)
            return destination
        except Exception as exc:  # noqa: BLE001 - any failure is a retry, then a raise
            last = exc
            log.warning(
                "bundle download from %s failed (attempt %d of %d): %s",
                host_of(url),
                attempt,
                attempts,
                scrubbed(exc, url),
            )
            if attempt < attempts:
                time.sleep(RETRY_WAIT_S)
    raise BootstrapError(
        f"could not download the data bundle from {host_of(url)} after {attempts} "
        f"attempts: {scrubbed(last, url)}"
    )


# --- extracting -----------------------------------------------------------------


def safe_members(archive: zipfile.ZipFile) -> list[str]:
    """The archive's entries, refusing any that would write outside the target.

    A bundle is downloaded from a URL, so it is treated as untrusted input: an absolute
    path or one containing `..` is a refusal, not something to normalise and continue
    with.
    """
    names: list[str] = []
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        pure = Path(name)
        if pure.is_absolute() or ".." in pure.parts or name.startswith(("/", "\\")):
            raise BootstrapError(f"the bundle contains an unsafe path: {name!r}")
        names.append(name)
    return names


def extract(zip_path: Path, data_dir: Path) -> dict:
    """Unpack a verified bundle into `data_dir`. Returns its manifest.

    Atomic in the way that matters: everything is unpacked into a temporary directory
    **inside** `data_dir` first, the manifest is checked against what actually came out,
    and only then is each file moved into its place with `os.replace`, which is atomic
    per file and cannot leave a half-written one behind. The temporary directory is a
    sibling of the final paths so the move is a rename on the same filesystem rather
    than a copy.
    """
    base = Path(data_dir)
    base.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bundle-", dir=base))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = safe_members(archive)
            if MANIFEST_NAME not in names:
                raise BootstrapError(f"the bundle has no {MANIFEST_NAME}")
            archive.extractall(staging, members=names)

        manifest = json.loads((staging / MANIFEST_NAME).read_text(encoding="utf-8"))
        problems = manifest_problems(manifest, staging)
        if problems:
            raise BootstrapError("the bundle does not match its manifest: " + "; ".join(problems))

        for item in manifest["files"]:
            member = str(item["path"])
            target = base / member
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging / member, target)
        return manifest
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# --- the one entry point --------------------------------------------------------


def ensure_data(
    data_dir: Path | None = None,
    url: str | None = None,
    expected_sha256: str | None = None,
    timeout: int = DOWNLOAD_TIMEOUT_S,
    attempts: int = DOWNLOAD_ATTEMPTS,
    opener=urllib.request.urlopen,
) -> str:
    """Put the runtime data in place if it is not there. Returns what happened.

    `PRESENT` when it was already on disk — the local case, and no download is even
    attempted. `DOWNLOADED` when a bundle was fetched, verified and extracted.
    `MISSING` when there is nothing on disk and no URL to fetch from, which is the
    caller's cue to stop. Anything that goes wrong on the way raises `BootstrapError`:
    a checksum that does not match, a manifest that does not describe what arrived, or
    a download that failed every attempt. None of those is something to start a server
    on top of.
    """
    base = Path(data_dir) if data_dir else DATA_DIR
    missing = missing_runtime_data(base)
    if not missing:
        log.info("runtime data is already in place at %s", base)
        return PRESENT

    bundle_url = settings.data_bundle_url if url is None else url
    if not bundle_url:
        log.error("%s%s", NO_DATA_MESSAGE, ", ".join(missing))
        return MISSING

    expected = settings.data_bundle_sha256 if expected_sha256 is None else expected_sha256
    log.info(
        "runtime data missing (%s); fetching the bundle from %s",
        ", ".join(missing),
        host_of(bundle_url),
    )

    work = Path(tempfile.mkdtemp(prefix="zonewise-bundle-"))
    try:
        archive = download(
            bundle_url, work / "bundle.zip", timeout=timeout, attempts=attempts, opener=opener
        )
        digest = sha256_of(archive)
        if expected and digest.lower() != expected.strip().lower():
            raise BootstrapError(
                "the data bundle does not match DATA_BUNDLE_SHA256: expected "
                f"{expected.strip().lower()}, got {digest}. Refusing to start: a bundle "
                "that is not the one this deployment was configured with is not a bundle "
                "to extract."
            )
        if not expected:
            log.warning(
                "DATA_BUNDLE_SHA256 is not set, so the bundle was not verified. Its "
                "sha256 is %s; set that as DATA_BUNDLE_SHA256 to check it next time.",
                digest,
            )
        manifest = extract(archive, base)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    still_missing = missing_runtime_data(base)
    if still_missing:
        raise BootstrapError(
            "the bundle extracted but the data is still incomplete: "
            + ", ".join(still_missing)
        )
    log.info(
        "data bundle in place: %d files, %d chunks, built from commit %s",
        manifest.get("file_count", 0),
        manifest.get("chunk_count", 0),
        manifest.get("git_commit") or "(unknown)",
    )
    return DOWNLOADED


def main() -> int:
    """Run the bootstrap as a step of its own. 0 to continue, 1 to stop."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        status = ensure_data()
    except BootstrapError as exc:
        log.error("%s", exc)
        return 1
    return 0 if status in (PRESENT, DOWNLOADED) else 1


if __name__ == "__main__":
    raise SystemExit(main())
