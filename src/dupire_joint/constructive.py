"""Data-driven sufficient certificate and certified dyadic mesh selection.

HiGHS proposes coefficients. Only an exact rational check confers certification.
See docs/CONSTRUCTIVE.md for the theorem, proof, assumptions and limitations.
"""
from __future__ import annotations

from fractions import Fraction as F
import hashlib
import json
from math import comb
from pathlib import Path
import numpy as np
from scipy import sparse

from .bernstein import rational as R, derivative, evaluate, residual_polynomials
from .data import Quotes, Grid
from .engine import independent_audit
from .model import LP, build_lp, audit_lp
from .operators import local_variance
from .progress import atomic_json
from .solver import SolverOptions, SolverSession
from .refinement import quadratic_parameters, quadratic_trial

FORMAT = "dupire-bernstein-constructive-v1"
FIELDS = ("t0", "t1", "x0", "x1", "vmin", "vmax", "buffer", "gamma_floor")


def validate(spec, degree):
    if not (1 <= degree[0] <= 8 and 2 <= degree[1] <= 20):
        raise ValueError("Require time degree in [1,8], space degree in [2,20]")
    if not (0 < spec["t0"] < spec["t1"] and 0 < spec["x0"] < spec["x1"]):
        raise ValueError("Certificate requires T_min>0, x_min>0 and nonempty intervals")
    if not (0 <= spec["vmin"] < spec["vmax"] and
            0 < 2*spec["buffer"] < spec["vmax"]-spec["vmin"] and spec["gamma_floor"] > 0):
        raise ValueError("Require vmin>=0, positive gamma-floor, 0<2*variance-buffer<vmax-vmin")


def quote_records(q):
    return [[R(v) for v in row] for row in zip(q.time, q.x, q.bid, q.ask, q.weight)]


def base_axes(records):
    t = sorted(set(row[0] for row in records))
    x = sorted(set(row[1] for row in records))
    if len(t) < 2 or len(x) < 2:
        raise ValueError("Need at least two distinct maturities and strikes")
    if len(x) == 2:
        x.insert(1, (x[0]+x[1])/2)
    return t, x


def observation_forms(c, spec, records, progress=None):
    unit = F(1) if c.ndim == 2 else np.eye(1, c.shape[2], c.shape[2]-1, dtype=object)[0]
    iterator = progress.bar(records, desc="Exact quote constraints", unit="quote") if progress else records
    for t, x, bid, ask, _ in iterator:
        if not (spec["t0"] <= t <= spec["t1"] and spec["x0"] <= x <= spec["x1"]):
            raise ValueError("Observation outside certificate rectangle")
        val = evaluate(c, (t-spec["t0"])/(spec["t1"]-spec["t0"]),
                       (x-spec["x0"])/(spec["x1"]-spec["x0"]))
        yield val-bid*unit
        yield ask*unit-val


def build_coefficient_lp(spec, degree, records, progress=None):
    """Linear sufficient condition in unknown coefficients, with interior margin.

    Each row is derived exactly, then converted to binary64 for the C++ LP.
    The maximized margin improves rational reconstruction; it is not a proof.
    """
    validate(spec, degree)
    m, n = degree
    count = (m+1)*(n+1)
    affine = np.zeros((count, count+1), dtype=object)
    affine[:, :count] = np.eye(count, dtype=object)
    affine = affine.reshape(m+1, n+1, count+1)
    forms = residual_polynomials(affine, spec)
    obs = list(observation_forms(affine, spec, records, progress))
    forms.append(("quotes", np.array(obs, dtype=object)))
    rows, rhs, groups = [], [], {}
    iterator = progress.bar(forms, desc="Exact coefficient constraints", unit="group") if progress else forms
    for label, block in iterator:
        start = len(rows)
        for row in block.reshape(-1, count+1):
            # Fixed exact normalization, independent of the unknown coefficients.
            scale = max(F(1), abs(row[-1]), sum(abs(v) for v in row[:-1]))
            rows.append([-float(v/scale) for v in row[:-1]]+[1.0])
            rhs.append(float(row[-1]/scale))
        groups[label] = (start, len(rows))
    lower = np.zeros(count+1)
    upper = np.ones(count+1)
    cost = np.zeros(count+1); cost[-1] = -1
    return LP(sparse.csr_matrix(rows), rhs, lower, upper, cost, groups)


def exact_check(coefficients, spec, records):
    c = np.asarray(coefficients, dtype=object)
    if c.ndim != 2:
        raise ValueError("Coefficient matrix must be two-dimensional")
    validate(spec, (c.shape[0]-1, c.shape[1]-1))
    residuals = residual_polynomials(c, spec)
    residuals.append(("quotes", np.array(list(observation_forms(c, spec, records)), dtype=object)))
    minima = {label: min(R(v) for v in block.flat) for label, block in residuals}
    passed = all(v >= 0 for v in minima.values())
    lx, lt = spec["x1"]-spec["x0"], spec["t1"]-spec["t0"]
    constants = {
        "gamma0": min(derivative(c, 1, lx, 2).flat),
        "M3": max(abs(v) for v in derivative(c, 1, lx, 3).flat),
        "M4": max(abs(v) for v in derivative(c, 1, lx, 4).flat),
        "Mtt": max(abs(v) for v in derivative(c, 0, lt, 2).flat),
    }
    return {"passed": passed, "minima": minima, "constants": constants}


def geometry(t, x):
    if len(t)<2 or len(x)<3 or any(b<=a for axis in (t,x) for a,b in zip(axis,axis[1:])):
        raise ValueError("Need increasing common axes with at least two times and three strikes")
    h = [b-a for a, b in zip(x, x[1:])]
    return {"dt": max(b-a for a, b in zip(t, t[1:])), "h": max(h),
            "asymmetry": max((abs(b-a) for a, b in zip(h, h[1:])), default=F(0))}


def mesh_plan(constants, spec, t, x, max_level=64):
    if not isinstance(max_level,int) or not 0 <= max_level <= 256:
        raise ValueError("max-level must be in [0,256]")
    g = geometry(t, x)
    parameters = quadratic_parameters(constants,spec,g)
    common = {"geometry": {k: str(v) for k,v in g.items()},
              "quadratic_criterion": _strings(parameters),
              "finite_threshold_exists_by_theorem": True,
              "observations_unchanged_at_all_levels": True,
              "same_surface_for_forward_and_backward": True}
    trials = []
    for level in range(max_level+1):
        scale = 2**level
        trial = quadratic_trial(parameters,constants,spec,level)
        trials.append({"level": level, "E_gamma": trial["Egamma"], "E_variance": trial["Evariance"],
                       "quadratic_margin": trial["quadratic_margin"],"condition_passed": trial["passed"]})
        if trial["passed"]:
            return {**common,"guaranteed_level": level,
                    "shape": [(len(t)-1)*scale+1, (len(x)-1)*scale+1],
                    "all_further_dyadic_levels": True,"trials": trials}
    return {**common,"guaranteed_level": None, "all_further_dyadic_levels": False,"trials": trials}


def _strings(value):
    if isinstance(value, F):
        return str(value)
    if isinstance(value, dict):
        return {k: _strings(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strings(v) for v in value]
    return value


def verify_payload(payload, quotes=None, max_level=64):
    if payload["format"] != FORMAT:
        raise ValueError("Unknown constructive certificate format")
    spec = {k: R(payload["spec"][k]) for k in FIELDS}
    records = [[R(v) for v in row] for row in payload["observations"]]
    if not records or any(len(row) != 5 for row in records):
        raise ValueError("Malformed observations")
    # The certificate binds to exactly the binary64 observations used by the CLI.
    if any(v != R(float(v)) for row in records for v in row):
        raise ValueError("Observation is not the declared binary64 input value")
    q = Quotes(*[np.array([float(row[k]) for row in records]) for k in range(5)])
    if q.digest() != payload["quotes_sha256"]:
        raise ValueError("Observation digest mismatch")
    if quotes is not None and (quotes.digest() != q.digest() or quote_records(quotes) != records):
        raise ValueError("Certificate does not refer to the provided quotes")
    t, x = base_axes(records)
    if (spec["t0"], spec["t1"], spec["x0"], spec["x1"]) != (t[0], t[-1], x[0], x[-1]):
        raise ValueError("Rectangle does not match observed domain")
    c = np.array([[R(v) for v in row] for row in payload["coefficients"]], dtype=object)
    check = exact_check(c, spec, records)
    plan = mesh_plan(check["constants"], spec, t, x, max_level) if check["passed"] else None
    return {"passed": check["passed"], "arithmetic": "exact rational; no acceptance tolerance",
            "checks": _strings(check), "mesh": plan}


def _float_basis(degree, u):
    return np.stack([comb(degree,i)*u**i*(1-u)**(degree-i) for i in range(degree+1)], axis=1)


def export_mesh(coefficients, spec, records, q, plan, out, args, progress):
    level = plan["guaranteed_level"]
    nt, nx = plan["shape"]
    if nt*nx > args.max_nodes:
        return {"materialized": False, "reason": "max-nodes budget", "nodes": nt*nx,
                "mathematical_mesh_guaranteed": True}
    t0, x0 = base_axes(records)
    def refined(axis):
        # Integer subdivision of original intervals avoids accumulated rounding.
        return [a+(b-a)*F(i, 2**level) for a,b in zip(axis,axis[1:]) for i in range(2**level)]+[axis[-1]]
    with progress.phase("Construct certified mesh", level=level, nodes=nt*nx):
        t, x = refined(t0), refined(x0)
        atomic_json(out/"mesh.exact.json", {"times": [str(v) for v in t], "strikes": [str(v) for v in x]})
        tf, xf = np.array([float(v) for v in t]), np.array([float(v) for v in x])
        if np.any(np.diff(tf) <= 0) or np.any(np.diff(xf) <= 0):
            return {"materialized": False, "reason": "mesh exceeds binary64 coordinate resolution",
                    "nodes": nt*nx, "mathematical_mesh_guaranteed": True}
        grid = Grid(tf,xf)
        grid.quote_indices(q)
        bt = _float_basis(len(coefficients)-1, (grid.times-float(spec["t0"]))/float(spec["t1"]-spec["t0"]))
        bx = _float_basis(len(coefficients[0])-1, (grid.strikes-float(spec["x0"]))/float(spec["x1"]-spec["x0"]))
    from .pricing import select_device
    with progress.phase("Select sample evaluation device", requested=args.device):
        device = select_device(args.device, nt*nx)
    with progress.phase("Evaluate constructed calibration", device=device, nodes=nt*nx):
        c = np.array(coefficients, dtype=float)
        if device in ("cuda", "torch-cpu"):
            import torch
            dev = "cuda" if device == "cuda" else "cpu"
            ts = [torch.as_tensor(a, dtype=torch.float64, device=dev) for a in (bt,c,bx)]
            prices = (ts[0]@ts[1]@ts[2].T).cpu().numpy()
        else:
            prices = bt@c@bx.T
        np.savez_compressed(out/"calibration.samples.npz", prices=prices, times=grid.times, strikes=grid.strikes)
    audits = {}
    for scheme in progress.bar(("forward", "backward"), desc="Independent sample audits", unit="scheme"):
        with progress.phase("Audit exported "+scheme+" samples"):
            model = build_lp(grid,q,float(spec["vmin"]),float(spec["vmax"]),scheme)
            audits[scheme] = {
                "binary64_lp": audit_lp(model, prices.ravel(), args.audit_tol),
                "direct": independent_audit(prices,grid,q,float(spec["vmin"]),float(spec["vmax"]),scheme,tol=args.audit_tol),
            }
            variance, gamma, theta, identified = local_variance(prices, grid, scheme)
            np.savez_compressed(out/(scheme+".witness.npz"), prices=prices, times=grid.times,
                                strikes=grid.strikes, local_variance=variance, gamma=gamma,
                                theta=theta, identified=identified, epsilon=0., full_solution=prices.ravel())
    return {"materialized": True, "device": device, "nodes": nt*nx, "audits": audits,
            "numeric_export_passed": all(a[k]["passed"] for a in audits.values() for k in ("binary64_lp","direct")),
            "semantics": "Exact theorem concerns rational nodes/values; NPZ exports are rounded and audited numerically"}


def construct(args, progress):
    out = Path(args.out)
    with progress.phase("Read observations and constructive hypotheses"):
        if not 0 <= args.max_level <= 256:
            raise ValueError("max-level must be in [0,256]")
        if args.demo:
            # The construction is given ONLY these quotes, never the generator coefficients.
            t = np.array([.25, .375, .625, 1.])
            x = np.array([.98, .985, .993, 1., 1.008, 1.02])
            u, z = t[:, None]-.25, x[None, :]-1
            prices = .06-.5*z+z*z+.2*z**3+.1*z**4+.04*u+.003*u*u
            q = Quotes.from_surface(t,x,prices,2e-5)
        else:
            q = Quotes.read(args.quotes)
        q.write(out/"observations.csv")
        records = quote_records(q)
        t,x = base_axes(records)
        spec = dict(zip(FIELDS, (t[0],t[-1],x[0],x[-1],R(args.sigma_min)**2,R(args.sigma_max)**2,
                                R(args.variance_buffer),R(args.gamma_floor))))
        degree = (args.degree_time, args.degree_space)
        validate(spec, degree)
        if not 1 <= args.max_nodes <= 2_000_000:
            raise ValueError("max-nodes must be in [1,2000000]")
    with progress.phase("Build constructive coefficient LP", degree=list(degree)):
        lp = build_coefficient_lp(spec, degree, records, progress)
        lp.save(out/"construction.lp.npz")
    options = SolverOptions(args.threads,args.time_limit,args.solver_tol,args.method)
    with SolverSession(options,progress) as session:
        result = session.solve(lp, "Construct Bernstein coefficients (HiGHS C++)")
    report = {"format": FORMAT, "quotes_sha256": q.digest(), "LP_sha256": lp.digest(),
              "degree": list(degree), "spec": _strings(spec),
              "solver": {k: v for k,v in result.items() if k not in ("x","ray")},
              "conclusion": "not_certified", "infeasibility_of_general_problem_claimed": False}
    candidate = result.get("x")
    if candidate is not None and np.isfinite(candidate).all():
        np.save(out/"candidate.npy", candidate)
        report["solver_margin"] = float(candidate[-1])
        raw = candidate[:-1].reshape(degree[0]+1,degree[1]+1)
        payload = {"format": FORMAT, "spec": _strings(spec), "quotes_sha256": q.digest(),
                   "observations": _strings(records)}
        for den in progress.bar((10**12, None), desc="Exact rational certification", unit="attempt"):
            with progress.phase("Verify reconstructed polynomial exactly", denominator_limit=den):
                c = [[R(v).limit_denominator(den) if den else R(v) for v in row] for row in raw]
                payload["coefficients"] = _strings(c)
                checked = verify_payload(payload,q,args.max_level)
            if checked["passed"]:
                atomic_json(out/"constructive.certificate.json", payload)
                report["verification"] = checked
                plan = checked["mesh"]
                report["conclusion"] = "continuous_window_certified"
                if plan["guaranteed_level"] is not None:
                    report["conclusion"] = "feasible_from_guaranteed_level"
                    report["samples"] = {"state": "pending"}
                    atomic_json(out/"construction.json", report)
                    try:
                        report["samples"] = export_mesh(c,spec,records,q,plan,out,args,progress)
                    except Exception as exc:
                        report["samples"] = {"state": "failed", "error": str(exc),
                                             "exact_certificate_preserved": True}
                        atomic_json(out/"construction.json", report)
                        raise
                break
            report["last_exact_check"] = checked
    atomic_json(out/"construction.json", report)
    print(json.dumps({"conclusion": report["conclusion"],
                      "guaranteed_level": report.get("verification",{}).get("mesh",{}).get("guaranteed_level"),
                      "numeric_export_passed": report.get("samples",{}).get("numeric_export_passed"),
                      "report": str(out/"construction.json")}, indent=2), flush=True)
    if report["conclusion"] == "not_certified":
        # Useful for scripts: a completed search without certificate is not success.
        progress.event("construct", force=True, state="not_certified", report=str(out/"construction.json"))
        raise SystemExit(3)


def verify_command(args, progress):
    with progress.phase("Verify constructive certificate with exact rational arithmetic"):
        payload = json.loads(Path(args.certificate).read_text(encoding="utf-8"))
        q = Quotes.read(args.quotes) if args.quotes else None
        result = verify_payload(payload,q,args.max_level)
        result["certificate_sha256"] = hashlib.sha256(Path(args.certificate).read_bytes()).hexdigest()
        atomic_json(Path(args.out)/"constructive.verification.json", result)
    print(json.dumps({"passed": result["passed"], "arithmetic": result["arithmetic"],
                      "guaranteed_level": (result.get("mesh") or {}).get("guaranteed_level"),
                      "report": str(Path(args.out)/"constructive.verification.json")},indent=2),flush=True)
    if not result["passed"]:
        raise ValueError("Constructive certificate rejected")


def register(sub, common):
    a = common("construct", "Construct and certify a sufficient calibration from bid/ask data")
    source = a.add_mutually_exclusive_group(required=True)
    source.add_argument("--quotes", help="Normalized CSV: time,x,bid,ask[,weight]")
    source.add_argument("--demo", action="store_true", help="Nonuniform synthetic quotes, no generator passed to fit")
    a.add_argument("--degree-time", type=int, default=3)
    a.add_argument("--degree-space", type=int, default=6)
    a.add_argument("--sigma-min", default="0.18", help="Exact decimal/rational volatility")
    a.add_argument("--sigma-max", default="0.22", help="Exact decimal/rational volatility")
    a.add_argument("--variance-buffer", default="0.001", help="Exact strict interior margin in VARIANCE units")
    a.add_argument("--gamma-floor", default="0.1", help="Exact positive convexity floor")
    a.add_argument("--max-level", type=int, default=64)
    a.add_argument("--max-nodes", type=int, default=50000, help="Export budget; no large mesh allocation above this")
    a.add_argument("--threads", type=int, default=10)
    a.add_argument("--time-limit", type=float, default=120)
    a.add_argument("--solver-tol", type=float, default=1e-9)
    a.add_argument("--audit-tol", type=float, default=1e-8)
    a.add_argument("--method", choices=["choose","simplex","ipm"], default="choose")
    a.add_argument("--device", choices=["auto","cpu","cuda","torch-cpu"], default="auto")
    a.set_defaults(func=construct)
    a = common("verify-construct", "Independently recheck rational polynomial and refinement threshold")
    a.add_argument("--certificate", required=True)
    a.add_argument("--quotes", help="Also bind verification to this original CSV")
    a.add_argument("--max-level", type=int, default=64)
    a.set_defaults(func=verify_command)
