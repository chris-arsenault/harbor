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

The probe fits a HAR-style model per instrument: next daily high-low range
regressed on the 1-day, 5-day, and 22-day average ranges, refit on an expanding
window so every prediction is out-of-sample. The effect is the correlation of
prediction versus realized range; the secondary metric is top-tercile range hit
rate among predicted high-range days. Daily bars use the New York 17:00
trading-day convention (no Sunday part-days).

## Monetization paths

A validated range forecast feeds three products, none of which needs
directional alpha: a no-trade/size-down filter for directional strategies,
inverse-range position sizing, and a direction-agnostic session straddle on
predicted high-range days.

## Gate

Promote only if the range forecast has stable explanatory power and materially
improves either drawdown control, position sizing, or execution filtering in a
later strategy gate.
