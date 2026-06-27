# H100 — Cross-sectional FX factors

- Status: active / research engine implemented
- Algorithms: `cs_momentum_20d_5d`, `cs_value_60d_5d`

## Hypothesis

A daily cross-sectional basket can extract more durable FX signal than single-pair
intraday candle patterns. Momentum should reward recent relative strength, while
longer-horizon value/reversion should reward fading stretched relative moves.

## Economic rationale

FX factor effects such as momentum and value are better-supported than isolated
chart patterns because they operate across currencies and reflect slow-moving
capital allocation, macro repricing, and behavioral under/over-reaction.

## Current implementation

The cross-instrument research engine converts persisted M1 candles into daily
closes, aligns instruments by date, and evaluates:

- `cs_momentum_20d_5d`: long top recent 20-day performers, short bottom performers, hold 5 trading days.
- `cs_value_60d_5d`: long 60-day underperformers, short 60-day outperformers, hold 5 trading days.

Returns are reported in basket basis points, not pips.
