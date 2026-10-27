from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
import json
import subprocess
import sys

import pytest
from dupire_joint.finite_criterion import Problem, CERTIFICATE, verify
from dossier.joint_separation import (CANDIDATES, make_candidate, individual_prices, obstruction,
                                     refine_time, theory, selected_audit, compatibility, search, verify_search)
from dossier.io import read, write
from dossier.app import main, verify_folder
from dossier.literature import generate, verify_comparison

ROOT = Path(__file__).resolve().parents[1]


def test_individual_witnesses_are_valid_and_cross_scheme_checks_fail():
    p, base = make_candidate(CANDIDATES[0])
    for scheme in ("forward", "backward"):
        values = individual_prices(p, base, scheme)
        sub = replace(p, scheme=scheme)
        cert = {"format": CERTIFICATE, "kind": "primal", "prices": list(map(str, values)),
                "problem_sha256": sub.digest()}
        assert verify(sub, cert)["verified"]
        cert["problem_sha256"] = p.digest()
        assert not verify(p, cert)["verified"]
        check = selected_audit(sub, values)
        assert check["selected_scheme_passed"] and not check["joint_passed"]
        assert not compatibility(p, values)["all_cells_admissible"]


def test_joint_separator_needs_both_families_and_positive_spreads():
    p, _ = make_candidate(CANDIDATES[0])
    cert, checked = obstruction(p)
    assert all(b < a for _, _, b, a in p.observations)
    assert verify(p, cert)["verified"]
    assert checked["exact_separation_margin"] == "991/8000000"
    assert checked["support_size"] == 7
    assert set(checked["local_groups_used"]) == {"forward_local_lower", "backward_local_upper"}


def test_widened_quotes_do_not_inherit_the_original_negative_proof():
    p, _ = make_candidate(CANDIDATES[0])
    cert, _ = obstruction(p)
    widened = replace(p, observations=tuple((t, x, b-Q(1, 100), a+Q(1, 100))
                                            for t, x, b, a in p.observations))
    cert["problem_sha256"] = widened.digest()
    assert not verify(widened, cert)["verified"]


def test_positive_joint_control_at_the_time_compatibility_limit():
    p, base = make_candidate(CANDIDATES[2])
    cert, _ = obstruction(p)
    assert cert is None
    refined, values = refine_time(p, base, 0)
    check = selected_audit(refined, values)
    assert check["selected_scheme_passed"]
    assert theory(p, base)["required_subdivision_factor_for_the_constructed_family"] == "1"


def test_threshold_and_every_materialized_later_level_preserve_quotes():
    p, base = make_candidate(CANDIDATES[0])
    t = theory(p, base)
    assert t["critical_time_step_for_frozen_boundaries"] == "1/15"
    assert t["required_subdivision_factor_for_the_constructed_family"] == "3/2"
    assert t["guaranteed_time_level"] == 1
    assert not selected_audit(*refine_time(p, base, 0))["selected_scheme_passed"]
    for level in range(1, 7):
        refined, values = refine_time(p, base, level)
        assert refined.observations == p.observations and refined.strikes == p.strikes
        assert selected_audit(refined, values)["selected_scheme_passed"]
        assert compatibility(refined, values)["all_cells_admissible"]


def test_candidate_with_smaller_variance_margin_needs_more_time_levels():
    p, base = make_candidate(CANDIDATES[1])
    cert, checked = obstruction(p)
    assert cert and checked["verified"]
    assert theory(p, base)["guaranteed_time_level"] == 4
    assert not selected_audit(*refine_time(p, base, 3))["selected_scheme_passed"]
    assert selected_audit(*refine_time(p, base, 4))["selected_scheme_passed"]


def test_complete_new_example_and_standard_library_independent_verifier(tmp_path):
    result = search(tmp_path)
    assert result["status"] == "joint_separation_and_time_refinement_certified"
    assert result["first_materialized_time_level"] == 1 and result["first_feasible_time_level_proved"]
    assert verify_search(tmp_path)["proofs"] == 4
    completed = subprocess.run([sys.executable, "-I", "-S", str(ROOT/"verifier_joint_independant.py"), str(tmp_path)],
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    check = json.loads(completed.stdout)
    assert check["individual_feasibility_does_not_imply_joint_feasibility"]
    assert not check["third_party_imports"] and not check["scientific_priority_certified"]


def test_zero_refinement_budget_keeps_only_the_three_coarse_proofs(tmp_path):
    result = search(tmp_path, max_level=0)
    assert result["status"] == "joint_separation_certified"
    assert result["refined_joint"] == "not_materialized_in_budget"
    assert result["theory"]["guaranteed_time_level"] == 1
    assert verify_search(tmp_path)["proofs"] == 3
    assert not (tmp_path/"refined_joint.certificate.json").exists()


def test_changed_observation_cannot_make_the_three_problems_different(tmp_path):
    search(tmp_path)
    name = tmp_path/"coarse_backward.problem.json"
    p = read(name)
    p["observations"][0][2] = str(Q(p["observations"][0][2])-Q(1, 10000))
    write(name, p)
    c = read(tmp_path/"coarse_backward.certificate.json")
    c["problem_sha256"] = Problem.load(p).digest()
    write(tmp_path/"coarse_backward.certificate.json", c)
    assert verify(Problem.load(p), c)["verified"]
    with pytest.raises(ValueError, match="Same grid, bounds and observations"):
        verify_search(tmp_path)


def test_combined_dual_tampering_is_detected(tmp_path):
    search(tmp_path)
    name = tmp_path/"coarse_joint.certificate.json"
    c = read(name)
    c["multipliers"] = ["0"]*len(c["multipliers"])
    write(name, c)
    with pytest.raises(ValueError, match="Invalid joint-discrimination proof"):
        verify_search(tmp_path)


def test_edited_analytic_threshold_is_detected(tmp_path):
    search(tmp_path)
    name = tmp_path/"theory.json"
    data = read(name)
    data["guaranteed_time_level"] = 0
    write(name, data)
    with pytest.raises(ValueError, match="lemma changed"):
        verify_search(tmp_path)


def test_forged_priority_flag_is_detected(tmp_path):
    search(tmp_path)
    name = tmp_path/"result.json"
    data = read(name)
    data["scientific_priority_certified"] = True
    write(name, data)
    with pytest.raises(ValueError, match="priority claim"):
        verify_search(tmp_path)


def test_forged_literature_completeness_is_detected(tmp_path):
    generate(ROOT/"literature/theoremes.json", tmp_path)
    name = tmp_path/"comparison.json"
    data = read(name)
    data["full_text_KKT2024_review_complete"] = True
    write(name, data)
    with pytest.raises(ValueError, match="Literature summary differs"):
        verify_comparison(tmp_path)


def test_evidence_only_mode_has_no_yahoo_dependency(tmp_path, monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("Yahoo must not be called in evidence-only mode")
    monkeypatch.setattr("dossier.app.audit", forbidden)
    assert main(["--evidence-only", "--out", str(tmp_path/"out")]) == 0
    data = read(tmp_path/"out/audit.json")
    assert data["yahoo"] is None and not (tmp_path/"out/yahoo").exists()
    assert verify_folder(tmp_path/"out")["joint_discriminant"]["verified"]
    assert data["claims"]["new_elements_relative_to_the_previous_project_dossier"]["individual_feasibility_with_empty_intersection"]
