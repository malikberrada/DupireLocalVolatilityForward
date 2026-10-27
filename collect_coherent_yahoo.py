"""Collect Yahoo books on a PREDECLARED strike mesh and certify exact F0.

Requires dupire-joint >=0.1.5, its normal dependencies, yfinance and tzdata.
This file's parent process imports only the standard library. All network,
native numerical imports and solving run in a bounded subprocess group.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, date, time as daytime, timedelta, timezone
from fractions import Fraction as Q
from types import SimpleNamespace
from zoneinfo import ZoneInfo

COLLECTOR_VERSION="0.2.0"


def utcnow():
    return datetime.now(timezone.utc)


def save(path, value):
    from dupire_joint._io import atomic_json
    if atomic_json(Path(path), value) is False:
        raise OSError("Cannot persist report: " + str(path))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:raise ValueError(message)


def local_zone(name):
    """Prefer the installed IANA database over a stale operating-system copy."""
    try:
        from importlib.resources import files
        with files("tzdata.zoneinfo").joinpath(*name.split("/")).open("rb") as stream:
            return ZoneInfo.from_file(stream,key=name)
    except (ModuleNotFoundError,FileNotFoundError):
        return ZoneInfo(name)


def session_window(now):
    """Cboe index-option RTH (09:30-16:15 ET; early-close calendar: 13:00)."""
    from dupire_joint.settlements import CLOSED, EARLY
    ny=local_zone("America/New_York")
    local=now.astimezone(ny)
    def interval(day):
        if day.year not in CLOSED:
            raise ValueError("Market-hours calendar covers 2026-2028 only")
        if day.weekday()>=5 or day.strftime("%m-%d") in CLOSED[day.year].split():
            return None
        opening=datetime.combine(day,daytime(9,30),ny)
        closing=datetime.combine(day,daytime(13,0) if day.isoformat() in EARLY else daytime(16,15),ny)
        return opening,closing
    today=interval(local.date())
    if today and today[0]<=local<today[1]:
        return {"open":True,"opening_utc":today[0].astimezone(timezone.utc).isoformat(),
                "closing_utc":today[1].astimezone(timezone.utc).isoformat()}
    for offset in range(10):
        candidate=interval(local.date()+timedelta(days=offset))
        if candidate and candidate[0]>local:
            return {"open":False,"next_open_utc":candidate[0].astimezone(timezone.utc).isoformat(),
                    "next_open_casablanca":candidate[0].astimezone(local_zone("Africa/Casablanca")).isoformat()}
    raise ValueError("No scheduled session found in the next ten days")


def fetch_archive(config, out, progress):
    """Save every retrieved chain. No lastPrice or history substitutes for books."""
    if config.get("offline_snapshot"):
        source=Path(config["offline_snapshot"])
        raw=json.loads(source.read_text(encoding="utf-8-sig"))
        if not raw.get("chains"):
            raise ValueError("Offline input must be raw snapshot.json with calls and puts, not a quality summary")
        shutil.copy2(source,out/"raw_snapshot.json")
        return raw
    with progress.phase("Import yfinance"):
        import yfinance as yf
    from dupire_joint.market_quality import select_expiries
    raw={"source":"yfinance","started_utc":utcnow().isoformat(),"chains":[],"errors":[],
         "quote_timestamps_available":False,"selection":{},
         "warning":"Retrieval times and lastTradeDate do not certify bid/ask times"}
    save(out/"raw_snapshot.json",raw)
    ticker=yf.Ticker(config["symbol"])
    with progress.phase("Read Yahoo expiries"):
        expiries=list(ticker.options)
    dates=select_expiries(expiries,config["max_expiries"],"spread",config["min_days"],
                         config["max_days"],raw["started_utc"])
    raw["selection"]={"expiry_rule":"spread_by_date_before_prices","available_count":len(expiries),
                      "selected_expiries":dates}
    if not dates:
        save(out/"raw_snapshot.json",raw)
        raise ValueError("Yahoo supplies no expiries in the requested window")
    next_request=time.monotonic()+1/config["rps"]
    for expiry in dates:
        delay=max(0,next_request-time.monotonic())
        if delay:time.sleep(delay)
        start=utcnow().isoformat()
        try:
            with progress.phase("Yahoo "+config["symbol"]+" "+expiry):
                chain=ticker.option_chain(expiry)
                calls=json.loads(chain.calls.to_json(orient="records",date_format="iso",double_precision=15))
                puts=json.loads(chain.puts.to_json(orient="records",date_format="iso",double_precision=15))
                underlying=chain.underlying if isinstance(chain.underlying,dict) else {}
            raw["chains"].append({"symbol":config["symbol"],"expiry":expiry,
                "retrieval_started_utc":start,"retrieval_ended_utc":utcnow().isoformat(),
                "underlying":underlying,"calls":calls,"puts":puts})
        except Exception as exc:
            raw["errors"].append({"expiry":expiry,"error":str(exc)})
        next_request=time.monotonic()+1/config["rps"]
        raw["ended_utc"]=utcnow().isoformat()
        save(out/"raw_snapshot.json",raw)
    if not raw["chains"]:
        raise ValueError("No Yahoo chain retrieved; see raw_snapshot.json")
    return raw


def select_books(raw, config):
    """Fixed window AND strike mesh, before parity/F0; no adaptive pruning."""
    from dupire_joint.curve_estimation import book
    from dupire_joint.settlements import aware_utc
    if not raw.get("started_utc") or not raw.get("ended_utc"):
        raise ValueError("Raw snapshot needs retrieval started_utc and ended_utc")
    ref=aware_utc(raw["started_utc"]).date()
    step=Q(str(config.get("strike_step",0)))
    require(step>=0,"strike_step must be nonnegative")
    selected={"source":raw.get("source","unknown"),"started_utc":raw["started_utc"],
        "ended_utc":raw["ended_utc"],"chains":[],"quote_timestamps_available":False,
        "selection_scope":"fixed spot-relative strike window plus explicit invalid-book exclusion",
        "spot_used_as_forward":False}
    exclusions=[];references=[]
    for chain in raw.get("chains",[]):
        if chain.get("symbol")!=config["symbol"]:
            continue
        days=(date.fromisoformat(chain["expiry"])-ref).days
        if not config["min_days"]<=days<=config["max_days"]:
            exclusions.append({"expiry":chain["expiry"],"reason":"outside_predeclared_date_window"})
            continue
        spot=config.get("reference_spot")
        origin="explicit_selection_reference"
        if spot is None:
            spot=chain.get("underlying",{}).get("regularMarketPrice")
            origin="Yahoo_underlying_regularMarketPrice"
        if spot is None or not math.isfinite(float(spot)) or float(spot)<=0:
            raise ValueError("Missing positive underlying reference for "+chain["expiry"]+
                             "; --reference-spot is for strike selection only, never normalization")
        spot=float(spot)
        lo=Q(str(spot))*Q(str(config["moneyness_min"]))
        hi=Q(str(spot))*Q(str(config["moneyness_max"]))
        references.append({"expiry":chain["expiry"],"spot":spot,"origin":origin,
                           "strike_lower":str(lo),"strike_upper":str(hi)})
        target={k:v for k,v in chain.items() if k not in ("calls","puts")}
        target.update(calls=[],puts=[])
        for field,side in (("calls","C"),("puts","P")):
            for row in chain.get(field,[]):
                try:
                    parsed=book(row,chain["expiry"],side,config["root"])
                except (TypeError,ValueError,ZeroDivisionError) as exc:
                    reason=str(exc)
                    if "mismatch" in reason:
                        raise ValueError("Contract integrity failure: "+reason) from exc
                    exclusions.append({"expiry":chain["expiry"],"contract":row.get("contractSymbol"),
                                       "reason":reason,"bid":row.get("bid"),"ask":row.get("ask")})
                    continue
                if parsed is None:
                    continue
                if not lo<=parsed["K"]<=hi:
                    exclusions.append({"expiry":chain["expiry"],"contract":row.get("contractSymbol"),
                                       "reason":"outside_predeclared_strike_window"})
                    continue
                if step and parsed["K"]%step:
                    exclusions.append({"expiry":chain["expiry"],"contract":row.get("contractSymbol"),
                                       "reason":"outside_predeclared_strike_mesh","strike":str(parsed["K"]),
                                       "strike_step":str(step),"strike_origin":"0"})
                    continue
                target[field].append(dict(row))
        selected["chains"].append(target)
    selected["selection"]={"symbol":config["symbol"],"root":config["root"],
        "moneyness_min":config["moneyness_min"],"moneyness_max":config["moneyness_max"],
        "references":references,"outlier_removal_by_feasibility":False,"book_prices_modified":False}
    if "strike_step" in config:
        selected["selection"].update(strike_step=str(step),strike_origin="0",
            selection_protocol="fixed_before_download",full_raw_chain_certified=False)
        selected["selection_scope"]="predeclared strike mesh and spot-relative window; unchanged valid bid/ask"
    return selected,exclusions


def exact_primal_check(lp, vector, time_limit=60):
    """Exact inequalities of the saved binary64 F0. No acceptance tolerance."""
    start=time.monotonic()
    x=[v if isinstance(v,Q) else Q(v) for v in vector]
    if len(x)!=len(lp.cost):return {"passed":False,"reason":"wrong witness dimension"}
    f=lambda z:Q.from_float(float(z))
    for j,value in enumerate(x):
        if not f(lp.lower[j])<=value<=f(lp.upper[j]):
            return {"passed":False,"reason":"variable bound","index":j}
    for i in range(lp.A.shape[0]):
        if time.monotonic()-start>time_limit:
            return {"passed":False,"reason":"exact verification time budget exceeded"}
        s=sum((f(lp.A.data[k])*x[int(lp.A.indices[k])]
               for k in range(lp.A.indptr[i],lp.A.indptr[i+1])),Q(0))
        if s>f(lp.b[i]):return {"passed":False,"reason":"row inequality","index":i}
    return {"passed":True,"rows":lp.A.shape[0],"variables":len(x),
            "arithmetic":"exact rational inequalities of saved binary64 coefficients and bounds"}


def interior_lp(base):
    """Seek numerical room to reconstruct a witness, without relaxing F0."""
    import numpy as np
    from scipy import sparse
    from dupire_joint.model import LP
    n=len(base.cost);m=len(base.b)
    scales=np.maximum(1,np.asarray(abs(base.A).sum(axis=1)).ravel())
    scales=np.maximum(scales,abs(base.b))
    # An equality bid=ask must remain exact; it cannot carry a positive margin.
    a,z=base.groups["ask"];c,d=base.groups["bid"]
    for i in range(z-a):
        if base.b[a+i]==-base.b[c+i]:scales[a+i]=scales[c+i]=0
    A=sparse.vstack([sparse.hstack([base.A,sparse.csr_matrix(scales[:,None])]),
        sparse.hstack([-sparse.eye(n),sparse.csr_matrix(np.ones((n,1)))]),
        sparse.hstack([sparse.eye(n),sparse.csr_matrix(np.ones((n,1)))])],format="csr")
    return LP(A,np.r_[base.b,-base.lower,base.upper],np.r_[base.lower,0.],np.r_[base.upper,1.],
              np.r_[np.zeros(n),-1.],{"base":[0,m],"interior_box":[m,m+2*n]},n)


def logical_grid(folder, config):
    """Exact nominal coordinates and original bid/ask, before binary rounding."""
    from dupire_joint.curve_estimation import book
    raw=json.loads((folder/"snapshot.json").read_text(encoding="utf-8-sig"))
    curves=json.loads((folder/"curves_estimees.csv.uncertainty.json").read_text())
    groups={g["expiry"]:g for g in curves["groups"] if g["status"]=="accepted"}
    obs=[];seen=set();sources=[]
    for chain in raw["chains"]:
        if chain["expiry"] not in groups:continue
        g=groups[chain["expiry"]]
        A,D=Q(g["nominal"]["prepaid_forward"]),Q(g["nominal"]["discount"])
        for field,side in (("calls","C"),("puts","P")):
            for row in chain.get(field,[]):
                r=book(row,chain["expiry"],side,config["root"])
                if r is None or r["contract"] in seen:continue
                seen.add(r["contract"])
                x=r["K"]*D/A
                # A put constrains the SAME call through C=P+A-DK.
                shift=1-x if side=="P" else Q(0)
                obs.append([Q(g["time"]),x,r["bid"]/A+shift,r["ask"]/A+shift])
                sources.append({"contract":r["contract"],"side":side,"expiry":chain["expiry"],
                                "strike":str(r["K"]),"bid":str(r["bid"]),"ask":str(r["ask"])})
    ts=sorted({r[0] for r in obs});xs=sorted({r[1] for r in obs})
    return {"times":[str(t) for t in ts],"strikes":[str(x) for x in xs],
            "observations":[[str(v) for v in r] for r in obs],"sources":sources}


def joint_quotes(folder,config):
    """Call intervals plus parity-translated puts; no raw quote is changed."""
    import numpy as np
    from dupire_joint.data import Quotes
    rows=np.asarray([[float(Q(v)) for v in row]
                     for row in logical_grid(folder,config)["observations"]])
    return Quotes(rows[:,0],rows[:,1],rows[:,2],rows[:,3])


def exact_shape_check(logical, vector, time_limit=60):
    """Check mathematical F0 directly on exact coordinates and original books."""
    start=time.monotonic()
    ts=list(map(Q,logical["times"]));xs=list(map(Q,logical["strikes"]))
    x=list(map(Q,vector));nt,nx=len(ts),len(xs)
    if len(x)!=nt*nx:return {"passed":False,"reason":"logical grid dimension mismatch"}
    c=[x[j*nx:(j+1)*nx] for j in range(nt)]
    ti={v:j for j,v in enumerate(ts)};xi={v:i for i,v in enumerate(xs)}
    for t,k,b,a in logical["observations"]:
        t,k,b,a=map(Q,(t,k,b,a))
        if not b<=c[ti[t]][xi[k]]<=a:return {"passed":False,"reason":"original quote interval"}
    for j,row in enumerate(c):
        if time.monotonic()-start>time_limit:return {"passed":False,"reason":"logical check time budget"}
        if any(not max(1-k,0)<=v<=1 for k,v in zip(xs,row)):
            return {"passed":False,"reason":"exact call value bounds"}
        slopes=[(row[i+1]-row[i])/(xs[i+1]-xs[i]) for i in range(nx-1)]
        if any(not -1<=v<=0 for v in slopes):return {"passed":False,"reason":"exact vertical spread"}
        if any(b<a for a,b in zip(slopes,slopes[1:])):return {"passed":False,"reason":"exact convexity"}
        if (row[0]-1)/xs[0]>slopes[0]:return {"passed":False,"reason":"exact left chord"}
        if j and any(a>b for a,b in zip(c[j-1],row)):
            return {"passed":False,"reason":"exact calendar monotonicity"}
    return {"passed":True,"arithmetic":"exact rational direct shape and original bid/ask checks",
            "times":nt,"strikes":nx,"observations":len(logical["observations"])}


def validate_f0(quotes, config, out, progress):
    import numpy as np
    from dupire_joint.data import Grid
    from dupire_joint.model import build_lp,audit_lp
    from dupire_joint.engine import independent_audit
    from dupire_joint.solver import SolverSession,SolverOptions
    from dupire_joint.certificates import find_certificate
    grid=Grid.from_quotes(quotes)
    nodes=int(np.prod(grid.shape))
    if nodes>config["max_nodes"]:
        return {"status":"not_accepted","reason":"grid_budget_exceeded","nodes":nodes}
    lp=build_lp(grid,quotes,local=False,max_variables=config["max_nodes"])
    lp.save(out/"F0.lp.npz")
    logical=logical_grid(out,config)
    if list(map(float,map(Q,logical["times"])))!=grid.times.tolist() or list(map(float,map(Q,logical["strikes"])))!=grid.strikes.tolist():
        return {"status":"not_accepted","reason":"coordinate_rounding_collision"}
    save(out/"F0.exact_grid.json",logical)
    options=SolverOptions(threads=config["threads"],time_limit=config["solver_seconds"])
    with SolverSession(options,progress) as session:
        original=session.solve(lp,"F0: observations + static/calendar no-arbitrage")
        if original["status"]=="infeasible":
            cert=find_certificate(lp,original,session,"F0")
            if cert:save(out/"F0.infeasibility.json",cert)
            return {"status":"not_accepted","reason":"F0_infeasible","certificate_saved":bool(cert)}
        if original.get("x") is None:
            return {"status":"not_accepted","reason":"F0_no_candidate","solver_status":original["status"]}
        candidates=[]
        interior=session.solve(interior_lp(lp),"Seek F0 interior witness; no quote relaxation")
        if interior.get("x") is not None:candidates.append(interior["x"][:-1])
        candidates.append(original["x"])
    for values in candidates:
        numerical=audit_lp(lp,values,1e-9)
        direct=independent_audit(values[:lp.nprice],grid,quotes,0.,1.,"forward",False,tol=1e-9)
        if not numerical["passed"] or not direct["passed"]:continue
        for denominator in (10**10,10**12,None):
            x=[Q.from_float(float(v)) for v in values]
            if denominator:x=[v.limit_denominator(denominator) for v in x]
            with progress.phase("Exact F0 witness check",denominator_limit=denominator):
                check=exact_primal_check(lp,x,config["exact_seconds"])
                shape=exact_shape_check(logical,x,config["exact_seconds"]) if check["passed"] else {"passed":False}
            if check["passed"] and shape["passed"]:
                save(out/"F0.witness.json",{"format":"coherent-yahoo-primal-v1","lp_sha256":lp.digest(),
                    "quotes_sha256":quotes.digest(),"prices_rational":[str(v) for v in x],"verification":check,
                    "logical_shape_verification":shape})
                save(out/"F0.verification.json",check)
                return {"status":"accepted_exact_F0","nodes":nodes,"shape":list(grid.shape),
                        "numeric_audit":numerical,"independent_audit":direct,"exact_audit":check,
                        "exact_original_book_shape_audit":shape}
    return {"status":"not_accepted","reason":"no_exact_witness_reconstructed",
            "note":"This does not prove infeasibility"}


def process_archive(raw, config, out, progress):
    from dupire_joint.market_quality import audit_archive
    from dupire_joint.curve_estimation import estimate_command
    if raw.get("errors"):
        return {"status":"not_accepted","reason":"incomplete_collection","errors":raw["errors"]}
    selected,excluded=select_books(raw,config)
    selected["raw_snapshot_sha256"]=digest(out/"raw_snapshot.json")
    save(out/"snapshot.json",selected)
    save(out/"selection.json",{"settings":config,"selection":selected["selection"],"excluded":excluded})
    import re
    coverage=[]
    for chain in selected["chains"]:
        count={f:len(chain[f]) for f in ("calls","puts")}
        original=next(c for c in raw["chains"] if c["symbol"]==chain["symbol"] and c["expiry"]==chain["expiry"])
        root_count=sum(bool(re.fullmatch(re.escape(config["root"])+r"\d{6}[CP]\d{8}",r.get("contractSymbol","")))
                       for f in ("calls","puts") for r in original[f])
        coverage.append({"expiry":chain["expiry"],"root":config["root"],"raw_root_books":root_count,
                         "retained":count,"root_present":bool(root_count),
                         "reason":"requested_root_absent" if not root_count else "predeclared_mesh"})
    save(out/"coverage.json",{"groups":coverage,"strike_step":str(config.get("strike_step",0)),
                             "bid_ask_modified":False,"root_substitution":False})
    save(out/"selection_quality.json",audit_archive(selected,config["min_pairs"]))
    args=SimpleNamespace(snapshot=str(out/"snapshot.json"),out=str(out),symbol=config["symbol"],root=config["root"],
        asof=None,settlements=None,min_days=config["min_days"],max_days=config["max_days"],
        min_pairs=config["min_pairs"],max_pairs=config["max_pairs"],time_limit=config["solver_seconds"],
        allow_partial=False,normalize=True,crossed_policy="reject")
    # Every selected maturity must pass. Never drop a maturity because its LP fails.
    try:estimate_command(args,progress)
    except SystemExit as exc:
        if exc.code!=3:raise
        return {"status":"not_accepted","reason":"parity_or_data_quality_failed"}
    from dupire_joint.data import Quotes
    q=Quotes.read(out/"quotes.csv")
    if len(set(q.time))<config["min_expiries"]:
        return {"status":"not_accepted","reason":"insufficient_accepted_expiries"}
    joint=joint_quotes(out,config)
    joint.write(out/"F0.quotes.csv")
    with progress.phase("Build and certify F0"):
        result=validate_f0(joint,config,out,progress)
    result.update(quote_count=len(q.time),expiry_count=len(set(q.time)),
        joint_call_and_put_interval_count=len(joint.time),
        bid_ask_timestamps_certified=False,local_volatility_bounds_certified=False,
        scope="predeclared strike mesh and strike/date window; unchanged valid books; nominal parity normalization")
    return result


def verify_bundle(folder, config, progress):
    from dupire_joint.curve_estimation import verify_curves,normalize_estimated
    from dupire_joint.data import Quotes,Grid
    from dupire_joint.model import LP,build_lp
    if (folder/"READY.json").exists():
        for name,expected in json.loads((folder/"READY.json").read_text()).get("sha256",{}).items():
            require(digest(folder/name)==expected,"Accepted file hash mismatch: "+name)
    selected,excluded=select_books(json.loads((folder/"raw_snapshot.json").read_text(encoding="utf-8-sig")),config)
    selected["raw_snapshot_sha256"]=digest(folder/"raw_snapshot.json")
    require(selected==json.loads((folder/"snapshot.json").read_text(encoding="utf-8-sig")),"Selection no longer matches raw books")
    verify_curves(folder/"snapshot.json",folder/"curves_estimees.csv",progress)
    quotes=Quotes.read(folder/"quotes.csv")
    with tempfile.TemporaryDirectory() as tmp:
        checked=normalize_estimated(folder/"snapshot.json",folder/"curves_estimees.csv",config["symbol"],config["root"],Path(tmp)/"q.csv")
        require(checked.digest()==quotes.digest(),"Normalized quotes differ from retained books")
    joint=joint_quotes(folder,config)
    require(joint.digest()==Quotes.read(folder/"F0.quotes.csv").digest(),"Joint call/put intervals differ from original books")
    lp=LP.load(folder/"F0.lp.npz")
    rebuilt=build_lp(Grid.from_quotes(joint),joint,local=False,max_variables=config["max_nodes"])
    require(lp.digest()==rebuilt.digest(),"F0 model does not match quotes")
    witness=json.loads((folder/"F0.witness.json").read_text())
    require(witness["lp_sha256"]==lp.digest() and witness["quotes_sha256"]==joint.digest(),"Witness hash mismatch")
    check=exact_primal_check(lp,[Q(v) for v in witness["prices_rational"]],config["exact_seconds"])
    require(check["passed"],str(check))
    logical=logical_grid(folder,config)
    require(logical==json.loads((folder/"F0.exact_grid.json").read_text()),"Exact grid differs from original books")
    shape=exact_shape_check(logical,witness["prices_rational"],config["exact_seconds"])
    require(shape["passed"],str(shape))
    return {"status":"verified_exact_F0","verification":check,
            "original_quote_shape_verification":shape,
            "raw_selection_and_nominal_normalization_recomputed":True,"bid_ask_timestamps_certified":False}


def worker(config_file, out_name, verify_only=False):
    config=json.loads(Path(config_file).read_text())
    out=Path(out_name)
    print("[worker] Import numerical dependencies",flush=True)
    from dupire_joint.progress import Progress
    from dupire_joint import __version__
    progress=Progress(out)
    try:
        if verify_only:result=verify_bundle(out,config,progress)
        else:
            with progress.phase("Acquire fresh raw archive" if not config.get("offline_snapshot") else "Read offline raw archive"):
                raw=fetch_archive(config,out,progress)
            result=process_archive(raw,config,out,progress)
            if result["status"]=="accepted_exact_F0":
                with progress.phase("Reverify selected books, curves and exact F0 from RAW archive"):
                    verified=verify_bundle(out,config,progress)
                save(out/"verification.json",verified)
                result["verified_from_raw_archive"]=True
        result.update(package_version=__version__,collector_version=COLLECTOR_VERSION,
                      mode="offline_replay" if config.get("offline_snapshot") else "live_yahoo")
        save(out/("reverification.json" if verify_only else "result.json"),result)
        print(json.dumps(result,indent=2),flush=True)
        return 0 if result["status"] in ("accepted_exact_F0","verified_exact_F0") else 3
    except Exception as exc:
        result={"status":"not_accepted","reason":"worker_error","error":str(exc)}
        save(out/("reverification.json" if verify_only else "result.json"),result)
        progress.event("collector",force=True,state="failed",error=str(exc))
        return 2


def terminate(process):
    if process.poll() is not None:return
    if os.name=="nt":
        try:
            subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,timeout=10,check=False)
        except (OSError,subprocess.TimeoutExpired):
            pass
    else:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name=="nt":process.kill()
        else:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        process.wait(timeout=3)


def supervise(config_path, out, timeout, verify_only=False):
    cmd=[sys.executable,"-u",str(Path(__file__).resolve()),"_worker",str(config_path),str(out)]
    if verify_only:cmd.append("verify")
    process=subprocess.Popen(cmd,start_new_session=os.name!="nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=="nt" else 0)
    start=time.monotonic();next_note=start+5
    try:
        while process.poll() is None:
            now=time.monotonic()
            if now-start>timeout:
                terminate(process)
                return {"status":"not_accepted","reason":"attempt_timeout","seconds":timeout}
            if now>=next_note:
                print(f"[supervisor] pid={process.pid} elapsed={now-start:.1f}s directory={out}",flush=True)
                next_note=now+5
            time.sleep(.2)
    except BaseException:
        terminate(process)
        raise
    result_path=out/("reverification.json" if verify_only else "result.json")
    if not result_path.exists():
        return {"status":"not_accepted","reason":"worker_exited_without_report","exit_code":process.returncode}
    result=json.loads(result_path.read_text())
    if process.returncode!=0 and result.get("status") in ("accepted_exact_F0","verified_exact_F0"):
        return {"status":"not_accepted","reason":"nonzero_worker_exit","exit_code":process.returncode}
    return result


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0]=="_worker":
        return worker(argv[1],argv[2],len(argv)>3 and argv[3]=="verify")
    print("[startup] Coherent Yahoo collector "+COLLECTOR_VERSION+" | Python "+sys.version.split()[0]+" | "+sys.executable,flush=True)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol",choices=["^SPX","^XSP"],default="^SPX")
    parser.add_argument("--root",choices=["SPXW","SPX","XSP"],default="SPXW")
    parser.add_argument("--out",default=None)
    parser.add_argument("--min-days",type=int,default=14)
    parser.add_argument("--max-days",type=int,default=180)
    parser.add_argument("--max-expiries",type=int,default=6)
    parser.add_argument("--min-expiries",type=int,default=2)
    parser.add_argument("--min-pairs",type=int,default=3)
    parser.add_argument("--max-pairs",type=int,default=2000)
    parser.add_argument("--moneyness-min",type=float,default=.95)
    parser.add_argument("--moneyness-max",type=float,default=1.05)
    parser.add_argument("--strike-step",type=float,default=None,
                        help="Fixed mesh BEFORE prices: default 50 index points for SPX/SPXW, 5 for XSP. 0: dense diagnostic mode")
    parser.add_argument("--reference-spot",type=float,default=None,help="Selection reference only; never a forward")
    parser.add_argument("--rps",type=float,default=1.)
    parser.add_argument("--threads",type=int,default=10)
    parser.add_argument("--max-nodes",type=int,default=50000)
    parser.add_argument("--solver-seconds",type=float,default=60)
    parser.add_argument("--exact-seconds",type=float,default=60)
    parser.add_argument("--attempt-seconds",type=float,default=300)
    parser.add_argument("--attempts",type=int,default=3)
    parser.add_argument("--retry-seconds",type=float,default=15)
    parser.add_argument("--max-collection-seconds",type=float,default=120)
    parser.add_argument("--allow-closed-market",action="store_true")
    parser.add_argument("--offline-snapshot",default=None,help="Replay an existing raw archive; not a new market observation")
    parser.add_argument("--verify",default=None,help="Recheck an accepted directory without any download")
    args=parser.parse_args(argv)
    from dupire_joint.settlements import ROOTS
    if args.verify:
        folder=Path(args.verify).resolve();config_file=folder/"collector_config.json"
        config=json.loads(config_file.read_text())
        result=supervise(config_file,folder,config["attempt_seconds"],True)
        print(json.dumps(result,indent=2),flush=True)
        return 0 if result["status"]=="verified_exact_F0" else 3
    if (args.symbol,args.root) not in ROOTS:parser.error("Symbol and root do not match")
    if args.strike_step is None:args.strike_step=5. if args.root=="XSP" else 50.
    if not math.isfinite(args.strike_step) or args.strike_step<0:parser.error("strike-step must be finite and nonnegative")
    if not (0<=args.min_days<args.max_days and 2<=args.min_expiries<=args.max_expiries and 2<=args.min_pairs<=args.max_pairs):
        parser.error("Invalid maturity, expiry or pair limits")
    for key in ("moneyness_min","moneyness_max","rps","solver_seconds","exact_seconds","attempt_seconds",
                "retry_seconds","max_collection_seconds"):
        if not math.isfinite(getattr(args,key)) or getattr(args,key)<=0:parser.error(key+" must be finite and positive")
    if not args.moneyness_min<args.moneyness_max or args.rps>2 or not 1<=args.attempts<=10 or args.threads<1 or args.max_nodes<6:
        parser.error("Invalid window, rate, attempt, thread or grid budget")
    if args.reference_spot is not None and (not math.isfinite(args.reference_spot) or args.reference_spot<=0):
        parser.error("reference-spot must be finite and positive")
    if args.offline_snapshot:args.offline_snapshot=str(Path(args.offline_snapshot).resolve())
    out=Path(args.out or ("runs/coherent_yahoo_"+utcnow().strftime("%Y%m%dT%H%M%S_%fZ"))).resolve()
    if out.exists() and any(out.iterdir()):parser.error("Use a new empty --out directory to preserve previous attempts")
    out.mkdir(parents=True,exist_ok=True)
    config=vars(args);save(out/"collector_config.json",config)
    save(out/"protocol.json",{"collector_version":COLLECTOR_VERSION,"symbol":args.symbol,"root":args.root,
        "strike_step":str(Q(str(args.strike_step))),"strike_origin":"0",
        "moneyness_window":[args.moneyness_min,args.moneyness_max],"min_pairs":args.min_pairs,
        "date_window_days":[args.min_days,args.max_days],"price_modification_allowed":False,
        "adaptive_strike_selection_allowed":False,"mathematical_failures_drop_expiry":False,
        "recorded_before_download":True})
    if not args.offline_snapshot and not args.allow_closed_market:
        hours=session_window(utcnow())
        if not hours["open"]:
            result={"status":"not_accepted","reason":"scheduled_regular_session_closed",**hours}
            save(out/"result.json",result);print(json.dumps(result,indent=2),flush=True)
            return 4
    attempts=1 if args.offline_snapshot else args.attempts
    for number in range(1,attempts+1):
        if not args.offline_snapshot and not args.allow_closed_market and not session_window(utcnow())["open"]:
            break
        attempt=out/f"attempt_{number:02d}";attempt.mkdir()
        save(attempt/"collector_config.json",config)
        shutil.copy2(out/"protocol.json",attempt/"protocol.json")
        print(f"[collector] attempt {number}/{attempts}: {attempt}",flush=True)
        result=supervise(attempt/"collector_config.json",attempt,args.attempt_seconds)
        if result["status"]=="accepted_exact_F0":
            raw=json.loads((attempt/"raw_snapshot.json").read_text(encoding="utf-8-sig"))
            if not args.offline_snapshot:
                from dupire_joint.settlements import aware_utc
                elapsed=(aware_utc(raw["ended_utc"])-aware_utc(raw["started_utc"])).total_seconds()
                if elapsed>args.max_collection_seconds:
                    result={"status":"not_accepted","reason":"collection_window_too_long","seconds":elapsed}
            if result["status"]=="accepted_exact_F0":
                accepted=out/"accepted";shutil.copytree(attempt,accepted)
                ready={"status":"accepted_exact_F0","quotes":str(accepted/"quotes.csv"),
                    "snapshot":str(accepted/"snapshot.json"),"raw_snapshot":str(accepted/"raw_snapshot.json"),
                    "F0_model":str(accepted/"F0.lp.npz"),"F0_witness":str(accepted/"F0.witness.json"),
                    "mode":"offline_replay" if args.offline_snapshot else "live_yahoo",
                    "bid_ask_timestamps_certified":False,"local_volatility_bounds_certified":False,
                    "collector_version":COLLECTOR_VERSION,"verified_from_raw_archive":True,
                    "selection_protocol":"fixed_strike_mesh_before_download",
                    "strike_step":str(Q(str(args.strike_step))),"strike_origin":"0",
                    "full_raw_chain_certified":False,"bid_ask_modified":False}
                ready["sha256"]={name:digest(accepted/name) for name in ("raw_snapshot.json","snapshot.json",
                    "collector_config.json",
                    "curves_estimees.csv","curves_estimees.csv.uncertainty.json","quotes.csv","F0.quotes.csv",
                    "F0.lp.npz","F0.witness.json","F0.exact_grid.json")}
                for name in ("coverage.json","verification.json","protocol.json"):
                    ready["sha256"][name]=digest(accepted/name)
                save(accepted/"READY.json",ready);save(out/"result.json",ready)
                print(json.dumps(ready,indent=2),flush=True)
                return 0
        save(attempt/"attempt_result.json",result)
        print("[collector] not accepted: "+result.get("reason","unknown"),flush=True)
        if number<attempts:time.sleep(args.retry_seconds)
    failed={"status":"not_accepted","reason":"no_coherent_snapshot_obtained","accepted_file_created":False,
            "note":"Raw attempts remain archived. No prices were repaired or widened."}
    save(out/"result.json",failed);print(json.dumps(failed,indent=2),flush=True)
    return 3


if __name__=="__main__":
    try:sys.exit(main())
    except KeyboardInterrupt:print("[collector] interrupted; subprocess group stopped",file=sys.stderr);sys.exit(130)
