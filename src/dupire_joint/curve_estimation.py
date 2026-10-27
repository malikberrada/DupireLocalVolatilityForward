"""Bid/ask put-call parity: exact two-dimensional feasible sets.

A = D F and L_i <= A - D K_i <= U_i. No regression, rate prior, quote
widening, spot substitution or statistical-confidence claim is used.
"""
from __future__ import annotations
from contextlib import nullcontext
import csv
from datetime import date, timedelta
from fractions import Fraction as Q
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import time
import numpy as np
from .data import Quotes
from ._io import atomic_json
from .settlements import ROOTS, aware_utc, scheduled_fixing, load_overrides

FORMAT = "dupire.curves.interval.v1"
FIELDS = ["symbol", "root", "expiry", "time", "forward", "discount", "style", "settlement",
          "source", "uncertainty_certificate"]
SECONDS_YEAR = 365 * 86400


def rational(value):
    if value is None or isinstance(value, bool):
        raise ValueError("Missing or nonnumeric value")
    return Q(str(value))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def years(delta):
    us = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    return Q(us, 1000000 * SECONDS_YEAR)


def book(row, expiry, side, root):
    name = row.get("contractSymbol", "")
    m = re.fullmatch(r"([A-Z]+)(\d{6})([CP])(\d{8})", name)
    if not m or m[1] != root:
        return None
    if m[2] != date.fromisoformat(expiry).strftime("%y%m%d") or m[3] != side:
        raise ValueError("contract_expiry_or_side_mismatch: " + name)
    k, b, a = (rational(row.get(f)) for f in ("strike", "bid", "ask"))
    if k != Q(int(m[4]), 1000):
        raise ValueError("contract_strike_mismatch: " + name)
    if k <= 0 or b < 0 or a <= 0:
        raise ValueError("invalid_strike_or_book: " + name)
    if b > a:
        raise ValueError("crossed_book: " + name)
    return {"contract": name, "K": k, "bid": b, "ask": a}


def matched_pairs(chains, root, crossed_policy="reject"):
    if crossed_policy not in ("reject", "exclude"):
        raise ValueError("Unknown crossed policy; choose reject or exclude")
    books = {"C": {}, "P": {}}
    excluded = []
    fatal = []
    for chain in chains:
        for side, field in (("C", "calls"), ("P", "puts")):
            for row in chain.get(field, []):
                try:
                    r = book(row, chain["expiry"], side, root)
                except (ValueError, TypeError, ZeroDivisionError) as exc:
                    message = str(exc)
                    # Explicitly excluding an invalid book does not repair it or
                    # exclude any other, valid interval on consistency grounds.
                    if message.startswith("crossed_book:") and crossed_policy == "exclude":
                        excluded.append({"contract": row.get("contractSymbol"), "reason": message,
                                         "bid": row.get("bid"), "ask": row.get("ask"),
                                         "policy": "explicit_crossed_book_exclusion"})
                    elif any(s in message for s in ("crossed_book", "mismatch")):
                        fatal.append(message)
                    else:
                        excluded.append({"contract": row.get("contractSymbol"), "reason": message})
                    continue
                if r is None:
                    continue
                prev = books[side].get(r["K"])
                if prev is not None and prev != r:
                    fatal.append("ambiguous_duplicate: " + r["contract"])
                books[side][r["K"]] = r
    if fatal:
        raise ValueError("; ".join(fatal[:8]))
    pairs = []
    for k in sorted(set(books["C"]) & set(books["P"])):
        c, p = books["C"][k], books["P"][k]
        pairs.append((k, c["bid"] - p["ask"], c["ask"] - p["bid"]))
    unmatched = sorted(set(books["C"]) ^ set(books["P"]))
    return pairs, excluded, [str(k) for k in unmatched]


def unique_cycle(points):
    result = []
    for p in points:
        if not result or p != result[-1]:
            result.append(p)
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def clip(poly, a, d, rhs):
    """Intersect a closed convex polygon (including segments/points) exactly."""
    if not poly:
        return []
    output = []
    prev = poly[-1]
    vp = a * prev[0] + d * prev[1] - rhs
    for cur in poly:
        vc = a * cur[0] + d * cur[1] - rhs
        if (vp <= 0) != (vc <= 0):
            t = vp / (vp - vc)
            output.append(tuple(prev[j] + t * (cur[j] - prev[j]) for j in (0, 1)))
        if vc <= 0:
            output.append(cur)
        prev, vp = cur, vc
    return unique_cycle(output)


def parity_polygon(pairs, progress=None, time_limit=120):
    """The two extreme strikes bound a box containing ALL positive solutions."""
    if len(pairs) < 2 or pairs[0][0] >= pairs[-1][0]:
        raise ValueError("At least two distinct matched strikes are required")
    k0, l0, u0 = pairs[0]
    kn, ln, un = pairs[-1]
    d0 = max(Q(0), (l0 - un) / (kn - k0))
    d1 = (u0 - ln) / (kn - k0)
    a0 = max(Q(0), l0 + d0 * k0)
    a1 = u0 + d1 * k0
    if d1 <= 0 or d0 > d1 or a1 <= 0 or a0 > a1:
        return []
    poly = unique_cycle([(a0, d0), (a1, d0), (a1, d1), (a0, d1)])
    start = time.monotonic()
    iterable = progress.bar(pairs, desc="Exact parity strips", unit="pair") if progress else pairs
    try:
        for k, lo, hi in iterable:
            if time.monotonic() - start > time_limit:
                raise TimeoutError("Exact parity intersection reached its time limit; no conclusion")
            poly = clip(clip(poly, Q(1), -k, hi), Q(-1), k, -lo)
            if not poly:
                break
    finally:
        if progress:
            iterable.close()
    return poly


def polygon_summary(poly):
    if not poly:
        raise ValueError("empty_parity_set")
    if min(p[0] for p in poly) <= 0 or min(p[1] for p in poly) <= 0:
        raise ValueError("unidentified_positive_normalization: A or D can approach zero")
    a = sum(p[0] for p in poly) / len(poly)
    d = sum(p[1] for p in poly) / len(poly)
    # Positive-denominator linear-fractional functions attain extrema at vertices.
    vals = {"prepaid_forward": [p[0] for p in poly], "discount": [p[1] for p in poly],
            "forward": [p[0] / p[1] for p in poly]}
    return {"vertices_A_D": [[str(v) for v in p] for p in poly],
            "nominal": {"prepaid_forward": str(a), "discount": str(d), "forward": str(a / d)},
            "bounds": {k: [str(min(v)), str(max(v))] for k, v in vals.items()}}


def observation_times(archive, explicit=None):
    if explicit:
        at = aware_utc(explicit)
        return at, at, at, "explicit_reference_time"
    if not archive.get("started_utc") or not archive.get("ended_utc"):
        raise ValueError("Snapshot needs started_utc/ended_utc, or provide --asof with an offset")
    start, end = (aware_utc(archive[k]) for k in ("started_utc", "ended_utc"))
    if end < start:
        raise ValueError("Snapshot ended_utc precedes started_utc")
    return start + (end - start) / 2, start, end, "retrieval_window_not_bid_ask_time"


def estimate_archive(archive, settings, overrides=None, progress=None):
    symbol, root = settings["symbol"], settings["root"]
    if (symbol, root) not in ROOTS:
        raise ValueError("Unsupported symbol/root combination")
    at, start, end, time_source = observation_times(archive, settings.get("asof"))
    grouped = {}
    for chain in archive.get("chains", []):
        if chain.get("symbol") == symbol and any(
            re.match(r"^" + root + r"\d{6}[CP]\d{8}$", r.get("contractSymbol", ""))
            for field in ("calls", "puts") for r in chain.get(field, [])):
            grouped.setdefault(chain["expiry"], []).append(chain)
    groups = []
    for expiry, chains in sorted(grouped.items()):
        record = {"symbol": symbol, "root": root, "expiry": expiry, "status": "rejected"}
        phase = progress.phase("Estimate " + root + " " + expiry) if progress else nullcontext()
        with phase:
            try:
                fixing = scheduled_fixing(symbol, root, expiry, overrides)
                delta = aware_utc(fixing["fixing_utc"]) - at
                t = years(delta)
                tlo = years(aware_utc(fixing["fixing_utc"]) - end)
                thi = years(aware_utc(fixing["fixing_utc"]) - start)
                record.update(fixing=fixing, time=str(t), time_range=[str(tlo), str(thi)])
                if t <= 0 or tlo <= 0 or not Q(settings["min_days"]) / 365 <= t <= Q(settings["max_days"]) / 365:
                    record.update(status="outside_window", reason="outside_requested_maturity_window")
                    groups.append(record)
                    continue
                pairs, excluded, unmatched = matched_pairs(chains, root, settings.get("crossed_policy", "reject"))
                record.update(pair_count=len(pairs), excluded_books=excluded, unmatched_strikes=unmatched)
                if len(pairs) < settings["min_pairs"]:
                    raise ValueError("insufficient_matched_strikes")
                if len(pairs) > settings["max_pairs"]:
                    raise ValueError("pair_budget_exceeded; raise --max-pairs explicitly")
                poly = parity_polygon(pairs, progress, settings["time_limit"])
                record.update(polygon_summary(poly))
                record["status"] = "accepted"
            except (ValueError, TypeError, ZeroDivisionError, TimeoutError) as exc:
                record["reason"] = str(exc)
        groups.append(record)
    accepted = [g for g in groups if g["status"] == "accepted"]
    rejected = [g for g in groups if g["status"] == "rejected"]
    return {"format": FORMAT, "settings": settings, "settlement_overrides": overrides or {},
            "asof_utc": at.isoformat(), "asof_range_utc": [start.isoformat(), end.isoformat()],
            "time_source": time_source, "day_count": "ACT/365F_to_scheduled_index_fixing",
            "groups": groups, "accepted_count": len(accepted), "rejected_count": len(rejected),
            "outside_window_count": sum(g["status"] == "outside_window" for g in groups),
            "all_selected_passed": bool(accepted) and not rejected,
            "arithmetic": "exact rationals of JSON decimal representations",
            "uncertainty_semantics": "deterministic feasible-set bounds; not confidence intervals",
            "quote_synchronization_verified": False, "robust_calibration_certified": False}


def curves_text(certificate, certificate_name):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for g in certificate["groups"]:
        if g["status"] != "accepted":
            continue
        n = g["nominal"]
        writer.writerow({"symbol": g["symbol"], "root": g["root"], "expiry": g["expiry"],
            "time": repr(float(Q(g["time"]))), "forward": repr(float(Q(n["forward"]))),
            "discount": repr(float(Q(n["discount"]))), "style": "european",
            "settlement": g["fixing"]["settlement"], "source": "estimated_call_put_intervals",
            "uncertainty_certificate": certificate_name})
    return buf.getvalue()


def verify_curves(snapshot_path, curves_path, progress=None):
    sidecar = Path(str(curves_path) + ".uncertainty.json")
    cert = json.loads(sidecar.read_text(encoding="utf-8"))
    if cert.get("format") != FORMAT or cert.get("snapshot_sha256") != sha(snapshot_path):
        raise ValueError("Curve certificate format or snapshot hash mismatch")
    if cert.get("curves_sha256") != sha(curves_path):
        raise ValueError("Curve CSV hash mismatch")
    expected_text = curves_text(cert, sidecar.name).encode("utf-8")
    if hashlib.sha256(expected_text).hexdigest() != cert["curves_sha256"]:
        raise ValueError("Curve CSV disagrees with the exact nominal curve")
    recomputed = estimate_archive(json.loads(Path(snapshot_path).read_text(encoding="utf-8-sig")),
                                  cert["settings"], cert["settlement_overrides"], progress)
    for k, v in recomputed.items():
        if cert.get(k) != v:
            raise ValueError("Curve certificate check failed: " + k)
    if not cert["accepted_count"] or (cert["rejected_count"] and not cert.get("allow_partial")):
        raise ValueError("No complete accepted curve set; --allow-partial was not selected")
    return cert


def outward(value, lower):
    """Export a binary64 bound rounded outward, without decimal interval claims."""
    f = float(value)
    if not math.isfinite(f):
        raise ValueError("Normalization exceeds binary64 range")
    r = Q.from_float(f)
    if (lower and r > value) or (not lower and r < value):
        f = math.nextafter(f, -math.inf if lower else math.inf)
    return f


def normalize_estimated(snapshot_path, curves_path, symbol, root, out, progress=None):
    cert = verify_curves(snapshot_path, curves_path, progress)
    if (symbol, root) != (cert["settings"]["symbol"], cert["settings"]["root"]):
        raise ValueError("Estimated curves belong to a different symbol/root")
    archive = json.loads(Path(snapshot_path).read_text(encoding="utf-8-sig"))
    accepted = {g["expiry"]: g for g in cert["groups"] if g["status"] == "accepted"}
    data, envelopes, excluded = [], [], []
    seen = set()
    for chain in archive.get("chains", []):
        if chain.get("symbol") != symbol or chain.get("expiry") not in accepted:
            continue
        g = accepted[chain["expiry"]]
        A, D = (Q(g["nominal"][k]) for k in ("prepaid_forward", "discount"))
        poly = [tuple(Q(v) for v in p) for p in g["vertices_A_D"]]
        amin, amax = (Q(v) for v in g["bounds"]["prepaid_forward"])
        for row in chain.get("calls", []):
            try:
                r = book(row, chain["expiry"], "C", root)
            except (ValueError, TypeError, ZeroDivisionError) as exc:
                excluded.append({"contract": row.get("contractSymbol"), "reason": str(exc)})
                continue
            if r is None or r["contract"] in seen:
                continue
            seen.add(r["contract"])
            k, b, a = (r[v] for v in ("K", "bid", "ask"))
            t = Q(g["time"])
            data.append([float(t), float(k * D / A), float(b / A), float(a / A)])
            xs = [k * d / aa for aa, d in poly]
            bounds = {"time": tuple(Q(v) for v in g["time_range"]),
                      "x": (min(xs), max(xs)), "bid": (b / amax, b / amin),
                      "ask": (a / amax, a / amin)}
            env = {"contract": r["contract"], "expiry": chain["expiry"]}
            for key, (lo, hi) in bounds.items():
                env[key + "_lower"] = repr(outward(lo, True))
                env[key + "_upper"] = repr(outward(hi, False))
                env[key + "_lower_exact"] = str(lo)
                env[key + "_upper_exact"] = str(hi)
            envelopes.append(env)
    if not data:
        raise ValueError("No usable calls for accepted curves")
    ar = np.asarray(data)
    q = Quotes(ar[:, 0], ar[:, 1], ar[:, 2], ar[:, 3])
    out = Path(out)
    q.write(out)
    envpath = Path(str(out) + ".uncertainty.csv")
    with envpath.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(envelopes[0]))
        w.writeheader()
        w.writerows(envelopes)
    atomic_json(str(out) + ".metadata.json", {
        "symbol": symbol, "root": root, "quote_count": len(data), "quotes_sha256": q.digest(),
        "snapshot_sha256": cert["snapshot_sha256"], "curve_csv": str(curves_path),
        "curve_certificate": str(curves_path) + ".uncertainty.json", "envelopes": str(envpath),
        "forward_discount_uncertainty_propagated": True,
        "uncertainty_scope": "marginal coordinate envelopes; shared A,D polygon retained",
        "conditional_on_supplied_normalization": True, "nominal_curve_is_estimated": True,
        "crossed_policy": cert["settings"].get("crossed_policy", "reject"),
        "original_snapshot_all_quotes_certified": False,
        "calibration_scope": "valid calls of accepted expiries; every skipped book is recorded",
        "synchronized_bid_ask_not_certified": True, "robust_calibration_certified": False,
        "excluded_books": excluded, "excluded_expiries": [g for g in cert["groups"] if g["status"] != "accepted"],
        "curve_bounds_arithmetic": cert["arithmetic"],
        "export_arithmetic": "nominal binary64; interval endpoints rounded outward; exact endpoints also exported"})
    return q


def estimate_command(args, progress):
    if (args.min_pairs < 2 or args.max_pairs < args.min_pairs
            or not all(math.isfinite(v) for v in (args.min_days, args.max_days))
            or not 0 <= args.min_days < args.max_days):
        raise ValueError("Require min-pairs>=2, max-pairs>=min-pairs, 0<=min-days<max-days")
    if not math.isfinite(args.time_limit) or args.time_limit <= 0:
        raise ValueError("time-limit must be finite and positive")
    out = Path(args.out)
    # Relocate earlier successful exports before a new attempt. A failed repeat
    # must never leave the old quotes at the path advertised for this run.
    owned = [out / name for name in ("curves_estimees.csv", "curves_estimees.csv.uncertainty.json",
              "quotes.csv", "quotes.csv.uncertainty.csv", "quotes.csv.metadata.json", "estimation.json", "input_quality.json")]
    previous = [p for p in owned if p.exists()]
    if previous:
        backup = out / "previous_exports" / str(time.time_ns())
        backup.mkdir(parents=True)
        for path in previous:
            shutil.move(str(path), str(backup / path.name))
    settings = {"symbol": args.symbol, "root": args.root, "min_pairs": args.min_pairs,
                "max_pairs": args.max_pairs, "min_days": str(args.min_days), "max_days": str(args.max_days),
                "time_limit": args.time_limit, "asof": args.asof,
                "crossed_policy": getattr(args,"crossed_policy","reject")}
    with progress.phase("Read snapshot and fixing conventions"):
        archive = json.loads(Path(args.snapshot).read_text(encoding="utf-8-sig"))
        overrides = load_overrides(args.settlements)
    cert = estimate_archive(archive, settings, overrides, progress)
    from .market_quality import audit_archive
    quality=audit_archive(archive,args.min_pairs,crossed_policy=settings["crossed_policy"])
    atomic_json(out/"input_quality.json",quality)
    for g in cert["groups"]:
        raw=next((r for r in quality["groups"] if (r["symbol"],r["root"],r["expiry"]) ==
                  (g["symbol"],g["root"],g["expiry"])),{})
        progress.event("Curve result "+g["root"]+" "+g["expiry"],force=True,state=g["status"],
                       paired_valid_strikes=raw.get("matched_valid_strikes",0),reason=g.get("reason",""),
                       excluded_crossed_books=sum(e.get("policy")=="explicit_crossed_book_exclusion"
                                                   for e in g.get("excluded_books",[])))
    cert.update(snapshot_sha256=sha(args.snapshot), allow_partial=args.allow_partial)
    curves = out / "curves_estimees.csv"
    sidecar = Path(str(curves) + ".uncertainty.json")
    curves.write_bytes(curves_text(cert, sidecar.name).encode("utf-8"))
    cert["curves_sha256"] = sha(curves)
    atomic_json(sidecar, cert)
    ready = bool(cert["accepted_count"]) and (cert["all_selected_passed"] or args.allow_partial)
    report = {"accepted_count": cert["accepted_count"], "rejected_count": cert["rejected_count"],
              "outside_window_count": cert["outside_window_count"], "curves": str(curves),
              "conclusion": "ready_partial" if ready and cert["rejected_count"] else "ready" if ready else "not_ready",
              "robust_calibration_certified": False, "quote_synchronization_verified": False}
    atomic_json(out / "estimation.json", report)
    if ready and args.normalize:
        try:
            with progress.phase("Verify curves and propagate normalization uncertainty"):
                q = normalize_estimated(args.snapshot, curves, args.symbol, args.root, out / "quotes.csv", progress)
        except Exception as exc:
            report.update(conclusion="normalization_failed", error=str(exc))
            atomic_json(out / "estimation.json", report)
            raise
        report.update(quotes=str(out / "quotes.csv"), quote_count=len(q.time))
    atomic_json(out / "estimation.json", report)
    print(json.dumps(report, indent=2), flush=True)
    if not ready:
        raise SystemExit(3)


def verify_command(args, progress):
    with progress.phase("Recompute exact parity sets and curve bounds"):
        cert = verify_curves(args.snapshot, args.curves, progress)
    report = {"passed": True, "accepted_count": cert["accepted_count"], "arithmetic": cert["arithmetic"],
              "quote_synchronization_verified": False, "robust_calibration_certified": False}
    atomic_json(Path(args.out) / "curves.verification.json", report)
    print(json.dumps(report, indent=2), flush=True)


def register(common):
    a = common("estimate-curves", "Estimate F,D and ACT/365F fixing maturities from call/put bid-ask intervals")
    a.add_argument("--snapshot", required=True)
    a.add_argument("--symbol", choices=["^SPX", "^XSP"], required=True)
    a.add_argument("--root", choices=["SPX", "SPXW", "XSP"], required=True)
    a.add_argument("--asof", help="Explicit reference timestamp with timezone; default: retrieval-window midpoint")
    a.add_argument("--settlements", help="Override CSV: symbol,root,expiry,fixing_utc,settlement,source")
    a.add_argument("--min-days", type=float, default=7)
    a.add_argument("--max-days", type=float, default=365)
    a.add_argument("--min-pairs", type=int, default=3)
    a.add_argument("--max-pairs", type=int, default=2000)
    a.add_argument("--time-limit", type=float, default=120)
    a.add_argument("--allow-partial", action="store_true", help="Explicitly permit exporting only accepted expiries")
    a.add_argument("--crossed-policy", choices=["reject","exclude"], default="reject",
                   help="reject: fail expiry on a crossed book; exclude: record and skip only invalid crossed books")
    a.add_argument("--normalize", action="store_true", help="Also export nominal quotes and normalization interval envelopes")
    a.set_defaults(func=estimate_command)
    a = common("verify-curves", "Recompute exact parity bounds and bind them to snapshot and curve CSV")
    a.add_argument("--snapshot", required=True)
    a.add_argument("--curves", required=True)
    a.set_defaults(func=verify_command)
