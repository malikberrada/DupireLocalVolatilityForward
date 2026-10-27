"""Independent rational checks of prices; no matrix residual is reused."""
from dataclasses import replace
from fractions import Fraction as Q
import csv
import hashlib
import json
from pathlib import Path


def stringify(value):
    if isinstance(value,Q):return str(value)
    if isinstance(value,dict):return {k:stringify(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [stringify(v) for v in value]
    return value


def observations_hash(problem):
    data=[[str(v) for v in row] for row in problem.observations]
    return hashlib.sha256(json.dumps(data,separators=(",",":")).encode()).hexdigest()


def direct_check(problem,values):
    ts,xs=problem.times,problem.strikes;nt,nx=problem.shape
    c=list(map(Q,values))
    if len(c)!=nt*nx:raise ValueError("Wrong price-vector length")
    price=lambda j,i:c[j*nx+i]
    minima={};violations={};gammas={};variance={"forward":[],"backward":[]}
    def check(group,slack):
        minima[group]=min(minima.get(group,slack),slack)
        violations[group]=violations.get(group,0)+(slack<0)
    for j in range(nt):
        for i,x in enumerate(xs):
            v=price(j,i);check("price_box",v-max(1-x,Q(0)));check("price_box",1-v)
            if ts[j]==0:check("payoff_T0",-abs(v-max(1-x,Q(0))))
        slopes=[(price(j,i+1)-price(j,i))/(xs[i+1]-xs[i]) for i in range(nx-1)]
        for slope in slopes:check("slope_upper",-slope);check("slope_lower",1+slope)
        check("left_chord",slopes[0]-(price(j,0)-1)/xs[0])
        for i in range(1,nx-1):
            gamma=2*(slopes[i]-slopes[i-1])/(xs[i+1]-xs[i-1])
            gammas[j,i]=gamma;check("convexity",gamma)
    for j in range(nt-1):
        for i in range(nx):check("calendar",price(j+1,i)-price(j,i))
        for scheme in variance:
            row=j if scheme=="forward" else j+1
            for i in range(1,nx-1):
                gamma=gammas[row,i]
                factor=(ts[j+1]-ts[j])*xs[i]**2*gamma/2
                delta=price(j+1,i)-price(j,i)
                check(scheme+"_local_lower",delta-problem.vmin[j][i-1]*factor)
                check(scheme+"_local_upper",problem.vmax[j][i-1]*factor-delta)
                if gamma>0:variance[scheme].append(2*delta/((ts[j+1]-ts[j])*xs[i]**2*gamma))
    tj={v:j for j,v in enumerate(ts)};xi={v:i for i,v in enumerate(xs)}
    for t,x,bid,ask in problem.observations:
        v=price(tj[t],xi[x]);check("bid",v-bid);check("ask",ask-v)
    shape_groups=[k for k in minima if k not in ("bid","ask") and "_local_" not in k]
    return {"passed":all(v>=0 for v in minima.values()),
            "shape_passed":all(minima[k]>=0 for k in shape_groups),
            "quotes_passed":min(minima["bid"],minima["ask"])>=0,
            "minimum_slack":stringify(minima),"violation_counts":violations,
            "minimum_gamma":str(min(gammas.values())),"zero_gamma_nodes":sum(g==0 for g in gammas.values()),
            "variance_ranges":{s:{"min":str(min(v)) if v else None,"max":str(max(v)) if v else None,
                                  "identified_cells":len(v),"cells":(nt-1)*(nx-2)} for s,v in variance.items()},
            "observation_count":len(problem.observations),"observations_sha256":observations_hash(problem),
            "arithmetic":"exact rational on declared coordinates and values"}


def read_external_surface(path,problem):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    values={}
    for row in rows:
        key=Q(row["time"]),Q(row["x"])
        if key in values:raise ValueError("Duplicate external surface node")
        values[key]=Q(row["price"])
    expected={(t,x) for t in problem.times for x in problem.strikes}
    if set(values)!=expected:
        raise ValueError("External surface must retain EXACTLY the declared axes; no implicit regridding")
    return [values[t,x] for t in problem.times for x in problem.strikes]


def polynomial_problem(payload,time_level,space_level):
    from dupire_joint.constructive import base_axes
    from dupire_joint.finite_criterion import Problem,dyadic
    records=[[Q(v) for v in row] for row in payload["observations"]]
    ts,xs=base_axes(records);s=payload["spec"]
    return Problem(dyadic(ts,time_level),dyadic(xs,space_level),[r[:4] for r in records],
                   s["vmin"],s["vmax"],"joint",source={"kind":"constructive_certificate_observations"})


def sample_polynomial(payload,time_level,space_level,max_nodes):
    import numpy as np
    from dupire_joint.bernstein import evaluate
    from dupire_joint.constructive import base_axes
    records=[[Q(v) for v in row] for row in payload["observations"]]
    t,x=base_axes(records)
    shape=((len(t)-1)*2**time_level+1,(len(x)-1)*2**space_level+1)
    if shape[0]*shape[1]>max_nodes:return None,None,list(shape)
    problem=polynomial_problem(payload,time_level,space_level)
    s={k:Q(v) for k,v in payload["spec"].items()}
    c=np.asarray([[Q(v) for v in row] for row in payload["coefficients"]],dtype=object)
    values=[Q(evaluate(c,(t-s["t0"])/(s["t1"]-s["t0"]),(x-s["x0"])/(s["x1"]-s["x0"])))
            for t in problem.times for x in problem.strikes]
    return problem,values,list(shape)


def exact_stencil_errors(payload,problem,values):
    import numpy as np
    from dupire_joint.bernstein import evaluate,derivative
    s={k:Q(v) for k,v in payload["spec"].items()}
    c=np.asarray([[Q(v) for v in row] for row in payload["coefficients"]],dtype=object)
    ct=derivative(c,0,s["t1"]-s["t0"]);cxx=derivative(c,1,s["x1"]-s["x0"],2)
    ts,xs=problem.times,problem.strikes;nt,nx=problem.shape
    v=list(map(Q,values));price=lambda j,i:v[j*nx+i]
    e_gamma=Q(0);e_var={"forward":Q(0),"backward":Q(0)}
    cache={}
    for j in range(nt):
        for i in range(1,nx-1):
            u,w=(ts[j]-s["t0"])/(s["t1"]-s["t0"]),(xs[i]-s["x0"])/(s["x1"]-s["x0"])
            g=2*((price(j,i+1)-price(j,i))/(xs[i+1]-xs[i])-(price(j,i)-price(j,i-1))/(xs[i]-xs[i-1]))/(xs[i+1]-xs[i-1])
            g_cont=Q(evaluate(cxx,u,w));theta_cont=Q(evaluate(ct,u,w))
            e_gamma=max(e_gamma,abs(g-g_cont));cache[j,i]=g,2*theta_cont/(xs[i]**2*g_cont)
    for j in range(nt-1):
        for scheme in e_var:
            row=j if scheme=="forward" else j+1
            for i in range(1,nx-1):
                g,continuous=cache[row,i]
                discrete=2*(price(j+1,i)-price(j,i))/((ts[j+1]-ts[j])*xs[i]**2*g)
                e_var[scheme]=max(e_var[scheme],abs(discrete-continuous))
    return {"gamma_error":str(e_gamma),"variance_error":stringify(e_var)}
