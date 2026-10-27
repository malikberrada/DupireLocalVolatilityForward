"""Shared JSON I/O for supervisors, progress and scientific checkpoints.

Windows readers buffer a snapshot and close the disk handle before returning
it, so an atomic rename can happen while that snapshot is consumed. Transient
sharing/access errors receive bounded retries; a failed scientific write
preserves the previous snapshot.
No numerical library is imported by this module.
"""
from __future__ import annotations
import errno
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time


def _retry_io(operation,timeout=2.0):
    if timeout<0:
        raise ValueError("timeout must be nonnegative")
    deadline=time.monotonic()+timeout
    delay=.01
    while True:
        try:
            return operation()
        except OSError as error:
            transient=isinstance(error,PermissionError) or getattr(error,"winerror",None) in (5,32,33) or error.errno==errno.EBUSY
            remaining=deadline-time.monotonic()
            if not transient or remaining<=0:
                raise
            time.sleep(min(delay,remaining))
            delay=min(delay*2,.1)


def atomic_json(path,data,*,timeout=2.0):
    # Serialize before touching the current destination: invalid JSON cannot
    # replace a valid scientific checkpoint.
    text=json.dumps(data,indent=2,allow_nan=False,default=str)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    # Short, unique names also avoid same-process/thread temporary collisions.
    fd,name=tempfile.mkstemp(prefix="dj_",suffix=".tmp",dir=path.parent)
    temp=Path(name)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as handle:
            handle.write(text)
        _retry_io(lambda:os.replace(temp,path),timeout)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _open_shared_read(path):
    if os.name!="nt":
        return open(path,"rb")
    name=os.path.abspath(os.fspath(path))
    if not name.startswith("\\\\?\\"):
        name="\\\\?\\UNC\\"+name[2:] if name.startswith("\\\\") else "\\\\?\\"+name
    # MoveFileExW (used by os.replace) cannot replace an open destination,
    # even when that reader grants FILE_SHARE_DELETE. JSON is already read
    # in full by json.load, so retain its bytes instead of a live disk handle.
    # A concurrent writer can retry the brief read, then publish a new file
    # while the caller continues to parse this consistent previous snapshot.
    with open(name,"rb") as handle:
        return BytesIO(handle.read())


def read_json(path):
    with _open_shared_read(path) as handle:
        return json.load(handle)


def append_jsonl(path,data,*,timeout=2.0):
    line=json.dumps(data,allow_nan=False,default=str)+"\n"
    def append():
        with Path(path).open("a",encoding="utf-8") as handle:
            handle.write(line)
    _retry_io(append,timeout)
