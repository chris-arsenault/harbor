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

The first probe uses close-to-close absolute return as a cheap daily movement
proxy and measures correlation/R² between previous movement and next movement by
instrument.

## Gate

Promote only if the volatility proxy has stable explanatory power and materially
improves either drawdown control or execution filtering in a later strategy gate.
