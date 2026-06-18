import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from harbor_bot.execution.reconciliation import ExecutionReconciler
from harbor_bot.oanda.types import parse_transaction_frame

FIXTURES = Path(__file__).parent / "fixtures" / "oanda" / "transactions"


@pytest.mark.asyncio
async def test_reconciler_persists_transactions_once_and_closes_trades() -> None:
    repository = FakeExecutionRepository()
    notifier = FakeNotifier()
    hub = FakeHub()
    reconciler = ExecutionReconciler(
        engine=FakeEngine(),
        execution_repository=repository,
        oanda_client=FakeOandaClient(),
        notifier=notifier,
        websocket_hub=hub,
    )
    frames = [
        _transaction("order_fill_open.json"),
        _transaction("order_fill_close.json"),
        _transaction("order_fill_close.json"),
    ]

    summary = await reconciler.reconcile_transactions(frames)

    assert summary.transaction_count == 2
    assert summary.checkpoint_transaction_id == "9201"
    assert repository.persisted_transaction_ids == ["9101", "9201", "9201"]
    assert repository.closed_trades == [
        {
            "broker_trade_id": "7001",
            "close_transaction_id": "9201",
            "exit_price": "1.09200",
            "exit_reason": "broker_close",
        }
    ]
    assert repository.checkpoints == ["9201"]
    assert hub.messages[-1]["type"] == "reconciliation"
    assert notifier.events == []


@pytest.mark.asyncio
async def test_reconciler_detects_open_state_drift_and_alerts() -> None:
    repository = FakeExecutionRepository(
        open_bot_trades=[{"broker_trade_id": "7001"}, {"broker_trade_id": "missing"}]
    )
    notifier = FakeNotifier()
    hub = FakeHub()
    reconciler = ExecutionReconciler(
        engine=FakeEngine(),
        execution_repository=repository,
        oanda_client=FakeOandaClient(),
        notifier=notifier,
        websocket_hub=hub,
    )

    summary = await reconciler.reconcile_open_state()

    assert summary.drift_detected is True
    assert summary.bot_open_trade_count == 2
    assert summary.broker_open_trade_count == 1
    assert summary.broker_open_position_count == 1
    assert notifier.events[0].event_type == "reconciliation_drift"
    assert hub.messages[-1]["payload"]["drift_detected"] is True


class FakeExecutionRepository:
    def __init__(self, *, open_bot_trades=None) -> None:
        self.open_bot_trades = open_bot_trades or [{"broker_trade_id": "7001"}]
        self.persisted: set[str] = set()
        self.persisted_transaction_ids: list[str] = []
        self.closed_trades: list[dict[str, str]] = []
        self.checkpoints: list[str] = []

    async def persist_broker_transaction(
        self,
        _connection: object,
        *,
        transaction_id: str,
        transaction_type: str,
        ts: datetime,
        raw: dict,
    ) -> bool:
        self.persisted_transaction_ids.append(transaction_id)
        if transaction_id in self.persisted:
            return False
        self.persisted.add(transaction_id)
        return True

    async def close_trade_from_transaction(self, _connection: object, **kwargs) -> bool:
        self.closed_trades.append(
            {
                "broker_trade_id": kwargs["broker_trade_id"],
                "close_transaction_id": kwargs["close_transaction_id"],
                "exit_price": str(kwargs["exit_price"]),
                "exit_reason": kwargs["exit_reason"],
            }
        )
        return True

    async def store_transaction_checkpoint(
        self,
        _connection: object,
        *,
        transaction_id: str,
    ) -> None:
        self.checkpoints.append(transaction_id)

    async def list_open_bot_trades(self, _connection: object):
        return self.open_bot_trades

    async def append_execution_event(self, *_args, **_kwargs):
        return 1


class FakeOandaClient:
    async def list_open_trades(self):
        from harbor_bot.oanda.types import OpenTrade

        return [
            OpenTrade(
                trade_id="7001",
                instrument="EUR_USD",
                price="1.09020",
                open_time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
                initial_units="1000",
                current_units="1000",
                state="OPEN",
                realized_pl="0",
                unrealized_pl="1.2",
                raw={},
            )
        ]

    async def list_open_positions(self):
        from harbor_bot.oanda.types import OpenPosition

        return [
            OpenPosition(
                instrument="EUR_USD",
                long_units="1000",
                short_units="0",
                unrealized_pl="1.2",
                raw={},
            )
        ]


class FakeNotifier:
    def __init__(self) -> None:
        self.events = []

    async def notify(self, event):
        from harbor_bot.notifier.models import NotificationResult

        self.events.append(event)
        return NotificationResult(sent=True, channels=("fake",))


class FakeHub:
    def __init__(self) -> None:
        self.messages = []

    async def broadcast(self, message):
        self.messages.append(message)


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


def _transaction(name: str):
    frame = parse_transaction_frame(json.loads((FIXTURES / name).read_text()))
    assert frame.__class__.__name__ == "TransactionFrame"
    return frame
