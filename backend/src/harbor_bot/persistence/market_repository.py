from datetime import UTC, datetime, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.persistence.schema import candles, sessions

_UTC_OFFSET = timedelta(0)


async def upsert_candle(
    connection: AsyncConnection,
    *,
    instrument: str,
    ts: datetime,
    o: Decimal,
    h: Decimal,
    low: Decimal,
    c: Decimal,
    volume: int,
    complete: bool,
) -> None:
    ts = _require_aware_utc(ts)
    statement = (
        insert(candles)
        .values(
            instrument=instrument,
            ts=ts,
            o=o,
            h=h,
            l=low,
            c=c,
            volume=volume,
            complete=complete,
        )
        .on_conflict_do_update(
            index_elements=[candles.c.instrument, candles.c.ts],
            set_={
                "o": o,
                "h": h,
                "l": low,
                "c": c,
                "volume": volume,
                "complete": complete,
            },
        )
    )
    await connection.execute(statement)


async def list_candles(
    connection: AsyncConnection,
    *,
    instrument: str,
) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            candles.c.instrument,
            candles.c.ts,
            candles.c.o,
            candles.c.h,
            candles.c.l,
            candles.c.c,
            candles.c.volume,
            candles.c.complete,
        )
        .where(candles.c.instrument == instrument)
        .order_by(candles.c.ts)
    )
    return [dict(row) for row in result.mappings()]


async def list_candles_range(
    connection: AsyncConnection,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            candles.c.instrument,
            candles.c.ts,
            candles.c.o,
            candles.c.h,
            candles.c.l,
            candles.c.c,
            candles.c.volume,
            candles.c.complete,
        )
        .where(
            candles.c.instrument == instrument,
            candles.c.ts >= _require_aware_utc(start),
            candles.c.ts <= _require_aware_utc(end),
            candles.c.complete.is_(True),
        )
        .order_by(candles.c.ts)
    )
    return [dict(row) for row in result.mappings()]


async def upsert_session_levels(
    connection: AsyncConnection,
    *,
    date: Date,
    instrument: str,
    asia_high: Decimal,
    asia_low: Decimal,
    london_high: Decimal,
    london_low: Decimal,
) -> None:
    statement = (
        insert(sessions)
        .values(
            date=date,
            instrument=instrument,
            asia_high=asia_high,
            asia_low=asia_low,
            london_high=london_high,
            london_low=london_low,
        )
        .on_conflict_do_update(
            index_elements=[sessions.c.date, sessions.c.instrument],
            set_={
                "asia_high": asia_high,
                "asia_low": asia_low,
                "london_high": london_high,
                "london_low": london_low,
            },
        )
    )
    await connection.execute(statement)


async def get_session_levels(
    connection: AsyncConnection,
    *,
    date: Date,
    instrument: str,
) -> dict[str, Any] | None:
    result = await connection.execute(
        select(
            sessions.c.date,
            sessions.c.instrument,
            sessions.c.asia_high,
            sessions.c.asia_low,
            sessions.c.london_high,
            sessions.c.london_low,
        ).where(sessions.c.date == date, sessions.c.instrument == instrument)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return dict(row)


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != _UTC_OFFSET:
        msg = "candle timestamps must be timezone-aware UTC datetimes"
        raise ValueError(msg)
    return value.astimezone(UTC)
