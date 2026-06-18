# Backend

Python FastAPI bot process for Harbor.

The backend currently owns the async PostgreSQL persistence foundation, the OANDA read path, the pure strategy package, the deterministic closed-candle backtester, and the offline optimizer. The read path includes a raw async `httpx` OANDA client, typed response adapters, JSON-line stream parsing, a closed M1 candle builder, historical candle ingestion, pricing stream ingestion, and transaction stream framing.

The pure strategy core consumes closed-candle data, session levels, current state, risk context, instrument rules, and config. It emits strategy decisions and market-entry setups only. It does not place orders, reconcile broker execution, call OANDA, or write persistence.

The backtester replays local recorded closed-candle fixtures through the same strategy core, simulates market-entry fills, broker-side brackets, and NY-close exits, then returns deterministic stats and trade lists. Backtest runs and trades can be persisted through `backtest_runs` and `backtest_trades`, and the backend exposes synchronous M5 API endpoints at `POST /api/backtests` and `GET /api/backtests/{run_id}`.

The optimizer uses Optuna TPE with a median pruner over bounded strategy parameters, scores trials by walk-forward out-of-sample expectancy divided by max drawdown, computes robustness against neighboring parameter sets, persists `opt_studies`/`opt_trials`, and writes ranked candidate `variants` with `paper` status. It uses no live-forward data, does not call OANDA, and does not run the paper engine.

M7 adds read-only observability APIs for the dashboard:

- `GET /api/status` returns bot/session/connection mode, guarded trading state, day P&L, account NAV, open positions, trade count, and last heartbeat facts.
- `GET /api/levels` returns persisted session levels for a requested date and instrument.
- `GET /api/candles` returns persisted M1 candles for a requested instrument and time range.
- `GET /api/markers` returns server-authored sweeps, FVG overlays, signals, and trades for a requested date and instrument.
- `GET /api/events` returns recent structured event rows by optional level and limit.
- `/ws` accepts dashboard WebSocket clients and pushes validated JSON envelopes for `candle`, `level_update`, `sweep`, `fvg`, `signal`, `trade`, `equity`, `status`, and `log` messages.

The M7 API does not place orders, call OANDA, mutate config, expose optimizer endpoints, enable trading, flatten positions, or require live credentials.

M8 adds the shadow paper engine and Lab API. The paper-forward service runs every active `paper` variant against the same injected closed-candle stream, reuses the pure strategy core plus backtester fill math, and persists simulated per-variant fills to `variant_trades`. The Lab aggregates optimizer studies, candidate scatter data, paper variants, leaderboard rows, and variant equity curves through `POST /api/optimize`, `GET /api/optimize/{study_id}`, `GET /api/variants`, `POST /api/variants`, and `POST /api/variants/{variant_id}/retire`.

M8 enforces live-forward data separation: optimizer paths read closed candles plus optimizer tables and never consume `variant_trades`; paper-forward reads active `variants` plus closed live candles; Lab live-forward scoring reads `variant_trades`. These APIs are paper-only. They do not place OANDA orders, promote variants to live config, enable trading, flatten positions, mutate strategy config, or require OANDA/live credentials for tests.

M9 adds guarded OANDA practice execution for exactly one `promoted` variant. Practice trading stays disabled until `POST /api/control/trading` succeeds with the configured confirmation token, and `POST /api/control/flatten` closes OANDA practice exposure through the execution boundary. Orders are market entries with attached stop-loss and take-profit; transaction replay dedupes OANDA ids and reconciles persisted trades by broker order id, client order id, broker trade id, open transaction id, and close transaction id. Alerts use ntfy first through the notifier boundary, with Telegram behind the same interface.

M10 exposes the full product surface through the web UI and matching backend routes. Product routes include Trades (`GET /api/trades`), Backtests (`GET/POST /api/backtests`, `GET /api/backtests/{run_id}`), optimizer studies (`GET/POST /api/optimize`, `GET /api/optimize/{study_id}`), variants (`GET /api/variants`, `GET /api/variants/{variant_id}`, paper create/retire, and practice promote), Config (`GET/PUT /api/config`), Events (`GET /api/events` with level/module/type/date filters), Operations status (`GET /api/status`), guarded practice controls, `/health`, `/ready`, and `/ws`.

Config writes are diffed, validated, confirmed with `APPLY_CONFIG`, and audited as events. Historical backtests, optimizer trials, paper-forward evidence, and promoted variants are not silently retuned by a config write.

Useful M9 practice execution checks:

```bash
uv run --extra dev pytest tests/test_oanda_execution_client.py tests/test_execution_api.py
uv run --extra dev pytest tests/test_practice_execution_service.py tests/test_execution_reconciliation.py tests/test_execution_controls.py
uv run --extra dev pytest tests/e2e/test_oanda_practice_execution.py
```

Real OANDA practice smoke probes are manual and credentialed; run them as `with-cred -- <command>` so `OANDA_API_TOKEN`, `OANDA_ACCOUNT_ID`, and notifier credentials are injected for that command only.

Deployment smoke checks use the LAN endpoint `http://192.168.66.3:30091/`. Non-credentialed checks can run with `scripts/smoke.sh`; any manual smoke that touches OANDA, AWS, database, ntfy, Telegram, or other secrets must run as `with-cred -- <command>`.

OANDA, backtester, and optimizer tests use fixtures and mocked transports; CI does not call live broker services and does not require live OANDA credentials.

Run backend checks from this directory:

```bash
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
uv run --extra dev pytest
```

Useful backtester checks:

```bash
uv run --extra dev pytest tests/test_backtester_models.py tests/test_backtester_data.py
uv run --extra dev pytest tests/test_backtester_fills.py tests/test_backtester_engine.py
uv run --extra dev pytest tests/test_backtester_stats.py tests/test_backtester_snapshots.py
uv run --extra dev pytest tests/integration/test_backtest_repository.py tests/test_backtest_api.py
```

Useful optimizer checks:

```bash
uv run --extra dev pytest tests/test_optimizer_models.py tests/test_optimizer_walkforward.py
uv run --extra dev pytest tests/test_optimizer_search_space.py tests/test_optimizer_objective.py
uv run --extra dev pytest tests/test_optimizer_robustness.py tests/test_optimizer_runner.py
uv run --extra dev pytest tests/integration/test_optimization_repository.py tests/test_optimizer_service.py
```

Useful observability checks:

```bash
uv run --extra dev pytest tests/test_observability_models.py
uv run --extra dev pytest tests/integration/test_observability_repository.py
uv run --extra dev pytest tests/test_observability_service.py tests/test_observability_api.py tests/test_observability_websocket.py
```

Useful M8 Lab and shadow paper engine checks:

```bash
uv run --extra dev pytest tests/test_paper_engine_models.py tests/test_paper_engine_engine.py tests/test_paper_engine_service.py
uv run --extra dev pytest tests/integration/test_variant_repository.py tests/test_lab_service.py tests/test_lab_api.py
```

Alembic is configured by `alembic.ini` with migration scripts in `db/migrations`.
