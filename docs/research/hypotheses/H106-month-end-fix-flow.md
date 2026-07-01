# H106 — Month-end and London fix flow

- Status: active / exploratory probe implemented
- Algorithm: `month_end_fix_probe`

## Hypothesis

Month-end and 4pm London WMR fix windows contain forced hedging/rebalancing FX
flow that may be directionally predictable, showing up as pre-fix drift and a
post-fix retracement.

## Economic rationale

Real-money portfolio hedge rebalancing is benchmark-driven and price-insensitive,
which creates a more plausible structural edge than arbitrary chart events.

## Initial test

No external calendar feed is required for the first pass: the 16:00
Europe/London fix time and the last business day of the month are both
computable from the clock. The probe measures the 15:40→16:00 London pre-fix
drift and scores the 16:00→16:30 retracement against the drift direction,
splitting month-end days from normal days per instrument.

## Future extension

Conditioning the fix-flow direction on the month's equity move still needs an
equity-return input and remains a follow-up once the unconditioned retracement
is measured.

## Gate

Promote only if the month-end retracement is materially stronger than the
normal-day baseline with enough independent month-ends, and survives cost
checks at the fix-window spread (which widens into the fix).
