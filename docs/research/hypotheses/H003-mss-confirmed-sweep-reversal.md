# H003 — MSS-confirmed sweep reversal

- Status: rejected / archived with sweep-reversal family
- Edge algorithm: `mss_confirmed_sweep_reversal`

## Hypothesis

A session sweep only predicts reversal after price confirms a market-structure
shift in the reversal direction.

## Economic rationale

A raw sweep may be a true breakout or a stop-run. A closed-candle structure break
is evidence that post-sweep order flow has actually shifted.

## Current implementation

The event time is the first closed candle within the configured FVG window where
the existing MSS confirmation function is true after the sweep.

## Pass condition

The confirmed-event forward returns must survive the same corrected edge gate as
other algorithms and beat the rejected generic sweep baseline.

## Decision

H003 did not rescue the sweep-reversal premise after corrected scans and broader family evidence. It remains archived for reproducibility only.

## Archive location

The algorithm remains available through the Lab archived edge-scan panel and explicit API requests, but it is excluded from active research defaults.
