# H103 — OANDA positioning and order-book information

- Status: proposed / data recorder needed
- Future algorithms: retail-position contrarian, liquidity-cluster proximity

## Hypothesis

OANDA's retail position book and order book contain useful outside information.
Retail positioning extremes may be contrarian, and visible order clusters may
identify real liquidity pools better than guessed session highs/lows.

## Data requirement

This data is not backfillable in Harbor today. A lightweight recorder should log
OANDA position/order-book snapshots forward before this can be tested.

## Implementation note

Building the recorder is integration plumbing and should be delegated unless it
becomes a research blocker.
