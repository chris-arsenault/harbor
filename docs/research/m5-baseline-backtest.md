# M5 Baseline Backtest

M6_RESEARCH_GATE: pending

## Scope

This report is the M5 research gate artifact for Harbor's recorded closed-candle fixtures. It uses the M4 pure strategy core through the M5 backtest engine. It does not fetch live OANDA data, launch optimizer work, paper variants, broker execution, frontend UI, or deployment changes.

## Dataset

| Dataset | Instrument | Range UTC | Fixture | Result |
| ---- | ---- | ---- | ---- | ---- |
| Clean signal day | EUR_USD | 2026-01-15T01:00:00+00:00 to 2026-01-15T16:30:00+00:00 | `backend/tests/fixtures/backtester/clean_signal_day.json` | One bullish sweep/FVG trade |
| No-trade day | EUR_USD | 2026-01-16T01:00:00+00:00 to 2026-01-16T16:30:00+00:00 | `backend/tests/fixtures/backtester/no_trade_day.json` | No trades |

Only local recorded fixtures were available for M5. The report should be replaced or extended when a larger historical fixture bundle is added.

## Parameter And Config Snapshot

| Setting | Value |
| ---- | ---- |
| Strategy instrument | EUR_USD |
| Strategy timezone | America/New_York |
| Entry mode | Market entry after qualifying closed-candle FVG |
| Target mode | rr_or_liquidity |
| Risk per trade | 0.5% NAV |
| Max daily loss | 2.0% NAV |
| Initial NAV | 10000 |
| Spread assumption | 0.8 pips |
| Slippage assumption | 0.1 pips |
| Commission per unit | 0 |
| Ambiguous bracket fill policy | pessimistic |
| Forced NY close | true |

## Baseline Stats

| Fixture | Trade count | Net PnL | Max drawdown | Expectancy | Average R | Ending NAV |
| ---- | ----: | ----: | ----: | ----: | ----: | ----: |
| Clean signal day | 1 | 96.150000 | 0 | 96.150000 | 1.785714285714285714285714286 | 10096.150000 |
| No-trade day | 0 | 0 | 0 | 0 | 0 | 10000 |

## Trade Snapshot

| Fixture | Side | Entry UTC | Entry | Exit UTC | Exit | Exit reason | PnL | R |
| ---- | ---- | ---- | ----: | ---- | ----: | ---- | ----: | ----: |
| Clean signal day | long | 2026-01-15T14:34:00+00:00 | 1.09105 | 2026-01-15T14:40:00+00:00 | 1.097300 | take_profit | 96.150000 | 1.785714285714285714285714286 |

Take-profit fills are modeled as limit orders (no adverse slippage); stop-side and forced exits keep slippage. Numbers above reflect that fill model.

## Lookahead Notes

The M5 engine test suite includes a lookahead guard proving the strategy evaluator receives candle history only through the current closed candle. The recorded clean-signal snapshot shows one target hit, and the no-trade day remains flat. This fixture sample is too small to prove edge; it is only a deterministic regression baseline. No lookahead symptoms are visible in these fixtures, but the M6 decision remains pending until this report is reviewed.
