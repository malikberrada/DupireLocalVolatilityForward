"""Regressions for silent CLI startup / native GIL-blocking initialization."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def run_cli(args,extra_path=None,timeout=20):
    env=os.environ.copy()
    source=str(Path(__file__).resolve().parents[1]/"src")
    env["PYTHONPATH"]=os.pathsep.join(p for p in (str(extra_path) if extra_path else None,source,env.get("PYTHONPATH")) if p)
    return subprocess.run([sys.executable,"-u","-m","dupire_joint",*args],env=env,
                          capture_output=True,text=True,timeout=timeout)


NATIVE_GIL_BLOCK="""import ctypes, os
if os.name == 'nt':
    ctypes.PyDLL('kernel32').Sleep(30000)
else:
    ctypes.PyDLL(None).sleep(30)
"""


def fake_torch(path,code):
    path.mkdir(parents=True,exist_ok=True)
    (path/"torch.py").write_text(code,encoding="utf-8")
    meta=path/"torch-0.0.0.dist-info"
    meta.mkdir()
    (meta/"METADATA").write_text("Metadata-Version: 2.1\nName: torch\nVersion: 0.0.0\n",encoding="utf-8")


def test_version_and_watch_need_no_native_imports(tmp_path):
    (tmp_path/"numpy.py").write_text("raise RuntimeError('NumPy must not be imported')\n",encoding="utf-8")
    r=run_cli(["--version"],tmp_path)
    from dupire_joint import __version__
    assert r.returncode==0 and r.stdout.strip()==__version__,r.stderr
    out=tmp_path/"run";out.mkdir()
    (out/"status.json").write_text(json.dumps({"stage":"Import PyTorch","state":"running"}))
    r=run_cli(["watch","--run",str(out),"--once"],tmp_path)
    assert r.returncode==0 and json.loads(r.stdout)["status"]["stage"]=="Import PyTorch",r.stderr


def test_native_import_holding_gil_has_a_real_startup_deadline(tmp_path):
    fake=tmp_path/"fake";fake.mkdir()
    (fake/"numpy.py").write_text(NATIVE_GIL_BLOCK,encoding="utf-8")
    out=tmp_path/"out"
    r=run_cli(["doctor","--device","cpu","--startup-timeout","1.5","--heartbeat","0.2","--out",str(out)],fake)
    assert r.returncode==124,r.stdout+r.stderr
    assert "executable=" in r.stderr
    assert "Import NumPy" in r.stderr
    assert "stage_time=" in r.stderr
    assert "Deadline" in r.stderr
    report=json.loads((out/"supervisor.json").read_text())
    assert report["state"]=="timed_out" and report["stage"]=="Import NumPy"


def test_cpu_doctor_does_not_import_an_installed_broken_torch(tmp_path):
    fake=tmp_path/"fake"
    fake_torch(fake,"raise RuntimeError('CPU doctor must not import torch')\n")
    out=tmp_path/"cpu"
    r=run_cli(["doctor","--device","cpu","--check-timeout","10","--out",str(out)],fake)
    assert r.returncode==0,r.stdout+r.stderr
    report=json.loads((out/"doctor.json").read_text())
    assert report["lp_smoke_test_passed"]
    assert report["cuda_check_skipped"]
    assert report["selected_device"]=="cpu"


def test_doctor_stops_at_a_gil_blocking_torch_import(tmp_path):
    fake=tmp_path/"fake"
    fake_torch(fake,NATIVE_GIL_BLOCK)
    out=tmp_path/"cuda"
    r=run_cli(["doctor","--device","cuda","--startup-timeout","10",
               "--check-timeout","1.5","--heartbeat","0.2","--out",str(out)],fake)
    assert r.returncode==124,r.stdout+r.stderr
    report=json.loads((out/"supervisor.json").read_text())
    assert report["state"]=="timed_out" and report["stage"]=="Import PyTorch"
    assert "Import PyTorch" in r.stderr and "Deadline" in r.stderr

