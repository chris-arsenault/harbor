# H113 — Cross-sectional reversal, vol-scaled and tranched

- Status: active / candidate strategy probe implemented
- Algorithm: `cs_reversal_20d_5d_tranched`

## Hypothesis

Short-horizon cross-sectional FX momentum in this universe is inverted: recent
20-day relative losers outperform recent winners over the next 5 trading days.
This is the strongest measured effect in the research log — H100 momentum came
out significantly negative (t=-2.14) — promoted here as a first-class strategy
construction instead of a probe footnote.

## Economic rationale

Cross-sectional over-extension in majors mean-reverts as dealers and macro
funds fade stretched relative moves; daily-horizon rebalancing keeps spread
cost immaterial relative to the 5-day move, which is exactly the failure mode
that killed the intraday sweep family.

## Construction

Three structural upgrades over the raw inverted H100 basket:

- **Inverse-vol weighted legs** — each leg instrument is weighted by the
  inverse of its trailing 20-day daily-return volatility, so JPY crosses do not
  dominate basket risk.
- **Long losers / short winners** — leg size is one quarter of the universe on
  each side.
- **5 staggered daily tranches** — one fifth of risk rebalances each day on a
  5-day hold. Observations become non-overlapping one-day portfolio returns, so
  the reported t-stat needs no overlap correction and the equity curve smooths.

Weights at day t use data through t only; returns are measured t→t+1.

## Gate

Promote to paper only if the daily-return series shows a positive mean with a
significant t-stat over the 2-year backfill, is robust to dropping any single
instrument, and survives a USD-factor neutralization check (the long/short legs
must not reduce to a noisy USD bet).
