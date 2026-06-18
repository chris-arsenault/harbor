# Harbor M10 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M10 - Full product UI and deployment hardening` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; the deployed LAN app exposes the full Harbor product surface in the web UI; backtests, optimizer/tuning runs, paper variants, promoted practice execution, config edits, logs, and operations are usable without dropping to the API; and the TrueNAS deployment is hardened for restart, readiness, secrets, and LAN-only access.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M10.
- Product/API/UI source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 7, 8, 9, 10, 11, 12, and 15.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires server-generated facts and the shared pure strategy core across live, backtest, optimizer, and paper variants.
- OANDA boundary decision: [ADR-0004](docs/adr/0004-raw-async-oanda-client.md) keeps broker REST/stream details inside the OANDA client boundary.
- Deployment decisions: [ADR-0001](docs/adr/0001-true-nas-platform-deployment.md), [../ahara/INTEGRATION.md](../ahara/INTEGRATION.md), [../ahara/TRUENAS-DEPLOY.md](../ahara/TRUENAS-DEPLOY.md), and [../sulion/docs/deploy.md](../sulion/docs/deploy.md) define the Ahara TrueNAS LAN deployment path.
- Reuse from M7:
  - [backend/src/harbor_bot/observability/*](backend/src/harbor_bot/observability/) provides status, event, chart, and WebSocket models/services.
  - [frontend/src/App.tsx](frontend/src/App.tsx), [frontend/src/components/LiveChart.tsx](frontend/src/components/LiveChart.tsx), and status components provide the dashboard shell.
- Reuse from M8:
  - [backend/src/harbor_bot/optimizer/*](backend/src/harbor_bot/optimizer/) implements Optuna/walk-forward tuning.
  - [backend/src/harbor_bot/backtester/*](backend/src/harbor_bot/backtester/) implements backtest execution and persisted runs.
  - [backend/src/harbor_bot/lab/*](backend/src/harbor_bot/lab/) and [backend/src/harbor_bot/paper_engine/*](backend/src/harbor_bot/paper_engine/) implement study snapshots, variants, live-forward stats, and paper actions.
  - [frontend/src/components/lab/*](frontend/src/components/lab/) provides the initial Lab surface.
- Reuse from M9:
  - [backend/src/harbor_bot/execution/*](backend/src/harbor_bot/execution/) and [backend/src/harbor_bot/notifier/*](backend/src/harbor_bot/notifier/) provide practice execution, reconciliation, controls, and alerts.
  - [frontend/src/components/GuardedTradingControls.tsx](frontend/src/components/GuardedTradingControls.tsx) provides guarded practice controls.
- Current API baseline:
  - Existing routes include `/api/status`, `/api/levels`, `/api/candles`, `/api/markers`, `/api/events`, `/api/backtests`, `/api/backtests/{id}`, `/api/optimize`, `/api/optimize/{id}`, `/api/variants`, `/api/variants/{id}/retire`, `/api/variants/{id}/promote`, `/api/control/trading`, `/api/control/flatten`, and `/ws`.
- M10 boundaries:
  - No OANDA live-mode enablement, live-account risk setting, public internet route, Ahara reverse-proxy route, or new platform resource class.
  - No generic ML framework. The product tuning surface is the existing Optuna TPE plus walk-forward optimizer from section 15 of the spec.
  - No frontend recomputation of strategy, backtest, optimizer, paper, or broker facts. The UI renders server-authored facts and sends guarded commands.
  - No local dev server. Verification uses test/build commands only unless the user explicitly asks to run a server.
  - No live OANDA, ntfy, Telegram, or AWS calls in CI. Any documented manual smoke command that touches external services must use `with-cred --`.
  - Configurable parameter values must be defaults/config, not user-owned decisions.
  - Forward-testing after M10 is tracked by [docs/forward-test-validation.md](docs/forward-test-validation.md), not as a build phase.

## Steps

1. Confirm M10 baseline and product-surface gaps
   - File(s): `HARBOR-PLAN.md`, `oanda-bot-spec.md`, `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/{backtester,optimizer,lab,paper_engine,execution,observability,persistence}/*`, `frontend/src/*`, `compose.yaml`, `frontend/nginx.conf`, `secret-paths.yml`, `scripts/deploy.sh`.
   - Reference behavior: M10 starts from completed M8/M9 capability. Existing dashboard, Lab, backtest, optimizer, variant, practice-control, reconciliation, notifier, and compose behavior must remain green. The web UI should not yet expose the complete product surface.
   - Change: No source changes.
   - Verify:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_backtest_api.py \
       tests/test_lab_api.py \
       tests/test_execution_api.py \
       tests/test_observability_api.py \
       tests/test_execution_controls.py \
       tests/test_execution_reconciliation.py
     cd ../frontend
     pnpm exec vitest run
     pnpm exec tsc --noEmit
     cd ..
     grep -q '192.168.66.3:30091:80' compose.yaml
     if rg -q 'reverse_proxy_routes|traefik|caddy' platform.yml compose.yaml secret-paths.yml; then exit 1; fi
     ```

2. Add product navigation and page shell [depends on #1]
   - File(s): `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/styles.css`, `frontend/src/components/navigation/ProductNav.tsx`, `frontend/src/components/navigation/ProductNav.test.tsx`.
   - Reference behavior: The first screen remains the operational dashboard, but every product workflow must be reachable from the app shell without using API docs or curl.
   - Change: Add a compact responsive navigation surface for Dashboard, Trades, Backtests, Lab, Config, Events, and Operations. Preserve WebSocket status and dashboard live updates while changing views. Do not add a marketing or landing page.
   - Verify: Red before the full navigation exists, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/navigation/ProductNav.test.tsx src/App.test.tsx
     pnpm exec tsc --noEmit
     ```

3. Add backend product query APIs for trades, backtest history, study history, and config reads [depends on #1]
   - File(s): `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/persistence/backtest_repository.py`, `backend/src/harbor_bot/persistence/variant_repository.py`, `backend/src/harbor_bot/persistence/execution_repository.py`, `backend/src/harbor_bot/persistence/config_repository.py`, `backend/tests/test_product_api.py`, `backend/tests/integration/test_product_repositories.py`.
   - Reference behavior: Section 7 requires `GET /api/trades?from=&to=`, config read/update routes, backtest results, optimizer progress, variants, and events. Existing table shapes should be reused before adding schema.
   - Change: Add read APIs/repository queries for broker trade journal rows, recent backtest runs, recent optimizer studies, variant detail including trades/equity, and effective config values. Preserve existing route behavior and response compatibility.
   - Verify: Red before the new read APIs exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_product_api.py tests/integration/test_product_repositories.py tests/test_backtest_api.py tests/test_lab_api.py
     ```

4. Add guarded config update and diff service [depends on #3]
   - File(s): `backend/src/harbor_bot/config/service.py`, `backend/src/harbor_bot/config/models.py`, `backend/src/harbor_bot/persistence/config_repository.py`, `backend/src/harbor_bot/persistence/event_repository.py`, `backend/src/harbor_bot/api.py`, `backend/tests/test_config_api.py`, `backend/tests/test_config_service.py`, `backend/tests/integration/test_config_repository.py`.
   - Reference behavior: Strategy params live in the config table, are hot-editable through the UI, require confirmation, show diffs, and log events. Parameter values are config, not user-owned decisions.
   - Change: Add config snapshot/diff/update models and service. Add `GET /api/config` and `PUT /api/config` with confirmation, validation against known config sections, event logging, and JSON-safe diff output. Do not let config updates mutate historical backtests, optimizer trials, or paper-forward evidence.
   - Verify: Red before config routes/service exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_config_api.py tests/test_config_service.py tests/integration/test_config_repository.py tests/integration/test_event_repository.py
     ```

5. Add experiment/backtest/optimizer orchestration APIs for the UI [depends on #3]
   - File(s): `backend/src/harbor_bot/backtester/service.py`, `backend/src/harbor_bot/optimizer/service.py`, `backend/src/harbor_bot/lab/service.py`, `backend/src/harbor_bot/api.py`, `backend/tests/test_experiment_api.py`, `backend/tests/test_backtest_api.py`, `backend/tests/test_lab_api.py`, `backend/tests/test_optimizer_service.py`.
   - Reference behavior: Backtesting and Optuna/walk-forward tuning are product workflows. The UI must be able to launch runs, read progress/history, review best-trial/candidate evidence, and compare results.
   - Change: Add UI-friendly payload/response models for starting backtests from persisted candle ranges or supplied fixtures, listing/readback of backtest runs, listing optimizer studies, starting tuning studies with bounded search/walk-forward config, reading progress and ranked trials, and exposing best-trial history. Reuse existing optimizer and backtester execution; do not introduce a separate ML subsystem.
   - Verify: Red before the orchestration APIs exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_experiment_api.py tests/test_backtest_api.py tests/test_lab_api.py tests/test_optimizer_service.py
     ```

6. Add frontend API types, clients, and hooks for the full product surface [depends on #3, #4, #5]
   - File(s): `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`, `frontend/src/api/client.test.ts`, `frontend/src/api/lab.test.ts`, `frontend/src/api/product.test.ts`.
   - Reference behavior: Frontend clients should map one-to-one to backend product APIs and typed server facts. The UI must not synthesize strategy, optimizer, or broker truth.
   - Change: Add typed clients/hooks for trades, backtest history/detail/start, optimizer study list/start/detail, config snapshot/diff/update, event filters, variant detail, practice promotion, and operations status. Preserve existing dashboard/Lab clients.
   - Verify: Red before clients/hooks exist, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/api/client.test.ts src/api/lab.test.ts src/api/product.test.ts
     pnpm exec tsc --noEmit
     ```

7. Build Trades/Journal view [depends on #6]
   - File(s): `frontend/src/components/trades/TradesView.tsx`, `frontend/src/components/trades/TradesTable.tsx`, `frontend/src/components/trades/TradeDetail.tsx`, `frontend/src/components/trades/TradesView.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.
   - Reference behavior: The UI needs a trade journal with broker/paper identity, side, units, entry/exit, PnL, R multiple, exit reason, and reconciliation facts. Broker truth comes from the backend.
   - Change: Add filters for date range, instrument, source/status, and variant/practice identity where available. Render journal rows, detail, aggregate totals, R-multiple stats, and reconciliation identifiers. Keep controls read-only from the journal.
   - Verify: Red before Trades view exists, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/trades/TradesView.test.tsx src/App.test.tsx
     pnpm exec tsc --noEmit
     ```

8. Build Backtests and Experiments view [depends on #6]
   - File(s): `frontend/src/components/backtests/BacktestsView.tsx`, `frontend/src/components/backtests/BacktestRunForm.tsx`, `frontend/src/components/backtests/BacktestResult.tsx`, `frontend/src/components/backtests/BacktestsView.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.
   - Reference behavior: A user can run backtests and inspect stats/trades from the web UI. Backtest decisions must use the same backend strategy core and persisted server results.
   - Change: Add a Backtests page with parameter/config selection, candle range or fixture input, run submission, recent run list, stats cards, trade list, and result detail. Label these as experiments/research evidence where appropriate without adding a separate strategy engine.
   - Verify: Red before Backtests view exists, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/backtests/BacktestsView.test.tsx src/App.test.tsx
     pnpm exec tsc --noEmit
     ```

9. Expand Lab into the full tuning/optimizer and variant workflow [depends on #5, #6]
   - File(s): `frontend/src/components/lab/*`, `frontend/src/components/lab/LabView.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.
   - Reference behavior: Section 15 defines one tuning path: Optuna TPE search, walk-forward validation, ranked robust candidates, paper-forward variants, and a single promoted practice variant. The UI must make that whole path operable.
   - Change: Add study creation controls for bounded search/walk-forward config, study history, live progress, best-trial history, candidate scatter, parameter table, trial-to-paper promotion, variant leaderboard, variant equity/trade detail, retirement, and guarded practice promotion. Show data-separation evidence and promoted status. Keep optimizer reads away from `variant_trades`.
   - Verify: Red before the full Lab workflow exists, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/lab/LabView.test.tsx src/App.test.tsx
     pnpm exec tsc --noEmit
     ```

10. Build Config view with diff and confirmation gates [depends on #4, #6]
    - File(s): `frontend/src/components/config/ConfigView.tsx`, `frontend/src/components/config/ConfigEditor.tsx`, `frontend/src/components/config/ConfigDiff.tsx`, `frontend/src/components/config/ConfigView.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.
    - Reference behavior: Config edits are explicit, diffed, confirmed, audited, and validated by the backend. The UI should expose strategy, risk, backtest, paper-engine, execution, notifier, and UI-relevant defaults that are meant to be configurable.
    - Change: Add a config page with sectioned read/edit state, diff preview, confirmation entry, backend validation errors, save/reset flow, and event visibility after save. Preserve historical evidence and do not silently retune promoted variants.
    - Verify: Red before Config view exists, green after:
      ```bash
      cd frontend
      pnpm exec vitest run src/components/config/ConfigView.test.tsx src/App.test.tsx
      pnpm exec tsc --noEmit
      ```

11. Build Events/Logs view and daily summary visibility [depends on #3, #6]
    - File(s): `backend/src/harbor_bot/observability/service.py`, `backend/src/harbor_bot/persistence/event_repository.py`, `backend/tests/test_events_api.py`, `frontend/src/components/events/EventsView.tsx`, `frontend/src/components/events/EventsView.test.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`.
    - Reference behavior: Structured JSON logs and the `events` table are part of operations. The UI needs full event visibility, not only a small dashboard panel.
    - Change: Add event filters by level/module/type/date, structured event detail, daily summary event rendering, live WebSocket log insertion, and clear empty/error states. If a daily summary producer is missing, add the smallest backend service that emits summary events from persisted facts through existing repositories.
    - Verify: Red before Events view/daily summaries exist, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_events_api.py tests/integration/test_event_repository.py
      cd ../frontend
      pnpm exec vitest run src/components/events/EventsView.test.tsx src/App.test.tsx
      pnpm exec tsc --noEmit
      ```

12. Build Operations view for practice execution, reconciliation, alerts, and deployment facts [depends on #6]
    - File(s): `frontend/src/components/operations/OperationsView.tsx`, `frontend/src/components/operations/OperationsView.test.tsx`, `frontend/src/components/GuardedTradingControls.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `backend/src/harbor_bot/observability/service.py`, `backend/tests/test_observability_api.py`.
    - Reference behavior: Practice controls, flatten-now, kill-switch, open position, promoted variant, notifier state, reconciliation state, heartbeat, and LAN deployment status must be visible and operable from the UI.
    - Change: Add an Operations page that reuses guarded practice controls, shows practice-only mode, promoted variant, reconciliation status, open broker state, notifier configuration state, kill-switch/day-loss state, container/readiness facts available from backend status, and manual flatten results. Do not add live-account enablement.
    - Verify: Red before Operations view exists, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_observability_api.py tests/test_execution_api.py
      cd ../frontend
      pnpm exec vitest run src/components/operations/OperationsView.test.tsx src/App.test.tsx
      pnpm exec tsc --noEmit
      ```

13. Consolidate UI state, responsiveness, and visual correctness across all pages [depends on #7, #8, #9, #10, #11, #12]
    - File(s): `frontend/src/App.tsx`, `frontend/src/components/**/*`, `frontend/src/styles.css`, `frontend/src/App.test.tsx`, existing component tests.
    - Reference behavior: Harbor is an operational tool. It should be dense, readable, mobile-friendly, and consistent. No page should depend on hidden API knowledge or recompute backend facts.
    - Change: Normalize loading/error/empty states, live update behavior, responsive layouts, stable dimensions, accessible labels, confirmation UX, and page-level state preservation. Keep text inside containers and avoid nested cards or marketing layouts.
    - Verify:
      ```bash
      cd frontend
      pnpm exec vitest run
      pnpm exec tsc --noEmit
      pnpm exec prettier --check .
      pnpm exec eslint .
      ```

14. Harden backend readiness, structured logging, and runtime validation [depends on #3, #4, #11, #12]
    - File(s): `backend/src/harbor_bot/main.py`, `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/settings.py`, `backend/src/harbor_bot/observability/service.py`, `backend/tests/test_health.py`, `backend/tests/test_settings.py`, `backend/tests/test_observability_api.py`.
    - Reference behavior: The TrueNAS deployment needs deterministic readiness, clear startup failures for missing required configuration, JSON logs to stdout, no secret leakage, and practice-only default safety.
    - Change: Add or refine readiness checks for DB/config dependencies, startup configuration validation, structured logging setup, secret redaction in errors/logs, and status/readiness facts consumed by the Operations UI. Preserve `/health` as a cheap liveness check.
    - Verify: Red before readiness/validation behavior exists, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_health.py tests/test_settings.py tests/test_observability_api.py
      uv run --extra dev ruff check .
      ```

15. Harden compose, nginx proxying, secret paths, restart behavior, and smoke checks [depends on #14]
    - File(s): `compose.yaml`, `frontend/nginx.conf`, `secret-paths.yml`, `scripts/deploy.sh`, `scripts/smoke.sh`, `backend/README.md`, `docs/development.md`, `docs/architecture.md`, `frontend/README.md`.
    - Reference behavior: Harbor deploys through Ahara to TrueNAS as a LAN-only app at `http://192.168.66.3:30091/`, with no reverse-proxy route and no public exposure. Backend API and WebSocket proxying must survive restarts.
    - Change: Add deterministic health/readiness wiring, nginx API/WebSocket proxy hardening, restart-safe compose settings, secret validation documentation, and a smoke script that checks `/health`, `/api/status`, frontend health, WebSocket upgrade configuration by static inspection or safe local command, and LAN endpoint documentation. Manual deployment/smoke commands that use AWS/OANDA/secrets must be documented with `with-cred --`.
    - Verify:
      ```bash
      docker compose config
      bash -n scripts/deploy.sh scripts/smoke.sh
      grep -q '192.168.66.3:30091' compose.yaml docs/development.md docs/architecture.md
      grep -q 'with-cred --' backend/README.md docs/development.md
      if rg -q 'reverse_proxy_routes|traefik|caddy' platform.yml compose.yaml secret-paths.yml; then exit 1; fi
      ```

16. Update documentation and validation handoff [depends on #13, #15]
    - File(s): `backend/README.md`, `frontend/README.md`, `docs/README.md`, `docs/development.md`, `docs/architecture.md`, `docs/forward-test-validation.md`, `HARBOR-PLAN.md`.
    - Reference behavior: Docs must describe the completed product UI, practice-only operational boundary, LAN deployment, manual deployment/smoke flow, and forward-test validation plan without presenting validation as a build milestone.
    - Change: Document each UI page and workflow, backend route summary, config edit rules, optimizer/tuning workflow, practice execution controls, deployment smoke checks, and the post-M10 forward-test validation report. Link [docs/forward-test-validation.md](docs/forward-test-validation.md) from the docs index.
    - Verify:
      ```bash
      grep -q 'Forward-Test Validation Plan' docs/README.md docs/forward-test-validation.md
      grep -q 'Trades' frontend/README.md docs/architecture.md
      grep -q 'Backtests' frontend/README.md docs/architecture.md
      grep -q 'Config' frontend/README.md docs/architecture.md
      grep -q 'Events' frontend/README.md docs/architecture.md
      grep -q 'optimizer' frontend/README.md docs/architecture.md docs/development.md
      grep -q 'LAN' docs/development.md docs/architecture.md
      ```

17. Run the M10 exit gate [depends on #16]
    - File(s): Harbor repo.
    - Reference behavior: M10 exit requires `make ci` green; the full product is usable in the web UI; practice execution remains guarded and practice-only; deployment is LAN-only and restart-hardened; forward testing is documented as operational validation, not a build phase.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_product_api.py \
        tests/test_config_api.py \
        tests/test_experiment_api.py \
        tests/test_events_api.py \
        tests/test_observability_api.py \
        tests/test_execution_api.py
      cd ../frontend
      pnpm exec vitest run \
        src/App.test.tsx \
        src/api/product.test.ts \
        src/components/navigation/ProductNav.test.tsx \
        src/components/trades/TradesView.test.tsx \
        src/components/backtests/BacktestsView.test.tsx \
        src/components/lab/LabView.test.tsx \
        src/components/config/ConfigView.test.tsx \
        src/components/events/EventsView.test.tsx \
        src/components/operations/OperationsView.test.tsx
      pnpm exec tsc --noEmit
      cd ..
      docker compose config
      bash -n scripts/deploy.sh scripts/smoke.sh
      git diff --check
      ```

## M10 Decision Register

No user-owned decisions are required in M10. Navigation shape, page layout, table columns, chart styling, config validation text, confirmation wording, optimizer form defaults, daily-summary cadence, smoke-check details, readiness thresholds, and deployment documentation wording are implementation/config values with checked-in defaults. Live-account enablement remains outside M10 and is only discussable after the operational validation plan passes.

## Handoff

Execute only these M10 steps next. Do not add OANDA live-mode enablement, live account controls, public exposure, reverse-proxy routes, new Terraform/platform resources, a generic ML framework, frontend strategy recomputation, or local dev servers during M10. Stop after the M10 exit gate.
