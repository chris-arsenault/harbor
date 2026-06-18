from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from harbor_bot.execution.models import (
    BrokerOrder,
    ExecutionSignal,
    KillSwitchState,
    SignalReservation,
    TradingControls,
)
from harbor_bot.persistence.config_repository import get_config_value, upsert_config_value
from harbor_bot.persistence.event_repository import append_event
from harbor_bot.persistence.schema import broker_transactions, signals, trades

TRADING_CONTROLS_KEY = "execution.trading_controls"
TRANSACTION_CHECKPOINT_KEY = "execution.transaction_checkpoint"


async def get_trading_controls(
    connection: AsyncConnection,
    *,
    confirmation_token: str,
) -> TradingControls:
    stored = await get_config_value(connection, TRADING_CONTROLS_KEY)
    if stored is None:
        return TradingControls(trading_enabled=False, confirmation_token=confirmation_token)

    return TradingControls(
        trading_enabled=bool(stored.get("trading_enabled", False)),
        confirmation_token=str(stored.get("confirmation_token", confirmation_token)),
        kill_switch_state=str(stored.get("kill_switch_state", KillSwitchState.CLEAR.value)),
        kill_switch_reason=stored.get("kill_switch_reason"),
        updated_ts=_parse_optional_datetime(stored.get("updated_ts")),
    )


async def set_trading_controls(
    connection: AsyncConnection,
    controls: TradingControls,
) -> None:
    await upsert_config_value(
        connection,
        key=TRADING_CONTROLS_KEY,
        value=controls.to_jsonable(),
    )


async def reserve_signal(
    connection: AsyncConnection,
    signal: ExecutionSignal,
) -> SignalReservation:
    statement = (
        insert(signals)
        .values(
            signal_key=signal.signal_key,
            ts=signal.ts,
            instrument=signal.instrument,
            direction=signal.direction,
            entry=signal.entry_price,
            stop=signal.stop_loss_price,
            target=signal.take_profit_price,
            risk=abs(signal.entry_price - signal.stop_loss_price),
            rr=_rr(signal),
            status="pending",
        )
        .on_conflict_do_nothing(index_elements=[signals.c.signal_key])
        .returning(signals.c.id)
    )
    result = await connection.execute(statement)
    inserted_id = result.scalar_one_or_none()
    if inserted_id is not None:
        return SignalReservation(signal_key=signal.signal_key, reserved=True)

    existing_trade_result = await connection.execute(
        select(trades.c.id)
        .join(signals, trades.c.signal_id == signals.c.id)
        .where(signals.c.signal_key == signal.signal_key)
        .order_by(trades.c.id)
        .limit(1)
    )
    return SignalReservation(
        signal_key=signal.signal_key,
        reserved=False,
        existing_trade_id=existing_trade_result.scalar_one_or_none(),
    )


async def get_signal_id_by_key(connection: AsyncConnection, signal_key: str) -> int | None:
    result = await connection.execute(
        select(signals.c.id).where(signals.c.signal_key == signal_key)
    )
    value = result.scalar_one_or_none()
    return None if value is None else int(value)


async def create_or_update_trade_from_order(
    connection: AsyncConnection,
    *,
    signal_id: int,
    signal: ExecutionSignal,
    order: BrokerOrder,
) -> int:
    statement = (
        insert(trades)
        .values(
            signal_id=signal_id,
            broker_order_id=order.broker_order_id,
            client_order_id=order.client_order_id,
            broker_trade_id=order.broker_trade_id,
            open_transaction_id=order.fill_transaction_id,
            close_transaction_id=None,
            side=signal.direction,
            units=abs(order.units),
            entry_price=order.price or signal.entry_price,
            entry_ts=order.ts,
            exit_price=None,
            exit_ts=None,
            pnl=None,
            r_multiple=None,
            exit_reason=None,
        )
        .on_conflict_do_update(
            index_elements=[trades.c.client_order_id],
            set_={
                "broker_order_id": order.broker_order_id,
                "broker_trade_id": order.broker_trade_id,
                "open_transaction_id": order.fill_transaction_id,
                "entry_price": order.price or signal.entry_price,
                "entry_ts": order.ts,
            },
        )
        .returning(trades.c.id)
    )
    result = await connection.execute(statement)
    return int(result.scalar_one())


async def close_trade_from_transaction(
    connection: AsyncConnection,
    *,
    broker_trade_id: str,
    close_transaction_id: str,
    exit_price: Decimal,
    exit_ts: datetime,
    pnl: Decimal,
    r_multiple: Decimal,
    exit_reason: str,
) -> bool:
    result = await connection.execute(
        update(trades)
        .where(trades.c.broker_trade_id == broker_trade_id, trades.c.exit_ts.is_(None))
        .values(
            close_transaction_id=close_transaction_id,
            exit_price=exit_price,
            exit_ts=exit_ts,
            pnl=pnl,
            r_multiple=r_multiple,
            exit_reason=exit_reason,
        )
        .returning(trades.c.id)
    )
    return result.scalar_one_or_none() is not None


async def list_open_bot_trades(connection: AsyncConnection) -> list[dict[str, Any]]:
    result = await connection.execute(
        select(
            trades.c.id,
            trades.c.signal_id,
            trades.c.broker_order_id,
            trades.c.client_order_id,
            trades.c.broker_trade_id,
            trades.c.open_transaction_id,
            trades.c.close_transaction_id,
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
        .where(trades.c.broker_trade_id.is_not(None), trades.c.exit_ts.is_(None))
        .order_by(trades.c.id)
    )
    return [dict(row) for row in result.mappings()]


async def list_trade_journal(
    connection: AsyncConnection,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    conditions = []
    if start is not None:
        conditions.append(trades.c.entry_ts >= start)
    if end is not None:
        conditions.append(trades.c.entry_ts <= end)

    statement = (
        select(
            trades.c.id,
            trades.c.signal_id,
            signals.c.signal_key,
            signals.c.instrument,
            signals.c.status.label("signal_status"),
            trades.c.broker_order_id,
            trades.c.client_order_id,
            trades.c.broker_trade_id,
            trades.c.open_transaction_id,
            trades.c.close_transaction_id,
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
        .join(signals, trades.c.signal_id == signals.c.id)
        .order_by(trades.c.entry_ts.desc(), trades.c.id.desc())
        .limit(limit)
    )
    if conditions:
        statement = statement.where(*conditions)

    result = await connection.execute(statement)
    return [dict(row) for row in result.mappings()]


async def persist_broker_transaction(
    connection: AsyncConnection,
    *,
    transaction_id: str,
    transaction_type: str,
    ts: datetime,
    raw: dict[str, Any],
) -> bool:
    statement = (
        insert(broker_transactions)
        .values(
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            ts=ts,
            raw_json=raw,
        )
        .on_conflict_do_nothing(index_elements=[broker_transactions.c.transaction_id])
        .returning(broker_transactions.c.id)
    )
    result = await connection.execute(statement)
    return result.scalar_one_or_none() is not None


async def store_transaction_checkpoint(
    connection: AsyncConnection,
    *,
    transaction_id: str,
) -> None:
    await upsert_config_value(
        connection,
        key=TRANSACTION_CHECKPOINT_KEY,
        value={"transaction_id": transaction_id},
    )


async def read_transaction_checkpoint(connection: AsyncConnection) -> str | None:
    stored = await get_config_value(connection, TRANSACTION_CHECKPOINT_KEY)
    if stored is None:
        return None
    value = stored.get("transaction_id")
    return None if value is None else str(value)


async def append_execution_event(
    connection: AsyncConnection,
    *,
    ts: datetime,
    level: str,
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> int:
    return await append_event(
        connection,
        ts=ts,
        level=level,
        module="execution",
        event_type=event_type,
        message=message,
        data=data,
    )


def _rr(signal: ExecutionSignal) -> Decimal:
    risk = abs(signal.entry_price - signal.stop_loss_price)
    if risk == 0:
        return Decimal("0")
    return abs(signal.take_profit_price - signal.entry_price) / risk


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
