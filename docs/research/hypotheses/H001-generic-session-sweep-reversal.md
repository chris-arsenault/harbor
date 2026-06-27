# H001 — Generic session sweep reversal

- Status: rejected
- Edge algorithm: `generic_sweep_reversal`
- Date rejected: 2026-06-26

## Hypothesis

Asia/London session high/low sweeps inside the NY trade window predict short-term
reversal strongly enough to support the existing FVG reversal strategy.

## Economic rationale tested

The strategy assumed resting stops around obvious session liquidity pools are
cleared by a stop-run, after which order flow should revert back inside the range.

## Result

A universe scan across the research instruments and 15m/30m/60m/120m horizons
found no statistically meaningful base-rate reversal edge. The best rows reported
by the rerun were still far below the threshold, for example EUR_JPY 120m with
100 sweeps, 51.0% hit rate, 3.5 pips mean reversal, corrected t=1.16, naive
t=1.53, effective N=69, and Bonferroni-adjusted p=1.0000.

## Decision

Reject the broad generic sweep→reversal premise. Do not optimize or promote the
current strategy as-is. Future work must test narrower economic claims before
entry/exit optimization.
