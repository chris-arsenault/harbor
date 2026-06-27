# H004 — Compressed-range sweep reversal

- Status: proposed
- Edge algorithm: `compressed_range_sweep_reversal`

## Hypothesis

Sweeps after below-median Asia/London range compression reverse more reliably than
sweeps after already-expanded ranges.

## Economic rationale

Compression can concentrate resting liquidity and leave more room for a stop-run
reversal. Expanded ranges may already have consumed the tradable move.

## Current implementation

For each instrument window, the algorithm computes the combined Asia/London range
for sweep days and keeps sweeps whose range is at or below the median candidate
range.

## Pass condition

The compressed-range subset must show statistically meaningful positive reversal
after clustered and multiple-test corrections.
