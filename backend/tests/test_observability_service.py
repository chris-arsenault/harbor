from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.observability.service import ObservabilityService
from harbor_bot.settings import Settings

DEFAULT_LEVELS = object()


def test_status_is_read_only_and_uses_persisted_equity_and_trade_summary() -> None:
    repo = FakeObservabilityRepository()
    service = ObservabilityService(
        engine=FakeEngine(),
        settings=Settings(OANDA_ENV="practice"),
        repository=repo,
        clock=lambda: datetime(2026, 1, 15, 14, 45, tzinfo=UTC),
    )

    status = run(service.get_status())

    assert status.bot_state == "IDLE"
    assert status.session_phase == "ny_trade"
    assert status.connection_health == "unknown"
    assert status.mode == "practice"
    assert status.trading_enabled is False
    assert status.trading_controls_available is False
    assert status.kill_switch_state == "armed"
    assert status.day_pnl == Decimal("60.00000000")
    assert status.account_nav == Decimal("10060.00000000")
    assert status.last_heartbeat == datetime(2026, 1, 15, 14, 31, tzinfo=UTC)


def test_service_maps_persisted_facts_to_dashboard_models() -> None:
    repo = FakeObservabilityRepository()
    service = ObservabilityService(
        engine=FakeEngine(),
        settings=Settings(OANDA_ENV="practice"),
        repository=repo,
        clock=lambda: datetime(2026, 1, 15, 14, 45, tzinfo=UTC),
    )
    start = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)
    end = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)

    dashboard = run(
        service.get_dashboard(
            date=date(2026, 1, 15),
            instrument="EUR_USD",
            start=start,
            end=end,
            events_limit=10,
        )
    )

    assert dashboard.status.session_phase == "ny_trade"
    assert dashboard.levels is not None
    assert dashboard.levels.swept_levels == ("asia_low",)
    assert dashboard.levels.taken_levels == ()
    assert dashboard.candles[0].close == Decimal("1.10400000")
    assert dashboard.markers[0].kind == "sweep"
    assert dashboard.markers[0].label == "asia_low swept"
    assert dashboard.fvgs[0].sweep_id == 3
    assert dashboard.signals[0].status == "filled"
    assert dashboard.trades[0].exit_reason == "target"
    assert dashboard.events[0].data == {"seconds": 31}
    assert repo.candle_range == ("EUR_USD", start, end)


def test_missing_levels_return_none_without_recomputing_strategy_facts() -> None:
    repo = FakeObservabilityRepository(levels=None, sweeps=())
    service = ObservabilityService(
        engine=FakeEngine(),
        settings=Settings(OANDA_ENV="practice"),
        repository=repo,
        clock=lambda: datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
    )

    assert run(service.get_levels(date=date(2026, 1, 15), instrument="EUR_USD")) is None


def run(awaitable: Any) -> Any:
    import asyncio

    return asyncio.run(awaitable)


class _FakeMappings:
    @staticmethod
    def one() -> dict[str, None]:
        return {"high": None, "low": None}


class _FakeResult:
    @staticmethod
    def mappings() -> _FakeMappings:
        return _FakeMappings()


class FakeConnection:
    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def execute(self, *_args: object, **_kwargs: object) -> _FakeResult:
        return _FakeResult()


class FakeEngine:
    def connect(self) -> FakeConnection:
        return FakeConnection()


class FakeObservabilityRepository:
    def __init__(
        self,
        *,
        levels: dict[str, Any] | None | object = DEFAULT_LEVELS,
        sweeps: tuple[dict[str, Any], ...] | None = None,
    ) -> None:
        ts = datetime(2026, 1, 15, 14, 31, tzinfo=UTC)
        self.candle_range: tuple[str, datetime, datetime] | None = None
        self.levels = levels
        if levels is DEFAULT_LEVELS:
            self.levels = {
                "date": date(2026, 1, 15),
                "instrument": "EUR_USD",
                "asia_high": Decimal("1.11000000"),
                "asia_low": Decimal("1.10000000"),
                "london_high": Decimal("1.11500000"),
                "london_low": Decimal("1.10500000"),
            }
        self.sweeps = sweeps
        if sweeps is None:
            self.sweeps = (
                {
                    "id": 3,
                    "ts": ts,
                    "instrument": "EUR_USD",
                    "level_name": "asia_low",
                    "level_price": Decimal("1.10000000"),
                    "direction": "bullish",
                    "sweep_extreme": Decimal("1.09900000"),
                },
            )
        self.fvgs = (
            {
                "id": 5,
                "ts": ts,
                "instrument": "EUR_USD",
                "type": "bullish",
                "top": Decimal("1.10600000"),
                "bottom": Decimal("1.10400000"),
                "midpoint": Decimal("1.10500000"),
                "sweep_id": 3,
            },
        )
        self.signals = (
            {
                "id": 7,
                "ts": ts,
                "instrument": "EUR_USD",
                "direction": "long",
                "entry": Decimal("1.10500000"),
                "stop": Decimal("1.10200000"),
                "target": Decimal("1.11100000"),
                "risk": Decimal("0.00300000"),
                "rr": Decimal("2.0000"),
                "status": "filled",
            },
        )
        self.trades = (
            {
                "id": 11,
                "signal_id": 7,
                "broker_trade_id": "broker-1",
                "side": "long",
                "units": Decimal("1000.0000"),
                "entry_price": Decimal("1.10500000"),
                "entry_ts": ts,
                "exit_price": Decimal("1.11100000"),
                "exit_ts": ts,
                "pnl": Decimal("60.00000000"),
                "r_multiple": Decimal("2.0000"),
                "exit_reason": "target",
            },
        )
        self.events = (
            {
                "id": 13,
                "ts": ts,
                "level": "warn",
                "module": "feed",
                "type": "heartbeat.stale",
                "message": "heartbeat stale",
                "data_json": {"seconds": 31},
            },
        )
        self.latest_equity = {
            "id": 17,
            "ts": ts,
            "nav": Decimal("10060.00000000"),
            "balance": Decimal("10060.00000000"),
            "unrealized_pnl": Decimal("0E-8"),
            "open_positions": 0,
        }
        self.summary = {"realized_pnl": Decimal("60.00000000"), "trade_count": 1}

    async def get_latest_equity_snapshot(self, _connection: object) -> dict[str, Any]:
        return self.latest_equity

    async def get_day_trade_summary(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> dict[str, Any]:
        assert date == date.__class__(2026, 1, 15)
        assert instrument == "EUR_USD"
        return self.summary

    async def get_session_levels_for_date(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> dict[str, Any] | None:
        assert instrument == "EUR_USD"
        return self.levels

    async def list_candles_for_range(
        self,
        _connection: object,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        self.candle_range = (instrument, start, end)
        return [
            {
                "instrument": instrument,
                "ts": start,
                "o": Decimal("1.10000000"),
                "h": Decimal("1.10500000"),
                "l": Decimal("1.09900000"),
                "c": Decimal("1.10400000"),
                "volume": 100,
                "complete": True,
            }
        ]

    async def list_sweeps_for_date(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> tuple[dict[str, Any], ...]:
        return self.sweeps or ()

    async def list_fvgs_for_date(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> tuple[dict[str, Any], ...]:
        return self.fvgs

    async def list_signals_for_date(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> tuple[dict[str, Any], ...]:
        return self.signals

    async def list_trades_for_date(
        self,
        _connection: object,
        *,
        date: date,
        instrument: str,
    ) -> tuple[dict[str, Any], ...]:
        return self.trades

    async def list_events_for_dashboard(
        self,
        _connection: object,
        *,
        level: str | None = None,
        limit: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        return self.events
