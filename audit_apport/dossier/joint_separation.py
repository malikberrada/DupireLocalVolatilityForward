"""Exact separation of individual feasibility from joint feasibility.

All candidates, quotes and budgets are declared. No optimizer or network is
used. A local algebraic obstruction proposes a dual certificate; the original
finite-grid verifier and an independent stencil audit decide acceptance.
"""
from dataclasses import replace
from fractions import Fraction as Q
from pathlib import Path

from dupire_joint.finite_criterion import Problem, ExactSystem, CERTIFICATE, verify, dyadic, rational
from .discriminant import primal_certificate, save_pair
from .exact import direct_check, observations_hash
from .io import read, write, require, clean

FAMILY = "constant_boundary_one_interior_node_v1"
CANDIDATES = [
    {"delta_t": "1/10", "vmin": "3/100", "vmax": "1/25", "epsilon": "1/1000000",
     "center_increment_bid": "1/2000", "center_increment_ask": "11/10000"},
    {"delta_t": "1/20", "vmin": "391/10000", "vmax": "803/20000", "epsilon": "1/1000000",
     "center_increment_bid": "3/10000", "center_increment_ask": "3/5000"},
    # Positive control: a common coarse witness exists at the compatibility limit.
    {"delta_t": "1/5", "vmin": "1/50", "vmax": "1/25", "epsilon": "1/1000000",
     "center_increment_bid": "3/5000", "center_increment_ask": "3/2000"},
]


def make_candidate(parameters):
    p = {k: rational(v) for k, v in parameters.items()}
    require(set(p) == set(CANDIDATES[0]), "Unknown joint-search parameter")
    require(p["delta_t"] > 0 and 0 < p["vmin"] < p["vmax"] and p["epsilon"] > 0,
            "Joint search needs positive steps, spreads and distinct positive variance bounds")
    require(0 < p["center_increment_bid"] < p["center_increment_ask"], "Invalid terminal center interval")
    ts = (Q(1, 4), Q(1, 4) + p["delta_t"])
    xs = (Q(9, 10), Q(1), Q(27, 25))
    base = tuple(Q(4, 5) - x + x*x/4 for x in xs)
    obs = []
    for j, t in enumerate(ts):
        for i, x in enumerate(xs):
            if j == 1 and i == 1:
                bid, ask = base[i]+p["center_increment_bid"], base[i]+p["center_increment_ask"]
            else:
                bid, ask = base[i]-p["epsilon"], base[i]+p["epsilon"]
            obs.append((t, x, bid, ask))
    problem = Problem(ts, xs, obs, p["vmin"], p["vmax"], "joint",
                      {"kind": "controlled_synthetic_search", "family": FAMILY, "parameters": parameters})
    return problem, base


def geometry(problem):
    require(problem.shape == (2, 3), "This analytic family needs two dates and three strikes")
    dt = problem.times[1]-problem.times[0]
    hm, hp = problem.strikes[1]-problem.strikes[0], problem.strikes[2]-problem.strikes[1]
    a = dt*problem.strikes[1]**2/2
    kappa = Q(2)/(hm*hp)
    lo, hi = problem.vmin[0][0], problem.vmax[0][0]
    vstar = 2*lo*hi/(lo+hi)
    return a, kappa, lo, hi, vstar


def individual_prices(problem, base, scheme):
    a, kappa, _, _, vstar = geometry(problem)
    delta = a*vstar/2  # The initial discrete gamma of the fixed quadratic is 1/2.
    if scheme == "backward":
        delta /= 1+a*vstar*kappa
    else:
        require(scheme == "forward", "Expected an individual stencil")
    prices = list(base)+list(base)
    prices[4] += delta
    return prices


def selected_audit(problem, prices):
    """direct_check intentionally reports both stencils; select active rows here."""
    audit = direct_check(problem, prices)
    schemes = ("forward", "backward") if problem.scheme == "joint" else (
        () if problem.scheme == "none" else (problem.scheme,))
    active = [v for name, v in audit["minimum_slack"].items()
              if "_local_" not in name or any(name.startswith(s+"_local_") for s in schemes)]
    return {"selected_scheme": problem.scheme,
            "selected_scheme_passed": all(Q(v) >= 0 for v in active),
            "joint_passed": audit["passed"], "all_stencil_diagnostics": audit}


def compatibility(problem, prices):
    """Intersection of the two admissible time-increment intervals; no division by gamma."""
    nt, nx = problem.shape
    xs, ts = problem.strikes, problem.times
    c = list(map(Q, prices))
    require(len(c) == nt*nx, "Incorrect compatibility-vector dimension")
    cells = []
    def gamma(j, i):
        hm, hp = xs[i]-xs[i-1], xs[i+1]-xs[i]
        return 2*((c[j*nx+i+1]-c[j*nx+i])/hp-(c[j*nx+i]-c[j*nx+i-1])/hm)/(hm+hp)
    for j in range(nt-1):
        for i in range(1, nx-1):
            g0, g1 = gamma(j, i), gamma(j+1, i)
            a = (ts[j+1]-ts[j])*xs[i]**2/2
            lo, hi = problem.vmin[j][i-1], problem.vmax[j][i-1]
            lower, upper = a*lo*max(g0, g1), a*hi*min(g0, g1)
            delta = c[(j+1)*nx+i]-c[j*nx+i]
            cells.append({"time_cell": j, "strike_index": i, "gamma_forward": str(g0),
                          "gamma_backward": str(g1), "increment": str(delta),
                          "joint_increment_lower": str(lower), "joint_increment_upper": str(upper),
                          "nonnegative_gammas": min(g0, g1) >= 0,
                          "admissible_increment_interval_nonempty": lower <= upper,
                          "this_increment_is_admissible": min(g0, g1) >= 0 and lower <= delta <= upper})
    return {"cells": cells, "all_cells_admissible": all(c["this_increment_is_admissible"] for c in cells),
            "zero_gamma_quotient_avoided": True}


def obstruction(problem):
    """Combine forward-lower and backward-upper, then cancel with quote rows.

    Let q be the weighted calendar increase at the two neighboring strikes.
    Gamma_1=Gamma_0+q-kappa*delta. The two rows imply
        a*[vmin*(1+a*kappa*vmax)-vmax]*Gamma_0-a*vmax*q <= 0.
    A positive minimum over the quote intervals is a valid joint separator.
    """
    require(problem.scheme == "joint", "The combined obstruction needs both schemes")
    system = ExactSystem(problem)
    a, kappa, lo, hi, _ = geometry(problem)
    first = [i for i, r in enumerate(system.rows) if r[0] == "forward_local_lower"]
    second = [i for i, r in enumerate(system.rows) if r[0] == "backward_local_upper"]
    require(len(first) == len(second) == 1, "Unexpected analytic stencil layout")
    multipliers = {first[0]: 1+a*kappa*hi, second[0]: Q(1)}
    combined = {}
    rhs = Q(0)
    for i, y in multipliers.items():
        _, row, b = system.rows[i]
        rhs += y*b
        for node, value in row.items():
            combined[node] = combined.get(node, Q(0))+y*value
    combined = {k: v for k, v in combined.items() if v}
    start = len(system.rows)-2*len(problem.observations)
    quotes = {}
    for j, (t, x, bid, ask) in enumerate(problem.observations):
        node = problem.times.index(t)*3+problem.strikes.index(x)
        entry = quotes.setdefault(node, {})
        if "bid" not in entry or bid > entry["bid"]:
            entry.update(bid=bid, bid_row=start+2*j+1)
        if "ask" not in entry or ask < entry["ask"]:
            entry.update(ask=ask, ask_row=start+2*j)
    require(all(k in quotes for k in combined), "Obstruction touches an unobserved price")
    minimum = sum((v*quotes[k]["bid" if v > 0 else "ask"] for k, v in combined.items()), Q(0))
    details = {"eta": str(lo*(1+a*kappa*hi)-hi), "combined_quote_minimum": str(minimum-rhs),
               "forward_lower_multiplier": str(1+a*kappa*hi), "backward_upper_multiplier": "1"}
    if minimum <= rhs:
        return None, {**details, "verified": False, "conclusion": "not_certified"}
    for node, value in combined.items():
        index = quotes[node]["bid_row" if value > 0 else "ask_row"]
        multipliers[index] = multipliers.get(index, Q(0))+abs(value)
    indices = sorted(multipliers)
    cert = {"format": CERTIFICATE, "kind": "dual", "problem_sha256": problem.digest(),
            "rows": indices, "multipliers": [str(multipliers[i]) for i in indices]}
    check = verify(problem, cert)
    require(check["verified"], "The combined joint separator was rejected")
    return cert, {**details, **check, "local_groups_used": [system.rows[i][0] for i in indices if i < start]}


def refine_time(problem, base, level):
    require(0 <= level <= 6, "Time-refinement level must be in 0..6")
    _, kappa, _, _, vstar = geometry(problem)
    times = dyadic(problem.times, level)
    dt = times[1]-times[0]
    z = kappa*problem.strikes[1]**2*dt*vstar/4
    require(0 <= z < 1, "Positive midpoint gamma ratio required")
    ratio = (1-z)/(1+z)
    prices = []
    for j in range(len(times)):
        row = list(base)
        row[1] += (Q(1, 2)-Q(1, 2)*ratio**j)/kappa
        prices.extend(row)
    p = Problem(times, problem.strikes, problem.observations,
                problem.vmin[0][0], problem.vmax[0][0], "joint", problem.source)
    return p, prices


def theory(problem, base):
    a, kappa, lo, hi, vstar = geometry(problem)
    lam = kappa*a*vstar
    require(0 < lam < 1, "The certified family uses 0 < lambda < 1")
    rstar = kappa*a*lo*hi/(hi-lo)
    level = 0
    while Q(2**level) < rstar:
        level += 1
    # Bernoulli bounds for rho^r place every constructed node in this interval.
    increase_min = Q(1, 2)/kappa*lam/(1+lam)
    increase_max = Q(1, 2)/kappa*lam
    terminal = next((b, h) for t, x, b, h in problem.observations
                    if t == problem.times[-1] and x == problem.strikes[1])
    require(terminal[0] <= base[1]+increase_min <= base[1]+increase_max <= terminal[1],
            "The analytic all-level bound does not preserve the terminal quote")
    # Every intermediate center lies between base[1] and base[1]+increase_max.
    static = replace(problem, scheme="none",
                     observations=tuple((t, x, Q(0), Q(1)) for t, x, _, _ in problem.observations))
    for increase in (Q(0), increase_max):
        prices = list(base)+list(base)
        prices[4] += increase
        require(verify(static, {"format": CERTIFICATE, "kind": "primal", "problem_sha256": static.digest(),
                               "prices": list(map(str, prices))})["verified"], "Shape-envelope check failed")
    return {"lemma": "one_interior_node_fixed_boundary_time_compatibility",
            "critical_time_step_for_frozen_boundaries": str((hi-lo)/(kappa*lo*hi)*2/problem.strikes[1]**2),
            "required_subdivision_factor_for_the_constructed_family": str(rstar),
            "guaranteed_time_level": level, "harmonic_midpoint_variance": str(vstar),
            "lambda": str(lam), "kappa": str(kappa),
            "terminal_increment_bounds_for_all_subdivisions": [str(increase_min), str(increase_max)],
            "all_dyadic_levels_from_threshold_preserve_original_quotes": True,
            "boundary_assumption_for_step_necessity": "constant neighboring prices; not all spread selections",
            "refinement_axes": "time_only_fixed_irregular_strikes",
            "same_polynomial_as_theorem_2_claimed": False,
            "scientific_priority_certified": False}


def search(folder, max_level=4, budget=3, progress=None):
    folder = Path(folder)
    require(0 <= max_level <= 6 and 1 <= budget <= len(CANDIDATES), "Invalid joint-search budget")
    protocol = {"format": "dupire-joint-separation-search-v1", "family": FAMILY,
                "candidates": CANDIDATES[:budget], "max_time_level": max_level,
                "synthetic_development_search": True, "finite_search_not_exhaustive": True,
                "observations_and_variance_bounds_fixed_across_schemes": True,
                "refinement_axes": "time_only_fixed_irregular_strikes"}
    write(folder/"search_protocol.json", protocol)
    attempts = []
    for number, parameters in enumerate(CANDIDATES[:budget], 1):
        if progress:
            progress.event("Search separate versus joint feasibility", force=True, candidate=number)
        p, base = make_candidate(parameters)
        primal = {}
        audits = {}
        for scheme in ("forward", "backward"):
            sub = replace(p, scheme=scheme)
            prices = individual_prices(p, base, scheme)
            primal[scheme], _ = primal_certificate(sub, prices)
            audits[scheme] = selected_audit(sub, prices)
            require(audits[scheme]["selected_scheme_passed"], "Independent individual check failed")
        negative, negative_check = obstruction(p)
        levels, found = [], None
        for level in range(max_level+1):
            refined, prices = refine_time(p, base, level)
            check = selected_audit(refined, prices)
            levels.append({"level": level, "shape": list(refined.shape),
                           "sampled_witness_passed": check["selected_scheme_passed"],
                           "witness_failure_proves_LP_infeasible": False})
            if level and check["selected_scheme_passed"] and negative:
                found = (level, refined, prices, check)
                break
        attempts.append({"candidate": number, "parameters": parameters,
                         "individual_witnesses_verified": True,
                         "joint_infeasible_exact": bool(negative), "time_levels": levels})
        if negative:
            for scheme in ("forward", "backward"):
                save_pair(folder, "coarse_"+scheme, replace(p, scheme=scheme), primal[scheme])
            save_pair(folder, "coarse_joint", p, negative)
            t = theory(p, base)
            write(folder/"theory.json", t)
            result = {"status": "joint_separation_certified", "selected_candidate": number,
                      "F_forward": "feasible_exact", "F_backward": "feasible_exact",
                      "F_joint": "infeasible_exact", "origin": "controlled_synthetic_search",
                      "observations_sha256": observations_hash(p), "observation_count": len(p.observations),
                      "coarse_shape": list(p.shape), "variance_bounds": [str(p.vmin[0][0]), str(p.vmax[0][0])],
                      "same_observations_and_bounds": True, "individual_audits": audits,
                      "joint_separator": negative_check,
                      "minimal_grid_for_declared_three_point_stencil": True,
                      "refined_joint": "not_materialized_in_budget", "first_materialized_time_level": None,
                      "first_feasible_time_level_proved": False,
                      "theory": t, "attempts": attempts,
                      "scientific_priority_certified": False, "solver_called": False, "network_used": False}
            if found:
                level, refined, prices, audit = found
                cert, _ = primal_certificate(refined, prices)
                save_pair(folder, "refined_joint", refined, cert)
                result.update(status="joint_separation_and_time_refinement_certified",
                              refined_joint="feasible_exact", refined_shape=list(refined.shape),
                              first_materialized_time_level=level, first_feasible_time_level_proved=(level == 1),
                              refined_audit=audit, refined_compatibility=compatibility(refined, prices))
            write(folder/"result.json", result)
            verify_search(folder)
            return clean(result)
    result = {"status": "no_joint_separator_found_in_budget", "attempts": attempts,
              "nonexistence_proved": False, "scientific_priority_certified": False}
    write(folder/"result.json", result)
    return result


def verify_search(folder):
    folder = Path(folder)
    protocol, result = read(folder/"search_protocol.json"), read(folder/"result.json")
    require(protocol["format"] == "dupire-joint-separation-search-v1" and protocol["family"] == FAMILY,
            "Unknown joint-search protocol")
    require(protocol["candidates"] == CANDIDATES[:len(protocol["candidates"])] and
            1 <= len(protocol["candidates"]) <= len(CANDIDATES), "Joint-search catalogue changed")
    require(type(protocol["max_time_level"]) is int and 0 <= protocol["max_time_level"] <= 6,
            "Invalid saved time budget")
    require(protocol == {"format": "dupire-joint-separation-search-v1", "family": FAMILY,
                         "candidates": CANDIDATES[:len(protocol["candidates"])],
                         "max_time_level": protocol["max_time_level"],
                         "synthetic_development_search": True, "finite_search_not_exhaustive": True,
                         "observations_and_variance_bounds_fixed_across_schemes": True,
                         "refinement_axes": "time_only_fixed_irregular_strikes"}, "Joint-search protocol changed")
    require(result.get("scientific_priority_certified") is False, "Unsupported priority claim")
    if result["status"] == "no_joint_separator_found_in_budget":
        require(result["nonexistence_proved"] is False, "Search failure cannot prove nonexistence")
        require(all(obstruction(make_candidate(p)[0])[0] is None for p in protocol["candidates"]),
                "A declared candidate actually has an exact joint separator")
        return {"verified": True, "joint_separation": False, "solver_called": False}
    require(result["status"] in {"joint_separation_certified", "joint_separation_and_time_refinement_certified"},
            "Unknown joint-separation status")
    number = result["selected_candidate"]
    require(type(number) is int and 1 <= number <= len(protocol["candidates"]), "Invalid selected candidate")
    p, base = make_candidate(protocol["candidates"][number-1])
    replay, first_level = [], None
    for n, parameters in enumerate(protocol["candidates"][:number], 1):
        candidate, initial = make_candidate(parameters)
        sep, _ = obstruction(candidate)
        levels = []
        for level in range(protocol["max_time_level"]+1):
            refined, prices = refine_time(candidate, initial, level)
            passed = selected_audit(refined, prices)["selected_scheme_passed"]
            levels.append({"level": level, "shape": list(refined.shape), "sampled_witness_passed": passed,
                           "witness_failure_proves_LP_infeasible": False})
            if level and passed and sep:
                first_level = level
                break
        replay.append({"candidate": n, "parameters": parameters, "individual_witnesses_verified": True,
                       "joint_infeasible_exact": bool(sep), "time_levels": levels})
        require(not sep or n == number, "Search skipped an earlier separating candidate")
    require(result["attempts"] == replay, "Declared joint-search attempts differ from exact replay")
    audits = {}
    count = 0
    for scheme in ("forward", "backward", "joint"):
        label = "coarse_"+scheme
        declared = Problem.load(read(folder/(label+".problem.json")))
        cert = read(folder/(label+".certificate.json"))
        require(declared.payload() == replace(p, scheme=scheme).payload(),
                "Same grid, bounds and observations required across the three schemes")
        require(cert["kind"] == ("dual" if scheme == "joint" else "primal") and verify(declared, cert)["verified"],
                "Invalid joint-discrimination proof: "+label)
        if scheme != "joint":
            expected = individual_prices(p, base, scheme)
            require(list(map(Q, cert["prices"])) == expected, "Individual witness changed")
            audits[scheme] = selected_audit(declared, expected)
            require(audits[scheme]["selected_scheme_passed"] and not audits[scheme]["joint_passed"],
                    "Individual witness does not demonstrate the declared distinction")
        count += 1
    negative, details = obstruction(p)
    require(negative == read(folder/"coarse_joint.certificate.json") and result["joint_separator"] == details,
            "Joint-obstruction derivation changed")
    require(set(details["local_groups_used"]) == {"forward_local_lower", "backward_local_upper"},
            "The joint proof must combine both local families")
    t = theory(p, base)
    require(t == read(folder/"theory.json") == result["theory"], "Time-refinement lemma changed")
    require(result["individual_audits"] == audits and
            result["observations_sha256"] == observations_hash(p) and result["observation_count"] == 6 and
            result["same_observations_and_bounds"] is True and result["coarse_shape"] == [2, 3] and
            result["minimal_grid_for_declared_three_point_stencil"] is True and
            result["variance_bounds"] == [str(p.vmin[0][0]), str(p.vmax[0][0])] and
            result["F_forward"] == result["F_backward"] == "feasible_exact" and
            result["F_joint"] == "infeasible_exact", "Unsupported joint-separation summary")
    materialized = result["status"] == "joint_separation_and_time_refinement_certified"
    require(materialized == (first_level is not None), "Refinement status contradicts the declared search")
    if materialized:
        level = result["first_materialized_time_level"]
        require(level == first_level, "Not the first materialized successful time level")
        require(type(level) is int and 1 <= level <= protocol["max_time_level"], "Invalid refined level")
        refined, prices = refine_time(p, base, level)
        actual = Problem.load(read(folder/"refined_joint.problem.json"))
        cert = read(folder/"refined_joint.certificate.json")
        require(actual.payload() == refined.payload(), "Refinement changed quotes, bounds, strikes or time subdivision")
        require(cert["kind"] == "primal" and verify(actual, cert)["verified"] and
                list(map(Q, cert["prices"])) == prices, "Refined joint proof failed")
        audit, comp = selected_audit(actual, prices), compatibility(actual, prices)
        require(audit["selected_scheme_passed"] and comp["all_cells_admissible"] and
                audit == result["refined_audit"] and comp == result["refined_compatibility"],
                "Independent refined-stencil check failed")
        require(result["refined_shape"] == list(actual.shape) and result["refined_joint"] == "feasible_exact" and
                result["first_feasible_time_level_proved"] is (level == 1), "Unsupported minimal-time-level claim")
        count += 1
    else:
        require(result["refined_joint"] == "not_materialized_in_budget" and
                result["first_materialized_time_level"] is None and
                result["first_feasible_time_level_proved"] is False, "Unsupported refinement result")
    return {"verified": True, "joint_separation": True, "proofs": count,
            "time_refinement_materialized": materialized, "same_observations_and_bounds": True,
            "all_level_time_lemma_checked": True, "scientific_priority_certified": False,
            "solver_called": False, "network_used": False}
