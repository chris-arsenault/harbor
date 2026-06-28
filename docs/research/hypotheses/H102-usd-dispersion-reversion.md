# H102 — USD-factor dispersion reversion

- Status: deprioritized / weak signal
- Algorithm: `usd_dispersion_reversion_5d`

## Hypothesis

Most major-pair movement shares a common USD factor. Instruments that diverge
strongly from the cross-sectional basket should mean-revert when the move is
idiosyncratic rather than broad-dollar information.

## Economic rationale

Single-pair dislocations without confirmation from the FX basket are more likely
to be liquidity/flow noise than durable macro repricing.

## Current implementation

The cross-instrument engine computes 5-day returns, subtracts the cross-sectional
mean return, ranks residual under/over-performers, and scores 5-day reversion.

## Latest evidence

Cross-instrument scan: Obs=538, hit=51.7%, mean=1.05 bps, t=0.26 — no meaningful
signal. Deprioritized.
