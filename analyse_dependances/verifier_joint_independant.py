"""Standalone rational verification: Python standard library only.

Usage: python verifier_joint_independant.py PATH_TO_joint_discriminant
This rebuilds the inequalities from their definitions, not from dupire_joint.
It verifies mathematical separation, not bibliographic priority.
"""
from fractions import Fraction as Q
from pathlib import Path
import hashlib
import json
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(folder, name):
    return json.loads((folder/name).read_text(encoding="utf-8-sig"))


def rebuild(p):
    require(p["format"] == "dupire-exact-grid-problem-v1" and
            p["tail"] == "finite_window_no_zero_tail_anchor" and
            p["normalization"] == "fixed_nominal_F_D_and_settlement_times", "Unsupported model")
    ts, xs = tuple(map(Q, p["times"])), tuple(map(Q, p["strikes"]))
    nt, nx = len(ts), len(xs)
    require(nt >= 2 and nx >= 3 and ts[0] > 0 and xs[0] > 0, "Invalid interior grid")
    require(all(b > a for axis in (ts, xs) for a, b in zip(axis, axis[1:])), "Axes must increase")
    obs = [tuple(map(Q, r)) for r in p["observations"]]
    require(all(t in ts and x in xs and b < a for t, x, b, a in obs), "Invalid positive-spread quotes")
    lo = [max(1-x, Q(0)) for _ in ts for x in xs]
    hi = [Q(1)]*(nt*nx)
    lower, upper = [[Q(x) for x in row] for row in p["vmin"]], [[Q(x) for x in row] for row in p["vmax"]]
    require(len(lower) == len(upper) == nt-1 and
            all(len(a) == len(b) == nx-2 for a, b in zip(lower, upper)), "Invalid local bound dimensions")
    require(all(0 <= a <= b for lr, hr in zip(lower, upper) for a, b in zip(lr, hr)), "Invalid variance bounds")
    rows = []
    def add(label, terms, rhs=0):
        row = {}
        for k, a in terms:
            row[k] = row.get(k, Q(0))+a
        rows.append((label, {k: a for k, a in row.items() if a}, Q(rhs)))
    def gamma(j, i):
        hm, hp = xs[i]-xs[i-1], xs[i+1]-xs[i]
        s = 2/(hm+hp)
        return [(j*nx+i-1, s/hm), (j*nx+i, -s*(1/hm+1/hp)), (j*nx+i+1, s/hp)]
    for j in range(nt):
        for i in range(nx-1):
            a, b = j*nx+i, j*nx+i+1
            add("slope_upper", [(b, Q(1)), (a, Q(-1))])
            add("slope_lower", [(a, Q(1)), (b, Q(-1))], xs[i+1]-xs[i])
        for i in range(1, nx-1):
            add("convexity", [(k, -a) for k, a in gamma(j, i)])
        h = xs[1]-xs[0]
        add("left_chord", [(j*nx, 1/h+1/xs[0]), (j*nx+1, -1/h)], 1/xs[0])
    for j in range(nt-1):
        for i in range(nx):
            add("calendar", [(j*nx+i, Q(1)), ((j+1)*nx+i, Q(-1))])
    require(p["scheme"] in {"none", "forward", "backward", "joint"}, "Unknown scheme")
    selected = ("forward", "backward") if p["scheme"] == "joint" else (p["scheme"],)
    for scheme in selected:
        if scheme == "none":
            continue
        for j in range(nt-1):
            for i in range(1, nx-1):
                g = gamma(j if scheme == "forward" else j+1, i)
                a = (ts[j+1]-ts[j])*xs[i]**2/2
                delta = [((j+1)*nx+i, Q(1)), (j*nx+i, Q(-1))]
                add(scheme+"_local_lower", [(k, a*lower[j][i-1]*v) for k, v in g]+[(k, -v) for k, v in delta])
                add(scheme+"_local_upper", delta+[(k, -a*upper[j][i-1]*v) for k, v in g])
    for t, x, bid, ask in obs:
        k = ts.index(t)*nx+xs.index(x)
        add("ask", [(k, Q(1))], ask)
        add("bid", [(k, Q(-1))], -bid)
    return rows, lo, hi


def check_pair(folder, label, kind):
    p = load(folder, label+".problem.json")
    c = load(folder, label+".certificate.json")
    digest = hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(c["format"] == "dupire-exact-grid-certificate-v1" and c["kind"] == kind and
            c["problem_sha256"] == digest, "Certificate binding failed: "+label)
    rows, lo, hi = rebuild(p)
    if kind == "primal":
        values = list(map(Q, c["prices"]))
        require(len(values) == len(lo) and all(a <= x <= b for a, x, b in zip(lo, values, hi)), "Price box failed")
        slacks = [rhs-sum((v*values[k] for k, v in row.items()), Q(0)) for _, row, rhs in rows]
        require(min(slacks) >= 0, "Primal inequality failed: "+label)
        return p, c, {"kind": kind, "verified": True, "rows": len(rows), "price_bounds": 2*len(lo)}
    require(len(c["rows"]) == len(c["multipliers"]) == len(set(c["rows"])) > 0, "Invalid dual support")
    residual, bound, groups = {}, Q(0), set()
    for i, y in zip(c["rows"], map(Q, c["multipliers"])):
        require(type(i) is int and 0 <= i < len(rows) and y >= 0, "Invalid dual multiplier")
        group, row, rhs = rows[i]
        groups.add(group)
        bound += y*rhs
        for k, a in row.items():
            residual[k] = residual.get(k, Q(0))+y*a
    minimum = sum((a*(lo[k] if a >= 0 else hi[k]) for k, a in residual.items()), Q(0))
    gap = minimum-bound
    require(gap > 0, "No strict separation")
    require({"forward_local_lower", "backward_local_upper"} <= groups, "Expected a genuinely combined separator")
    return p, c, {"kind": kind, "verified": True, "rows": len(rows), "support_size": len(c["rows"]),
                  "separation_margin": str(gap)}


def verify_folder(folder):
    folder = Path(folder)
    proofs, problems = {}, {}
    for name, kind in (("coarse_forward", "primal"), ("coarse_backward", "primal"), ("coarse_joint", "dual")):
        problems[name], _, proofs[name] = check_pair(folder, name, kind)
    joint = problems["coarse_joint"]
    require(joint["scheme"] == "joint", "Wrong combined scheme")
    for scheme in ("forward", "backward"):
        p = problems["coarse_"+scheme]
        require(p["scheme"] == scheme and {k: v for k, v in p.items() if k != "scheme"} ==
                {k: v for k, v in joint.items() if k != "scheme"}, "Observations, bounds or geometry changed between schemes")
    status = load(folder, "result.json")
    refined = (folder/"refined_joint.problem.json").exists()
    if refined:
        p, _, proofs["refined_joint"] = check_pair(folder, "refined_joint", "primal")
        require(p["scheme"] == "joint" and p["observations"] == joint["observations"] and
                p["strikes"] == joint["strikes"], "Refinement changed original quotes or strikes")
        for bound in ("vmin", "vmax"):
            require({Q(x) for row in p[bound] for x in row} == {Q(x) for row in joint[bound] for x in row},
                    "Refinement changed variance bounds")
        level = status["first_materialized_time_level"]
        require(type(level) is int and 1 <= level <= 6, "Invalid time-refinement level")
        t0, t1 = map(Q, joint["times"])
        require(list(map(Q, p["times"])) == [t0+(t1-t0)*Q(i, 2**level) for i in range(2**level+1)],
                "Not the declared time-only dyadic refinement")
    require(status.get("scientific_priority_certified") is False, "Unsupported priority claim")
    return {"status": "independent_joint_separation_verified", "proofs": proofs,
            "individual_feasibility_does_not_imply_joint_feasibility": True,
            "same_quotes_and_bounds": True, "time_refinement_verified": refined,
            "scientific_priority_certified": False, "third_party_imports": False,
            "solver_called": False, "network_used": False}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent/"validation/demo/joint_discriminant"
    print(json.dumps(verify_folder(target), ensure_ascii=False, indent=2))
