"""Controlled comparisons, with explicit labels for adaptations of published work."""
from dataclasses import replace
from fractions import Fraction as Q
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from .metrics import direct_check,stringify,observations_hash


def reconstruct(vector):
    if not np.isfinite(vector).all():return
    for den in (10**10,10**12,None):
        yield [Q(float(v)).limit_denominator(den) if den else Q(float(v)) for v in vector]


def weak_polynomial_check(c,spec,records):
    from dupire_joint.bernstein import residual_polynomials,derivative
    from dupire_joint.constructive import observation_forms,exact_check
    c=np.asarray(c,dtype=object)
    forms=[(name,array) for name,array in residual_polynomials(c,spec) if not name.startswith("local_")]
    minima={name:min(Q(v) for v in block.flat) for name,block in forms}
    minima["calendar"]=min(derivative(c,0,spec["t1"]-spec["t0"]).flat)
    minima["quotes"]=min(Q(v) for v in observation_forms(c,spec,records))
    full=exact_check(c,spec,records)
    return {"shape_quotes_gamma_floor_verified":all(v>=0 for v in minima.values()),
            "full_constructive_condition_verified":full["passed"],"minimum_slack":stringify(minima),
            "local_coefficient_minima":stringify({k:v for k,v in full["minima"].items() if k.startswith("local_")})}


def bernstein_ablation(payload,session,out):
    from dupire_joint.bernstein import derivative
    from dupire_joint.constructive import build_coefficient_lp
    from dupire_joint.model import LP
    from dupire_joint.progress import atomic_json
    spec={k:Q(v) for k,v in payload["spec"].items()}
    records=[[Q(v) for v in row] for row in payload["observations"]]
    degree=(len(payload["coefficients"])-1,len(payload["coefficients"][0])-1)
    base=build_coefficient_lp(spec,degree,records)
    keep=np.ones(len(base.b),dtype=bool)
    for group in ("local_lower","local_upper"):
        a,b=base.groups[group];keep[a:b]=False
    ncoef=len(base.cost)-1
    affine=np.zeros((ncoef,ncoef+1),dtype=object);affine[:,:ncoef]=np.eye(ncoef,dtype=object)
    affine=affine.reshape(degree[0]+1,degree[1]+1,ncoef+1)
    theta=derivative(affine,0,spec["t1"]-spec["t0"])
    rows=[];rhs=[]
    for row in theta.reshape(-1,ncoef+1):
        scale=max(Q(1),abs(row[-1]),sum(abs(v) for v in row[:-1]))
        rows.append([-float(v/scale) for v in row[:-1]]+[1.])
        rhs.append(float(row[-1]/scale))
    lp=LP(sparse.vstack([base.A[keep],sparse.csr_matrix(rows)]),np.r_[base.b[keep],rhs],
          base.lower,base.upper,base.cost)
    result=session.solve(lp,"Bernstein ablation / keep quotes and shape, remove local bounds")
    record={"method":"bernstein_shape_ablation","implementation":"controlled_ablation_not_paper_reproduction",
            "related_sources":["KKTG2016","KKT2024"],"solver_status":result["status"],
            "local_bounds_imposed":False,"calendar_and_gamma_floor_imposed":True,"status":"not_certified"}
    if result.get("x") is not None:
        for candidate in reconstruct(result["x"][:-1]):
            c=np.asarray(candidate,dtype=object).reshape(degree[0]+1,degree[1]+1)
            check=weak_polynomial_check(c,spec,records)
            if check["shape_quotes_gamma_floor_verified"]:
                record.update(status="shape_certified_exact",verification=check)
                atomic_json(out/"bernstein_shape_ablation.witness.json",
                            {"format":"bernstein-shape-ablation-v1","spec":stringify(spec),
                             "observations":stringify(records),"coefficients":stringify(c.tolist()),
                             "verification":check,"not_a_full_constructive_certificate":not check["full_constructive_condition_verified"]})
                break
    return record


def crw_cost(epsilon,half_spread,delta0):
    e,h,d=Q(epsilon),Q(half_spread),Q(delta0)
    if not 0<d<=h:raise ValueError("CRW midpoint objective needs 0 < delta0 <= half-spread")
    return max(-e-h+d,-d*e/h,d*e/h,e-h+d)


def adapted_crw_lp(problem):
    from dupire_joint.finite_criterion import ExactSystem
    from dupire_joint.model import LP
    half=[(a-b)/2 for _,_,b,a in problem.observations]
    if min(half)<=0:raise ValueError("CRW bid/ask objective requires strictly positive spreads")
    # The paper's equation (8), with midpoint references:
    delta0=min(Q(1,len(half)),min(half))
    system=ExactSystem(replace(problem,scheme="none"))
    # This is an adaptation: the original paper's global arbitrage constraints
    # are replaced by the project's finite-window F0 shape constraints.
    system.rows=[r for r in system.rows if r[0] not in ("bid","ask")]
    base,_=system.oracle();n=system.n;nq=len(half)
    a=sparse.hstack([base.A,sparse.csr_matrix((len(base.b),nq))],format="csr")
    rr=[];cc=[];vv=[];bs=[];upper=[]
    tj={t:j for j,t in enumerate(problem.times)};xi={x:i for i,x in enumerate(problem.strikes)}
    for q,(t,x,bid,ask) in enumerate(problem.observations):
        k=tj[t]*len(xi)+xi[x];m=(bid+ask)/2;h=half[q]
        affine=[(-Q(1),-h+delta0),(-delta0/h,Q(0)),(delta0/h,Q(0)),(Q(1),-h+delta0)]
        upper.append(float(max(crw_cost(system.lower[k]-m,h,delta0),crw_cost(system.upper[k]-m,h,delta0))+1))
        for slope,offset in affine:
            row=len(bs);rr.extend((row,row));cc.extend((k,n+q));vv.extend((float(slope),-1.))
            bs.append(float(slope*m-offset))
    epigraph=sparse.csr_matrix((vv,(rr,cc)),shape=(len(bs),n+nq))
    lp=LP(sparse.vstack([a,epigraph]),np.r_[base.b,bs],np.r_[base.lower,np.zeros(nq)],
          np.r_[base.upper,upper],np.r_[np.zeros(n),np.ones(nq)],nprice=n)
    return lp,delta0


def crw_comparison(problem,session,out):
    from dupire_joint.progress import atomic_json
    record={"method":"crw_objective_on_window_F0","related_sources":["CRW2020"],
            "implementation":"published_four_affine_objective_with_adapted_constraints",
            "hard_bidask":False,"local_bounds_imposed":False,
            "scientific_comparison":"different_feasible_set; audit only, no dominance conclusion"}
    try:lp,delta0=adapted_crw_lp(problem)
    except ValueError as exc:return {**record,"status":"not_applicable","reason":str(exc)}
    result=session.solve(lp,"CRW objective / adapted finite-window shape constraints")
    record.update(solver_status=result["status"],objective_numeric=result.get("objective"),
                  delta0=str(delta0),optimality_certified_exact=False,status="no_witness")
    if result.get("x") is not None:
        from dupire_joint.model import audit_lp
        record["numeric_lp_audit"]=audit_lp(lp,result["x"],1e-8)
        record["numeric_lp_audit"]["semantics"]="absolute residuals of the rounded, row-normalized adaptation LP; not an exact rational proof"
        record["status"]="numeric_witness_only"
        last=None
        for values in reconstruct(result["x"][:lp.nprice]):
            check=direct_check(problem,values);last=(values,check)
            if check["shape_passed"]:
                record.update(status="shape_witness_verified_exact",verification=check)
                break
        if last:
            values,check=last
            atomic_json(out/"crw_adapted.witness.json",{"prices":list(map(str,values)),"verification":check,
                        "problem_sha256":problem.digest(),"objective_optimality_proved":False,
                        "status":record["status"]})
            record.setdefault("verification",check)
    return record


def nodal_comparison(payload,levels,session,out,max_nodes):
    from dupire_joint.finite_criterion import search
    from dupire_joint.constructive import base_axes
    from .metrics import polynomial_problem
    records=[[Q(v) for v in row] for row in payload["observations"]]
    ts,xs=base_axes(records);runs=[]
    for level in levels:
        shape=[(len(ts)-1)*2**level+1,(len(xs)-1)*2**level+1]
        if shape[0]*shape[1]>max_nodes:
            runs.append({"level":level,"shape":shape,"conclusion":"not_run_node_budget"});continue
        problem=polynomial_problem(payload,level,level)
        folder=out/f"nodal_level_{level:02d}";folder.mkdir(parents=True,exist_ok=True)
        result=search(problem,session,folder,"joint",max_nodes)
        result.update(level=level,shape=shape,observations_sha256=observations_hash(problem),
                      method="project_nodal_LP",implementation="common_grid_adaptation_not_full_BR2016")
        runs.append(result)
    return runs
