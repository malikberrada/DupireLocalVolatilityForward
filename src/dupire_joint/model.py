from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy import sparse
from .operators import gamma_matrix


@dataclass
class LP:
    A: sparse.csr_matrix
    b: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    cost: np.ndarray
    groups: dict = field(default_factory=dict)
    nprice: int = 0

    def __post_init__(self):
        self.A = sparse.csr_matrix(self.A,dtype=float)
        self.A.sum_duplicates()
        self.A.eliminate_zeros()
        self.A.sort_indices()
        for name in ("b","lower","upper","cost"):
            setattr(self,name,np.asarray(getattr(self,name),dtype=float))
        m,n=self.A.shape
        if self.b.shape!=(m,) or any(getattr(self,k).shape!=(n,) for k in ("lower","upper","cost")):
            raise ValueError("Malformed LP dimensions")
        if not np.isfinite(self.A.data).all() or not np.isfinite(self.b).all() or not np.isfinite(self.cost).all():
            raise ValueError("Nonfinite coefficients")
        if np.isnan(self.lower).any() or np.isnan(self.upper).any() or np.any(self.lower>self.upper):
            raise ValueError("Invalid variable bounds")

    def digest(self):
        h=hashlib.sha256()
        h.update(np.asarray(self.A.shape,dtype="<i8").tobytes())
        for a,dtype in ((self.A.indptr,"<i8"),(self.A.indices,"<i8"),(self.A.data,"<f8"),
                        (self.b,"<f8"),(self.lower,"<f8"),(self.upper,"<f8"),(self.cost,"<f8")):
            h.update(np.asarray(a,dtype=dtype).tobytes())
        return h.hexdigest()

    def save(self,path):
        np.savez_compressed(path,data=self.A.data,indices=self.A.indices,indptr=self.A.indptr,
                            shape=self.A.shape,b=self.b,lower=self.lower,upper=self.upper,
                            cost=self.cost,nprice=self.nprice,groups=json.dumps(self.groups))

    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as d:
            return cls(sparse.csr_matrix((d['data'],d['indices'],d['indptr']),shape=tuple(d['shape'])),
                       d['b'],d['lower'],d['upper'],d['cost'],json.loads(str(d['groups'])),int(d['nprice']))

    def scaled(self):
        scale=np.asarray(abs(self.A).max(axis=1).toarray()).ravel()
        scale=np.maximum(scale,1e-30)
        return sparse.diags(1/scale,format="csr")@self.A,self.b/scale,scale


def build_lp(grid,quotes,vmin=0.18**2,vmax=0.22**2,scheme="forward",local=True,
             epsilon=False,variance_slack=0.0,max_variables=2_000_000):
    nt,nx=grid.shape
    n=nt*nx
    if n>max_variables:
        raise ValueError(f"Grid has {n:,} price variables; limit {max_variables:,}")
    if scheme not in ("forward","backward"):
        raise ValueError("Unknown scheme")
    if not np.isfinite(variance_slack) or variance_slack<0:
        raise ValueError("Variance relaxation must be finite and nonnegative")
    shape=(nt-1,nx-2)
    vlo=np.broadcast_to(np.asarray(vmin,dtype=float),shape)
    vhi=np.broadcast_to(np.asarray(vmax,dtype=float),shape)
    if not np.isfinite(vlo).all() or not np.isfinite(vhi).all() or np.any(vlo<0) or np.any(vhi<vlo):
        raise ValueError("Require finite 0 <= vmin <= vmax in every interior cell")
    lo=np.maximum(vlo-variance_slack,0).ravel()
    hi=(vhi+variance_slack).ravel()
    blocks=[];rhs=[];groups={};cursor=0
    def add(name,a,b):
        nonlocal cursor
        a=sparse.csr_matrix(a)
        b=np.broadcast_to(b,(a.shape[0],)).copy()
        blocks.append(a);rhs.append(b)
        groups[name]=[cursor,cursor+a.shape[0]]
        cursor+=a.shape[0]
    # Each row has O(1) entries. No dense grid-sized square arrays.
    D=sparse.diags([-np.ones(nx-1),np.ones(nx-1)],[0,1],shape=(nx-1,nx),format="csr")
    G=gamma_matrix(grid.strikes)
    add("slope_upper",sparse.kron(sparse.eye(nt),D,format="csr"),0)
    add("slope_lower",-sparse.kron(sparse.eye(nt),D,format="csr"),np.tile(np.diff(grid.strikes),nt))
    add("convexity",-sparse.kron(sparse.eye(nt),G,format="csr"),0)
    # Convex connection to c(T,0)=1, without imposing a spurious zero right wing.
    h=grid.strikes[1]-grid.strikes[0]; x0=grid.strikes[0]
    left=sparse.csr_matrix(([1/h+1/x0,-1/h],([0,0],[0,1])),shape=(1,nx))
    add("left_chord",sparse.kron(sparse.eye(nt),left,format="csr"),1/x0)
    E0=sparse.eye(nt-1,nt,k=0,format="csr")
    E1=sparse.eye(nt-1,nt,k=1,format="csr")
    calendar=sparse.kron(E1-E0,sparse.eye(nx),format="csr")
    add("calendar",-calendar,0)
    if local:
        inner=sparse.eye(nx-2,nx,k=1,format="csr")
        delta=sparse.kron(E1-E0,inner,format="csr")
        gs=sparse.kron(E0 if scheme=="forward" else E1,G,format="csr")
        fac=(np.diff(grid.times)[:,None]*grid.strikes[None,1:-1]**2/2).ravel()
        add("local_lower",sparse.diags(fac*lo)@gs-delta,0)
        add("local_upper",delta-sparse.diags(fac*hi)@gs,0)
    indices=grid.quote_indices(quotes)
    nq=len(indices)
    Q=sparse.csr_matrix((np.ones(nq),(np.arange(nq),indices)),shape=(nq,n))
    add("ask",Q,quotes.ask)
    add("bid",-Q,-quotes.bid)
    A=sparse.vstack(blocks,format="csr")
    b=np.concatenate(rhs)
    lower=np.tile(np.maximum(1-grid.strikes,0),nt)
    upper=np.ones(n)
    if grid.times[0]==0:
        upper[:nx]=lower[:nx]
    if grid.tail_x is not None:
        lower[nx-1::nx]=0
        upper[nx-1::nx]=0
    cost=np.zeros(n)
    if epsilon:
        slack=np.zeros(A.shape[0])
        for k in ("bid","ask"):
            a,z=groups[k];slack[a:z]=-quotes.weight
        A=sparse.hstack([A,sparse.csr_matrix(slack[:,None])],format="csr")
        lower=np.r_[lower,0.0];upper=np.r_[upper,np.inf];cost=np.r_[cost,1.0]
    return LP(A,b,lower,upper,cost,groups,n)


def audit_lp(lp,solution,tolerance=1e-8):
    x=np.asarray(solution,dtype=float)
    if x.shape!=lp.cost.shape or not np.isfinite(x).all():
        return {"passed":False,"error":"Nonfinite or wrongly shaped witness"}
    residual=lp.A@x-lp.b
    violations={k:float(max(0,np.max(residual[a:b],initial=0))) for k,(a,b) in lp.groups.items()}
    bound=float(max(0,np.max(lp.lower-x,initial=0),np.max(x-lp.upper,initial=0)))
    worst=float(max(0,np.max(residual,initial=0),bound))
    return {"passed":worst<=tolerance,"max_violation":worst,"bound_violation":bound,
            "groups":violations,"tolerance":tolerance,"semantics":"absolute residuals of unscaled binary64 LP"}
