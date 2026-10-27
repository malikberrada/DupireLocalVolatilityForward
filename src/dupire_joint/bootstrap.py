"""Standard-library-only CLI supervisor: observable before native DLL imports.

The numerical program runs in its own process group. A native import/kernel
holding the GIL cannot suppress this parent's heartbeats or deadline checks.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from . import __version__
from ._io import atomic_json as _atomic,read_json


def _read(path):
    try:
        value=read_json(path)
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}


def _note(message,quiet=False):
    if not quiet:
        print(f"[startup] {message}",file=sys.stderr,flush=True)


def _terminate_tree(process):
    """Stop only this invocation's subprocess group, never arbitrary Python jobs."""
    if process.poll() is not None:
        return
    if os.name=="nt":
        try:
            subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10,check=False)
        except (OSError,subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
    process.wait(timeout=5)


def _watch(argv):
    # Reading status must work even if importing SciPy/PyTorch itself hangs.
    parser=argparse.ArgumentParser(prog="dupire-joint watch")
    parser.add_argument("--run",required=True)
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--seconds",type=float,default=0.)
    parser.add_argument("--interval",type=float,default=2.)
    args=parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval<=0 or not math.isfinite(args.seconds) or args.seconds<0:
        parser.error("Invalid interval/duration")
    start=time.monotonic()
    while True:
        directory=Path(args.run)
        result={"status":_read(directory/"status.json"),"supervisor":_read(directory/"supervisor.json"),
                "startup":_read(directory/"startup.json")}
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if args.once or (args.seconds>0 and time.monotonic()-start>=args.seconds):
            return
        time.sleep(args.interval)


def supervise(argv,out,startup_timeout,check_timeout,heartbeat,quiet=False):
    """Return the numerical child's exit code, or 124 for a diagnosed deadline."""
    out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    startup_file=out/"startup.json"
    # Do not reuse a previous invocation's ready marker or status as current state.
    invocation=f"{os.getpid()}-{time.time_ns()}"
    started=time.monotonic()
    _atomic(startup_file,{"invocation":invocation,"stage":"Start Python child","state":"starting"})
    _atomic(out/"status.json",{"stage":"Start Python child","state":"starting","invocation":invocation})
    env=os.environ.copy()
    env["PYTHONUNBUFFERED"]="1"
    env["DUPIRE_STARTUP_FILE"]=str(startup_file)
    env["DUPIRE_INVOCATION"]=invocation
    command=[sys.executable,"-u","-m","dupire_joint._runner",*argv]
    process=subprocess.Popen(command,env=env,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=="nt" else 0,
                             start_new_session=os.name!="nt")
    doctor=bool(argv and argv[0]=="doctor")
    phase="Start Python child";phase_start=started;last_note=started
    def update(state,**extra):
        record={"state":state,"stage":phase,"pid":process.pid,"invocation":invocation,
                "utc":datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds":round(time.monotonic()-started,3),
                "stage_seconds":round(time.monotonic()-phase_start,3),**extra}
        _atomic(out/"supervisor.json",record)
        return record
    update("running")
    try:
        while process.poll() is None:
            boot=_read(startup_file)
            ready=boot.get("state")=="ready" and boot.get("invocation")==invocation
            progress=_read(out/"status.json") if ready else boot
            new_phase=str(progress.get("stage",phase))
            if new_phase!=phase:
                phase=new_phase;phase_start=time.monotonic()
            now=time.monotonic()
            deadline_reached=(not ready and now-started>=startup_timeout) or (ready and doctor and now-phase_start>=check_timeout)
            if deadline_reached:
                _terminate_tree(process)
                limit=startup_timeout if not ready else check_timeout
                reason=f"Deadline {limit:g}s exceeded at: {phase}"
                record=update("timed_out",exit_code=124,error=reason,
                              tracebacks=str(out/"native_tracebacks.log"))
                _atomic(out/"status.json",{**record,"state":"failed","conclusion":"no numerical conclusion"})
                print(f"ERROR: {reason}\nOnly this invocation's process group was stopped. "
                      f"See {out/'startup.json'}, {out/'supervisor.json'} and {out/'native_tracebacks.log'}.",
                      file=sys.stderr,flush=True)
                return 124
            update("running",startup_ready=ready)
            if now-last_note>=heartbeat:
                _note(f"pid={process.pid} stage={phase} stage_time={now-phase_start:.1f}s "
                      f"total={now-started:.1f}s",quiet)
                last_note=now
            time.sleep(.1)
        code=process.wait()
        update("completed" if code==0 else "failed",exit_code=code)
        if code!=0:
            _note(f"child exited with code={code}; last stage={phase}; output={out}",quiet)
        return code
    except KeyboardInterrupt:
        _terminate_tree(process)
        record=update("interrupted",exit_code=130)
        _atomic(out/"status.json",record)
        return 130
    finally:
        if process.poll() is None:
            _terminate_tree(process)


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv==["--version"]:
        print(__version__,flush=True)
        return
    if argv and argv[0]=="watch":
        try:
            return _watch(argv[1:])
        except KeyboardInterrupt:
            raise SystemExit(130) from None
    flags=argparse.ArgumentParser(add_help=False)
    flags.add_argument("--startup-timeout",type=float,default=60.,help="Seconds allowed for numerical imports")
    flags.add_argument("--check-timeout",type=float,default=60.,help="Seconds allowed for each doctor stage")
    flags.add_argument("--heartbeat",type=float,default=5.)
    opts,remaining=flags.parse_known_args(argv)
    if any(not math.isfinite(x) or x<=0 for x in (opts.startup_timeout,opts.check_timeout,opts.heartbeat)):
        flags.error("Timeouts and heartbeat must be finite and strictly positive")
    # This print occurs before importing NumPy, SciPy, tqdm, HiGHS or PyTorch.
    quiet="--quiet" in remaining
    _note(f"dupire-joint {__version__} | Python {sys.version.split()[0]} | executable={sys.executable}",quiet)
    out_parser=argparse.ArgumentParser(add_help=False)
    out_parser.add_argument("--out")
    supplied,_=out_parser.parse_known_args(remaining)
    if supplied.out is None:
        label=remaining[0] if remaining and not remaining[0].startswith("-") else "help"
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        out=str(Path("runs")/(label+"_"+stamp))
        if remaining and remaining[0] in {"doctor","demo","solve","generate","study","verify","bound","benchmark","snapshot","normalize","construct","verify-construct","criterion","verify-criterion"}:
            remaining.extend(["--out",out])
    else:
        out=supplied.out
    _note(f"output={Path(out).resolve()} | startup_timeout={opts.startup_timeout:g}s | "
          f"doctor_stage_timeout={opts.check_timeout:g}s",quiet)
    code=supervise(remaining,out,opts.startup_timeout,opts.check_timeout,opts.heartbeat,quiet)
    if code:
        raise SystemExit(code)

