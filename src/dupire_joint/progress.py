"""TTY progress, non-TTY heartbeats, atomic state and append-only event logs."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import sys
import threading
import time
from tqdm import tqdm
from ._io import atomic_json,append_jsonl


class Progress:
    def __init__(self, out=None, quiet=False, heartbeat=5.0):
        self.out = Path(out) if out else None
        if self.out:
            self.out.mkdir(parents=True, exist_ok=True)
        self.quiet = quiet
        self.heartbeat = heartbeat
        self.started = time.monotonic()
        self.last_print = 0.0
        self.lock = threading.RLock()
        self.state = {}

    def event(self, stage, *, force=False, **fields):
        with self.lock:
            now = time.monotonic()
            self.state = dict(stage=stage, utc=datetime.now(timezone.utc).isoformat(),
                              elapsed_seconds=round(now-self.started, 3), **fields)
            if self.out:
                atomic_json(self.out / "status.json", self.state)
                append_jsonl(self.out/"events.jsonl",self.state)
            if not self.quiet and (force or now-self.last_print >= self.heartbeat):
                self.last_print = now
                extras = " ".join(f"{k}={v}" for k,v in fields.items())
                tqdm.write(f"[{self.state['utc']}] {stage} | {now-self.started:.1f}s {extras}", file=sys.stderr)

    @contextmanager
    def phase(self, name, **fields):
        self.event(name, force=True, state="running", **fields)
        stop = threading.Event()
        def beat():
            while not stop.wait(self.heartbeat):
                self.event(name, state="running", **fields)
        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        except BaseException as e:
            self.event(name, force=True, state="failed", error=str(e), **fields)
            raise
        else:
            self.event(name, force=True, state="done", **fields)
        finally:
            stop.set()
            thread.join(timeout=1)

    def bar(self, iterable=None, *, total=None, desc="", **kwargs):
        return tqdm(iterable, total=total, desc=desc, disable=self.quiet or not sys.stderr.isatty(),
                    dynamic_ncols=True, mininterval=0.3, **kwargs)

