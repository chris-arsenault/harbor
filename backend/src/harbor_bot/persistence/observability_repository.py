from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.persistence.schema import (
    candles,
    equity_snapshots,
    events,
    fvgs,
    sessions,
    signals,
    sweeps,
    trades,
)


async def list_candles_for_range(
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
            candles.c.ts >= start,
            candles.c.ts < end,
        )
        .order_by(candles.c.ts)
    )
    return [dict(row) for row in result.mappings()]


async def get_session_levels_for_date(
    connection: AsyncConnection,
    *,
    date: date,
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


async def list_sweeps_for_date(
    connection: AsyncConnection,
    *,
    date: date,
    instrument: str,
) -> list[dict[str, Any]]:
    start, end = _utc_day_bounds(date)
    result = await connection.execute(
        select(sweeps)
        .where(
            sweeps.c.instrument == instrument,
            sweeps.c.ts >= start,
            sweeps.c.ts < end,
        )
        .order_by(sweeps.c.ts, sweeps.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_fvgs_for_date(
    connection: AsyncConnection,
    *,
    date: date,
    instrument: str,
) -> list[dict[str, Any]]:
    start, end = _utc_day_bounds(date)
    result = await connection.execute(
        select(fvgs)
        .where(
            fvgs.c.instrument == instrument,
            fvgs.c.ts >= start,
            fvgs.c.ts < end,
        )
        .order_by(fvgs.c.ts, fvgs.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_signals_for_date(
    connection: AsyncConnection,
    *,
    date: date,
    instrument: str,
) -> list[dict[str, Any]]:
    start, end = _utc_day_bounds(date)
    result = await connection.execute(
        select(signals)
        .where(
            signals.c.instrument == instrument,
            signals.c.ts >= start,
            signals.c.ts < end,
        )
        .order_by(signals.c.ts, signals.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_trades_for_date(
    connection: AsyncConnection,
    *,
    date: date,
    instrument: str,
) -> list[dict[str, Any]]:
    start, end = _utc_day_bounds(date)
    result = await connection.execute(
        select(trades)
        .join(signals, trades.c.signal_id == signals.c.id)
        .where(
            signals.c.instrument == instrument,
            trades.c.entry_ts >= start,
            trades.c.entry_ts < end,
        )
        .order_by(trades.c.entry_ts, trades.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_events_for_dashboard(
    connection: AsyncConnection,
    *,
    level: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(events).order_by(desc(events.c.ts), desc(events.c.id))
    if level is not None:
        statement = statement.where(events.c.level == level)
    if limit is not None:
        statement = statement.limit(limit)

    result = await connection.execute(statement)
    return [dict(row) for row in result.mappings()]


async def get_latest_equity_snapshot(connection: AsyncConnection) -> dict[str, Any] | None:
    result = await connection.execute(
        select(equity_snapshots)
        .order_by(desc(equity_snapshots.c.ts), desc(equity_snapshots.c.id))
        .limit(1)
    )
    row = result.mappings().first()
    if row is None:
        return None
    return dict(row)


async def get_day_trade_summary(
    connection: AsyncConnection,
    *,
    date: date,
    instrument: str,
) -> dict[str, Any]:
    start, end = _utc_day_bounds(date)
    result = await connection.execute(
        select(
            func.coalesce(func.sum(trades.c.pnl), Decimal("0")).label("realized_pnl"),
            func.count(trades.c.id).label("trade_count"),
        )
        .select_from(trades.join(signals, trades.c.signal_id == signals.c.id))
        .where(
            signals.c.instrument == instrument,
            trades.c.exit_ts >= start,
            trades.c.exit_ts < end,
        )
    )
    row = result.mappings().one()
    return {
        "realized_pnl": row["realized_pnl"],
        "trade_count": row["trade_count"],
    }


def _utc_day_bounds(value: date) -> tuple[datetime, datetime]:
    start = datetime.combine(value, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)
