# H114 — Cross-pair sweep divergence

- Status: active / exploratory probe implemented
- Algorithm: `sweep_divergence_probe`

## Hypothesis

Session-level sweeps are two populations pooled together, which is one
hypothesis for why the generic sweep family averaged to nothing. A sweep that
no currency-linked sibling pair confirms is an idiosyncratic stop-run and
should revert; a sweep confirmed by a simultaneous sibling sweep is common
(usually USD) repricing and should continue.

## Economic rationale

A stop-run consumes local resting liquidity in one pair; the price returns once
the stops are cleared. A macro repricing moves the shared currency leg across
the whole network at once; there is no local liquidity story to fade.

## Initial test

For each generic sweep event, the probe checks whether any instrument sharing a
currency leg produced its own sweep event within ±10 minutes. Divergent events
are reversal-scored at 60 minutes; confirmed events are continuation-scored.
Both rows report the contrast population's mean as the secondary metric.

## Gate

Promote only if the divergent-reversal and confirmed-continuation splits are
both directionally consistent (the contrast is the point), survive clustered
standard errors on the pooled panel, and hold on the 2-year backfill.
