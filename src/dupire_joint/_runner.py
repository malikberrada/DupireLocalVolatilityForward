"""Numerical child of the stdlib supervisor; safe to re-import under spawn."""
from __future__ import annotations
import faulthandler
import importlib
import json
import os
from pathlib import Path
import sys
import time
from ._io import atomic_json,append_jsonl


def _checkpoint(stage,state="loading"):
    payload={"invocation":os.environ.get("DUPIRE_INVOCATION"),"stage":stage,"state":state,
             "pid":os.getpid(),"monotonic":time.monotonic()}
    target=Path(os.environ["DUPIRE_STARTUP_FILE"])
    atomic_json(target,payload)
    append_jsonl(target.parent/"startup_events.jsonl",payload)
    if "--quiet" not in sys.argv:
        print(f"[import] {stage}",file=sys.stderr,flush=True)


def main():
    target=Path(os.environ["DUPIRE_STARTUP_FILE"])
    with (target.parent/"native_tracebacks.log").open("a",encoding="utf-8") as trace:
        faulthandler.enable(file=trace)
        faulthandler.dump_traceback_later(20,repeat=True,file=trace)
        try:
            for title,module in (("Import NumPy","numpy"),("Import SciPy sparse","scipy.sparse"),
                                 ("Import SciPy special","scipy.special"),("Import SciPy linalg","scipy.linalg"),
                                 ("Import terminal progress","tqdm"),("Import command implementation","dupire_joint.cli")):
                _checkpoint(title)
                importlib.import_module(module)
            _checkpoint("CLI ready","ready")
            # Keep stack diagnostics for doctor native checks, bounded by the parent.
            if not (len(sys.argv)>1 and sys.argv[1]=="doctor"):
                faulthandler.cancel_dump_traceback_later()
            from .cli import main as numerical_main
            numerical_main()
        finally:
            faulthandler.cancel_dump_traceback_later()
            faulthandler.disable()


if __name__=="__main__":
    main()
