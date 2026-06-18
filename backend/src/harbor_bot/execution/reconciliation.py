from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.execution.models import ReconciliationSummary
from harbor_bot.notifier.models import NotificationEvent
from harbor_bot.oanda.types import TransactionFrame
from harbor_bot.persistence import execution_repository


class ExecutionReconciler:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        execution_repository: Any = execution_repository,
        oanda_client: Any,
        notifier: Any,
        websocket_hub: Any | None = None,
    ) -> None:
        self._engine = engine
        self._repository = execution_repository
        self._oanda = oanda_client
        self._notifier = notifier
        self._websocket_hub = websocket_hub

    async def reconcile_transactions(
        self,
        frames: Iterable[TransactionFrame],
    ) -> ReconciliationSummary:
        processed_count = 0
        checkpoint: str | None = None
        async with self._engine.connect() as connection:
            for frame in frames:
                if frame.transaction_id is None:
                    continue
                inserted = await self._repository.persist_broker_transaction(
                    connection,
                    transaction_id=frame.transaction_id,
                    transaction_type=frame.transaction_type,
                    ts=frame.time,
                    raw=frame.raw,
                )
                checkpoint = frame.transaction_id
                if not inserted:
                    continue
                processed_count += 1
                await self._apply_transaction(connection, frame)

            if checkpoint is not None:
                await self._repository.store_transaction_checkpoint(
                    connection,
                    transaction_id=checkpoint,
                )
            open_bot_trades = await self._repository.list_open_bot_trades(connection)

        summary = ReconciliationSummary(
            checked_ts=_now(),
            transaction_count=processed_count,
            bot_open_trade_count=len(open_bot_trades),
            broker_open_trade_count=len(open_bot_trades),
            broker_open_position_count=0,
            drift_detected=False,
            checkpoint_transaction_id=checkpoint,
        )
        await self._broadcast_summary(summary)
        return summary

    async def reconcile_open_state(self) -> ReconciliationSummary:
        broker_trades = await self._oanda.list_open_trades()
        broker_positions = await self._oanda.list_open_positions()
        async with self._engine.connect() as connection:
            bot_trades = await self._repository.list_open_bot_trades(connection)

        bot_trade_ids = {str(trade["broker_trade_id"]) for trade in bot_trades}
        broker_trade_ids = {str(trade.trade_id) for trade in broker_trades}
        drift_detected = bot_trade_ids != broker_trade_ids
        summary = ReconciliationSummary(
            checked_ts=_now(),
            transaction_count=0,
            bot_open_trade_count=len(bot_trades),
            broker_open_trade_count=len(broker_trades),
            broker_open_position_count=len(broker_positions),
            drift_detected=drift_detected,
            checkpoint_transaction_id=None,
        )
        if drift_detected:
            await self._notifier.notify(
                NotificationEvent(
                    event_type="reconciliation_drift",
                    title="Harbor reconciliation drift",
                    message="Bot open trades differ from OANDA practice open trades",
                    ts=summary.checked_ts,
                    severity="warning",
                    data=summary.to_jsonable(),
                )
            )
        await self._broadcast_summary(summary)
        return summary

    async def _apply_transaction(self, connection: Any, frame: TransactionFrame) -> None:
        if frame.transaction_type != "ORDER_FILL":
            return

        for closed in frame.raw.get("tradesClosed", []):
            trade_id = str(closed["tradeID"])
            exit_price = Decimal(str(closed.get("price", frame.raw.get("price", "0"))))
            pnl = Decimal(str(closed.get("realizedPL", frame.raw.get("pl", "0"))))
            await self._repository.close_trade_from_transaction(
                connection,
                broker_trade_id=trade_id,
                close_transaction_id=str(frame.transaction_id),
                exit_price=exit_price,
                exit_ts=frame.time,
                pnl=pnl,
                r_multiple=Decimal("0"),
                exit_reason="broker_close",
            )
            await self._repository.append_execution_event(
                connection,
                ts=frame.time,
                level="info",
                event_type="trade_closed",
                message="broker trade closed",
                data={"broker_trade_id": trade_id, "transaction_id": frame.transaction_id},
            )

    async def _broadcast_summary(self, summary: ReconciliationSummary) -> None:
        if self._websocket_hub is not None:
            await self._websocket_hub.broadcast(
                {
                    "type": "reconciliation",
                    "payload": summary.to_jsonable(),
                }
            )


def _now() -> datetime:
    return datetime.now(UTC)
