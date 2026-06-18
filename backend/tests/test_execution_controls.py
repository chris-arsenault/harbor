from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.execution.config import load_practice_execution_config
from harbor_bot.execution.controls import TradingControlService
from harbor_bot.execution.models import KillSwitchState
from harbor_bot.oanda.types import TradeCloseResult


@pytest.mark.asyncio
async def test_control_service_enables_practice_trading_when_guards_pass() -> None:
    repository = FakeVariantRepository(promoted={"id": 10})
    execution_repository = FakeExecutionRepository()
    service = _service(repository=repository, execution_repository=execution_repository)

    controls = await service.set_trading_enabled(
        enabled=True,
        confirmation_token="OANDA_PRACTICE",
    )

    assert controls.trading_enabled is True
    assert controls.kill_switch_state is KillSwitchState.CLEAR
    assert execution_repository.saved_controls[-1].trading_enabled is True


@pytest.mark.asyncio
async def test_control_service_rejects_live_mode_and_missing_promoted_variant() -> None:
    with pytest.raises(ValueError, match="practice mode only"):
        await _service(oanda_env="live").set_trading_enabled(
            enabled=True,
            confirmation_token="OANDA_PRACTICE",
        )

    with pytest.raises(ValueError, match="promoted variant"):
        await _service(repository=FakeVariantRepository(promoted=None)).set_trading_enabled(
            enabled=True,
            confirmation_token="OANDA_PRACTICE",
        )


@pytest.mark.asyncio
async def test_flatten_now_closes_broker_trades_and_positions_then_reconciles() -> None:
    oanda = FakeOandaClient()
    reconciler = FakeReconciler()
    notifier = FakeNotifier()
    hub = FakeHub()
    service = _service(
        oanda=oanda,
        reconciler=reconciler,
        notifier=notifier,
        hub=hub,
    )

    result = await service.flatten_now(reason="manual")

    assert result.reason == "manual"
    assert result.closed_trade_ids == ("7001",)
    assert result.closed_position_instruments == ("EUR_USD",)
    assert oanda.closed_trades == ["7001"]
    assert oanda.closed_positions == [("EUR_USD", "ALL", None)]
    assert reconciler.called is True
    assert notifier.events[0].event_type == "flatten"
    assert hub.messages[-1]["type"] == "control"


@pytest.mark.asyncio
async def test_daily_loss_kill_switch_disables_trading_and_flattens() -> None:
    execution_repository = FakeExecutionRepository()
    service = _service(execution_repository=execution_repository)

    result = await service.trip_daily_loss_if_needed(
        day_start_nav=Decimal("10000"),
        current_nav=Decimal("9799"),
    )

    assert result is not None
    assert execution_repository.saved_controls[-1].trading_enabled is False
    assert execution_repository.saved_controls[-1].kill_switch_state is KillSwitchState.TRIPPED
    assert execution_repository.saved_controls[-1].kill_switch_reason == "daily_loss"


class FakeVariantRepository:
    def __init__(self, *, promoted) -> None:
        self.promoted = promoted

    async def get_promoted_variant(self, _connection: object):
        return self.promoted


class FakeExecutionRepository:
    def __init__(self) -> None:
        self.saved_controls = []

    async def get_trading_controls(self, _connection: object, *, confirmation_token: str):
        from harbor_bot.execution.models import TradingControls

        return TradingControls(
            trading_enabled=False,
            confirmation_token=confirmation_token,
            kill_switch_state=KillSwitchState.CLEAR,
        )

    async def set_trading_controls(self, _connection: object, controls):
        self.saved_controls.append(controls)

    async def list_open_bot_trades(self, _connection: object):
        return []

    async def append_execution_event(self, *_args, **_kwargs):
        return 1


class FakeOandaClient:
    def __init__(self) -> None:
        self.closed_trades: list[str] = []
        self.closed_positions: list[tuple[str, str | None, str | None]] = []

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

    async def close_trade(self, *, trade_id: str, units: str = "ALL"):
        self.closed_trades.append(trade_id)
        return TradeCloseResult(
            trade_id=trade_id,
            close_transaction_ids=("9201",),
            last_transaction_id="9201",
            raw={},
        )

    async def close_position(
        self,
        *,
        instrument: str,
        long_units: str | None = None,
        short_units: str | None = None,
    ):
        self.closed_positions.append((instrument, long_units, short_units))


class FakeReconciler:
    def __init__(self) -> None:
        self.called = False

    async def reconcile_open_state(self):
        from harbor_bot.execution.models import ReconciliationSummary

        self.called = True
        return ReconciliationSummary(
            checked_ts=datetime(2026, 1, 15, 17, 0, tzinfo=UTC),
            transaction_count=0,
            bot_open_trade_count=0,
            broker_open_trade_count=0,
            broker_open_position_count=0,
            drift_detected=False,
            checkpoint_transaction_id="9201",
        )


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


def _service(
    *,
    repository=None,
    execution_repository=None,
    oanda=None,
    reconciler=None,
    notifier=None,
    hub=None,
    oanda_env: str = "practice",
) -> TradingControlService:
    return TradingControlService(
        engine=FakeEngine(),
        variant_repository=repository or FakeVariantRepository(promoted={"id": 10}),
        execution_repository=execution_repository or FakeExecutionRepository(),
        oanda_client=oanda or FakeOandaClient(),
        reconciler=reconciler or FakeReconciler(),
        notifier=notifier or FakeNotifier(),
        websocket_hub=hub or FakeHub(),
        execution_config=load_practice_execution_config(),
        oanda_env=oanda_env,
    )
