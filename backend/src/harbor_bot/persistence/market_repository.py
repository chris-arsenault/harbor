from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
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
    replace_existing: bool = True,
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
    insert_statement = insert(candles).values(**values)
    if replace_existing:
        statement = insert_statement.on_conflict_do_update(
            index_elements=[candles.c.instrument, candles.c.ts],
            set_={key: value for key, value in values.items() if key not in ("instrument", "ts")},
        )
    else:
        statement = insert_statement.on_conflict_do_nothing(
            index_elements=[candles.c.instrument, candles.c.ts]
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


_DAILY_AGGREGATE_SQL = text(
    """
    WITH local_candles AS (
        SELECT
            CASE
                WHEN (timezone('America/New_York', ts))::time >= CAST(:rollover AS time)
                THEN ((timezone('America/New_York', ts))::date + 1)
                ELSE (timezone('America/New_York', ts))::date
            END AS trading_day,
            ts, o, h, l, c
        FROM candles
        WHERE instrument = :instrument
          AND ts >= :start
          AND ts <= :end
          AND complete IS TRUE
    )
    SELECT
        trading_day AS day,
        max(h) AS high,
        min(l) AS low,
        (array_agg(o ORDER BY ts ASC))[1] AS first_open,
        (array_agg(c ORDER BY ts DESC))[1] AS close
    FROM local_candles
    GROUP BY trading_day
    ORDER BY trading_day
    """
)


async def list_daily_candle_aggregates(
    connection: AsyncConnection,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Daily bars aggregated in SQL under the New York 17:00 trading-day
    convention (``timezone('America/New_York', ts)`` is DST-correct, not a
    hardcoded offset).

    Research probes that only need daily resolution read ~100-700 rows per
    instrument this way instead of materializing 100k+ M1 candles in Python.
    """
    result = await connection.execute(
        _DAILY_AGGREGATE_SQL,
        {
            "instrument": instrument,
            "start": _require_aware_utc(start),
            "end": _require_aware_utc(end),
            "rollover": time(17, 0),
        },
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


async def get_daily_candle_coverage(
    connection: AsyncConnection,
    *,
    instruments: tuple[str, ...],
    start: Date,
    end: Date,
) -> list[dict[str, Any]]:
    start_ts = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_ts = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    result = await connection.execute(
        select(
            candles.c.instrument,
            func.date(candles.c.ts).label("day"),
            func.count(candles.c.id).label("candle_count"),
            func.count(candles.c.bid_h).label("bid_ask_count"),
        )
        .where(
            candles.c.instrument.in_(instruments),
            candles.c.ts >= start_ts,
            candles.c.ts < end_ts,
            candles.c.complete.is_(True),
        )
        .group_by(candles.c.instrument, func.date(candles.c.ts))
        .order_by(candles.c.instrument, func.date(candles.c.ts))
    )
    return [
        {
            "instrument": row["instrument"],
            "day": _to_date(row["day"]),
            "candle_count": int(row["candle_count"]),
            "bid_ask_count": int(row["bid_ask_count"]),
        }
        for row in result.mappings()
    ]


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
    """Select the most recent trading dates that cover *required_days* with a
    surplus for non-evaluable days.

    Forex markets close on weekends, so calendar-day contiguity is not
    required — only distinct dates with complete candles are counted.  A 50%
    surplus is fetched so the walk-forward builder has room for days that fail
    strict evaluability, without loading the entire history.
    """
    if required_days <= 0:
        msg = "required_days must be positive"
        raise ValueError(msg)

    fetch_limit = int(required_days * 1.5)
    result = await connection.execute(
        select(func.date(candles.c.ts).label("candle_date"))
        .where(candles.c.instrument == instrument, candles.c.complete.is_(True))
        .group_by(func.date(candles.c.ts))
        .order_by(func.date(candles.c.ts).desc())
        .limit(fetch_limit)
    )
    dates = [row["candle_date"] for row in result.mappings()]
    if len(dates) < required_days:
        return None

    midnight = datetime.min.time()
    day_after_latest = _to_date(dates[0]) + timedelta(days=1)
    latest_ts = datetime.combine(day_after_latest, midnight, tzinfo=UTC) - timedelta(microseconds=1)
    earliest_ts = datetime.combine(_to_date(dates[-1]), midnight, tzinfo=UTC)
    coverage = await get_candle_coverage(connection, instrument=instrument)
    return {
        "instrument": instrument,
        "from": earliest_ts,
        "to": latest_ts,
        "required_days": required_days,
        "coverage": coverage,
    }


def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


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
