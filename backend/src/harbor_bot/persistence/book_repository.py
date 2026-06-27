from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.oanda.types import BookSnapshot
from harbor_bot.persistence.schema import book_snapshots

_UTC_OFFSET = timedelta(0)
BOOK_TYPES = ("order", "position")


async def upsert_book_snapshot(
    connection: AsyncConnection,
    *,
    snapshot: BookSnapshot,
    recorded_ts: datetime,
) -> bool:
    """Insert a book snapshot once. Existing snapshot keys are left untouched."""
    snapshot_time = _require_aware_utc(snapshot.time)
    recorded_at = _require_aware_utc(recorded_ts)
    statement = (
        insert(book_snapshots)
        .values(
            book_type=snapshot.book_type,
            instrument=snapshot.instrument,
            snapshot_time=snapshot_time,
            mid_price=snapshot.price,
            bucket_width=snapshot.bucket_width,
            bucket_count=len(snapshot.buckets),
            buckets_json=[
                {
                    "price": format(bucket.price, "f"),
                    "long_pct": format(bucket.long_percent, "f"),
                    "short_pct": format(bucket.short_percent, "f"),
                }
                for bucket in snapshot.buckets
            ],
            recorded_ts=recorded_at,
        )
        .on_conflict_do_nothing(
            index_elements=[
                book_snapshots.c.book_type,
                book_snapshots.c.instrument,
                book_snapshots.c.snapshot_time,
            ]
        )
        .returning(book_snapshots.c.id)
    )
    result = await connection.execute(statement)
    return result.scalar_one_or_none() is not None


async def get_book_coverage(
    connection: AsyncConnection,
    *,
    instruments: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not instruments:
        return []

    coverage_result = await connection.execute(
        select(
            book_snapshots.c.book_type,
            book_snapshots.c.instrument,
            func.count(book_snapshots.c.id).label("snapshot_count"),
            func.min(book_snapshots.c.snapshot_time).label("from_ts"),
            func.max(book_snapshots.c.snapshot_time).label("to_ts"),
        )
        .where(book_snapshots.c.instrument.in_(instruments))
        .group_by(book_snapshots.c.book_type, book_snapshots.c.instrument)
    )
    coverage_by_key = {
        (row["book_type"], row["instrument"]): {
            "book_type": row["book_type"],
            "instrument": row["instrument"],
            "snapshot_count": int(row["snapshot_count"]),
            "from": row["from_ts"],
            "to": row["to_ts"],
            "latest_mid_price": None,
        }
        for row in coverage_result.mappings()
    }

    latest_result = await connection.execute(
        select(
            book_snapshots.c.book_type,
            book_snapshots.c.instrument,
            book_snapshots.c.mid_price,
            func.row_number()
            .over(
                partition_by=(book_snapshots.c.book_type, book_snapshots.c.instrument),
                order_by=book_snapshots.c.snapshot_time.desc(),
            )
            .label("rank"),
        )
        .where(book_snapshots.c.instrument.in_(instruments))
        .subquery()
        .select()
    )
    for row in latest_result.mappings():
        if row["rank"] != 1:
            continue
        key = (row["book_type"], row["instrument"])
        if key in coverage_by_key:
            coverage_by_key[key]["latest_mid_price"] = row["mid_price"]

    rows: list[dict[str, Any]] = []
    for instrument in instruments:
        for book_type in BOOK_TYPES:
            rows.append(
                coverage_by_key.get(
                    (book_type, instrument),
                    {
                        "book_type": book_type,
                        "instrument": instrument,
                        "snapshot_count": 0,
                        "from": None,
                        "to": None,
                        "latest_mid_price": None,
                    },
                )
            )
    return rows


async def get_latest_book_snapshot(
    connection: AsyncConnection,
    *,
    book_type: str,
    instrument: str,
) -> dict[str, Any] | None:
    result = await connection.execute(
        select(
            book_snapshots.c.book_type,
            book_snapshots.c.instrument,
            book_snapshots.c.snapshot_time,
            book_snapshots.c.mid_price,
            book_snapshots.c.bucket_width,
            book_snapshots.c.bucket_count,
            book_snapshots.c.buckets_json,
            book_snapshots.c.recorded_ts,
        )
        .where(
            book_snapshots.c.book_type == book_type,
            book_snapshots.c.instrument == instrument,
        )
        .order_by(book_snapshots.c.snapshot_time.desc())
        .limit(1)
    )
    row = result.mappings().first()
    return None if row is None else dict(row)


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != _UTC_OFFSET:
        msg = "book snapshots require timezone-aware UTC timestamps"
        raise ValueError(msg)
    return value.astimezone(UTC)
