# Harbor M2 - Phase Plan

Expand [HARBOR-PLAN.md](HARBOR-PLAN.md) milestone `M2 - Persistence and configuration foundation` into execution-ready steps. Run these steps in order. The phase exit gate is `make ci` green; Alembic migrations apply cleanly to an empty real Postgres database; default config seeding is idempotent.

## Phase Context

- Source milestone: [HARBOR-PLAN.md](HARBOR-PLAN.md) M2.
- Product/data-model source: [oanda-bot-spec.md](oanda-bot-spec.md) sections 4, 6, 10, 12, and 15.
- Backend decision: [ADR-0002](docs/adr/0002-python-fastapi-backend.md) selects Python 3.12, FastAPI, SQLAlchemy/Alembic, async Postgres, and `uv`.
- Strategy boundary decision: [ADR-0003](docs/adr/0003-pure-closed-candle-strategy-core.md) keeps strategy logic pure; persistence records facts but does not compute strategy semantics.
- Platform decision: [ADR-0001](docs/adr/0001-true-nas-platform-deployment.md) keeps database ownership/credentials in Ahara TrueNAS platform integration.
- Testing reference: `/home/dev/repos/ahara-standards/standards/testing.md` requires real Postgres integration tests for database operations.
- Current scaffold:
  - [backend/pyproject.toml](backend/pyproject.toml) already includes SQLAlchemy, asyncpg, Alembic, PyYAML, pytest, pytest-asyncio, and ruff.
  - [db/migrations/README.md](db/migrations/README.md) reserves the migration home.
  - Platform ownership lives in `ahara-infra`; M2 does not touch deployment resources.

## Steps

1. Confirm corrected M0 baseline before persistence work
   - File(s): `platform.yml`, `Makefile`, `compose.yaml`, `backend/pyproject.toml`, `db/migrations/README.md`.
   - Reference behavior: M2 depends on M0. Harbor has Python/TypeScript/TrueNAS compose scaffolding, Alembic/SQLAlchemy dependencies, and a migration home.
   - Change: No source changes.
   - Verify: Red if M0 drifted, green when Harbor is ready for persistence:
     ```bash
     make ci
     grep -q '^  - python$' platform.yml
     grep -q '^  - typescript$' platform.yml
     grep -q 'sqlalchemy' backend/pyproject.toml
     grep -q 'alembic' backend/pyproject.toml
     test -f db/migrations/README.md
     ```

2. Add runtime database settings boundary
   - File(s): `backend/src/harbor_bot/settings.py`, `backend/tests/test_settings.py`.
   - Reference behavior: `compose.yaml` supplies `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME`; tests need a `DATABASE_URL` override. ADR-0002 requires async Postgres via SQLAlchemy/asyncpg.
   - Change: Add a small Pydantic settings object that derives an async SQLAlchemy URL from `DATABASE_URL` when present, otherwise from the compose DB variables. Keep settings free of OANDA/client behavior.
   - Verify: Red before `harbor_bot.settings` exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_settings.py
     ```

3. Define SQLAlchemy table metadata for the M2 data model
   - File(s): `backend/src/harbor_bot/persistence/__init__.py`, `backend/src/harbor_bot/persistence/schema.py`, `backend/tests/test_schema.py`.
   - Reference behavior: `oanda-bot-spec.md` section 6 names the persistence tables. ADR-0003 says persistence records backend-authored facts and must not recompute strategy logic.
   - Change: Define SQLAlchemy Core metadata for `candles`, `sessions`, `sweeps`, `fvgs`, `signals`, `trades`, `equity_snapshots`, `events`, `config`, `backtest_runs`, `backtest_trades`, `opt_studies`, `opt_trials`, `variants`, and `variant_trades`. Include unique constraints for `candles(instrument, ts)`, `sessions(date, instrument)`, and `opt_trials(study_id, trial_no)`; foreign keys for sweep/FVG/signal/trade, backtest trade, trial/variant, and variant trade relationships; JSONB columns for `*_json`/`data_json`; and check constraints for status/direction/type fields that the source spec enumerates.
   - Verify: Red before the schema module exists, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_schema.py
     ```

4. Add the real Postgres integration test harness [depends on #2]
   - File(s): `backend/tests/integration/conftest.py`, `backend/tests/integration/test_postgres_harness.py`.
   - Reference behavior: Ahara testing standards require real Postgres for SQL correctness, constraint behavior, migrations, and transaction behavior. `../bookmarker` uses Docker CLI helpers for Postgres tests instead of Python testcontainers. This is test wiring for M2, not application behavior.
   - Change: Add a pytest fixture that starts a fresh Postgres container through `docker run`, publishes a fixed host port, waits with `pg_isready`, returns an async SQLAlchemy URL, and removes the container on teardown. Keep the fixture local to tests; do not add Docker services to `compose.yaml`.
   - Verify: Red before the dependency/fixture exists, green after:
     ```bash
     cd backend
     uv sync --extra dev
     uv run --extra dev pytest tests/integration/test_postgres_harness.py
     ```

5. Wire Alembic to the Harbor metadata and create the initial schema migration [depends on #3, #4]
   - File(s): `backend/alembic.ini`, `db/migrations/env.py`, `db/migrations/script.py.mako`, `db/migrations/versions/0001_persistence_foundation.py`, `backend/tests/integration/test_migrations.py`.
   - Reference behavior: M2 requires Alembic migrations for every section-6 table, and the exit gate requires migrations to apply cleanly to an empty Postgres database.
   - Change: Configure Alembic to use `db/migrations` as the script location and `harbor_bot.persistence.schema.metadata` as target metadata. Add the initial migration that creates the M2 schema. The migration must be deterministic and must not read application secrets.
   - Verify: Red before Alembic is wired/migration exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_migrations.py::test_migrations_apply_to_empty_postgres
     uv run --extra dev pytest tests/integration/test_migrations.py::test_expected_tables_and_constraints_exist
     ```

6. Add configurable strategy defaults [depends on #5]
   - File(s): `backend/src/harbor_bot/config/defaults.yaml`, `backend/tests/test_default_config_file.py`.
   - Reference behavior: `oanda-bot-spec.md` locks `EUR_USD`, `America/New_York`, session windows, `fvg_window = 8`, `risk_per_trade_pct = 0.5`, `max_daily_loss_pct = 2.0`, target mode `rr_or_liquidity`, RR floor `2.0`, one trade per level, and `min_forward_days = 20`. It leaves some initial runtime values as ranges or bounded tunables.
   - Change: Create `defaults.yaml` with fixed spec values plus editable tunable entries for `sweep_buffer_pips`, `max_trades_per_day`, `max_spread_pips`, `swing_lookback`, and `max_units`. Tunable entries must carry both a seed `value` and explicit `bounds`; these are operational defaults, not architecture decisions. Do not add strategy logic.
   - Verify: Red before `defaults.yaml` exists or misses required keys, green after:
     ```bash
     cd backend
     uv run --extra dev pytest tests/test_default_config_file.py
     ```

7. Implement idempotent default config seeding [depends on #5, #6]
   - File(s): `backend/src/harbor_bot/config/__init__.py`, `backend/src/harbor_bot/config/defaults.py`, `backend/src/harbor_bot/persistence/config_repository.py`, `backend/tests/integration/test_config_seed.py`.
   - Reference behavior: M2 requires default strategy config seeded from `defaults.yaml` into the `config(key, value_json, updated_ts)` table. The source spec says config is live-editable, so seeding must insert missing defaults without overwriting user-edited values.
   - Change: Add a YAML loader and repository method that seeds missing config rows inside one transaction. The second seed run must be a no-op, and existing rows must be preserved.
   - Verify: Red before the seeding code exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_config_seed.py
     ```

8. Add async database engine and transaction helpers [depends on #5]
   - File(s): `backend/src/harbor_bot/persistence/database.py`, `backend/tests/integration/test_transactions.py`.
   - Reference behavior: M2 requires repository boundaries and transaction patterns. ADR-0002 requires async SQLAlchemy/Postgres; ADR-0003 keeps persistence as I/O outside the pure strategy core.
   - Change: Add helpers to create an async engine/sessionmaker from settings and a transaction context used by repositories. Do not create global mutable sessions. Do not start the FastAPI app or wire startup migration behavior in M2.
   - Verify: Red before transaction helpers exist, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_transactions.py
     ```

9. Implement market-fact repositories [depends on #8]
   - File(s): `backend/src/harbor_bot/persistence/market_repository.py`, `backend/tests/integration/test_market_repository.py`.
   - Reference behavior: `candles` are a cache unique by `(instrument, ts)`; session levels are persisted facts for each trading date/instrument. All timestamps must be timezone-aware UTC at the boundary, while session definitions remain configured in America/New_York.
   - Change: Add repository methods for upserting closed candles and writing/reading session levels. Keep candle completion explicit; do not emit or compute strategy decisions here.
   - Verify: Red before the repository exists, green after against real Postgres:
     ```bash
     cd backend
     uv run --extra dev pytest tests/integration/test_market_repository.py
     ```

10. Implement decision/event repositories with rollback coverage [depends on #8, #9]
    - File(s): `backend/src/harbor_bot/persistence/decision_repository.py`, `backend/src/harbor_bot/persistence/event_repository.py`, `backend/tests/integration/test_decision_repository.py`, `backend/tests/integration/test_event_repository.py`.
    - Reference behavior: Section 6 names sweeps, FVGs, signals, trades, equity snapshots, and events as persisted backend facts. M2 asks for append-only transaction patterns, not broker execution or strategy computation.
    - Change: Add append/read methods for sweeps, FVGs, signals, trades, equity snapshots, and events. Verify foreign keys and check constraints through repository tests. Include a test that inserts multiple related facts in one transaction and proves a later error rolls back the whole group.
    - Verify: Red before repositories exist, green after against real Postgres:
      ```bash
      cd backend
      uv run --extra dev pytest tests/integration/test_decision_repository.py tests/integration/test_event_repository.py
      ```

11. Register persistence package exports and documentation [depends on #7, #10]
    - File(s): `backend/src/harbor_bot/persistence/__init__.py`, `backend/README.md`, `docs/development.md`, `db/migrations/README.md`.
    - Reference behavior: M2 changes the backend from a health-check scaffold to a database-backed package with migrations and real Postgres tests. Top-level docs stay concise and current-state.
    - Change: Export only stable persistence entry points needed by tests/future phases, and update docs with the migration/test command shape. Do not add API endpoints.
    - Verify: Red before docs mention old migration-only placeholder state, green after:
      ```bash
      ! grep -q 'Reserved home for Harbor PostgreSQL migrations' db/migrations/README.md
      grep -q 'Alembic' backend/README.md docs/development.md db/migrations/README.md
      grep -q 'real Postgres' docs/development.md
      ```

12. Run the M2 exit gate [depends on #11]
    - File(s): Harbor repo.
    - Reference behavior: M2 exit requires `make ci` green, clean migration apply on an empty real Postgres database, and idempotent config seeding.
    - Change: No source changes.
    - Verify:
      ```bash
      make ci
      cd backend
      uv run --extra dev pytest tests/integration/test_migrations.py tests/integration/test_config_seed.py
      cd ..
      ```

## M2 Decision Register

| Step | Decision you own |
| ---- | ---- |
| None | Strategy parameter values are configurable runtime data, not user-owned architecture decisions. |

## Handoff

Execute only these M2 steps next. Do not add API endpoints, strategy logic, broker/OANDA integration, frontend UI, or deployment changes during M2.
