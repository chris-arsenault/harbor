# H101 — Triangular residual convergence

- Status: active / research engine implemented
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
