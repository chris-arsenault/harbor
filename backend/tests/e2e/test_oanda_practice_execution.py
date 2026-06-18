import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from harbor_bot.execution.config import load_practice_execution_config
from harbor_bot.execution.controls import TradingControlService
from harbor_bot.execution.reconciliation import ExecutionReconciler
from harbor_bot.execution.service import PracticeExecutionService
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.oanda.types import (
    OpenPosition,
    OpenTrade,
    OrderCreateResult,
    TradeCloseResult,
    parse_transaction_frame,
)
from harbor_bot.strategy.core import StrategyResult
from harbor_bot.strategy.models import (
    DayState,
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    StrategyConfig,
    StrategyDecision,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "oanda" / "transactions"


@pytest.mark.asyncio
async def test_oanda_practice_order_reconciles_exactly_to_persisted_trade() -> None:
    variant_repository = FakeVariantRepository()
    execution_repository = FakeExecutionRepository()
    oanda = FakeOandaPracticeClient()
    notifier = FakeNotifier()
    hub = FakeHub()
    config = load_practice_execution_config()
    reconciler = ExecutionReconciler(
        engine=FakeEngine(),
        execution_repository=execution_repository,
        oanda_client=oanda,
        notifier=notifier,
        websocket_hub=hub,
    )
    controls = TradingControlService(
        engine=FakeEngine(),
        variant_repository=variant_repository,
        execution_repository=execution_repository,
        oanda_client=oanda,
        reconciler=reconciler,
        notifier=notifier,
        websocket_hub=hub,
        execution_config=config,
        oanda_env="practice",
    )
    service = PracticeExecutionService(
        engine=FakeEngine(),
        variant_repository=variant_repository,
        execution_repository=execution_repository,
        oanda_client=oanda,
        notifier=notifier,
        websocket_hub=hub,
        control_service=controls,
        execution_config=config,
        base_strategy_config=_strategy_config(),
        instrument_rules=_instrument_rules(),
        strategy_evaluator=_entry_evaluator,
    )

    await variant_repository.promote_variant(variant_id=7)
    await controls.set_trading_enabled(enabled=True, confirmation_token="OANDA_PRACTICE")
    order_result = await service.process_closed_candle(_closed_candle())
    await reconciler.reconcile_transactions([_transaction("order_fill_open.json")])
    flatten_result = await controls.flatten_now(
        reason="manual",
        confirmation_token="OANDA_PRACTICE",
    )
    await reconciler.reconcile_transactions([_transaction("order_fill_close.json")])

    assert order_result.orders_placed == 1
    assert flatten_result.closed_trade_ids == ("7001",)
    assert oanda.created_orders[0].stop_loss_price == Decimal("1.08000")
    assert oanda.created_orders[0].take_profit_price == Decimal("1.11000")

    trade = execution_repository.trades[0]
    assert trade["broker_order_id"] == "9100"
    assert trade["client_order_id"] == "harbor-practice:7:EUR_USD:2026-01-15T14:30:00+00:00"
    assert trade["broker_trade_id"] == "7001"
    assert trade["open_transaction_id"] == "9101"
    assert trade["close_transaction_id"] == "9201"
    assert trade["entry_price"] == Decimal("1.09020")
    assert trade["exit_price"] == Decimal("1.09200")
    assert trade["units"] == Decimal("1000")
    assert trade["pnl"] == Decimal("18.00000")
    assert execution_repository.transaction_ids == ["9101", "9201"]
    assert execution_repository.checkpoints[-1] == "9201"
    assert notifier.event_types == ["fill", "reconciliation_drift", "flatten"]


def _entry_evaluator(**_kwargs) -> StrategyResult:
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
        decisions=[StrategyDecision(kind="market_entry", ts=setup.ts, payload={"setup": setup})],
    )


class FakeVariantRepository:
    def __init__(self) -> None:
        self.promoted: dict | None = None

    async def promote_variant(self, *, variant_id: int) -> None:
        self.promoted = {
            "id": variant_id,
            "label": "promoted",
            "params": {},
            "status": "promoted",
        }

    async def get_promoted_variant(self, _connection: object):
        return self.promoted


class FakeExecutionRepository:
    def __init__(self) -> None:
        self.controls = None
        self.signal_ids: dict[str, int] = {}
        self.trades: list[dict] = []
        self.transactions: set[str] = set()
        self.transaction_ids: list[str] = []
        self.checkpoints: list[str] = []

    async def get_trading_controls(self, _connection: object, *, confirmation_token: str):
        from harbor_bot.execution.models import TradingControls

        return self.controls or TradingControls(
            trading_enabled=False,
            confirmation_token=confirmation_token,
        )

    async def set_trading_controls(self, _connection: object, controls):
        self.controls = controls

    async def list_open_bot_trades(self, _connection: object):
        return [trade for trade in self.trades if trade["exit_ts"] is None]

    async def reserve_signal(self, _connection: object, signal):
        from harbor_bot.execution.models import SignalReservation

        if signal.signal_key in self.signal_ids:
            return SignalReservation(signal_key=signal.signal_key, reserved=False)
        self.signal_ids[signal.signal_key] = len(self.signal_ids) + 1
        return SignalReservation(signal_key=signal.signal_key, reserved=True)

    async def get_signal_id_by_key(self, _connection: object, signal_key: str):
        return self.signal_ids.get(signal_key)

    async def create_or_update_trade_from_order(
        self,
        _connection: object,
        *,
        signal_id,
        signal,
        order,
    ):
        trade = {
            "signal_id": signal_id,
            "broker_order_id": order.broker_order_id,
            "client_order_id": order.client_order_id,
            "broker_trade_id": order.broker_trade_id,
            "open_transaction_id": order.fill_transaction_id,
            "close_transaction_id": None,
            "side": signal.direction,
            "units": abs(order.units),
            "entry_price": order.price,
            "entry_ts": order.ts,
            "exit_price": None,
            "exit_ts": None,
            "pnl": None,
            "r_multiple": None,
            "exit_reason": None,
        }
        self.trades.append(trade)
        return len(self.trades)

    async def persist_broker_transaction(
        self,
        _connection: object,
        *,
        transaction_id: str,
        transaction_type: str,
        ts: datetime,
        raw: dict,
    ) -> bool:
        if transaction_id in self.transactions:
            return False
        self.transactions.add(transaction_id)
        self.transaction_ids.append(transaction_id)
        return True

    async def close_trade_from_transaction(self, _connection: object, **kwargs) -> bool:
        for trade in self.trades:
            if trade["broker_trade_id"] == kwargs["broker_trade_id"] and trade["exit_ts"] is None:
                trade["close_transaction_id"] = kwargs["close_transaction_id"]
                trade["exit_price"] = kwargs["exit_price"]
                trade["exit_ts"] = kwargs["exit_ts"]
                trade["pnl"] = kwargs["pnl"]
                trade["r_multiple"] = kwargs["r_multiple"]
                trade["exit_reason"] = kwargs["exit_reason"]
                return True
        return False

    async def store_transaction_checkpoint(self, _connection: object, *, transaction_id: str):
        self.checkpoints.append(transaction_id)

    async def append_execution_event(self, *_args, **_kwargs):
        return 1


class FakeOandaPracticeClient:
    def __init__(self) -> None:
        self.created_orders = []
        self.trade_open = False

    async def create_market_order_with_bracket(self, request):
        self.created_orders.append(request)
        self.trade_open = True
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

    async def list_open_trades(self):
        if not self.trade_open:
            return []
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
                unrealized_pl="0",
                raw={},
            )
        ]

    async def list_open_positions(self):
        if not self.trade_open:
            return []
        return [
            OpenPosition(
                instrument="EUR_USD",
                long_units="1000",
                short_units="0",
                unrealized_pl="0",
                raw={},
            )
        ]

    async def close_trade(self, *, trade_id: str, units: str = "ALL"):
        self.trade_open = False
        return TradeCloseResult(
            trade_id=trade_id,
            close_transaction_ids=("9201",),
            last_transaction_id="9201",
            raw={},
        )

    async def close_position(self, **_kwargs):
        self.trade_open = False


class FakeNotifier:
    def __init__(self) -> None:
        self.event_types: list[str] = []

    async def notify(self, event):
        from harbor_bot.notifier.models import NotificationResult

        self.event_types.append(event.event_type)
        return NotificationResult(sent=True, channels=("fake",))


class FakeHub:
    async def broadcast(self, _message):
        return None


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


def _closed_candle() -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.09000"),
        h=Decimal("1.09100"),
        low=Decimal("1.08950"),
        c=Decimal("1.09050"),
        volume=128,
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
