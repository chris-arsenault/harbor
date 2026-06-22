# Backlog

Planned-but-not-built work. Each item is a positive assertion of future-state behavior.

## Strategy Research

- Add a high-impact news pause filter fed by a maintained calendar source.
- Add multi-instrument support after the EUR_USD system is validated.
- Add richer slippage models from recorded practice fills.
- Add an OANDA order-book and position-book snapshot recorder that captures the ~20-minute liquidity-cluster snapshots forward, building local history for a future "sweep sits on a visible cluster" entry filter and "next cluster as draw" target.
- Add live order management for trailing and partial exits so a promoted variant whose exit mode needs active broker management can run live (deferred from the exit-decoupling research work per ADR 0007).
- Add a partial-at-1R-plus-runner exit mode, which requires modelling a position that produces two fills (a partial take-profit then a runner) rather than the single-exit backtest trade used today.
- Add a forex-sentiment positioning filter from OANDA Forex Labs long/short ratios as a contrarian gate.

## Operations

- Add Prometheus metrics for feed health, reconnects, latency, signals, fills, and equity.
- Add a daily exported research report for backtest, optimizer, and forward-test comparisons.
- Add deployment smoke checks through the LAN endpoint at `192.168.66.3:30091`.

## Product

- Add authenticated remote mobile views tuned for fast status checks.
- Add chart replay controls for backtest and forward-test trade review.
