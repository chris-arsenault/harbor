# H006 — Early-NY sweep reversal

- Status: proposed
- Edge algorithm: `early_ny_sweep_reversal`

## Hypothesis

Sweeps during the early NY opening auction behave differently from later NY-window
sweeps and may contain stronger reversal signal.

## Economic rationale

The NY open concentrates liquidity discovery, stop placement, and institutional
execution. Late-window moves may be lower-quality drift or post-news continuation.

## Current implementation

The algorithm keeps sweeps whose closed candle is between 09:30 and 10:15
America/New_York.

## Pass condition

The early-NY subset must beat the rejected generic baseline under corrected edge
statistics.
