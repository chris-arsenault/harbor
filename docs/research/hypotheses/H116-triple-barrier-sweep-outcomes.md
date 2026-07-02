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
barriers inside one candle) are excluded and counted, like timeouts — folding
them into either side biases the hit rate mechanically. The mean of ±1 outcomes
is 2·hit_rate−1, tested against the coin-flip null with day-clustered standard
errors and BH-FDR across the scan family.

## Barrier scale

ATR is candle-timeframe ATR (~1-2 pips on M1), so `barrier_r` must be a
trade-scale multiple — the default is 5. The 2026-07-02 run at 1R demonstrated
the failure mode: barriers resolved within a candle or two, so results were
identical across 30/60/120m horizons with zero timeouts, and the sub-50% hit
rate was dominated by the (then adverse-folded) ambiguous-candle artifact
rather than by information. Identical rows across horizons are the tell that
the barrier is too tight.

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
