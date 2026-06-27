import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_TABLES = {
    "alembic_version",
    "backtest_runs",
    "backtest_trades",
    "book_snapshots",
    "broker_transactions",
    "candles",
    "config",
    "equity_snapshots",
    "events",
    "fvgs",
    "opt_studies",
    "opt_trials",
    "sessions",
    "signals",
    "sweeps",
    "trades",
    "variant_trades",
    "variants",
}

EXPECTED_CONSTRAINTS = {
    "broker_transactions_transaction_id_key",
    "book_snapshots_book_type_instrument_snapshot_time_key",
    "candles_instrument_ts_key",
    "sessions_date_instrument_key",
    "signals_signal_key_key",
    "trades_client_order_id_key",
    "opt_trials_study_id_trial_no_key",
    "ck_sweeps_sweeps_direction_check",
    "ck_fvgs_fvgs_type_check",
    "ck_signals_signals_direction_check",
    "ck_signals_signals_status_check",
    "ck_trades_trades_side_check",
    "ck_variants_variants_status_check",
    "ck_book_snapshots_book_type_check",
}


def test_migrations_apply_to_empty_postgres(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    rows = asyncio.run(
        _fetch_all(
            postgres_url,
            "SELECT version_num FROM alembic_version ORDER BY version_num",
        )
    )

    assert rows == [("0006_orderbook_positionbook",)]


def test_expected_tables_and_constraints_exist(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    tables = {
        row[0]
        for row in asyncio.run(
            _fetch_all(
                postgres_url,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """,
            )
        )
    }
    constraints = {
        row[0]
        for row in asyncio.run(
            _fetch_all(
                postgres_url,
                """
                SELECT conname
                FROM pg_constraint
                WHERE connamespace = 'public'::regnamespace
                """,
            )
        )
    }

    assert tables == EXPECTED_TABLES
    assert constraints >= EXPECTED_CONSTRAINTS


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


async def _fetch_all(database_url: str, sql: str) -> list[tuple]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text(sql))
            return list(result)
    finally:
        await engine.dispose()
