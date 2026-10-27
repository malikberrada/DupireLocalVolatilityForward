"""Acquire the original immutable snapshots, current Yahoo books, or cited PDFs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def checked_path(root, relative):
    p = PurePosixPath(relative)
    if p.is_absolute() or not p.parts or any(x in ("..", ".") for x in p.parts) or "\\" in relative:
        raise ValueError("Unsafe manifest path: " + relative)
    target = (Path(root) / Path(*p.parts)).resolve()
    if not target.is_relative_to(Path(root).resolve()):
        raise ValueError("Manifest path leaves destination")
    return target


def validate(path, entry):
    if Path(path).stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
        raise ValueError("Size/SHA-256 mismatch: " + str(path))


def github_location(repo=None, ref=None):
    if repo is None:
        remote = subprocess.check_output(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"], text=True,
            stderr=subprocess.PIPE).strip()
        match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?", remote)
        if not match:
            raise ValueError("origin must be a GitHub HTTPS or SSH remote; alternatively pass --repo")
        repo = match.group(1)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("--repo must be OWNER/REPOSITORY")
    if ref is None:
        ref = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                      text=True, stderr=subprocess.PIPE).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        raise ValueError("--ref must be a full 40-character commit SHA, not a moving branch/tag")
    return repo, ref.lower()


def fetch(url, destination, entry, *, timeout=30, retries=2):
    """Publish bytes atomically only after checking the committed size and hash."""
    destination = Path(destination)
    if destination.exists():
        validate(destination, entry)
        return "already_verified"
    if not url.startswith("https://"):
        raise ValueError("Downloads require HTTPS")
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries + 1):
        fd, name = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
        try:
            request = Request(url, headers={"User-Agent": "dupire-reproduction/1.0"})
            with os.fdopen(fd, "wb") as out:
                with urlopen(request, timeout=timeout) as response:
                    if not response.geturl().startswith("https://"):
                        raise ValueError("Refusing a redirect to an insecure URL")
                    total = 0
                    while block := response.read(1024 * 1024):
                        total += len(block)
                        if total > entry["bytes"]:
                            raise ValueError("Download exceeds the committed size")
                        out.write(block)
            validate(name, entry)
            os.replace(name, destination)
            return "downloaded_verified"
        except (HTTPError, URLError, TimeoutError) as exc:
            retryable = not isinstance(exc, HTTPError) or exc.code in (408, 429, 500, 502, 503, 504)
            if not retryable or attempt == retries:
                raise
            time.sleep(min(2 ** attempt, 4))
        finally:
            Path(name).unlink(missing_ok=True)


def acquire_frozen(destination, source="bundled", repo=None, ref=None, ids=None):
    manifest = load(ROOT / "data/manifest.json")
    entries = manifest["files"]
    if ids:
        known = {e["id"] for e in entries}
        if set(ids) - known:
            raise ValueError("Unknown snapshot IDs: " + ", ".join(sorted(set(ids) - known)))
        entries = [e for e in entries if e["id"] in ids]
    if source == "github":
        repo, ref = github_location(repo, ref)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for entry in entries:
        target = checked_path(destination, PurePosixPath(entry["path"]).name)
        if source == "bundled":
            original = checked_path(ROOT, entry["path"])
            validate(original, entry)
            if target.exists():
                validate(target, entry)
            else:
                # fetch() handles remote transfers; this branch deliberately needs no network.
                fd, name = tempfile.mkstemp(prefix=".copy-", dir=destination)
                try:
                    with os.fdopen(fd, "wb") as out:
                        out.write(original.read_bytes())
                    validate(name, entry)
                    os.replace(name, target)
                finally:
                    Path(name).unlink(missing_ok=True)
            origin = entry["path"]
            status = "bundled_bytes_verified"
        else:
            origin = f"https://raw.githubusercontent.com/{repo}/{ref}/{entry['path']}"
            status = fetch(origin, target, entry)
        files.append({"id": entry["id"], "path": str(target), "sha256": entry["sha256"],
                      "origin": origin, "status": status})
    report = {"status": "original_snapshots_verified", "dataset_id": manifest["dataset_id"],
              "source": source, "network_used": source == "github", "files": files,
              "github_commit": ref, "provider_redownload_claimed": False,
              "manifest_sha256": sha(ROOT / "data/manifest.json")}
    (destination / "acquisition.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    frozen = sub.add_parser("frozen", help="Get exactly the four Yahoo snapshots used by this repository")
    frozen.add_argument("--source", choices=["bundled", "github"], default="bundled")
    frozen.add_argument("--repo", help="GitHub OWNER/REPO; default: origin")
    frozen.add_argument("--ref", help="Full commit SHA; default: local HEAD")
    frozen.add_argument("--id", action="append", choices=[e["id"] for e in load(ROOT / "data/manifest.json")["files"]])
    frozen.add_argument("--out", type=Path, default=ROOT / "data/downloaded/yahoo_20261026")
    live = sub.add_parser("live", help="Download current Yahoo chains and run the predeclared selection/F0 checks")
    live.add_argument("--symbol", choices=["^SPX", "^XSP"], default="^SPX")
    live.add_argument("--root", choices=["SPXW", "SPX", "XSP"], default="SPXW")
    live.add_argument("--out", type=Path)
    live.add_argument("--threads", type=int, default=4)
    live.add_argument("--strike-step", type=float)
    papers = sub.add_parser("papers", help="Download the source versions used by the bibliographic audit, with fixed hashes")
    papers.add_argument("--id", action="append", help="Work ID; omit for all seven")
    papers.add_argument("--out", type=Path, default=ROOT / "data/papers")
    args = parser.parse_args(argv)
    if args.command == "frozen":
        if args.source == "bundled" and (args.repo or args.ref):
            parser.error("--repo and --ref require --source github")
        report = acquire_frozen(args.out, args.source, args.repo, args.ref, args.id)
    elif args.command == "live":
        out = args.out or ROOT / "runs" / ("live_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
        cmd = [sys.executable, "-u", str(ROOT / "collect_coherent_yahoo.py"),
               "--symbol", args.symbol, "--root", args.root, "--threads", str(args.threads),
               "--out", str(out), "--attempts", "1", "--attempt-seconds", "120"]
        if args.strike_step is not None:
            cmd += ["--strike-step", str(args.strike_step)]
        return subprocess.call(cmd, cwd=ROOT)
    else:
        entries = load(ROOT / "data/papers_manifest.json")["files"]
        if args.id and set(args.id) - {e["id"] for e in entries}:
            parser.error("Unknown paper ID")
        results, failed = [], False
        for entry in entries:
            if args.id and entry["id"] not in args.id:
                continue
            errors = []
            for url in entry["urls"]:
                try:
                    status = fetch(url, args.out / (entry["id"] + ".pdf"), entry)
                    results.append({"id": entry["id"], "status": status, "sha256": entry["sha256"]})
                    break
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
            else:
                failed = True
                results.append({"id": entry["id"], "status": "unavailable_or_changed", "errors": errors})
        report = {"status": "incomplete" if failed else "source_bytes_verified", "files": results,
                  "readings_automatically_accepted": 0}
        print(json.dumps(report, indent=2), flush=True)
        return 1 if failed else 0
    print(json.dumps(report, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
