import asyncio
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.market_repository import (
    get_candle_coverage,
    get_session_levels,
    latest_complete_candle_window,
    list_candles,
    list_daily_candle_aggregates,
    upsert_candle,
    upsert_session_levels,
)
from harbor_bot.settings import Settings


def test_candles_are_upserted_by_instrument_and_timestamp(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_candle_upsert(postgres_url))


def test_session_levels_are_upserted_by_date_and_instrument(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_session_level_upsert(postgres_url))


def test_candles_require_timezone_aware_utc_timestamps(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_timestamp_boundary(postgres_url))


def test_candle_coverage_and_latest_contiguous_window(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_candle_coverage_and_window(postgres_url))


async def _assert_candle_upsert(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    try:
        async with transaction(engine) as connection:
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=ts,
                o=Decimal("1.1000"),
                h=Decimal("1.1050"),
                low=Decimal("1.0990"),
                c=Decimal("1.1040"),
                volume=100,
                complete=True,
            )
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=ts,
                o=Decimal("1.1000"),
                h=Decimal("1.1060"),
                low=Decimal("1.0990"),
                c=Decimal("1.1055"),
                volume=125,
                complete=True,
            )

        async with engine.connect() as connection:
            rows = await list_candles(connection, instrument="EUR_USD")

        assert len(rows) == 1
        assert rows[0]["instrument"] == "EUR_USD"
        assert rows[0]["ts"] == ts
        assert rows[0]["h"] == Decimal("1.10600000")
        assert rows[0]["c"] == Decimal("1.10550000")
        assert rows[0]["volume"] == 125
        assert rows[0]["complete"] is True
    finally:
        await engine.dispose()


async def _assert_session_level_upsert(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    trading_date = date(2026, 1, 15)
    try:
        async with transaction(engine) as connection:
            await upsert_session_levels(
                connection,
                date=trading_date,
                instrument="EUR_USD",
                asia_high=Decimal("1.1100"),
                asia_low=Decimal("1.1000"),
                london_high=Decimal("1.1150"),
                london_low=Decimal("1.1050"),
            )
            await upsert_session_levels(
                connection,
                date=trading_date,
                instrument="EUR_USD",
                asia_high=Decimal("1.1110"),
                asia_low=Decimal("1.1010"),
                london_high=Decimal("1.1160"),
                london_low=Decimal("1.1060"),
            )

        async with engine.connect() as connection:
            levels = await get_session_levels(
                connection,
                date=trading_date,
                instrument="EUR_USD",
            )

        assert levels == {
            "date": trading_date,
            "instrument": "EUR_USD",
            "asia_high": Decimal("1.11100000"),
            "asia_low": Decimal("1.10100000"),
            "london_high": Decimal("1.11600000"),
            "london_low": Decimal("1.10600000"),
        }
    finally:
        await engine.dispose()


async def _assert_timestamp_boundary(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        async with transaction(engine) as connection:
            with pytest.raises(ValueError, match="timezone-aware UTC"):
                await upsert_candle(
                    connection,
                    instrument="EUR_USD",
                    ts=datetime(2026, 1, 15, 14, 30),
                    o=Decimal("1.1000"),
                    h=Decimal("1.1050"),
                    low=Decimal("1.0990"),
                    c=Decimal("1.1040"),
                    volume=100,
                    complete=True,
                )
            with pytest.raises(ValueError, match="timezone-aware UTC"):
                await upsert_candle(
                    connection,
                    instrument="EUR_USD",
                    ts=datetime(2026, 1, 15, 9, 30, tzinfo=timezone(timedelta(hours=-5))),
                    o=Decimal("1.1000"),
                    h=Decimal("1.1050"),
                    low=Decimal("1.0990"),
                    c=Decimal("1.1040"),
                    volume=100,
                    complete=True,
                )
    finally:
        await engine.dispose()


async def _assert_candle_coverage_and_window(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    try:
        async with transaction(engine) as connection:
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
                o=Decimal("1.1000"),
                h=Decimal("1.1050"),
                low=Decimal("1.0990"),
                c=Decimal("1.1040"),
                volume=100,
                complete=True,
            )
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=datetime(2026, 1, 16, 14, 30, tzinfo=UTC),
                o=Decimal("1.1000"),
                h=Decimal("1.1050"),
                low=Decimal("1.0990"),
                c=Decimal("1.1040"),
                volume=100,
                complete=True,
            )
            await upsert_candle(
                connection,
                instrument="EUR_USD",
                ts=datetime(2026, 1, 18, 14, 30, tzinfo=UTC),
                o=Decimal("1.1000"),
                h=Decimal("1.1050"),
                low=Decimal("1.0990"),
                c=Decimal("1.1040"),
                volume=100,
                complete=True,
            )

        async with engine.connect() as connection:
            coverage = await get_candle_coverage(connection, instrument="EUR_USD")
            latest_two_days = await latest_complete_candle_window(
                connection,
                instrument="EUR_USD",
                required_days=2,
            )
            latest_three_days = await latest_complete_candle_window(
                connection,
                instrument="EUR_USD",
                required_days=3,
            )

        assert coverage["candle_count"] == 3
        assert coverage["from"] == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
        assert coverage["to"] == datetime(2026, 1, 18, 14, 30, tzinfo=UTC)
        assert latest_two_days is not None
        assert latest_two_days["from"] == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        assert latest_two_days["to"] == datetime(2026, 1, 18, 23, 59, 59, 999999, tzinfo=UTC)
        assert latest_three_days is not None
        assert latest_three_days["from"] == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        assert latest_three_days["to"] == datetime(2026, 1, 18, 23, 59, 59, 999999, tzinfo=UTC)
    finally:
        await engine.dispose()


def test_daily_candle_aggregates_group_by_ny_trading_day(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_daily_candle_aggregates(postgres_url))


async def _assert_daily_candle_aggregates(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    # 2026-01-04 is a Sunday: the 22:15 UTC reopen candle (17:15 ET) must fold
    # into Monday's trading day, contribute the first_open, and not create a
    # standalone Sunday row.
    sunday_reopen = datetime(2026, 1, 4, 22, 15, tzinfo=UTC)
    monday_midday = datetime(2026, 1, 5, 15, 0, tzinfo=UTC)
    monday_late = datetime(2026, 1, 5, 21, 0, tzinfo=UTC)
    try:
        async with transaction(engine) as connection:
            for ts, o, h, low, c in (
                (sunday_reopen, "1.2000", "1.2010", "1.1990", "1.2005"),
                (monday_midday, "1.2005", "1.2100", "1.2000", "1.2050"),
                (monday_late, "1.2050", "1.2060", "1.1950", "1.2040"),
            ):
                await upsert_candle(
                    connection,
                    instrument="EUR_USD",
                    ts=ts,
                    o=Decimal(o),
                    h=Decimal(h),
                    low=Decimal(low),
                    c=Decimal(c),
                    volume=100,
                    complete=True,
                )

        async with engine.connect() as connection:
            rows = await list_daily_candle_aggregates(
                connection,
                instrument="EUR_USD",
                start=datetime(2026, 1, 1, tzinfo=UTC),
                end=datetime(2026, 1, 10, tzinfo=UTC),
            )

        assert len(rows) == 1
        row = rows[0]
        assert row["day"] == date(2026, 1, 5)
        assert row["day"].weekday() == 0
        assert row["first_open"] == Decimal("1.2000")
        assert row["close"] == Decimal("1.2040")
        assert row["high"] == Decimal("1.2100")
        assert row["low"] == Decimal("1.1950")
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
