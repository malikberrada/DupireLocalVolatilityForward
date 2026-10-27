"""Shared JSON I/O for supervisors, progress and scientific checkpoints.

Windows readers explicitly share DELETE access so an atomic rename may happen
while they read the previous snapshot. Transient sharing/access errors receive
bounded retries; a failed scientific write preserves the previous snapshot.
No numerical library is imported by this module.
"""
from __future__ import annotations
import errno
from functools import lru_cache
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


@lru_cache(maxsize=1)
def _windows_reader_api():
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    create=kernel.CreateFileW
    create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,
                     wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    create.restype=wintypes.HANDLE
    close=kernel.CloseHandle
    close.argtypes=[wintypes.HANDLE]
    close.restype=wintypes.BOOL
    return ctypes,create,close


def _open_shared_read(path):
    if os.name!="nt":
        return open(path,"rb")
    import msvcrt
    ctypes,create,close=_windows_reader_api()
    name=os.path.abspath(os.fspath(path))
    if not name.startswith("\\\\?\\"):
        name="\\\\?\\UNC\\"+name[2:] if name.startswith("\\\\") else "\\\\?\\"+name
    # GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
    # OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL.
    handle=create(name,0x80000000,0x1|0x2|0x4,None,3,0x80,None)
    if handle is None or handle==ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd=msvcrt.open_osfhandle(int(handle),os.O_RDONLY|os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    try:
        # Ownership of the Windows handle moved to the CRT fd and this stream.
        return os.fdopen(fd,"rb")
    except BaseException:
        os.close(fd)
        raise


def read_json(path):
    with _open_shared_read(path) as handle:
        return json.load(handle)


def append_jsonl(path,data,*,timeout=2.0):
    line=json.dumps(data,allow_nan=False,default=str)+"\n"
    def append():
        with Path(path).open("a",encoding="utf-8") as handle:
            handle.write(line)
    _retry_io(append,timeout)
