"""Exact rational verification of a separating inequality for the binary64 LP.

For any y>=0, A x<=b implies r.x<=d, r=A.T y and d=b.T y.
Over the variable box, r.x >= sum_j min(r_j*l_j,r_j*u_j).
If that exact lower bound exceeds d, infeasibility is proved. This remains
valid with a nonzero dual residual, unlike a tolerance-only Farkas check.
"""
from __future__ import annotations
from fractions import Fraction
import json
from pathlib import Path
import numpy as np
from scipy import sparse
from .model import LP


def _fraction(x):
    return Fraction.from_float(float(x))


def verify_certificate(lp,certificate):
    if certificate.get("lp_sha256")!=lp.digest():
        return {"verified":False,"reason":"LP hash mismatch"}
    if not np.isfinite(lp.lower).all() or not np.isfinite(lp.upper).all():
        return {"verified":False,"reason":"This verifier requires a finite variable box"}
    rows=certificate.get("rows",[]);values=certificate.get("multipliers",[])
    if not rows or len(rows)!=len(values) or len(set(rows))!=len(rows):
        return {"verified":False,"reason":"Invalid multiplier support"}
    r={};d=Fraction(0)
    try:
        for row,v in zip(rows,values):
            if not isinstance(row,int) or not 0<=row<lp.A.shape[0]:
                raise ValueError("Invalid row index")
            if not np.isfinite(float(v)) or float(v)<0:
                raise ValueError("Multipliers must be finite and nonnegative")
            y=_fraction(v)
            d+=y*_fraction(lp.b[row])
            for k in range(lp.A.indptr[row],lp.A.indptr[row+1]):
                col=int(lp.A.indices[k])
                r[col]=r.get(col,Fraction(0))+y*_fraction(lp.A.data[k])
        lower=sum((v*_fraction(lp.lower[j] if v>=0 else lp.upper[j]) for j,v in r.items()),Fraction(0))
        margin=lower-d
        return {"verified":margin>0,"exact_margin_numerator":str(margin.numerator),
                "exact_margin_denominator":str(margin.denominator),"margin_approx":float(margin),
                "support_size":len(rows),"scope":"exact rational arithmetic on saved binary64 coefficients and bounds"}
    except (TypeError,ValueError,OverflowError) as e:
        return {"verified":False,"reason":str(e)}


def _candidate(lp,y):
    y=np.maximum(np.asarray(y,dtype=float),0)
    if not np.isfinite(y).all() or len(y)!=lp.A.shape[0] or np.max(y,initial=0)==0:
        return None
    y=y/np.max(y)
    rows=np.flatnonzero(y>0)
    cert={"format":"dupire-joint-box-separation-v1","lp_sha256":lp.digest(),
          "rows":rows.tolist(),"multipliers":y[rows].tolist()}
    cert["verification"]=verify_certificate(lp,cert)
    return cert if cert["verification"]["verified"] else None


def find_certificate(lp,result,session,label="certificate"):
    if result.get("ray") is not None:
        for sign in (-1,1):
            cert=_candidate(lp,sign*result["ray"])
            if cert:
                cert["source"]="HiGHS dual ray, corrected by the exact variable box"
                return cert
    # Auxiliary normalized Farkas LP, only if the native dual ray did not verify.
    A,b,scale=lp.scaled();n=A.shape[1];m=A.shape[0]
    if not np.isfinite(lp.lower).all() or not np.isfinite(lp.upper).all():
        return None
    M=sparse.vstack([A,sparse.eye(n),-sparse.eye(n)],format="csr")
    rhs=np.r_[b,lp.upper,-lp.lower]
    k=M.shape[0]
    ones=sparse.csr_matrix(np.ones((1,k)))
    eq=sparse.vstack([M.T,-M.T,ones,-ones],format="csr")
    aux=LP(eq,np.r_[np.zeros(2*n),1.,-1.],np.zeros(k),np.ones(k),rhs)
    sol=session.solve(aux,label+" / dual auxiliary LP")
    if sol["status"]=="optimal" and sol["x"] is not None:
        cert=_candidate(lp,sol["x"][:m]/scale)
        if cert:
            cert["source"]="Auxiliary Farkas LP, corrected by the exact variable box"
            return cert
    return None

