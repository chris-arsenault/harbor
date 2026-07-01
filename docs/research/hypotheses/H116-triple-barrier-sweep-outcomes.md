# H116 — Triple-barrier sweep outcomes and meta-labeling

- Status: active / barrier scoring implemented, meta-label gate future
- Algorithm: `run_barrier_scan` over any edge event algorithm

## Hypothesis

Fixed-horizon mean forward returns are the wrong outcome variable for a
bracket-trading strategy: they carry enormous variance and do not match the
trade payoff. Scoring each sweep event by which of two symmetric ±k·ATR
barriers is touched first (a bounded ±1 outcome) matches the actual bracket
shape and materially raises statistical power at the same sample size.

## Economic rationale

The strategy exits on stops and targets, not at a clock time. If sweeps have an
edge in first-touch space that fixed-horizon means cannot resolve, the family
was rejected on the wrong metric.

## Initial test

`POST /api/research/edge/barriers` scores any event algorithm's events by first
touch of entry ± barrier_r·ATR within the horizon. Ambiguous candles (both
barriers inside one candle) resolve adverse; timeouts are counted but excluded.
The mean of ±1 outcomes is 2·hit_rate−1, tested against the coin-flip null with
day-clustered standard errors and BH-FDR across the scan family.

## Meta-labeling roadmap

Barrier labels are the training target for a future probabilistic gate over
sweep events: features from the archived filters (session-range compression,
time-of-day, MSS, ATR regime), book state (H111), and cross-pair confirmation
(H114), fit under purged walk-forward validation. Individually weak
conditioners can be jointly strong; the one-at-a-time edge studies structurally
cannot see that.

## Gate

A barrier-space edge must survive the same clustered/FDR machinery, then a
cost-adjusted replay (barrier distances net of spread) before informing any
strategy change.
