import errno
import json
import os
from pathlib import Path
import threading
import pytest
from dupire_joint import _io


def test_transient_winerror5_during_replace_is_retried(tmp_path,monkeypatch):
    path=tmp_path/"startup.json"
    _io.atomic_json(path,{"stage":"old"})
    replace=os.replace
    attempts=[]
    def transient(source,destination):
        attempts.append(1)
        if len(attempts)<4:
            assert json.loads(path.read_text())["stage"]=="old"
            e=PermissionError(errno.EACCES,"Access denied")
            e.winerror=5
            raise e
        return replace(source,destination)
    monkeypatch.setattr(_io.os,"replace",transient)
    _io.atomic_json(path,{"stage":"new"})
    assert len(attempts)==4
    assert _io.read_json(path)["stage"]=="new"
    assert not list(tmp_path.glob("dj_*.tmp"))


def test_persistent_denial_preserves_old_checkpoint(tmp_path,monkeypatch):
    path=tmp_path/"report.json"
    _io.atomic_json(path,{"valid":True})
    def denied(*args):
        raise PermissionError(errno.EACCES,"Still locked")
    monkeypatch.setattr(_io.os,"replace",denied)
    with pytest.raises(PermissionError):
        _io.atomic_json(path,{"valid":False},timeout=.025)
    assert _io.read_json(path)=={"valid":True}
    assert not list(tmp_path.glob("dj_*.tmp"))


def test_invalid_json_does_not_touch_checkpoint(tmp_path):
    path=tmp_path/"report.json"
    _io.atomic_json(path,{"valid":True})
    with pytest.raises(ValueError):
        _io.atomic_json(path,{"invalid":float("nan")})
    assert _io.read_json(path)=={"valid":True}


def test_parallel_writers_use_distinct_temporary_files(tmp_path):
    path=tmp_path/"status.json"
    errors=[]
    def writer(identity):
        try:
            for k in range(30):
                _io.atomic_json(path,{"writer":identity,"index":k})
        except BaseException as error:
            errors.append(error)
    threads=[threading.Thread(target=writer,args=(i,)) for i in range(4)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert not errors
    assert _io.read_json(path)["index"]==29
    assert not list(tmp_path.glob("dj_*.tmp"))


def test_open_reader_allows_atomic_replacement(tmp_path):
    path=tmp_path/"startup.json"
    _io.atomic_json(path,{"stage":"old"})
    with _io._open_shared_read(path) as reader:
        _io.atomic_json(path,{"stage":"new"})
        assert json.load(reader)=={"stage":"old"}
    assert _io.read_json(path)=={"stage":"new"}


@pytest.mark.skipif(os.name!="nt",reason="Windows path and replacement semantics require a Windows test host")
def test_windows_shared_reader_handles_long_unicode_path(tmp_path):
    parent=tmp_path
    while len(str(parent))<260:
        parent=parent/"long_windows_path_\u00e9_\U0001f9ea"
    path=parent/"\u00e9tat.json"
    _io.atomic_json(path,{"stage":"ready"})
    with _io._open_shared_read(path) as reader:
        _io.atomic_json(path,{"stage":"done"})
        assert json.load(reader)["stage"]=="ready"
    assert _io.read_json(path)["stage"]=="done"
