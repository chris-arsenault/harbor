# Harbor M7 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M7 - API, WebSocket, and dashboard foundation` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; the backend exposes read-only observability REST endpoints and `/ws`; the frontend renders a dashboard status strip, health cards, heartbeat indicator, and live chart from server-authored facts; and the UI never recomputes strategy signals or chart markers.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M7.
- Product/API/UI source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 7 and 8.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires server-generated facts to drive observability; the frontend renders markers and must not recompute strategy logic.
- Reuse from M2/M3/M4:
  - [backend/src/harbor_bot/persistence/schema.py](backend/src/harbor_bot/persistence/schema.py) already defines `candles`, `sessions`, `sweeps`, `fvgs`, `signals`, `trades`, `equity_snapshots`, and `events`.
  - [backend/src/harbor_bot/persistence/market_repository.py](backend/src/harbor_bot/persistence/market_repository.py), [backend/src/harbor_bot/persistence/decision_repository.py](backend/src/harbor_bot/persistence/decision_repository.py), and [backend/src/harbor_bot/persistence/event_repository.py](backend/src/harbor_bot/persistence/event_repository.py) show the existing SQLAlchemy Core repository style.
  - [backend/src/harbor_bot/persistence/database.py](backend/src/harbor_bot/persistence/database.py) owns async engine/transaction helpers.
  - [backend/src/harbor_bot/settings.py](backend/src/harbor_bot/settings.py) provides OANDA mode and database settings.
  - [backend/src/harbor_bot/strategy/sessions.py](backend/src/harbor_bot/strategy/sessions.py) provides session window behavior for status/session phase calculations.
  - [backend/src/harbor_bot/api.py](backend/src/harbor_bot/api.py) is the current FastAPI app factory with injectable service boundaries.
- Reuse from M5/M6:
  - Existing `/api/backtests` routes must continue working.
  - M5/M6 docs already state that paper engine, broker execution, dashboard controls, and live trading do not exist yet.
- Frontend starting point:
  - [frontend/src/App.tsx](frontend/src/App.tsx) is a static shell.
  - [frontend/package.json](frontend/package.json) does not yet include TanStack Query or `lightweight-charts`.
  - [frontend/src/App.test.tsx](frontend/src/App.test.tsx) is the current Vitest/Testing Library pattern.
- M7 boundaries:
  - No paper engine, optimizer API endpoints, broker/OANDA calls, order execution, reconciliation, alerts, config editing, flatten-now action, trading-enable mutation, frontend Lab page, Trades page, Backtest page, deployment changes, or local dev server.
  - M7 may display trading-enabled state, but controls stay read-only/disabled because execution is not present.
  - The WebSocket endpoint may broadcast in-process status/fact messages and support test injection; it must not open OANDA streams in M7.
  - API and UI facts come from persisted database rows or injected test services. The frontend must render server-authored levels, sweeps, FVGs, signals, trades, and status; it must not detect sweeps/FVGs from candle data.
  - All dashboard defaults such as heartbeat stale threshold, initial chart range, and polling fallback intervals are runtime/frontend config constants, not user decisions.

## Steps

1. Confirm M7 baseline before observability work
   - File(s): `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/persistence/*`, `backend/src/harbor_bot/strategy/*`, `frontend/src/*`, `frontend/package.json`.
   - Reference behavior: M7 builds on persisted facts and the pure strategy boundary. Existing M5 backtest routes and M6 optimizer code must keep passing; dashboard work must not move strategy detection into the frontend.
   - Change: No source changes.
   - Verify: Red if the current backend/frontend baseline drifted, green when Harbor is ready for M7:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_strategy_core.py \
       tests/test_backtest_api.py \
       tests/test_optimizer_service.py \
       tests/integration/test_market_repository.py \
       tests/integration/test_decision_repository.py \
       tests/integration/test_event_repository.py
     cd ../frontend
     pnpm exec vitest run
     cd ..
     grep -q 'candles' backend/src/harbor_bot/persistence/schema.py
     grep -q 'sessions' backend/src/harbor_bot/persistence/schema.py
     grep -q 'sweeps' backend/src/harbor_bot/persistence/schema.py
     grep -q 'fvgs' backend/src/harbor_bot/persistence/schema.py
     grep -q 'signals' backend/src/harbor_bot/persistence/schema.py
     grep -q 'events' backend/src/harbor_bot/persistence/schema.py
     ```

2. Add backend observability response models and serializers [depends on #1]
   - File(s): `backend/src/harbor_bot/observability/__init__.py`, `backend/src/harbor_bot/observability/models.py`, `backend/tests/test_observability_models.py`.
   - Reference behavior: API responses must serialize persisted facts into stable dashboard DTOs without leaking SQLAlchemy rows or Decimal/datetime objects directly.
   - Change: Add immutable dataclasses or Pydantic models for `StatusSnapshot`, `SessionLevelSnapshot`, `CandlePoint`, `ChartMarker`, `FvgBox`, `SignalMarker`, `TradeMarker`, `EventLogItem`, `DashboardSnapshot`, and `WebSocketEnvelope`. Include JSON-safe serializers for UTC datetimes and Decimals. Status includes `bot_state`, `session_phase`, `connection_health`, `mode`, `trading_enabled`, `trading_controls_available`, `kill_switch_state`, `day_pnl`, `account_nav`, and `last_heartbeat`.
   - Verify: Red before observability models exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_observability_models.py
     ```

3. Add read-only observability repository queries [depends on #2]
   - File(s): `backend/src/harbor_bot/persistence/observability_repository.py`, `backend/tests/integration/test_observability_repository.py`.
   - Reference behavior: M7 REST endpoints read persisted facts from Postgres. They do not call OANDA and do not recompute strategy signals.
   - Change: Add repository functions to list candles by instrument/time range, get session levels by date/instrument, list sweeps/FVGs/signals/trades for a date/instrument as chart marker source data, list events by level/limit, get latest equity snapshot, and aggregate same-day realized PnL/trade count from persisted trades. Use the existing Docker Postgres integration-test style and existing schema only.
   - Verify: Red before repository exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_observability_repository.py
     ```

4. Add observability service boundary [depends on #2, #3]
   - File(s): `backend/src/harbor_bot/observability/service.py`, `backend/tests/test_observability_service.py`.
   - Reference behavior: The API layer should depend on a service that can be injected in tests. Status must be read-only until execution exists.
   - Change: Add `ObservabilityService` that accepts an async engine and settings, builds `StatusSnapshot`, `SessionLevelSnapshot`, candle lists, marker lists, event lists, and a combined dashboard snapshot from repository data. Include an injectable clock for session phase/time-to-NY-window tests. If no execution service is present, return `trading_enabled=false` and `trading_controls_available=false` while still displaying the state.
   - Verify: Red before service exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_observability_service.py
     ```

5. Add read-only observability REST endpoints [depends on #4]
   - File(s): `backend/src/harbor_bot/api.py`, `backend/tests/test_observability_api.py`.
   - Reference behavior: M7 explicitly adds `GET /api/status`, `GET /api/levels`, `GET /api/candles`, `GET /api/markers`, and `GET /api/events`. Existing `/health` and `/api/backtests` behavior must remain intact.
   - Change: Extend the FastAPI app factory with an injectable `ObservabilityService`. Add the five read-only endpoints with query parsing for `date`, `instrument`, `from`, `to`, `level`, and `limit` as appropriate. Return `404` only for missing singular resources such as levels for a requested date; empty list endpoints return `[]`. Do not add control mutations or optimizer endpoints.
   - Verify: Red before endpoints exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_observability_api.py tests/test_backtest_api.py tests/test_health.py
     ```

6. Add WebSocket broadcast hub and `/ws` endpoint [depends on #4]
   - File(s): `backend/src/harbor_bot/observability/websocket.py`, `backend/src/harbor_bot/api.py`, `backend/tests/test_observability_websocket.py`.
   - Reference behavior: `/ws` pushes server-authored JSON events such as `candle`, `level_update`, `sweep`, `fvg`, `signal`, `trade`, `equity`, `status`, and `log`. M7 must not open broker streams.
   - Change: Add an in-process WebSocket connection manager/broadcast hub with JSON envelope validation and app-factory injection. Add `/ws` to accept clients, send an initial status/dashboard envelope if available, broadcast injected/test messages, and handle disconnects cleanly. Keep it local to the FastAPI process; no Redis or external pub/sub in M7.
   - Verify: Red before `/ws` exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_observability_websocket.py
     ```

7. Add frontend data dependencies and API/WebSocket clients [depends on #5, #6]
   - File(s): `frontend/package.json`, `frontend/pnpm-lock.yaml`, `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`, `frontend/src/api/live.ts`, `frontend/src/api/client.test.ts`, `frontend/src/api/live.test.ts`.
   - Reference behavior: The frontend consumes REST through TanStack Query and live messages through native WebSocket. It does not recompute markers from candles.
   - Change: Add `@tanstack/react-query` and `lightweight-charts` through `pnpm`. Add typed API clients and query hooks for status, levels, candles, markers, and events. Add a WebSocket client/hook that parses `WebSocketEnvelope` messages, updates heartbeat state, and leaves marker semantics untouched. Tests mock `fetch` and `WebSocket`; no dev server.
   - Verify: Red before frontend API clients exist, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/api/client.test.ts src/api/live.test.ts
     ```

8. Build dashboard status strip, health cards, and heartbeat indicator [depends on #7]
   - File(s): `frontend/src/components/StatusStrip.tsx`, `frontend/src/components/HealthCards.tsx`, `frontend/src/components/HeartbeatIndicator.tsx`, `frontend/src/components/ReadOnlyTradingState.tsx`, `frontend/src/components/status.test.tsx`, `frontend/src/styles.css`.
   - Reference behavior: M7 dashboard shows bot/session/connection/mode/trading/kill-switch state, day PnL, open/account facts when present, and a heartbeat indicator that goes stale after a configured threshold. Controls remain read-only/disabled because execution is not present.
   - Change: Add accessible React components for the status strip, health cards, heartbeat indicator, and read-only trading state. Use compact operational dashboard styling, stable responsive dimensions, and no marketing/landing-page layout. Tests assert stale heartbeat behavior, disabled trading control state, and key status/card rendering.
   - Verify: Red before components exist, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/status.test.tsx
     ```

9. Build live chart component with server-authored overlays [depends on #7]
   - File(s): `frontend/src/components/LiveChart.tsx`, `frontend/src/components/chartAdapter.ts`, `frontend/src/components/LiveChart.test.tsx`, `frontend/src/styles.css`.
   - Reference behavior: The chart renders persisted M1 candles and server-authored session levels, sweep markers, FVG boxes, entry/stop/target lines, and exit markers. The frontend must not detect sweeps, FVGs, entries, stops, targets, or exits from candle data.
   - Change: Add a `lightweight-charts` adapter around chart creation/update so tests can stub it. Render candles from `/api/candles` and overlays from `/api/levels` plus `/api/markers`. Use labels/colors that distinguish Asia and London levels. Add tests proving candle updates and overlay rendering use API marker payloads directly and no local strategy detector is called or imported.
   - Verify: Red before chart component exists, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/LiveChart.test.tsx
     ```

10. Wire the dashboard app shell and live updates [depends on #8, #9]
    - File(s): `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/App.test.tsx`, `frontend/src/styles.css`.
    - Reference behavior: The first screen is the usable dashboard, not a landing page. It renders REST data initially and applies live WebSocket status/candle/marker/event updates without polling-only behavior.
    - Change: Wrap the app in `QueryClientProvider`, render the dashboard as the default screen, connect the WebSocket hook, feed live envelopes into dashboard/chart state, and keep events/logs visible in a compact recent-events panel. Preserve frontend health/build behavior.
    - Verify: Red before app shell is wired, green after:
      ```bash
      cd frontend
      pnpm exec vitest run src/App.test.tsx
      pnpm exec tsc --noEmit
      ```

11. Add M7 documentation [depends on #5, #10]
    - File(s): `backend/README.md`, `frontend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: Docs must describe the observability API/WebSocket/dashboard foundation without implying paper engine, broker execution, optimizer API, control actions, Lab UI, or live trading exists.
    - Change: Update docs with M7 endpoint list, WebSocket envelope types, read-only dashboard scope, server-authored marker rule, no-live-credentials policy, and frontend command shape. State that controls are display-only until execution phases.
    - Verify: Red before docs mention M7 observability, green after:
      ```bash
      grep -q '/api/status' backend/README.md docs/development.md docs/architecture.md
      grep -q '/ws' backend/README.md docs/development.md docs/architecture.md
      grep -q 'server-authored' frontend/README.md docs/development.md docs/architecture.md
      grep -q 'read-only' frontend/README.md docs/development.md docs/architecture.md
      ```

12. Run the M7 exit gate [depends on #11]
    - File(s): Harbor repo.
    - Reference behavior: M7 exit requires `make ci` green and the dashboard rendering persisted candles plus live WebSocket updates without recomputing strategy logic. No OANDA credentials are required.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_observability_models.py \
        tests/integration/test_observability_repository.py \
        tests/test_observability_service.py \
        tests/test_observability_api.py \
        tests/test_observability_websocket.py
      cd ../frontend
      pnpm exec vitest run \
        src/api/client.test.ts \
        src/api/live.test.ts \
        src/components/status.test.tsx \
        src/components/LiveChart.test.tsx \
        src/App.test.tsx
      pnpm exec tsc --noEmit
      cd ..
      grep -q '/api/status' backend/README.md docs/development.md docs/architecture.md
      grep -q '/ws' backend/README.md docs/development.md docs/architecture.md
      grep -q 'server-authored' frontend/README.md docs/development.md docs/architecture.md
      ```

## M7 Decision Register

No user-owned decisions are required in M7. Endpoint response shapes, heartbeat stale thresholds, initial dashboard layout, chart colors, and polling fallback intervals are implementation/config values with checked-in defaults.

## Handoff

Execute only these M7 steps next. Do not add paper-engine execution, live-forward scoring, broker/OANDA calls, order execution, reconciliation, alerts, optimizer API endpoints, config editing, trading-enable/flatten mutations, frontend Lab UI, deployment changes, or local dev servers during M7. Stop after the M7 exit gate.
