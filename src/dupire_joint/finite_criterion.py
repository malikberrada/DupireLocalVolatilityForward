"""Theorem 1: exact finite-grid alternative, conditional on fixed normalization.

The authoritative model is rational. HiGHS only proposes primal/dual witnesses;
neither its status nor its rounded matrix is used as a mathematical proof.
See docs/CRITERE_PROUVE.md for hypotheses, both proofs and scope.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from .model import LP
from .progress import atomic_json
from .solver import SolverOptions, SolverSession

FORMAT = "dupire-exact-grid-problem-v1"
CERTIFICATE = "dupire-exact-grid-certificate-v1"
SCHEMES = ("none", "forward", "backward", "joint")


def rational(v):
    if isinstance(v, (float, np.floating, bool)):
        raise ValueError("Use decimal/rational strings or integers, not floating-point inputs")
    return Q(v)


def bound_array(value, nt, nx):
    if isinstance(value, (str, int, Q)):
        return tuple(tuple(rational(value) for _ in range(nx-2)) for _ in range(nt-1))
    rows = tuple(tuple(rational(x) for x in row) for row in value)
    if len(rows) != nt-1 or any(len(row) != nx-2 for row in rows):
        raise ValueError("Variance bounds need shape (number of times-1, number of strikes-2)")
    return rows


@dataclass(frozen=True)
class Problem:
    times: tuple
    strikes: tuple
    observations: tuple
    vmin: tuple
    vmax: tuple
    scheme: str = "joint"
    source: dict | None = None

    def __post_init__(self):
        ts, xs = tuple(map(rational, self.times)), tuple(map(rational, self.strikes))
        obs = tuple(tuple(map(rational, row)) for row in self.observations)
        if len(ts) < 2 or len(xs) < 3:
            raise ValueError("Require at least two times and three strikes on a common grid")
        if ts[0] < 0 or xs[0] <= 0 or any(b <= a for axis in (ts, xs) for a,b in zip(axis,axis[1:])):
            raise ValueError("Times must increase from >=0; strikes must increase from >0")
        if not obs or any(len(row) != 4 for row in obs):
            raise ValueError("Observations must be nonempty rows [time,x,bid,ask]")
        ti, xi = set(ts), set(xs)
        if any(t not in ti or x not in xi for t,x,_,_ in obs):
            raise ValueError("Every original observation must be a grid node; no interpolation")
        lo, hi = bound_array(self.vmin,len(ts),len(xs)), bound_array(self.vmax,len(ts),len(xs))
        if any(l < 0 or h < l for lr,hr in zip(lo,hi) for l,h in zip(lr,hr)):
            raise ValueError("Require finite 0 <= vmin <= vmax in every cell")
        if self.scheme not in SCHEMES:
            raise ValueError("scheme must be none, forward, backward or joint")
        for name,value in (("times",ts),("strikes",xs),("observations",obs),("vmin",lo),("vmax",hi)):
            object.__setattr__(self,name,value)

    @property
    def shape(self):
        return len(self.times),len(self.strikes)

    def payload(self):
        return {"format":FORMAT,"times":list(map(str,self.times)),"strikes":list(map(str,self.strikes)),
                "observations":[list(map(str,row)) for row in self.observations],
                "vmin":[list(map(str,row)) for row in self.vmin],
                "vmax":[list(map(str,row)) for row in self.vmax],"scheme":self.scheme,
                "source":self.source,"tail":"finite_window_no_zero_tail_anchor",
                "normalization":"fixed_nominal_F_D_and_settlement_times"}

    def digest(self):
        return hashlib.sha256(json.dumps(self.payload(),sort_keys=True,separators=(",",":")).encode()).hexdigest()

    @classmethod
    def load(cls,payload):
        if payload.get("format") != FORMAT:
            raise ValueError("Unknown exact-grid problem format")
        if payload.get("tail") != "finite_window_no_zero_tail_anchor":
            raise ValueError("This criterion does not silently add a zero tail anchor")
        if payload.get("normalization") != "fixed_nominal_F_D_and_settlement_times":
            raise ValueError("Unsupported normalization hypothesis")
        return cls(*(payload[k] for k in ("times","strikes","observations","vmin","vmax","scheme")),
                   source=payload.get("source"))


def read_source(path,logical=False):
    path=Path(path)
    if logical:
        raw=json.loads(path.read_text(encoding="utf-8-sig"),parse_float=Q)
        ts,xs=raw["times"],raw["strikes"]
        obs=[row[:4] for row in raw["observations"]]
        kind="rational_normalized_grid"
    else:
        with path.open(encoding="utf-8-sig",newline="") as f:
            obs=[[row[k] for k in ("time","x","bid","ask")] for row in csv.DictReader(f)]
        ts=sorted({rational(r[0]) for r in obs});xs=sorted({rational(r[1]) for r in obs})
        if len(xs)==2:
            xs.insert(1,(xs[0]+xs[1])/2)
        kind="exact_decimal_CSV"
    source={"kind":kind,"filename":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    return ts,xs,obs,source


def dyadic(axis,level):
    if not isinstance(level,int) or not 0<=level<=12:
        raise ValueError("Refinement level must be an integer in [0,12]")
    a=tuple(map(rational,axis));r=2**level
    return tuple(x+(y-x)*Q(i,r) for x,y in zip(a,a[1:]) for i in range(r))+(a[-1],)


class ExactSystem:
    """Sparse rational rows A c<=b, plus a finite intrinsic/upper price box."""
    def __init__(self,problem,max_nodes=100000):
        self.problem=problem
        nt,nx=problem.shape
        self.n=nt*nx
        if self.n>max_nodes:
            raise ValueError(f"Exact grid has {self.n} nodes; max-nodes={max_nodes}")
        ts,xs=problem.times,problem.strikes
        self.lower=[max(1-x,Q(0)) for _ in ts for x in xs]
        self.upper=[Q(1) for _ in range(self.n)]
        if ts[0]==0:
            self.upper[:nx]=self.lower[:nx]
        self.rows=[]

        def add(group,entries,rhs=0):
            row={}
            for k,v in entries:
                row[k]=row.get(k,Q(0))+v
            self.rows.append((group,{k:v for k,v in row.items() if v},Q(rhs)))

        def gamma(j,i):
            hm,hp=xs[i]-xs[i-1],xs[i+1]-xs[i]
            s=Q(2)/(hm+hp)
            return [(j*nx+i-1,s/hm),(j*nx+i,-s*(1/hm+1/hp)),(j*nx+i+1,s/hp)]

        for j in range(nt):
            for i in range(nx-1):
                left,right=j*nx+i,j*nx+i+1
                add("slope_upper",[(right,Q(1)),(left,Q(-1))])
                add("slope_lower",[(left,Q(1)),(right,Q(-1))],xs[i+1]-xs[i])
            for i in range(1,nx-1):
                add("convexity",[(k,-v) for k,v in gamma(j,i)])
            h=xs[1]-xs[0]
            add("left_chord",[(j*nx,1/h+1/xs[0]),(j*nx+1,-1/h)],1/xs[0])
        for j in range(nt-1):
            for i in range(nx):
                add("calendar",[(j*nx+i,Q(1)),((j+1)*nx+i,Q(-1))])
        selected=("forward","backward") if problem.scheme=="joint" else (problem.scheme,)
        for scheme in selected:
            if scheme=="none":continue
            for j in range(nt-1):
                for i in range(1,nx-1):
                    g=gamma(j if scheme=="forward" else j+1,i)
                    fac=(ts[j+1]-ts[j])*xs[i]**2/2
                    delta=[((j+1)*nx+i,Q(1)),(j*nx+i,Q(-1))]
                    lo,hi=problem.vmin[j][i-1],problem.vmax[j][i-1]
                    add(scheme+"_local_lower",[(k,fac*lo*v) for k,v in g]+[(k,-v) for k,v in delta])
                    add(scheme+"_local_upper",delta+[(k,-fac*hi*v) for k,v in g])
        t_index={t:j for j,t in enumerate(ts)};x_index={x:i for i,x in enumerate(xs)}
        for t,x,bid,ask in problem.observations:
            k=t_index[t]*nx+x_index[x]
            add("ask",[(k,Q(1))],ask)
            add("bid",[(k,Q(-1))],-bid)

    def primal(self,values):
        c=list(map(rational,values))
        if len(c)!=self.n:
            return {"verified":False,"reason":"Wrong witness dimension"}
        minima={"price_box":min(min(v-l,u-v) for v,l,u in zip(c,self.lower,self.upper))}
        for group,row,b in self.rows:
            slack=b-sum((a*c[k] for k,a in row.items()),Q(0))
            minima[group]=min(minima.get(group,slack),slack)
        nt,nx=self.problem.shape
        xs=self.problem.strikes
        gammas=[2*((c[j*nx+i+1]-c[j*nx+i])/(xs[i+1]-xs[i])
                   -(c[j*nx+i]-c[j*nx+i-1])/(xs[i]-xs[i-1]))/(xs[i+1]-xs[i-1])
                for j in range(nt) for i in range(1,nx-1)]
        return {"verified":min(minima.values())>=0,"minimum_slack":{k:str(v) for k,v in minima.items()},
                "checked_rows":len(self.rows),"checked_price_bounds":2*self.n,
                "minimum_gamma":str(min(gammas)),"zero_gamma_nodes":sum(g==0 for g in gammas),
                "variance_quotient_everywhere_identifiable":all(g>0 for g in gammas),
                "arithmetic":"exact rationals on the original declared data and geometry"}

    def dual(self,indices,multipliers):
        if not indices or len(indices)!=len(multipliers) or len(set(indices))!=len(indices):
            raise ValueError("Invalid dual support")
        residual={};rhs=Q(0)
        for i,y in zip(indices,map(rational,multipliers)):
            if not isinstance(i,int) or not 0<=i<len(self.rows) or y<0:
                raise ValueError("Invalid dual row or negative multiplier")
            _,row,b=self.rows[i]
            rhs+=y*b
            for k,a in row.items():residual[k]=residual.get(k,Q(0))+y*a
        box_min=sum((r*(self.lower[k] if r>=0 else self.upper[k]) for k,r in residual.items()),Q(0))
        gap=box_min-rhs
        return {"verified":gap>0,"exact_separation_margin":str(gap),"box_minimum":str(box_min),
                "combined_rhs":str(rhs),"support_size":len(indices),
                "arithmetic":"exact rationals on the original declared data and geometry"}

    def oracle(self):
        ri=[];ci=[];av=[];bs=[];scales=[]
        for i,(_,row,b) in enumerate(self.rows):
            scale=max([Q(1),abs(b)]+[abs(a) for a in row.values()])
            scales.append(scale);bs.append(float(b/scale))
            for j,a in row.items():ri.append(i);ci.append(j);av.append(float(a/scale))
        lp=LP(sparse.csr_matrix((av,(ri,ci)),shape=(len(bs),self.n)),bs,
              list(map(float,self.lower)),list(map(float,self.upper)),np.zeros(self.n),nprice=self.n)
        return lp,scales


def verify(problem,certificate,max_nodes=100000):
    if certificate.get("format")!=CERTIFICATE or certificate.get("problem_sha256")!=problem.digest():
        return {"verified":False,"reason":"Certificate format or exact problem hash mismatch"}
    system=ExactSystem(problem,max_nodes)
    if certificate.get("kind")=="primal":
        check=system.primal(certificate["prices"])
    elif certificate.get("kind")=="dual":
        check=system.dual(certificate["rows"],certificate["multipliers"])
    else:
        raise ValueError("Certificate must be a primal witness or a dual separator")
    return {**check,"kind":certificate["kind"],"scheme":problem.scheme,"problem_sha256":problem.digest()}


def interior(lp):
    m,n=lp.A.shape
    a=sparse.vstack([
        sparse.hstack([lp.A,sparse.csr_matrix(np.ones((m,1)))]),
        sparse.hstack([-sparse.eye(n),sparse.csr_matrix(np.ones((n,1)))]),
        sparse.hstack([sparse.eye(n),sparse.csr_matrix(np.ones((n,1)))])])
    return LP(a,np.r_[lp.b,-lp.lower,lp.upper],np.r_[lp.lower,0.],np.r_[lp.upper,1.],
              np.r_[np.zeros(n),-1.],nprice=n)


def search(problem,session,out,label,max_nodes):
    system=ExactSystem(problem,max_nodes)
    lp,scales=system.oracle()
    atomic_json(out/(label+".problem.json"),problem.payload())
    result=session.solve(lp,label+" / numerical proposal for the exact criterion")
    record={"solver_status":result["status"],"conclusion":"not_certified","scheme":problem.scheme,
            "problem_sha256":problem.digest(),"rows":len(system.rows),"nodes":system.n}
    certificate=None
    candidates=[]
    if result.get("x") is not None:
        proposed=session.solve(interior(lp),label+" / interior proposal, unchanged exact constraints")
        if proposed.get("x") is not None:candidates.append(proposed["x"][:-1])
        candidates.append(result["x"])
    for vector in candidates:
        if not np.isfinite(vector).all():continue
        for den in (10**10,10**12,None):
            prices=[Q(float(v)).limit_denominator(den) if den else Q(float(v)) for v in vector]
            if system.primal(prices)["verified"]:
                certificate={"kind":"primal","prices":list(map(str,prices))}
                break
        if certificate:break
    if certificate is None and result["status"]=="infeasible":
        rays=[]
        if result.get("ray") is not None:
            rays.extend((result["ray"],-result["ray"]))
        from .certificates import find_certificate
        fallback=find_certificate(lp,result,session,label+" / dual proposal")
        if fallback:
            y=np.zeros(len(system.rows))
            y[fallback["rows"]]=fallback["multipliers"]
            rays.append(y)
        for ray in rays:
            if not np.isfinite(ray).all():continue
            ys=[max(Q(float(y)),Q(0))/s for y,s in zip(ray,scales)]
            indices=[i for i,y in enumerate(ys) if y]
            if indices and system.dual(indices,[ys[i] for i in indices])["verified"]:
                certificate={"kind":"dual","rows":indices,"multipliers":[str(ys[i]) for i in indices]}
                break
    if certificate:
        certificate.update(format=CERTIFICATE,problem_sha256=problem.digest())
        check=verify(problem,certificate,max_nodes)
        if not check["verified"]:raise RuntimeError("Internal certificate verification failed")
        atomic_json(out/(label+".certificate.json"),certificate)
        record.update(conclusion="feasible_exact" if certificate["kind"]=="primal" else "infeasible_exact",
                      verification=check,certificate=label+".certificate.json")
    return record


def command(args,progress):
    out=Path(args.out)
    if any((out/name).exists() for name in ("criterion.json","F0.problem.json","criterion.problem.json")):
        raise ValueError("Use a new --out directory; previous exact proofs are preserved")
    with progress.phase("Read exact observations and declare finite-grid hypotheses"):
        path=args.logical_grid or args.quotes
        ts,xs,obs,source=read_source(path,logical=bool(args.logical_grid))
        nt=(len(ts)-1)*2**args.time_level+1;nx=(len(xs)-1)*2**args.space_level+1
        if nt*nx>args.max_nodes:raise ValueError("Requested grid exceeds --max-nodes before allocation")
        ts,xs=dyadic(ts,args.time_level),dyadic(xs,args.space_level)
        slo,shi=rational(args.sigma_min),rational(args.sigma_max)
        if not 0<=slo<=shi:raise ValueError("Require 0 <= sigma-min <= sigma-max")
        problem=Problem(ts,xs,obs,slo*slo,shi*shi,args.scheme,source)
    with SolverSession(SolverOptions(args.threads,args.time_limit,1e-10,args.method),progress) as session:
        f0=search(replace(problem,scheme="none"),session,out,"F0",args.max_nodes)
        if args.scheme=="none":
            requested=f0
        elif f0["conclusion"]=="infeasible_exact":
            requested={"conclusion":"infeasible_by_exact_F0_subset","scheme":args.scheme}
        else:
            requested=search(problem,session,out,"criterion",args.max_nodes)
    conclusion=requested["conclusion"]
    diagnosis=("observations_and_static_constraints_incompatible" if f0["conclusion"]=="infeasible_exact"
               else "bounds_and_grid_incompatible_with_observations" if conclusion=="infeasible_exact" and f0["conclusion"]=="feasible_exact"
               else "compatible_on_declared_grid" if conclusion=="feasible_exact" else "not_certified")
    report={"theorem":"docs/CRITERE_PROUVE.md, Theoreme 1","F0":f0,"requested":requested,
            "conclusion":conclusion,"diagnosis":diagnosis,"source":source,
            "assumptions":{"common_cartesian_grid":True,"shape":[nt,nx],"all_observations_retained":True,
                           "observation_count":len(obs),"normalization_fixed":True,
                           "variance_bounds":[str(slo*slo),str(shi*shi)],"same_surface_for_both_schemes":args.scheme=="joint",
                           "zero_tail_anchor":False,"payoff_at_T0":problem.times[0]==0},
            "continuous_extension_proved":False,"normalization_uncertainty_propagated":False,
            "numerical_discovery_is_complete_exact_algorithm":False}
    atomic_json(out/"criterion.json",report)
    print(json.dumps({"conclusion":conclusion,"diagnosis":diagnosis,"scheme":args.scheme,
                      "shape":[nt,nx],"report":str(out/"criterion.json")},indent=2),flush=True)
    if conclusion in ("infeasible_exact","infeasible_by_exact_F0_subset"):raise SystemExit(4)
    if conclusion!="feasible_exact":raise SystemExit(3)


def verify_command(args,progress):
    with progress.phase("Verify exact-grid alternative without calling a solver"):
        problem=Problem.load(json.loads(Path(args.problem).read_text(encoding="utf-8-sig")))
        if args.quotes or args.logical_grid:
            path=args.logical_grid or args.quotes
            _,_,obs,source=read_source(path,logical=bool(args.logical_grid))
            if tuple(tuple(map(rational,row)) for row in obs)!=problem.observations:
                raise ValueError("External original observations differ from the certified problem")
            if problem.source and source["sha256"]!=problem.source.get("sha256"):
                raise ValueError("External source file hash differs")
        certificate=json.loads(Path(args.certificate).read_text(encoding="utf-8-sig"))
        check=verify(problem,certificate,args.max_nodes)
        check["external_source_checked"]=bool(args.quotes or args.logical_grid)
        atomic_json(Path(args.out)/"criterion.verification.json",check)
    print(json.dumps(check,indent=2),flush=True)
    if not check["verified"]:raise SystemExit(3)


def register(common):
    a=common("criterion","Prove exact finite-grid feasibility or infeasibility on declared data")
    src=a.add_mutually_exclusive_group(required=True)
    src.add_argument("--quotes",help="Normalized CSV; decimals are exact rationals, every row retained")
    src.add_argument("--logical-grid",help="Rational JSON: times,strikes,observations (Yahoo F0.exact_grid.json)")
    a.add_argument("--scheme",choices=SCHEMES,default="joint",help="joint: ONE surface for both local schemes")
    a.add_argument("--sigma-min",default="0.05",help="Exact decimal/rational volatility")
    a.add_argument("--sigma-max",default="1.0",help="Exact decimal/rational volatility")
    a.add_argument("--time-level",type=int,choices=range(13),default=0)
    a.add_argument("--space-level",type=int,choices=range(13),default=0)
    a.add_argument("--max-nodes",type=int,default=100000)
    a.add_argument("--threads",type=int,default=4)
    a.add_argument("--time-limit",type=float,default=120)
    a.add_argument("--method",choices=["choose","simplex","ipm"],default="ipm")
    a.set_defaults(func=command)
    a=common("verify-criterion","Rebuild and verify exact-grid proof, without a solver")
    a.add_argument("--problem",required=True)
    a.add_argument("--certificate",required=True)
    src=a.add_mutually_exclusive_group()
    src.add_argument("--quotes")
    src.add_argument("--logical-grid")
    a.add_argument("--max-nodes",type=int,default=100000)
    a.set_defaults(func=verify_command)
