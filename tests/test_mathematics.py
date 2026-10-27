import copy
import json
import numpy as np
import pytest
from scipy import sparse
from dupire_joint.data import Quotes,Grid
from dupire_joint.model import LP,build_lp,audit_lp
from dupire_joint.operators import gamma_matrix,local_variance,conditional_error_bound
from dupire_joint.pricing import black_scholes,discrete_surface,heston_checked,Heston
from dupire_joint.certificates import verify_certificate
from dupire_joint.engine import independent_audit


def test_document_counterexample():
    grid=Grid([.25,1.],[.9,1.,1.1])
    c=black_scholes(grid.times,grid.strikes,.2)
    vf=local_variance(c,grid,"forward")[0][0,0]
    vb=local_variance(c,grid,"backward")[0][0,0]
    assert np.sqrt(vf)==pytest.approx(.16952961,abs=1e-8)
    assert np.sqrt(vb)==pytest.approx(.23323334,abs=1e-8)
    q=Quotes.from_surface(grid.times,grid.strikes,c)
    assert audit_lp(build_lp(grid,q,local=False),c.ravel())["passed"]
    for s in ("forward","backward"):
        assert not audit_lp(build_lp(grid,q,scheme=s),c.ravel())["passed"]


def test_irregular_stencil_and_asymmetry_term():
    x=np.array([.7,.81,1.,1.12,1.4])
    G=gamma_matrix(x)
    np.testing.assert_allclose(G@(x*x),2.,atol=1e-12)
    # A cubic is not second-order exact on an arbitrarily asymmetric mesh.
    expected=6*x[1:-1]+2*(np.diff(x)[1:]-np.diff(x)[:-1])
    np.testing.assert_allclose(G@(x**3),expected,atol=1e-12)


def test_original_observations_survive_grid_changes():
    q=Quotes([.2,.2,.6,.6],[.8,1.,1.,1.3],[.2,.05,.07,.01],[.22,.06,.08,.02])
    digest=q.digest()
    for l in range(4):
        grid=Grid.from_quotes(q,l,l)
        idx=grid.quote_indices(q)
        np.testing.assert_array_equal(np.repeat(grid.times,len(grid.strikes))[idx],q.time)
        np.testing.assert_array_equal(np.tile(grid.strikes,len(grid.times))[idx],q.x)
        assert q.digest()==digest


def test_discrete_generated_backward_witness():
    grid=Grid([.1,.23,.57,1.],[.65,.78,.9,1.,1.11,1.27,1.45])
    c=discrete_surface(grid,.2)
    q=Quotes.from_surface(grid.times,grid.strikes,c,1e-10)
    assert audit_lp(build_lp(grid,q,scheme="backward"),c.ravel())["passed"]
    assert independent_audit(c,grid,q,.18**2,.22**2,"backward")["passed"]
    v,g,theta,good=local_variance(c,grid,"backward")
    np.testing.assert_allclose(v[good],.04,rtol=1e-9,atol=1e-10)


def test_degenerate_cells_are_unidentified_not_zero_vol():
    grid=Grid([.25,1.],[.5,.6,.7])
    c=np.tile(1-grid.strikes,(2,1))
    v,g,t,good=local_variance(c,grid)
    assert not good.any()
    assert np.isnan(v).all()


def test_exact_box_separation_tolerates_a_dual_residual_and_rejects_tampering(tmp_path):
    # x<=.2 and x>=.8, but use slightly unequal multipliers: A.T y != 0.
    lp=LP(sparse.csr_matrix([[1.],[-1.]]),[.2,-.8],[0.],[1.],[0.])
    cert={"lp_sha256":lp.digest(),"rows":[0,1],"multipliers":[1.,1.-1e-12]}
    assert verify_certificate(lp,cert)["verified"]
    path=tmp_path/"model.npz";lp.save(path)
    assert LP.load(path).digest()==lp.digest()
    bad=copy.deepcopy(cert);bad["multipliers"][1]=-1
    assert not verify_certificate(lp,bad)["verified"]
    bad=copy.deepcopy(cert);bad["lp_sha256"]="0"*64
    assert not verify_certificate(lp,bad)["verified"]
    feasible=LP(sparse.csr_matrix([[1.],[-1.]]),[.8,-.2],[0.],[1.],[0.])
    assert not verify_certificate(feasible,{**cert,"lp_sha256":feasible.digest()})["verified"]


def test_conditional_bound_and_nonpositive_gamma_guard():
    a=conditional_error_bound(.1,.1,.2,.7,.1,.5,2.,.03,.08)
    b=conditional_error_bound(.05,.05,.1,.7,.1,.5,2.,.03,.08)
    assert b["variance_error_bound"]<a["variance_error_bound"]
    a=conditional_error_bound(.5,.5,.2,.7,.001,.5,2.,.03,.08)
    assert a["variance_error_bound"] is None


def test_heston_quadrature_and_bs_limit():
    t=[.2,.5,1.];x=[.8,1.,1.2]
    c,quality=heston_checked(t,x,Heston(volvol=.01,rho=0.),nodes=128)
    bs=black_scholes(t,x,.2)
    np.testing.assert_allclose(c,bs,atol=2e-5,rtol=0)
    assert quality["quadrature_error_indicator"]<1e-7
    assert not quality["rigorous_enclosure"]


def test_torch_reference_matches_numpy_cpu():
    pytest.importorskip("torch")
    t=[0.,.1,.5,1.];x=[.6,.9,1.,1.1,1.8]
    np.testing.assert_allclose(black_scholes(t,x,device="torch-cpu"),black_scholes(t,x),atol=1e-14)
    t=[.2,.5];x=[.8,1.,1.2]
    a,_=heston_checked(t,x,nodes=64)
    b,_=heston_checked(t,x,nodes=64,device="torch-cpu")
    np.testing.assert_allclose(a,b,atol=2e-13)


def test_cuda_matches_independent_cpu_if_available():
    torch=pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("No CUDA device on this test host")
    t=[.1,.5,1.];x=[.65,.9,1.,1.1,1.45]
    np.testing.assert_allclose(black_scholes(t,x,device="cuda"),black_scholes(t,x),atol=1e-12)
    a,_=heston_checked(t,x,nodes=64)
    b,_=heston_checked(t,x,nodes=64,device="cuda")
    np.testing.assert_allclose(a,b,atol=1e-10)

