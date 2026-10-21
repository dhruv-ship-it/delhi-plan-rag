"""Tests for app/data_bootstrap.py, against a tiny fake bundle over a file:// URL.

Nothing here touches the network or the real data. A five-file `data/` tree is built in
a temporary directory, zipped with the same manifest the real builder writes, and served
to `ensure_data` as a `file://` URL — which `urllib` opens exactly as it opens an https
one, so the happy path, the checksum, the manifest check and the retry loop are all
exercised through the real code path rather than a stub of it.

The four cases the deployment turns on (D-112):

  the happy path            a bundle is fetched, verified, extracted and checked
  a bad checksum            refused, and nothing is written into the live paths
  a file missing from it    the manifest promised it, so the bundle is refused
  data already present      nothing is fetched at all, however set the URL is
"""

import json
import logging
import zipfile

import pytest

from app.data_bootstrap import (
    DOWNLOADED,
    MANIFEST_NAME,
    MISSING,
    PRESENT,
    BootstrapError,
    build_manifest,
    bundle_members,
    data_present,
    download,
    ensure_data,
    host_of,
    manifest_problems,
    missing_runtime_data,
    scrubbed,
    sha256_of,
)

#: A SAS URL's shape, as App Service will hold it: the token after the `?` is the
#: secret, which is why only the host may ever be logged.
SAS_URL = (
    "https://zonewisedata.blob.core.windows.net/bundles/zonewise-data-20261022.zip"
    "?sp=r&st=2026-10-22T00:00:00Z&se=2027-10-22T00:00:00Z&sig=SECRETsignature%3D"
)


def make_tree(root):
    """A `data/` directory with one file for each thing the server reads."""
    data = root / "data"
    (data / "processed").mkdir(parents=True)
    (data / "processed" / "chunks.jsonl").write_text(
        '{"chunk_id": "MPD47_GAZETTE_EN:4.2.3@p753:0"}\n', encoding="utf-8"
    )
    (data / "index" / "chroma").mkdir(parents=True)
    (data / "index" / "bm25.pkl").write_bytes(b"pretend this is a pickled BM25 model")
    (data / "index" / "chroma" / "chroma.sqlite3").write_bytes(b"pretend this is sqlite")
    (data / "layers" / "dda").mkdir(parents=True)
    (data / "layers" / "dda" / "nctd_boundary.geojson").write_text(
        '{"type": "FeatureCollection", "features": []}', encoding="utf-8"
    )
    (data / "gazetteer").mkdir(parents=True)
    (data / "gazetteer" / "metro_stations.json").write_text("[]", encoding="utf-8")
    return data


def write_zip(zip_path, data_dir, skip=()):
    """Zip a data tree the way scripts/make_data_bundle.py does.

    `skip` leaves a file out of the archive **while keeping it in the manifest**, which
    is how the "listed but missing" case is built: a bundle that lost a file on the way
    into blob storage looks exactly like this.
    """
    members = bundle_members(data_dir)
    manifest = build_manifest(members, data_dir, git_commit="abc1234", chunk_count=1)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
        for member in members:
            if member in skip:
                continue
            archive.write(data_dir / member, arcname=member)
    return manifest


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Nothing in this file should spend `RETRY_WAIT_S` really waiting.

    Autouse, because a test suite that takes six seconds to prove a retry loop retries
    is a test suite people stop running. The one test that cares how long the wait is
    asserts on the recorded numbers instead.
    """
    monkeypatch.setattr("app.data_bootstrap.time.sleep", lambda seconds: None)


@pytest.fixture
def bundle(tmp_path):
    """A built bundle, its manifest, its sha256 and an empty target data directory."""
    source = make_tree(tmp_path / "source")
    zip_path = tmp_path / "zonewise-data-20261022.zip"
    manifest = write_zip(zip_path, source)
    target = tmp_path / "target" / "data"
    target.mkdir(parents=True)
    return {
        "source": source,
        "zip": zip_path,
        "url": zip_path.as_uri(),
        "sha256": sha256_of(zip_path),
        "manifest": manifest,
        "target": target,
    }


# --- what counts as present -----------------------------------------------------


def test_a_complete_tree_is_present_and_an_empty_one_is_not(tmp_path) -> None:
    data = make_tree(tmp_path)
    assert missing_runtime_data(data) == []
    assert data_present(data) is True
    assert data_present(tmp_path / "nothing") is False


def test_the_gazetteer_is_not_required(tmp_path) -> None:
    """D-074: without it `locate_place` falls back to Nominatim, so it is not a blocker."""
    data = make_tree(tmp_path)
    (data / "gazetteer" / "metro_stations.json").unlink()
    assert missing_runtime_data(data) == []


def test_each_missing_piece_is_named(tmp_path) -> None:
    """The log line has to say what is missing, so it names each path."""
    data = make_tree(tmp_path)
    (data / "index" / "bm25.pkl").unlink()
    (data / "layers" / "dda" / "nctd_boundary.geojson").unlink()
    assert missing_runtime_data(data) == ["index/bm25.pkl", "layers/dda"]


def test_the_file_list_is_posix_and_sorted(tmp_path) -> None:
    """A bundle built on Windows must list the same names as one built on Linux."""
    data = make_tree(tmp_path)
    members = bundle_members(data)
    assert members == sorted(members)
    assert all("\\" not in member for member in members)
    assert "index/chroma/chroma.sqlite3" in members
    # the model weights are never in a bundle: they are baked into the image (D-112)
    assert not any(member.startswith("index/models") for member in members)


def test_raw_pdfs_and_logs_are_never_packed(tmp_path) -> None:
    """The two things the bundle must not carry, asserted rather than assumed."""
    data = make_tree(tmp_path)
    (data / "raw").mkdir()
    (data / "raw" / "MPD47_GAZETTE_EN.pdf").write_bytes(b"%PDF-1.7 pretend")
    (data / "logs").mkdir()
    (data / "logs" / "requests.jsonl").write_text('{"question": "secret"}\n', encoding="utf-8")
    (data / "index" / "models").mkdir()
    (data / "index" / "models" / "weights.onnx").write_bytes(b"pretend 65 MB")

    members = bundle_members(data)
    assert not any(member.startswith(("raw/", "logs/", "index/models/")) for member in members)


# --- the four cases -------------------------------------------------------------


def test_the_happy_path_downloads_verifies_and_extracts(bundle) -> None:
    status = ensure_data(
        data_dir=bundle["target"], url=bundle["url"], expected_sha256=bundle["sha256"]
    )

    assert status == DOWNLOADED
    assert data_present(bundle["target"]) is True
    assert (bundle["target"] / "processed" / "chunks.jsonl").read_text(encoding="utf-8")
    assert (bundle["target"] / "index" / "chroma" / "chroma.sqlite3").is_file()
    assert (bundle["target"] / "gazetteer" / "metro_stations.json").is_file()
    # nothing is left behind: the staging directory is a temporary sibling
    assert [path.name for path in bundle["target"].glob(".bundle-*")] == []


def test_a_bad_checksum_refuses_to_start_and_writes_nothing(bundle) -> None:
    """D-112. A bundle that is not the configured one is not a bundle to extract."""
    with pytest.raises(BootstrapError) as raised:
        ensure_data(data_dir=bundle["target"], url=bundle["url"], expected_sha256="0" * 64)

    assert "DATA_BUNDLE_SHA256" in str(raised.value)
    assert data_present(bundle["target"]) is False
    # the live paths were never touched, because extraction happens after the check
    assert list(bundle["target"].iterdir()) == []


def test_a_file_listed_in_the_manifest_but_missing_is_refused(tmp_path) -> None:
    source = make_tree(tmp_path / "source")
    zip_path = tmp_path / "short.zip"
    write_zip(zip_path, source, skip=("index/bm25.pkl",))
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(BootstrapError) as raised:
        ensure_data(data_dir=target, url=zip_path.as_uri(), expected_sha256=sha256_of(zip_path))

    assert "index/bm25.pkl" in str(raised.value)
    assert "manifest" in str(raised.value)
    # and nothing from the bundle was moved into place, not even the files that did arrive
    assert not (target / "processed" / "chunks.jsonl").exists()


def test_data_already_present_fetches_nothing(tmp_path) -> None:
    """The local case. The URL is deliberately one that would fail if it were opened."""
    data = make_tree(tmp_path)

    def refuse(*args, **kwargs):
        raise AssertionError("ensure_data tried to download although the data was there")

    status = ensure_data(data_dir=data, url=SAS_URL, expected_sha256="0" * 64, opener=refuse)
    assert status == PRESENT
    assert data_present(data) is True


def test_no_data_and_no_url_says_so_once_and_asks_the_caller_to_stop(tmp_path, caplog) -> None:
    with caplog.at_level(logging.ERROR, logger="zonewise.data"):
        status = ensure_data(data_dir=tmp_path / "empty", url="")

    assert status == MISSING
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "DATA_BUNDLE_URL" in message
    assert "processed/chunks.jsonl" in message
    assert "scripts/05_build_index.py" in message


# --- the checksum being unset ---------------------------------------------------


def test_an_unverified_bundle_is_used_but_its_hash_is_logged(bundle, caplog) -> None:
    """Without DATA_BUNDLE_SHA256 the bundle is still used, and the log says what to set."""
    with caplog.at_level(logging.WARNING, logger="zonewise.data"):
        status = ensure_data(data_dir=bundle["target"], url=bundle["url"], expected_sha256="")

    assert status == DOWNLOADED
    warnings = [record.getMessage() for record in caplog.records]
    assert any(bundle["sha256"] in message for message in warnings)


# --- the manifest check on its own ----------------------------------------------


def test_the_manifest_catches_a_truncated_file(tmp_path) -> None:
    data = make_tree(tmp_path)
    manifest = build_manifest(bundle_members(data), data, "abc1234", 1)
    (data / "index" / "bm25.pkl").write_bytes(b"short")

    problems = manifest_problems(manifest, data)
    assert len(problems) == 1
    assert "index/bm25.pkl" in problems[0]
    assert "bytes" in problems[0]


def test_the_manifest_catches_a_file_whose_contents_changed(tmp_path) -> None:
    """Same length, different bytes: only the hash can see this."""
    data = make_tree(tmp_path)
    manifest = build_manifest(bundle_members(data), data, "abc1234", 1)
    original = (data / "index" / "bm25.pkl").read_bytes()
    (data / "index" / "bm25.pkl").write_bytes(b"X" * len(original))

    problems = manifest_problems(manifest, data)
    assert problems == ["index/bm25.pkl does not match its sha256 in the manifest"]


def test_an_empty_manifest_is_a_problem(tmp_path) -> None:
    assert manifest_problems({}, tmp_path) == ["the manifest lists no files"]
    assert manifest_problems({"files": []}, tmp_path) == ["the manifest lists no files"]


# --- a bundle is untrusted input ------------------------------------------------


def test_a_zip_that_would_write_outside_the_data_directory_is_refused(tmp_path) -> None:
    """A bundle arrives over the network, so a path escaping `data/` is a refusal."""
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(MANIFEST_NAME, json.dumps({"files": [{"path": "../escaped.txt"}]}))
        archive.writestr("../escaped.txt", "nope")
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(BootstrapError) as raised:
        ensure_data(data_dir=target, url=zip_path.as_uri(), expected_sha256=sha256_of(zip_path))

    assert "unsafe path" in str(raised.value)
    assert not (tmp_path / "escaped.txt").exists()


def test_a_bundle_with_no_manifest_is_refused(tmp_path) -> None:
    zip_path = tmp_path / "bare.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("processed/chunks.jsonl", "{}\n")
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(BootstrapError) as raised:
        ensure_data(data_dir=target, url=zip_path.as_uri(), expected_sha256=sha256_of(zip_path))

    assert MANIFEST_NAME in str(raised.value)


# --- the download, and the secret in the URL ------------------------------------


def test_the_download_retries_and_then_gives_up(tmp_path, caplog) -> None:
    """Three attempts, as D-112 says, and the URL is in none of the log lines."""
    attempts = []

    def fail(url, timeout=None):
        attempts.append(url)
        raise OSError(f"connection reset while reading {url}")

    with caplog.at_level(logging.WARNING, logger="zonewise.data"):
        with pytest.raises(BootstrapError) as raised:
            download(SAS_URL, tmp_path / "out.zip", attempts=3, opener=fail)

    assert len(attempts) == 3
    assert "SECRETsignature" not in str(raised.value)
    assert "blob.core.windows.net" in str(raised.value)
    for record in caplog.records:
        assert "SECRETsignature" not in record.getMessage()
        assert "sig=" not in record.getMessage()


def test_a_download_that_succeeds_on_the_second_attempt_is_not_a_failure(tmp_path) -> None:
    calls = {"n": 0}
    real = (tmp_path / "real.zip")
    real.write_bytes(b"bundle bytes")

    def flaky(url, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("temporary failure in name resolution")
        return real.open("rb")

    out = download(SAS_URL, tmp_path / "out.zip", attempts=3, opener=flaky)
    assert out.read_bytes() == b"bundle bytes"
    assert calls["n"] == 2


def test_only_the_host_of_a_sas_url_is_ever_shown() -> None:
    assert host_of(SAS_URL) == "zonewisedata.blob.core.windows.net"
    assert host_of("") == "(no host)"
    assert host_of("not a url at all") == "(no host)"


def test_a_message_carrying_the_url_is_scrubbed() -> None:
    message = f"HTTP Error 403: Server failed to authenticate {SAS_URL}"
    cleaned = scrubbed(message, SAS_URL)
    assert "SECRETsignature" not in cleaned
    assert "sig=" not in cleaned
    assert "zonewisedata.blob.core.windows.net" in cleaned


def test_retrying_waits_but_not_for_long(monkeypatch, tmp_path) -> None:
    """The wait is in front of the server starting, so it is seconds and not minutes."""
    slept: list[float] = []
    # overrides the autouse fixture above, to see the numbers it was asked to sleep for
    monkeypatch.setattr("app.data_bootstrap.time.sleep", lambda seconds: slept.append(seconds))

    def fail(url, timeout=None):
        raise OSError("nope")

    with pytest.raises(BootstrapError):
        download(SAS_URL, tmp_path / "out.zip", attempts=3, opener=fail)

    # two waits for three attempts, and nothing after the last one
    assert len(slept) == 2
    assert sum(slept) <= 10
