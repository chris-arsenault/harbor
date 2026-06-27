# H007 — EUR_USD sweep continuation

- Status: active / exploratory
- Edge algorithms: `generic_sweep_continuation`, `mss_confirmed_sweep_continuation`, `early_ny_sweep_continuation`

## Hypothesis

EUR_USD NY-window session sweeps may be continuation events rather than reversal
events, especially when the sweep is early in NY or followed by market-structure
confirmation.

## Economic rationale

The latest broad scan showed several EUR_USD reversal tests with strongly
negative corrected t-statistics. Because the edge framework scores positive
values as reversal, those negative results suggest that some EUR_USD sweeps may
represent genuine repricing or breakout continuation instead of stop-run mean
reversion.

## Current implementation

The continuation algorithms reuse the corresponding sweep-event definitions and
invert the favorable direction:

- `generic_sweep_continuation`: all first session sweeps, continuation-scored.
- `mss_confirmed_sweep_continuation`: MSS-confirmed sweep events, continuation-scored.
- `early_ny_sweep_continuation`: 09:30–10:15 ET sweep events, continuation-scored.

## Confirmatory test

After the 2-year backfill, run EUR_USD only with 15m/30m/60m/120m horizons and
these three continuation algorithms. The hypothesis remains exploratory unless a
continuation row survives clustered standard errors, multiple-test adjustment,
realistic cost sanity checks, and later walk-forward/paper-forward validation.

## Run command after 2-year backfill

```bash
curl -X POST "http://192.168.66.3:30091/api/research/edge/scan" \
  -H "content-type: application/json" \
  -d '{
    "instruments": ["EUR_USD"],
    "algorithms": [
      "generic_sweep_continuation",
      "mss_confirmed_sweep_continuation",
      "early_ny_sweep_continuation"
    ],
    "horizons": [15, 30, 60, 120],
    "window_days": 730
  }'
```
