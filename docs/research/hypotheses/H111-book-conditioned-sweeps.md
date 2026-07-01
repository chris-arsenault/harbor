# H111 — Book/position conditioned liquidity sweeps

- Status: active / awaiting H103 forward data
- Algorithm: `book_conditioner_readiness`

## Hypothesis

A sweep is not enough. A sweep becomes economically meaningful when order-book or
position-book state shows crowded/trapped liquidity at or beyond the swept level.
The book is the fuel; the sweep is only the trigger.

## Economic rationale

The failed sweep family likely had a real trigger but no conditioning variable.
Retail positioning and visible liquidity clusters can identify when a stop run
has enough trapped flow to matter.

## Initial test

The current probe is a readiness gate over H103 recorder coverage. It marks an
instrument ready after enough paired order/position snapshots exist to condition
future sweep events.

## Gate

Do not test edge until the recorder has sufficient paired snapshots. Then run a
pre-registered sweep × book-state interaction test rather than unconditional
sweeps.
