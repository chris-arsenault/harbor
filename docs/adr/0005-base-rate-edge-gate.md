# 0005 - Base-rate edge gate before strategy expansion

- Status: Accepted
- Date: 2026-06-22

## Context

Harbor can optimize the sweep-to-FVG strategy and validate candidates on a held-out window, but it has no measurement of the raw conditional edge: after a session level is swept (wick through, close back inside), is the next N minutes' return distribution in the reversal direction skewed any more than chance? Holdout validation tests the whole entry-and-exit machine at once, so it cannot separate "there is no edge" from "the edge exists but the entry or exit is wrong." Widening the search space or adding filters without that measurement risks fitting noise, where a profitable backtest is the dangerous outcome rather than the good one.

## Decision

Before expanding entry or exit logic or the search space, Harbor builds a base-rate conditional-edge study that measures forward-return distributions after sweeps, conditioned by level type, session, and volatility, against a chance baseline. Strategy-changing work (market-structure-shift gate, new exit modes, new levels) is contingent on a demonstrated forward-return skew from this study.

## Alternatives considered

- **Keep optimizing and adding filters without a base-rate check** - faster to a backtest, but cannot distinguish a real edge from overfit noise, and inflates confidence in fragile parameter sets.
- **Rely on holdout validation alone** - already present, but it scores the full strategy, so a failing holdout cannot tell you whether the premise or the machinery is at fault.

## Consequences

The first milestone is a research module plus an API endpoint and a Lab surface, not a strategy change. Later strategy phases are gated on the study's per-instrument verdict, which slows the first strategy change but de-risks the entire program. The study reuses the existing pure sweep detection and runs across the research universe.
