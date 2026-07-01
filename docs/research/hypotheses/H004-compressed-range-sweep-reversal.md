# H004 — Compressed-range sweep reversal

- Status: rejected / archived with sweep-reversal family
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

## Decision

H004 did not justify further strategy work after the sweep-reversal family failed to show a material corrected edge. It remains archived for reproducibility only.

## Archive location

The algorithm remains available through the Lab archived edge-scan panel and explicit API requests, but it is excluded from active research defaults.
