"""Input diagnostics: zero books are missing market information, not prices.

Raw counts do not imply simultaneous parity feasibility. Optional exact
checks use the unchanged 0.1.3 interval estimator, separately by root/expiry.
"""
from __future__ import annotations
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from .curve_estimation import book, matched_pairs, parity_polygon, polygon_summary
from .settlements import ROOTS
from ._io import atomic_json


def select_expiries(expiries, cap, mode="front", min_days=None, max_days=None, asof=None):
    if cap < 1 or mode not in ("front", "spread"):
        raise ValueError("Require max-expiries>=1 and expiry-selection front/spread")
    if min_days is not None and min_days < 0 or max_days is not None and max_days < 0:
        raise ValueError("Snapshot day bounds must be nonnegative")
    if min_days is not None and max_days is not None and min_days > max_days:
        raise ValueError("min-days must not exceed max-days")
    ref = date.fromisoformat(str(asof)[:10]) if asof else date.today()
    eligible = []
    for exp in sorted(set(expiries)):
        days = (date.fromisoformat(exp) - ref).days
        if (min_days is None or days >= min_days) and (max_days is None or days <= max_days):
            eligible.append(exp)
    if len(eligible) <= cap:
        return eligible
    if mode == "front" or cap == 1:
        return eligible[:cap]
    indices = [i * (len(eligible) - 1) // (cap - 1) for i in range(cap)]
    return [eligible[i] for i in indices]


def audit_archive(archive, min_pairs=3, check_parity=False, max_pairs=2000, time_limit=30, crossed_policy="reject"):
    if min_pairs < 2 or max_pairs < min_pairs:
        raise ValueError("Require min-pairs>=2 and max-pairs>=min-pairs")
    if crossed_policy not in ("reject", "exclude"):
        raise ValueError("Unknown crossed policy; choose reject or exclude")
    grouped = {}
    for chain in archive.get("chains", []):
        symbol, expiry = chain.get("symbol"), chain.get("expiry")
        for s, root in ROOTS:
            if symbol == s and any(re.fullmatch(root+r"\d{6}[CP]\d{8}", r.get("contractSymbol", ""))
                 for field in ("calls", "puts") for r in chain.get(field, [])):
                grouped.setdefault((s, root, expiry), []).append(chain)
    groups = []
    for (symbol, root, expiry), chains in sorted(grouped.items()):
        counters = Counter()
        reasons = Counter()
        valid = {"C": {}, "P": {}}
        examples = []
        for chain in chains:
            for side, field in (("C", "calls"), ("P", "puts")):
                for r in chain.get(field, []):
                    if not re.fullmatch(root+r"\d{6}[CP]\d{8}", r.get("contractSymbol", "")):
                        continue
                    counters[field] += 1
                    if r.get("bid") == 0 and r.get("ask") == 0:
                        counters[field+"_zero_book"] += 1
                    try:
                        entry = book(r, expiry, side, root)
                    except (ValueError, TypeError, ZeroDivisionError) as exc:
                        reason = str(exc).split(":")[0]
                        reasons[reason] += 1
                        if len(examples) < 4:
                            examples.append({"contract": r.get("contractSymbol"), "reason": str(exc),
                                             "bid": r.get("bid"), "ask": r.get("ask")})
                        continue
                    if entry is not None:
                        counters[field+"_valid_book"] += 1
                        valid[side][entry["K"]] = entry
        matched = sorted(set(valid["C"]) & set(valid["P"]))
        counts = {k: counters[k] for k in ("calls", "puts", "calls_zero_book", "puts_zero_book",
                                           "calls_valid_book", "puts_valid_book")}
        g = {"symbol": symbol, "root": root, "expiry": expiry, **counts,
             "matched_valid_strikes": len(matched), "matched_strikes": [str(k) for k in matched],
             "invalid_reasons": dict(reasons), "invalid_examples": examples,
             "pair_count_sufficient": len(matched) >= min_pairs,
             "parity_status": "not_checked", "curve_certified": False}
        if check_parity:
            try:
                pairs, excluded, _ = matched_pairs(chains, root, crossed_policy)
                g["excluded_crossed_books"]=[r for r in excluded if r.get("policy")=="explicit_crossed_book_exclusion"]
                if len(pairs) < min_pairs:
                    g["parity_status"] = "insufficient_pairs"
                elif len(pairs) > max_pairs:
                    g["parity_status"] = "budget_exceeded"
                else:
                    summary = polygon_summary(parity_polygon(pairs, time_limit=time_limit))
                    g.update(parity_status="compatible_intervals", parity_bounds=summary["bounds"])
            except (ValueError, TypeError, ZeroDivisionError, TimeoutError) as exc:
                g.update(parity_status="rejected", parity_reason=str(exc))
        groups.append(g)
    roots = []
    for symbol, root in sorted({(g["symbol"], g["root"]) for g in groups}):
        relevant = [g for g in groups if (g["symbol"], g["root"]) == (symbol, root)]
        totals = {key: sum(g[key] for g in relevant) for key in (
            "calls", "puts", "calls_zero_book", "puts_zero_book", "calls_valid_book", "puts_valid_book",
            "matched_valid_strikes")}
        roots.append({"symbol": symbol, "root": root, **totals,
            "expiry_count": len(relevant), "expiries_with_enough_pairs": sum(g["pair_count_sufficient"] for g in relevant),
            "compatible_parity_expiries": sum(g["parity_status"] == "compatible_intervals" for g in relevant)})
    return {"format": "dupire.snapshot.quality.v1", "source": archive.get("source"),
            "started_utc": archive.get("started_utc"), "ended_utc": archive.get("ended_utc"),
            "roots": roots, "groups": groups, "min_pairs": min_pairs, "parity_checked": check_parity,
            "crossed_policy": crossed_policy,
            "parity_scope": "retained valid pairs under the declared crossed-book policy",
            "original_snapshot_all_quotes_certified": False,
            "has_enough_paired_books": any(g["pair_count_sufficient"] for g in groups),
            "has_compatible_parity": any(g["parity_status"] == "compatible_intervals" for g in groups) if check_parity else None,
            "quote_synchronization_verified": False, "calibration_feasibility_claimed": False,
            "note": "Counts refer to recorded books. Transaction dates do not timestamp bid/ask. No book is replaced by lastPrice."}


def audit_file(snapshot_path, out, min_pairs=3, check_parity=False, crossed_policy="reject"):
    p = Path(snapshot_path)
    archive = json.loads(p.read_text(encoding="utf-8-sig"))
    report = audit_archive(archive, min_pairs, check_parity, crossed_policy=crossed_policy)
    report["snapshot_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    atomic_json(out, report)
    return report


def command(args, progress):
    with progress.phase("Audit raw calls, puts and matching strikes"):
        report = audit_file(args.snapshot, Path(args.out)/"snapshot.quality.json", args.min_pairs, args.check_parity,
                            args.crossed_policy)
    for row in report["roots"]:
        progress.event("Input quality", force=True, state="assessed", **row)
    print(json.dumps({"roots": report["roots"], "has_enough_paired_books": report["has_enough_paired_books"],
        "has_compatible_parity": report["has_compatible_parity"],
        "report": str(Path(args.out)/"snapshot.quality.json")}, indent=2), flush=True)


def register(common):
    a = common("diagnose-snapshot", "Count zero/invalid books and same-strike call-put pairs, separated by root")
    a.add_argument("--snapshot", required=True)
    a.add_argument("--min-pairs", type=int, default=3)
    a.add_argument("--check-parity", action="store_true")
    a.add_argument("--crossed-policy", choices=["reject","exclude"], default="reject")
    a.set_defaults(func=command)
