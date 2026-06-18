# Harbor - Implementation Plan

Harbor builds the self-hosted OANDA practice-trading research system described in [oanda-bot-spec.md](oanda-bot-spec.md). The plan produces a TrueNAS-deployed Ahara platform service with a Python backend, React dashboard, PostgreSQL state, pure closed-candle strategy core, replayable backtester/optimizer, shadow paper variants, guarded OANDA practice execution, and observable operations. Live trading support is a guarded runtime mode, not an initial validation target.

## Confirmed decisions

- Harbor follows the Ahara TrueNAS LAN deployment path, including Komodo, `secret-paths.yml`, TrueNAS PostgreSQL registration, and LAN-only port publishing.
- The backend is Python 3.12 with asyncio, FastAPI, SQLAlchemy/Alembic, and `uv`.
- The frontend is React 18 + Vite + TypeScript + TailwindCSS + TanStack Query + `lightweight-charts`.
- The canonical verification command is `make ci`.
- The v1 trading instrument is `EUR_USD`.
- OANDA practice mode is the default and only initially enabled mode.
- Live mode requires `OANDA_ENV=live`, `ALLOW_LIVE=true`, and explicit trading enablement.
- Strategy decisions are made from closed candles only.
- The pure `strategy_core` is the shared engine for live, backtest, optimizer, and paper variants.
- The deployment endpoint is planned as `http://192.168.66.3:30091/` on the LAN/WireGuard network. Harbor does not register an Ahara reverse-proxy route in M1.

## Context / reuse map

| Source | Reuse |
| ---- | ---- |
| [oanda-bot-spec.md](oanda-bot-spec.md) | Product, strategy, API, data, UI, testing, and optimization source of truth |
| [../ahara/INTEGRATION.md](../ahara/INTEGRATION.md) | Platform integration rules, required project files, deployer registration, shared workflow, and SSM conventions |
| [../ahara/CI-WORKFLOW.md](../ahara/CI-WORKFLOW.md) | `platform.yml`, shared CI, Python/TypeScript checks, and TrueNAS deploy behavior |
| [../ahara/TRUENAS-DEPLOY.md](../ahara/TRUENAS-DEPLOY.md) | Multi-image TrueNAS compose, GHCR image naming, `secret-paths.yml`, Komodo deployment, and TrueNAS database registration |
| [../sulion/compose.yaml](../sulion/compose.yaml) and [../sulion/docs/deploy.md](../sulion/docs/deploy.md) | LAN-only TrueNAS port publishing pattern with no `reverse_proxy_routes` entry |
| [../ahara-infra/infrastructure/terraform/control](../ahara-infra/infrastructure/terraform/control) | Deployer role registration pattern with `terraform-state` and `komodo-deploy` policy modules |
| [../ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf](../ahara-infra/infrastructure/terraform/services/db-migrate-truenas.tf) | TrueNAS database registration map |
| Official OANDA v20 docs | Endpoint behavior for candles, pricing stream, orders, account summary, and transaction stream |

Reuse-as-is:

- Ahara shared reusable workflow.
- Ahara TrueNAS Komodo deploy action.
- Ahara TrueNAS database registration Lambda.
- Sulion LAN-only TrueNAS port publishing pattern.
- TradingView `lightweight-charts` for chart rendering.

Reuse-but-adapt:

- Ahara Python CI path, because the shared workflow runs `uv` and `ruff` but Harbor needs explicit Python tests in `make ci`.
- Ahara Docker packaging expectations, because Python containers need a reproducible package/install strategy while frontend artifacts can use the standard `dist/` path.

Build-new:

- OANDA async client boundary.
- Closed-candle feed/candle builder.
- Pure strategy core.
- Risk, execution, reconciliation, persistence, API, backtester, optimizer, paper engine, and dashboard.

## Cross-cutting constraints

- Closed-candle correctness is the first invariant in feed, strategy, backtest, optimizer, UI overlays, and tests.
- Broker, DB, clock, and notification I/O stay outside the strategy core.
- All time windows are configured in America/New_York and converted with timezone-aware runtime logic.
- Server-generated facts drive the dashboard; the frontend renders strategy markers and never recomputes them.
- OANDA secrets, database credentials, alert tokens, and AWS credentials are supplied through `with-cred`, SSM, Docker/Kmodo environment injection, or local placeholders only.
- Practice trading is the default operational state until forward-testing and reconciliation gates pass.
- Platform integration changes in `ahara-infra` are real implementation work and must be verified in that repo before Harbor can deploy.
- Optimizer data separation is enforced in data model, APIs, and promotion workflow so forward-test data is never reused for training.

## Milestones

### M0 - Platform-ready project scaffold
Create the executable repository baseline.
- Add `.env.example`, `.python-version`, `.node-version`, root `platform.yml`, and `.github/workflows/ci.yml`.
- Expand the root `Makefile` from documentation verification to the full Python, TypeScript, compose, script, and docs `make ci` gate.
- Create `backend/` with `pyproject.toml`, `uv.lock`, package skeleton, ruff config, pytest setup, and a health endpoint placeholder.
- Create `frontend/` with Vite React TypeScript, pnpm, Tailwind, ESLint v9 flat config, Prettier, Vitest, and a static health-checkable shell.
- Create `compose.yaml`, `secret-paths.yml`, component Dockerfiles, and nginx proxy config without starting services.
- Keep platform resource ownership in `ahara-infra`; this repository contains Harbor application and deploy inputs.
- Add `scripts/deploy.sh` as a parameterless local validation entry that delegates deployment to the Ahara shared CI/Komodo path.
- Exit: `make ci` green; shared workflow governance passes locally by inspection; compose config validates without launching long-lived services.

### M1 - Ahara infra registration [depends on M0]
Register Harbor as a deployable TrueNAS platform service.
- Add `project-harbor.tf` in `ahara-infra` control with allowed repo `harbor`, state key `projects/harbor`, and `terraform-state` plus `komodo-deploy` policy modules.
- Register Harbor's TrueNAS PostgreSQL database in `truenas_db_stacks`.
- Verify Harbor publishes only a LAN endpoint at `192.168.66.3:30091` and does not add an Ahara reverse-proxy route.
- Add any required SSM path permissions for Harbor-specific secrets.
- Exit: Harbor `make ci` green; `ahara-infra` Terraform formatting/checks green for touched files; planned DB and deployer changes are visible in Terraform plan; no Harbor reverse-proxy route is present.

### M2 - Persistence and configuration foundation [depends on M0]
Build the database and configuration spine.
- Create Alembic migrations for candles, sessions, sweeps, FVGs, signals, trades, equity snapshots, events, config, backtest runs/trades, optimization studies/trials, variants, and variant trades.
- Seed default strategy config from `defaults.yaml` into the config table.
- Implement repository boundaries and transaction patterns for append-only market/decision facts.
- Add integration tests against real Postgres.
- Exit: `make ci` green; migrations apply cleanly to an empty Postgres database and idempotent seeds produce stable config.

### M3 - OANDA market data and closed-candle feed [depends on M2]
Create the broker read path without trading.
- Implement the raw async OANDA client for account summary, instrument metadata, historical candles, pricing stream, and transaction stream framing.
- Build reconnect/backoff and heartbeat handling.
- Build the M1 candle cache and closed-candle emitter.
- Add recorded fixtures and tests proving no current candle reaches the strategy boundary.
- Exit: `make ci` green; historical candle ingestion and stream parsing produce persisted closed M1 candles for `EUR_USD`.

### M4 - Pure strategy core and risk math [depends on M3]
Implement the strategy semantics from the source spec.
- Model session levels, sweep state, FVG detection, entry decisions, stop/target calculation, day state, and level cooldown.
- Implement spread, daily-loss, trade-count, one-trade-per-level, and one-position guards as testable risk gates.
- Add fixture tests for clean sweep, rejected sweep, wrong-direction FVG, FVG window expiry, NY close flatten signal, target selection, sizing, and DST-sensitive session boundaries.
- Exit: `make ci` green; deterministic fixtures cover every strategy rule and demonstrate closed-candle-only behavior.

### M5 - Backtester and research gate [depends on M4]
Replay historical candles through the same core.
- Implement a backtest engine with spread/slippage assumptions, market-entry fills, broker-side bracket simulation, forced NY close, and stats output.
- Persist backtest runs and trades.
- Add API endpoints to start/read backtests.
- Add regression snapshot tests from recorded days.
- **[DECISION]** Continue to optimizer only if baseline backtests show a plausible out-of-sample edge and no lookahead symptoms.
- Exit: `make ci` green; months of historical `EUR_USD` data can be replayed into a stats report and trade list.

### M6 - Optimizer and walk-forward validation [depends on M5]
Build the offline parameter-tuning path.
- Implement Optuna TPE trials over the bounded search space.
- Score trials by out-of-sample expectancy divided by max drawdown with minimum trade count floors.
- Implement walk-forward separation and robustness scoring for neighboring parameter plateaus.
- Persist studies, trials, and ranked candidate variants.
- Exit: `make ci` green; an optimization run writes ranked robust candidates without reading forward-test data.

### M7 - API, WebSocket, and dashboard foundation [depends on M4]
Expose system state and build the first observability UI.
- Implement `/api/status`, `/api/levels`, `/api/candles`, `/api/markers`, `/api/events`, and `/ws`.
- Build the React dashboard status strip, health cards, heartbeat indicator, and live chart with server-authored levels, sweeps, FVGs, entries, stops, targets, and exits.
- Keep controls read-only except guarded trading enablement state if execution is not present.
- Exit: `make ci` green; dashboard renders persisted candles and live WebSocket updates without recomputing strategy logic.

### M8 - Shadow paper engine and Lab [depends on M6, M7]
Forward-test candidate variants in parallel without broker orders.
- Run all candidate variants against the one live price stream.
- Simulate fills with spread/slippage assumptions and write `variant_trades`.
- Build Lab study progress, candidate scatter, leaderboard, variant equity, and retire/promote-to-paper actions.
- Enforce optimizer/live-forward data separation in services and UI.
- Exit: `make ci` green; multiple variants forward-test from the same stream with independent journals and equity curves.

### M9 - Practice execution, reconciliation, and alerts [depends on M7]
Enable the single promoted variant to trade OANDA practice.
- Implement order placement with attached stop-loss and take-profit on fill.
- Add idempotent signal dedupe, transaction-stream reconciliation, open trade/position reconciliation, flatten-now, NY-close flatten, and daily-loss kill switch.
- Add ntfy first, with Telegram behind the notifier boundary.
- Add guarded dashboard controls for trading enablement and flatten now.
- Exit: `make ci` green; OANDA practice orders reconcile exactly to persisted trades in paper e2e testing.

### M10 - Full product UI and deployment hardening [depends on M8, M9]
Complete the usable product and LAN deployment hardening.
- Put the entire Harbor product surface in the web UI: dashboard, Trades/Journal, Backtests, Config, Events/Logs, Lab, experiments, optimizer/tuning runs, paper variants, promoted practice execution, and operations controls.
- Make backtesting and Optuna/walk-forward tuning operable from the UI, including experiment launch, progress, result review, candidate comparison, paper promotion, practice promotion, retirement, and live-forward evidence.
- Add config diffing, confirmation gates, audit events, daily summaries, structured logs, and full event visibility.
- Harden compose health checks, frontend-to-backend proxying, backend readiness, secret validation, restart behavior, and deployment smoke checks.
- Deploy through Ahara to TrueNAS and verify the LAN endpoint.
- Exit: `make ci` green; deployed Harbor is reachable at `http://192.168.66.3:30091/` on the LAN, exposes the full product surface, shows live status, and runs practice mode safely.

## Operational validation plan

Forward-testing the promoted practice variant is product use and evidence gathering, not a build milestone. Track it in [docs/forward-test-validation.md](docs/forward-test-validation.md) after M10 is complete.

- Forward-test the promoted practice variant for at least 20 trading days.
- Reconcile bot trades against OANDA transactions and compare practice fills against paper-engine simulations.
- Retire variants that drift outside tolerance from backtest/forward expectations.
- Discuss live enablement only after the sustained forward-test and reconciliation gates pass.
- Produce a forward-test report that documents eligibility or retirement for the promoted variant.

## Decisions needing your input

| Where | Decision you own |
| ---- | ---- |
| M5 | Decide whether baseline backtest evidence is strong enough to proceed to optimization. |
| Operational validation | Decide whether live enablement is worth discussing after the forward-test and reconciliation gates pass. |
