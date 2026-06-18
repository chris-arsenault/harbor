# Harbor M6 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M6 - Optimizer and walk-forward validation` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; an offline optimization run uses Optuna TPE over bounded, configured strategy parameters; every trial is scored through the M5 backtester with walk-forward out-of-sample separation; robust ranked trials are persisted to `opt_trials`; and the top candidates are written to `variants` with `paper` status.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M6.
- Product/optimizer source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 14 and 15.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires live, backtest, optimization, and paper variants to call the same pure strategy core over closed candles.
- M5 handoff:
  - [docs/research/m5-baseline-backtest.md](docs/research/m5-baseline-backtest.md) records `M6_RESEARCH_GATE: pending` and no visible lookahead symptoms in the current fixtures.
  - [backend/src/harbor_bot/backtester/engine.py](backend/src/harbor_bot/backtester/engine.py) provides `run_backtest`.
  - [backend/src/harbor_bot/backtester/models.py](backend/src/harbor_bot/backtester/models.py) provides `BacktestInput`, `BacktestConfig`, `BacktestRunResult`, and stats/trade shapes.
  - [backend/src/harbor_bot/backtester/data.py](backend/src/harbor_bot/backtester/data.py) provides local recorded closed-candle fixture loading.
  - [backend/src/harbor_bot/backtester/stats.py](backend/src/harbor_bot/backtester/stats.py) provides stats/snapshot helpers.
  - [backend/src/harbor_bot/persistence/backtest_repository.py](backend/src/harbor_bot/persistence/backtest_repository.py) is the transaction/repository style to reuse.
- Reuse from M2/M4/M5:
  - [backend/src/harbor_bot/config/defaults.py](backend/src/harbor_bot/config/defaults.py) loads default strategy config.
  - [backend/src/harbor_bot/strategy/models.py](backend/src/harbor_bot/strategy/models.py) provides `StrategyConfig` and `InstrumentRules`.
  - [backend/src/harbor_bot/persistence/database.py](backend/src/harbor_bot/persistence/database.py) owns async engine/transaction helpers.
  - [backend/src/harbor_bot/persistence/schema.py](backend/src/harbor_bot/persistence/schema.py) already defines `opt_studies`, `opt_trials`, and `variants`.
  - Existing integration tests use the Docker Postgres harness in [backend/tests/integration/conftest.py](backend/tests/integration/conftest.py); M6 must follow that style.
- M6 boundaries:
  - No paper engine, broker/OANDA calls, live-forward scoring, frontend UI, dashboard/Lab pages, WebSocket work, deployment changes, or live trading controls.
  - No API endpoints unless a later phase explicitly asks for optimizer API. M6 implements backend optimizer services and persistence only.
  - No schema expansion unless an existing schema bug makes M6 persistence impossible.
  - The optimizer may read only the closed-candle dataset supplied to the offline run. It must not read `variant_trades`, live-forward data, OANDA streams, or broker state.
  - Search-space bounds, scoring floors, drawdown floor, robustness-neighbor size, candidate count, trial count, and walk-forward window sizes are runtime/config values with checked-in defaults, not user decisions.
  - Locked strategy decisions remain locked: v1 instrument is `EUR_USD`, entry mode is market entry, target mode is `rr_or_liquidity`, and risk/live-safety gates are not hand-tuned in M6.

## Steps

1. Confirm M5 handoff before optimizer work
   - File(s): `docs/research/m5-baseline-backtest.md`, `backend/src/harbor_bot/backtester/*`, `backend/src/harbor_bot/persistence/schema.py`.
   - Reference behavior: M6 depends on a deterministic M5 backtester and the M5 research gate artifact. The optimizer must reuse `run_backtest`; it must not fork strategy or fill semantics.
   - Change: No source changes.
   - Verify: Red if M5 drifted, green when Harbor is ready for optimizer work:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_backtester_models.py \
       tests/test_backtester_data.py \
       tests/test_backtester_fills.py \
       tests/test_backtester_engine.py \
       tests/test_backtester_stats.py \
       tests/test_backtester_snapshots.py \
       tests/integration/test_backtest_repository.py \
       tests/test_backtest_api.py \
       tests/test_backtester_research_report.py
     cd ..
     grep -q 'M6_RESEARCH_GATE: pending' docs/research/m5-baseline-backtest.md
     grep -q 'lookahead' docs/research/m5-baseline-backtest.md
     grep -q 'opt_studies' backend/src/harbor_bot/persistence/schema.py
     grep -q 'opt_trials' backend/src/harbor_bot/persistence/schema.py
     grep -q 'variants' backend/src/harbor_bot/persistence/schema.py
     ```

2. Add Optuna dependency and optimizer package shell [depends on #1]
   - File(s): `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/harbor_bot/optimizer/__init__.py`, `backend/tests/test_optimizer_dependency.py`.
   - Reference behavior: The source spec requires Optuna TPE with a median pruner. Do not hand-roll hill-climbing, annealing, or bespoke search.
   - Change: Add the `optuna` dependency through `uv`; create the optimizer package. Export no unstable internals yet.
   - Verify: Red before Optuna/package exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_dependency.py
     ```

3. Add optimizer domain models and configurable search space [depends on #2]
   - File(s): `backend/src/harbor_bot/optimizer/models.py`, `backend/src/harbor_bot/optimizer/config.py`, `backend/src/harbor_bot/optimizer/defaults.yaml`, `backend/tests/test_optimizer_models.py`.
   - Reference behavior: M6 searches only bounded strategy parameters named by the source spec: session-window offsets, `sweep_buffer_pips`, `fvg_window`, `swing_lookback`, `rr_floor`, `max_spread_pips`, and `max_trades_per_day`. Parameter values and bounds are config, not architecture decisions.
   - Change: Add immutable models for `OptimizationConfig`, `SearchSpace`, `SearchParameter`, `WalkForwardConfig`, `TrialScore`, `TrialRecord`, `CandidateVariant`, and `OptimizationStatus`. Add a checked-in optimizer defaults YAML loader that validates numeric bounds, enum/integer/decimal parameter types, minimum trade-count floors, drawdown floor, robustness-neighbor settings, TPE seed, trial count, and candidate count. Add a converter that applies sampled params onto an existing `StrategyConfig` without changing locked fields such as instrument, target mode, and risk caps.
   - Verify: Red before models/config exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_models.py
     ```

4. Add walk-forward split and data-isolation helpers [depends on #3]
   - File(s): `backend/src/harbor_bot/optimizer/walkforward.py`, `backend/tests/test_optimizer_walkforward.py`.
   - Reference behavior: Every trial is scored by walk-forward validation. The optimizer may score on window `N+1` only after training/searching on window `N`; it must never read live-forward data.
   - Change: Add pure helpers that accept sorted closed candles and produce chronological train/out-of-sample window pairs from configured window sizes. Require UTC timestamps, complete candles, one instrument, non-overlapping OOS windows, and no OOS candle appearing in its train window. Reject datasets too small to produce at least one pair.
   - Verify: Red before splitter exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_walkforward.py
     ```

5. Add Optuna search-space sampler and strategy-config adapter [depends on #3]
   - File(s): `backend/src/harbor_bot/optimizer/search_space.py`, `backend/tests/test_optimizer_search_space.py`.
   - Reference behavior: Optuna trials choose bounded strategy parameters and each trial backtests through the same M5/M4 core. Session windows are searchable offsets from defaults, not hand-tuned replacements.
   - Change: Add functions that call Optuna `Trial.suggest_int`, `suggest_float`, or `suggest_categorical` according to optimizer config, return a params JSON dict, and produce a `StrategyConfig` variant from those params. Keep sampled values JSON-serializable for `opt_trials.params_json`. Do not mutate default config objects.
   - Verify: Red before sampler exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_search_space.py
     ```

6. Add walk-forward objective scoring over the M5 backtester [depends on #4, #5]
   - File(s): `backend/src/harbor_bot/optimizer/objective.py`, `backend/tests/test_optimizer_objective.py`.
   - Reference behavior: The only objective is out-of-sample expectancy divided by max drawdown, with hard minimum trade-count floors. Raw PnL is not the objective. All scores come from `run_backtest`.
   - Change: Add pure scoring functions that run each sampled `StrategyConfig` through `BacktestInput` for each walk-forward train/OOS pair, aggregate in-sample and out-of-sample stats, reject/prune parameter sets below configured trade-count floors, and calculate `is_score` and `oos_score` with a configured drawdown floor to avoid divide-by-zero semantics. Include a test double or monkeypatch proving `run_backtest` is the evaluator and no alternate strategy logic is used.
   - Verify: Red before objective exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_objective.py
     ```

7. Add robustness plateau scoring [depends on #6]
   - File(s): `backend/src/harbor_bot/optimizer/robustness.py`, `backend/tests/test_optimizer_robustness.py`.
   - Reference behavior: The source spec rejects sharp peaks and prefers parameter plateaus whose local neighbors also score well.
   - Change: Add deterministic neighbor generation from `SearchSpace` using configured neighbor steps, evaluate neighbor OOS scores through the same objective/backtester path, and compute a robustness score that penalizes lone spikes. Keep neighbor count and step sizes configurable. Do not introduce a second optimizer algorithm.
   - Verify: Red before robustness scoring exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_robustness.py
     ```

8. Add Optuna study runner with TPE sampler and median pruner [depends on #6, #7]
   - File(s): `backend/src/harbor_bot/optimizer/runner.py`, `backend/tests/test_optimizer_runner.py`.
   - Reference behavior: M6 implements Optuna TPE trials with a median pruner. The runner must return ranked robust candidates and trial records; it must not persist yet.
   - Change: Add an in-process runner that creates an Optuna study with `TPESampler` and `MedianPruner`, runs the configured number of trials, reports intermediate walk-forward OOS scores for pruning, records pruned/failed/completed trials, computes robustness for completed trials, and returns the top configured candidate count sorted by out-of-sample score then robustness score. Keep test datasets small and deterministic.
   - Verify: Red before runner exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_optimizer_runner.py
     ```

9. Persist optimization studies, trials, and paper variants [depends on #8]
   - File(s): `backend/src/harbor_bot/persistence/optimization_repository.py`, `backend/tests/integration/test_optimization_repository.py`.
   - Reference behavior: M2 schema already defines `opt_studies(search_space_json, walkforward_json, status)`, `opt_trials(study_id, trial_no, params_json, is_score, oos_score, robustness_score, pruned)`, and `variants(label, params_json, source_trial_id, status)`. M6 requires ranked candidates written as paper variants.
   - Change: Add repository functions to create an optimization study, append trial rows, append ranked candidate variants with status `paper`, and read a study with trials/variants by id. Persist study + trials + variants in one transaction for completed runs. Verify rollback if a trial or variant insert fails. Do not add new tables unless existing schema makes persistence impossible.
   - Verify: Red before repository exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_optimization_repository.py
     ```

10. Add optimizer service boundary [depends on #8, #9]
    - File(s): `backend/src/harbor_bot/optimizer/service.py`, `backend/tests/test_optimizer_service.py`.
    - Reference behavior: M6 exit requires an optimization run that writes ranked robust candidates. Existing frontend/API/background-worker work is out of scope. Tests must not need live OANDA credentials.
    - Change: Add a backend service function that accepts inline or fixture closed candles, optimizer config overrides, backtest assumptions, and instrument rules; runs the Optuna study runner; persists the study/trials/variants when an engine is configured; and returns study id, ranked candidates, trial summary, and data-separation metadata. Keep the service synchronous from the caller's perspective in M6. Do not add FastAPI endpoints, background workers, OANDA calls, or paper-engine execution.
    - Verify: Red before service exists, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_optimizer_service.py
      ```

11. Add optimizer run report and data-separation artifact [depends on #10]
    - File(s): `docs/research/m6-optimizer-run.md`, `backend/tests/test_optimizer_research_report.py`.
    - Reference behavior: M6 must prove the optimizer uses walk-forward out-of-sample scoring and does not read forward-test/live data. The output is ranked robust candidates, not live promotion.
    - Change: Add a deterministic report from the recorded fixtures and current optimizer defaults. The report must include dataset ranges, search-space config snapshot, walk-forward window summary, trial count, minimum trade floors, objective formula, top ranked candidates, paper variant status, and explicit data-separation notes that no live-forward data, `variant_trades`, OANDA streams, broker state, paper engine, or frontend UI were used.
    - Verify: Red before report exists, green after:
      ```bash
      cd backend
      uv run --extra dev pytest tests/test_optimizer_research_report.py
      cd ..
      grep -q 'walk-forward' docs/research/m6-optimizer-run.md
      grep -q 'out-of-sample' docs/research/m6-optimizer-run.md
      grep -q 'paper' docs/research/m6-optimizer-run.md
      grep -q 'no live-forward data' docs/research/m6-optimizer-run.md
      ```

12. Register optimizer exports and documentation [depends on #10, #11]
    - File(s): `backend/src/harbor_bot/optimizer/__init__.py`, `backend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: M6 changes the backend from backtest-capable to offline-optimization-capable. Docs must not imply paper engine, Lab UI, optimizer API endpoints, broker execution, or live-forward promotion exists.
    - Change: Export only stable optimizer entry points needed by tests and later phases. Update docs with M6 command shape, Optuna/TPE policy, walk-forward data-separation policy, persistence scope, ranked paper-variant output, and no-live-credentials policy.
    - Verify: Red before docs mention optimizer support, green after:
      ```bash
      grep -q 'optimizer' backend/README.md docs/development.md docs/architecture.md
      grep -q 'Optuna' backend/README.md docs/development.md
      grep -q 'walk-forward' docs/development.md docs/architecture.md
      grep -q 'no live-forward data' docs/development.md docs/architecture.md
      ```

13. Run the M6 exit gate [depends on #12]
    - File(s): Harbor repo.
    - Reference behavior: M6 exit requires `make ci` green and an optimization run that writes ranked robust candidates without reading forward-test data. No OANDA credentials are required.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest \
        tests/test_optimizer_dependency.py \
        tests/test_optimizer_models.py \
        tests/test_optimizer_walkforward.py \
        tests/test_optimizer_search_space.py \
        tests/test_optimizer_objective.py \
        tests/test_optimizer_robustness.py \
        tests/test_optimizer_runner.py \
        tests/integration/test_optimization_repository.py \
        tests/test_optimizer_service.py \
        tests/test_optimizer_research_report.py
      cd ..
      grep -q 'walk-forward' docs/research/m6-optimizer-run.md
      grep -q 'out-of-sample' docs/research/m6-optimizer-run.md
      grep -q 'no live-forward data' docs/research/m6-optimizer-run.md
      ```

## M6 Decision Register

No user-owned decisions are required in M6. Optimizer parameter bounds, scoring floors, walk-forward sizes, robustness settings, trial count, and candidate count are configuration values with checked-in defaults.

## Handoff

Execute only these M6 steps next. Do not add paper-engine execution, live-forward scoring, broker/OANDA calls, optimizer API endpoints, frontend/Lab UI, WebSocket work, deployment changes, or dashboard controls during M6. Stop after the M6 exit gate; the paper-engine/Lab work belongs to later phases.
