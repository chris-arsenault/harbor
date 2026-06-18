# Frontend

React observability dashboard for Harbor.

M7 renders the default read-only dashboard: status strip, health cards, heartbeat indicator, recent events, and a live chart. Data comes from REST through TanStack Query and live `/ws` messages through the native WebSocket client.

The chart renders server-authored candles, session levels, sweep markers, FVG overlays, entries, stops, targets, exits, and event facts. The frontend does not recompute strategy signals, sweeps, FVGs, entries, stops, targets, or exits from candles.

M8 adds the Lab as a secondary view while keeping the dashboard as the default first screen. The Lab consumes backend facts from `GET /api/optimize/{study_id}` and `GET /api/variants`, renders study progress, candidate scatter data, paper variant leaderboard rows, and variant equity curves, and exposes paper-only actions for creating a paper variant from a trial and retiring a paper variant.

The Lab renders backend-provided scores, `variant_trades`-derived equity, and WebSocket `variant_trade`, `variant_equity`, and `lab_status` envelopes. It does not recompute optimizer scores from candles, does not recompute variant trades, does not promote variants to live config, and does not add trading-enable, flatten, config, Trades, or Backtest pages in M8.

M9 adds guarded practice trading controls to the dashboard when the backend reports `trading_controls_available=true`. The dashboard can submit `POST /api/control/trading` and `POST /api/control/flatten` with the configured confirmation token, shows the promoted variant, reconciliation state, and open practice position facts from `/api/status`.

M10 adds the full product UI:

- Dashboard for live status, chart overlays, heartbeat, and guarded practice controls.
- Trades for broker/paper journal facts, PnL, R multiple, exit reasons, and reconciliation ids.
- Backtests for launching experiments, reading recent runs, reviewing stats, and inspecting trades.
- Lab for optimizer/tuning studies, walk-forward evidence, candidate parameters, paper variants, retirement, and practice promotion.
- Config for diffed, confirmed, backend-validated edits with event audit.
- Events for filtered structured logs, daily summaries, and live WebSocket log insertion.
- Operations for practice-only controls, promoted variant, reconciliation, notifier state, open position, kill switch/day-loss facts, LAN deployment facts, readiness, and manual flatten results.

The frontend does not recompute optimizer scores, backtest trades, paper-forward trades, broker state, reconciliation, or strategy signals from raw candles.

The deployed frontend is the LAN-only entrypoint at `http://192.168.66.3:30091/`. Nginx serves `/health`, proxies `/ready` and `/api/` to the backend, and keeps `/ws` upgraded for live dashboard and Lab events.

Useful frontend commands:

```bash
pnpm exec vitest run src/api/client.test.ts src/api/live.test.ts
pnpm exec vitest run src/api/lab.test.ts src/components/lab/LabView.test.tsx
pnpm exec vitest run src/components/status.test.tsx src/components/LiveChart.test.tsx src/App.test.tsx
pnpm exec tsc --noEmit
```
