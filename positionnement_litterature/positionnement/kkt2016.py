"""Kundu et al. 2016, equations (18)-(24), in normalized price units.

This implements their fixed-maturity constrained least-squares problem at a
predeclared degree. It does not implement their AIC selection, calendar
coupling, or the different 2023/2024 surface paper. No bid/ask constraint
or local-volatility constraint is added to the published slice problem.
"""
from fractions import Fraction as Q
import time
import numpy as np
from scipy.optimize import minimize,LinearConstraint

from .metrics import direct_check,stringify
from .experiments import reconstruct


def constraints(degree,xmin,xmax):
    n=degree;length=xmax-xmin
    if not isinstance(n,int) or not 2<=n<=20 or not 0<xmin<xmax:
        raise ValueError("Need degree in [2,20] and 0 < xmin < xmax")
    rows=[];rhs=[]
    def add(terms,b):
        row=[Q(0)]*(n+1)
        for k,a in terms:row[k]+=Q(a)
        rows.append(row);rhs.append(Q(b))
    for k in range(n-1):add(((k,1),(k+1,-2),(k+2,1)),0)
    add(((n-1,1),(n,-1)),0)
    add(((0,-1),(1,1)),-length/n)
    add(((n,1),),0)
    add(((0,1),),1-xmin)
    add(((0,-1),),-1)
    return rows,rhs


def check_coefficients(beta,degree,xmin,xmax):
    a,b=constraints(degree,xmin,xmax)
    if len(beta)!=degree+1:raise ValueError("Wrong Bernstein slice degree")
    slacks=[sum((v*x for v,x in zip(row,beta)),Q(0))-rhs for row,rhs in zip(a,b)]
    return {"verified":min(slacks)>=0,"minimum_coefficient_slack":str(min(slacks)),
            "scope":"exact inequalities (18)-(23), normalized r=q=0 and unit forward; fixed maturity"}


def strict_reference(degree,xmin,xmax):
    """A rational strictly feasible quadratic, degree-elevated analytically.

    P(x)=1-e*x+q*x^2 with e=min(1/4,1/(4*xmax)), q=e/(8*xmax).
    All six families of slice inequalities have strict slack on xmin>0.
    """
    length=xmax-xmin;e=min(Q(1,4),1/(4*xmax));q=e/(8*xmax)
    a=1-e*xmin+q*xmin*xmin;b=length*(-e+2*q*xmin);d=q*length*length
    return [a+b*Q(k,degree)+d*Q(k*(k-1),degree*(degree-1)) for k in range(degree+1)]


def recover_coefficients(beta,degree,xmin,xmax,max_change=Q(1,10**9)):
    """Correct only bounded rounding error, never claim exact QP optimality."""
    original=list(map(Q,beta));check=check_coefficients(original,degree,xmin,xmax)
    if check["verified"]:return original,{"applied":False,"max_coefficient_change":"0"}
    reference=strict_reference(degree,xmin,xmax);rows,rhs=constraints(degree,xmin,xmax)
    alpha=Q(0)
    for row,b in zip(rows,rhs):
        s=sum((a*v for a,v in zip(row,original)),Q(0))-b
        r=sum((a*v for a,v in zip(row,reference)),Q(0))-b
        if r<=0:raise ArithmeticError("The explicit interior reference is not strict")
        if s<0:alpha=max(alpha,-s/(r-s))
    alpha=min(Q(1),2*alpha)
    repaired=[(1-alpha)*a+alpha*b for a,b in zip(original,reference)]
    delta=max(abs(a-b) for a,b in zip(original,repaired))
    if delta>max_change:return None,{"applied":False,"reason":"rounding correction exceeds declared budget"}
    if not check_coefficients(repaired,degree,xmin,xmax)["verified"]:
        raise ArithmeticError("Rational slice recovery failed")
    # Partition of unity also bounds the price change by the coefficient change.
    return repaired,{"applied":True,"method":"exact convex mixture with a strict feasible reference",
                     "alpha":str(alpha),"max_coefficient_change":str(delta),
                     "max_price_change_on_domain":str(delta),"allowed_price_change":str(max_change),
                     "optimality_certified":False}


def fit_slices(problem,degree,time_limit=60):
    from dupire_joint.bernstein import basis
    ts,xs=problem.times,problem.strikes;xmin,xmax=xs[0],xs[-1];length=xmax-xmin
    rows,rhs=constraints(degree,xmin,xmax)
    af=np.asarray(rows,dtype=float);bf=np.asarray(rhs,dtype=float)
    fitted=[];coefficients=[];slice_reports=[];started=time.monotonic()
    for t in ts:
        obs=[r for r in problem.observations if r[0]==t]
        if not obs:
            return {"status":"not_applicable","reason":"A published independent-slice fit needs observations at every fitted maturity"},None
        exact_b=[basis(degree,(x-xmin)/length) for _,x,_,_ in obs]
        b=np.asarray(exact_b,dtype=float);mid=np.asarray([float((bid+ask)/2) for _,_,bid,ask in obs])
        def objective(beta):
            if time.monotonic()-started>time_limit:raise TimeoutError("KKT2016 slice fit time limit")
            residual=b@beta-mid
            return float(residual@residual/len(mid))
        def jac(beta):return 2*b.T@(b@beta-mid)/len(mid)
        initial=np.full(degree+1,float(max(1-xmin,Q(0))))
        try:
            solution=minimize(objective,initial,jac=jac,method="SLSQP",bounds=[(0.,1.)]*(degree+1),
                              constraints=[LinearConstraint(af,bf,np.inf)],
                              options={"ftol":1e-13,"maxiter":2000,"disp":False})
        except TimeoutError as exc:return {"status":"time_limit","reason":str(exc)},None
        checked=None;chosen=None;recovery=None
        for candidate in reconstruct(solution.x):
            check=check_coefficients(candidate,degree,xmin,xmax)
            if check["verified"]:chosen=candidate;checked=check;break
        if chosen is None:
            chosen,recovery=recover_coefficients([Q(float(v)) for v in solution.x],degree,xmin,xmax)
            if chosen is not None:checked=check_coefficients(chosen,degree,xmin,xmax)
        if chosen is None:
            return {"status":"numeric_slice_only","maturity":str(t),"solver_success":bool(solution.success),
                    "message":str(solution.message),"exact_reconstruction_failed":True},None
        fitted.extend(sum((v*a for v,a in zip(chosen,basis(degree,(x-xmin)/length))),Q(0)) for x in xs)
        coefficients.append(chosen)
        slice_reports.append({"maturity":str(t),"quotes":len(obs),"solver_success":bool(solution.success),
                              "objective_numeric":float(solution.fun),"exact_shape_check":checked,
                              "rounding_correction":recovery or {"applied":False}})
    record={"status":"slice_shapes_verified_exact","method":"KKTG2016_fixed_degree_slices",
            "implementation":"equation_24_objective_and_18_to_23_constraints_in_normalized_units",
            "source":"KKTG2016","degree":degree,"AIC_selection_implemented":False,
            "hard_bidask":False,"calendar_imposed":False,"local_bounds_imposed":False,
            "objective_optimality_certified_exact":False,"slice_reports":slice_reports,
            "coefficients":stringify(coefficients),"direct_audit":direct_check(problem,fitted),
            "scope":"Published slice formulation at fixed degree; not the paper's full degree-selection experiment or 2024 surface algorithm"}
    return record,fitted
