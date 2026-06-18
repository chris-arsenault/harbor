from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.persistence.schema import equity_snapshots, fvgs, signals, sweeps, trades


async def append_sweep(
    connection: AsyncConnection,
    *,
    ts: datetime,
    instrument: str,
    level_name: str,
    level_price: Decimal,
    direction: str,
    sweep_extreme: Decimal,
) -> int:
    result = await connection.execute(
        sweeps.insert()
        .values(
            ts=ts,
            instrument=instrument,
            level_name=level_name,
            level_price=level_price,
            direction=direction,
            sweep_extreme=sweep_extreme,
        )
        .returning(sweeps.c.id)
    )
    return result.scalar_one()


async def append_fvg(
    connection: AsyncConnection,
    *,
    ts: datetime,
    instrument: str,
    fvg_type: str,
    top: Decimal,
    bottom: Decimal,
    midpoint: Decimal,
    sweep_id: int,
) -> int:
    result = await connection.execute(
        fvgs.insert()
        .values(
            ts=ts,
            instrument=instrument,
            type=fvg_type,
            top=top,
            bottom=bottom,
            midpoint=midpoint,
            sweep_id=sweep_id,
        )
        .returning(fvgs.c.id)
    )
    return result.scalar_one()


async def append_signal(
    connection: AsyncConnection,
    *,
    ts: datetime,
    instrument: str,
    direction: str,
    entry: Decimal,
    stop: Decimal,
    target: Decimal,
    risk: Decimal,
    rr: Decimal,
    status: str,
) -> int:
    result = await connection.execute(
        signals.insert()
        .values(
            signal_key=None,
            ts=ts,
            instrument=instrument,
            direction=direction,
            entry=entry,
            stop=stop,
            target=target,
            risk=risk,
            rr=rr,
            status=status,
        )
        .returning(signals.c.id)
    )
    return result.scalar_one()


async def append_trade(
    connection: AsyncConnection,
    *,
    signal_id: int,
    broker_trade_id: str | None,
    side: str,
    units: Decimal,
    entry_price: Decimal,
    entry_ts: datetime,
    exit_price: Decimal | None = None,
    exit_ts: datetime | None = None,
    pnl: Decimal | None = None,
    r_multiple: Decimal | None = None,
    exit_reason: str | None = None,
) -> int:
    result = await connection.execute(
        trades.insert()
        .values(
            signal_id=signal_id,
            broker_order_id=None,
            client_order_id=None,
            broker_trade_id=broker_trade_id,
            open_transaction_id=None,
            close_transaction_id=None,
            side=side,
            units=units,
            entry_price=entry_price,
            entry_ts=entry_ts,
            exit_price=exit_price,
            exit_ts=exit_ts,
            pnl=pnl,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
        )
        .returning(trades.c.id)
    )
    return result.scalar_one()


async def append_equity_snapshot(
    connection: AsyncConnection,
    *,
    ts: datetime,
    nav: Decimal,
    balance: Decimal,
    unrealized_pnl: Decimal,
    open_positions: int,
) -> int:
    result = await connection.execute(
        equity_snapshots.insert()
        .values(
            ts=ts,
            nav=nav,
            balance=balance,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
        )
        .returning(equity_snapshots.c.id)
    )
    return result.scalar_one()


async def list_sweeps(connection: AsyncConnection, *, instrument: str) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(sweeps).where(sweeps.c.instrument == instrument).order_by(sweeps.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_fvgs(connection: AsyncConnection, *, instrument: str) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(fvgs).where(fvgs.c.instrument == instrument).order_by(fvgs.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_signals(connection: AsyncConnection, *, instrument: str) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            signals.c.id,
            signals.c.ts,
            signals.c.instrument,
            signals.c.direction,
            signals.c.entry,
            signals.c.stop,
            signals.c.target,
            signals.c.risk,
            signals.c.rr,
            signals.c.status,
        )
        .where(signals.c.instrument == instrument)
        .order_by(signals.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_trades(connection: AsyncConnection, *, signal_id: int) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            trades.c.id,
            trades.c.signal_id,
            trades.c.broker_trade_id,
            trades.c.side,
            trades.c.units,
            trades.c.entry_price,
            trades.c.entry_ts,
            trades.c.exit_price,
            trades.c.exit_ts,
            trades.c.pnl,
            trades.c.r_multiple,
            trades.c.exit_reason,
        )
        .where(trades.c.signal_id == signal_id)
        .order_by(trades.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_equity_snapshots(connection: AsyncConnection) -> list[dict[str, Any]]:
    result = await connection.execute(select(equity_snapshots).order_by(equity_snapshots.c.id))
    return [dict(row) for row in result.mappings()]
