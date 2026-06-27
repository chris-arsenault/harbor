# H103 — OANDA positioning and order-book information

- Status: recorder built; awaiting forward data
- Future algorithms: retail-position contrarian, liquidity-cluster proximity

## Hypothesis

OANDA's retail position book and order book contain useful outside information.
Retail positioning extremes may be contrarian, and visible order clusters may
identify real liquidity pools better than guessed session highs/lows.

## Data requirement

This data is not backfillable in Harbor today. Harbor now includes a lightweight
recorder that logs OANDA position/order-book snapshots forward once enabled.

## Implementation note

Do not test H103 until enough forward-recorded snapshots exist for the selected
instrument universe.
