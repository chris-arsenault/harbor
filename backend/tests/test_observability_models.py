from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from harbor_bot.observability.models import (
    CandlePoint,
    ChartMarker,
    DashboardSnapshot,
    EventLogItem,
    FvgBox,
    SessionLevelSnapshot,
    SignalMarker,
    StatusSnapshot,
    TradeMarker,
    WebSocketEnvelope,
)


def test_status_snapshot_serializes_decimal_and_datetime_values() -> None:
    heartbeat = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)

    status = StatusSnapshot(
        bot_state="WAIT_SWEEP",
        session_phase="ny_trade",
        connection_health="healthy",
        mode="practice",
        trading_enabled=False,
        trading_controls_available=False,
        kill_switch_state="armed",
        day_pnl=Decimal("12.345"),
        trades_today=1,
        max_trades_per_day=2,
        account_nav=Decimal("10000.25"),
        open_positions=0,
        unrealized_pnl=Decimal("0"),
        last_heartbeat=heartbeat,
    )

    assert status.to_jsonable() == {
        "bot_state": "WAIT_SWEEP",
        "session_phase": "ny_trade",
        "connection_health": "healthy",
        "mode": "practice",
        "trading_enabled": False,
        "trading_controls_available": False,
        "kill_switch_state": "armed",
        "day_pnl": "12.345",
        "trades_today": 1,
        "max_trades_per_day": 2,
        "account_nav": "10000.25",
        "open_positions": 0,
        "unrealized_pnl": "0",
        "last_heartbeat": "2026-01-15T14:30:00Z",
        "promoted_variant": None,
        "reconciliation_state": None,
        "open_position": None,
        "notifier_state": None,
        "deployment": None,
    }


def test_dashboard_snapshot_keeps_server_authored_chart_facts() -> None:
    ts = datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
    status = StatusSnapshot(
        bot_state="WAIT_FVG",
        session_phase="ny_trade",
        connection_health="healthy",
        mode="practice",
        trading_enabled=False,
        trading_controls_available=False,
        kill_switch_state="armed",
        day_pnl=Decimal("0"),
        trades_today=0,
        max_trades_per_day=2,
        account_nav=None,
        open_positions=None,
        unrealized_pnl=None,
        last_heartbeat=ts,
    )
    levels = SessionLevelSnapshot(
        date=date(2026, 1, 15),
        instrument="EUR_USD",
        asia_high=Decimal("1.1100"),
        asia_low=Decimal("1.1000"),
        london_high=Decimal("1.1150"),
        london_low=Decimal("1.1050"),
        swept_levels=("asia_low",),
        taken_levels=("asia_low",),
    )
    candle = CandlePoint(
        instrument="EUR_USD",
        ts=ts,
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0995"),
        close=Decimal("1.1005"),
        volume=125,
        complete=True,
    )
    marker = ChartMarker(
        kind="sweep",
        ts=ts,
        instrument="EUR_USD",
        label="Asia low swept",
        price=Decimal("1.1000"),
        direction="bullish",
        level_name="asia_low",
    )
    fvg = FvgBox(
        id=7,
        ts=ts,
        instrument="EUR_USD",
        type="bullish",
        top=Decimal("1.1015"),
        bottom=Decimal("1.1005"),
        midpoint=Decimal("1.1010"),
        sweep_id=3,
    )
    signal = SignalMarker(
        id=9,
        ts=ts,
        instrument="EUR_USD",
        direction="long",
        entry=Decimal("1.1020"),
        stop=Decimal("1.0990"),
        target=Decimal("1.1080"),
        status="filled",
    )
    trade = TradeMarker(
        id=11,
        signal_id=9,
        side="long",
        units=Decimal("1000"),
        entry_price=Decimal("1.1020"),
        entry_ts=ts,
        exit_price=Decimal("1.1080"),
        exit_ts=ts,
        pnl=Decimal("60"),
        r_multiple=Decimal("2"),
        exit_reason="target",
    )
    event = EventLogItem(
        id=13,
        ts=ts,
        level="info",
        module="strategy",
        type="signal",
        message="server-authored signal",
        data={"signal_id": 9},
    )

    snapshot = DashboardSnapshot(
        status=status,
        levels=levels,
        candles=(candle,),
        markers=(marker,),
        fvgs=(fvg,),
        signals=(signal,),
        trades=(trade,),
        events=(event,),
    )

    payload = snapshot.to_jsonable()
    assert payload["levels"]["asia_low"] == "1.1000"
    assert payload["candles"][0]["close"] == "1.1005"
    assert payload["markers"][0]["kind"] == "sweep"
    assert payload["fvgs"][0]["sweep_id"] == 3
    assert payload["signals"][0]["status"] == "filled"
    assert payload["trades"][0]["exit_reason"] == "target"
    assert payload["events"][0]["data"] == {"signal_id": 9}


def test_websocket_envelope_serializes_type_timestamp_and_payload() -> None:
    sent_at = datetime(2026, 1, 15, 14, 32, tzinfo=UTC)
    envelope = WebSocketEnvelope(
        type="status",
        sent_at=sent_at,
        payload={"bot_state": "WAIT_SWEEP", "day_pnl": Decimal("1.25")},
    )

    assert envelope.to_jsonable() == {
        "type": "status",
        "sent_at": "2026-01-15T14:32:00Z",
        "payload": {"bot_state": "WAIT_SWEEP", "day_pnl": "1.25"},
    }


def test_observability_models_are_immutable() -> None:
    status = StatusSnapshot(
        bot_state="IDLE",
        session_phase="closed",
        connection_health="unknown",
        mode="practice",
        trading_enabled=False,
        trading_controls_available=False,
        kill_switch_state="armed",
        day_pnl=Decimal("0"),
        trades_today=0,
        max_trades_per_day=2,
        account_nav=None,
        open_positions=None,
        unrealized_pnl=None,
        last_heartbeat=None,
    )

    with pytest.raises(ValidationError):
        status.bot_state = "RUNNING"
