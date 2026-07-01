# H110 — Forecast volatility/range instead of direction

- Status: active / exploratory probe implemented
- Algorithm: `range_forecast_probe`

## Hypothesis

FX direction is weakly predictable at our horizons, but volatility/range is more
autocorrelated. A useful research product may first predict when to size down,
avoid entries, or expect large movement rather than which direction to trade.

## Economic rationale

Volatility clusters because liquidity, macro attention, and dealer risk budgets
cluster. A no-trade/risk-sizing model can improve future strategies even without
standalone directional alpha.

## Initial test

The probe now uses true daily high-low range from persisted candles and measures
correlation between previous daily range and next daily range by instrument. The
secondary metric is top-tercile range hit rate among predicted high-range days.

## Gate

Promote only if the range forecast has stable explanatory power and materially
improves either drawdown control, position sizing, or execution filtering in a
later strategy gate.
