from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
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


async def get_candle_coverage_with_quality(
    connection: AsyncConnection,
    *,
    instrument: str,
) -> dict[str, Any]:
    result = await connection.execute(
        select(
            func.count(candles.c.id).label("candle_count"),
            func.min(candles.c.ts).label("from_ts"),
            func.max(candles.c.ts).label("to_ts"),
            func.count(candles.c.bid_h).label("bid_ask_count"),
        ).where(candles.c.instrument == instrument, candles.c.complete.is_(True))
    )
    row = result.mappings().one()
    return {
        "instrument": instrument,
        "candle_count": int(row["candle_count"]),
        "from": row["from_ts"],
        "to": row["to_ts"],
        "bid_ask_count": int(row["bid_ask_count"]),
    }


async def get_bulk_candle_coverage(
    connection: AsyncConnection,
    *,
    instruments: tuple[str, ...],
) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            candles.c.instrument,
            func.count(candles.c.id).label("candle_count"),
            func.min(candles.c.ts).label("from_ts"),
            func.max(candles.c.ts).label("to_ts"),
            func.count(candles.c.bid_h).label("bid_ask_count"),
        )
        .where(candles.c.instrument.in_(instruments), candles.c.complete.is_(True))
        .group_by(candles.c.instrument)
    )
    by_instrument = {
        row["instrument"]: {
            "instrument": row["instrument"],
            "candle_count": int(row["candle_count"]),
            "from": row["from_ts"],
            "to": row["to_ts"],
            "bid_ask_count": int(row["bid_ask_count"]),
        }
        for row in result.mappings()
    }
    empty = {"candle_count": 0, "from": None, "to": None, "bid_ask_count": 0}
    return [by_instrument.get(inst, {"instrument": inst, **empty}) for inst in instruments]


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
    """Return the full persisted date range when at least *required_days* trading
    days exist.  Forex markets close on weekends, so only distinct dates with
    complete candles are counted — calendar-day contiguity is not required.

    The full range (not just the most recent N days) is returned so the
    walk-forward builder receives all available data and can maximise the
    number of evaluable session days.
    """
    if required_days <= 0:
        msg = "required_days must be positive"
        raise ValueError(msg)

    coverage = await get_candle_coverage(connection, instrument=instrument)
    if coverage["candle_count"] <= 0 or coverage["from"] is None:
        return None

    result = await connection.execute(
        select(func.count(func.distinct(func.date(candles.c.ts)))).where(
            candles.c.instrument == instrument, candles.c.complete.is_(True)
        )
    )
    trading_days = result.scalar_one()
    if trading_days < required_days:
        return None

    return {
        "instrument": instrument,
        "from": coverage["from"],
        "to": coverage["to"],
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
