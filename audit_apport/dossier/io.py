from __future__ import annotations
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def clean(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def copy(source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    require(sha(source) == sha(target), "Input copy changed bytes")
    return target


def safe_child(root, relative):
    root = Path(root).resolve()
    child = (root / relative).resolve()
    require(child.is_relative_to(root), "Path escapes the audit directory")
    return child


def seal(folder):
    folder = Path(folder)
    files = {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob("*"))
             if p.is_file() and p.name not in {"manifest.json", "events.jsonl", "status.json"}}
    write(folder / "manifest.json", {"format": "dupire-audit-manifest-v1", "sha256": files,
                                      "provider_authentication": False})


def check_manifest(folder):
    m = read(Path(folder) / "manifest.json")
    require(m.get("format") == "dupire-audit-manifest-v1", "Unknown manifest format")
    for name, expected in m["sha256"].items():
        require(sha(safe_child(folder, name)) == expected, "Hash mismatch: " + name)
    return len(m["sha256"])
