# Harbor M9 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M9 - Practice execution, reconciliation, and alerts` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; the single promoted variant can place OANDA practice market orders with attached stop-loss and take-profit, idempotent signal handling prevents duplicate orders, broker transaction/open-position reconciliation drives persisted trades, ntfy alerts are available behind a notifier boundary, and the dashboard exposes guarded practice trading controls.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M9.
- Product/API/UI source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 4, 5, 6, 7, 8, 9, 10, 12, and 15.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires practice execution, backtests, optimizer trials, and paper variants to call the same pure closed-candle strategy core.
- OANDA boundary decision: [ADR-0004](docs/adr/0004-raw-oanda-v20-client-boundary.md) keeps bearer auth, base URLs, timeouts, retry/backoff, streaming JSON-line parsing, request IDs, and response normalization inside the OANDA client boundary.
- OANDA endpoint references:
  - Order creation: <https://developer.oanda.com/rest-live-v20/order-ep/>
  - Trade close/list endpoints: <https://developer.oanda.com/rest-live-v20/trade-ep/>
  - Position close/list endpoints: <https://developer.oanda.com/rest-live-v20/position-ep/>
  - Transaction stream/history endpoints: <https://developer.oanda.com/rest-live-v20/transaction-ep/>
- Reuse from M2/M7:
  - [backend/src/harbor_bot/persistence/schema.py](backend/src/harbor_bot/persistence/schema.py) already defines `signals`, `trades`, `equity_snapshots`, `events`, `config`, `variants`, and `variant_trades`.
  - [backend/src/harbor_bot/persistence/database.py](backend/src/harbor_bot/persistence/database.py) owns async engine/transaction helpers.
  - [backend/src/harbor_bot/persistence/decision_repository.py](backend/src/harbor_bot/persistence/decision_repository.py), [backend/src/harbor_bot/persistence/config_repository.py](backend/src/harbor_bot/persistence/config_repository.py), and [backend/src/harbor_bot/persistence/event_repository.py](backend/src/harbor_bot/persistence/event_repository.py) show the existing repository style.
  - [backend/src/harbor_bot/observability/service.py](backend/src/harbor_bot/observability/service.py), [backend/src/harbor_bot/observability/models.py](backend/src/harbor_bot/observability/models.py), and [backend/src/harbor_bot/observability/websocket.py](backend/src/harbor_bot/observability/websocket.py) provide status DTOs and the in-process broadcast hub.
- Reuse from M3/M4/M5:
  - [backend/src/harbor_bot/oanda/client.py](backend/src/harbor_bot/oanda/client.py) and [backend/src/harbor_bot/oanda/types.py](backend/src/harbor_bot/oanda/types.py) are the raw OANDA v20 client/type boundary.
  - [backend/src/harbor_bot/feed/transactions.py](backend/src/harbor_bot/feed/transactions.py) and [backend/src/harbor_bot/oanda/stream.py](backend/src/harbor_bot/oanda/stream.py) already parse transaction/pricing stream frames and monitor stream health.
  - [backend/src/harbor_bot/feed/candles.py](backend/src/harbor_bot/feed/candles.py) defines closed M1 candle objects.
  - [backend/src/harbor_bot/strategy/core.py](backend/src/harbor_bot/strategy/core.py) emits market-entry and flatten decisions from closed candles.
  - [backend/src/harbor_bot/strategy/risk.py](backend/src/harbor_bot/strategy/risk.py) contains spread, NY-close flatten, and daily-loss flatten behavior that execution must honor instead of duplicating risk semantics.
- Reuse from M8:
  - [backend/src/harbor_bot/persistence/variant_repository.py](backend/src/harbor_bot/persistence/variant_repository.py) persists optimizer-derived variants and already distinguishes `paper`, `promoted`, and `retired` status values.
  - [backend/src/harbor_bot/lab/service.py](backend/src/harbor_bot/lab/service.py) and [backend/src/harbor_bot/paper_engine/service.py](backend/src/harbor_bot/paper_engine/service.py) demonstrate the service/repository separation for variant actions and forward loops.
  - [frontend/src/api/client.ts](frontend/src/api/client.ts), [frontend/src/api/hooks.ts](frontend/src/api/hooks.ts), [frontend/src/api/types.ts](frontend/src/api/types.ts), and [frontend/src/App.tsx](frontend/src/App.tsx) are the current REST/query/dashboard surface.
- M9 boundaries:
  - OANDA practice is the only executable broker mode in M9. If runtime settings request `OANDA_ENV=live`, practice execution must refuse to start or place orders, even if `ALLOW_LIVE` is present.
  - No live-trading enablement, minimum-size/live-account decision, M10 product pages, deployment hardening, reverse proxy changes, Terraform, platform resources, local dev servers, or public internet exposure.
  - Practice execution touches exactly one `promoted` variant. It must never execute `paper` or `retired` variants.
  - The optimizer, paper engine, backtester, strategy core, frontend, and Lab views must not call OANDA or recompute broker state.
  - Trading starts disabled by default. All parameter values such as risk limits, heartbeat intervals, reconciliation tolerances, notifier topics, and confirmation text are checked-in configuration or environment-backed configuration, not user decisions.
  - CI uses mocked OANDA/notifier transports and repository fakes or the existing backend integration-test database style. Real OANDA practice smoke commands, if documented, must be explicitly manual and wrapped in `with-cred --`.

## Steps

1. Confirm M9 baseline before broker execution work
   - File(s): `backend/src/harbor_bot/oanda/*`, `backend/src/harbor_bot/feed/*`, `backend/src/harbor_bot/strategy/*`, `backend/src/harbor_bot/persistence/*`, `backend/src/harbor_bot/observability/*`, `backend/src/harbor_bot/lab/*`, `backend/src/harbor_bot/paper_engine/*`, `frontend/src/*`.
   - Reference behavior: M9 builds on M8 Lab/paper-forward work and M7 observability. Existing strategy, backtest, optimizer, paper engine, Lab, OANDA stream, and dashboard behavior must remain green. There must not already be practice order placement, broker control routes, or notifier modules.
   - Change: No source changes.
   - Verify:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_oanda_client.py \
       tests/test_transaction_feed.py \
       tests/test_strategy_core.py \
       tests/test_paper_engine_service.py \
       tests/test_lab_api.py \
       tests/test_observability_api.py
     cd ../frontend
     pnpm exec vitest run
     cd ..
     test ! -d backend/src/harbor_bot/execution
     test ! -d backend/src/harbor_bot/notifier
     if rg -q 'create_market_order_with_bracket|api/control/(flatten|trading)|variants/.+promote' backend/src frontend/src; then exit 1; fi
     ```

2. Add OANDA practice execution client contracts [depends on #1]
   - File(s): `backend/src/harbor_bot/oanda/types.py`, `backend/src/harbor_bot/oanda/client.py`, `backend/tests/test_oanda_execution_client.py`, `backend/tests/fixtures/oanda/*.json`.
   - Reference behavior: ADR-0004 keeps OANDA REST details behind the raw client. Practice order creation uses an OANDA market order with client extensions and attached `stopLossOnFill` and `takeProfitOnFill`. Trade/position close, open-trade/open-position listing, and transaction-history reads are normalized without leaking `httpx` responses above the client boundary.
   - Change: Add typed request/response models for market bracket orders, client extensions, order-create results, trade-close results, open trades, open positions, and transaction-history pages. Add client methods for creating a market order with attached stop-loss/take-profit, closing a trade, closing an instrument position, listing open trades, listing open positions, and reading transactions since a checkpoint. Preserve existing pricing/transaction stream behavior.
   - Verify: Red before the new methods/types exist, green after with mocked HTTP fixtures:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_oanda_execution_client.py tests/test_oanda_client.py
     ```

3. Add execution model contracts and config defaults [depends on #2]
   - File(s): `backend/src/harbor_bot/execution/__init__.py`, `backend/src/harbor_bot/execution/models.py`, `backend/src/harbor_bot/execution/config.py`, `backend/src/harbor_bot/execution/defaults.yaml`, `backend/tests/test_execution_models.py`.
   - Reference behavior: M9 practice execution is explicit, configurable, and disabled by default. Numeric thresholds and runtime intervals are config values, not user decisions. Models must serialize UTC datetimes and Decimals safely.
   - Change: Add immutable execution/control models for `ExecutionMode`, `TradingControls`, `ExecutionSignal`, `SignalReservation`, `BrokerOrder`, `BrokerTrade`, `BrokerPosition`, `ReconciliationSummary`, `FlattenResult`, `KillSwitchState`, and `PracticeExecutionConfig`. Defaults include practice-only mode, trading disabled, one open position, signal idempotency namespace, max daily loss percentage, spread guard, reconciliation lag tolerance, heartbeat interval, NY-close flatten behavior, notifier enablement, and confirmation text.
   - Verify: Red before model/config symbols exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_execution_models.py
     ```

4. Add execution persistence for dedupe, broker transactions, controls, and trade reconciliation [depends on #3]
   - File(s): `backend/src/harbor_bot/persistence/schema.py`, `backend/src/harbor_bot/persistence/execution_repository.py`, `backend/src/harbor_bot/persistence/config_repository.py`, `backend/tests/integration/test_execution_repository.py`.
   - Reference behavior: Existing `signals`, `trades`, `events`, and `config` tables are the base execution journal. M9 may extend the schema only for data the existing tables cannot represent durably: idempotent broker order identity, transaction replay dedupe/checkpoints, and exact broker-trade reconciliation.
   - Change: Add the minimal schema support for `broker_transactions` plus broker/client order identity on persisted trades as needed. Add repository functions to get/set trading controls through `config`, reserve a signal idempotently by deterministic signal key, create or update a broker-backed trade from an order fill, close/update a trade from broker transactions, list open bot trades, persist broker transactions exactly once by transaction id, store/read transaction checkpoints, and append structured execution events. Preserve existing decision repository behavior.
   - Verify: Red before repository/schema support exists, green after against the existing Postgres integration-test style:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_execution_repository.py tests/integration/test_decision_repository.py tests/integration/test_config_repository.py
     ```

5. Add single-promoted-variant selection for practice execution [depends on #4]
   - File(s): `backend/src/harbor_bot/persistence/variant_repository.py`, `backend/src/harbor_bot/lab/service.py`, `backend/tests/integration/test_variant_repository.py`, `backend/tests/test_lab_service.py`.
   - Reference behavior: The real OANDA practice account is touched by exactly one variant: the `promoted` one. Promotion in M9 means selecting a paper variant for OANDA practice validation; it is not live-account enablement.
   - Change: Add repository/service operations to promote one existing `paper` variant, demote any previous promoted variant back to `paper`, reject promotion of `retired` or missing variants, fetch the current promoted variant with source params, and reject promotion while practice trading is enabled or broker-backed trades are open. Do not change optimizer-study scoring or paper-forward behavior.
   - Verify: Red before promoted-selection operations exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_variant_repository.py tests/test_lab_service.py
     ```

6. Add notifier boundary with ntfy first and Telegram behind the same interface [depends on #3]
   - File(s): `backend/src/harbor_bot/notifier/__init__.py`, `backend/src/harbor_bot/notifier/models.py`, `backend/src/harbor_bot/notifier/service.py`, `backend/src/harbor_bot/notifier/ntfy.py`, `backend/src/harbor_bot/notifier/telegram.py`, `backend/tests/test_notifier_service.py`.
   - Reference behavior: Alerts cover fills, errors/disconnects, kill-switch trips, manual flatten, daily summary, and heartbeat. CI must not call live ntfy or Telegram endpoints.
   - Change: Add a notifier protocol/service with event types and routing config. Implement ntfy over injectable `httpx.AsyncClient` and add a Telegram adapter behind the same service boundary, disabled by default unless configured. Add no-op/fake notifier support for tests. Do not put notifier HTTP calls in strategy, risk, paper, optimizer, or frontend code.
   - Verify: Red before notifier modules exist, green after with mocked HTTP:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_notifier_service.py
     ```

7. Add practice execution service over the promoted variant [depends on #4, #5, #6]
   - File(s): `backend/src/harbor_bot/execution/service.py`, `backend/tests/test_practice_execution_service.py`.
   - Reference behavior: Practice execution consumes closed M1 candles, runs the single promoted variant through the same strategy core, and places broker orders only after all controls and risk gates pass. Market orders must include attached stop-loss and take-profit. Strategy/risk code remains pure and unaware of OANDA.
   - Change: Add `PracticeExecutionService` with injectable clock, promoted-variant repository, execution repository, OANDA client, notifier, WebSocket hub, and strategy evaluator. On each closed candle, load the promoted variant, apply its params to base strategy config, evaluate the pure strategy, persist server-authored facts, reserve market-entry signals idempotently, reject duplicate/open-position/disabled/kill-switch/spread-guard cases, calculate signed OANDA units from configured risk/account facts, place a market bracket order, persist broker-backed trades from the order response, emit events, broadcast status/trade envelopes, and notify fills/errors. Flatten decisions from the strategy are passed to the control path rather than hand-rolled in the engine.
   - Verify: Red before the service exists, green after with fake repositories/OANDA/notifier:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_practice_execution_service.py
     ```

8. Add transaction-stream and open-state reconciliation [depends on #4, #7]
   - File(s): `backend/src/harbor_bot/execution/reconciliation.py`, `backend/src/harbor_bot/feed/transactions.py`, `backend/tests/test_execution_reconciliation.py`, `backend/tests/fixtures/oanda/transactions/*.json`.
   - Reference behavior: Broker truth wins for fills, closes, and open positions. Transaction frames are deduped by OANDA transaction id, persisted raw, and mapped to bot trades exactly once. Open trade/position reconciliation detects drift between persisted bot state and OANDA practice state.
   - Change: Add `ExecutionReconciler` that consumes transaction-stream frames or transaction-history pages, persists raw broker transactions, maps order-fill/open/close/cancel/reject events to persisted trades/events, advances checkpoints, and compares OANDA open trades/positions with bot open trades. Emit reconciliation summaries, status changes, WebSocket envelopes, and notifier alerts for mismatches or disconnects. Preserve existing transaction stream parser tests.
   - Verify: Red before reconciler exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_execution_reconciliation.py tests/test_transaction_feed.py
     ```

9. Add guarded trading controls, flatten-now, NY-close flatten, and daily-loss kill switch [depends on #7, #8]
   - File(s): `backend/src/harbor_bot/execution/controls.py`, `backend/src/harbor_bot/execution/service.py`, `backend/tests/test_execution_controls.py`.
   - Reference behavior: Trading is disabled by default and enabling it is a guarded practice-only action. Flatten-now closes broker-backed open trades/positions through OANDA and reconciles the result. NY-close and daily-loss kill-switch behavior must flatten, disable trading, persist events, and alert.
   - Change: Add `TradingControlService` for enabling/disabling practice trading, setting/clearing kill-switch state, manual flatten, strategy-driven NY-close flatten, and daily-loss flatten. Enablement must require exactly one promoted variant, practice mode, no live mode, no kill switch, and no unreconciled broker drift. Flatten must close all known OANDA practice trades/positions, call reconciliation, persist/broadcast summaries, and notify. Daily-loss calculation uses persisted/equity account facts and configured thresholds.
   - Verify: Red before controls exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_execution_controls.py tests/test_practice_execution_service.py tests/test_execution_reconciliation.py
     ```

10. Add M9 practice control API and status integration [depends on #5, #9]
    - File(s): `backend/src/harbor_bot/api.py`, `backend/src/harbor_bot/observability/service.py`, `backend/src/harbor_bot/observability/models.py`, `backend/tests/test_execution_api.py`, `backend/tests/test_observability_api.py`, `backend/tests/test_lab_api.py`.
    - Reference behavior: The spec names `POST /api/control/trading`, `POST /api/control/flatten`, and `POST /api/variants/{id}/promote`. These routes are guarded practice-control routes in M9, not live-trading routes. Existing M7/M8 routes continue working.
    - Change: Extend the app factory with injectable execution/control services. Add `POST /api/variants/{variant_id}/promote`, `POST /api/control/trading`, and `POST /api/control/flatten`. Require the configured confirmation token for enable/flatten mutations, return clear guard failures, and expose updated `trading_enabled`, `trading_controls_available`, `kill_switch_state`, promoted variant, reconciliation state, open position, and account/day PnL facts in `GET /api/status`. Do not add full config editing, Trades page APIs, deployment APIs, or live-account controls.
    - Verify: Red before API routes/status fields exist, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_execution_api.py tests/test_observability_api.py tests/test_lab_api.py tests/test_health.py
      ```

11. Add frontend guarded practice controls to the dashboard [depends on #10]
    - File(s): `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`, `frontend/src/components/GuardedTradingControls.tsx`, `frontend/src/components/status.test.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/styles.css`.
    - Reference behavior: M9 adds guarded dashboard controls for practice trading enablement and flatten-now. The dashboard remains the first screen and renders server-authored state. It does not expose live trading, full config editing, or M10 product pages.
    - Change: Add typed clients/hooks for promote/trading/flatten controls and status fields. Replace the read-only trading widget with guarded controls only when `trading_controls_available` is true. Require explicit confirmation before enabling practice trading or flattening, surface backend guard failures, show promoted variant/reconciliation/kill-switch state, and apply WebSocket status/trade/control envelopes. Preserve the Lab view and existing chart behavior.
    - Verify: Red before frontend controls exist, green after:
      ```bash
      cd frontend
      pnpm exec vitest run src/api/client.test.ts src/components/status.test.tsx src/App.test.tsx
      pnpm exec tsc --noEmit
      ```

12. Add deterministic practice execution e2e and M9 documentation [depends on #8, #10, #11]
    - File(s): `backend/tests/e2e/test_oanda_practice_execution.py`, `backend/README.md`, `frontend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: M9 exit requires OANDA practice orders to reconcile exactly to persisted trades in paper e2e testing. CI must use an OANDA-shaped fake transport and captured practice transaction fixtures; real OANDA practice smoke testing is manual and credentialed.
    - Change: Add an e2e test that promotes one variant, enables practice trading, feeds closed candles, creates a market bracket order through the fake OANDA practice client, replays transaction-stream/history fixtures, reconciles open trades/positions, flattens, and asserts persisted trades match OANDA transaction ids, broker trade ids, client order ids, prices, units, and close state exactly. Update docs with practice-only scope, control routes, notifier config, reconciliation behavior, kill-switch behavior, manual `with-cred --` practice smoke command shape, and the explicit no-live/no-public-exposure boundary.
    - Verify: Red before the e2e/docs exist, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/e2e/test_oanda_practice_execution.py
      cd ..
      grep -q 'OANDA practice' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/control/trading' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/control/flatten' backend/README.md docs/development.md docs/architecture.md
      grep -q 'ntfy' backend/README.md docs/development.md docs/architecture.md
      grep -q 'with-cred --' backend/README.md docs/development.md
      grep -q 'practice trading' frontend/README.md docs/architecture.md
      ```

13. Run the M9 exit gate [depends on #12]
    - File(s): Harbor repo.
    - Reference behavior: M9 exit requires `make ci` green; one promoted variant can execute OANDA practice orders with attached brackets; duplicate signals do not duplicate orders; transaction/open-state reconciliation exactly updates persisted trades; flatten, NY-close flatten, daily-loss kill-switch, ntfy alerts, and guarded dashboard controls work through injectable boundaries.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_oanda_execution_client.py \
        tests/test_execution_models.py \
        tests/integration/test_execution_repository.py \
        tests/integration/test_variant_repository.py \
        tests/test_notifier_service.py \
        tests/test_practice_execution_service.py \
        tests/test_execution_reconciliation.py \
        tests/test_execution_controls.py \
        tests/test_execution_api.py \
        tests/e2e/test_oanda_practice_execution.py
      cd ../frontend
      pnpm exec vitest run \
        src/api/client.test.ts \
        src/components/status.test.tsx \
        src/App.test.tsx
      pnpm exec tsc --noEmit
      cd ..
      grep -q 'OANDA practice' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/control/trading' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/control/flatten' backend/README.md docs/development.md docs/architecture.md
      ```

## M9 Decision Register

No user-owned decisions are required in M9. Practice-only execution, confirmation tokens, risk thresholds, reconciliation tolerances, notifier topics, heartbeat intervals, and UI guard wording are implementation/config values with checked-in defaults. Live-account eligibility and minimum-size/live-risk decisions remain out of scope until the post-M10 forward-test validation plan passes.

## Handoff

Execute only these M9 steps next. Do not add live trading, live-account enablement, public exposure, reverse proxy changes, Terraform/platform resources, deployment hardening, Trades/Backtest/Config product pages, optimizer changes, paper-engine rewrites, or local dev servers during M9. Stop after the M9 exit gate.
