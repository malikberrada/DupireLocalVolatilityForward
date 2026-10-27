"""Vectorized CPU/CUDA FP64 references. No compiler, nvcc, CMake or torch.compile."""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from scipy.special import ndtr, roots_legendre


def select_device(request="auto",size=0,threshold=100_000):
    if request not in ("auto","cpu","cuda","torch-cpu"):
        raise ValueError("Device must be auto, cpu, cuda or torch-cpu")
    if request=="cpu":
        return "cpu"
    if request=="auto" and size<threshold:
        return "cpu"
    try:
        import torch
    except ImportError:
        if request in ("cuda","torch-cpu"):
            raise RuntimeError("Install PyTorch wheels to use the requested device") from None
        return "cpu"
    if request=="torch-cpu":
        return "torch-cpu"
    available=torch.cuda.is_available()
    if request=="cuda" and not available:
        raise RuntimeError("CUDA explicitly requested, but PyTorch cannot access a CUDA GPU")
    return "cuda" if available and (request=="cuda" or size>=threshold) else "cpu"


def _torch_device(device):
    return "cpu" if device=="torch-cpu" else device


def black_scholes(times,strikes,sigma=.2,device="cpu"):
    """Normalized call F=D=1; shape (n_times,n_strikes)."""
    t=np.asarray(times,float).reshape(-1,1)
    x=np.asarray(strikes,float).reshape(1,-1)
    if not np.isfinite(t).all() or not np.isfinite(x).all() or np.any(t<0) or np.any(x<=0) or not np.isfinite(sigma) or sigma<0:
        raise ValueError("BS requires finite T>=0, x>0, sigma>=0")
    dev=select_device(device,t.size*x.size)
    if sigma==0:
        return np.broadcast_to(np.maximum(1-x,0),(len(t),x.size)).copy()
    if dev=="cpu":
        s=sigma*np.sqrt(np.maximum(t,np.finfo(float).tiny))
        d1=-np.log(x)/s+s/2;d2=d1-s
        c=ndtr(d1)-x*ndtr(d2)
        return np.where(t==0,np.maximum(1-x,0),c)
    import torch
    with torch.inference_mode():
        tt=torch.as_tensor(t,dtype=torch.float64,device=_torch_device(dev))
        xx=torch.as_tensor(x,dtype=torch.float64,device=_torch_device(dev))
        s=sigma*torch.sqrt(torch.clamp(tt,min=np.finfo(float).tiny))
        d1=-torch.log(xx)/s+s/2;d2=d1-s
        c=torch.special.ndtr(d1)-xx*torch.special.ndtr(d2)
        c=torch.where(tt==0,torch.clamp(1-xx,min=0),c)
        return c.cpu().numpy()


@dataclass(frozen=True)
class Heston:
    kappa: float = 2.0
    theta: float = .04
    volvol: float = .4
    rho: float = -.7
    v0: float = .04

    def validate(self):
        a=np.array([self.kappa,self.theta,self.volvol,self.rho,self.v0])
        if not np.isfinite(a).all() or min(self.kappa,self.theta,self.volvol,self.v0)<=0 or not abs(self.rho)<1:
            raise ValueError("Require positive Heston parameters and -1<rho<1")


@lru_cache(maxsize=24)
def _legendre(nodes):
    # Reuse C/Fortran-backed quadrature setup across surfaces and maturities.
    return roots_legendre(nodes)


def heston_calls(times,strikes,params=Heston(),nodes=256,cutoff=160.,device="cpu",progress=None):
    """Little-trap characteristic function and Gauss-Legendre quadrature.

    Deterministic quadrature is NOT a rigorous pricing enclosure. Use
    heston_checked to compare both node count and integration cutoff.
    """
    params.validate()
    if nodes<32 or cutoff<=0 or not np.isfinite(cutoff):
        raise ValueError("nodes>=32 and finite cutoff>0 required")
    t=np.asarray(times,float);x=np.asarray(strikes,float)
    if t.ndim!=1 or x.ndim!=1 or np.any(t<=0) or np.any(x<=0) or not np.isfinite(t).all() or not np.isfinite(x).all():
        raise ValueError("Heston reference requires T>0 and x>0")
    dev=select_device(device,len(t)*len(x)*nodes)
    if dev!="cpu":
        import torch
        xp=torch
        target=_torch_device(dev)
        arr=lambda a,dtype=None: torch.as_tensor(a,dtype=dtype or torch.float64,device=target)
        exp,log,sqrt=xp.exp,xp.log,xp.sqrt
    else:
        xp=np
        arr=lambda a,dtype=None: np.asarray(a,dtype=dtype or np.float64)
        exp,log,sqrt=np.exp,np.log,np.sqrt
    u,w=_legendre(nodes)
    u=arr((u+1)*cutoff/2);w=arr(w*cutoff/2)
    xx=arr(x)
    p=params
    def phi(z,T):
        a=p.kappa-p.rho*p.volvol*1j*z
        d=sqrt(a*a+p.volvol**2*(z*z+1j*z))
        g=(a-d)/(a+d)
        e=exp(-d*T)
        C=p.kappa*p.theta/p.volvol**2*((a-d)*T-2*log((1-g*e)/(1-g)))
        D=(a-d)/p.volvol**2*((1-e)/(1-g*e))
        return exp(C+D*p.v0)
    result=np.empty((len(t),len(x)))
    iterator=progress.bar(enumerate(t),total=len(t),desc="Heston maturities") if progress else enumerate(t)
    for j,T in iterator:
        f1=phi(u-1j,float(T));f2=phi(u,float(T))
        # Chunk strikes: bounded GPU memory, including complex128 intermediates.
        for start in range(0,len(x),256):
            end=min(start+256,len(x))
            phase=exp(-1j*log(xx[start:end,None])*u[None,:])/(1j*u[None,:])
            P1=.5+((phase*f1).real*w).sum(axis=1)/math.pi
            P2=.5+((phase*f2).real*w).sum(axis=1)/math.pi
            c=P1-xx[start:end]*P2
            result[j,start:end]=c.cpu().numpy() if dev!="cpu" else c
        if progress:
            progress.event("Heston quadrature",completed=j+1,total=len(t),device=dev,nodes=nodes,cutoff=cutoff)
    if not np.isfinite(result).all():
        raise ArithmeticError("Nonfinite Heston reference; choose another quadrature/domain")
    return result


def heston_checked(times,strikes,params=Heston(),nodes=256,cutoff=160.,device="cpu",tolerance=1e-7,progress=None):
    a=heston_calls(times,strikes,params,nodes,cutoff,device,progress)
    b=heston_calls(times,strikes,params,2*nodes,cutoff,device,progress)
    c=heston_calls(times,strikes,params,4*nodes,2*cutoff,device,progress)
    error=float(max(np.max(abs(a-b)),np.max(abs(b-c))))
    if error>tolerance:
        raise ArithmeticError(f"Heston quadrature disagreement {error:.3g} > {tolerance}; increase --heston-nodes")
    return c,{"quadrature_error_indicator":error,"tolerance":tolerance,"rigorous_enclosure":False,
              "nodes_final":4*nodes,"cutoff_final":2*cutoff}


def discrete_surface(grid,sigma=.2,initial_sigma=.2):
    """A feasible backward stencil witness, generated with a tridiagonal solve.

    Endpoint prices are held constant across time. This is a finite-domain
    numerical fixture, not a claim about a global Black-Scholes diffusion.
    """
    from scipy.linalg import solve_banded
    from .operators import gamma_matrix
    nt,nx=grid.shape
    c=np.zeros(grid.shape)
    c[0]=black_scholes([grid.times[0]],grid.strikes,initial_sigma)[0]
    G=gamma_matrix(grid.strikes)
    for j,dt in enumerate(np.diff(grid.times)):
        coef=.5*sigma**2*dt*grid.strikes[1:-1]**2
        lower=-coef*G.diagonal(0)
        main=1-coef*G.diagonal(1)
        upper=-coef*G.diagonal(2)
        band=np.zeros((3,nx-2))
        band[0,1:]=upper[:-1];band[1]=main;band[2,:-1]=lower[1:]
        rhs=c[j,1:-1].copy()
        rhs[0]-=lower[0]*c[0,0];rhs[-1]-=upper[-1]*c[0,-1]
        c[j+1,0]=c[0,0];c[j+1,-1]=c[0,-1]
        c[j+1,1:-1]=solve_banded((1,1),band,rhs)
    return c
