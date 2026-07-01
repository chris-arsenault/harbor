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

The current probe reports both readiness and a first interaction diagnostic.
Readiness uses paired order/position snapshot counts. The interaction row tests
generic sweep reversals conditioned on latest position-book crowding being
trapped against the reversal direction by at least 10 percentage points.

## Gate

Do not promote from snapshot count alone. Promote only if the conditioned sweep
interaction has enough independent trading days, positive net forward returns,
and beats the unconditioned sweep baseline after clustered standard errors.
