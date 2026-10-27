from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
import json
import shutil
import socket
import subprocess
import sys

import pytest
from dupire_joint.finite_criterion import Problem, ExactSystem, verify
from dossier.discriminant import (CANDIDATES, make_candidate, polynomial, primal_certificate,
                                 interval_separator, search, verify_search)
from dossier.io import read, write, safe_child, seal, check_manifest
from dossier.literature import validate, generate, verify_comparison
from dossier.trace import inspect, audit, verify_audit
from dossier.app import main, verify_folder

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def yahoo(tmp_path):
    path = tmp_path/"yahoo"
    shutil.copytree(ROOT/"fixtures/yahoo", path)
    return path


def test_coarse_variances_exceed_fixed_band_analytically():
    p, _, _ = make_candidate(CANDIDATES[0])
    q = Q(1,50)
    forward = 2*q+q*q
    backward = forward/(1+q)**2
    assert forward > p.vmax[0][0]
    assert backward < p.vmin[0][0]
    assert p.strikes[1]-p.strikes[0] != p.strikes[2]-p.strikes[1]


def test_positive_spreads_and_static_feasibility():
    p, _, _ = make_candidate(CANDIDATES[0])
    assert all(b < a for _, _, b, a in p.observations)
    f0 = replace(p, scheme="none")
    c = [polynomial(Q(1,50),t,x) for t in p.times for x in p.strikes]
    cert, result = primal_certificate(f0,c)
    assert result["verified"] and Q(result["minimum_gamma"]) > 0


def test_rational_separator_proves_local_infeasibility():
    p, _, _ = make_candidate(CANDIDATES[0])
    cert, check = interval_separator(p)
    assert cert["kind"] == "dual" and verify(p,cert)["verified"]
    assert "local" in check["offending_group"] and Q(check["exact_separation_margin"]) > 0
    assert all(Q(v) >= 0 for v in cert["multipliers"])


def test_widening_quotes_invalidates_the_negative_proof():
    p, _, _ = make_candidate(CANDIDATES[0])
    cert, _ = interval_separator(p)
    widened = replace(p, observations=tuple((t,x,b-Q(1,100),a+Q(1,100)) for t,x,b,a in p.observations))
    cert["problem_sha256"] = widened.digest()
    assert not verify(widened,cert)["verified"]


def test_corrupt_dual_rejected():
    p, _, _ = make_candidate(CANDIDATES[0])
    cert, _ = interval_separator(p)
    cert["multipliers"] = ["0"]*len(cert["rows"])
    assert not verify(p,cert)["verified"]


def test_discriminant_preserves_all_six_observations(tmp_path):
    result = search(tmp_path)
    assert result["status"] == "discriminating_example_certified"
    assert result["first_verified_polynomial_level"] == 2
    assert result["guaranteed_level_by_sufficient_bound"] == 6
    a=Problem.load(read(tmp_path/"coarse_joint.problem.json"))
    b=Problem.load(read(tmp_path/"refined_joint.problem.json"))
    assert len(a.observations) == 6 and a.observations == b.observations
    assert set(a.times) <= set(b.times) and set(a.strikes) <= set(b.strikes)
    assert verify_search(tmp_path)["verified"]


def test_intermediate_polynomial_failure_is_not_a_negative_LP_claim(tmp_path):
    result = search(tmp_path,max_level=1,budget=1)
    assert result["status"] == "no_discriminant_found_in_budget"
    assert not result["nonexistence_proved"]
    assert all(not r["failed_polynomial_implies_LP_infeasible"] for r in result["attempts"][0]["levels"])


def test_modified_refined_quote_rejected_even_with_new_hash(tmp_path):
    search(tmp_path)
    path=tmp_path/"refined_joint.problem.json"
    data=read(path);data["observations"][0][2]=str(Q(data["observations"][0][2])-Q(1,10000));write(path,data)
    p=Problem.load(data);c=read(tmp_path/"refined_joint.certificate.json");c["problem_sha256"]=p.digest()
    write(tmp_path/"refined_joint.certificate.json",c)
    assert verify(p,c)["verified"]
    with pytest.raises(ValueError, match="changed observations"):
        verify_search(tmp_path)


def test_polynomial_continuous_certificate_cannot_be_replaced(tmp_path):
    search(tmp_path)
    path=tmp_path/"polynomial.json";data=read(path);data["coefficients"][0][0]="1";write(path,data)
    with pytest.raises(ValueError,match="Polynomial specification"):
        verify_search(tmp_path)


def test_original_yahoo_fixture_full_lineage(yahoo):
    result, links=inspect(yahoo)
    assert result["complete_lineage_verified"] and result["observation_count"]==121
    assert (result["call_count"],result["put_count"])==(59,62)
    assert result["shape"]==[5,75]
    assert result["selection_policy_chosen_before_prices_proved"] is False
    assert result["bid_ask_synchronization_certified"] is False
    assert result["replay_metadata"]["kind"]=="retrospective_reconstruction"
    for row in links:
        t,x,b,a=map(Q,row["normalized_observation"])
        assert x==Q(row["strike"])*Q(row["discount_D"])/Q(row["prepaid_forward_A"])
        assert b==Q(row["raw_bid"])/Q(row["prepaid_forward_A"])+(1-x if row["side_field"]=="puts" else 0)
        assert a>=b


def test_trace_export_and_recheck(yahoo,tmp_path):
    out=tmp_path/"audit"
    result=audit(yahoo,yahoo,out)
    assert result["exact_grid_source_rechecked"]
    assert verify_audit(out)["observation_count"]==121


def test_changed_raw_bid_rejected(yahoo):
    p=yahoo/"raw_snapshot.json";data=read(p)
    # Affect even an excluded row: the archive digest must remain identical.
    data["chains"][0]["calls"][0]["bid"]=0
    write(p,data)
    with pytest.raises(ValueError,match="raw books"):
        inspect(yahoo)


def test_changed_put_ask_rejected(yahoo):
    p=yahoo/"snapshot.json";data=read(p);data["chains"][0]["puts"][0]["ask"]+=1;write(p,data)
    with pytest.raises(ValueError,match="raw books"):
        inspect(yahoo)


def test_changed_selection_rule_rejected(yahoo):
    p=yahoo/"selection.json";data=read(p);data["settings"]["strike_step"]=100;write(p,data)
    with pytest.raises(ValueError,match="raw books"):
        inspect(yahoo)


def test_changed_curve_certificate_rejected(yahoo):
    p=yahoo/"curves_estimees.csv.uncertainty.json";data=read(p)
    data["groups"][0]["nominal"]["discount"]="1";write(p,data)
    with pytest.raises(ValueError,match="Curve CSV"):
        inspect(yahoo)


def test_same_grid_different_bytes_breaks_source_binding(yahoo):
    p=yahoo/"F0.exact_grid.json";p.write_bytes(p.read_bytes()+b"\n")
    with pytest.raises(ValueError,match="source hash"):
        inspect(yahoo)


def test_problem_observation_cannot_silently_disappear(yahoo):
    p=yahoo/"criterion.problem.json";data=read(p);data["observations"].pop();write(p,data)
    with pytest.raises(ValueError,match="observations differ"):
        inspect(yahoo)


def test_missing_curve_file_is_an_error_not_a_complete_trace(yahoo):
    (yahoo/"curves_estimees.csv").unlink()
    with pytest.raises(ValueError,match="Missing trace input"):
        inspect(yahoo)


def test_registry_has_128_cells_and_preserves_partial_access_unknowns():
    r=validate(read(ROOT/"literature/theoremes.json"))
    assert len(r["axes"])*len(r["results"])==128
    k=next(x for x in r["results"] if x["paper_id"]=="KKT2024")
    assert k["access"]=="abstract_and_public_appendix_reviewed"
    assert k["comparisons"]["threshold"]["relation"]=="unknown"


def test_partial_access_cannot_be_given_maintext_evidence():
    r=read(ROOT/"literature/theoremes.json")
    k=next(x for x in r["results"] if x["paper_id"]=="KKT2024")
    k["comparisons"]["representation"]["locator"]="Theorem 2, page 9"
    with pytest.raises(ValueError,match="Partial access"):
        validate(r)


def test_incomplete_hypothesis_map_rejected():
    r=read(ROOT/"literature/theoremes.json");r["results"][0]["comparisons"].pop("threshold")
    with pytest.raises(ValueError,match="coverage"):
        validate(r)


def test_attaching_fulltext_does_not_mark_it_reviewed(tmp_path):
    source=tmp_path/"article.pdf";source.write_bytes(b"local test fixture; no article content")
    out=tmp_path/"lit"
    result=generate(ROOT/"literature/theoremes.json",out,["KKT2024="+str(source)])
    assert not result["full_text_KKT2024_review_complete"]
    assert verify_comparison(out)["verified"]


def test_fulltext_review_cannot_be_claimed_without_review_metadata():
    r=read(ROOT/"literature/theoremes.json")
    k=next(x for x in r["results"] if x["paper_id"]=="KKT2024")
    k["access"]="full_text_sections_reviewed"
    with pytest.raises(ValueError,match="named reviewer"):
        validate(r)


def test_original_ready_detects_corrupt_extra_file(yahoo):
    from dossier.io import sha
    extra=yahoo/"original_export.csv";extra.write_text("original")
    write(yahoo/"READY.json",{"sha256":{"original_export.csv":sha(extra)}})
    assert inspect(yahoo)[0]["complete_lineage_verified"]
    extra.write_text("corrupted")
    with pytest.raises(ValueError,match="READY hash"):
        inspect(yahoo)


def test_ready_named_extra_files_are_preserved_in_the_audit(yahoo,tmp_path):
    from dossier.io import sha
    extra=yahoo/"original_export.csv";extra.write_text("original")
    write(yahoo/"READY.json",{"sha256":{"original_export.csv":sha(extra)}})
    out=tmp_path/"audit"
    audit(yahoo,yahoo,out)
    assert (out/"inputs/original_export.csv").read_bytes()==extra.read_bytes()
    assert verify_audit(out)["verified"]


def test_manifest_detects_changed_artifact(tmp_path):
    (tmp_path/"a.txt").write_text("original");seal(tmp_path)
    assert check_manifest(tmp_path)==1
    (tmp_path/"a.txt").write_text("changed")
    with pytest.raises(ValueError,match="Hash mismatch"):
        check_manifest(tmp_path)


def test_manifest_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError,match="escapes"):
        safe_child(tmp_path,"../outside.txt")


def test_full_flow_and_verification_without_network_or_solver(tmp_path,monkeypatch):
    def forbidden(*a,**kw):
        raise AssertionError("Network or solver was called")
    monkeypatch.setattr(socket,"create_connection",forbidden)
    from dupire_joint.solver import SolverSession
    monkeypatch.setattr(SolverSession,"__enter__",forbidden)
    out=tmp_path/"full"
    assert main(["--demo","--out",str(out)])==0
    result=verify_folder(out)
    assert not result["solver_called"] and not result["network_used"]
    assert result["discriminant"]["proofs"]==3
    with pytest.raises(ValueError,match="new --out"):
        main(["--demo","--out",str(out)])


def test_cli_reverify_in_fresh_process(tmp_path):
    out=tmp_path/"external"
    made=subprocess.run([sys.executable,str(ROOT/"auditer_apport.py"),"--demo","--out",str(out)],capture_output=True,text=True)
    assert made.returncode==0,made.stderr
    checked=subprocess.run([sys.executable,str(ROOT/"auditer_apport.py"),"--verify",str(out)],capture_output=True,text=True)
    assert checked.returncode==0,checked.stderr
    assert json.loads(checked.stdout)["status"]=="verified_exact_audit"
