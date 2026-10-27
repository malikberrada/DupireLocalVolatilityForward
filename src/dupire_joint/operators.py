from __future__ import annotations
import numpy as np
from scipy import sparse


def gamma_matrix(x):
    x=np.asarray(x,dtype=float)
    hm,hp=np.diff(x)[:-1],np.diff(x)[1:]
    f=2/(hm+hp)
    return sparse.diags([f/hm,-f*(1/hm+1/hp),f/hp], [0,1,2],
                        shape=(len(x)-2,len(x)),format="csr")


def derivatives(prices, grid):
    """Independent direct stencils, without using the assembled LP matrices."""
    c=np.asarray(prices,dtype=float).reshape(grid.shape)
    h=np.diff(grid.strikes)
    slopes=np.diff(c,axis=1)/h
    gamma=2*np.diff(slopes,axis=1)/(h[:-1]+h[1:])
    theta=np.diff(c,axis=0)[:,1:-1]/np.diff(grid.times)[:,None]
    return slopes,gamma,theta


def local_variance(prices,grid,scheme="forward",gamma_tol=1e-12):
    _,g,theta=derivatives(prices,grid)
    gamma=g[:-1] if scheme=="forward" else g[1:]
    good=gamma>gamma_tol
    v=np.full_like(theta,np.nan)
    np.divide(2*theta,grid.strikes[None,1:-1]**2*gamma,out=v,where=good)
    return v,gamma,theta,good


def conditional_error_bound(hm,hp,dt,xmin,gamma0,M3,M4,Mtt,vmax):
    """Taylor bound conditional on supplied GLOBAL derivative/convexity bounds.

    Eg <= |hp-hm| M3/3 + (hp^3+hm^3) M4/[12(hp+hm)].
    |vh-v| <= (dt Mtt/xmin^2 + vmax Eg)/(gamma0-Eg).
    This does not establish that a continuous admissible surface exists.
    """
    vals=np.array([hm,hp,dt,xmin,gamma0,M3,M4,Mtt,vmax],float)
    if not np.isfinite(vals).all() or np.any(vals[:5]<=0) or np.any(vals[5:]<0):
        raise ValueError("Invalid global bounds or mesh parameters")
    eg=abs(hp-hm)*M3/3+(hp**3+hm**3)*M4/(12*(hp+hm))
    err=(dt*Mtt/xmin**2+vmax*eg)/(gamma0-eg) if gamma0>eg else None
    return {"gamma_error_bound":float(eg),"variance_error_bound":err,
            "positive_denominator":bool(gamma0>eg),"conditional_on_user_bounds":True}

