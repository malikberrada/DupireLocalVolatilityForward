# Crossed books: strict rejection or explicit exclusion

Introduced in 0.1.5 and retained in **0.1.6**. The historical policy rejects an expiry when any book in the selected root has `bid>ask`, even if that contract has no call-put match. Explicit exclusion permits parity estimation on the remaining valid books without widening intervals.

## Policies

| Option | Behavior |
|---|---|
| `--crossed-policy reject` | Default historical behavior: reject the affected expiry |
| `--crossed-policy exclude` | Remove only crossed books from matching and record contract, bid, ask, and reason |

The opposite member of an excluded pair becomes unmatched; no price is reconstructed. Inconsistent contracts, strike/date/type errors, and contradictory duplicates still reject the expiry. Zero and nonfinite books remain excluded and recorded.

No valid book is removed because it makes parity infeasible. All valid matched bands are intersected together; an empty intersection remains `empty_parity_set`. There is no midpoint regression, `lastPrice` replacement, or hidden tolerance change.

## Diagnose and estimate

```powershell
& $PyDupire -u -m dupire_joint diagnose-snapshot `
  --snapshot runs/yahoo_snapshot_spread/snapshot.json `
  --check-parity --crossed-policy exclude --out runs/yahoo_quality_exclude

& $PyDupire -u -m dupire_joint estimate-curves `
  --snapshot runs/yahoo_snapshot_spread/snapshot.json `
  --symbol '^XSP' --root XSP --min-days 7 --max-days 365 `
  --crossed-policy exclude --allow-partial --normalize `
  --out runs/yahoo_XSP_normalized
```

For SPXW, use `--symbol '^SPX' --root SPXW` and another output directory. Reports retain raw counts, excluded books, and parity status after exclusion. Three pairs are still not a compatibility or calibration guarantee. `construct` needs at least two accepted expiries; polynomial degrees and local bounds require separate justification.

## Certificate scope

Certificates record `settings.crossed_policy` and per-expiry exclusions. `verify-curves` repeats selection from the hash-bound raw snapshot and recomputes exact constraints and bounds. Changing a saved policy without recomputation fails verification when outputs change. Certificates without the field use historical `reject` semantics.

Normalization exports valid calls from accepted expiries and records every omitted call. Metadata includes the policy and `original_snapshot_all_quotes_certified: false`. A certificate covers the retained data after exclusion, not the crossed original books or simultaneous observation times. Coordinate uncertainty envelopes do not certify calibration for every admissible curve.

## Historical 17:05 UTC development report

The earlier supplied report contained 50 root/expiry groups: 42 lacked three pairs and eight were rejected for crossed books. None of those eight had an `empty_parity_set` result, so the report alone did not show that their remaining valid pairs were inconsistent.

| Root | Expiry | Valid pairs |
|---|---|---:|
| SPXW | 2027-03-31 | 5 |
| XSP | 2027-02-19 | 8 |
| XSP | 2027-03-19 | 16 |
| XSP | 2027-05-21 | 3 |
| XSP | 2027-06-17 | 28 |
| XSP | 2027-08-20 | 10 |

XSP also had two pairs on 2026-12-18 and 2027-01-29, below the default threshold; SPX had at most one pair in a group. The summary `snapshot.quality.json` did not contain all underlying bid-ask values, so a post-exclusion intersection could not be computed from that summary alone. The commands above require `snapshot.json`.

This historical diagnostic is not a positive calibration result for that capture. The four archived inputs supporting the later reproducible market illustration are described in [DATA.md](DATA.md).
