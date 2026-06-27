# H005 — Clean-level first-touch sweep

- Status: rejected
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
## Confirmatory result

The larger-sample confirmatory scan did not preserve the exploratory signal:

- 60m: N=102, hit-rate=52.0%, mean=6.4p, corrected t=1.48, effective N=92, adjusted p=0.2088.
- 15m: N=102, hit-rate=53.9%, mean=1.8p, corrected t=0.89, effective N=92, adjusted p=0.5620.
- 30m: N=102, hit-rate=51.0%, mean=1.3p, corrected t=0.45, effective N=92, adjusted p=0.9814.

The earlier high hit-rate / high mean result was not stable when the sample expanded.

## Decision

Reject H005 as a reversal basis. Do not build or optimize strategy variants around
GBP_JPY clean-level first-touch reversal unless a materially different economic
hypothesis is proposed.
