import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config

from harbor_bot.execution.models import (
    BrokerOrder,
    ExecutionSignal,
    KillSwitchState,
    TradingControls,
)
from harbor_bot.persistence.database import create_engine, transaction
from harbor_bot.persistence.event_repository import list_events
from harbor_bot.persistence.execution_repository import (
    append_execution_event,
    close_trade_from_transaction,
    create_or_update_trade_from_order,
    get_signal_id_by_key,
    get_trading_controls,
    list_open_bot_trades,
    persist_broker_transaction,
    read_transaction_checkpoint,
    reserve_signal,
    set_trading_controls,
    store_transaction_checkpoint,
)
from harbor_bot.settings import Settings


def test_execution_repository_persists_controls_dedupe_and_reconciliation_state(
    postgres_url: str,
) -> None:
    command.upgrade(_alembic_config(postgres_url), "head")

    asyncio.run(_assert_execution_repository(postgres_url))


async def _assert_execution_repository(postgres_url: str) -> None:
    engine = create_engine(Settings(DATABASE_URL=postgres_url))
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    signal = ExecutionSignal(
        signal_key="harbor-practice:variant-1:2026-01-15T14:30:00Z",
        variant_id=1,
        instrument="EUR_USD",
        direction="long",
        entry_price=Decimal("1.09020"),
        stop_loss_price=Decimal("1.08000"),
        take_profit_price=Decimal("1.11000"),
        units=Decimal("1000"),
        ts=ts,
    )
    order = BrokerOrder(
        client_order_id=signal.signal_key,
        broker_order_id="9100",
        broker_trade_id="7001",
        fill_transaction_id="9101",
        instrument="EUR_USD",
        units=Decimal("1000"),
        price=Decimal("1.09020"),
        stop_loss_price=Decimal("1.08000"),
        take_profit_price=Decimal("1.11000"),
        ts=ts,
    )

    try:
        async with transaction(engine) as connection:
            default_controls = await get_trading_controls(
                connection,
                confirmation_token="OANDA_PRACTICE",
            )
            assert default_controls.trading_enabled is False

            controls = TradingControls(
                trading_enabled=True,
                confirmation_token="OANDA_PRACTICE",
                kill_switch_state=KillSwitchState.CLEAR,
                updated_ts=ts,
            )
            await set_trading_controls(connection, controls)
            assert (
                await get_trading_controls(
                    connection,
                    confirmation_token="OANDA_PRACTICE",
                )
                == controls
            )

            reservation = await reserve_signal(connection, signal)
            assert reservation.reserved is True
            duplicate = await reserve_signal(connection, signal)
            assert duplicate.reserved is False
            assert duplicate.existing_trade_id is None

            signal_id = await get_signal_id_by_key(connection, signal.signal_key)
            assert signal_id is not None
            trade_id = await create_or_update_trade_from_order(
                connection,
                signal_id=signal_id,
                signal=signal,
                order=order,
            )
            duplicate_after_trade = await reserve_signal(connection, signal)
            assert duplicate_after_trade.existing_trade_id == trade_id

            open_trades = await list_open_bot_trades(connection)
            assert open_trades[0]["client_order_id"] == signal.signal_key
            assert open_trades[0]["broker_order_id"] == "9100"
            assert open_trades[0]["open_transaction_id"] == "9101"

            inserted_transaction = await persist_broker_transaction(
                connection,
                transaction_id="9101",
                transaction_type="ORDER_FILL",
                ts=ts,
                raw={"id": "9101", "type": "ORDER_FILL"},
            )
            duplicate_transaction = await persist_broker_transaction(
                connection,
                transaction_id="9101",
                transaction_type="ORDER_FILL",
                ts=ts,
                raw={"id": "9101", "type": "ORDER_FILL"},
            )
            assert inserted_transaction is True
            assert duplicate_transaction is False

            await store_transaction_checkpoint(connection, transaction_id="9101")
            assert await read_transaction_checkpoint(connection) == "9101"

            closed = await close_trade_from_transaction(
                connection,
                broker_trade_id="7001",
                close_transaction_id="9201",
                exit_price=Decimal("1.09200"),
                exit_ts=datetime(2026, 1, 15, 16, 59, tzinfo=UTC),
                pnl=Decimal("18.0"),
                r_multiple=Decimal("2.0"),
                exit_reason="broker_close",
            )
            assert closed is True
            assert await list_open_bot_trades(connection) == []

            event_id = await append_execution_event(
                connection,
                ts=ts,
                level="info",
                event_type="trade_filled",
                message="trade filled",
                data={"broker_trade_id": "7001"},
            )
            assert event_id > 0

        async with engine.connect() as connection:
            events = await list_events(connection)
            assert events[-1]["module"] == "execution"
            assert events[-1]["data_json"] == {"broker_trade_id": "7001"}
    finally:
        await engine.dispose()


def _alembic_config(database_url: str) -> Config:
    config = Config(Path("alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
