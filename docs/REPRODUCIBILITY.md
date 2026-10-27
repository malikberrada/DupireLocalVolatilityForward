# Reproduction and success criteria

Run commands from a complete repository checkout or source archive, using the Python 3.12 environment in the root [README](../README.md). The engine wheel alone does not include research data or audit scripts. `scripts/reproduce.py` uses the same `sys.executable` for all subprocesses. Main settings are versioned in `config/reproduction.json`.

## Profiles

| Profile | Work performed |
|---|---|
| `proofs` | Rebuild the additional dual from constraints, export written proofs, and check rational identities and certificates |
| `market` | Replay one raw snapshot, reconstruct selection/curves/grid, solve both stencils and their intersection with a common witness |
| `core` | Proofs, original and newly fitted polynomial certificates, `attempt_03`, provenance, discriminating examples, and archived numerical verification |
| `study` | Reverify archived evidence and recompute 12 cases from their original CSV inputs on three levels |
| `all` | `core`, all four historical snapshots, and all 12 recomputed synthetic cases |

```powershell
& $PyDupire scripts/reproduce.py --profile core --out runs/reproduction
& $PyDupire scripts/reproduce.py --profile market --snapshot live_capture --out runs/replay_capture
& $PyDupire scripts/reproduce.py --profile all --out runs/full_reproduction
```

Each command needs a different empty output directory. `live_capture` was recorded on 26 October 2026 at 20:09 UTC and makes no fresh Yahoo request.

For the manuscript's original computation tree, check out commit `173d1cf0c941a14669bb14fd65ac438f7796a0de` in a separate clean directory before installation. To fetch its archived inputs explicitly:

```powershell
& $PyDupire scripts/download_data.py frozen --source github `
  --repo malikberrada/DupireLocalVolatilityForward `
  --ref 173d1cf0c941a14669bb14fd65ac438f7796a0de
```

## Outputs and failure handling

The market workflow checks exact status, observation counts, reconstructed geometry, and agreement with the original grid. `joint` returns one rational vector. The historical `valider_yahoo.py` launcher returns separate forward and backward witnesses. The provenance audit links the joint certificate back to the raw bid-ask records.

A failed step produces a nonzero exit, a `summary.json` with `status: failed`, and a diagnostic log. Nonempty output directories are rejected. Frozen inputs are not overwritten. Downloads are installed at their destination only after size and SHA-256 checks.

Successful runs write `summary.json`, `environment.json`, commands and step logs, and `outputs.sha256.json`. `study` and `all` also write `study_comparison.json`.

## Exact and numerical evidence

Raw bytes, original observations, rational constraints, dual margins, and the specified algebraic identities are checked exactly. A hash binds bytes; it does not authenticate Yahoo.

The new polynomial fit interprets the parameter strings `0.18` and `0.22` exactly before squaring. The original witness used rational representations of recorded binary64 bounds and is verified separately, without substituting the new decimal parameters.

Archived `.npz` models, numerical witnesses, and reports remain in `reference/study/`. Each `report.json` records the original environment. The current lock does not recreate that older CUDA environment. Recalculation replays the **original CSV inputs**, preserving inputs despite rounding differences between CPU and GPU generators.

The archived study contains 108 comparisons: 12 synthetic cases, three refinement levels, and `F0`/forward/backward models. It contains 32 numerical feasible witnesses, 70 exact negative certificates for the stored binary64 LPs, and six indeterminate outcomes. `study` and `all` require the same LP models and conclusions; any difference stops the workflow and is retained in the comparison file. Solver bases, timings, and selected witnesses may vary.

The 12 cases are synthetic Black-Scholes, discrete, perturbed, and Heston experiments. The four Yahoo snapshots are from one date. Reproduction profiles make no Ollama calls and do not accept bibliographic annotations as human-reviewed readings.

## Independent commands

```powershell
# Inspect a completed new Yahoo run without solving or network access.
& $PyDupire valider_yahoo.py --verify runs/new_market

# Reverify only the archived synthetic evidence.
& $PyDupire scripts/verify_reference.py

# Reconstruct rational proofs using only the Python standard library.
& $PyDupire -I -S analyse_dependances/generer_dependances.py --out runs/proofs
& $PyDupire -I -S runs/proofs/verifier_dependances.py --verify-json runs/proofs/preuves_dependances.json

# Generate an additional synthetic study from a seed.
& $PyDupire -m dupire_joint study --device cpu --seed 20261025 --cases 12 --families bs,discrete,corrupt,heston --nt 5 --nx 25 --stagger --levels 0,1,2 --relax --threads 2 --out runs/generated_study

# Recompile the original proof note when pdflatex is installed.
& $PyDupire -I -S analyse_dependances/generer_dependances.py --out runs/proofs_pdf --compile-pdf

# Test the engine and supporting workflows.
& $PyDupire -m pytest -q
```

The seeded study is additional analysis; exact archived comparison uses the original CSVs. Without `--compile-pdf`, the generator copies the supplied PDF. Certificates and rational calculations are still reconstructed. General proof fragments are exported from the authored LaTeX, not discovered or formally proved by the program. The original proof note retains its source language.

## Source provenance

The source archive originally contained engine 0.1.1 at its root and a second `source/` tree at 0.1.6. This repository uses the 0.1.6 tree, matching the supplied 0.1.6 wheel's Python modules. Old patches, backups, bundled wheels, nested archives, caches, and intermediate runs were removed; useful reference inputs, certificates, and tests were retained. `.gitattributes` protects sealed inputs against line-ending conversion.

The [validation record](../VALIDATION.md) separates original local receipts from subsequent native Ubuntu/Windows CI. No GPU is required by the locked CPU workflow. Optional CUDA evaluates or generates surfaces; HiGHS LP solving and rational checking remain on CPU.
