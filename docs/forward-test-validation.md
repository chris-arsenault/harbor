# Forward-Test Validation Plan

This plan keeps Harbor honest after M10 ships. It is not a build phase: it is the operational evidence required before any live-trading discussion.

## Scope

- Run exactly one promoted practice variant against OANDA practice.
- Keep all optimization, paper-forward, and practice-execution evidence separated.
- Validate that broker practice fills and bot reconciliation match persisted Harbor state.
- Retire variants that drift from backtest, walk-forward, or paper-forward expectations.
- Do not enable OANDA live mode from this plan.

## Minimum Window

- Run for at least 20 trading days.
- Record daily summaries for uptime, trading state, open position state, realized PnL, trade count, alerts, and reconciliation status.
- Pause or restart the validation window if data separation is violated, reconciliation is broken, or runtime configuration is changed in a way that invalidates comparison with the promoted variant's backtest/paper evidence.

## Daily Checks

- Confirm the dashboard shows live heartbeat, account facts, promoted variant, trading controls, open position state, and recent events.
- Confirm all OANDA transactions since the prior checkpoint are persisted once.
- Confirm persisted Harbor trades match OANDA transaction ids, broker trade ids, client order ids, units, prices, and close state.
- Compare practice execution against the paper engine for the same promoted variant and time window.
- Confirm alerts fired for fills, flatten events, reconnect/disconnect events, kill-switch events, and daily summary events when applicable.
- Confirm no optimizer path reads `variant_trades` or forward-test outcome data.

## Failure Criteria

- Duplicate broker orders for one signal.
- Missing or duplicated OANDA transactions.
- Persisted open trade state disagrees with OANDA open trade/position state.
- Practice fill/slippage drift exceeds configured tolerance from the paper engine.
- Live-forward stats drift outside configured tolerance from backtest or walk-forward expectations.
- Daily-loss, NY-close flatten, manual flatten, or kill-switch behavior fails to persist events and reconcile broker state.
- Public exposure, reverse-proxy routing, or live-mode enablement appears without an explicit separate decision.

## Report

At the end of the window, write a report with:

- Date range and number of trading days.
- Promoted variant id, source study/trial, and parameter snapshot.
- Backtest, walk-forward, paper-forward, and practice-trading summary stats.
- Trade reconciliation table with Harbor trade ids and OANDA transaction/trade/client-order ids.
- Practice-vs-paper fill and slippage comparison.
- Uptime, reconnects, missed heartbeat windows, alerts, and kill-switch/flatten events.
- Drift analysis and retirement or eligibility recommendation.
- Explicit decision record: retired, continue practice validation, or discuss live enablement.
