# Validation record for 27 October 2026

This record distinguishes the original local validation from the subsequent GitHub Actions runs. The numerical research inputs and archived receipts remain unchanged.

## Native GitHub Actions validation

The Windows JSON checkpoint fix was validated in [workflow run 40526125833](https://github.com/malikberrada/DupireLocalVolatilityForward/actions/runs/40526125833), head commit `07ee8124dce96535f988831de813af4ef0011061`, then merged into `main` as `173d1cf0c941a14669bb14fd65ac438f7796a0de`.

| Platform | Tests passed | Tests skipped | Core reproduction |
|---|---:|---:|---|
| Ubuntu | 315 | 3 | All 16 steps passed |
| Windows | 316 | 2 | All 16 steps passed |

The workflow installs Python 3.12 and the locked CPU dependencies, tests the source tree, runs the core reproduction from the original raw inputs, and uploads the evidence. The native Windows sharing test runs on Windows; PyTorch and CUDA tests depend on optional runtime availability. These results establish native CPU validation on both platforms. No native CUDA or macOS validation is recorded here.

## Original local and extracted-archive validation

The initial preparation used a fresh Linux Python **3.12.14** virtual environment with the exact versions in `requirements-lock.txt`. The ZIP was then extracted elsewhere and installed into a second independent environment. Both the 315 passing tests and the 16 core steps passed after extraction.

| Check | Recorded result |
|---|---|
| Engine, collector, download, and audit tests | 315 passed, 3 optional or platform-specific skips |
| `core` profile | Proofs, polynomial fit, raw replay, curves, separate and joint criteria, provenance passed |
| `all` profile | Four historical snapshots and twelve synthetic cases recomputed |
| Synthetic comparison | 108/108 LP models and conclusions matched |
| Archived synthetic evidence | 70 exact dual certificates for stored binary64 LPs, 32 numerical primal witnesses, and 6 indeterminate outcomes preserved |
| Additional dual | 10 nonzero terms; exact margin `4739/384000000` |
| Positive-spread separation | Exact gap `1153/128000000` |
| Polynomial construction | Original certificate verified; new fit certified at sufficient level 2 |
| Packaging | Python wheel and source distribution built without CMake |
| Dependency consistency | `pip check` reported no conflicts |
| Windows dependency resolution | All locked Python 3.12 x64 wheels resolved and downloaded before the native CI run |

## Acquisition and interpretation

A fresh Yahoo test on 27 October 2026, **14:12:10 to 14:12:29 UTC**, received six chains without a network error. Parity/quality checks subsequently rejected some expiries. The nonzero exit and retained attempts are expected for rejected inputs; the test did not establish a successful calibration for that new capture. It did not replace the four historical inputs.

Frozen-data downloads verify byte sizes, full-commit URLs, and SHA-256 hashes, and reject altered content. The repository is now published; the original local `validation/` receipts describe its preparation before publication. Reproduction from a pinned GitHub download is documented in [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

Machine-readable local receipts are in `validation/`; original evidence is in `reference/`. New runs generate their own commands, logs, summaries, environment record, and output hashes under the selected output directory. A documentation revision does not relabel historical receipts as new experiments.

Computational validation establishes the stated calculations and software checks. Scientific priority, continuous extension, quote synchronization, and correctness of external market measurements remain separate questions.
