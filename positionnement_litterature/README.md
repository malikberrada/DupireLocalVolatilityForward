# Positioning the constructive result

Companion version **0.1.0**, used with **dupire-joint 0.1.6**. Install from the repository root using the [main README](../README.md). The tested integrated workflow is `scripts/reproduce.py --profile core`; examples naming historical personal campaigns require their original files.

This module organizes bibliographic annotations, mathematical comparisons, and controlled experiments. It verifies supplied evidence and source links; it does not certify scientific priority. See [mathematical alignment](docs/ALIGNEMENT_MATHEMATIQUE.md) and [the manuscript result map](../docs/RESEARCH.md).

## Run with an existing Yahoo criterion

```powershell
& $PyDupire -u positionnement_litterature/positionner_apport.py `
  --criterion-run runs/criterion --threads 4 --out runs/literature_positioning

# Also bind verification to the original accepted logical grid.
& $PyDupire -u positionnement_litterature/positionner_apport.py `
  --criterion-run runs/criterion `
  --logical-grid reference/market/grids/F0.exact_grid.json `
  --threads 4 --out runs/positioning_with_source
```

The criterion directory must contain `criterion.problem.json` and `criterion.certificate.json` from `criterion --scheme joint`. The existing witness is checked against constraints rebuilt from rational coordinates. No new Yahoo data are substituted.

The default polynomial certificate is a **controlled synthetic example**, distinct from the market record. To use another polynomial:

```powershell
& $PyDupire -u positionnement_litterature/positionner_apport.py `
  --criterion-run runs/criterion `
  --constructive-certificate runs/constructive/constructive.certificate.json `
  --threads 4 --out runs/positioning_my_certificate
```

The report identifies each comparison's data origin. A synthetic polynomial certificate alongside a Yahoo witness does not establish polynomial construction on Yahoo. Market and control experiments are not pooled into a ranking.

## Outputs

| File | Contents |
|---|---|
| `rapport.md` | Positioning, limits, and interpreted numerical results |
| `matrice_litterature.md` | Documented properties with exact versions and locators |
| `references.bib` | BibTeX bibliography |
| `claims.json` | Identified prior components, candidate contribution, and open questions |
| `positionnement.json` | Structured results, audits, and provenance |
| `polynomial_level_*.witness.json` | Same polynomial sampled on refined grids |
| `nodal_level_*/joint.*.json` | Nodal LP problems and exact evidence |
| `kkt2016_slices.witness.json` | Per-expiry prices and coefficients when certified |
| `crw_adapted.witness.json` | Adapted-CRW witness and audit scope |
| `manifest.json` | Stable report-file hashes |

Use a fresh output directory, or omit `--out` for a timestamped name. Long steps and solver progress are shown; HiGHS worker processes are closed at completion.

## Comparators actually executed

| Comparator | Implementation and limits |
|---|---|
| KKTG2016 per expiry, fixed degree | Least-squares objective (24) and constraints (18)-(23), in normalized units. No AIC selection, shared calendar, hard bid-ask intervals, or local bounds. A recorded rational rounding correction is allowed up to `1e-9` uniformly in normalized price. Exact QP optimality is not claimed. |
| CRW objective adapted to `F0` | Four affine functions in (9), `delta0` from (8), and LP epigraph (10). The paper's global arbitrage system is replaced by the project's finite-window shape constraints. Bid-ask constraints remain soft. Numerical feasibility and failed rational reconstruction are distinct outcomes. |
| Bernstein ablation | Same polynomial family, observations, and gamma floor; removes only the two local-bound inequalities while retaining the calendar. This is an ablation, not another published method. |
| Project nodal LP | Same observations and bounds at different refinement levels. The common-grid adaptation does not reproduce all Buehler-Ryskin transport operators. |

Sources are identified in `literature/registry.json`. SANOS, Andreasen-Huge, SSVI, Fengler, Tikhonov, and neural/GP models are not implemented as pricers here. Actual external implementations can be imported using the contract below.

## Independent verification

```powershell
& $PyDupire -u positionnement_litterature/positionner_apport.py --verify runs/literature_positioning
```

This checks hashes, polynomial certificates, refined samples, actual errors, sufficient bounds, nodal certificates, and saved comparator audits. It uses no download or solver and does not reevaluate human source interpretation.

`--skip-experiments` generates only the bibliographic audit and supplied-witness checks. `--levels 0,1,2,3` adds a level; `--max-nodes` limits materialization without invalidating a theoretical threshold.

## Sources and access

The recorded targeted review has a **26 October 2026** cutoff and 15 primary references with preprint versions retained. `literature/search_protocol.json` records actual searches and selection criteria. It is a mechanism-focused targeted review, not an exhaustive systematic review. The later audit module has its own recorded corpus and cutoff.

`?` in the matrix means **not evaluated**. In particular, the retained KKT2024 main-text gap is not filled by its abstract; the abstract establishes prior surface construction but cannot exclude an equivalent theorem. Convergent regularization, global boundaries, moving grids, and soft quotes carry different assumptions.

Optional network operations:

```powershell
& $PyDupire -u positionnement_litterature/positionner_apport.py `
  --skip-experiments --fetch-sources `
  --crossref-query 'Bernstein local volatility bounded calibration refinement' `
  --out runs/positioning_sources
```

Downloads are hashed; access failures are retained. A successful fetch does not become a whole-work reading automatically. Crossref results remain unevaluated candidates and do not replace preprint searches or theorem review.

## Import a real external implementation

The CSV must contain `time,x,price` at **every exact reference-problem node**. Axes are not silently rounded or interpolated. Export while preserving problem coordinates:

```powershell
& $PyDupire positionnement_litterature/exporter_surface.py `
  --problem runs/criterion/criterion.problem.json `
  --pricer my_sanos_model:price --out runs/sanos_surface.csv

& $PyDupire -u positionnement_litterature/positionner_apport.py `
  --criterion-run runs/criterion --external-surface 'SANOS=runs/sanos_surface.csv' `
  --out runs/positioning_with_sanos
```

`price(T,x)` must belong to the actual implementation being compared. The exporter audits returned values; implementation provenance and training time require separate documentation. Returned floating-point prices are interpreted as their exact binary64 rationals.

```powershell
& $PyDupire -m pytest positionnement_litterature/tests -q
```

The module's `validation/` contains the recorded execution summary and checks. Its original generated reports remain historical evidence rather than being relabeled by this documentation update.
