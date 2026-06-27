# H005 — Clean-level first-touch sweep

- Status: proposed
- Edge algorithm: `clean_level_sweep_reversal`

## Hypothesis

Sweeps of clean, not-yet-tapped NY-window levels carry more reversal signal than
sweeps of levels already traded around before the sweep.

## Economic rationale

A clean first touch is more likely to represent a discrete liquidity pool. A level
that has already been repeatedly probed may be noisy, partially consumed, or less
informative.

## Current implementation

The algorithm keeps sweeps only when no prior NY-window candle touched the swept
level within the configured sweep buffer.

## Pass condition

The clean-level subset must produce a corrected positive base-rate edge and enough
independent trading-day samples.
