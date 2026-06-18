from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from harbor_bot.api import create_app
from harbor_bot.observability.models import (
    CandlePoint,
    ChartMarker,
    EventLogItem,
    FvgBox,
    SessionLevelSnapshot,
    SignalMarker,
    StatusSnapshot,
    TradeMarker,
)


def test_status_endpoint_reads_injected_observability_service() -> None:
    service = FakeObservabilityService()
    client = TestClient(create_app(observability_service=service))

    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["bot_state"] == "WAIT_SWEEP"
    assert response.json()["mode"] == "practice"
    assert response.json()["trading_enabled"] is False
    assert response.json()["trading_controls_available"] is False
    assert response.json()["notifier_state"] == {
        "ntfy_enabled": False,
        "telegram_enabled": False,
    }
    assert response.json()["deployment"]["access"] == "LAN"
    assert response.json()["deployment"]["frontend_url"] == "http://192.168.66.3:30091/"
    assert response.json()["deployment"]["readiness_path"] == "/ready"


def test_levels_endpoint_parses_date_and_returns_404_for_missing_levels() -> None:
    service = FakeObservabilityService()
    client = TestClient(create_app(observability_service=service))

    response = client.get("/api/levels?date=2026-01-15&instrument=EUR_USD")
    missing = client.get("/api/levels?date=2026-01-16&instrument=EUR_USD")

    assert response.status_code == 200
    assert response.json()["asia_low"] == "1.10000000"
    assert response.json()["swept_levels"] == ["asia_low"]
    assert service.level_requests == [
        (date(2026, 1, 15), "EUR_USD"),
        (date(2026, 1, 16), "EUR_USD"),
    ]
    assert missing.status_code == 404
    assert missing.json() == {"detail": "session levels not found"}


def test_candles_endpoint_parses_instrument_and_time_range() -> None:
    service = FakeObservabilityService()
    client = TestClient(create_app(observability_service=service))

    response = client.get(
        "/api/candles?instrument=EUR_USD&from=2026-01-15T14:00:00Z&to=2026-01-15T15:00:00Z"
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "instrument": "EUR_USD",
            "ts": "2026-01-15T14:00:00Z",
            "open": "1.10000000",
            "high": "1.10500000",
            "low": "1.09900000",
            "close": "1.10400000",
            "volume": 100,
            "complete": True,
        }
    ]
    assert service.candle_request == (
        "EUR_USD",
        datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
        datetime(2026, 1, 15, 15, 0, tzinfo=UTC),
    )


def test_markers_endpoint_returns_server_authored_overlay_payloads() -> None:
    client = TestClient(create_app(observability_service=FakeObservabilityService()))

    response = client.get("/api/markers?date=2026-01-15&instrument=EUR_USD")

    assert response.status_code == 200
    assert response.json()["markers"][0]["kind"] == "sweep"
    assert response.json()["fvgs"][0]["sweep_id"] == 3
    assert response.json()["signals"][0]["entry"] == "1.10500000"
    assert response.json()["trades"][0]["exit_reason"] == "target"


def test_events_endpoint_filters_by_level_and_limit() -> None:
    service = FakeObservabilityService()
    client = TestClient(create_app(observability_service=service))

    response = client.get("/api/events?level=warn&limit=5")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 13,
            "ts": "2026-01-15T14:31:00Z",
            "level": "warn",
            "module": "feed",
            "type": "heartbeat.stale",
            "message": "heartbeat stale",
            "data": {"seconds": 31},
        }
    ]
    assert service.events_request == ("warn", 5)


class FakeObservabilityService:
    def __init__(self) -> None:
        ts = datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
        self.level_requests: list[tuple[date, str]] = []
        self.candle_request: tuple[str, datetime, datetime] | None = None
        self.events_request: tuple[str | None, int] | None = None
        self.status = StatusSnapshot(
            bot_state="WAIT_SWEEP",
            session_phase="ny_trade",
            connection_health="unknown",
            mode="practice",
            trading_enabled=False,
            trading_controls_available=False,
            kill_switch_state="armed",
            day_pnl=Decimal("60.00000000"),
            trades_today=1,
            max_trades_per_day=2,
            account_nav=Decimal("10060.00000000"),
            open_positions=0,
            unrealized_pnl=Decimal("0E-8"),
            last_heartbeat=ts,
            notifier_state={"ntfy_enabled": False, "telegram_enabled": False},
            deployment={
                "access": "LAN",
                "frontend_url": "http://192.168.66.3:30091/",
                "public_route": False,
                "readiness_path": "/ready",
            },
        )
        self.levels = SessionLevelSnapshot(
            date=date(2026, 1, 15),
            instrument="EUR_USD",
            asia_high=Decimal("1.11000000"),
            asia_low=Decimal("1.10000000"),
            london_high=Decimal("1.11500000"),
            london_low=Decimal("1.10500000"),
            swept_levels=("asia_low",),
            taken_levels=(),
        )
        self.candle = CandlePoint(
            instrument="EUR_USD",
            ts=datetime(2026, 1, 15, 14, 0, tzinfo=UTC),
            open=Decimal("1.10000000"),
            high=Decimal("1.10500000"),
            low=Decimal("1.09900000"),
            close=Decimal("1.10400000"),
            volume=100,
            complete=True,
        )
        self.markers = {
            "markers": (
                ChartMarker(
                    kind="sweep",
                    ts=ts,
                    instrument="EUR_USD",
                    label="asia_low swept",
                    price=Decimal("1.10000000"),
                    direction="bullish",
                    level_name="asia_low",
                ),
            ),
            "fvgs": (
                FvgBox(
                    id=5,
                    ts=ts,
                    instrument="EUR_USD",
                    type="bullish",
                    top=Decimal("1.10600000"),
                    bottom=Decimal("1.10400000"),
                    midpoint=Decimal("1.10500000"),
                    sweep_id=3,
                ),
            ),
            "signals": (
                SignalMarker(
                    id=7,
                    ts=ts,
                    instrument="EUR_USD",
                    direction="long",
                    entry=Decimal("1.10500000"),
                    stop=Decimal("1.10200000"),
                    target=Decimal("1.11100000"),
                    status="filled",
                ),
            ),
            "trades": (
                TradeMarker(
                    id=11,
                    signal_id=7,
                    side="long",
                    units=Decimal("1000.0000"),
                    entry_price=Decimal("1.10500000"),
                    entry_ts=ts,
                    exit_price=Decimal("1.11100000"),
                    exit_ts=ts,
                    pnl=Decimal("60.00000000"),
                    r_multiple=Decimal("2.0000"),
                    exit_reason="target",
                ),
            ),
        }
        self.event = EventLogItem(
            id=13,
            ts=ts,
            level="warn",
            module="feed",
            type="heartbeat.stale",
            message="heartbeat stale",
            data={"seconds": 31},
        )

    async def get_status(self) -> StatusSnapshot:
        return self.status

    async def get_levels(self, *, date: date, instrument: str) -> SessionLevelSnapshot | None:
        self.level_requests.append((date, instrument))
        if date == self.levels.date:
            return self.levels
        return None

    async def get_candles(
        self,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> tuple[CandlePoint, ...]:
        self.candle_request = (instrument, start, end)
        return (self.candle,)

    async def get_markers(self, *, date: date, instrument: str) -> dict[str, tuple[object, ...]]:
        return self.markers

    async def get_events(
        self,
        *,
        level: str | None = None,
        limit: int = 100,
    ) -> tuple[EventLogItem, ...]:
        self.events_request = (level, limit)
        return (self.event,)
