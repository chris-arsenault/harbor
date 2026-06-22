from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
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
    bid_h: Decimal | None = None,
    bid_l: Decimal | None = None,
    ask_h: Decimal | None = None,
    ask_l: Decimal | None = None,
) -> None:
    ts = _require_aware_utc(ts)
    values = {
        "instrument": instrument,
        "ts": ts,
        "o": o,
        "h": h,
        "l": low,
        "c": c,
        "volume": volume,
        "complete": complete,
        "bid_h": bid_h,
        "bid_l": bid_l,
        "ask_h": ask_h,
        "ask_l": ask_l,
    }
    statement = (
        insert(candles)
        .values(**values)
        .on_conflict_do_update(
            index_elements=[candles.c.instrument, candles.c.ts],
            set_={key: value for key, value in values.items() if key not in ("instrument", "ts")},
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
            candles.c.bid_h,
            candles.c.bid_l,
            candles.c.ask_h,
            candles.c.ask_l,
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
            candles.c.bid_h,
            candles.c.bid_l,
            candles.c.ask_h,
            candles.c.ask_l,
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


async def get_candle_coverage(
    connection: AsyncConnection,
    *,
    instrument: str,
) -> dict[str, Any]:
    result = await connection.execute(
        select(
            func.count(candles.c.id).label("candle_count"),
            func.min(candles.c.ts).label("from_ts"),
            func.max(candles.c.ts).label("to_ts"),
        ).where(candles.c.instrument == instrument, candles.c.complete.is_(True))
    )
    row = result.mappings().one()
    return {
        "instrument": instrument,
        "candle_count": int(row["candle_count"]),
        "from": row["from_ts"],
        "to": row["to_ts"],
    }


async def get_prior_day_range(
    connection: AsyncConnection,
    *,
    instrument: str,
    day: date,
) -> dict[str, Decimal] | None:
    """High/low of the prior UTC calendar day's complete candles, for a
    previous-day-high/low reference line on the chart."""
    prior = day - timedelta(days=1)
    result = await connection.execute(
        select(
            func.max(candles.c.h).label("high"),
            func.min(candles.c.l).label("low"),
        ).where(
            candles.c.instrument == instrument,
            func.date(candles.c.ts) == prior,
            candles.c.complete.is_(True),
        )
    )
    row = result.mappings().one()
    if row["high"] is None or row["low"] is None:
        return None
    return {"high": row["high"], "low": row["low"]}


async def get_bid_ask_candle_count(
    connection: AsyncConnection,
    *,
    instrument: str,
) -> int:
    result = await connection.execute(
        select(func.count(candles.c.id)).where(
            candles.c.instrument == instrument,
            candles.c.complete.is_(True),
            candles.c.bid_h.isnot(None),
        )
    )
    return int(result.scalar_one())


async def latest_complete_candle_window(
    connection: AsyncConnection,
    *,
    instrument: str,
    required_days: int,
) -> dict[str, Any] | None:
    if required_days <= 0:
        msg = "required_days must be positive"
        raise ValueError(msg)

    result = await connection.execute(
        select(func.date(candles.c.ts).label("candle_date"))
        .where(candles.c.instrument == instrument, candles.c.complete.is_(True))
        .group_by("candle_date")
        .order_by(desc("candle_date"))
        .limit(required_days * 8)
    )
    dates = [_date_value(row["candle_date"]) for row in result.mappings()]
    if not dates:
        return None

    contiguous = [dates[0]]
    for candle_date in dates[1:]:
        if candle_date == contiguous[-1] - timedelta(days=1):
            contiguous.append(candle_date)
            if len(contiguous) >= required_days:
                break
        elif candle_date < contiguous[-1] - timedelta(days=1):
            contiguous = [candle_date]

    if len(contiguous) < required_days:
        return None

    latest = contiguous[0]
    earliest = contiguous[required_days - 1]
    start = datetime.combine(earliest, time.min, tzinfo=UTC)
    end = datetime.combine(latest + timedelta(days=1), time.min, tzinfo=UTC) - timedelta(
        microseconds=1
    )
    coverage = await get_candle_coverage(connection, instrument=instrument)
    return {
        "instrument": instrument,
        "from": start,
        "to": end,
        "required_days": required_days,
        "coverage": coverage,
    }


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


def candle_record_from_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Shape a persisted candle row into a backtester/optimizer record, carrying
    bid/ask extremes when present so honest fill detection (ADR 0006) applies on
    every consumer, not just the backtest service."""
    record: dict[str, Any] = {
        "instrument": row["instrument"],
        "ts": row["ts"].isoformat(),
        "o": str(row["o"]),
        "h": str(row["h"]),
        "low": str(row["l"]),
        "c": str(row["c"]),
        "volume": row["volume"],
        "complete": row["complete"],
    }
    bid = _ohlc_extremes(row.get("bid_h"), row.get("bid_l"))
    ask = _ohlc_extremes(row.get("ask_h"), row.get("ask_l"))
    if bid is not None:
        record["bid"] = bid
    if ask is not None:
        record["ask"] = ask
    return record


def _ohlc_extremes(high: Any, low: Any) -> dict[str, str] | None:
    if high is None or low is None:
        return None
    return {"h": str(high), "l": str(low)}


def _require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != _UTC_OFFSET:
        msg = "candle timestamps must be timezone-aware UTC datetimes"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
