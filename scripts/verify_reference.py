"""Reverify the archived study/demo models and evidence; no solver or network."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compare_rerun(folder):
    """Compare all 108 study conclusions and saved LPs to the original inputs."""
    rows = []
    for case in sorted((ROOT / "reference/study").glob("case_*")):
        current = Path(folder) / ("refit_" + case.name)
        levels = json.loads((current / "refinement.json").read_text())["runs"]
        for level in levels:
            level_name = "level_%02d" % level["level"]
            old = json.loads((case / level_name / "report.json").read_text())
            new = json.loads((current / level_name / "report.json").read_text())
            if old["inputs"]["quotes_sha256"] != new["inputs"]["quotes_sha256"]:
                raise ValueError("Study rerun changed its original quote data")
            for scheme in ["F0", "forward", "backward"]:
                before = old["F0"] if scheme == "F0" else old["variants"][scheme]
                after = new["F0"] if scheme == "F0" else new["variants"][scheme]
                rows.append({"case": case.name, "level": level["level"], "scheme": scheme,
                             "original": before["conclusion"], "rerun": after["conclusion"],
                             "identical_model": before["lp_sha256"] == after["lp_sha256"]})
    return {"conclusions_compared": len(rows),
            "identical_conclusions": sum(r["original"] == r["rerun"] for r in rows),
            "identical_models": sum(r["identical_model"] for r in rows), "comparisons": rows}


def verify(folder):
    import numpy as np
    from dupire_joint.certificates import verify_certificate
    from dupire_joint.data import Grid, Quotes
    from dupire_joint.engine import independent_audit
    from dupire_joint.model import LP, audit_lp

    counts = {"reports": 0, "exact_dual_certificates": 0, "numeric_primal_witnesses": 0,
              "indeterminate_results_preserved": 0, "artifact_hashes": 0}
    for path in sorted(Path(folder).rglob("report.json")):
        report = json.loads(path.read_text(encoding="utf-8-sig"))
        if report.get("format") != "dupire-joint-report-v1":
            continue
        counts["reports"] += 1
        base = path.parent
        for name, expected in report["artifacts_sha256"].items():
            child = (base / name).resolve()
            if not child.is_relative_to(base.resolve()):
                raise ValueError("Unsafe artifact path")
            if hashlib.sha256(child.read_bytes()).hexdigest() != expected:
                raise ValueError("Archived artifact changed: " + str(child))
            counts["artifact_hashes"] += 1
        inputs = report["inputs"]
        q = Quotes.read(base / "observations.csv")
        if q.digest() != inputs["quotes_sha256"]:
            raise ValueError("Archived quote binding changed")
        grid = Grid(inputs["times"], inputs["strikes"], inputs.get("tail_x"))
        variants = [("none", report["F0"])] + list(report["variants"].items())
        for scheme, result in variants:
            conclusion = result["conclusion"]
            if "model_file" not in result:
                if conclusion == "indeterminate":
                    counts["indeterminate_results_preserved"] += 1
                    continue
                raise ValueError("Missing archived model binding")
            lp = LP.load(base / result["model_file"])
            if lp.digest() != result["lp_sha256"]:
                raise ValueError("Archived model digest differs")
            if result.get("certificate_file"):
                cert = json.loads((base / result["certificate_file"]).read_text(encoding="utf-8-sig"))
                if not verify_certificate(lp, cert)["verified"]:
                    raise ValueError("Invalid archived dual certificate")
                counts["exact_dual_certificates"] += 1
            elif result.get("witness_file"):
                with np.load(base / result["witness_file"]) as saved:
                    prices = saved["prices"]
                tolerance = inputs["audit_tol"]
                if not audit_lp(lp, prices.ravel(), tolerance)["passed"]:
                    raise ValueError("Archived numerical LP witness failed")
                if not independent_audit(prices, grid, q, inputs["vmin"], inputs["vmax"],
                                         "forward" if scheme == "none" else scheme,
                                         scheme != "none", tol=tolerance)["passed"]:
                    raise ValueError("Archived numerical stencil witness failed")
                counts["numeric_primal_witnesses"] += 1
            elif conclusion == "indeterminate":
                counts["indeterminate_results_preserved"] += 1
            else:
                raise ValueError("Unsupported archived conclusion: " + conclusion)
    if not counts["reports"]:
        raise ValueError("No archived study/demo reports found")
    return {"status": "archived_evidence_reverified", **counts,
            "arithmetic": "dual certificates exact for saved binary64 LP; primal witnesses numerical",
            "solver_called": False, "network_used": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder", type=Path, default=ROOT / "reference/study")
    args = p.parse_args()
    print(json.dumps(verify(args.folder), indent=2))
