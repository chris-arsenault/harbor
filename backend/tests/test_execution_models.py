from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.execution.config import load_practice_execution_config
from harbor_bot.execution.models import (
    BrokerOrder,
    BrokerPosition,
    BrokerTrade,
    ExecutionMode,
    ExecutionSignal,
    FlattenResult,
    KillSwitchState,
    PracticeExecutionConfig,
    ReconciliationSummary,
    SignalReservation,
    TradingControls,
)


def test_default_practice_execution_config_is_disabled_and_practice_only() -> None:
    config = load_practice_execution_config()

    assert config.mode is ExecutionMode.PRACTICE
    assert config.trading_enabled_default is False
    assert config.max_open_positions == 1
    assert config.signal_id_namespace == "harbor-practice"
    assert config.max_daily_loss_pct == Decimal("2.0")
    assert config.max_spread_pips == Decimal("1.5")
    assert config.reconciliation_lag_tolerance_seconds == 30
    assert config.heartbeat_interval_seconds == 300
    assert config.ntfy_enabled is False
    assert config.telegram_enabled is False
    assert config.confirmation_token == "OANDA_PRACTICE"
    assert config.to_jsonable()["mode"] == "practice"


def test_practice_execution_config_rejects_live_mode() -> None:
    with pytest.raises(ValueError, match="practice mode"):
        PracticeExecutionConfig(mode="live")


def test_trading_controls_are_json_safe() -> None:
    controls = TradingControls(
        trading_enabled=True,
        confirmation_token="OANDA_PRACTICE",
        kill_switch_state=KillSwitchState.TRIPPED,
        kill_switch_reason="daily_loss",
        updated_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
    )

    assert controls.to_jsonable() == {
        "confirmation_token": "OANDA_PRACTICE",
        "kill_switch_reason": "daily_loss",
        "kill_switch_state": "tripped",
        "trading_enabled": True,
        "updated_ts": "2026-01-15T14:30:00+00:00",
    }


def test_execution_signal_and_broker_order_normalize_decimals_and_datetimes() -> None:
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    signal = ExecutionSignal(
        signal_key="harbor-practice:1:2026-01-15T14:30:00Z",
        variant_id=1,
        instrument="EUR_USD",
        direction="long",
        entry_price="1.09020",
        stop_loss_price="1.08000",
        take_profit_price="1.11000",
        units="1000",
        ts=ts,
    )
    order = BrokerOrder(
        client_order_id="harbor-practice:1:2026-01-15T14:30:00Z",
        broker_order_id="9100",
        broker_trade_id="7001",
        fill_transaction_id="9101",
        instrument="EUR_USD",
        units="1000",
        price="1.09020",
        stop_loss_price="1.08000",
        take_profit_price="1.11000",
        ts=ts,
    )

    assert signal.units == Decimal("1000")
    assert signal.ts == ts
    assert order.price == Decimal("1.09020")
    assert order.to_jsonable()["broker_trade_id"] == "7001"


def test_signal_reservation_and_reconciliation_models_are_json_safe() -> None:
    summary = ReconciliationSummary(
        checked_ts=datetime(2026, 1, 15, 14, 31, tzinfo=UTC),
        transaction_count=2,
        bot_open_trade_count=1,
        broker_open_trade_count=1,
        broker_open_position_count=1,
        drift_detected=False,
        checkpoint_transaction_id="9201",
    )
    reservation = SignalReservation(signal_key="key", reserved=True, existing_trade_id=None)
    flatten = FlattenResult(
        requested_ts=datetime(2026, 1, 15, 16, 59, tzinfo=UTC),
        reason="manual",
        closed_trade_ids=("7001",),
        closed_position_instruments=("EUR_USD",),
        reconciliation=summary,
    )

    assert reservation.to_jsonable() == {
        "existing_trade_id": None,
        "reserved": True,
        "signal_key": "key",
    }
    assert flatten.to_jsonable()["reconciliation"]["checkpoint_transaction_id"] == "9201"


def test_broker_trade_and_position_models_normalize_prices() -> None:
    trade = BrokerTrade(
        broker_trade_id="7001",
        instrument="EUR_USD",
        units="1000",
        entry_price="1.09020",
        entry_ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        state="OPEN",
        realized_pl="0",
        unrealized_pl="1.2",
    )
    position = BrokerPosition(
        instrument="EUR_USD",
        long_units="1000",
        short_units="0",
        unrealized_pl="1.2",
    )

    assert trade.entry_price == Decimal("1.09020")
    assert position.long_units == Decimal("1000")
    assert trade.to_jsonable()["entry_ts"] == "2026-01-15T14:30:00+00:00"
