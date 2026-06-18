# Harbor M5 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M5 - Backtester and research gate` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; recorded closed-candle fixtures replay through the same M4 pure strategy core into deterministic stats and trade lists; backtest runs/trades persist to Postgres; the research gate produces a baseline report before M6 optimizer work.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M5.
- Product/backtest source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 4, 5, 6, 12, and 13.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires live, backtest, optimization, and paper variants to call the same pure strategy core over closed candles.
- Reuse from M2/M3/M4:
  - [backend/src/harbor_bot/feed/candles.py](backend/src/harbor_bot/feed/candles.py) provides `ClosedCandle`.
  - [backend/src/harbor_bot/config/defaults.py](backend/src/harbor_bot/config/defaults.py) loads strategy defaults.
  - [backend/src/harbor_bot/strategy/core.py](backend/src/harbor_bot/strategy/core.py) provides the pure strategy orchestrator.
  - [backend/src/harbor_bot/strategy/sessions.py](backend/src/harbor_bot/strategy/sessions.py) computes session windows and levels.
  - [backend/src/harbor_bot/strategy/models.py](backend/src/harbor_bot/strategy/models.py) provides config/state/decision models and instrument rules.
  - [backend/src/harbor_bot/persistence/database.py](backend/src/harbor_bot/persistence/database.py) owns async engine/transaction helpers.
  - [backend/src/harbor_bot/persistence/schema.py](backend/src/harbor_bot/persistence/schema.py) already defines `backtest_runs` and `backtest_trades`.
  - [backend/src/harbor_bot/api.py](backend/src/harbor_bot/api.py) is the current FastAPI app factory.
- M5 boundaries:
  - No optimizer/TPE/walk-forward search, paper variant engine, broker/OANDA calls, live execution, frontend UI, deployment changes, or schema expansion unless a step explicitly requires a migration fix.
  - Backtest assumptions such as initial NAV, spread, slippage, ambiguous bracket fill policy, and commission are runtime config values with defaults, not user decisions.
  - M5 may add start/read backtest API endpoints because the milestone explicitly names them, but it must not add dashboard UI or live trading controls.
  - The M5 research gate is a real [DECISION] point: after the baseline report exists, stop and ask whether to continue to M6.

## Steps

1. Confirm M4 baseline before backtester work
   - File(s): `backend/src/harbor_bot/strategy/*`, `backend/src/harbor_bot/feed/candles.py`, `backend/src/harbor_bot/persistence/schema.py`, `backend/src/harbor_bot/api.py`.
   - Reference behavior: M5 depends on the M4 pure strategy core and M2 `backtest_runs`/`backtest_trades` schema. Backtesting must reuse `evaluate_closed_candle`; it must not fork strategy semantics.
   - Change: No source changes.
   - Verify: Red if M4 drifted, green when Harbor is ready for backtester work:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest \
       tests/test_strategy_models.py \
       tests/test_strategy_sessions.py \
       tests/test_strategy_sweeps.py \
       tests/test_strategy_fvgs.py \
       tests/test_strategy_signals.py \
       tests/test_strategy_risk.py \
       tests/test_strategy_core.py
     grep -q 'backtest_runs' src/harbor_bot/persistence/schema.py
     grep -q 'backtest_trades' src/harbor_bot/persistence/schema.py
     ```

2. Add backtest domain models and runtime assumptions [depends on #1]
   - File(s): `backend/src/harbor_bot/backtester/__init__.py`, `backend/src/harbor_bot/backtester/models.py`, `backend/tests/test_backtester_models.py`.
   - Reference behavior: M5 needs spread/slippage assumptions, market-entry fills, broker-side bracket simulation, forced NY close, stats output, and persisted run/trade shapes. Parameter values are config, not architecture decisions.
   - Change: Add immutable dataclasses/enums for `BacktestConfig`, `BacktestInput`, `BacktestRunResult`, `BacktestTrade`, `BacktestStats`, `EquityPoint`, `FillPolicy`, and `BacktestStatus`. Defaults should be conservative and configurable: initial NAV, spread pips, slippage pips, commission per unit, and ambiguous bracket fill policy. Include converters between `ClosedCandle`/strategy decisions and backtest-local trade records. Do not implement engine replay yet.
   - Verify: Red before the backtester package exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_models.py
     ```

3. Add recorded candle fixtures and replay input validation [depends on #2]
   - File(s): `backend/src/harbor_bot/backtester/data.py`, `backend/tests/fixtures/backtester/*.json`, `backend/tests/test_backtester_data.py`.
   - Reference behavior: The source spec requires recorded-day regression/snapshot tests and closed-candle-only behavior. M5 must replay historical candles, not fetch live OANDA data.
   - Change: Add compact recorded-day JSON fixtures for `EUR_USD` closed M1 candles that cover one clean signal day and one no-trade day. Add loaders that convert fixture JSON to `ClosedCandle`, require timezone-aware UTC timestamps, require `complete=true`, sort by timestamp, and reject duplicate `(instrument, ts)` rows. Keep loaders pure and filesystem/local-data only.
   - Verify: Red before fixture loader exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_data.py
     ```

4. Implement deterministic fill and bracket simulation [depends on #2]
   - File(s): `backend/src/harbor_bot/backtester/fills.py`, `backend/tests/test_backtester_fills.py`.
   - Reference behavior: The source spec says backtests simulate fills, spread/slippage assumptions, broker-side SL/TP brackets, and forced NY close. M4 emits market-entry setups only; M5 supplies fill assumptions.
   - Change: Add pure fill simulation for market entries at the next closed candle's open adjusted by spread/slippage, stop-loss/take-profit bracket exits using subsequent candle high/low, pessimistic handling when stop and target are both touched in the same candle, and forced NY-close exits. Compute PnL and R multiple from side, units, entry, stop, target, and exit. Do not call OANDA or persistence.
   - Verify: Red before fill simulator exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_fills.py
     ```

5. Implement the pure backtest engine over the M4 strategy core [depends on #3, #4]
   - File(s): `backend/src/harbor_bot/backtester/engine.py`, `backend/tests/test_backtester_engine.py`.
   - Reference behavior: Live trading, backtesting, optimization, and paper variants all call the same pure strategy core. The engine must feed only closed candles, compute session levels at the NY window boundary, reset day state by trading date, use the fill simulator for entries/exits, and never expose future candles to the strategy.
   - Change: Add a deterministic engine that replays closed candles in timestamp order, calls `evaluate_closed_candle` incrementally, opens at most one simulated position from a `market_entry` decision, advances broker-side bracket simulation candle by candle, forces NY close exits, and returns a `BacktestRunResult` with trades and an equity curve. Include a lookahead guard test proving the strategy call only receives history through the current closed candle.
   - Verify: Red before engine exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_engine.py
     ```

6. Add stats and regression snapshot coverage [depends on #5]
   - File(s): `backend/src/harbor_bot/backtester/stats.py`, `backend/tests/test_backtester_stats.py`, `backend/tests/test_backtester_snapshots.py`.
   - Reference behavior: M5 exit requires stats output and regression snapshots from recorded days so refactors cannot silently change signals/trades. The source spec calls out sanity checking for lookahead leakage.
   - Change: Add stats functions for trade count, win rate, net PnL, expectancy, average R, max drawdown, ending NAV, and a simple lookahead-sanity flag for implausible fixture results. Add snapshot tests for the clean recorded day and no-trade recorded day that assert exact trade list and stats JSON.
   - Verify: Red before stats/snapshots exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_stats.py tests/test_backtester_snapshots.py
     ```

7. Persist backtest runs and trades [depends on #5, #6]
   - File(s): `backend/src/harbor_bot/persistence/backtest_repository.py`, `backend/tests/integration/test_backtest_repository.py`.
   - Reference behavior: M2 schema already defines `backtest_runs(params_json, stats_json)` and `backtest_trades(run_id, side, units, entry_price, entry_ts, exit_price, exit_ts, pnl, r_multiple, exit_reason)`. M5 requires persisted backtest runs and trades.
   - Change: Add repository functions to append a completed backtest run and its trades in one transaction, and read a run with trades by id. Preserve params/stats JSON exactly enough for API/report consumers. Verify rollback if any trade insert fails. Do not add new tables unless an existing schema bug makes persistence impossible.
   - Verify: Red before repository exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_backtest_repository.py
     ```

8. Add backtest service boundary and API endpoints [depends on #5, #7]
   - File(s): `backend/src/harbor_bot/backtester/service.py`, `backend/src/harbor_bot/api.py`, `backend/tests/test_backtest_api.py`.
   - Reference behavior: M5 explicitly adds API endpoints to start/read backtests. Existing frontend work is out of scope. Tests must not need live OANDA credentials.
   - Change: Add a backend service function that accepts a backtest request with inline or preloaded closed candles, strategy/default config, instrument rules, and backtest assumptions; runs the engine; persists the result when an engine is configured; and returns run id, stats, and trades. Add FastAPI routes `POST /api/backtests` and `GET /api/backtests/{run_id}` using dependency injection so tests can use a fake service without Postgres. Keep routes synchronous from the caller's perspective in M5; do not add background workers.
   - Verify: Red before endpoints exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtest_api.py
     ```

9. Add baseline research report and gate artifact [depends on #6, #7]
   - File(s): `docs/research/m5-baseline-backtest.md`, `backend/tests/test_backtester_research_report.py`.
   - Reference behavior: M5 includes a research gate: continue to optimizer only if baseline backtests show a plausible out-of-sample edge and no lookahead symptoms. The source spec says if there is no edge, stop and rethink the rules before building more.
   - Change: Generate a deterministic baseline report from the recorded fixtures and any locally available historical fixture data. The report must include dataset ranges, parameter/config snapshot, trade count, net PnL, max drawdown, expectancy, average R, lookahead sanity notes, and an explicit `M6_RESEARCH_GATE: pending` line. Do not make the continue/stop decision in code.
   - Verify: Red before the report exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_backtester_research_report.py
     cd ..
     grep -q 'M6_RESEARCH_GATE: pending' docs/research/m5-baseline-backtest.md
     grep -q 'lookahead' docs/research/m5-baseline-backtest.md
     ```
10. Register backtester exports and documentation [depends on #8, #9]
    - File(s): `backend/src/harbor_bot/backtester/__init__.py`, `backend/README.md`, `docs/development.md`, `docs/architecture.md`.
    - Reference behavior: M5 changes the backend from pure strategy plus read path to a backtest-capable backend with persisted research runs and minimal backtest API endpoints. Docs must not imply optimizer, paper engine, broker execution, or dashboard UI exists.
    - Change: Export only stable backtester entry points needed by tests and future phases. Update docs with M5 command shape, recorded-fixture policy, no-live-credentials policy, persistence/API scope, and research gate status.
    - Verify: Red before docs mention no backtester support, green after:
      ```bash
      grep -q 'backtester' backend/README.md docs/development.md docs/architecture.md
      grep -q 'recorded fixtures' docs/development.md
      grep -q 'research gate' docs/development.md docs/architecture.md
      ```

11. Run the M5 exit gate [depends on #10]
    - File(s): Harbor repo.
    - Reference behavior: M5 exit requires `make ci` green, replayable historical fixtures into stats/trade lists, persisted backtest runs/trades, and a research gate artifact. No live OANDA credentials are required.
    - Change: No source changes.
    - Verify:
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
      ```

12. Review the M5 research gate [DECISION] [depends on #11]
    - File(s): `docs/research/m5-baseline-backtest.md`.
    - Reference behavior: M5 includes a research gate before M6 optimizer work. Continue only if baseline backtests show a plausible out-of-sample edge and no lookahead symptoms; otherwise stop and rethink the strategy rules first.
    - Change: No source changes.
    - Verify: Red if the gate artifact is missing, green when the decision can be made from the report:
      ```bash
      grep -q 'M6_RESEARCH_GATE: pending' docs/research/m5-baseline-backtest.md
      grep -q 'lookahead' docs/research/m5-baseline-backtest.md
      ```
    - Stop condition: Ask whether to continue toward M6 optimizer work. Do not plan or implement optimizer work in M5.

## M5 Decision Register

| Step | Decision you own |
| ---- | ---- |
| #12 | Decide, after reviewing the baseline report, whether the observed out-of-sample behavior is plausible enough to continue to M6 optimizer work or whether strategy rules should be revised first. |

## Handoff

Execute only these M5 steps next. Do not add optimizer/TPE/walk-forward search, paper variant engine, broker/OANDA calls, live execution, frontend UI, deployment changes, or dashboard controls during M5. Stop after step #12 asks for the M6 decision.
