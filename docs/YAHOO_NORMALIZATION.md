# Yahoo normalization through put-call parity

Introduced in 0.1.3 and retained in **0.1.6**. `estimate-curves` derives curves from a saved snapshot; `verify-curves` reconstructs admissible sets and bounds. Manual `normalize` and constructive calibration remain available. No current interest rate or substituted spot is used to estimate the curves.

## Commands

Use the explicit environment from the root README:

```powershell
& $PyDupire -u -m dupire_joint snapshot `
  --symbols "^SPX,^XSP" --max-expiries 24 --rps 0.5 --retries 3 `
  --out runs/yahoo_snapshot

& $PyDupire -u -m dupire_joint estimate-curves `
  --snapshot runs/yahoo_snapshot/snapshot.json `
  --symbol '^SPX' --root SPXW --min-days 7 --max-days 365 `
  --allow-partial --normalize --out runs/yahoo_SPXW_normalized

& $PyDupire -u -m dupire_joint verify-curves `
  --snapshot runs/yahoo_snapshot/snapshot.json `
  --curves runs/yahoo_SPXW_normalized/curves_estimees.csv `
  --out runs/yahoo_SPXW_verified
```

For XSP use `--symbol '^XSP' --root XSP` and a different output directory. The 7-to-365-day window is explicit and recorded. Maturity uses ACT/365F from the reference time to scheduled index fixing.

Three matched call-put strikes are required by default; the threshold can explicitly be reduced to two. One strike does not identify both `F` and `D`. `--max-pairs 2000` and `--time-limit 120` bound computation per expiry. A budget limit is a computational refusal, not an infeasibility conclusion.

Without `--allow-partial`, any rejected selected expiry blocks normalization with exit code 3. With it, accepted expiries alone are exported and all rejections remain recorded. No accepted curves always yields code 3. Reusing an output directory moves previous exports to `previous_exports`, so failure cannot leave an old `quotes.csv` masquerading as the new output. Startup monitoring remains active.

## Outputs

| File | Contents |
|---|---|
| `curves_estimees.csv` | Expected eight columns, provenance, and certificate filename |
| `curves_estimees.csv.uncertainty.json` | Exact polygons, nominal curves, bounds, times, and exclusions |
| `estimation.json` | Summary and output paths |
| `quotes.csv` | Calls normalized with the nominal curve, for `solve` and `construct` |
| `quotes.csv.uncertainty.csv` | Time, normalized strike, bid, and ask envelopes |
| `quotes.csv.metadata.json` | Normalization assumptions and scope |

Keep the curve CSV and its `.uncertainty.json` together. `normalize` recognizes the latter and propagates uncertainty. A CSV marked `estimated_call_put_intervals` is rejected if the sidecar is missing. Rational curve verification establishes consistency with the declared observations, rather than external validation of market quotes.

## Estimation from observed intervals

For one root and expiry, put `A=D*F`. Each matched strike `K` imposes

$$
L=C_{bid}-P_{ask}\le A-DK\le C_{ask}-P_{bid}=U.
$$

The admissible set intersects these bands with `A>=0,D>=0`. The code uses exact rationals from JSON decimal representations, without midpoint regression or an assumed rate. OCC identifier strikes and dates are checked; SPX, SPXW, and XSP roots remain separate.

Missing, nonfinite, or nonpositive-ask books and unmatched strikes are excluded and listed. Contradictory duplicates and inconsistent contracts reject the expiry. Crossed books reject it under the default policy; [explicit exclusion](CROSSED_BOOK_POLICY.md) is available since 0.1.5. Valid books are not removed merely because they make parity infeasible. No interval is widened or replaced by `lastPrice`.

The extreme matched strikes `k0<kn` imply

$$
\frac{L_0-U_n}{k_n-k_0}\le D\le\frac{U_0-L_n}{k_n-k_0}.
$$

Intersecting with `D>=0`, then using the first band, gives a finite `(A,D)` box containing every positive solution. Exact clipping by all bands retains segments and points. Empty sets are reported. If the closure touches `A=0` or `D=0`, normalization is rejected as insufficiently identified. Otherwise the mean of the vertices supplies a deterministic admissible nominal curve.

Extrema of `A`, `D`, and `F=A/D` occur at vertices when `D>0`. `verify-curves` starts from the original snapshot, reconstructs bands, intersections, and bounds, then checks hashes and the CSV. Hashes bind files rather than authenticate providers.

## Uncertainty propagation

For a raw call,

$$
x=KD/A,\qquad bid_{norm}=C_{bid}/A,\qquad ask_{norm}=C_{ask}/A.
$$

Extrema are evaluated over the **same polygon** in `(A,D)`, without combining unrelated bounds on `F` and `D`. Outputs contain `time_lower/upper`, `x_lower/upper`, `bid_lower/upper`, `ask_lower/upper`, and `_exact` forms. Binary64 bounds are rounded outward; exact rationals retain unrounded endpoints.

These are deterministic marginal envelopes, not confidence intervals. All options in an expiry share the polygon's dependence. Strike envelopes are not a fixed grid to pass directly to `construct`. `quotes.csv` uses the nominal curve without widening its intervals. A certificate at that curve does not certify every curve in the polygon; metadata records `robust_calibration_certified: false`.

## Fixing times and calendar

Recorded conventions are SPX=AM, SPXW=PM, and XSP=PM. The embedded calendar covers 2026 through 2028 using scheduled NYSE holidays and early closes. PM fixing uses the scheduled underlying equity close, 16:00 or 13:00 New York time, rather than the later trading close of non-expiring options. `zoneinfo` handles UTC and daylight-saving conversions; Windows needs `tzdata` when its timezone database is unavailable.

The default reference is the midpoint of the global retrieval window. Its endpoints define the time envelope; they do not bound actual bid-ask staleness. `lastTradeDate` is never used as a bid-ask timestamp. `--asof 2026-10-26T14:00:00Z` sets an explicit alternative reference.

For SPX AM, 09:30 is a scheduled opening reference. Actual SET depends on component openings and need not be published at that instant. The report records this assumption. `T` targets fixing, while payment can occur on the following business day. `D` is inferred from contractual parity, without substituting `exp(-r*T)`.

For fixing outside the embedded calendar, a holiday, or an exceptional change, supply `--settlements PATH.csv` with:

```csv
symbol,root,expiry,fixing_utc,settlement,source
```

Each row must give a timezone-aware instant, AM/PM convention, and source. Expiration dates are not shifted automatically. Calendar assumptions remain conditional on later changes.

## Construct a polynomial from normalized calls

```powershell
& $PyDupire -u -m dupire_joint construct `
  --quotes runs/yahoo_SPXW_normalized/quotes.csv `
  --degree-time 4 --degree-space 10 `
  --sigma-min 0.05 --sigma-max 1.00 `
  --variance-buffer 0.001 --gamma-floor 0.01 `
  --device cpu --threads 4 --out runs/constructive_yahoo
```

These are exploratory settings, without a success guarantee. Retained strikes, intervals, and local bounds require justification. At least two accepted expiries are needed; common normalized-strike unions can be large, so construction budgets apply. Optional CUDA requires a compatible PyTorch installation.

## Primary sources and evidence

- [Cboe XSP fact sheet](https://cdn.cboe.com/resources/xsp/XSP_Options_Fact_Sheet.pdf).
- [NYSE 2026-2028 holiday and early-close calendar](https://ir.theice.com/press/news-details/2025/NYSE-Group-Announces-2026-2027-and-2028-Holiday-and-Early-Closings-Calendar/).
- [yfinance option-chain implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/ticker.py).

The initial module tests used synthetic snapshots and inconsistent cases. The later archived SPXW replay is documented separately in [DATA.md](DATA.md) and [VALIDATION.md](../VALIDATION.md); a historical replay is distinct from a fresh live acquisition.
