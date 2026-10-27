"""Rebuild raw -> selected books -> nominal curves -> rational grid -> proof.

Hashes bind bytes. They do not authenticate Yahoo, synchronize books, or prove
that a selection policy was chosen before viewing prices.
"""
from __future__ import annotations
from datetime import date
from fractions import Fraction as Q
from pathlib import Path
import math

from dupire_joint.curve_estimation import book, verify_curves
from dupire_joint.finite_criterion import Problem, dyadic, verify
from .exact import direct_check, observations_hash
from .io import read, write, copy, sha, digest, require, safe_child

FILES = ("raw_snapshot.json", "snapshot.json", "selection.json", "curves_estimees.csv",
         "curves_estimees.csv.uncertainty.json", "F0.exact_grid.json")


def select(raw, settings):
    """Replay collector 0.2.0 selection, including the original row objects."""
    from dupire_joint.settlements import aware_utc
    require(raw.get("started_utc") and raw.get("ended_utc"), "Missing retrieval interval")
    reference_date = aware_utc(raw["started_utc"]).date()
    step = Q(str(settings.get("strike_step", 0)))
    require(step >= 0, "Negative strike mesh")
    selected = {"source": raw.get("source", "unknown"), "started_utc": raw["started_utc"],
                "ended_utc": raw["ended_utc"], "chains": [], "quote_timestamps_available": False,
                "selection_scope": "fixed spot-relative strike window plus explicit invalid-book exclusion",
                "spot_used_as_forward": False}
    exclusions, references = [], []
    for chain in raw.get("chains", []):
        if chain.get("symbol") != settings["symbol"]:
            continue
        days = (date.fromisoformat(chain["expiry"]) - reference_date).days
        if not settings["min_days"] <= days <= settings["max_days"]:
            exclusions.append({"expiry": chain["expiry"], "reason": "outside_predeclared_date_window"})
            continue
        spot = settings.get("reference_spot")
        origin = "explicit_selection_reference"
        if spot is None:
            spot = chain.get("underlying", {}).get("regularMarketPrice")
            origin = "Yahoo_underlying_regularMarketPrice"
        require(spot is not None and math.isfinite(float(spot)) and float(spot) > 0,
                "Missing positive spot reference for strike selection")
        spot = float(spot)
        lo, hi = Q(str(spot))*Q(str(settings["moneyness_min"])), Q(str(spot))*Q(str(settings["moneyness_max"]))
        references.append({"expiry": chain["expiry"], "spot": spot, "origin": origin,
                           "strike_lower": str(lo), "strike_upper": str(hi)})
        target = {k: v for k, v in chain.items() if k not in ("calls", "puts")}
        target.update(calls=[], puts=[])
        for field, side in (("calls", "C"), ("puts", "P")):
            for row in chain.get(field, []):
                try:
                    parsed = book(row, chain["expiry"], side, settings["root"])
                except (TypeError, ValueError, ZeroDivisionError) as exc:
                    reason = str(exc)
                    if "mismatch" in reason:
                        raise ValueError("Contract integrity failure: " + reason) from exc
                    exclusions.append({"expiry": chain["expiry"], "contract": row.get("contractSymbol"),
                                       "reason": reason, "bid": row.get("bid"), "ask": row.get("ask")})
                    continue
                if parsed is None:
                    continue
                if not lo <= parsed["K"] <= hi:
                    exclusions.append({"expiry": chain["expiry"], "contract": row.get("contractSymbol"),
                                       "reason": "outside_predeclared_strike_window"})
                    continue
                if step and parsed["K"] % step:
                    exclusions.append({"expiry": chain["expiry"], "contract": row.get("contractSymbol"),
                                       "reason": "outside_predeclared_strike_mesh", "strike": str(parsed["K"]),
                                       "strike_step": str(step), "strike_origin": "0"})
                    continue
                target[field].append(dict(row))
        selected["chains"].append(target)
    selected["selection"] = {"symbol": settings["symbol"], "root": settings["root"],
          "moneyness_min": settings["moneyness_min"], "moneyness_max": settings["moneyness_max"],
          "references": references, "outlier_removal_by_feasibility": False, "book_prices_modified": False}
    if "strike_step" in settings:
        selected["selection"].update(strike_step=str(step), strike_origin="0",
          selection_protocol="fixed_before_download", full_raw_chain_certified=False)
        selected["selection_scope"] = "predeclared strike mesh and spot-relative window; unchanged valid bid/ask"
    return selected, exclusions


def rebuild_grid(selected, curves, root):
    groups = {g["expiry"]: g for g in curves["groups"] if g["status"] == "accepted"}
    observations, sources, links, seen = [], [], [], set()
    for j, chain in enumerate(selected["chains"]):
        if chain["expiry"] not in groups:
            continue
        g = groups[chain["expiry"]]
        A, D = Q(g["nominal"]["prepaid_forward"]), Q(g["nominal"]["discount"])
        require(A > 0 and D > 0 and Q(g["nominal"]["forward"]) == A / D, "Invalid nominal curves")
        for field, side in (("calls", "C"), ("puts", "P")):
            for i, row in enumerate(chain.get(field, [])):
                parsed = book(row, chain["expiry"], side, root)
                if parsed is None:
                    continue
                require(parsed["contract"] not in seen, "Duplicate contract in normalized books")
                seen.add(parsed["contract"])
                x = parsed["K"] * D / A
                shift = 1 - x if side == "P" else Q(0)
                obs = [Q(g["time"]), x, parsed["bid"] / A + shift, parsed["ask"] / A + shift]
                source = {"contract": parsed["contract"], "side": side, "expiry": chain["expiry"],
                          "strike": str(parsed["K"]), "bid": str(parsed["bid"]), "ask": str(parsed["ask"])}
                observations.append(obs)
                sources.append(source)
                links.append({"observation_index": len(observations)-1, "selected_chain_index": j,
                              "selected_book_index": i, "side_field": field, "contract": parsed["contract"],
                              "expiry": chain["expiry"], "raw_bid": str(parsed["bid"]), "raw_ask": str(parsed["ask"]),
                              "strike": str(parsed["K"]), "prepaid_forward_A": str(A), "discount_D": str(D),
                              "forward_F": str(A/D), "put_to_call_shift": str(shift),
                              "normalized_observation": list(map(str, obs)), "row_sha256": digest(row)})
    grid = {"times": list(map(str, sorted({r[0] for r in observations}))),
            "strikes": list(map(str, sorted({r[1] for r in observations}))),
            "observations": [list(map(str, r)) for r in observations], "sources": sources}
    return grid, links


def inspect(folder, max_nodes=100000):
    """All necessary bytes already copied into one immutable audit input folder."""
    folder = Path(folder)
    for name in FILES + ("criterion.problem.json", "criterion.certificate.json"):
        require((folder / name).is_file(), "Missing trace input: " + name)
    raw, saved, declaration = (read(folder / n) for n in ("raw_snapshot.json", "snapshot.json", "selection.json"))
    require(not raw.get("errors"), "Raw archive declares incomplete collection")
    settings = declaration["settings"]
    selected, exclusions = select(raw, settings)
    selected["raw_snapshot_sha256"] = sha(folder / "raw_snapshot.json")
    require(selected == saved, "Selected snapshot differs from a replay of raw books")
    require(declaration["selection"] == selected["selection"] and declaration["excluded"] == exclusions,
            "Selection declaration or exclusions differ")
    curves = verify_curves(folder / "snapshot.json", folder / "curves_estimees.csv")
    require(curves["settings"]["symbol"] == settings["symbol"] and
            curves["settings"]["root"] == settings["root"], "Curve and selection roots differ")
    grid, links = rebuild_grid(selected, curves, settings["root"])
    require(grid == read(folder / "F0.exact_grid.json"), "Rational grid differs from raw books and curves")
    problem = Problem.load(read(folder / "criterion.problem.json"))
    certificate = read(folder / "criterion.certificate.json")
    require(problem.scheme == "joint" and certificate["kind"] == "primal", "A joint positive market proof is required")
    require(problem.observations == tuple(tuple(map(Q, r)) for r in grid["observations"]),
            "Certified observations differ, including order or multiplicity")
    expected_source = {"kind": "rational_normalized_grid", "filename": "F0.exact_grid.json",
                       "sha256": sha(folder / "F0.exact_grid.json")}
    require(problem.source == expected_source, "Problem source hash or semantics differ")
    levels = []
    for actual, base in ((problem.times, grid["times"]), (problem.strikes, grid["strikes"])):
        possible = [level for level in range(13) if len(actual) == (len(base)-1)*2**level+1]
        require(len(possible) == 1 and actual == dyadic(base, possible[0]), "Certified axes do not preserve declared geometry")
        levels.append(possible[0])
    checked = verify(problem, certificate, max_nodes)
    audit = direct_check(problem, certificate["prices"])
    require(checked["verified"] and audit["passed"], "Joint market certificate rejected")
    # Find the exact original raw row, not just its contract name.
    raw_rows = {}
    for j, chain in enumerate(raw.get("chains", [])):
        for field in ("calls", "puts"):
            for i, row in enumerate(chain.get(field, [])):
                key = chain.get("symbol"), chain["expiry"], field, row.get("contractSymbol")
                raw_rows.setdefault(key, []).append((j, i, row))
    for link in links:
        selected_row = selected["chains"][link["selected_chain_index"]][link["side_field"]][link["selected_book_index"]]
        key = settings["symbol"], link["expiry"], link["side_field"], link["contract"]
        matches = [(j, i) for j, i, r in raw_rows.get(key, []) if r == selected_row]
        require(len(matches) == 1, "Missing or ambiguous raw contract row: " + link["contract"])
        link.update(raw_chain_index=matches[0][0], raw_book_index=matches[0][1])
    # READY is optional; when supplied, all its named bytes must also be present.
    if (folder / "READY.json").exists():
        for name, expected in read(folder / "READY.json").get("sha256", {}).items():
            require(sha(safe_child(folder, name)) == expected, "Original READY hash differs: " + name)
    result = {"status": "verified_raw_to_joint_certificate", "complete_lineage_verified": True,
              "exact_grid_source_rechecked": True, "selection_replayed": True,
              "nominal_curve_certificate_recomputed": True, "raw_bid_ask_unchanged": True,
              "observations_sha256": observations_hash(problem), "observation_count": len(problem.observations),
              "call_count": sum(l["side_field"] == "calls" for l in links),
              "put_count": sum(l["side_field"] == "puts" for l in links), "shape": list(problem.shape),
              "refinement_levels": levels, "joint_certificate_verified": True,
              "selection_policy_chosen_before_prices_proved": False, "provider_authentication": False,
              "bid_ask_synchronization_certified": False, "normalization_uncertainty_propagated": False,
              "whole_raw_chain_certified": False, "constructive_Yahoo_certificate_inferred": False,
              "replay_metadata": read(folder / "REPLAY_ORIGIN.json") if (folder / "REPLAY_ORIGIN.json").exists() else None,
              "file_sha256": {n: sha(folder/n) for n in FILES + ("criterion.problem.json", "criterion.certificate.json")}}
    return result, links


def audit(accepted_dir, criterion_run, out, logical_grid=None, max_nodes=100000):
    accepted_dir, criterion_run, out = map(Path, (accepted_dir, criterion_run, out))
    inputs = out / "inputs"
    for name in FILES:
        source = Path(logical_grid) if name == "F0.exact_grid.json" and logical_grid else accepted_dir/name
        copy(source, inputs/name)
    for name in ("criterion.problem.json", "criterion.certificate.json"):
        copy(criterion_run/name, inputs/name)
    for name in ("READY.json", "REPLAY_ORIGIN.json"):
        if (accepted_dir/name).exists():
            copy(accepted_dir/name, inputs/name)
    # Preserve any extra files named by the original collector manifest.
    if (inputs / "READY.json").exists():
        for name in read(inputs / "READY.json").get("sha256", {}):
            if not safe_child(inputs, name).exists():
                copy(safe_child(accepted_dir, name), safe_child(inputs, name))
    result, links = inspect(inputs, max_nodes)
    write(out / "lineage.json", result)
    write(out / "observation_links.json", links)
    return result


def verify_audit(folder, max_nodes=100000):
    folder = Path(folder)
    recomputed, links = inspect(folder/"inputs", max_nodes)
    require(recomputed == read(folder/"lineage.json"), "Lineage report differs from recomputation")
    require(links == read(folder/"observation_links.json"), "Observation links differ")
    return {"verified": True, "complete_lineage_verified": True,
            "observation_count": recomputed["observation_count"], "solver_called": False, "network_used": False}
