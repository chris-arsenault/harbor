# 0006 - Bid/ask candles for backtest fill realism

- Status: Accepted
- Date: 2026-06-22

## Context

Live trading, backtests, and the optimizer all use M1 midpoint candles. The backtester models a fixed spread and slippage on entry, but it detects intrabar stop and target touches against midpoint OHLC. A long position's stop is hit when the bid touches it, and the bid sits below the midpoint, so midpoint touch detection under-counts stop-outs and overstates results on a tight-stop 1-minute strategy. This is the most likely source of an over-optimistic backtest, and it is invisible to the existing fixed-cost model because the cost is applied after an already-optimistic fill decision.

## Decision

Harbor persists real bid/ask candles from OANDA (`price=BA`) and detects intrabar touches on the true bid and ask rather than on midpoint OHLC. The honest fill result becomes the baseline expectancy that all later strategy phases are measured against, and the survival of current expectancy under honest fills is quantified explicitly.

## Alternatives considered

- **Half-spread band on existing midpoint candles** - cheap and needs no new data, widening the touch test by half the modeled spread; rejected because it only approximates the bid/ask path and reuses a single fixed spread, where accuracy was the stated priority over cost.
- **Keep midpoint touch detection** - simplest, but it is the known source of inflated backtests and would carry that optimism into every later phase.

## Consequences

A new bid/ask candle import path and storage (migration) are added alongside the existing midpoint store, and the backtester fill and touch logic are reworked to consume them. Reported expectancy is expected to fall to a more honest, possibly negative, level; that honest number gates whether the strategy-expansion phases proceed. Once shipped, an AGENTS critical rule records that backtest fills use bid/ask, not midpoint.
