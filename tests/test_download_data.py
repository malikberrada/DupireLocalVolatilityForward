"""Data acquisition must preserve original bytes and reject changed sources."""
import hashlib
import io
from pathlib import Path

import pytest

import download_data as data


def test_all_bundled_snapshots_are_original_bytes_and_repeated_acquisition_is_safe(tmp_path):
    report = data.acquire_frozen(tmp_path)
    assert report["network_used"] is False
    assert report["provider_redownload_claimed"] is False
    assert len(report["files"]) == 4
    for result in report["files"]:
        assert data.sha(result["path"]) == result["sha256"]
    assert data.acquire_frozen(tmp_path)["files"] == report["files"]
    original = tmp_path / "attempt_03.json"
    original.write_bytes(b"changed existing data")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        data.acquire_frozen(tmp_path)
    assert original.read_bytes() == b"changed existing data"


class Response(io.BytesIO):
    def geturl(self):
        return "https://example.test/data"


def test_download_rejects_changed_payload_before_publishing_and_cleans_partial_file(tmp_path, monkeypatch):
    payload = b"original raw bytes\r\n"
    entry = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    target = tmp_path / "snapshot.json"
    monkeypatch.setattr(data, "urlopen", lambda *a, **k: Response(b"x" * len(payload)))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        data.fetch("https://example.test/data", target, entry)
    assert not target.exists() and not list(tmp_path.iterdir())
    monkeypatch.setattr(data, "urlopen", lambda *a, **k: Response(payload))
    assert data.fetch("https://example.test/data", target, entry) == "downloaded_verified"
    assert target.read_bytes() == payload
    assert data.fetch("https://example.test/data", target, entry) == "already_verified"


def test_oversize_or_html_response_cannot_become_an_accepted_snapshot(tmp_path, monkeypatch):
    payload = b"correct"
    entry = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    monkeypatch.setattr(data, "urlopen", lambda *a, **k: Response(b"<html>sign in</html>"))
    with pytest.raises(ValueError, match="exceeds"):
        data.fetch("https://example.test/data", tmp_path / "data.pdf", entry)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "data/../../escape", "data\\escape"])
def test_manifest_paths_cannot_escape_destination(tmp_path, relative):
    with pytest.raises(ValueError):
        data.checked_path(tmp_path, relative)


def test_github_requires_immutable_commit_and_downloads_committed_path(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="full 40-character"):
        data.github_location("owner/repo", "main")
    with pytest.raises(ValueError, match="OWNER/REPOSITORY"):
        data.github_location("../bad/repo", "a" * 40)
    calls = []

    def fake_fetch(url, destination, entry):
        calls.append(url)
        source = next(e for e in data.load(data.ROOT / "data/manifest.json")["files"] if e["sha256"] == entry["sha256"])
        Path(destination).write_bytes((data.ROOT / source["path"]).read_bytes())
        return "downloaded_verified"

    monkeypatch.setattr(data, "fetch", fake_fetch)
    result = data.acquire_frozen(tmp_path, "github", "owner/repo", "a" * 40, ["attempt_03"])
    assert result["network_used"] is True
    assert calls == ["https://raw.githubusercontent.com/owner/repo/" + "a" * 40 + "/data/raw/yahoo/2026-10-26/attempt_03.json"]
