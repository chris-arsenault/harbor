# H108 — Weekend risk-asset information gap

- Status: active / data-gated probe implemented
- Algorithm: `weekend_risk_gap_probe`

## Hypothesis

When FX is closed over the weekend, 24/7 risk assets such as BTC/ETH can price
new global risk information before FX reopens. Weekend proxy returns should help
explain Monday FX gaps or early-week direction, especially in JPY, AUD, and NZD
risk-sensitive crosses.

## Economic rationale

This is a market-hours asymmetry rather than a chart pattern. Information can
arrive while one market is shut and another is open, creating a mechanical lead
for continuously traded risk proxies.

## Initial test

The probe splits the weekend effect into two labeled legs against the
Friday→Sunday risk-proxy return:

- **Gap leg** (`corr(weekend_proxy,reopen_gap)`): Friday close → first
  Monday-session price. High correlation here means weekend information is
  repriced instantly at the reopen and is not tradable by itself.
- **Drift leg** (`corr(weekend_proxy,post_reopen_drift)`): first Monday-session
  price → Monday close. Correlation here is the tradable underreaction
  component.

It reports data-required when no risk proxy candles exist. Daily grouping uses
the New York 17:00 trading-day convention, so Sunday reopen candles belong to
Monday.

## Gate

Only build a strategy if at least one risk-sensitive FX pair shows stable
out-of-sample correlation with enough Monday observations and the effect survives
transaction-cost and open-gap execution checks.
