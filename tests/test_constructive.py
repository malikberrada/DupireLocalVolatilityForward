"""Independent exact algebra/stencil checks and an end-to-end certificate test."""
from fractions import Fraction as F
from math import comb
from pathlib import Path
import copy
import json
import os
import subprocess
import sys
import numpy as np
import pytest

from dupire_joint.bernstein import derivative, elevate, evaluate, times_x_squared
from dupire_joint.constructive import exact_check, mesh_plan, geometry, verify_payload, validate
from dupire_joint.data import Quotes


def from_powers(powers, m, n):
    # Independent identity u^k = sum_{i>=k} choose(i,k)/choose(m,k) B_i^m(u).
    return np.array([[sum(v*F(comb(i,k),comb(m,k))*F(comb(j,l),comb(n,l))
                         for (k,l),v in powers.items() if k<=i and l<=j)
                      for j in range(n+1)] for i in range(m+1)], dtype=object)


def example():
    spec = {"t0": F(1,4), "t1": F(1), "x0": F(49,50), "x1": F(51,50),
            "vmin": F(81,2500), "vmax": F(121,2500), "buffer": F(1,1000), "gamma_floor": F(1)}
    z0, lx, lt = spec["x0"]-1, spec["x1"]-spec["x0"], spec["t1"]-spec["t0"]
    powers = {}
    for k,v in enumerate((F(3,50), F(-1,2), F(1), F(1,5), F(1,10))):
        for j in range(k+1):
            powers[0,j] = powers.get((0,j),F(0))+v*comb(k,j)*z0**(k-j)*lx**j
    powers[1,0] = F(1,25)*lt
    powers[2,0] = F(3,1000)*lt**2
    c = from_powers(powers,2,4)
    t = [F(1,4),F(1)]
    x = [F(49,50),F(199,200),F(51,50)]
    records = []
    for ti in t:
        for xi in x:
            p = evaluate(c,(ti-spec["t0"])/lt,(xi-spec["x0"])/lx)
            records.append([ti,xi,p-F(1,100000),p+F(1,100000),F(1,100000)])
    return c,spec,records,t,x


def refine(axis, level):
    return [a+(b-a)*F(i,2**level) for a,b in zip(axis,axis[1:]) for i in range(2**level)]+[axis[-1]]


def test_exact_algebra_against_monomials():
    a = from_powers({(0,0):F(2),(1,0):F(3),(0,2):F(-4),(2,3):F(7)},2,3)
    for u,w in ((F(0),F(1)),(F(1,3),F(2,5)),(F(1),F(0))):
        assert evaluate(a,u,w) == 2+3*u-4*w*w+7*u*u*w**3
        assert evaluate(elevate(elevate(a,0,5),1,7),u,w) == evaluate(a,u,w)
        assert evaluate(derivative(a,1,F(2)),u,w) == (-8*w+21*u*u*w*w)/2
        assert evaluate(derivative(a,0,F(3),2),u,w) == F(14,9)*w**3
        assert evaluate(times_x_squared(a,F(2),F(4)),u,w) == (2+2*w)**2*evaluate(a,u,w)
        assert evaluate(derivative(a,1,F(2),4),u,w) == 0


def test_constructed_bounds_and_all_further_meshes_exactly():
    c,spec,records,t,x = example()
    check = exact_check(c,spec,records)
    assert check["passed"]
    assert check["constants"]["Mtt"] == F(3,500)
    assert check["constants"]["M4"] == F(12,5)
    plan = mesh_plan(check["constants"],spec,t,x)
    assert plan["guaranteed_level"] > 0
    for level in range(plan["guaranteed_level"],plan["guaranteed_level"]+3):
        tr,xr = refine(t,level),refine(x,level)
        values = [[evaluate(c,(ti-spec["t0"])/(spec["t1"]-spec["t0"]),
                             (xi-spec["x0"])/(spec["x1"]-spec["x0"])) for xi in xr] for ti in tr]
        for j in range(len(tr)-1):
            for i in range(1,len(xr)-1):
                hm,hp = xr[i]-xr[i-1],xr[i+1]-xr[i]
                theta = (values[j+1][i]-values[j][i])/(tr[j+1]-tr[j])
                for row in (j,j+1):
                    gamma = 2*((values[row][i+1]-values[row][i])/hp
                               -(values[row][i]-values[row][i-1])/hm)/(hm+hp)
                    v = 2*theta/(xr[i]**2*gamma)
                    assert spec["vmin"] <= v <= spec["vmax"]
        g = geometry(tr,xr)
        assert g["asymmetry"] == geometry(t,x)["asymmetry"]/2**level


def test_cubic_asymmetry_term_cannot_be_dropped():
    # Gamma(x^3) - (x^3)'' = 2(h_plus-h_minus), exactly.
    x,hm,hp = F(1),F(1,10),F(1,5)
    gamma = 2*(((x+hp)**3-x**3)/hp-(x**3-(x-hm)**3)/hm)/(hm+hp)
    assert gamma-6*x == 2*(hp-hm)


def test_no_tolerance_in_the_quote_condition():
    c,spec,records,_,_ = example()
    # At the lower left corner, P equals the first Bernstein coefficient.
    records[0][2] = c[0,0]+F(1,10**30)
    records[0][3] = c[0,0]+F(2,10**30)
    check = exact_check(c,spec,records)
    assert not check["passed"]
    assert check["minima"]["quotes"] == -F(1,10**30)


@pytest.mark.parametrize("field,value", [("t0",F(0)),("gamma_floor",F(0)),("buffer",F(0)),("buffer",F(1))])
def test_hypotheses_are_mandatory(field,value):
    _,spec,_,_,_ = example()
    spec[field] = value
    with pytest.raises(ValueError):
        validate(spec,(2,4))


def run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]/"src")
    return subprocess.run([sys.executable,"-u","-m","dupire_joint",*map(str,args)],
                          env=env,capture_output=True,text=True,timeout=45)


def test_cli_construct_verify_and_reject_tampering(tmp_path):
    out = tmp_path/"fit"
    result = run_cli("construct","--demo","--device","cpu","--degree-time",2,"--degree-space",4,
                     "--threads",1,"--out",out)
    assert result.returncode == 0, result.stdout+result.stderr
    report = json.loads((out/"construction.json").read_text())
    assert report["conclusion"] == "feasible_from_guaranteed_level"
    assert report["samples"]["numeric_export_passed"]
    assert 0 < report["verification"]["mesh"]["guaranteed_level"] <= 8
    payload = json.loads((out/"constructive.certificate.json").read_text())
    q = Quotes.read(out/"observations.csv")
    assert verify_payload(payload,q)["passed"]
    altered = copy.deepcopy(payload)
    altered["coefficients"][0][0] = "-1"
    assert not verify_payload(altered,q)["passed"]
    # Even a tiny violation of a quote is rejected, with no LP tolerance.
    altered = copy.deepcopy(payload)
    altered["observations"][0][2] = altered["observations"][0][3] = str(F(payload["coefficients"][0][0])+F(1,10**15))
    with pytest.raises(ValueError):
        verify_payload(altered,q)
    different = copy.deepcopy(q)
    different.ask[0] += 1e-10
    with pytest.raises(ValueError,match="provided quotes"):
        verify_payload(payload,different)
    verified = run_cli("verify-construct","--certificate",out/"constructive.certificate.json",
                       "--quotes",out/"observations.csv","--out",tmp_path/"verify")
    assert verified.returncode == 0, verified.stdout+verified.stderr


def test_no_materialization_budget_and_no_false_general_infeasibility(tmp_path):
    out = tmp_path/"budget"
    result = run_cli("construct","--demo","--device","cpu","--degree-time",2,"--degree-space",4,
                     "--threads",1,"--max-nodes",1,"--out",out)
    assert result.returncode == 0, result.stderr
    report = json.loads((out/"construction.json").read_text())
    assert report["verification"]["passed"] and not report["samples"]["materialized"]
    assert not (out/"calibration.samples.npz").exists()
    q = Quotes.read(out/"observations.csv")
    q.bid[0] = q.ask[0]+.01
    q.write(tmp_path/"crossed.csv")
    failed = tmp_path/"not_certified"
    result = run_cli("construct","--quotes",tmp_path/"crossed.csv","--threads",1,"--out",failed)
    assert result.returncode == 3, result.stdout+result.stderr
    report = json.loads((failed/"construction.json").read_text())
    assert report["conclusion"] == "not_certified"
    assert report["infeasibility_of_general_problem_claimed"] is False
    assert not (failed/"constructive.certificate.json").exists()


def test_mesh_search_limit_keeps_continuous_certificate():
    c,spec,records,t,x = example()
    check = exact_check(c,spec,records)
    plan = mesh_plan(check["constants"],spec,t,x,max_level=0)
    assert plan["guaranteed_level"] is None
    assert plan["finite_threshold_exists_by_theorem"]
