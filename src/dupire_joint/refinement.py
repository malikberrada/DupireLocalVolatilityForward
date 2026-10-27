"""Exact, explicit quadratic refinement criterion from Theorem 2.

No optimization and no floating-point square root enter this calculation.
Constants must come from a globally certified surface, e.g. Bernstein.
"""
from fractions import Fraction as Q


def quadratic_parameters(constants,spec,geometry):
    gamma=constants["gamma0"]
    m3,m4,mtt=(constants[k] for k in ("M3","M4","Mtt"))
    delta,vmax,xmin=spec["buffer"],spec["vmax"],spec["x0"]
    if gamma<=0 or delta<=0 or vmax<=delta or xmin<=0 or min(m3,m4,mtt)<0:
        raise ValueError("The quadratic guarantee needs gamma0>0, vmax>delta>0, xmin>0 and nonnegative derivative bounds")
    if min(geometry["dt"],geometry["h"])<=0 or geometry["asymmetry"]<0:
        raise ValueError("Invalid base-grid geometry")
    a=m3*geometry["asymmetry"]/3
    b=m4*geometry["h"]**2/12
    d=geometry["dt"]*mtt/xmin**2
    A=d+(vmax+delta)*a
    B=(vmax+delta)*b
    C=delta*gamma
    # For r>=1, Ar+B <= (A+B)r. This supplies a finite exact upper
    # bound for the required level even when the bounded search stops early.
    ratio=(A+B)/C
    r_upper=max(1,-(-ratio.numerator//ratio.denominator))
    level_upper=(r_upper-1).bit_length()
    return {"a":a,"b":b,"d":d,"A":A,"B":B,"C":C,
            "discriminant":A*A+4*B*C,"level_upper_bound":level_upper,
            "root_formula":"(A + sqrt(A^2 + 4*B*C))/(2*C)",
            "condition":"C*r^2 - A*r - B >= 0, r=2^level"}


def quadratic_trial(parameters,constants,spec,level):
    if not isinstance(level,int) or level<0:
        raise ValueError("Level must be a nonnegative integer")
    r=2**level
    p=parameters
    gap=p["C"]*r*r-p["A"]*r-p["B"]
    error=p["a"]/r+p["b"]/(r*r)
    denominator=constants["gamma0"]-error
    variance_error=(p["d"]/r+spec["vmax"]*error)/denominator if denominator>0 else None
    passed=gap>=0
    if passed != (variance_error is not None and variance_error<=spec["buffer"]):
        raise ArithmeticError("Quadratic criterion and original error bound disagree")
    return {"level":level,"r":r,"Egamma":str(error),
            "Evariance":str(variance_error) if variance_error is not None else None,
            "quadratic_margin":str(gap),"passed":passed}
