# 0007 - Research-first strategy evolution, deferred live order management

- Status: Accepted
- Date: 2026-06-22

## Context

New entry and exit features under consideration - a market-structure-shift gate and decoupled exit modes such as partial-at-1R-plus-runner, ATR trailing, and time stops - change the strategy core, which drives live trading. Live execution today places a single static OANDA bracket order (stop loss and take profit) per trade. Trailing and partial exits require active order management against the broker, a materially larger and riskier live surface. Harbor already has a variant and promotion pipeline with paper-forward evaluation that new strategy behavior can flow through without touching live execution.

## Decision

New strategy features are implemented in the pure strategy core and exercised through backtest, paper-forward, and the variant pipeline first. Live execution stays on static brackets, and live order management for trailing or partial exits is deferred until a mode is validated and promoted. A variant whose exit mode needs active management is marked not live-eligible until a dedicated live-execution phase exists.

## Alternatives considered

- **Build live order management concurrently with the exit-decoupling work** - a promoted variant could run its exit live immediately, but it adds a large, error-prone live surface before the edge is proven and before any exit mode has earned promotion.

## Consequences

The v1 live behavior stays frozen while research proceeds. Exit modes that need active management are fully backtestable and paper-testable but cannot run live until a follow-on live-execution phase, which is recorded in the backlog. The strategy core stays pure and identical across live, paper, and backtest, preserving the existing single-core invariant.
