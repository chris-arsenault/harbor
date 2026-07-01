# H112 — Currency-network lead/lag propagation

- Status: active / exploratory probe implemented
- Algorithm: `lead_lag_network_probe`

## Hypothesis

Currencies are a coupled network. Some pairs may consistently lead broad FX
repricing while others lag by one or more days. The edge is not relative strength
ranking; it is propagation timing.

## Economic rationale

Liquidity and information flow through the FX network unevenly. USD majors,
JPY-risk crosses, and regional crosses may absorb shocks at different speeds.
Stable propagation can create timing signal even when single-pair patterns fail.

## Initial test

The probe computes daily return correlations for leader at t versus lagger at
+t+1, +t+2, and +t+5 days, reporting the strongest pair/lag relationships. The
family is ~168 tests, so candidate status requires a Benjamini-Hochberg q-value
≤ 0.10 across the whole family (reported as the row's secondary metric); a raw
correlation threshold alone is guaranteed to fire on noise at this family size.
Shared USD/EUR/JPY legs still induce mechanical correlation and must be argued
away before promotion.

## Gate

Promote only if a relationship is stable over time, economically interpretable,
and not merely shared exposure to the same broad USD factor.
