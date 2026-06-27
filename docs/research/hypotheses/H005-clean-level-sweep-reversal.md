# H005 — Clean-level first-touch sweep

- Status: active / underpowered promising
- Edge algorithm: `clean_level_sweep_reversal`

## Hypothesis

Sweeps of clean, not-yet-tapped NY-window levels carry more reversal signal than
sweeps of levels already traded around before the sweep.

## Economic rationale

A clean first touch is more likely to represent a discrete liquidity pool. A level
that has already been repeatedly probed may be noisy, partially consumed, or less
informative.

## Current implementation

The algorithm keeps sweeps only when no prior NY-window candle touched the swept
level within the configured sweep buffer.

## Latest evidence

The latest broad scan showed a coherent GBP_JPY cluster:

- 15m: N=19, hit-rate=73.7%, mean=14.7p, corrected t=2.99, effective N=15, adjusted p=0.2694.
- 30m: N=19, hit-rate=78.9%, mean=20.8p, corrected t=2.98, effective N=15, adjusted p=0.2790.
- 60m: N=19, hit-rate=68.4%, mean=19.6p, corrected t=2.23, effective N=15.

This is promising but underpowered. It does not yet pass the edge gate because
effective sample size is too small and the multiple-test-adjusted p-values are
not significant.

## Confirmatory test

After the 2-year backfill, run GBP_JPY only with this algorithm at 15m/30m/60m.
Keep the H005 definition frozen. Target at least 30 effective NY trading-day
clusters, preferably 50+, before considering entry/exit capture tests.

## Run command after 2-year backfill

```bash
curl -X POST "http://192.168.66.3:30091/api/research/edge/scan" \
  -H "content-type: application/json" \
  -d '{
    "instruments": ["GBP_JPY"],
    "algorithms": ["clean_level_sweep_reversal"],
    "horizons": [15, 30, 60],
    "window_days": 730
  }'
```
