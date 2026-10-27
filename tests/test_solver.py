import json
import numpy as np
import pytest
from scipy import sparse
from dupire_joint.data import Quotes,Grid
from dupire_joint.model import LP,build_lp,audit_lp
from dupire_joint.pricing import black_scholes,discrete_surface
from dupire_joint.solver import SolverSession,SolverOptions
from dupire_joint.certificates import find_certificate,verify_certificate
from dupire_joint.engine import run_grid,variance_relaxation
from dupire_joint.progress import Progress


@pytest.fixture(scope="module")
def session():
    with SolverSession(SolverOptions(threads=2,time_limit=30)) as s:
        yield s


def test_joint_counterexample_infeasible_with_exact_saved_proof(session):
    grid=Grid([.25,1.],[.9,1.,1.1]);c=black_scholes(grid.times,grid.strikes)
    q=Quotes.from_surface(grid.times,grid.strikes,c)
    f0=build_lp(grid,q,local=False)
    r=session.solve(f0)
    assert r["status"]=="optimal" and audit_lp(f0,r["x"])["passed"]
    for scheme in ("forward","backward"):
        lp=build_lp(grid,q,scheme=scheme);r=session.solve(lp)
        assert r["status"]=="infeasible"
        cert=find_certificate(lp,r,session)
        assert cert is not None and verify_certificate(lp,cert)["verified"]


def test_crossed_quote_infeasibility_is_not_a_local_variance_claim(session):
    grid=Grid([.25,1.],[.9,1.,1.1]);c=black_scholes(grid.times,grid.strikes)
    q=Quotes.from_surface(grid.times,grid.strikes,c,.001)
    q.bid[0]=q.ask[0]+.01
    lp=build_lp(grid,q,local=False);r=session.solve(lp)
    assert r["status"]=="infeasible"
    assert verify_certificate(lp,find_certificate(lp,r,session))["verified"]


def test_minimum_quote_widening_lp_and_variance_bisection(session):
    grid=Grid([.25,1.],[.9,1.,1.1]);c=black_scholes(grid.times,grid.strikes)
    q=Quotes.from_surface(grid.times,grid.strikes,c)
    lp=build_lp(grid,q,scheme="forward",epsilon=True)
    r=session.solve(lp)
    assert r["status"]=="optimal" and r["x"][-1]>0
    assert audit_lp(lp,r["x"])["passed"]
    relax=variance_relaxation(grid,q,.18**2,.22**2,"forward",session,steps=18)
    exact_gap=.18**2-float(__import__('dupire_joint.operators',fromlist=['local_variance']).local_variance(c,grid)[0][0,0])
    lo,hi=relax["bracket"]
    # The feasibility tolerance produces a small numerical threshold uncertainty.
    assert lo-1e-7<=exact_gap<=hi+1e-7
    assert hi-lo<3e-7


def test_feasible_by_construction(session):
    grid=Grid([.1,.25,.5,1.],np.linspace(.65,1.45,13))
    c=discrete_surface(grid)
    q=Quotes.from_surface(grid.times,grid.strikes,c,1e-6)
    lp=build_lp(grid,q,scheme="backward");r=session.solve(lp)
    assert r["status"]=="optimal" and audit_lp(lp,r["x"])["passed"]


def test_full_report_resume_and_artifact_tampering(session,tmp_path):
    grid=Grid([.25,1.],[.9,1.,1.1]);c=black_scholes(grid.times,grid.strikes)
    q=Quotes.from_surface(grid.times,grid.strikes,c)
    r=run_grid(grid,q,session,tmp_path,relax=False)
    assert r["F0"]["conclusion"]=="feasible_numeric"
    assert r["variants"]["forward"]["conclusion"]=="infeasible_certified_binary_lp"
    same=run_grid(grid,q,session,tmp_path,relax=False,resume=True)
    assert same["fingerprint"]==r["fingerprint"]
    (tmp_path/"observations.csv").write_text("tampered",encoding="utf-8")
    with pytest.raises(ValueError,match="Checkpoint differs"):
        run_grid(grid,q,session,tmp_path,relax=False,resume=True)


def test_worker_is_closed_even_after_exception():
    s=SolverSession(SolverOptions(threads=1))
    with pytest.raises(RuntimeError):
        with s:
            proc=s.process
            raise RuntimeError("controlled")
    assert not proc.is_alive()


def test_incomplete_grid_is_recomputed_on_resume(session,tmp_path):
    grid=Grid([.25,1.],[.9,1.,1.1]);c=black_scholes(grid.times,grid.strikes)
    q=Quotes.from_surface(grid.times,grid.strikes,c)
    r=run_grid(grid,q,session,tmp_path,relax=False)
    # Simulate an interrupted grid after its fingerprint was written.
    (tmp_path/"report.json").write_text(json.dumps({"fingerprint":r["fingerprint"],"complete":False}))
    restored=run_grid(grid,q,session,tmp_path,relax=False,resume=True)
    assert restored["complete"]
    assert restored["variants"]["forward"]["conclusion"]=="infeasible_certified_binary_lp"


def test_quiet_solver_still_has_live_status(tmp_path):
    p=Progress(tmp_path,quiet=True,heartbeat=.01)
    with SolverSession(SolverOptions(threads=1,time_limit=10),p) as s:
        lp=LP(sparse.csr_matrix([[1.]]),[.5],[0.],[1.],[-1.])
        assert s.solve(lp,"quiet LP")["status"]=="optimal"
    state=json.loads((tmp_path/"status.json").read_text())
    assert state["stage"]=="quiet LP" and state["state"]=="done"
    assert len((tmp_path/"events.jsonl").read_text().splitlines())>=2

