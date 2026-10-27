# Yahoo snapshot quality and expiry selection

Diagnostics and expiry selection were introduced in 0.1.4 and remain available in **0.1.6**. Missing bid-ask books are not reconstructed, zeros are not replaced by `lastPrice`, and book counts do not establish a feasible Dupire surface.

## Diagnose a saved snapshot

```powershell
& $PyDupire -u -m dupire_joint diagnose-snapshot `
  --snapshot runs/yahoo_snapshot/snapshot.json `
  --check-parity --out runs/yahoo_diagnostic
```

`snapshot.quality.json` reports calls, puts, all-zero books, valid books, and matched strikes by root and expiry. Optional parity checking reconstructs exact bands. Enough matched pairs alone does not imply compatible bands. `estimate-curves` writes `input_quality.json` and records each expiry's acceptance or rejection reason. Existing curve certificates remain verifiable.

## Acquire a broader expiry selection

```powershell
& $PyDupire -u -m dupire_joint snapshot `
  --symbols "^SPX,^XSP" --expiry-selection spread `
  --min-days 7 --max-days 365 --max-expiries 24 `
  --rps 0.5 --retries 3 --require-matched-pairs 3 `
  --out runs/yahoo_snapshot_spread
```

`spread` distributes at most 24 dates per symbol across the available window, retaining the first and last. Selection depends on dates before inspecting prices. `front` preserves the historical first-dates behavior and remains the default for older commands.

Download windows use calendar days from the UTC acquisition date. Estimation then applies its own ACT/365F bounds to fixing. Selected expiries and available-date counts are saved in `snapshot.json`.

The command archives the data and writes `snapshot.quality.json`. `--require-matched-pairs 3` returns code 3 if no individual root/expiry has three strikes with valid call and put books. Attempts remain available. The threshold is necessary for the default estimation configuration but guarantees neither parity nor calibration. Counts are not pooled across roots or expiries.

## Historical diagnostic example

An earlier development snapshot was collected on **25 October 2026, 16:29:09.843070 to 16:30:57.750179 UTC**. It is distinct from the four 26 October inputs used for the published replay.

| Root | Contracts | Books with bid=ask=0 | Valid books | Valid matched strikes |
|---|---:|---:|---:|---:|
| SPXW | 6974 | 6900 | 72 | 0 |
| SPX | 560 | 521 | 38 | 0 |
| XSP | 4203 | 4064 | 138 | 4 |

The four XSP pairs belonged to 20 November 2026 and had incompatible discount-factor bands: some required `D>=13377/13250`, others `D<=15667/16500`. The first bound exceeds the second, so the failure was not a solver-tolerance issue.

Root classification and matching were correct for that example. Excluding SPXW's crossed book would still yield no valid pair. The snapshot could not provide the required normalization curves. The rare matched XSP contracts had `lastTradeDate` values from May through September, which are transaction dates rather than bid-ask timestamps. Acquisition on a Sunday alone does not prove the cause of the zero books.

A broader future capture can provide better books without a guarantee. If books remain absent or inconsistent, this framework cannot validate that Yahoo input. It does not silently change provider or instrument family. See [crossed-book policy](CROSSED_BOOK_POLICY.md), [normalization](YAHOO_NORMALIZATION.md), and [the retained research inputs](DATA.md).
