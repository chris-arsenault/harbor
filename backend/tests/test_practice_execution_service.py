from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from harbor_bot.execution.config import load_practice_execution_config
from harbor_bot.execution.service import PracticeExecutionService
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.oanda.types import OrderCreateResult
from harbor_bot.strategy.core import StrategyResult
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyConfig,
    StrategyDecision,
)


@pytest.mark.asyncio
async def test_practice_execution_places_bracket_order_for_promoted_variant() -> None:
    repository = FakeVariantRepository()
    execution_repository = FakeExecutionRepository()
    oanda = FakeOandaClient()
    notifier = FakeNotifier()
    hub = FakeHub()
    service = _service(
        repository=repository,
        execution_repository=execution_repository,
        oanda=oanda,
        notifier=notifier,
        hub=hub,
        strategy_evaluator=entry_evaluator,
    )

    result = await service.process_closed_candle(_candle())

    assert result.orders_placed == 1
    assert result.skipped_reason is None
    assert repository.requested_promoted_variant is True
    assert execution_repository.reserved_keys == [
        "harbor-practice:10:EUR_USD:2026-01-15T14:30:00+00:00"
    ]
    assert oanda.requests[0].instrument == "EUR_USD"
    assert oanda.requests[0].units == 1000
    assert oanda.requests[0].stop_loss_price == Decimal("1.08000")
    assert oanda.requests[0].take_profit_price == Decimal("1.11000")
    assert execution_repository.trades[0]["broker_trade_id"] == "7001"
    assert notifier.events[0].event_type == "fill"
    assert hub.messages[0]["type"] == "trade"


@pytest.mark.asyncio
async def test_practice_execution_skips_when_trading_disabled() -> None:
    execution_repository = FakeExecutionRepository(trading_enabled=False)
    service = _service(
        execution_repository=execution_repository,
        strategy_evaluator=entry_evaluator,
    )

    result = await service.process_closed_candle(_candle())

    assert result.orders_placed == 0
    assert result.skipped_reason == "trading_disabled"


@pytest.mark.asyncio
async def test_practice_execution_dedupes_reserved_signals() -> None:
    execution_repository = FakeExecutionRepository(duplicate_signal=True)
    oanda = FakeOandaClient()
    service = _service(
        execution_repository=execution_repository,
        oanda=oanda,
        strategy_evaluator=entry_evaluator,
    )

    result = await service.process_closed_candle(_candle())

    assert result.orders_placed == 0
    assert result.skipped_reason == "duplicate_signal"
    assert oanda.requests == []


@pytest.mark.asyncio
async def test_practice_execution_rejects_incomplete_candles() -> None:
    service = _service(strategy_evaluator=entry_evaluator)

    with pytest.raises(ValueError, match="closed candles"):
        await service.process_closed_candle(_candle(complete=False))


@pytest.mark.asyncio
async def test_practice_execution_delegates_flatten_decisions_to_control_service() -> None:
    controls = FakeControlService()
    service = _service(strategy_evaluator=flatten_evaluator, controls=controls)

    result = await service.process_closed_candle(_candle())

    assert result.flatten_requested is True
    assert result.orders_placed == 0
    assert controls.flatten_reasons == ["ny_close"]


def entry_evaluator(**kwargs) -> StrategyResult:
    config = kwargs["config"]
    assert config.fvg_window == 9
    setup = MarketEntrySetup(
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_HIGH,
        entry_reference=Decimal("1.09020"),
        stop=Decimal("1.08000"),
        target=Decimal("1.11000"),
        risk=Decimal("0.01020"),
        units=Decimal("1000"),
    )
    return StrategyResult(
        state=DayState(trading_date=date(2026, 1, 15), has_open_position=True),
        decisions=[
            StrategyDecision(
                kind="market_entry",
                ts=setup.ts,
                payload={"setup": setup},
            )
        ],
    )


def flatten_evaluator(**_kwargs) -> StrategyResult:
    return StrategyResult(
        state=DayState(trading_date=date(2026, 1, 15)),
        decisions=[
            StrategyDecision(
                kind="flatten",
                ts=datetime(2026, 1, 15, 16, 59, tzinfo=UTC),
                payload={"reason": "ny_close"},
            )
        ],
    )


class FakeVariantRepository:
    def __init__(self) -> None:
        self.requested_promoted_variant = False

    async def get_promoted_variant(self, _connection: object):
        self.requested_promoted_variant = True
        return {
            "id": 10,
            "label": "promoted",
            "params": {"fvg_window": 9},
            "status": "promoted",
        }


class FakeExecutionRepository:
    def __init__(self, *, trading_enabled: bool = True, duplicate_signal: bool = False) -> None:
        self.trading_enabled = trading_enabled
        self.duplicate_signal = duplicate_signal
        self.reserved_keys: list[str] = []
        self.trades: list[dict[str, str | int | None]] = []

    async def get_trading_controls(self, _connection: object, *, confirmation_token: str):
        from harbor_bot.execution.models import TradingControls

        return TradingControls(
            trading_enabled=self.trading_enabled,
            confirmation_token=confirmation_token,
        )

    async def list_open_bot_trades(self, _connection: object):
        return []

    async def reserve_signal(self, _connection: object, signal):
        from harbor_bot.execution.models import SignalReservation

        self.reserved_keys.append(signal.signal_key)
        return SignalReservation(
            signal_key=signal.signal_key,
            reserved=not self.duplicate_signal,
            existing_trade_id=42 if self.duplicate_signal else None,
        )

    async def get_signal_id_by_key(self, _connection: object, _signal_key: str):
        return 101

    async def create_or_update_trade_from_order(
        self,
        _connection: object,
        *,
        signal_id,
        signal,
        order,
    ):
        self.trades.append(
            {
                "broker_trade_id": order.broker_trade_id,
                "client_order_id": order.client_order_id,
                "signal_id": signal_id,
                "signal_key": signal.signal_key,
            }
        )
        return 501

    async def append_execution_event(self, *_args, **_kwargs):
        return 1


class FakeOandaClient:
    def __init__(self) -> None:
        self.requests = []

    async def create_market_order_with_bracket(self, request):
        self.requests.append(request)
        return OrderCreateResult(
            order_id="9100",
            fill_transaction_id="9101",
            trade_id="7001",
            instrument=request.instrument,
            units=Decimal(request.units),
            price=Decimal("1.09020"),
            last_transaction_id="9103",
            related_transaction_ids=("9100", "9101", "9103"),
            raw={},
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


class FakeControlService:
    def __init__(self) -> None:
        self.flatten_reasons: list[str] = []

    async def flatten_now(self, *, reason: str):
        self.flatten_reasons.append(reason)


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
    notifier=None,
    hub=None,
    strategy_evaluator=None,
    controls=None,
) -> PracticeExecutionService:
    return PracticeExecutionService(
        engine=FakeEngine(),
        variant_repository=repository or FakeVariantRepository(),
        execution_repository=execution_repository or FakeExecutionRepository(),
        oanda_client=oanda or FakeOandaClient(),
        notifier=notifier or FakeNotifier(),
        websocket_hub=hub or FakeHub(),
        control_service=controls,
        execution_config=load_practice_execution_config(),
        base_strategy_config=_strategy_config(),
        instrument_rules=_instrument_rules(),
        strategy_evaluator=strategy_evaluator or entry_evaluator,
    )


def _candle(*, complete: bool = True) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.09000"),
        h=Decimal("1.09100"),
        low=Decimal("1.08950"),
        c=Decimal("1.09050"),
        volume=128,
        complete=complete,
    )


def _strategy_config() -> StrategyConfig:
    return StrategyConfig(
        instrument="EUR_USD",
        timezone="America/New_York",
        sessions={
            "asia": {"start": "18:00", "end": "00:00"},
            "london": {"start": "02:00", "end": "05:00"},
            "ny_trade": {"start": "09:30", "end": "11:00"},
        },
        fvg_window=4,
        sweep_buffer_pips=Decimal("0.2"),
        risk_per_trade_pct=Decimal("0.5"),
        max_daily_loss_pct=Decimal("2.0"),
        target_mode="opposite_session",
        rr_floor=Decimal("2"),
        liquidity_rr_floor=Decimal("1"),
        one_trade_per_level=True,
        max_trades_per_day=1,
        max_spread_pips=Decimal("1.5"),
        swing_lookback=3,
        max_units=Decimal("100000"),
    )


def _instrument_rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
