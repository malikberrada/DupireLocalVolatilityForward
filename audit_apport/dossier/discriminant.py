"""Search a declared rational quadratic family; proofs never use a solver status.

A failed sampled polynomial does not imply LP infeasibility. A negative result
is published only after a rational separating inequality has been verified.
"""
from __future__ import annotations
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path
import numpy as np

from dupire_joint.finite_criterion import Problem, ExactSystem, CERTIFICATE, dyadic, verify
from dupire_joint.constructive import exact_check, mesh_plan
from .exact import direct_check, observations_hash
from .io import read, write, require, clean

POLYNOMIAL = "dupire-rational-polynomial-witness-v1"
# This is a synthetic development search, never a selection of Yahoo quotes.
CANDIDATES = [
    {"q": "1/50", "vmin": "391/10000", "vmax": "803/20000", "buffer": "1/100000"},
    {"q": "1/5", "vmin": "8/25", "vmax": "21/50", "buffer": "1/200"},
    {"q": "1/10", "vmin": "7/40", "vmax": "41/200", "buffer": "1/1000"},
]


def polynomial(q, t, x):
    return Q(4, 5) - x + Q(1, 4) * (1 + q * (t - Q(1, 4))) ** 2 * x ** 2


def make_candidate(parameters, spread=Q(1, 10**6)):
    q = Q(parameters["q"])
    ts, xs = (Q(1, 4), Q(5, 4)), (Q(9, 10), Q(1), Q(27, 25))
    observations = tuple((t, x, polynomial(q, t, x) - spread,
                          polynomial(q, t, x) + spread) for t in ts for x in xs)
    problem = Problem(ts, xs, observations, parameters["vmin"], parameters["vmax"], "joint",
                      {"kind": "controlled_synthetic_search", "generator": "quadratic_family_v1",
                       "q": str(q), "half_spread": str(spread)})
    # b(t)=(1+q*u)^2/4 has degree-two Bernstein coefficients below.
    btime = [Q(1, 4), (1 + q) / 4, (1 + q) ** 2 / 4]
    xlinear = [xs[0], (xs[0] + xs[-1]) / 2, xs[-1]]
    xsquare = [xs[0]**2, xs[0] * xs[-1], xs[-1]**2]
    coefficients = [[Q(4, 5) - xlinear[i] + bt * xsquare[i] for i in range(3)] for bt in btime]
    spec = {"t0": ts[0], "t1": ts[-1], "x0": xs[0], "x1": xs[-1],
            "vmin": Q(parameters["vmin"]), "vmax": Q(parameters["vmax"]),
            "buffer": Q(parameters["buffer"]), "gamma_floor": Q(49, 100)}
    return problem, coefficients, spec


def primal_certificate(problem, prices):
    certificate = {"format": CERTIFICATE, "kind": "primal", "problem_sha256": problem.digest(),
                   "prices": list(map(str, prices))}
    check = verify(problem, certificate)
    require(check["verified"], "Invalid primal proposal")
    return certificate, check


def interval_separator(problem):
    """Try each non-quote inequality against the intersection of observed boxes.

    To cancel a positive row coefficient add its bid inequality; to cancel a
    negative coefficient add its ask inequality. All multipliers are nonnegative.
    This is incomplete discovery followed by the full exact dual check.
    """
    system = ExactSystem(problem)
    nx = len(problem.strikes)
    ti = {t: i for i, t in enumerate(problem.times)}
    xi = {x: i for i, x in enumerate(problem.strikes)}
    observed = {}
    start = len(system.rows) - 2 * len(problem.observations)
    for k, (t, x, bid, ask) in enumerate(problem.observations):
        node = ti[t] * nx + xi[x]
        entry = observed.setdefault(node, {})
        if "bid" not in entry or bid > entry["bid"]:
            entry.update(bid=bid, bid_row=start + 2*k + 1)
        if "ask" not in entry or ask < entry["ask"]:
            entry.update(ask=ask, ask_row=start + 2*k)
    for index, (group, row, rhs) in enumerate(system.rows[:start]):
        if not row or not all(k in observed for k in row):
            continue
        minimum = sum((a * observed[k]["bid" if a > 0 else "ask"] for k, a in row.items()), Q(0))
        if minimum <= rhs:
            continue
        multipliers = {index: Q(1)}
        for k, a in row.items():
            bound_row = observed[k]["bid_row" if a > 0 else "ask_row"]
            multipliers[bound_row] = multipliers.get(bound_row, Q(0)) + abs(a)
        ids = sorted(multipliers)
        certificate = {"format": CERTIFICATE, "kind": "dual", "problem_sha256": problem.digest(),
                       "rows": ids, "multipliers": [str(multipliers[i]) for i in ids]}
        checked = verify(problem, certificate)
        require(checked["verified"], "Invalid interval separator")
        return certificate, {**checked, "offending_group": group, "interval_gap": str(minimum - rhs)}
    return None, {"verified": False, "conclusion": "not_certified"}


def save_pair(folder, label, problem, certificate):
    write(folder / (label + ".problem.json"), problem.payload())
    write(folder / (label + ".certificate.json"), certificate)


def search(folder, max_level=4, budget=3, progress=None):
    folder = Path(folder)
    require(0 <= max_level <= 6 and 1 <= budget <= len(CANDIDATES), "Invalid search budget")
    attempts = []
    write(folder / "search_protocol.json", {"family": "P(T,x)=4/5-x+(1+q*(T-1/4))^2*x^2/4",
          "candidates": CANDIDATES[:budget], "levels": list(range(max_level+1)),
          "quote_half_spread": "1/1000000", "finite_search_not_exhaustive": True,
          "synthetic_development_search": True, "bid_ask_unchanged_between_levels": True})
    for number, parameters in enumerate(CANDIDATES[:budget]):
        if progress:
            progress.event("Search exact discriminating example", force=True, candidate=number+1)
        problem, coefficients, spec = make_candidate(parameters)
        values = [polynomial(Q(parameters["q"]), t, x) for t in problem.times for x in problem.strikes]
        f0 = replace(problem, scheme="none")
        f0cert, f0check = primal_certificate(f0, values)
        negative, negative_check = interval_separator(problem)
        records = [list(row)+[Q(1)] for row in problem.observations]
        continuous = exact_check(np.asarray(coefficients, dtype=object), spec, records)
        runs = []
        found = None
        for level in range(max_level+1):
            refined = Problem(dyadic(problem.times, level), dyadic(problem.strikes, level),
                              problem.observations, parameters["vmin"], parameters["vmax"], "joint", problem.source)
            sampled = [polynomial(Q(parameters["q"]), t, x) for t in refined.times for x in refined.strikes]
            audit = direct_check(refined, sampled)
            runs.append({"level": level, "shape": refined.shape, "polynomial_passed": audit["passed"],
                         "observations_sha256": observations_hash(refined),
                         "failed_polynomial_implies_LP_infeasible": False})
            if level and negative and audit["passed"] and continuous["passed"]:
                found = refined, sampled, level, audit
                break
        attempt = {"candidate": number+1, "parameters": parameters,
                   "F0": "feasible_exact", "coarse_joint": "infeasible_exact" if negative else "not_certified",
                   "polynomial_continuous_conditions": continuous["passed"], "levels": runs}
        attempts.append(attempt)
        if found:
            refined, sampled, level, audit = found
            positive, positive_check = primal_certificate(refined, sampled)
            save_pair(folder, "coarse_F0", f0, f0cert)
            save_pair(folder, "coarse_joint", problem, negative)
            save_pair(folder, "refined_joint", refined, positive)
            plan = mesh_plan(continuous["constants"], spec, problem.times, problem.strikes)
            write(folder / "polynomial.json", {"format": POLYNOMIAL, "parameters": parameters,
                  "spec": spec, "coefficients": coefficients, "observations": records,
                  "arithmetic": "exact rational observations, not binary64 CSV semantics",
                  "checks": continuous, "mesh_plan": plan})
            result = {"status": "discriminating_example_certified", "origin": "controlled_synthetic_search",
                  "F0": "feasible_exact", "coarse_joint": "infeasible_exact", "refined_joint": "feasible_exact",
                  "selected_candidate": number+1, "observations_unchanged": True,
                  "observations_sha256": observations_hash(problem), "observation_count": len(problem.observations),
                  "variance_bounds": [parameters["vmin"], parameters["vmax"]],
                  "first_verified_polynomial_level": level, "first_feasible_LP_level_proved": False,
                  "same_witness_for_both_schemes": True, "coarse_separator": negative_check,
                  "refined_audit": audit, "guaranteed_level_by_sufficient_bound": plan["guaranteed_level"],
                  "coarse_shape": problem.shape, "refined_shape": refined.shape,
                  "no_general_nesting_claimed": True, "scientific_novelty_certified": False,
                  "individual_stencil_obstructions": {s: interval_separator(replace(problem, scheme=s))[1]
                                                       for s in ("forward", "backward")},
                  "attempts": attempts}
            write(folder / "result.json", result)
            verify_search(folder)
            return clean(result)
    result = {"status": "no_discriminant_found_in_budget", "attempts": attempts,
              "nonexistence_proved": False, "scientific_novelty_certified": False}
    write(folder / "result.json", result)
    return result


def verify_search(folder):
    folder = Path(folder)
    result = read(folder / "result.json")
    require(result.get("scientific_novelty_certified") is False, "Unsupported scientific-priority claim")
    protocol = read(folder / "search_protocol.json")
    require(protocol["candidates"] == CANDIDATES[:len(protocol["candidates"])], "Search protocol changed")
    if result["status"] != "discriminating_example_certified":
        require(result["status"] == "no_discriminant_found_in_budget", "Unknown search conclusion")
        return {"verified": True, "discriminant": False, "solver_called": False}
    ps = {}
    for label, kind in (("coarse_F0", "primal"), ("coarse_joint", "dual"), ("refined_joint", "primal")):
        p = Problem.load(read(folder / (label + ".problem.json")))
        c = read(folder / (label + ".certificate.json"))
        require(c["kind"] == kind and verify(p, c)["verified"], "Rejected proof: " + label)
        ps[label] = p
    coarse, fine, f0 = ps["coarse_joint"], ps["refined_joint"], ps["coarse_F0"]
    require(coarse.scheme == fine.scheme == "joint" and f0.scheme == "none", "Unexpected schemes")
    parameters = protocol["candidates"][result["selected_candidate"]-1]
    expected, coefs, spec = make_candidate(parameters)
    require(expected.payload() == coarse.payload(), "Candidate differs from declared generator")
    require(replace(coarse, scheme="none").payload() == f0.payload(), "Ablation changed more than local constraints")
    level = result["first_verified_polynomial_level"]
    require(fine.times == dyadic(coarse.times, level) and fine.strikes == dyadic(coarse.strikes, level),
            "Refined grid is not the declared subdivision")
    require(fine.observations == coarse.observations and
            {v for row in coarse.vmin for v in row} == {v for row in fine.vmin for v in row} and
            {v for row in coarse.vmax for v in row} == {v for row in fine.vmax for v in row},
            "Refinement changed observations or variance bounds")
    require(result["observations_sha256"] == observations_hash(coarse), "Wrong observation digest")
    require(result["F0"] == "feasible_exact" and result["coarse_joint"] == "infeasible_exact" and
            result["refined_joint"] == "feasible_exact" and result["same_witness_for_both_schemes"] is True and
            result["first_feasible_LP_level_proved"] is False and result["observations_unchanged"] is True,
            "Unsupported discrimination claim")
    require(result["observation_count"] == len(coarse.observations) and
            result["coarse_shape"] == list(coarse.shape) and result["refined_shape"] == list(fine.shape) and
            result["variance_bounds"] == [parameters["vmin"], parameters["vmax"]],
            "Incorrect discrimination parameters")
    expected_separator, separator_check = interval_separator(coarse)
    require(read(folder / "coarse_joint.certificate.json") == expected_separator and
            result["coarse_separator"] == separator_check, "Incorrect reported separator")
    if "individual_stencil_obstructions" in result:
        require(result["individual_stencil_obstructions"] ==
                {s: interval_separator(replace(coarse, scheme=s))[1] for s in ("forward", "backward")},
                "Incorrect individual-stencil obstruction in the polynomial example")
    prices = [polynomial(Q(parameters["q"]), t, x) for t in fine.times for x in fine.strikes]
    cert = read(folder / "refined_joint.certificate.json")
    require(list(map(Q, cert["prices"])) == prices, "Refined witness is not the declared polynomial")
    audit = direct_check(fine, prices)
    require(audit["passed"] and audit == result["refined_audit"], "Independent stencil check failed")
    poly = read(folder / "polynomial.json")
    require(poly["format"] == POLYNOMIAL and poly["parameters"] == parameters and
            poly["spec"] == clean(spec) and poly["coefficients"] == clean(coefs), "Polynomial specification changed")
    records = [list(row)+[Q(1)] for row in coarse.observations]
    require(poly["observations"] == clean(records), "Polynomial observations differ")
    check = exact_check(np.asarray(coefs, dtype=object), spec, records)
    require(check["passed"] and clean(check) == poly["checks"], "Continuous coefficient proof failed")
    plan = mesh_plan(check["constants"], spec, coarse.times, coarse.strikes)
    require(clean(plan) == poly["mesh_plan"] and plan["guaranteed_level"] ==
            result["guaranteed_level_by_sufficient_bound"], "Theoretical refinement bound changed")
    return {"verified": True, "discriminant": True, "proofs": 3,
            "polynomial_certificate": True, "observations_unchanged": True,
            "solver_called": False, "network_used": False}
