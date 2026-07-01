# H100 — Cross-sectional FX factors

- Status: rejected / archived except as future reversal inspiration
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

## Latest evidence

First cross-instrument scan results:

- `cs_value_60d_5d`: Obs=483, hit=53.4%, mean=7.56 bps, t=1.20 — positive but not significant.
- `cs_momentum_20d_5d`: Obs=523, hit=46.7%, mean=-13.40 bps, t=-2.14 — significantly **negative**.

Interpretation: short-horizon cross-sectional **momentum is inverted** in this
universe (i.e. cross-sectional reversal). Momentum as implemented is rejected;
value/reversion is weakly positive and kept as a lower-priority branch. A future
`cs_reversal` algorithm (invert the momentum leg) is worth testing but is lower
priority than H101.

## Decision

Archive H100 as implemented. Cross-sectional momentum was significantly negative and the value/reversion basket was weak; neither should remain in active Lab defaults. A future inverse-momentum/reversal hypothesis would need a new H-ID and explicit economic framing rather than continuing H100 as-is.

## Archive location

The H100 algorithms remain available through the Lab archived cross-instrument panel and explicit API requests, but they are excluded from active cross-instrument defaults.
