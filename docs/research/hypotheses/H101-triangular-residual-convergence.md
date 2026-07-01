# H101 — Triangular residual convergence

- Status: paused / archived; structurally interesting but underpowered
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

## Decision

Pause and archive H101. The no-arbitrage rationale remains structurally interesting, but the cost-aware follow-up did not produce a materially substantiated tradable result: synthetic triangle construction was dead after three-leg costs, while direct EUR_GBP remained underpowered and not strong enough to justify active research attention now.

## Archive location

The cross-instrument residual scan and triangular capture surface remain available under the Lab archived-hypotheses disclosure and explicit API requests for reproducibility.
