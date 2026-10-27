from dataclasses import replace
from fractions import Fraction as Q
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from positionnement.catalogue import load,validate,assess,matrix_markdown,sha256
from positionnement.experiments import crw_cost,adapted_crw_lp,weak_polynomial_check
from positionnement.metrics import (direct_check,read_external_surface,sample_polynomial,
                                   exact_stencil_errors,observations_hash)
from positionnement.kkt2016 import constraints,check_coefficients,fit_slices,recover_coefficients,strict_reference

ROOT=Path(__file__).resolve().parents[1]


def example():
    from dupire_joint.finite_criterion import Problem
    ts=(Q(1,4),Q(1,2),Q(1));xs=(Q(4,5),Q(19,20),Q(11,10),Q(13,10))
    def price(t,x):return Q(1,10)-Q(2,5)*(x-1)+(x-1)**2/2+t/50
    obs=[(t,x,price(t,x)-Q(1,100000),price(t,x)+Q(1,100000)) for t in ts for x in xs]
    return Problem(ts,xs,obs,"1/100","1/10","joint"),[price(t,x) for t in ts for x in xs]


def test_registry_preserves_unknown_and_scientific_priority_remains_unresolved():
    r=load(ROOT/"literature/registry.json");a=assess(r)
    assert len(r["papers"])>=15 and a["novelty_status"]=="not_determined_by_this_tool"
    assert "KKT2024" in a["access_gaps"] and "FH2015" in a["access_gaps"]
    assert all(p["evidence"]["preserved_refinement"]["status"]=="not_assessed" for p in r["papers"])
    assert "jamais une preuve d'absence" in matrix_markdown(r)


@pytest.mark.parametrize("change",["future","absent","unsupported_full_text","new_claim","duplicate"])
def test_evidence_errors_cannot_be_promoted_to_novelty(change):
    r=load(ROOT/"literature/registry.json")
    if change=="future":r["papers"][0]["available_date"]="2027-01-01"
    if change=="absent":r["papers"][0]["evidence"]["preserved_refinement"]={"status":"absent"}
    if change=="unsupported_full_text":
        p=next(p for p in r["papers"] if p["id"]=="KKT2024")
        p["evidence"]["preserved_refinement"]={"status":"documented","locator":"Theorem 7"}
    if change=="new_claim":r["claims"][-1]["status"]="novelty_proved"
    if change=="duplicate":r["papers"].append(copy.deepcopy(r["papers"][0]))
    with pytest.raises(ValueError):validate(r)


def test_direct_audit_checks_the_math_and_rejects_a_tiny_exact_quote_violation():
    p,c=example();check=direct_check(p,c)
    assert check["passed"] and check["shape_passed"] and check["quotes_passed"]
    t,x,_,_=p.observations[0]
    obs=list(p.observations);obs[0]=(t,x,c[0]+Q(1,10**30),c[0]+Q(2,10**30))
    changed=replace(p,observations=obs)
    assert not direct_check(changed,c)["quotes_passed"]
    assert observations_hash(changed)!=observations_hash(p)


def test_hard_static_compatibility_does_not_imply_the_local_variance_bounds():
    # P=.06-.5*(x-1)+(x-1)^2+.1*(t-.25): gamma=2, theta=.1.
    # Thus the continuous variance is .1/x^2, outside [.18^2,.22^2].
    spec={"t0":Q(1,4),"t1":Q(1),"x0":Q(49,50),"x1":Q(51,50),
          "vmin":Q(81,2500),"vmax":Q(121,2500),"buffer":Q(1,1000),"gamma_floor":Q(1,10)}
    z=spec["x0"]-1;length=spec["x1"]-spec["x0"]
    a=Q(3,50)-z/2+z*z;b=-length/2+2*z*length;d=length**2
    first=[a,a+b/2,a+b+d]
    c=np.asarray([first,[v+Q(3,40) for v in first]],dtype=object)
    from dupire_joint.bernstein import evaluate
    records=[]
    for t,u in ((spec["t0"],Q(0)),(spec["t1"],Q(1))):
        for x,w in ((spec["x0"],Q(0)),(Q(1),Q(1,2)),(spec["x1"],Q(1))):
            value=Q(evaluate(c,u,w));records.append([t,x,value-Q(1,100000),value+Q(1,100000),Q(1)])
    result=weak_polynomial_check(c,spec,records)
    assert result["shape_quotes_gamma_floor_verified"]
    assert not result["full_constructive_condition_verified"]
    assert Q(result["local_coefficient_minima"]["local_upper"])<0


def test_crw_four_affine_formula_and_published_delta0():
    h,d=Q(1,10),Q(1,100)
    assert crw_cost(0,h,d)==0
    assert crw_cost(h,h,d)==crw_cost(-h,h,d)==d
    assert crw_cost(2*h,h,d)==crw_cost(-2*h,h,d)==h+d
    with pytest.raises(ValueError):crw_cost(0,h,0)
    p,c=example();lp,delta0=adapted_crw_lp(p)
    assert delta0==min(Q(1,len(p.observations)),Q(1,100000))
    # The analytic surface equals all reference midpoints: the epigraph t=0
    # is valid and has objective zero, independent of the solver.
    vector=np.r_[list(map(float,c)),np.zeros(len(p.observations))]
    assert max(lp.A@vector-lp.b)<1e-10 and lp.cost@vector==0
    crossed=list(p.observations);t,x,bid,ask=crossed[0];crossed[0]=(t,x,ask,bid)
    with pytest.raises(ValueError,match="positive spreads"):adapted_crw_lp(replace(p,observations=crossed))


def test_kkt2016_constraint_set_and_known_quadratic_fit():
    p,_=example();xmin,xmax=p.strikes[0],p.strikes[-1];length=xmax-xmin
    for t in p.times:
        a=Q(1,10)-Q(2,5)*(xmin-1)+(xmin-1)**2/2+t/50
        b=length*(-Q(2,5)+xmin-1);d=length**2/2
        beta=[a,a+b/2,a+b+d]
        assert check_coefficients(beta,2,xmin,xmax)["verified"]
    record,values=fit_slices(p,2)
    assert record["status"]=="slice_shapes_verified_exact"
    assert values is not None and record["direct_audit"]["quotes_passed"]
    assert not record["calendar_imposed"] and not record["AIC_selection_implemented"]


def test_slice_rounding_correction_is_exact_and_has_a_uniform_price_budget():
    xmin,xmax=Q(4,5),Q(13,10)
    # A flat price curve is feasible on this window; a tiny last-coefficient
    # increase violates decreasingness, but is a rounding-scale error.
    beta=[Q(1,2),Q(1,2),Q(1,2)+Q(1,10**30)]
    assert not check_coefficients(beta,2,xmin,xmax)["verified"]
    recovered,info=recover_coefficients(beta,2,xmin,xmax)
    assert check_coefficients(recovered,2,xmin,xmax)["verified"]
    assert Q(info["max_price_change_on_domain"])<=Q(info["allowed_price_change"])
    assert not info["optimality_certified"]
    reference=strict_reference(4,xmin,xmax)
    assert Q(check_coefficients(reference,4,xmin,xmax)["minimum_coefficient_slack"])>0
    assert recover_coefficients([Q(10)]*3,2,xmin,xmax)[0] is None


def test_refinement_bound_is_sufficient_and_can_be_conservative():
    from dupire_joint.constructive import verify_payload
    payload=json.loads((ROOT/"fixtures/constructive.certificate.json").read_text())
    check=verify_payload(payload)
    assert check["passed"] and check["mesh"]["guaranteed_level"]==2
    hashes=[]
    for level in (0,1,2):
        p,c,_=sample_polynomial(payload,level,level,10000)
        audit=direct_check(p,c);assert audit["passed"]
        errors=exact_stencil_errors(payload,p,c)
        trial=check["mesh"]["trials"][level]
        assert Q(errors["gamma_error"])<=Q(trial["E_gamma"])
        assert all(Q(v)<=Q(trial["E_variance"]) for v in errors["variance_error"].values())
        hashes.append(observations_hash(p))
    assert len(set(hashes))==1
    assert not check["mesh"]["trials"][0]["condition_passed"]
    assert sample_polynomial(payload,2,2,1)[0] is None


def test_external_prices_cannot_silently_regrid_the_problem(tmp_path):
    p,prices=example();f=tmp_path/"surface.csv"
    with f.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['time','x','price'])
        writer.writerows((str(t),str(x),str(v)) for (t,x),v in zip(((t,x) for t in p.times for x in p.strikes),prices))
    assert read_external_surface(f,p)==prices
    f.write_text(f.read_text().replace('4/5','8000000000000001/10000000000000000',1))
    with pytest.raises(ValueError,match="EXACTLY"):read_external_surface(f,p)


def cli(*args):
    return subprocess.run([sys.executable,str(ROOT/"positionner_apport.py"),*map(str,args)],
                          capture_output=True,text=True,timeout=60)


def test_full_offline_cli_and_independent_reverification(tmp_path):
    out=tmp_path/"report"
    run=cli("--criterion-run",ROOT/"fixtures/market_example","--logical-grid",ROOT/"fixtures/market_example/F0.exact_grid.json",
            "--threads",1,"--out",out)
    assert run.returncode==0,run.stdout+run.stderr
    result=json.loads((out/"positionnement.json").read_text())
    assert result["criterion_run"]["verified"] and result["criterion_run"]["original_source_rechecked"]
    assert result["constructive"]["guaranteed_level"]==2
    assert result["bibliographic_assessment"]["novelty_status"]=="not_determined_by_this_tool"
    assert result["experiments"]["bernstein_ablation"]["status"]=="shape_certified_exact"
    verify=cli("--verify",out)
    assert verify.returncode==0,verify.stdout+verify.stderr
    checked=json.loads(verify.stdout)
    assert checked["verified"] and not checked["solver_called"] and not checked["network_used"]
    assert not checked["scientific_novelty_certified"]
    # A different feasible vector is not the stated polynomial. Even after
    # updating the file manifest, the mathematical binding must reject it.
    f=out/"polynomial_level_00.witness.json";d=json.loads(f.read_text())
    d["prices"][0]=str(Q(d["prices"][0])+Q(1,10**30));f.write_text(json.dumps(d))
    manifest=json.loads((out/"manifest.json").read_text());manifest["sha256"][f.name]=sha256(f)
    (out/"manifest.json").write_text(json.dumps(manifest))
    rejected=cli("--verify",out)
    assert rejected.returncode==2 and "not the declared polynomial" in rejected.stderr


def test_cli_preserves_previous_results_and_respects_node_budget(tmp_path):
    out=tmp_path/"budget"
    r=cli("--skip-experiments","--max-nodes",1,"--out",out)
    assert r.returncode==0,r.stdout+r.stderr
    report=json.loads((out/"positionnement.json").read_text())
    assert report["constructive"]["guaranteed_level"]==2
    assert all(not r["materialized"] for r in report["constructive"]["runs"])
    again=cli("--skip-experiments","--out",out)
    assert again.returncode==2 and "previous evidence" in again.stderr


def test_network_candidates_remain_unreviewed_and_filter_is_explicit(monkeypatch):
    from positionnement import retrieval
    seen=[]
    def fake(url,**kwargs):
        seen.append(url)
        return json.dumps({"message":{"items":[{"title":["An unreviewed candidate"],"DOI":"10.fake/x"}]}}).encode(),{"sha256":"x"}
    monkeypatch.setattr(retrieval,"fetch",fake)
    data=retrieval.crossref_candidates("Bernstein local volatility","2026-10-26")
    assert data["candidates"][0]["status"]=="unreviewed_candidate"
    assert "until-pub-date%3A2026-10-26" in seen[0]
    with pytest.raises(ValueError):retrieval.crossref_candidates("x","2026-10-26",rows=100)


def test_external_export_preserves_rational_axes_and_binary_price_values(tmp_path):
    p,_=example();problem=tmp_path/"problem.json";problem.write_text(json.dumps(p.payload()))
    (tmp_path/"my_pricer.py").write_text("def price(t,x):\n    return 0.2\n")
    output=tmp_path/"surface.csv"
    r=subprocess.run([sys.executable,str(ROOT/"exporter_surface.py"),"--problem",str(problem),
                      "--pricer","my_pricer:price","--out",str(output)],cwd=tmp_path,
                     capture_output=True,text=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
    assert read_external_surface(output,p)==[Q(.2)]*(len(p.times)*len(p.strikes))
