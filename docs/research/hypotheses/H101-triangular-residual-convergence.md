# H101 — Triangular residual convergence

- Status: active / promising, cost-capture testing
- Algorithm: `tri_eur_gbp_residual_5d`

## Hypothesis

EUR_USD, GBP_USD, and EUR_GBP should remain internally consistent. When the
EUR_GBP cross diverges from EUR_USD / GBP_USD, the residual should converge.

## Economic rationale

Triangular relationships are mechanically anchored by arbitrage. Persistent
residuals may reflect liquidity or timing frictions; convergence is a more
structural object than a naked directional pattern.

## Current implementation

The cross-instrument engine builds the residual
`log(EUR_GBP) - (log(EUR_USD) - log(GBP_USD))`, computes a rolling z-score, and
scores 5-day convergence when |z| is large.

## Latest evidence

The cross-instrument scan flagged this as the strongest signal so far:

- Obs=36, hit-rate=86.1%, mean=2.06 bps, total=74.1 bps, t-stat=4.58.

Strong t-stat and a real no-arbitrage mechanism, but the sample is small and the
per-event edge is tiny in bps, so it is execution-sensitive.

## Next gate — cost-aware capture

A triangular capture engine now tests convergence after costs across a grid of
z-thresholds and holding horizons, in two construction modes:

- `direct_eur_gbp`: trade only EUR_GBP, fading the residual (1 leg).
- `synthetic_triangle`: trade the EUR_GBP vs EUR_USD/GBP_USD residual (3 legs).

Net return is reported in basis points after a configurable per-leg cost. The
hypothesis only advances if net return stays positive with enough events and
holds across a first-half/second-half split.
