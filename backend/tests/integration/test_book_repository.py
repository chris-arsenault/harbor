import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.oanda.types import BookBucket, BookSnapshot
from harbor_bot.persistence.book_repository import (
    get_book_coverage,
    get_latest_book_snapshot,
    upsert_book_snapshot,
)
from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.settings import Settings


def test_book_snapshots_are_idempotent_and_queryable(postgres_url: str) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_book_snapshot_repository(postgres_url))


async def _assert_book_snapshot_repository(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    snapshot = _snapshot("order", datetime(2026, 1, 15, 14, 20, tzinfo=UTC))
    newer = _snapshot("order", datetime(2026, 1, 15, 14, 40, tzinfo=UTC))
    position = _snapshot("position", datetime(2026, 1, 15, 14, 20, tzinfo=UTC))
    try:
        async with transaction(engine) as connection:
            first = await upsert_book_snapshot(
                connection,
                snapshot=snapshot,
                recorded_ts=datetime(2026, 1, 15, 14, 21, tzinfo=UTC),
            )
            second = await upsert_book_snapshot(
                connection,
                snapshot=snapshot,
                recorded_ts=datetime(2026, 1, 15, 14, 22, tzinfo=UTC),
            )
            await upsert_book_snapshot(
                connection,
                snapshot=newer,
                recorded_ts=datetime(2026, 1, 15, 14, 41, tzinfo=UTC),
            )
            await upsert_book_snapshot(
                connection,
                snapshot=position,
                recorded_ts=datetime(2026, 1, 15, 14, 21, tzinfo=UTC),
            )

        async with engine.connect() as connection:
            coverage = await get_book_coverage(connection, instruments=("EUR_USD", "GBP_USD"))
            latest = await get_latest_book_snapshot(
                connection,
                book_type="order",
                instrument="EUR_USD",
            )

        order_coverage = _find_coverage(coverage, book_type="order", instrument="EUR_USD")
        empty_coverage = _find_coverage(coverage, book_type="position", instrument="GBP_USD")
        assert first is True
        assert second is False
        assert order_coverage["snapshot_count"] == 2
        assert order_coverage["from"] == datetime(2026, 1, 15, 14, 20, tzinfo=UTC)
        assert order_coverage["to"] == datetime(2026, 1, 15, 14, 40, tzinfo=UTC)
        assert order_coverage["latest_mid_price"] == Decimal("1.09000000")
        assert empty_coverage["snapshot_count"] == 0
        assert latest is not None
        assert latest["snapshot_time"] == datetime(2026, 1, 15, 14, 40, tzinfo=UTC)
        assert latest["bucket_count"] == 2
        assert latest["buckets_json"][0]["long_pct"] == "0.20"
    finally:
        await engine.dispose()


def _snapshot(book_type: str, time: datetime) -> BookSnapshot:
    return BookSnapshot(
        book_type=book_type,
        instrument="EUR_USD",
        time=time,
        price=Decimal("1.09000"),
        bucket_width=Decimal("0.00050"),
        buckets=(
            BookBucket(
                price=Decimal("1.08500"),
                long_percent=Decimal("0.20"),
                short_percent=Decimal("0.15"),
            ),
            BookBucket(
                price=Decimal("1.09000"),
                long_percent=Decimal("0.35"),
                short_percent=Decimal("0.40"),
            ),
        ),
    )


def _find_coverage(rows: list[dict], *, book_type: str, instrument: str) -> dict:
    return next(
        row for row in rows if row["book_type"] == book_type and row["instrument"] == instrument
    )


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
