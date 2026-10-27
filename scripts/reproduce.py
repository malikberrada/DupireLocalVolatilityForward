"""Run a checked reproduction from immutable raw data with the current Python."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from download_data import ROOT, acquire_frozen, load


def require(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", choices=["core", "proofs", "market", "study", "all"], default="core")
    p.add_argument("--snapshot", choices=[e["id"] for e in load(ROOT / "data/manifest.json")["files"]], default="attempt_03")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--out", type=Path)
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    args = p.parse_args(argv)
    require(args.threads > 0, "threads must be positive")
    out = (args.out or ROOT / "runs" / ("reproduce_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))).resolve()
    require(not out.exists() or not any(out.iterdir()), "Use a new empty --out directory")
    require(out != ROOT and not ROOT.is_relative_to(out), "Output must not contain the source repository")
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir()
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONHASHSEED="0")
    steps = []
    config = load(ROOT / "config/reproduction.json")
    environment = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                   "device_requested": args.device, "threads": args.threads, "packages": {}}
    for pkg in ("dupire-joint", "numpy", "scipy", "highspy", "pandas", "yfinance", "tzdata", "torch"):
        try:
            environment["packages"][pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            environment["packages"][pkg] = None
    write(out / "environment.json", environment)

    def run(label, arguments, *, isolated=False, seconds=600):
        command = [sys.executable] + (["-I", "-S"] if isolated else ["-u"]) + list(map(str, arguments))
        print("[reproduce] " + label, flush=True)
        started = time.monotonic()
        log = out / "logs" / (label + ".log")
        record = {"step": label, "command": command, "log": str(log.relative_to(out))}
        steps.append(record)
        with log.open("w", encoding="utf-8") as stream:
            try:
                process = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=seconds)
                record["exit_code"] = process.returncode
            finally:
                record["wall_seconds"] = round(time.monotonic() - started, 3)
                write(out / "steps.json", steps)
        if process.returncode:
            tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-18:])
            raise RuntimeError(label + " failed; see " + str(log) + "\n" + tail)

    def cli(label, command, *options):
        target = out / label
        run(label, ["-m", "dupire_joint", command, *options, "--out", target])
        return target

    summary = {"profile": args.profile, "output": str(out), "network_used": False,
               "status": "running", "results": {}, "scientific_priority_certified": False}
    write(out / "summary.json", summary)
    try:
        if args.profile in ("core", "all", "proofs"):
            proof = out / "dependencies"
            run("dependencies_generate", [ROOT / "analyse_dependances/generer_dependances.py", "--out", proof], isolated=True)
            run("dependencies_verify", [proof / "verifier_dependances.py", "--verify-json", proof / "preuves_dependances.json"], isolated=True)
            exact = load(proof / "generation.json")
            require(exact["dual_strict_margin"] == "4739/384000000", "Dual margin changed")
            require(exact["robust_terminal_price_gap"] == "1153/128000000", "Separation gap changed")
            summary["results"]["exact_dependencies"] = {k: exact[k] for k in ("dual_support_size", "dual_strict_margin", "robust_terminal_price_gap")}
        if args.profile in ("core", "all"):
            run("bibliographic_corrections_verify", [ROOT / "audit_apport/rectifier_lectures.py",
                                                    "--verify", ROOT / "reference/readings"])
            cli("original_criterion_verify", "verify-criterion", "--problem", ROOT / "reference/criterion/criterion.problem.json",
                "--certificate", ROOT / "reference/criterion/criterion.certificate.json",
                "--logical-grid", ROOT / "reference/market/grids/F0.exact_grid.json")
            cli("constructive_original_verify", "verify-construct", "--certificate", ROOT / "reference/constructive/constructive.certificate.json",
                "--quotes", ROOT / "reference/constructive/observations.csv")
            construct = cli("constructive_refit", "construct", "--quotes", ROOT / "reference/constructive/observations.csv",
                            "--degree-time", "2", "--degree-space", "4", "--sigma-min", "0.18", "--sigma-max", "0.22",
                            "--threads", args.threads, "--device", args.device)
            record = load(construct / "construction.json")
            require(record["conclusion"] == "feasible_from_guaranteed_level", "Constructive refit lacks a certificate")
            cli("constructive_refit_verify", "verify-construct", "--certificate", construct / "constructive.certificate.json",
                "--quotes", ROOT / "reference/constructive/observations.csv")
            summary["results"]["constructive"] = {"conclusion": record["conclusion"], "guaranteed_level": record["verification"]["mesh"]["guaranteed_level"]}
        if args.profile in ("core", "all", "market"):
            acquisition = acquire_frozen(out / "inputs", ids=None if args.profile == "all" else [args.snapshot])
            write(out / "data_acquisition.json", acquisition)
            for item in acquisition["files"]:
                sid = item["id"]
                market = out / ("market_" + sid)
                run("replay_" + sid, [ROOT / "valider_yahoo.py", "--snapshot", item["path"], "--threads", args.threads,
                                     "--sigma-min", config["sigma_min"], "--sigma-max", config["sigma_max"],
                                     "--strike-step", config["strike_step"], "--out", market])
                run("reverify_" + sid, [ROOT / "valider_yahoo.py", "--verify", market])
                accepted = market / "collecte/accepted"
                exact_grid = accepted / "F0.exact_grid.json"
                criterion = cli("criterion_" + sid, "criterion", "--logical-grid", exact_grid,
                                "--scheme", "joint", "--sigma-min", config["sigma_min"], "--sigma-max", config["sigma_max"],
                                "--threads", args.threads)
                cli("criterion_verify_" + sid, "verify-criterion", "--problem", criterion / "criterion.problem.json",
                    "--certificate", criterion / "criterion.certificate.json", "--logical-grid", exact_grid)
                result = load(criterion / "criterion.json")
                require(result["conclusion"] == config["expected_market"]["conclusion"], "Joint criterion not reproduced")
                expected = config["expected_market"]
                require(result["assumptions"]["observation_count"] == expected["observations"], "Unexpected quote count")
                require(result["assumptions"]["shape"] == expected["grid_shape"], "Unexpected grid geometry")
                # The complete rational geometry must also match the original archived bytes semantically.
                reference_grid = "F0.exact_grid_live.json" if sid == "live_capture" else {
                    "attempt_01": "F0.exact_grid_01.json", "attempt_02": "F0.exact_grid_02.json",
                    "attempt_03": "F0.exact_grid.json"}[sid]
                require(load(exact_grid) == load(ROOT / "reference/market/grids" / reference_grid), "Rebuilt grid differs from the original")
                summary["results"][sid] = {"raw_sha256": item["sha256"], "conclusion": result["conclusion"],
                                            "observations": expected["observations"], "shape": expected["grid_shape"]}
                if args.profile in ("core", "all") and sid == args.snapshot:
                    audit = out / "audit"
                    run("audit", [ROOT / "audit_apport/auditer_apport.py", "--criterion-run", criterion,
                                  "--accepted-dir", accepted, "--out", audit])
                    run("audit_verify", [ROOT / "audit_apport/auditer_apport.py", "--verify", audit])
                    run("audit_independent", [ROOT / "audit_apport/verifier_joint_independant.py", audit / "joint_discriminant"], isolated=True)
                    summary["results"]["audit"] = load(audit / "audit.json")["joint_discriminant"]["status"]
        if args.profile in ("core", "all", "study"):
            run("study_reference_verify", [ROOT / "scripts/verify_reference.py"])
            run("demo_reference_verify", [ROOT / "scripts/verify_reference.py", "--folder", ROOT / "reference/demo"])
            summary["results"]["archived_study"] = "evidence_reverified_with_original_quotes"
        if args.profile in ("all", "study"):
            # A numerical rerun uses each original CSV, bypassing CPU/GPU generator rounding differences.
            for case in sorted((ROOT / "reference/study").glob("case_*")):
                quotes = case / "level_00/observations.csv"
                cli("refit_" + case.name, "solve", "--quotes", quotes, "--levels", "0,1,2", "--relax",
                    "--threads", args.threads, "--sigma-min", "0.18", "--sigma-max", "0.22")
            from verify_reference import compare_rerun
            comparison = compare_rerun(out)
            write(out / "study_comparison.json", comparison)
            require(comparison["conclusions_compared"] == 108 and comparison["identical_conclusions"] == 108
                    and comparison["identical_models"] == 108,
                    "The locked study rerun differs from the archive; inspect study_comparison.json")
            summary["results"]["study_refit"] = {k: comparison[k] for k in
                                                ("conclusions_compared", "identical_conclusions", "identical_models")}
        summary["status"] = "reproduced_and_checked"
    except BaseException as exc:
        summary.update(status="failed", error=str(exc))
        raise
    finally:
        write(out / "summary.json", summary)
        write(out / "outputs.sha256.json", {p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                            for p in sorted(out.rglob("*")) if p.is_file() and p.name != "outputs.sha256.json"})
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("ERROR: " + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
