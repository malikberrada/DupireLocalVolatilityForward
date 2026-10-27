# Dupire Local Volatility: Joint Feasibility and Observation Preserving Refinement

Research software by **Abdelmalik Berrada** for European option calibration on an irregular common grid. The model imposes observed bid-ask intervals, finite-grid shape restrictions, and bounds on local variance. The `joint` criterion requires **one price vector to satisfy both the forward and backward endpoint stencils**.

The repository includes engine version **0.1.6**, four original Yahoo SPXW snapshots from **26 October 2026**, verified data downloads, processing scripts, exact certificates, and result reproduction. HiGHS supplies the C++ LP solver through a Python wheel; no CMake build is required. The reference workflow runs on CPU. CUDA is optional for surface generation and evaluation; LP solving and exact rational verification run on CPU.

Start with the [documentation index](docs/README.md), the [research results and scope](docs/RESEARCH.md), or the [validation record](VALIDATION.md).

## Quick start

Clone the repository and use **Python 3.12** with the locked dependencies. On Windows, choose a short path, such as `F:\Trading\DupireLocalVolatilityForward`.

```powershell
git clone https://github.com/malikberrada/DupireLocalVolatilityForward.git
Set-Location DupireLocalVolatilityForward
.\scripts\bootstrap.ps1
```

The bootstrap script stops at the first failure. To run the steps manually in PowerShell:

```powershell
py -3.12 -m venv .venv312
$PyDupire = (Resolve-Path .\.venv312\Scripts\python.exe).Path
& $PyDupire -m pip install -r requirements-lock.txt
& $PyDupire -m pip install --no-build-isolation --no-deps -e .
& $PyDupire scripts/download_data.py frozen
& $PyDupire scripts/reproduce.py --profile core --out runs/reproduction
```

Check that each command exits successfully before continuing. Using the explicit `.venv312` executable avoids accidentally invoking another Python installation, including Anaconda. Use a new, empty output directory for each reproduction.

On Linux or macOS:

```bash
git clone https://github.com/malikberrada/DupireLocalVolatilityForward.git
cd DupireLocalVolatilityForward
python3.12 -m venv .venv312
.venv312/bin/python -m pip install -r requirements-lock.txt
.venv312/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv312/bin/python scripts/download_data.py frozen
.venv312/bin/python scripts/reproduce.py --profile core --out runs/reproduction
```

Ubuntu and Windows CPU runs are covered by GitHub Actions. macOS commands are provided but do not constitute a recorded native macOS validation.

## Download the data used in the results

The four raw snapshots are included in `data/raw/yahoo/2026-10-26/`. Their SHA-256 hashes, byte sizes, acquisition times, expiries, and provenance are recorded in [data/manifest.json](data/manifest.json).

The default `frozen` command verifies the bundled bytes and prepares a working copy in `data/downloaded/`, without a network request. To download **the same archived inputs from GitHub**:

```powershell
& $PyDupire scripts/download_data.py frozen --source github
```

The script resolves `origin` and the full local `HEAD` commit, downloads from that immutable commit, and rejects any size or SHA-256 mismatch. When working from a ZIP without Git metadata, supply both arguments explicitly. The manuscript's computation record uses this source commit:

```powershell
& $PyDupire scripts/download_data.py frozen --source github `
  --repo malikberrada/DupireLocalVolatilityForward `
  --ref 173d1cf0c941a14669bb14fd65ac438f7796a0de
```

A fresh Yahoo request returns a **new observation** and cannot reconstruct historical bid-ask quotes:

```powershell
& $PyDupire scripts/download_data.py live --symbol '^SPX' --root SPXW --out runs/new_capture

# Collect new data and validate the two stencils separately.
& $PyDupire -u valider_yahoo.py --symbol '^SPX' --root SPXW --threads 4 --out runs/new_market
```

Every received book and rejection reason is retained. Acquisition may fail when the session is closed, the provider is unavailable, or the observed parity bands are incompatible. A successful download alone does not establish calibration feasibility. See [data and provenance](docs/DATA.md).

## Reproduce the results

| Reference calculation | Recorded result |
|---|---|
| Yahoo `attempt_03` processing | 5 expiries, 59 calls, 62 puts, 121 retained observations, 375 grid nodes |
| Yahoo joint criterion, volatility bounds 5% to 100% | One rational price vector satisfies both stencils |
| Positive-spread separation example | Each stencil is feasible separately; the coarse intersection is empty; one time subdivision makes the joint problem feasible with the same observed intervals |
| Coarse backward endpoint versus refined joint endpoint | Strict price gap `1153/128000000` |
| Additional exact dual certificate | 10 nonzero multipliers; margin `4739/384000000` |
| Constructive result C1 | Certified polynomial and an explicit sufficient refinement threshold |
| Synthetic study | 108 LP models and conclusions reproduced across 12 cases and 3 levels |

The four Yahoo snapshots come from **one trading date**, not four independent days. The synthetic study contains Black-Scholes, discrete, perturbed, and Heston cases; its archived comparisons concern `F0`, forward, and backward, rather than the joint system.

```powershell
# All four archived snapshots and all 12 synthetic cases.
& $PyDupire scripts/reproduce.py --profile all --out runs/full_reproduction

# Rational proof calculations only; Python standard library, no pip installation.
& $PyDupire -I -S analyse_dependances/generer_dependances.py --out runs/proofs
& $PyDupire -I -S runs/proofs/verifier_dependances.py --verify-json runs/proofs/preuves_dependances.json

# Engine, collector, download, and audit tests.
& $PyDupire -m pytest -q
```

`core` runs the 16-step reference workflow: proof reconstruction, original and new polynomial certificates, raw market replay, separate and joint feasibility, provenance checks, and archived study verification. Each run records summaries, environment information, commands, logs, and output hashes. See [reproducibility](docs/REPRODUCIBILITY.md).

The archived study retains **32 numerical feasible witnesses, 70 exact infeasibility certificates for stored binary64 LPs, and 6 indeterminate outcomes**. Those categories are preserved. Solver bases, timings, and chosen witnesses need not be byte-identical.

## Repository layout

| Path | Purpose |
|---|---|
| `src/dupire_joint/` | Engine version 0.1.6 |
| `collect_coherent_yahoo.py`, `valider_yahoo.py` | Acquisition, processing, and bounded validation processes |
| `scripts/` | Download, reproduction, reference checking, and Windows setup |
| `data/` | Frozen raw inputs and provenance manifests |
| `reference/` | Original observations, results, certificates, and reading records |
| `analyse_dependances/` | Standard-library proof generator, exact dual, and original PDF/LaTeX note |
| `audit_apport/` | Argument audits, rational examples, and bibliographic annotations |
| `positionnement_litterature/` | Targeted comparisons and surface exports |
| `docs/` | English usage guides, mathematical statements, and research scope |
| `tests/`, `.github/workflows/` | Automated tests and Ubuntu/Windows CI |

## Scientific scope

C1 is a **sufficient condition**, conditional on obtaining a certified polynomial witness with positive gamma and an interior variance margin. The three-strike characterization and positive-spread example answer precisely stated finite-grid questions. The fixed-grid alternative uses classical convex separation; the refinement estimate uses Taylor bounds and quotient perturbation; the scalar recurrence is the classical implicit midpoint rule.

The results provide a restricted constructive answer to the motivating feasibility question. They do not establish a general data-only criterion for the full Buehler-Ryskin framework or general scientific priority. The Yahoo certificates concern the retained grid and nominal normalization. They do not establish synchronized bid-ask timestamps, feasibility of every raw contract, or a continuous martingale extension.

Rational checks verify the specified identities and certificates. General proofs are written mathematical arguments, rather than formally verified proofs. Original reading annotations retain their recorded validation status. See [research results](docs/RESEARCH.md) and [exact criteria](docs/CRITERE_PROUVE.md).

## Citation and license

Use [CITATION.cff](CITATION.cff) and record the exact Git commit used. The manuscript title is **Dupire Local Volatility: Joint Feasibility and Observation Preserving Refinement**. No SSRN identifier is assigned in this repository.

The author's code is released under the [MIT license](LICENSE). Yahoo data and third-party publications remain subject to their providers' terms; see [DATA.md](docs/DATA.md). Third-party PDFs are optional for numerical reproduction and can be requested with `scripts/download_data.py papers`; available bytes are checked against the recorded hashes.
