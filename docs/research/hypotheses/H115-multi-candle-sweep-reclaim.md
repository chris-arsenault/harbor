# H115 — Multi-candle sweep reclaim

- Status: active / exploratory algorithm implemented
- Algorithm: `multi_candle_sweep_reclaim_reversal`

## Hypothesis

The strategy's sweep definition requires a single M1 candle to wick beyond a
session level and close back inside. Real stop-runs often take several minutes:
a breach candle closes beyond the level, price digests, then a later candle
reclaims it. That slower reclaim population is invisible to the current
detector and may carry the reversal edge the single-candle events lacked.

## Economic rationale

A slow reclaim shows absorbed breakout flow: the market accepted price beyond
the level, found no follow-through, and forced the breakout traders to unwind —
a stronger trapped-flow signal than a one-minute wick.

## Initial test

The edge algorithm marks a breach when a candle closes beyond a session level
(plus buffer) and emits a reversal event when a later candle closes back inside
within the `fvg_window` deadline. Single-candle wick-and-reclaim sweeps are
excluded (they are the archived H001 population), and each level resolves at
most once per day.

## Gate

Standard research gate: clustered standard errors, family FDR control in scans,
cost sanity checks, and the confirmatory rerun before any strategy work.
