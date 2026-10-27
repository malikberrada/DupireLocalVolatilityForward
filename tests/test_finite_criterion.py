"""Exact examples, separating certificates and CLI round trips for Theorem 1."""
from dataclasses import replace
from fractions import Fraction as Q
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from dupire_joint.finite_criterion import (CERTIFICATE,ExactSystem,Problem,dyadic,
                                          read_source,verify)
from dupire_joint.refinement import quadratic_parameters,quadratic_trial


def price(t,x):
    # Gamma=1 and theta=1/50, so v=1/(25*x^2) for either stencil.
    return Q(1,10)-Q(2,5)*(x-1)+(x-1)**2/2+t/50


def example():
    ts=(Q(1,4),Q(1,2),Q(1));xs=(Q(4,5),Q(19,20),Q(11,10),Q(13,10))
    obs=tuple((t,x,price(t,x)-Q(1,10**6),price(t,x)+Q(1,10**6))
              for t,x in ((ts[0],xs[0]),(ts[0],xs[-1]),(ts[-1],xs[1]),(ts[-1],xs[-1])))
    return Problem(ts,xs,obs,"1/100","1/10","joint")


def test_exact_joint_surface_on_irregular_grid_and_preserved_observations():
    p=example()
    for level in (0,1,2):
        refined=replace(p,times=dyadic(p.times,level),strikes=dyadic(p.strikes,level),
                        vmin="1/100",vmax="1/10")
        c=[price(t,x) for t in refined.times for x in refined.strikes]
        assert ExactSystem(refined).primal(c)["verified"]
        # Independent analytic values check the bounds without assembling rows.
        assert all(Q(1,100)<=1/(25*x*x)<=Q(1,10) for x in refined.strikes[1:-1])
        assert refined.observations==p.observations
    assert Problem.load(p.payload()).digest()==p.digest()


def test_crossed_interval_has_exact_dual_even_below_binary64_resolution():
    p=example();obs=list(p.observations)
    t,x,_,_=obs[0];gap=Q(1,10**30)
    obs[0]=(t,x,price(t,x)+gap,price(t,x))
    p=replace(p,observations=tuple(obs))
    system=ExactSystem(p)
    # The last 2*nquotes rows are ask, bid, in input order; coefficients cancel.
    indices=[len(system.rows)-2*len(obs),len(system.rows)-2*len(obs)+1]
    certificate={"format":CERTIFICATE,"problem_sha256":p.digest(),"kind":"dual",
                 "rows":indices,"multipliers":["1","1"]}
    checked=verify(p,certificate)
    assert checked["verified"] and Q(checked["exact_separation_margin"])==gap
    bad=copy.deepcopy(certificate);bad["multipliers"][0]="-1"
    with pytest.raises(ValueError,match="negative"):
        verify(p,bad)
    bad=copy.deepcopy(certificate);bad["problem_sha256"]="0"*64
    assert not verify(p,bad)["verified"]


def test_price_box_corrects_a_nonzero_dual_residual():
    p=example();t,x,_,_=p.observations[0]
    p=replace(p,observations=((t,x,Q(0),Q(1,10)),))
    s=ExactSystem(p)
    # Intrinsic at x=.8 is .2. The ask row alone, with residual +1,
    # contradicts the price box; a zero dual residual is unnecessary.
    result=s.dual([len(s.rows)-2],["1"])
    assert result["verified"] and Q(result["exact_separation_margin"])==Q(1,10)


def test_flat_gamma_inequalities_do_not_identify_a_variance():
    p=example()
    c=[Q(7,10)-x/2 for _ in p.times for x in p.strikes]
    obs=((p.times[0],p.strikes[0],c[0],c[0]),)
    p=replace(p,observations=obs)
    check=ExactSystem(p).primal(c)
    assert check["verified"] and not check["variance_quotient_everywhere_identifiable"]
    assert check["zero_gamma_nodes"]==len(p.times)*(len(p.strikes)-2)
    # All time increments and all second divided differences are exactly zero.
    assert all(c[i]==c[len(p.strikes)+i] for i in range(len(p.strikes)))


def test_decimal_inputs_are_not_silently_rounded_and_duplicate_rows_retained(tmp_path):
    f=tmp_path/"quotes.csv"
    f.write_text("time,x,bid,ask\n0.25,0.8,0.20,0.21\n1,1.3,0.04,0.06\n"
                 "0.25,0.8,0.200000000000000000000000000001,0.21\n")
    ts,xs,obs,source=read_source(f)
    p=Problem(ts,xs,obs,"0","1",source=source)
    assert len(p.observations)==3 and len(p.strikes)==3
    assert p.observations[-1][2]-p.observations[0][2]==Q(1,10**30)
    assert p.observations[0][1]==Q(4,5)
    assert p.observations[0][1]!=Q(float(.8))
    assert len([r for r in ExactSystem(p).rows if r[0]=="ask"])==3


@pytest.mark.parametrize("change",[
    {"times":("1/4","1/4","1")},
    {"strikes":("0","1","2")},
    {"times":("-1","1/2","1")},
    {"vmin":"-1"}, {"vmax":"1/1000"}, {"vmin":(("0",),)},
    {"observations":(("1/3","1","0.1","0.2"),)},
    {"scheme":"both"}, {"vmin":.01},
])
def test_invalid_hypotheses_rejected(change):
    with pytest.raises((ValueError,TypeError)):
        replace(example(),**change)


def test_explicit_quadratic_threshold_including_zero_derivatives():
    spec={"buffer":Q(1,1000),"vmax":Q(1,10),"x0":Q(4,5)}
    constants={"gamma0":Q(1),"M3":Q(2),"M4":Q(3),"Mtt":Q(1,100)}
    geometry={"dt":Q(3,4),"h":Q(1,5),"asymmetry":Q(1,20)}
    p=quadratic_parameters(constants,spec,geometry)
    upper=p["level_upper_bound"]
    assert quadratic_trial(p,constants,spec,upper)["passed"]
    trials=[quadratic_trial(p,constants,spec,k) for k in range(upper+3)]
    first=next(k for k,t in enumerate(trials) if t["passed"])
    assert first>0 and all(t["passed"] for t in trials[first:])
    for t in trials:
        r=2**t["level"]
        assert Q(t["quadratic_margin"])==p["C"]*r*r-p["A"]*r-p["B"]
    flat={**constants,"M3":Q(0),"M4":Q(0),"Mtt":Q(0)}
    p=quadratic_parameters(flat,spec,geometry)
    assert p["level_upper_bound"]==0 and quadratic_trial(p,flat,spec,0)["passed"]


def cli(*args):
    env=os.environ.copy()
    env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1]/"src")
    return subprocess.run([sys.executable,"-m","dupire_joint",*map(str,args)],env=env,
                          capture_output=True,text=True,timeout=60)


def test_cli_certifies_original_rational_geometry_and_verifies_without_solver(tmp_path):
    p=example();f=tmp_path/"input.json"
    f.write_text(json.dumps(p.payload()))
    out=tmp_path/"positive"
    result=cli("criterion","--logical-grid",f,"--sigma-min","0.1","--sigma-max","0.4",
               "--threads",1,"--out",out)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads((out/"criterion.json").read_text())
    assert report["conclusion"]=="feasible_exact" and report["assumptions"]["same_surface_for_both_schemes"]
    saved=Problem.load(json.loads((out/"criterion.problem.json").read_text()))
    cert=json.loads((out/"criterion.certificate.json").read_text())
    assert verify(saved,cert)["verified"]
    result=cli("verify-criterion","--problem",out/"criterion.problem.json",
               "--certificate",out/"criterion.certificate.json","--logical-grid",f,
               "--out",tmp_path/"verification")
    assert result.returncode==0,result.stdout+result.stderr
    cert["prices"][0]="0"
    assert not verify(saved,cert)["verified"]


def test_cli_proves_infeasible_F0_and_does_not_blame_the_local_bounds(tmp_path):
    p=example();payload=p.payload()
    payload["observations"][0][2:]=["0.31","0.30"]
    f=tmp_path/"crossed.json";f.write_text(json.dumps(payload))
    out=tmp_path/"negative"
    result=cli("criterion","--logical-grid",f,"--threads",1,"--out",out)
    assert result.returncode==4,result.stdout+result.stderr
    report=json.loads((out/"criterion.json").read_text())
    assert report["F0"]["conclusion"]=="infeasible_exact"
    assert report["diagnosis"]=="observations_and_static_constraints_incompatible"
    assert not (out/"criterion.certificate.json").exists()
    result=cli("verify-criterion","--problem",out/"F0.problem.json",
               "--certificate",out/"F0.certificate.json","--logical-grid",f,
               "--out",tmp_path/"verification")
    assert result.returncode==0,result.stdout+result.stderr


def test_cli_distinguishes_incompatible_local_bounds_from_feasible_quotes(tmp_path):
    p=example();payload=p.payload()
    payload["observations"]=[[str(t),str(x),str(price(t,x)),str(price(t,x))]
                             for t in p.times for x in p.strikes]
    f=tmp_path/"fixed_prices.json";f.write_text(json.dumps(payload))
    out=tmp_path/"bounds_negative"
    result=cli("criterion","--logical-grid",f,"--sigma-min","0","--sigma-max","0",
               "--threads",1,"--out",out)
    assert result.returncode==4,result.stdout+result.stderr
    report=json.loads((out/"criterion.json").read_text())
    assert report["F0"]["conclusion"]=="feasible_exact"
    assert report["requested"]["conclusion"]=="infeasible_exact"
    assert report["diagnosis"]=="bounds_and_grid_incompatible_with_observations"
    saved=Problem.load(json.loads((out/"criterion.problem.json").read_text()))
    cert=json.loads((out/"criterion.certificate.json").read_text())
    assert verify(saved,cert)["verified"]
