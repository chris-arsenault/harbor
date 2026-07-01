# H102 — USD-factor dispersion reversion

- Status: rejected / no material corrected signal
- Algorithm: `usd_dispersion_reversion_5d`

## Hypothesis

Most major-pair movement shares a common USD factor. Instruments that diverge
strongly from the cross-sectional basket should mean-revert when the move is
idiosyncratic rather than broad-dollar information.

## Economic rationale

Single-pair dislocations without confirmation from the FX basket are more likely
to be liquidity/flow noise than durable macro repricing.

## Current implementation

The corrected cross-instrument engine computes 5-day returns, normalizes USD
exposure so `XXX_USD` and `USD_XXX` pairs are comparable, subtracts the
cross-sectional mean USD-factor return, ranks instruments by residual
under/over-performance, and scores 5-day residual reversion. Days with no real
residual dispersion are skipped rather than producing arbitrary tie trades.

## Latest evidence

Corrected rerun on the deployed `be3b9b4` build:

- Obs=538
- Hit-rate=54.1%
- Mean=0.79 bps
- Median=10.10 bps
- Total=427.0 bps
- t-stat=0.14

The corrected scan changed the result shape but did not reveal a statistically
meaningful edge. The higher hit rate and median are overwhelmed by payoff
variance/tails, leaving the mean close to zero and the t-stat effectively null.

## Decision

Reject H102 as a standalone strategy hypothesis. Do not run parameter search or
strategy build-out for simple USD-factor dispersion reversion without a new,
material economic conditioning variable.

## Archive location

The algorithm remains available for reproducibility as an explicit archived
cross-instrument scan, but it is excluded from active cross-instrument defaults
and moved under the Lab archived-hypotheses disclosure.
