# Development

Harbor uses the Ahara project layout with a Python backend in `backend/`, a TypeScript React frontend in `frontend/`, migrations in `backend/db/migrations/`, and platform/deploy files at the repository root.

## Canonical Verification

`make ci` is the canonical verification command. It mirrors the shared Ahara workflow:

- Python: `uv sync --extra dev`, `ruff check`, `ruff format --check`, and fast unit/API tests.
- TypeScript: `pnpm install --frozen-lockfile`, ESLint, Prettier, `tsc --noEmit`, Vitest, and Vite build.
- Deploy files: manifest, compose, and shell checks.
- Compose: static validation without starting long-lived services.
- Shell: syntax checks for deployment hooks.

The per-commit gate intentionally excludes `backend/tests/integration` and `backend/tests/e2e`.
Those suites use real services or broker-shaped paths and should run when the touched work changes
persistence, migrations, ingestion, deployment behavior, or OANDA practice execution.

Useful backend gates:

```bash
make backend-test             # fast tests used by make ci
make backend-test-integration # real Postgres and repository/service integration tests
make backend-test-e2e         # broker-shaped e2e tests
make backend-test-all         # complete backend suite
```

## Persistence

Backend persistence uses SQLAlchemy Core with async PostgreSQL connections and Alembic migrations in `backend/db/migrations/`. Repository integration tests use real Postgres containers through the Docker CLI so constraints, transactions, JSONB, and migrations are verified against PostgreSQL rather than SQLite.

Useful backend commands:

```bash
cd backend
uv run --extra dev pytest tests/integration/test_migrations.py
uv run --extra dev pytest tests/integration/test_config_seed.py
```

## OANDA Read Path

The backend OANDA boundary uses raw async `httpx`, typed adapters, and fixtures or `httpx.MockTransport` in tests. CI does not call live OANDA services and does not require OANDA credentials. Manual live probes, if added later, must run through `with-cred -- ...`.

The feed path emits and persists only closed M1 candles. Historical ingestion drops incomplete OANDA candles, and pricing stream ingestion keeps the active minute in memory until a later minute starts.

Useful M3 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_oanda_client.py tests/test_oanda_stream.py
uv run --extra dev pytest tests/test_candle_builder.py tests/test_transaction_stream.py
uv run --extra dev pytest tests/integration/test_historical_ingestion.py tests/integration/test_pricing_stream_ingestion.py
```

## Pure Strategy

The pure strategy package is deterministic and closed-candle-only. It consumes feed candles, session levels, immutable day state, risk context, instrument rules, and config, then returns decisions without OANDA calls, database writes, API work, broker execution, or backtest fill simulation.

The rule is simple: strategy parameters are config. Numeric values such as sweep buffer, FVG window, spread cap, trade count, risk percent, RR floor, and max units come from default/live config or instrument metadata rather than hardcoded architecture choices.

Useful M4 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_strategy_models.py tests/test_strategy_sessions.py
uv run --extra dev pytest tests/test_strategy_sweeps.py tests/test_strategy_fvgs.py
uv run --extra dev pytest tests/test_strategy_signals.py tests/test_strategy_risk.py tests/test_strategy_core.py
```

## Backtester

The backend backtester is deterministic and local-data-only. It replays recorded fixtures through the same M4 `evaluate_closed_candle` strategy core, fills market entries on the next closed candle's open with configurable spread/slippage assumptions, simulates broker-side stop/target brackets, forces NY-close exits, and writes stats/trades. The backtester does not call OANDA, place broker orders, launch optimizer work, run paper variants, or require live credentials.

Recorded fixtures live under `backend/tests/fixtures/backtester/`. The recorded fixtures policy is that tests use complete UTC closed candles only; loaders reject incomplete, non-UTC, and duplicate instrument/timestamp rows.

The M5 API scope is synchronous `POST /api/backtests` and `GET /api/backtests/{run_id}` behind an injectable backend service. Tests use fake services or local fixture data. Persisted runs use the existing `backtest_runs` and `backtest_trades` tables. The M5 research gate artifact is `docs/research/m5-baseline-backtest.md` and currently records `M6_RESEARCH_GATE: pending`.

Useful M5 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_backtester_models.py tests/test_backtester_data.py
uv run --extra dev pytest tests/test_backtester_fills.py tests/test_backtester_engine.py
uv run --extra dev pytest tests/test_backtester_stats.py tests/test_backtester_snapshots.py
uv run --extra dev pytest tests/integration/test_backtest_repository.py tests/test_backtest_api.py
uv run --extra dev pytest tests/test_backtester_research_report.py
```

## Optimizer

The offline optimizer uses Optuna TPE with a median pruner on top of the M5 backtester. It searches bounded strategy parameters from `backend/src/harbor_bot/optimizer/defaults.yaml`, including session-window offsets, sweep buffer, FVG window, swing lookback, RR floor, spread cap, and trade-count cap. Parameter bounds, trial count, robustness settings, trade-count floors, and walk-forward window sizes are config values.

M6 scoring is walk-forward and out-of-sample by construction: each sampled parameter set is evaluated through `run_backtest`, scored by out-of-sample expectancy divided by max drawdown with a configured drawdown floor, then robustness-checked against neighboring parameter sets. Raw PnL is not the optimizer objective.

Persistence is limited to `opt_studies`, `opt_trials`, and ranked `variants` with `paper` status. M6 uses no live-forward data, no `variant_trades`, no OANDA streams, no broker state, no paper engine, no optimizer API endpoints, and no frontend Lab UI.

Useful M6 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_optimizer_dependency.py
uv run --extra dev pytest tests/test_optimizer_models.py tests/test_optimizer_walkforward.py
uv run --extra dev pytest tests/test_optimizer_search_space.py tests/test_optimizer_objective.py
uv run --extra dev pytest tests/test_optimizer_robustness.py tests/test_optimizer_runner.py
uv run --extra dev pytest tests/integration/test_optimization_repository.py tests/test_optimizer_service.py
uv run --extra dev pytest tests/test_optimizer_research_report.py
```

## Observability API and Dashboard

M7 adds read-only observability endpoints and a dashboard foundation. The backend exposes `GET /api/status`, `GET /api/levels`, `GET /api/candles`, `GET /api/markers`, `GET /api/events`, and `/ws`. REST endpoints read persisted database facts through repository/service boundaries; `/ws` pushes validated JSON envelopes for `candle`, `level_update`, `sweep`, `fvg`, `signal`, `trade`, `equity`, `status`, and `log`.

The dashboard uses TanStack Query for REST and native WebSocket messages for live updates. Chart overlays are server-authored: the frontend renders session levels, sweeps, FVGs, entries, stops, targets, exits, and events exactly as received and does not recompute strategy logic from candles.

Controls are read-only in M7. There is no paper engine, broker execution, OANDA order placement, config editing, trading-enable mutation, flatten action, optimizer API, frontend Lab UI, or live trading. M7 observability checks do not require live credentials.

Useful M7 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_observability_models.py
uv run --extra dev pytest tests/integration/test_observability_repository.py
uv run --extra dev pytest tests/test_observability_service.py tests/test_observability_api.py tests/test_observability_websocket.py
cd ../frontend
pnpm exec vitest run src/api/client.test.ts src/api/live.test.ts
pnpm exec vitest run src/components/status.test.tsx src/components/LiveChart.test.tsx src/App.test.tsx
pnpm exec tsc --noEmit
```

## Shadow Paper Engine and Lab

M8 adds a shadow paper engine for live-forward research and a Lab view/API for optimizer and paper-variant facts. The paper-forward service runs active `paper` variants against one injected closed-candle stream, reuses the M4 strategy core and M5 fill math, and writes simulated fills to `variant_trades`. It does not open OANDA streams itself, place broker orders, reconcile practice execution, mutate live config, enable trading, flatten positions, or require OANDA/live credentials for tests.

The Lab backend exposes `POST /api/optimize`, `GET /api/optimize/{study_id}`, `GET /api/variants`, `POST /api/variants`, and `POST /api/variants/{variant_id}/retire`. `POST /api/variants` creates a paper variant from an optimizer trial; retire marks a paper variant retired and leaves `variant_trades` intact. M8 intentionally does not expose live promotion, config writes, broker controls, alerting, Trades, Backtest, Config, or deployment changes.

The live-forward data separation rule is explicit: optimizer reads closed candles and optimizer tables, paper-forward reads active `variants` plus closed live candles, and Lab live-forward scoring reads `variant_trades`. Optimizer paths must not query or join `variant_trades`.

Useful M8 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_paper_engine_models.py tests/test_paper_engine_engine.py tests/test_paper_engine_service.py
uv run --extra dev pytest tests/integration/test_variant_repository.py tests/test_lab_service.py tests/test_lab_api.py
cd ../frontend
pnpm exec vitest run src/api/lab.test.ts src/components/lab/LabView.test.tsx src/App.test.tsx
pnpm exec tsc --noEmit
```

## OANDA Practice Execution

M9 adds guarded OANDA practice execution for the single `promoted` variant. The backend exposes `POST /api/variants/{variant_id}/promote`, `POST /api/control/trading`, and `POST /api/control/flatten`; the dashboard renders guarded practice trading controls only when `/api/status` reports `trading_controls_available=true`.

Practice orders are market orders with attached stop-loss and take-profit. Signal ids are deterministic, duplicate signals do not place duplicate orders, and OANDA transaction ids are persisted once before reconciliation updates bot trades. Reconciliation compares persisted open trades with OANDA practice open trades/positions, and flatten closes broker exposure before broadcasting control/reconciliation status.

Alerts use ntfy first through `harbor_bot.notifier`, with Telegram behind the same boundary and disabled unless configured. CI uses fake OANDA and notifier transports. Any manual OANDA practice smoke command that touches broker or notifier credentials must use `with-cred -- <command>`.

Useful M9 commands:

```bash
cd backend
uv run --extra dev pytest tests/test_oanda_execution_client.py tests/test_execution_models.py
uv run --extra dev pytest tests/integration/test_execution_repository.py tests/integration/test_variant_repository.py
uv run --extra dev pytest tests/test_notifier_service.py tests/test_practice_execution_service.py tests/test_execution_reconciliation.py tests/test_execution_controls.py tests/test_execution_api.py
uv run --extra dev pytest tests/e2e/test_oanda_practice_execution.py
cd ../frontend
pnpm exec vitest run src/api/client.test.ts src/components/status.test.tsx src/App.test.tsx
pnpm exec tsc --noEmit
```

## M10 Product UI

The web UI now exposes the complete Harbor product surface without using API docs or curl:

- Dashboard: live status, chart overlays, heartbeat, guarded practice controls, and recent events.
- Trades: journal rows, broker/paper identity, PnL, R multiple, exit reasons, and reconciliation identifiers.
- Backtests: experiment launch from fixtures or persisted candle ranges, recent runs, stats, and trade detail.
- Lab: Optuna optimizer/tuning study launch, walk-forward evidence, candidate parameters, data separation, paper variants, retirement, and practice promotion.
- Config: sectioned config editing with diff preview, `APPLY_CONFIG` confirmation, backend validation, and event audit.
- Events: level/module/type/date filters, structured JSON detail, daily summaries, and live WebSocket log insertion.
- Operations: practice-only mode, promoted variant, reconciliation, open position, notifier state, kill switch/day-loss facts, LAN deployment facts, readiness, and manual flatten results.

The frontend renders server-authored facts only. It does not recompute strategy, backtest, optimizer, paper, broker, or reconciliation truth.

Useful M10 checks:

```bash
cd frontend
pnpm exec vitest run
pnpm exec tsc --noEmit
pnpm exec prettier --check .
pnpm exec eslint .
```

Backend product routes are `GET /api/trades`, `GET/POST /api/backtests`, `GET /api/backtests/{run_id}`, `GET/POST /api/optimize`, `GET /api/optimize/{study_id}`, variant create/read/retire/promote routes, `GET/PUT /api/config`, `GET /api/events`, guarded control routes, `/health`, `/ready`, and `/ws`.

Config edits are explicit: the UI previews diffs, the backend validates known config keys and bounds, and writes require `APPLY_CONFIG`. Config edits audit an event and do not mutate historical backtest, optimizer, paper-forward, or practice-execution evidence.

## Platform Integration

Harbor follows the Ahara TrueNAS LAN deployment path:

- `platform.yml` declares `python`, `typescript`, `truenas`, and the `backend`/`frontend` images.
- `.github/workflows/ci.yml` calls the shared reusable workflow.
- `secret-paths.yml` maps compose environment variables to SSM paths.
- `compose.yaml` runs the backend and frontend containers on TrueNAS and publishes the frontend on `192.168.66.3:30091`.
- `ahara-infra` registers the Harbor deployer role and TrueNAS database. Harbor does not register an Ahara reverse-proxy route.
- The LAN endpoint is `http://192.168.66.3:30091/`; backend readiness is available through the frontend at `/ready`, and `/health` remains the cheap frontend liveness check.
- `scripts/smoke.sh` checks frontend `/health`, backend `/ready`, `/api/status`, static WebSocket proxy configuration, and the LAN endpoint binding. If a manual smoke command is extended to use OANDA, AWS, database, ntfy, Telegram, or other credentials, run it as `with-cred -- <command>`.

## Secrets

Local commands that need OANDA, AWS, database, ntfy, Telegram, or other credentials run through `with-cred -- ...`. The repo stores placeholders and SSM parameter paths, not real values.
