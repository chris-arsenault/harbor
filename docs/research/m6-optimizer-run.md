# M6 Optimizer Run

## Scope

This report is the M6 optimizer artifact for Harbor's recorded closed-candle fixtures. It uses Optuna TPE with a median pruner, the M5 backtester, and the M4 pure strategy core. It does not call OANDA, read live-forward data, read `variant_trades`, use broker state, run the paper engine, start frontend UI, or make deployment changes.

## Dataset

| Dataset | Instrument | Range UTC | Fixture |
| ---- | ---- | ---- | ---- |
| Clean signal day | EUR_USD | 2026-01-15T01:00:00+00:00 to 2026-01-15T16:30:00+00:00 | `backend/tests/fixtures/backtester/clean_signal_day.json` |
| No-trade day | EUR_USD | 2026-01-16T01:00:00+00:00 to 2026-01-16T16:30:00+00:00 | `backend/tests/fixtures/backtester/no_trade_day.json` |

Only local recorded fixtures were available for M6. The run is a deterministic integration proof of the optimizer path, not evidence of production edge.

## Search-Space Config Snapshot

| Setting | Value |
| ---- | ---- |
| Sampler | Optuna `TPESampler` |
| Pruner | Optuna `MedianPruner` |
| Trial count | 4 |
| Candidate count | 3 |
| TPE seed | 17 |
| Objective | out-of-sample expectancy / max(max drawdown, drawdown floor) |
| Drawdown floor | 1 |
| Minimum in-sample trades | 0 |
| Minimum out-of-sample trades | 0 |
| Robustness neighbors | 2 |
| Robustness step scale | 1 |

The searched parameters are session-window offsets, `sweep_buffer_pips`, `fvg_window`, `swing_lookback`, `rr_floor`, `max_spread_pips`, and `max_trades_per_day`. Locked fields remain locked: instrument `EUR_USD`, market entry, `rr_or_liquidity` target mode, and live safety/risk gates.

## Walk-Forward Summary

The walk-forward split for this deterministic run is:

| Window | Train UTC dates | Out-of-sample UTC dates |
| ---- | ---- | ---- |
| 0 | 2026-01-15 | 2026-01-16 |

The optimizer scores the untouched out-of-sample window. It does not reuse live-forward data for training or scoring.

## Trial Summary

| Trial | Status | Out-of-sample score | Robustness score | Notes |
| ----: | ---- | ----: | ----: | ---- |
| 0 | completed | 0 | 0 | Produced the ranked paper candidate |
| 1 | failed | 0 | 0 | Sparse fixture coverage after sampled session offsets removed required Asia candles |
| 2 | failed | 0 | 0 | Sparse fixture coverage after sampled session offsets removed required London candles |
| 3 | failed | 0 | 0 | Sparse fixture coverage after sampled session offsets removed required London candles |

## Ranked Candidates

| Rank | Variant status | Source trial | Params summary |
| ----: | ---- | ----: | ---- |
| 1 | paper | 0 | `fvg_window=12`, `sweep_buffer_pips=2.0`, `rr_floor=2.0`, `max_trades_per_day=1`, session offsets sampled from the checked-in M6 defaults |

## Data-Separation Notes

The optimizer used only the two recorded closed-candle fixture days listed above. There was no live-forward data, no `variant_trades` read, no OANDA stream or broker state, no paper engine, and no frontend UI. Paper variants written by M6 are records for later forward testing only; M6 does not run live-forward scoring or promote anything to live/practice execution.
