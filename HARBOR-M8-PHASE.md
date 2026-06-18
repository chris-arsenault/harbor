# Harbor M8 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M8 - Shadow paper engine and Lab` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; the backend can run every paper candidate variant against the same closed-candle stream without broker orders; simulated fills are attributed to `variant_trades`; and the frontend Lab renders study progress, candidate scatter data, leaderboard, variant equity, and paper-only variant actions.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M8.
- Product/API/UI source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 6, 7, 8, and 15.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires live, backtest, optimizer, and paper variants to call the same pure closed-candle strategy core.
- Reuse from M2/M6:
  - [backend/src/harbor_bot/persistence/schema.py](backend/src/harbor_bot/persistence/schema.py) already defines `opt_studies`, `opt_trials`, `variants`, and `variant_trades`.
  - [backend/src/harbor_bot/persistence/optimization_repository.py](backend/src/harbor_bot/persistence/optimization_repository.py) persists optimizer studies, trials, and candidate variants.
  - [backend/src/harbor_bot/optimizer/config.py](backend/src/harbor_bot/optimizer/config.py) already applies optimizer params to the base `StrategyConfig`; reuse this for paper variants rather than duplicating parameter semantics.
  - [backend/src/harbor_bot/optimizer/service.py](backend/src/harbor_bot/optimizer/service.py) can start offline optimization through an injectable runner and currently enforces no live-forward data use.
- Reuse from M3/M4/M5:
  - [backend/src/harbor_bot/feed/candles.py](backend/src/harbor_bot/feed/candles.py) defines closed M1 candle objects.
  - [backend/src/harbor_bot/strategy/core.py](backend/src/harbor_bot/strategy/core.py) is the single decision engine for paper variants.
  - [backend/src/harbor_bot/backtester/fills.py](backend/src/harbor_bot/backtester/fills.py) already implements market-entry, bracket-exit, slippage, spread, and NY-close fill math that paper variants must reuse.
  - [backend/src/harbor_bot/backtester/models.py](backend/src/harbor_bot/backtester/models.py) provides `BacktestConfig`, trade shape, and JSON helpers for fill assumptions.
- Reuse from M7:
  - [backend/src/harbor_bot/api.py](backend/src/harbor_bot/api.py) has an injectable FastAPI app factory and M7 observability routes.
  - [backend/src/harbor_bot/observability/websocket.py](backend/src/harbor_bot/observability/websocket.py) is the in-process WebSocket broadcast hub for live dashboard updates.
  - [frontend/src/api/client.ts](frontend/src/api/client.ts), [frontend/src/api/hooks.ts](frontend/src/api/hooks.ts), and [frontend/src/api/types.ts](frontend/src/api/types.ts) are the frontend REST/query surface.
  - [frontend/src/App.tsx](frontend/src/App.tsx) renders the dashboard shell and handles live WebSocket envelopes.
  - [frontend/src/components/LiveChart.tsx](frontend/src/components/LiveChart.tsx) and [frontend/src/components/chartAdapter.ts](frontend/src/components/chartAdapter.ts) show the adapter/test pattern for chart-like components.
- M8 boundaries:
  - No broker/OANDA order placement, transaction reconciliation, real account practice execution, live config promotion, trading-enable mutation, flatten-now action, alerts/notifiers, Trades page, Backtest page, Config page, deployment changes, or local dev server.
  - The paper engine may consume a closed-candle iterable or injected stream adapter in tests. It must not open OANDA streams directly in M8.
  - The paper engine runs `paper` candidate variants only. `retired` variants are excluded, and M8 does not implement the guarded `promoted` live-account path.
  - `POST /api/variants` promotes an optimizer trial to a `paper` variant. It does not promote a paper variant to live config.
  - `POST /api/variants/{id}/retire` retires a paper variant. It must not delete `variant_trades` or feed retired variants back into the optimizer.
  - Optimizer/live-forward separation is mandatory: optimizer reads `candles` and optimizer tables; paper-forward reads `variants` and closed live candles; live-forward scoring reads `variant_trades`; no optimizer path reads `variant_trades`.
  - Defaults such as paper initial NAV, slippage, spread, live-forward score floor, leaderboard sort order, chart colors, and Lab polling intervals are checked-in config defaults, not user decisions.

## Steps

1. Confirm M8 baseline before paper-forward work
   - File(s): `backend/src/harbor_bot/optimizer/*`, `backend/src/harbor_bot/strategy/*`, `backend/src/harbor_bot/backtester/*`, `backend/src/harbor_bot/observability/*`, `frontend/src/*`, `frontend/package.json`.
   - Reference behavior: M8 builds on M6 optimizer variants and M7 dashboard/API plumbing. Existing strategy/backtester/optimizer/observability behavior must remain green. There must not already be a paper-engine implementation that writes `variant_trades`.
   - Change: No source changes.
   - Verify:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_strategy_core.py \
       tests/test_backtester_engine.py \
       tests/test_backtester_fills.py \
       tests/test_optimizer_service.py \
       tests/integration/test_optimization_repository.py \
       tests/test_observability_api.py \
       tests/test_observability_websocket.py
     cd ../frontend
     pnpm exec vitest run
     cd ..
     grep -q 'variants' backend/src/harbor_bot/persistence/schema.py
     grep -q 'variant_trades' backend/src/harbor_bot/persistence/schema.py
     test ! -d backend/src/harbor_bot/paper_engine
     ```

2. Add paper-forward model contracts and config defaults [depends on #1]
   - File(s): `backend/src/harbor_bot/paper_engine/__init__.py`, `backend/src/harbor_bot/paper_engine/models.py`, `backend/src/harbor_bot/paper_engine/defaults.yaml`, `backend/src/harbor_bot/paper_engine/config.py`, `backend/tests/test_paper_engine_models.py`.
   - Reference behavior: M8 paper variants are independent simulations with explicit fill assumptions and no broker state. Numeric parameters are configuration values.
   - Change: Add immutable model/config objects for `PaperVariant`, `PaperEngineConfig`, `VariantTrade`, `VariantEquityPoint`, `VariantStats`, `VariantLeaderboardRow`, and `LabStudySnapshot`. Include JSON-safe serializers for UTC datetimes and Decimals. Defaults include paper initial NAV, spread/slippage/commission, ambiguous fill policy, live-forward score drawdown floor, leaderboard minimum-trade floor, and max Lab rows.
   - Verify: Red before model/config symbols exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_paper_engine_models.py
     ```

3. Add variant and Lab repository queries/actions [depends on #2]
   - File(s): `backend/src/harbor_bot/persistence/variant_repository.py`, `backend/tests/integration/test_variant_repository.py`.
   - Reference behavior: M8 persists live-forward results only to `variant_trades` and reads optimizer candidates from `opt_studies`/`opt_trials`/`variants`. It does not add new tables unless an existing migration is objectively insufficient.
   - Change: Add repository functions to list studies with trial progress, get one study with trials/candidates, list active paper variants with source trial scores, create a paper variant from an `opt_trials.id`, retire a paper variant, append `variant_trades`, list variant trades by variant/time range, derive variant equity curves from closed trades plus configured initial NAV, and compute variant stats/leaderboard rows. Retiring a variant must leave existing trades intact. Optimizer-study reads must not join or query `variant_trades`.
   - Verify: Red before repository exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_variant_repository.py
     ```

4. Add deterministic shadow paper engine [depends on #2]
   - File(s): `backend/src/harbor_bot/paper_engine/engine.py`, `backend/tests/test_paper_engine_engine.py`.
   - Reference behavior: The paper engine consumes the one closed-candle stream and runs all active paper variants independently through the same strategy core. It must reuse M5 fill math and reject incomplete candles.
   - Change: Add `ShadowPaperEngine` that accepts paper variants, base strategy config, instrument rules, paper engine config, and an injectable strategy evaluator. On each closed candle, dispatch the same candle to every non-retired variant, maintain per-variant day state/history/session levels/pending entry/open position/NAV, simulate market entries and bracket/NY-close exits with `backtester.fills`, and emit attributed `VariantTrade` records. Use `optimizer.config.apply_params_to_strategy_config` to apply each variant's params.
   - Verify: Red before engine exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_paper_engine_engine.py
     ```

5. Add paper-forward service boundary and persistence loop [depends on #3, #4]
   - File(s): `backend/src/harbor_bot/paper_engine/service.py`, `backend/tests/test_paper_engine_service.py`.
   - Reference behavior: Runtime orchestration should be injectable in tests and should not open broker streams directly. One closed-candle source feeds every active paper variant.
   - Change: Add `PaperForwardService` that loads active paper variants through `variant_repository`, builds one `ShadowPaperEngine`, consumes an injected closed-candle iterable/batch, persists emitted `variant_trades`, writes structured `events`, and optionally broadcasts `variant_trade`/`variant_equity` envelopes through the M7 WebSocket hub. The service must ignore retired variants and must not call OANDA, execution, notifier, or live config paths.
   - Verify: Red before service exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_paper_engine_service.py
     ```

6. Add Lab service and response models [depends on #3]
   - File(s): `backend/src/harbor_bot/lab/__init__.py`, `backend/src/harbor_bot/lab/models.py`, `backend/src/harbor_bot/lab/service.py`, `backend/tests/test_lab_service.py`.
   - Reference behavior: Lab aggregates optimizer progress and live-forward results while preserving optimizer/live-forward data separation.
   - Change: Add `LabService` with injectable repository/config dependencies. It returns study progress, candidate scatter points from `opt_trials`, paper variants, leaderboard rows ranked by out-of-sample score then live-forward score, and variant equity curves derived from `variant_trades`. Include actions to create a paper variant from a trial and retire a paper variant. Add a data-separation block proving optimizer paths do not consume `variant_trades`.
   - Verify: Red before Lab service exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_lab_service.py
     ```

7. Add M8 Lab and paper-forward API endpoints [depends on #5, #6]
   - File(s): `backend/src/harbor_bot/api.py`, `backend/tests/test_lab_api.py`, `backend/tests/test_backtest_api.py`, `backend/tests/test_observability_api.py`.
   - Reference behavior: The source API names optimizer and variant endpoints, but M8 only supports paper-forward Lab actions. Existing M5/M7 routes must continue working.
   - Change: Extend `create_app` with injectable `OptimizerService`, `LabService`, and `PaperForwardService` boundaries. Add `POST /api/optimize`, `GET /api/optimize/{study_id}`, `GET /api/variants`, `POST /api/variants`, and `POST /api/variants/{variant_id}/retire`. Keep closed-candle batch execution behind the `PaperForwardService` test/service boundary rather than exposing a product route for it. Do not add `POST /api/variants/{id}/promote`, config writes, broker controls, or live trading routes.
   - Verify: Red before endpoints exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_lab_api.py tests/test_backtest_api.py tests/test_observability_api.py
     ```

8. Add frontend Lab API types, clients, hooks, and live envelope handling [depends on #7]
   - File(s): `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/hooks.ts`, `frontend/src/api/live.ts`, `frontend/src/api/lab.test.ts`.
   - Reference behavior: Frontend Lab consumes backend facts and actions. It must not calculate optimizer scores from candles or recompute variant trades.
   - Change: Add TypeScript types for study progress, candidate scatter points, variants, leaderboard rows, variant trades/equity, and Lab action responses. Add REST client/hooks for optimize start/read, variants list, trial-to-paper creation, and retire. Extend live handling for `variant_trade`, `variant_equity`, and `lab_status` envelopes while preserving existing dashboard envelope behavior.
   - Verify: Red before Lab API clients exist, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/api/lab.test.ts src/api/client.test.ts src/api/live.test.ts
     ```

9. Build Lab components for study progress, scatter, leaderboard, equity, and actions [depends on #8]
   - File(s): `frontend/src/components/lab/StudyProgress.tsx`, `frontend/src/components/lab/CandidateScatter.tsx`, `frontend/src/components/lab/VariantLeaderboard.tsx`, `frontend/src/components/lab/VariantEquityChart.tsx`, `frontend/src/components/lab/LabActions.tsx`, `frontend/src/components/lab/LabView.tsx`, `frontend/src/components/lab/LabView.test.tsx`, `frontend/src/styles.css`.
   - Reference behavior: The Lab presents optimizer progress and paper-forward variants. It can promote an optimizer trial to a paper variant and retire a paper variant, but it cannot promote anything to live config in M8.
   - Change: Add accessible operational components for study progress, candidate scatter by in-sample/out-of-sample/robustness score, leaderboard sorted by backend-provided rank, variant equity curve, and guarded paper-only actions. The equity chart may use a small `lightweight-charts` adapter or a testable SVG component; tests must assert the component renders backend-provided points directly. No Lab action may mutate live trading/config state.
   - Verify: Red before Lab components exist, green after:
     ```bash
     cd frontend
     pnpm exec vitest run src/components/lab/LabView.test.tsx
     ```

10. Wire Lab into the app shell without replacing the dashboard [depends on #9]
    - File(s): `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `frontend/src/styles.css`.
    - Reference behavior: Dashboard remains the default first screen. M8 adds a Lab view reachable from the app shell, with live WebSocket updates applied to Lab state when variant envelopes arrive.
    - Change: Add a compact Dashboard/Lab tab or segmented view control. Keep Dashboard as default. Render `LabView` from REST data, apply `variant_trade`, `variant_equity`, and `lab_status` live envelopes, and keep dashboard status/chart behavior from M7 green. Do not add Trades, Backtest, Config, or control pages.
    - Verify: Red before App exposes Lab, green after:
      ```bash
      cd frontend
      pnpm exec vitest run src/App.test.tsx src/components/lab/LabView.test.tsx
      pnpm exec tsc --noEmit
      ```

11. Add M8 documentation [depends on #7, #10]
    - File(s): `backend/README.md`, `frontend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: Docs must describe shadow paper forwarding and Lab without implying broker execution, live promotion, config mutation, alerts, or deployment exists.
    - Change: Update docs with paper engine scope, one-stream/many-variants rule, `variant_trades` persistence, Lab API endpoints, optimizer/live-forward data separation, Lab frontend command shape, and paper-only action boundaries. State that M8 requires no OANDA/live credentials for tests.
    - Verify: Red before docs mention M8, green after:
      ```bash
      grep -q 'shadow paper engine' backend/README.md docs/development.md docs/architecture.md
      grep -q 'variant_trades' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/variants' backend/README.md docs/development.md docs/architecture.md
      grep -q 'Lab' frontend/README.md docs/development.md docs/architecture.md
      grep -q 'live-forward data separation' backend/README.md docs/development.md docs/architecture.md
      ```

12. Run the M8 exit gate [depends on #11]
    - File(s): Harbor repo.
    - Reference behavior: M8 exit requires `make ci` green; multiple variants can be forward-tested from the same closed-candle stream with independent journals/equity; Lab renders study and variant facts; and optimizer/live-forward data separation is enforced.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_paper_engine_models.py \
        tests/integration/test_variant_repository.py \
        tests/test_paper_engine_engine.py \
        tests/test_paper_engine_service.py \
        tests/test_lab_service.py \
        tests/test_lab_api.py
      cd ../frontend
      pnpm exec vitest run \
        src/api/lab.test.ts \
        src/components/lab/LabView.test.tsx \
        src/App.test.tsx
      pnpm exec tsc --noEmit
      cd ..
      grep -q 'shadow paper engine' backend/README.md docs/development.md docs/architecture.md
      grep -q 'variant_trades' backend/README.md docs/development.md docs/architecture.md
      grep -q '/api/variants' backend/README.md docs/development.md docs/architecture.md
      grep -q 'live-forward data separation' backend/README.md docs/development.md docs/architecture.md
      ```

## M8 Decision Register

No user-owned decisions are required in M8. Paper fill assumptions, initial NAV, live-forward score floor, leaderboard ordering, chart style, and Lab polling/live-update behavior are implementation/config values with checked-in defaults.

## Handoff

Execute only these M8 steps next. Do not add broker/OANDA order placement, OANDA stream ownership inside the paper engine, practice execution, transaction reconciliation, live config promotion, trading-enable/flatten mutations, alerts/notifiers, Trades/Backtest/Config pages, deployment changes, or local dev servers during M8. Stop after the M8 exit gate.
