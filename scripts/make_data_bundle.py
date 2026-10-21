"""Pack the runtime data into one zip, for a container to download at startup.

    uv run python scripts/make_data_bundle.py
    uv run python scripts/make_data_bundle.py --out-dir dist

Writes `dist/zonewise-data-<YYYYMMDD>.zip` and prints its size, its SHA-256 and how many
files it holds. `dist/` is gitignored: a bundle is a build product, it carries the DDA
layers, and CLAUDE.md's rule 3 keeps all of that out of git.

**What goes in** is exactly what the running server reads — the five runtime paths from
section (a) of `reports/deploy_audit.md`, listed once as `BUNDLE_PATTERNS` in
`app/data_bootstrap.py` so the packer and the unpacker cannot disagree:

    processed/chunks.jsonl          the clause text and metadata, read at search time
    index/bm25.pkl                  the keyword index
    index/chroma/**                 the vector store
    layers/dda/*.geojson            the eight DDA map layers
    gazetteer/metro_stations.json   the metro station names (optional, D-074)

**What does not**, and why: `data/raw` (109 MB of PDFs, nothing reads them once the
chunks exist), `data/logs` (written by the container, never shipped to it), and
`data/index/models` — the embedding model's weights, which are baked into the image at
build time instead, so the bundle stays small and startup needs no Hugging Face (D-112).

A `manifest.json` goes in beside them with every file's size and SHA-256, the git commit
the data was built from and the chunk count. `app/data_bootstrap.py` checks the extracted
tree against it, so a bundle that lost a file or arrived truncated is refused rather than
serving half an index.

Safe to re-run: it rebuilds today's zip in place. Nothing is uploaded — the upload is a
manual step in docs/DEPLOY.md, because the destination is a private blob container whose
SAS URL is a secret.
"""

import argparse
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, PROJECT_ROOT  # noqa: E402
from app.data_bootstrap import (  # noqa: E402
    MANIFEST_NAME,
    build_manifest,
    bundle_members,
    missing_runtime_data,
    sha256_of,
)
from app.extract import use_utf8_output  # noqa: E402
from app.indexing import human_size  # noqa: E402

#: Where bundles are written. Gitignored.
DEFAULT_OUT_DIR = PROJECT_ROOT / "dist"


def git_commit(repo: Path) -> str:
    """The commit the data was built from, with `-dirty` when the tree is not clean.

    Recorded because "which chunks are in this bundle" and "which code wrote them" are
    the same question, and a bundle in blob storage has no other way to answer it. A
    failure to read git is not a failure to build a bundle, so it returns "unknown".
    """
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{sha}-dirty" if dirty else sha


def count_chunks(path: Path) -> int:
    """How many chunks are in chunks.jsonl. 0 when it is not there."""
    if not path.is_file():
        return 0
    with path.open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def write_bundle(zip_path: Path, members: list[str], manifest: dict, data_dir: Path) -> None:
    """Write the zip: the manifest first, then every file under its relative path.

    Deflated, because the Chroma store and the GeoJSON layers are both very
    compressible, and a smaller bundle is a shorter startup.
    """
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False))
        for member in members:
            archive.write(data_dir / member, arcname=member)


def main(argv: list[str] | None = None) -> int:
    """Build one bundle and print what it contains."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Pack the runtime data into one zip.")
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="where to write the zip (default: dist/, which is gitignored)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help="which data directory to pack (default: data/)",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    missing = missing_runtime_data(data_dir)
    members = bundle_members(data_dir)
    if not members:
        print(f"Nothing to pack: no runtime files under {data_dir}.")
        print("Run the pipeline first: scripts/05_build_index.py, scripts/06_fetch_layers.py")
        return 1

    manifest = build_manifest(
        members,
        data_dir,
        git_commit=git_commit(PROJECT_ROOT),
        chunk_count=count_chunks(data_dir / "processed" / "chunks.jsonl"),
    )

    zip_path = out_dir / f"zonewise-data-{time.strftime('%Y%m%d')}.zip"
    write_bundle(zip_path, members, manifest, data_dir)
    digest = sha256_of(zip_path)
    size = zip_path.stat().st_size

    groups: dict[str, int] = {}
    for member in members:
        groups[member.split("/")[0]] = groups.get(member.split("/")[0], 0) + 1

    print(f"Wrote {zip_path}")
    print(f"  files     {len(members)} " + ", ".join(f"{name} {count}" for name, count in sorted(groups.items())))
    print(f"  chunks    {manifest['chunk_count']}")
    print(f"  commit    {manifest['git_commit']}")
    print(f"  unpacked  {human_size(manifest['total_bytes'])}")
    print(f"  zip       {human_size(size)} ({size} bytes)")
    print(f"  sha256    {digest}")
    print()
    print("Next, from docs/DEPLOY.md step B: upload this file to the private blob")
    print("container, generate a read-only SAS URL for it, and set both app settings:")
    print("  DATA_BUNDLE_URL      the SAS URL (a secret: never commit it)")
    print(f"  DATA_BUNDLE_SHA256   {digest}")
    if missing:
        print()
        print("WARNING: the data directory is incomplete, so this bundle is too.")
        print("  missing: " + ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
