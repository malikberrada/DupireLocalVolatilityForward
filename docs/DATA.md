# Data acquisition and provenance

The raw files are real Yahoo responses obtained through `yfinance.Ticker.option_chain`. They contain calls, puts, underlying information, and request times. [The data manifest](../data/manifest.json) records every expiry, contract count, byte size, and SHA-256 hash.

| Snapshot ID | Acquisition start on 26 October 2026, UTC | Use |
|---|---|---|
| `attempt_01` | 19:31:29 | Replay of the first original snapshot |
| `attempt_02` | 19:31:59 | Replay of the second original snapshot |
| `attempt_03` | 19:32:31 | Main joint-criterion and provenance input |
| `live_capture` | 20:09:06 | Later capture from the same date, retained in the original validation |

These are four observations from one trading date. `live_capture` is an archive identifier, not an instruction to make a live request.

## Frozen downloads and new observations

A bundled copy and a download pinned to a full Git commit contain the same bytes. From the repository root:

```powershell
& $PyDupire scripts/download_data.py frozen
& $PyDupire scripts/download_data.py frozen --source github
```

The first command verifies bundled inputs without network access. The second resolves the repository's `origin` and full `HEAD`, then downloads the archived files from GitHub. For a source ZIP without Git metadata:

```powershell
& $PyDupire scripts/download_data.py frozen --source github `
  --repo malikberrada/DupireLocalVolatilityForward `
  --ref 173d1cf0c941a14669bb14fd65ac438f7796a0de
```

Size and hash checks precede installation at the destination. The default working directory is `data/downloaded/yahoo_20261026/`, with an `acquisition.json` receipt. `--id attempt_03` selects one input; `--out PATH` selects another destination.

Current `option_chain` calls cannot recreate the old bid-ask observations. They are archived as new inputs:

```powershell
& $PyDupire scripts/download_data.py live --symbol '^SPX' --root SPXW --out runs/new_capture
```

## Processing chain

1. The collector records the protocol: symbol `^SPX`, root `SPXW`, strikes from 95% to 105% of spot in multiples of 50, expiries from 14 to 180 calendar days, and at most six requested dates. Spot determines selection; it is not substituted for the forward.
2. All received chains remain in `raw_snapshot.json`. Selection and exclusion reasons are recorded. Retained bid-ask intervals are unchanged. A fixed replay rule does not retrospectively establish that every development choice preceded inspection of prices.
3. Put-call parity determines admissible nominal forward and discount curves. No invented interest rate or dividend series replaces them.
4. Normalization retains 121 call/put intervals on the selected grid. Price boxes, slopes, convexity, and calendars are checked on the declared rational geometry.
5. The historical launcher certifies forward and backward separately. `scripts/reproduce.py` additionally solves the **joint** criterion and checks a single common witness.

The market result is conditional on the nominal curves, retained observations, and annualized volatility bounds of 5% to 100%. Retrieval times and `lastTradeDate` are not authenticated bid-ask timestamps. The result does not cover every raw contract or every curve in the parity uncertainty set.

The embedded acquisition calendar covers 2026 through 2028. The collector checks scheduled regular sessions and refuses a closed session; this does not detect every trading halt or later exceptional schedule change. See [Yahoo normalization](YAHOO_NORMALIZATION.md) for settlement overrides. Project sources include [yfinance](https://github.com/ranaroussi/yfinance) and [Cboe trading hours](https://www.cboe.com/about/hours/us-options).

## Bibliographic inputs

`data/papers_manifest.json` records URLs and hashes for seven original PDF files, including the six indexed full texts used by the 18 corrections. Third-party PDFs are optional for the main numerical reproduction.

```powershell
& $PyDupire scripts/download_data.py papers --id BR2016
```

The downloader checks the recorded version. HTML responses, access failures, or changed PDF bytes cause explicit failure. It does not bypass access controls. Original corrected readings in `reference/readings/` retain their pending validation status. A retrieved text and its hash do not validate an interpretation or establish scientific priority.

## Third-party terms

The repository's MIT license applies to the author's code. Archived Yahoo data remain subject to Yahoo's and the relevant rights holders' terms; they are not declared MIT-licensed. Articles remain the property of their authors or publishers. The snapshots contain no API keys or authentication cookies, and the collector does not request them.
