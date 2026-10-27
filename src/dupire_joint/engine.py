from __future__ import annotations
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import numpy as np
from . import __version__
from .model import build_lp, audit_lp
from .operators import derivatives, local_variance
from .certificates import find_certificate
from .progress import atomic_json


def _max0(a):
    return float(max(0,np.max(a,initial=0)))


def independent_audit(prices,grid,quotes,vmin,vmax,scheme,local=True,eps=0.,tol=1e-8):
    c=np.asarray(prices,dtype=float).reshape(grid.shape)
    slope,gamma,theta=derivatives(c,grid)
    observed=c.ravel()[grid.quote_indices(quotes)]
    checks={"ask":_max0(observed-quotes.ask-eps*quotes.weight),
            "bid":_max0(quotes.bid-observed-eps*quotes.weight),
            "call_lower":_max0(np.maximum(1-grid.strikes,0)-c),
            "call_upper":_max0(c-1),"slope_upper":_max0(np.diff(c,axis=1)),
            "slope_lower":_max0(-np.diff(c,axis=1)-np.diff(grid.strikes)),
            "convexity":_max0(-gamma),"calendar":_max0(-np.diff(c,axis=0)),
            "left_chord":_max0((c[:,0]-1)/grid.strikes[0]-slope[:,0])}
    if grid.times[0]==0:
        checks["initial_payoff"]=_max0(abs(c[0]-np.maximum(1-grid.strikes,0)))
    if grid.tail_x is not None:
        checks["tail_anchor"]=_max0(abs(c[:,-1]))
    if local:
        gs=gamma[:-1] if scheme=="forward" else gamma[1:]
        delta=np.diff(c,axis=0)[:,1:-1]
        fac=.5*np.diff(grid.times)[:,None]*grid.strikes[None,1:-1]**2
        checks["local_lower"]=_max0(fac*np.asarray(vmin)*gs-delta)
        checks["local_upper"]=_max0(delta-fac*np.asarray(vmax)*gs)
    return {"passed":max(checks.values())<=tol,"checks":checks,"tolerance":tol,
            "method":"direct finite differences, independently of sparse assembly"}


def _json_result(result):
    return {k:v for k,v in result.items() if k not in ("x","ray")}


def _fingerprint(grid,quotes,vmin,vmax,schemes,options,audit_tol,relax,bisect_steps):
    versions={k:importlib.metadata.version(k) for k in ("numpy","scipy","highspy")}
    payload={"package_version":__version__,"versions":versions,"quotes_sha256":quotes.digest(),
             "times":grid.times.tolist(),"strikes":grid.strikes.tolist(),"tail_x":grid.tail_x,
             "vmin":np.asarray(vmin).tolist(),"vmax":np.asarray(vmax).tolist(),"schemes":list(schemes),
             "solver":asdict(options),"audit_tol":audit_tol,"relax":relax,"bisect_steps":bisect_steps}
    code=json.dumps(payload,sort_keys=True,allow_nan=False).encode()
    return hashlib.sha256(code).hexdigest(),payload


def _files_valid(directory,report):
    for name,digest in report.get("artifacts_sha256",{}).items():
        path=directory/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            return False
    return bool(report.get("artifacts_sha256"))


def inspect_solution(lp,result,grid,quotes,vmin,vmax,scheme,local,session,out,name,audit_tol=1e-8,certify=True):
    record=_json_result(result)
    record["lp_sha256"]=lp.digest()
    lp.save(out/f"{name}.lp.npz")
    record["model_file"]=f"{name}.lp.npz"
    record["conclusion"]="indeterminate"
    if result.get("x") is not None:
        record["audit"]=audit_lp(lp,result["x"],audit_tol)
        eps=float(result["x"][-1]) if len(result["x"])>lp.nprice else 0.
        c=result["x"][:lp.nprice].reshape(grid.shape)
        record["independent_audit"]=independent_audit(c,grid,quotes,vmin,vmax,scheme,local,eps,audit_tol)
        if record["audit"]["passed"] and record["independent_audit"]["passed"]:
            record["conclusion"]="feasible_numeric"
            v,gamma,theta,identified=local_variance(c,grid,scheme)
            np.savez_compressed(out/f"{name}.witness.npz",prices=c,times=grid.times,strikes=grid.strikes,
                                local_variance=v,gamma=gamma,theta=theta,identified=identified,
                                epsilon=eps,full_solution=result["x"])
            record["witness_file"]=f"{name}.witness.npz"
            record["unidentified_cells"]=int(np.count_nonzero(~identified))
            record["total_interior_cells"]=int(identified.size)
            if np.any(identified):
                record["local_variance_range"]=[float(v[identified].min()),float(v[identified].max())]
            if len(result["x"])>lp.nprice:
                record["epsilon_upper_bound_numeric"]=eps
                if result["status"]=="optimal":
                    record["epsilon_star_numeric"]=eps
            np.savetxt(out/f"{name}.surface.csv",np.column_stack([
                np.repeat(grid.times,len(grid.strikes)),np.tile(grid.strikes,len(grid.times)),c.ravel()]),
                       delimiter=",",header="time,x,call",comments="",fmt="%.17g")
    if result["status"]=="infeasible" and certify:
        with session.progress.phase(name+" / exact certificate") if session.progress else _nullcontext():
            cert=find_certificate(lp,result,session,name+" certificate")
        if cert:
            atomic_json(out/f"{name}.certificate.json",cert)
            record["conclusion"]="infeasible_certified_binary_lp"
            record["certificate_file"]=f"{name}.certificate.json"
            record["certificate_verification"]=cert["verification"]
        else:
            record["conclusion"]="infeasible_solver_only"
    return record


from contextlib import nullcontext as _nullcontext


def variance_relaxation(grid,quotes,vmin,vmax,scheme,session,steps=20,audit_tol=1e-8,max_slack=100.):
    """Fixed-grid monotone feasibility bisection. Never label an unknown infeasible."""
    lo=0.;hi=max(float(np.max(vmax)),.01)
    checks=[]
    def check(value,label):
        lp=build_lp(grid,quotes,vmin,vmax,scheme,variance_slack=value)
        sol=session.solve(lp,label)
        good=sol.get("x") is not None and audit_lp(lp,sol["x"],audit_tol)["passed"]
        if good:
            good=independent_audit(sol["x"][:lp.nprice],grid,quotes,
                                   np.maximum(np.asarray(vmin)-value,0),np.asarray(vmax)+value,
                                   scheme,tol=audit_tol)["passed"]
        state="feasible_numeric" if good else ("infeasible_solver" if sol["status"]=="infeasible" else "unknown")
        checks.append({"lambda":value,"result":state})
        return state
    initial=check(0.,scheme+" lambda=0")
    if initial=="feasible_numeric":
        return {"lambda_star_numeric":0.,"bracket":[0.,0.],"checks":checks}
    if initial=="unknown":
        return {"status":"indeterminate","checks":checks}
    while hi<=max_slack:
        state=check(hi,f"{scheme} bracket lambda={hi:.6g}")
        if state=="feasible_numeric":
            break
        if state=="unknown":
            return {"status":"indeterminate","checks":checks}
        lo=hi;hi*=2
    else:
        return {"status":"not_bracketed","max_lambda_tested":checks[-1]["lambda"],"checks":checks}
    bar=session.progress.bar(range(steps),desc=f"{scheme} variance bisection") if session.progress else range(steps)
    for k in bar:
        mid=(lo+hi)/2
        state=check(mid,f"{scheme} bisection {k+1}/{steps}")
        if state=="unknown":
            return {"status":"indeterminate","bracket":[lo,hi],"checks":checks}
        if state=="feasible_numeric":
            hi=mid
        else:
            lo=mid
    return {"status":"bracketed_numeric","bracket":[lo,hi],"absolute_width":hi-lo,
            "units":"variance, not volatility","exact_lower_bound_certified":False,
            "checks":checks}


def run_grid(grid,quotes,session,out,vmin=.18**2,vmax=.22**2,schemes=("forward","backward"),
             audit_tol=1e-8,relax=True,bisect_steps=16,resume=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fp,inputs=_fingerprint(grid,quotes,vmin,vmax,schemes,session.options,audit_tol,relax,bisect_steps)
    report_path=out/"report.json"
    if resume and report_path.exists():
        report=json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("fingerprint")!=fp:
            raise ValueError("Checkpoint differs from inputs/options; use another --out")
        completed=report.get("complete",bool(report.get("artifacts_sha256")))
        if completed and _files_valid(out,report):
            if session.progress:
                session.progress.event("resume",force=True,directory=str(out),state="verified_checkpoint_reused")
            return report
        if completed:
            raise ValueError("Checkpoint differs: its artifacts changed; use another --out")
        if session.progress:
            session.progress.event("resume",force=True,directory=str(out),state="recompute_incomplete_grid")
    elif report_path.exists():
        raise ValueError(f"Output grid already exists: {out}; use --resume with matching options or another --out")
    report={"format":"dupire-joint-report-v1","complete":False,"fingerprint":fp,"inputs":inputs,
            "domain":{"time":[float(grid.times[0]),float(grid.times[-1])],
                      "strike":[float(grid.strikes[0]),float(grid.strikes[-1])],
                      "shape":list(grid.shape),"boundary":"c(0)=1 convex chord; " +
                      ("finite support with explicit zero tail anchor" if grid.tail_x is not None else "free right window endpoint; no global tail existence claim")},
            "continuous_existence_proved":False,"variants":{}}
    quotes.write(out/"observations.csv")
    p=session.progress
    with p.phase("assemble F0") if p else _nullcontext():
        lp0=build_lp(grid,quotes,vmin,vmax,local=False)
    sol0=session.solve(lp0,"F0 / quotes + static shape")
    f0=inspect_solution(lp0,sol0,grid,quotes,vmin,vmax,"forward",False,session,out,"F0",audit_tol)
    report["F0"]=f0
    atomic_json(report_path,report)
    for scheme in schemes:
        with p.phase("assemble "+scheme) if p else _nullcontext():
            lp=build_lp(grid,quotes,vmin,vmax,scheme)
        sol=session.solve(lp,scheme+" / joint constraints")
        rec=inspect_solution(lp,sol,grid,quotes,vmin,vmax,scheme,True,session,out,scheme,audit_tol)
        if f0["conclusion"]=="infeasible_certified_binary_lp":
            diagnosis="observations_incompatible_under_recorded_domain_assumptions"
        elif f0["conclusion"]=="feasible_numeric" and rec["conclusion"]=="infeasible_certified_binary_lp":
            diagnosis="joint_constraints_incompatible_on_this_grid_F0_numerically_feasible"
        elif rec["conclusion"]=="feasible_numeric":
            diagnosis="discrete_feasibility_verified_to_tolerance"
        else:
            diagnosis="indeterminate"
        rec["diagnosis"]=diagnosis
        if relax:
            eps_lp=build_lp(grid,quotes,vmin,vmax,scheme,epsilon=True)
            eps_sol=session.solve(eps_lp,scheme+" / minimum quote widening")
            rec["quote_relaxation"]=inspect_solution(eps_lp,eps_sol,grid,quotes,vmin,vmax,scheme,
                                                     True,session,out,scheme+"_epsilon",audit_tol,certify=False)
            if f0["conclusion"]=="feasible_numeric":
                rec["variance_relaxation"]=variance_relaxation(grid,quotes,vmin,vmax,scheme,session,bisect_steps,audit_tol)
            else:
                rec["variance_relaxation"]={"status":"not_computed_F0_not_verified_feasible"}
        report["variants"][scheme]=rec
        atomic_json(report_path,report)
    # Include every scientific output but not this self-referential report.
    artifacts=[x for x in out.iterdir() if x.is_file() and x.name!="report.json"]
    report["artifacts_sha256"]={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in sorted(artifacts)}
    report["complete"]=True
    atomic_json(report_path,report)
    return report
