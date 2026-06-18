# Harbor M4 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M4 - Pure strategy core and risk math` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; deterministic fixtures cover every strategy rule named in M4; the strategy core consumes only closed candles and performs no OANDA, database, API, frontend, or broker-execution I/O.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M4.
- Product/strategy source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 4, 5, and 6.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, asyncio, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) requires the strategy core to be pure, deterministic, and driven only by closed candles, session levels, current state, and config.
- Reuse from M2/M3:
  - [backend/src/harbor_bot/config/defaults.yaml](backend/src/harbor_bot/config/defaults.yaml) owns default strategy parameter values and bounds.
  - [backend/src/harbor_bot/config/defaults.py](backend/src/harbor_bot/config/defaults.py) loads default config data.
  - [backend/src/harbor_bot/feed/candles.py](backend/src/harbor_bot/feed/candles.py) provides `ClosedCandle` from the feed boundary.
  - [backend/src/harbor_bot/oanda/types.py](backend/src/harbor_bot/oanda/types.py) provides OANDA instrument metadata shape that can feed strategy instrument rules.
- M4 boundaries:
  - No persistence writes, migrations, OANDA calls, order placement, broker execution, backtester engine, optimizer, API endpoints, frontend UI, or deployment changes.
  - Parameter values are runtime config. If a value is needed for a strategy rule, expose it in `StrategyConfig` or instrument metadata rather than asking for a decision.
  - M4 emits strategy decisions and market-entry setups only. It must not simulate broker fills; risk/target/sizing functions accept an explicit entry price so later live execution/backtesting can provide the actual market fill.

## Steps

1. Confirm M3 baseline before strategy work
   - File(s): `backend/src/harbor_bot/feed/*`, `backend/src/harbor_bot/oanda/*`, `backend/src/harbor_bot/config/defaults.yaml`, `docs/adr/0003-pure-closed-candle-strategy-core.md`.
   - Reference behavior: M4 depends on M3 closed-candle feed output and ADR-0003's pure strategy boundary.
   - Change: No source changes.
   - Verify: Red if M3 drifted, green when Harbor is ready for pure strategy work:
     ```bash
     make ci
     cd backend
     uv run --extra dev pytest tests/test_candle_builder.py tests/test_oanda_types.py tests/integration/test_historical_ingestion.py tests/integration/test_pricing_stream_ingestion.py
     grep -q 'Pure Closed-Candle Strategy Core' ../docs/adr/0003-pure-closed-candle-strategy-core.md
     ```

2. Add strategy domain models and config adapter [depends on #1]
   - File(s): `backend/src/harbor_bot/strategy/__init__.py`, `backend/src/harbor_bot/strategy/models.py`, `backend/tests/test_strategy_models.py`.
   - Reference behavior: ADR-0003 says the core consumes closed candles, session levels, state, and config. `defaults.yaml` contains `instrument`, `timezone`, `sessions`, `fvg_window`, `sweep_buffer_pips`, `risk_per_trade_pct`, `max_daily_loss_pct`, `target_mode`, `rr_floor`, `one_trade_per_level`, `max_trades_per_day`, `max_spread_pips`, `swing_lookback`, and `max_units`.
   - Change: Add immutable dataclasses/enums for `StrategyConfig`, `InstrumentRules`, `SessionLevels`, `LevelName`, `Bias`, `SweepState`, `DayState`, `MarketEntrySetup`, `FlattenDecision`, and `StrategyDecision`. Add a config adapter that builds `StrategyConfig` from the default-config mapping without depending on persistence. Include pips-to-price conversion on `InstrumentRules` using pip location metadata. Reject non-closed candle inputs at the strategy boundary.
   - Verify: Red before the strategy package exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_models.py
     ```

3. Implement session calendar and liquidity level calculation [depends on #2]
   - File(s): `backend/src/harbor_bot/strategy/sessions.py`, `backend/tests/test_strategy_sessions.py`.
   - Reference behavior: The source spec anchors all windows to `America/New_York` and converts to UTC at runtime. Asia is 20:00 previous day to 00:00, London is 02:00 to 05:00, and NY trade window is 09:30 to 11:30. At the start of the NY window, compute Asia/London high/low from completed M1 candles and persist them later outside the core.
   - Change: Add pure functions that resolve session windows for a trading date using `zoneinfo`, determine whether a candle is inside the NY trade window, and compute `SessionLevels` from closed M1 candles. Do not hardcode UTC offsets. Do not write levels to persistence.
   - Verify: Red before session functions exist, green after, including DST-sensitive fixtures:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_sessions.py
     ```

4. Implement sweep detection and level cooldown state [depends on #2, #3]
   - File(s): `backend/src/harbor_bot/strategy/sweeps.py`, `backend/tests/test_strategy_sweeps.py`.
   - Reference behavior: A high sweep is `candle.high > level + buffer` and `candle.close < level`, producing bearish bias. A low sweep is `candle.low < level - buffer` and `candle.close > level`, producing bullish bias. Only the first sweep of a given level per day is actionable when `one_trade_per_level` is true. The sweep deadline is now plus `fvg_window` closed candles.
   - Change: Add pure sweep detection over a single closed candle plus session levels/config/day state. Record level name, level price, bias, sweep extreme, sweep candle time, and FVG deadline index. Add day-state helpers for marking a level taken/cooling down without mutating existing state.
   - Verify: Red before sweep functions exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_sweeps.py
     ```

5. Implement FVG detection and window validation [depends on #4]
   - File(s): `backend/src/harbor_bot/strategy/fvgs.py`, `backend/tests/test_strategy_fvgs.py`.
   - Reference behavior: A bullish FVG is `low[i] > high[i-2]` and is valid only after a bullish low sweep. A bearish FVG is `high[i] < low[i-2]` and is valid only after a bearish high sweep. The FVG must form within `fvg_window` closed candles after the sweep and inside the NY trade window.
   - Change: Add pure FVG detection over closed-candle windows and active `SweepState`. Return top, bottom, midpoint, type, source sweep, and qualifying candle time. Reject wrong-direction gaps, expired windows, incomplete candle inputs, and out-of-window candles.
   - Verify: Red before FVG functions exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_fvgs.py
     ```

6. Implement market-entry setup, stop, target, and sizing math [depends on #5]
   - File(s): `backend/src/harbor_bot/strategy/signals.py`, `backend/tests/test_strategy_signals.py`.
   - Reference behavior: The strategy requests a market entry when the qualifying FVG candle closes. Stop is beyond the sweep extreme by `sweep_buffer_pips`, optionally widened to the swing low/high over `swing_lookback` closed candles. Target mode `rr_or_liquidity` takes whichever is closer between the RR target and the opposite untapped session level, while respecting the configured RR floor. Position sizing uses `risk_per_trade_pct` of NAV divided by stop distance, then clamps to broker/instrument min/step and `max_units`.
   - Change: Add pure functions that build a `MarketEntrySetup` from an FVG/sweep context and compute stop/target/sizing when supplied an explicit entry price, NAV, session levels, instrument rules, and config. Do not simulate fills or place orders. Treat broker min size, unit precision/step, hard max units, and quote/home conversion as runtime instrument inputs.
   - Verify: Red before signal/risk math exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_signals.py
     ```

7. Implement risk gates [depends on #2, #6]
   - File(s): `backend/src/harbor_bot/strategy/risk.py`, `backend/tests/test_strategy_risk.py`.
   - Reference behavior: The source spec names hard guards for max one concurrent position, `max_trades_per_day`, one trade per level per day, NY close flattening, daily-loss kill switch, and spread filter. News filtering is optional v2 and is not part of M4.
   - Change: Add pure risk-gate functions for spread, daily loss, trade count, one-position, and one-trade-per-level. Return explicit allow/veto results with reason codes that later persistence/API layers can record. Add a flatten/disable decision for NY window close and daily-loss breach. Do not send notifications or broker commands.
   - Verify: Red before risk gates exist, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_risk.py
     ```

8. Implement the pure strategy orchestrator [depends on #3, #4, #5, #6, #7]
   - File(s): `backend/src/harbor_bot/strategy/core.py`, `backend/tests/test_strategy_core.py`.
   - Reference behavior: ADR-0003 requires one deterministic strategy core for live trading, backtesting, optimization, and paper variants. The source state machine is `IDLE -> MARK_LEVELS -> WAIT_SWEEP -> SWEPT -> WAIT_FVG -> IN_TRADE -> FLAT/COOLDOWN`, with NY close flatten/reset. No current or incomplete candle may reach the strategy boundary.
   - Change: Add a pure `evaluate_closed_candle` or equivalent core function that consumes current immutable strategy state, a closed candle, session levels if already marked, config, risk context, and instrument rules, then returns new state plus decisions. It must compose the session, sweep, FVG, signal setup, and risk-gate modules without database/OANDA/API calls. Include deterministic fixtures for clean sweep-to-entry, rejected sweep, wrong-direction FVG, FVG expiry, NY close flatten, and closed-candle-only rejection.
   - Verify: Red before core orchestration exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_strategy_core.py
     ```

9. Register strategy exports and documentation [depends on #8]
   - File(s): `backend/src/harbor_bot/strategy/__init__.py`, `backend/README.md`, `docs/development.md`, `docs/architecture.md`.
   - Reference behavior: M4 changes the backend from read-path plus persistence to a pure strategy package. Docs must say strategy logic is pure and closed-candle-only, and must not imply broker execution/backtesting/API endpoints are implemented.
   - Change: Export only stable strategy entry points needed by tests and future phases. Update docs with the M4 command shape, closed-candle invariant, config-driven parameter rule, and boundary exclusions.
   - Verify: Red before docs mention only persistence/OANDA read path, green after:
     ```bash
     grep -q 'pure strategy' backend/README.md docs/development.md docs/architecture.md
     grep -q 'closed-candle' backend/README.md docs/development.md docs/architecture.md
     grep -q 'strategy parameters are config' docs/development.md
     ```

10. Run the M4 exit gate [depends on #9]
    - File(s): Harbor repo.
    - Reference behavior: M4 exit requires `make ci` green and deterministic fixtures covering every strategy rule named in the milestone. No live OANDA credentials, Postgres schema changes, API endpoints, or broker execution are required for the gate.
    - Change: No source changes.
    - Verify:
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
      ```

## M4 Decision Register

| Step | Decision you own |
| ---- | ---- |
| None | Strategy parameters and instrument mechanics are runtime config or metadata inputs, not user-owned architecture decisions. |

## Handoff

Execute only these M4 steps next. Do not add persistence writes, migrations, OANDA calls, order placement, broker execution, backtester fill simulation, optimizer work, REST/WebSocket API endpoints, frontend UI, or deployment changes during M4.
