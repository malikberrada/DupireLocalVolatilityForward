from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import numpy as np
from . import __version__
from .data import Quotes,Grid
from .engine import run_grid
from .model import LP
from .operators import local_variance,conditional_error_bound
from .pricing import black_scholes,heston_checked,Heston,discrete_surface,select_device
from .progress import Progress,atomic_json
from .solver import SolverSession,SolverOptions


def solver_options(args):
    return SolverOptions(threads=args.threads,time_limit=args.time_limit,tolerance=args.solver_tol,method=args.method)


def schemes(args):
    return ("forward","backward") if args.scheme=="both" else (args.scheme,)


def levels(value):
    a=[int(v) for v in value.split(",")]
    if not a or any(v<0 or v>8 for v in a) or a!=sorted(set(a)):
        raise argparse.ArgumentTypeError("Use increasing distinct levels in [0,8], e.g. 0,1,2")
    return a


def refinement_run(q,args,session,p,out=None):
    out=Path(out or args.out)
    reports=[]
    for level in p.bar(args.levels,desc="Grid refinements"):
        sl=level if args.refine_mode in ("coupled","space") else 0
        tl=level if args.refine_mode in ("coupled","time") else 0
        grid=Grid.from_quotes(q,sl,tl,args.tail_x)
        rec=run_grid(grid,q,session,out/f"level_{level:02d}",args.sigma_min**2,args.sigma_max**2,
                     schemes(args),args.audit_tol,args.relax,args.bisect_steps,args.resume)
        reports.append({"level":level,"shape":list(grid.shape),"F0":rec["F0"]["conclusion"],
                        "variants":{k:v["conclusion"] for k,v in rec["variants"].items()},
                        "report":f"level_{level:02d}/report.json","quotes_sha256":q.digest()})
        atomic_json(out/"refinement.json",{"runs":reports,"observation_hash_unchanged":True})
    changed={}
    for scheme in schemes(args):
        seen_bad=False;changed[scheme]=False
        for r in reports:
            value=r["variants"][scheme]
            changed[scheme] |= seen_bad and value=="feasible_numeric"
            seen_bad |= value=="infeasible_certified_binary_lp"
    summary={"runs":reports,"mesh_dependence_demonstrated_numeric_fine_witness":changed,
             "continuous_existence_proved":False,"nested_feasible_sets_assumed":False,
             "observation_hash_unchanged":True}
    atomic_json(out/"refinement.json",summary)
    return summary


def show_summary(summary):
    for r in summary["runs"]:
        print(f"level={r['level']} grid={r['shape']} F0={r['F0']}",flush=True)
        for scheme,status in r["variants"].items():
            print(f"  {scheme}: {status}",flush=True)


def cmd_demo(args,p):
    device=select_device(args.device,6)
    with p.phase("Black-Scholes counterexample",device=device):
        t=np.array([.25,1.]);x=np.array([.9,1.,1.1])
        c=black_scholes(t,x,.2,device)
        q=Quotes.from_surface(t,x,c)
        q.write(Path(args.out)/"counterexample.csv")
        grid=Grid(t,x)
        values={s:float(math.sqrt(local_variance(c,grid,s)[0][0,0])) for s in ("forward","backward")}
    atomic_json(Path(args.out)/"counterexample.json",{"sigma_BS":.2,"discrete_sigma":values,
                "bounds_sigma":[args.sigma_min,args.sigma_max],"reference_arithmetic":"binary64; not an interval enclosure"})
    print("Counterexample: "+", ".join(f"{s}={100*v:.6f}%" for s,v in values.items()),flush=True)
    with SolverSession(solver_options(args),p) as session:
        summary=refinement_run(q,args,session,p)
    show_summary(summary)


def cmd_solve(args,p):
    with p.phase("Load and validate observations"):
        q=Quotes.read(args.quotes)
    with SolverSession(solver_options(args),p) as session:
        summary=refinement_run(q,args,session,p)
    show_summary(summary)


def _axes(args,rng=None):
    if args.nx<3 or args.nt<2:
        raise ValueError("Require nx>=3, nt>=2")
    x=np.linspace(.65,1.45,args.nx)
    if rng is not None:
        x[1:-1]+=rng.uniform(-.2,.2,args.nx-2)*(x[1]-x[0])
    t=np.geomspace(.1,1.,args.nt)
    return t,x


def _stagger(q,times):
    keep=np.zeros(len(q.time),dtype=bool)
    for j,T in enumerate(times):
        ids=np.flatnonzero(q.time==T)
        keep[ids[::2] if j%2==0 else ids[1::2]]=True
        keep[ids[0]]=True;keep[ids[-1]]=True
    return Quotes(q.time[keep],q.x[keep],q.bid[keep],q.ask[keep],q.weight[keep])


def cmd_generate(args,p):
    rng=np.random.default_rng(args.seed)
    t,x=_axes(args,rng)
    dev=select_device(args.device,len(t)*len(x)*(args.heston_nodes*4 if args.family=="heston" else 1))
    metadata={"family":args.family,"seed":args.seed,"device":dev}
    with p.phase("Generate "+args.family,device=dev):
        if args.family=="heston":
            c,quality=heston_checked(t,x,nodes=args.heston_nodes,device=dev,progress=p)
            metadata.update(quality)
            metadata["parameters"]=asdict(Heston())
            metadata["local_bounds_not_inferred_from_v0"]=True
        elif args.family=="discrete":
            c=discrete_surface(Grid(t,x),args.sigma,args.sigma)
        else:
            c=black_scholes(t,x,args.sigma,dev)
    q=Quotes.from_surface(t,x,c,args.half_spread)
    if args.stagger:
        q=_stagger(q,t)
        metadata["different_observed_strikes_by_maturity"]=True
    target=Path(args.out)/"quotes.csv";q.write(target)
    metadata["quotes_sha256"]=q.digest();metadata["sigma"]=args.sigma
    atomic_json(Path(args.out)/"generation.json",metadata)
    print(target,flush=True)


def cmd_study(args,p):
    if not 1<=args.cases<=10000:
        raise ValueError("cases must be in [1,10000]")
    families=[s.strip() for s in args.families.split(",")]
    if not families or not set(families)<={"bs","discrete","corrupt","heston"}:
        raise ValueError("Families: bs,discrete,corrupt,heston")
    rng=np.random.default_rng(args.seed)
    summary=[]
    with SolverSession(solver_options(args),p) as session:
        for k in p.bar(range(args.cases),desc="Research cases"):
            family=families[k%len(families)]
            t,x=_axes(args,rng)
            width=args.sigma_max-args.sigma_min
            sigma=float(rng.uniform(args.sigma_min+.25*width,args.sigma_max-.25*width))
            case=Path(args.out)/f"case_{k:04d}_{family}"
            case.mkdir(parents=True,exist_ok=True)
            dev=select_device(args.device,len(t)*len(x)*256 if family=="heston" else len(t)*len(x))
            with p.phase(f"case {k+1}/{args.cases} {family} reference",device=dev):
                if family=="heston":
                    c,quality=heston_checked(t,x,nodes=args.heston_nodes,device=dev,progress=p)
                elif family=="discrete":
                    c=discrete_surface(Grid(t,x),sigma,sigma);quality={"scheme":"backward"}
                else:
                    c=black_scholes(t,x,sigma,dev);quality={"analytic_generator":"Black-Scholes","sigma":sigma}
                q=Quotes.from_surface(t,x,c,args.half_spread)
                if args.stagger:
                    q=_stagger(q,t)
                    quality["different_observed_strikes_by_maturity"]=True
                if family=="corrupt":
                    # Exact crossed interval gives a controlled, model-independent F0 contradiction.
                    q.bid[len(q.bid)//2]=q.ask[len(q.bid)//2]+.01
                    quality["controlled_perturbation"]="crossed quote, gap .01 normalized units"
            atomic_json(case/"reference.json",quality)
            result=refinement_run(q,args,session,p,case)
            summary.append({"case":k,"family":family,"reference":quality,"result":result})
            atomic_json(Path(args.out)/"study.json",{"seed":args.seed,"cases":summary})
    for case in summary:
        print(f"case={case['case']} family={case['family']}",flush=True)
        show_summary(case["result"])


def cmd_doctor(args,p):
    data={"package_version":__version__,"python":sys.version,"platform":platform.platform(),
          "logical_cpus":os.cpu_count(),"lp_backend":"HiGHS C++ CPU (pip wheel)","precision":"float64"}
    with p.phase("Read package metadata"):
        for name in ("numpy","scipy","highspy","torch","yfinance"):
            try:
                data[name]=importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                data[name]=None
    available=False
    if args.device=="cpu":
        # A CPU diagnostic must remain usable if importing torch/CUDA hangs.
        data["cuda_check_skipped"]=True
        data["cuda_available"]=None
        data["selected_device"]="cpu"
    elif data["torch"]:
        with p.phase("Import PyTorch"):
            import torch
        data["torch_cuda_runtime"]=torch.version.cuda
        if args.device=="torch-cpu":
            with p.phase("PyTorch CPU kernel smoke test"):
                result=torch.tensor([1.,2.],dtype=torch.float64)+1
                if result.tolist()!=[2.,3.]:
                    raise ArithmeticError("PyTorch CPU smoke test failed")
            data["cuda_check_skipped"]=True
            data["cuda_available"]=None
            data["selected_device"]="torch-cpu"
        else:
            with p.phase("Check CUDA availability"):
                available=torch.cuda.is_available()
            data["cuda_available"]=available
            data["cuda_check_skipped"]=False
            if available:
                with p.phase("Initialize CUDA device"):
                    data["gpu"]=torch.cuda.get_device_name(0)
                    props=torch.cuda.get_device_properties(0)
                    data["gpu_memory_GiB"]=props.total_memory/2**30
                with p.phase("CUDA Black-Scholes kernel smoke test"):
                    a=black_scholes([.25,1.],[.9,1.,1.1],.2,"cuda")
                    b=black_scholes([.25,1.],[.9,1.,1.1],.2,"cpu")
                    data["cuda_BS_max_error"]=float(np.max(abs(a-b)))
                    if data["cuda_BS_max_error"]>1e-10:
                        raise ArithmeticError("CUDA BS smoke test differs from CPU")
                data["selected_device"]="cuda"
            elif args.device=="cuda":
                raise RuntimeError("CUDA explicitly requested, but PyTorch reports no accessible CUDA GPU")
            else:
                data["selected_device"]="cpu"
    elif args.device in ("cuda","torch-cpu"):
        raise RuntimeError("PyTorch is missing; install its wheel for the requested device")
    else:
        data["cuda_available"]=False
        data["selected_device"]="cpu"
    p.event("Start HiGHS worker",force=True,state="running")
    with SolverSession(SolverOptions(threads=min(2,os.cpu_count() or 1),time_limit=10),p) as session:
        from scipy import sparse
        lp=LP(sparse.csr_matrix([[1.]]),np.array([.5]),np.array([0.]),np.array([1.]),np.array([-1.]))
        r=session.solve(lp,"C++ LP smoke test")
        data["lp_smoke_test_passed"]=bool(r["status"]=="optimal" and abs(r["x"][0]-.5)<1e-8)
        if not data["lp_smoke_test_passed"]:
            raise RuntimeError("C++ LP smoke test failed")
    atomic_json(Path(args.out)/"doctor.json",data)
    print(json.dumps(data,indent=2),flush=True)


def cmd_verify(args,p):
    from .certificates import verify_certificate
    with p.phase("Exact certificate verification"):
        lp=LP.load(args.model)
        certificate=json.loads(Path(args.certificate).read_text(encoding="utf-8"))
        result=verify_certificate(lp,certificate)
    atomic_json(Path(args.out)/"verification.json",result)
    print(json.dumps(result,indent=2),flush=True)
    if not result["verified"]:
        raise ValueError("Certificate did not verify")


def cmd_bound(args,p):
    records=[]
    for level in range(args.max_level+1):
        factor=2**level
        r=conditional_error_bound(args.hm/factor,args.hp/factor,args.dt/factor,args.xmin,
                                  args.gamma0,args.M3,args.M4,args.Mtt,args.vmax)
        r["level"]=level;r["below_variance_margin"]=r["variance_error_bound"] is not None and r["variance_error_bound"]<=args.delta_v
        records.append(r)
        if r["below_variance_margin"]:
            break
    result={"conditional_only":True,"observations_feasibility_not_established":True,"levels":records,
            "suggested_coupled_level":records[-1]["level"] if records[-1]["below_variance_margin"] else None}
    atomic_json(Path(args.out)/"conditional_bound.json",result)
    print(json.dumps(result,indent=2),flush=True)


def cmd_benchmark(args,p):
    sizes=[int(v) for v in args.sizes.split(",")]
    if min(sizes)<10 or max(sizes)>50_000_000 or args.repeat<1:
        raise ValueError("Use 10<=sizes<=50 million, repeat>=1")
    cuda=select_device("auto",1_000_000)=="cuda"
    if args.device=="cuda":
        select_device("cuda",1)
    rows=[]
    for size in p.bar(sizes,desc="CPU/CUDA benchmark"):
        nx=max(3,int(math.sqrt(size)));nt=max(2,size//nx)
        t=np.linspace(.05,2.,nt);x=np.linspace(.4,1.8,nx)
        row={"calls":nt*nx}
        reference=None
        for dev in (["cpu","cuda"] if cuda else ["cpu"]):
            with p.phase("benchmark "+dev,calls=nt*nx):
                black_scholes(t[:2],x[:3],.2,dev) # initialization excluded
                durations=[]
                for k in range(args.repeat):
                    start=time.perf_counter();c=black_scholes(t,x,.2,dev)
                    durations.append(time.perf_counter()-start) # includes device->host transfer
                row[dev+"_median_seconds"]=float(np.median(durations))
                if dev=="cpu":
                    reference=c
                else:
                    row["max_price_difference"]=float(np.max(abs(c-reference)))
                    if row["max_price_difference"]>1e-10:
                        raise ArithmeticError("CPU/CUDA benchmark price mismatch")
        if cuda:
            row["measured_cuda_speedup"]=row["cpu_median_seconds"]/row["cuda_median_seconds"]
        rows.append(row)
    result={"cuda_available":cuda,"results":rows,"timing_includes_output_transfer":True,
            "lp_backend_is_CPU":True,"guaranteed_speedup_claimed":False}
    atomic_json(Path(args.out)/"benchmark.json",result)
    print(json.dumps(result,indent=2),flush=True)


def cmd_watch(args,p):
    started=time.monotonic()
    while True:
        path=Path(args.run)/"status.json"
        if path.exists():
            try:
                print(json.dumps(json.loads(path.read_text(encoding="utf-8")),ensure_ascii=False),flush=True)
            except (OSError,json.JSONDecodeError):
                print("Status update in progress",flush=True)
        else:
            print("Waiting for status.json",flush=True)
        if args.once or (args.seconds>0 and time.monotonic()-started>=args.seconds):
            break
        time.sleep(args.interval)


def parser():
    root=argparse.ArgumentParser(description="Joint discrete Dupire feasibility | HiGHS C++ + optional PyTorch CUDA")
    root.add_argument("--version",action="version",version=__version__)
    sub=root.add_subparsers(dest="command",required=True)
    def common(name,help):
        a=sub.add_parser(name,help=help)
        a.add_argument("--out",default=None,help="Output directory (default: runs/command_timestamp)")
        a.add_argument("--quiet",action="store_true",help="Disable console progress, keep status/events files")
        return a
    def device(a):
        a.add_argument("--device",choices=["auto","cpu","cuda","torch-cpu"],default="auto")
    def solving(a):
        a.add_argument("--threads",type=int,default=min(10,max(1,(os.cpu_count() or 2)//2)))
        a.add_argument("--time-limit",type=float,default=120.,help="Native solve limit in seconds per LP")
        a.add_argument("--solver-tol",type=float,default=1e-9)
        a.add_argument("--audit-tol",type=float,default=1e-8)
        a.add_argument("--method",choices=["choose","simplex","ipm"],default="choose")
        a.add_argument("--scheme",choices=["forward","backward","both"],default="both")
        a.add_argument("--sigma-min",type=float,default=.18)
        a.add_argument("--sigma-max",type=float,default=.22)
        a.add_argument("--levels",type=levels,default=[0,1,2])
        a.add_argument("--refine-mode",choices=["coupled","space","time"],default="coupled")
        a.add_argument("--tail-x",type=float,default=None,help="Optional explicit finite-support zero tail anchor")
        a.add_argument("--relax",action="store_true",help="Compute epsilon* LP and lambda* bisection")
        a.add_argument("--bisect-steps",type=int,default=16)
        a.add_argument("--resume",action="store_true",help="Reuse matching completed grids with SHA-256 checked artifacts")
    def axes(a):
        a.add_argument("--nx",type=int,default=25)
        a.add_argument("--nt",type=int,default=5)
        a.add_argument("--seed",type=int,default=20261025)
        a.add_argument("--half-spread",type=float,default=1e-5,help="Normalized call units")
        a.add_argument("--heston-nodes",type=int,default=128)
        a.add_argument("--stagger",action="store_true",help="Use different observed strikes by maturity; solve on their union")
    from .constructive import register
    register(sub,common)
    from .finite_criterion import register as register_criterion
    register_criterion(common)
    from .curve_estimation import register as register_curves
    register_curves(common)
    from .market_quality import register as register_market_quality
    register_market_quality(common)
    a=common("demo","Reproduce the Black-Scholes discretization counterexample");device(a);solving(a)
    a.set_defaults(func=cmd_demo)
    a=common("solve","Analyze normalized quote CSV, preserving all observation nodes");solving(a)
    a.add_argument("--quotes",required=True);a.set_defaults(func=cmd_solve)
    a=common("generate","Generate a synthetic quote surface");device(a);axes(a)
    a.add_argument("--family",choices=["bs","discrete","heston"],default="bs")
    a.add_argument("--sigma",type=float,default=.2);a.set_defaults(func=cmd_generate)
    a=common("study","Reproducible irregular-grid BS/discrete/perturbed/Heston experiments");device(a);solving(a);axes(a)
    a.add_argument("--cases",type=int,default=12)
    a.add_argument("--families",default="bs,discrete,corrupt")
    a.set_defaults(func=cmd_study)
    a=common("doctor","Check pip libraries, C++ solver and optional CUDA");device(a);a.set_defaults(func=cmd_doctor)
    a=common("verify","Verify a saved infeasibility certificate with exact rational arithmetic")
    a.add_argument("--model",required=True);a.add_argument("--certificate",required=True);a.set_defaults(func=cmd_verify)
    a=common("bound","Conditional common-grid Taylor bound and coupled refinement plan")
    for field in ("hm","hp","dt","xmin","gamma0","M3","M4","Mtt","vmax","delta-v"):
        a.add_argument("--"+field,type=float,required=True)
    a.add_argument("--max-level",type=int,default=16);a.set_defaults(func=cmd_bound)
    a=common("benchmark","Measure CPU/CUDA BS performance including output transfer");device(a)
    a.add_argument("--sizes",default="1000,100000,1000000");a.add_argument("--repeat",type=int,default=5)
    a.set_defaults(func=cmd_benchmark)
    a=common("snapshot","Archive available Yahoo European index option chains")
    a.add_argument("--symbols",default="^SPX,^XSP");a.add_argument("--max-expiries",type=int,default=12)
    a.add_argument("--retries",type=int,default=3);a.add_argument("--rps",type=float,default=.5)
    a.add_argument("--expiry-selection",choices=["front","spread"],default="front")
    a.add_argument("--min-days",type=int,default=None)
    a.add_argument("--max-days",type=int,default=None)
    a.add_argument("--require-matched-pairs",type=int,default=0,help="0 disables quality gate; otherwise require >=2 paired strikes in at least one root/expiry")
    def do_snapshot(args,p):
        from .market import snapshot
        snapshot(args.symbols.split(","),args.out,p,args.max_expiries,args.retries,args.rps,
                 args.expiry_selection,args.min_days,args.max_days,args.require_matched_pairs)
    a.set_defaults(func=do_snapshot)
    a=common("normalize","Normalize a single verified European contract root with explicit curves")
    a.add_argument("--snapshot",required=True);a.add_argument("--curves",required=True)
    a.add_argument("--symbol",required=True);a.add_argument("--root",required=True)
    def do_normalize(args,p):
        from .market import normalize_snapshot
        with p.phase("Normalize European calls"):
            q=normalize_snapshot(args.snapshot,args.curves,args.symbol,args.root,Path(args.out)/"quotes.csv")
        print(f"{len(q.time)} quotes -> {Path(args.out)/'quotes.csv'}",flush=True)
    a.set_defaults(func=do_normalize)
    a=sub.add_parser("watch",help="Read live status from another terminal")
    a.add_argument("--run",required=True);a.add_argument("--once",action="store_true")
    a.add_argument("--seconds",type=float,default=0.,help="0: continue until Ctrl+C")
    a.add_argument("--interval",type=float,default=2.);a.set_defaults(func=cmd_watch,out=None,quiet=True)
    return root


def main(argv=None):
    args=parser().parse_args(argv)
    if args.command!="watch" and args.out is None:
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        args.out=str(Path("runs")/(args.command+"_"+stamp))
    p=Progress(args.out,args.quiet)
    try:
        if hasattr(args,"sigma_min"):
            if args.command in ("criterion","construct"):
                from fractions import Fraction
                if not 0<=Fraction(args.sigma_min)<=Fraction(args.sigma_max):
                    raise ValueError("Require exact 0<=sigma-min<=sigma-max")
            elif not 0<=args.sigma_min<=args.sigma_max or not np.isfinite([args.sigma_min,args.sigma_max]).all():
                raise ValueError("Require finite 0<=sigma-min<=sigma-max; inputs are decimal volatilities")
        if hasattr(args,"audit_tol") and (not 0<args.audit_tol<=1e-4 or not np.isfinite(args.audit_tol)):
            raise ValueError("audit-tol must be finite in (0,1e-4]")
        if hasattr(args,"bisect_steps") and not 1<=args.bisect_steps<=64:
            raise ValueError("bisect-steps must be in [1,64]")
        if hasattr(args,"half_spread") and (not np.isfinite(args.half_spread) or args.half_spread<0):
            raise ValueError("half-spread must be finite and nonnegative")
        if args.command=="watch" and (not np.isfinite(args.interval) or args.interval<=0 or not np.isfinite(args.seconds) or args.seconds<0):
            raise ValueError("Invalid watch interval/duration")
        if args.command=="bound" and (not np.isfinite(args.delta_v) or args.delta_v<=0 or not 0<=args.max_level<=64):
            raise ValueError("delta-v must be positive and max-level in [0,64]")
        p.event(args.command,force=True,state="starting",package_version=__version__,output=args.out)
        args.func(args,p)
        p.event(args.command,force=True,state="completed",output=args.out)
        if args.out:
            print(f"Outputs: {Path(args.out).resolve()}",flush=True)
    except KeyboardInterrupt:
        p.event(args.command,force=True,state="interrupted",checkpoints_preserved=True)
        raise SystemExit(130) from None
    except Exception as e:
        p.event(args.command,force=True,state="failed",error=str(e))
        print(f"ERROR: {e}",file=sys.stderr,flush=True)
        raise SystemExit(2) from None

