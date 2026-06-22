from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.config.defaults import load_default_config
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
)
from harbor_bot.persistence import event_repository, observability_repository
from harbor_bot.persistence.market_repository import get_prior_day_range
from harbor_bot.settings import Settings
from harbor_bot.strategy.models import StrategyConfig, strategy_config_from_defaults
from harbor_bot.strategy.sessions import session_windows_for_date

DEFAULT_EVENTS_LIMIT = 100


class ObservabilityService:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        settings: Settings,
        repository: Any = observability_repository,
        event_store: Any | None = None,
        clock: Callable[[], datetime] | None = None,
        strategy_config: StrategyConfig | None = None,
        execution_status_provider: Any | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._repository = repository
        self._event_store = event_store
        self._clock = clock or (lambda: datetime.now(tz=UTC))
        self._strategy_config = strategy_config or strategy_config_from_defaults(
            load_default_config()
        )
        self._execution_status_provider = execution_status_provider

    async def get_status(
        self,
        *,
        date: date | None = None,
        instrument: str | None = None,
    ) -> StatusSnapshot:
        trading_date = date or self._current_trading_date()
        target_instrument = instrument or self._strategy_config.instrument
        async with self._engine.connect() as connection:
            latest_equity = await self._repository.get_latest_equity_snapshot(connection)
            trade_summary = await self._repository.get_day_trade_summary(
                connection,
                date=trading_date,
                instrument=target_instrument,
            )

        execution_overlay: dict[str, Any] = {}
        if self._execution_status_provider is not None:
            execution_overlay = await self._execution_status_provider.get_status_overlay()

        return StatusSnapshot(
            bot_state="IDLE",
            session_phase=self._session_phase(),
            connection_health="unknown",
            mode=self._settings.oanda_env,
            trading_enabled=bool(execution_overlay.get("trading_enabled", False)),
            trading_controls_available=bool(
                execution_overlay.get("trading_controls_available", False)
            ),
            kill_switch_state=str(execution_overlay.get("kill_switch_state", "armed")),
            day_pnl=trade_summary["realized_pnl"],
            trades_today=trade_summary["trade_count"],
            max_trades_per_day=self._strategy_config.max_trades_per_day,
            account_nav=latest_equity["nav"] if latest_equity else None,
            open_positions=int(execution_overlay["open_positions"])
            if "open_positions" in execution_overlay
            else latest_equity["open_positions"]
            if latest_equity
            else None,
            unrealized_pnl=latest_equity["unrealized_pnl"] if latest_equity else None,
            last_heartbeat=latest_equity["ts"] if latest_equity else None,
            promoted_variant=execution_overlay.get("promoted_variant"),
            reconciliation_state=execution_overlay.get("reconciliation_state"),
            open_position=execution_overlay.get("open_position"),
            notifier_state=execution_overlay.get("notifier_state", _default_notifier_state()),
            deployment=execution_overlay.get("deployment", _deployment_facts()),
        )

    async def get_levels(
        self,
        *,
        date: date,
        instrument: str,
    ) -> SessionLevelSnapshot | None:
        async with self._engine.connect() as connection:
            row = await self._repository.get_session_levels_for_date(
                connection,
                date=date,
                instrument=instrument,
            )
            if row is None:
                return None
            sweeps = await self._repository.list_sweeps_for_date(
                connection,
                date=date,
                instrument=instrument,
            )
            prior_day = await get_prior_day_range(connection, instrument=instrument, day=date)

        return SessionLevelSnapshot(
            date=row["date"],
            instrument=row["instrument"],
            asia_high=row["asia_high"],
            asia_low=row["asia_low"],
            london_high=row["london_high"],
            london_low=row["london_low"],
            prev_day_high=prior_day["high"] if prior_day else None,
            prev_day_low=prior_day["low"] if prior_day else None,
            swept_levels=_ordered_level_names(sweeps),
            taken_levels=(),
        )

    async def get_candles(
        self,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
    ) -> tuple[CandlePoint, ...]:
        async with self._engine.connect() as connection:
            rows = await self._repository.list_candles_for_range(
                connection,
                instrument=instrument,
                start=start,
                end=end,
            )
        return tuple(
            CandlePoint(
                instrument=row["instrument"],
                ts=row["ts"],
                open=row["o"],
                high=row["h"],
                low=row["l"],
                close=row["c"],
                volume=row["volume"],
                complete=row["complete"],
            )
            for row in rows
        )

    async def get_markers(self, *, date: date, instrument: str) -> dict[str, tuple[Any, ...]]:
        async with self._engine.connect() as connection:
            sweeps = await self._repository.list_sweeps_for_date(
                connection,
                date=date,
                instrument=instrument,
            )
            fvgs = await self._repository.list_fvgs_for_date(
                connection,
                date=date,
                instrument=instrument,
            )
            signals = await self._repository.list_signals_for_date(
                connection,
                date=date,
                instrument=instrument,
            )
            trades = await self._repository.list_trades_for_date(
                connection,
                date=date,
                instrument=instrument,
            )

        return {
            "markers": tuple(_sweep_marker(row) for row in sweeps),
            "fvgs": tuple(_fvg_box(row) for row in fvgs),
            "signals": tuple(_signal_marker(row) for row in signals),
            "trades": tuple(_trade_marker(row) for row in trades),
        }

    async def get_events(
        self,
        *,
        level: str | None = None,
        module: str | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = DEFAULT_EVENTS_LIMIT,
    ) -> tuple[EventLogItem, ...]:
        async with self._engine.connect() as connection:
            if self._uses_dashboard_event_repository(
                module=module,
                event_type=event_type,
                start=start,
                end=end,
            ):
                rows = await self._repository.list_events_for_dashboard(
                    connection,
                    level=level,
                    limit=limit,
                )
            else:
                event_store = self._event_store or event_repository
                rows = await event_store.list_events(
                    connection,
                    level=level,
                    module=module,
                    event_type=event_type,
                    start=start,
                    end=end,
                    limit=limit,
                    descending=True,
                )
        return tuple(_event(row) for row in rows)

    def _uses_dashboard_event_repository(
        self,
        *,
        module: str | None,
        event_type: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> bool:
        return (
            self._event_store is None
            and module is None
            and event_type is None
            and start is None
            and end is None
            and hasattr(self._repository, "list_events_for_dashboard")
        )

    async def emit_daily_summary_event(
        self,
        *,
        date: date | None = None,
        instrument: str | None = None,
    ) -> EventLogItem:
        trading_date = date or self._current_trading_date()
        target_instrument = instrument or self._strategy_config.instrument
        status = await self.get_status(date=trading_date, instrument=target_instrument)
        ts = self._now_utc()
        summary = {
            "date": trading_date.isoformat(),
            "instrument": target_instrument,
            "day_pnl": str(status.day_pnl),
            "trades_today": status.trades_today,
            "account_nav": str(status.account_nav) if status.account_nav is not None else None,
            "open_positions": status.open_positions,
            "unrealized_pnl": str(status.unrealized_pnl)
            if status.unrealized_pnl is not None
            else None,
            "promoted_variant": status.promoted_variant,
        }
        async with self._engine.begin() as connection:
            event_id = await self._event_store.append_daily_summary_event(
                connection,
                ts=ts,
                summary=summary,
            )
        return EventLogItem(
            id=event_id,
            ts=ts,
            level="info",
            module="daily",
            type="daily_summary",
            message="daily summary",
            data=summary,
        )

    async def get_dashboard(
        self,
        *,
        date: date,
        instrument: str,
        start: datetime,
        end: datetime,
        events_limit: int = DEFAULT_EVENTS_LIMIT,
    ) -> DashboardSnapshot:
        status = await self.get_status(date=date, instrument=instrument)
        levels = await self.get_levels(date=date, instrument=instrument)
        candles = await self.get_candles(instrument=instrument, start=start, end=end)
        marker_payload = await self.get_markers(date=date, instrument=instrument)
        events = await self.get_events(limit=events_limit)

        return DashboardSnapshot(
            status=status,
            levels=levels,
            candles=candles,
            markers=marker_payload["markers"],
            fvgs=marker_payload["fvgs"],
            signals=marker_payload["signals"],
            trades=marker_payload["trades"],
            events=events,
        )

    def _current_trading_date(self) -> date:
        now = self._now_utc()
        return now.astimezone(ZoneInfo(self._strategy_config.timezone)).date()

    def _session_phase(self) -> str:
        now = self._now_utc()
        local_date = now.astimezone(ZoneInfo(self._strategy_config.timezone)).date()
        for candidate_date in (local_date, local_date + timedelta(days=1)):
            windows = session_windows_for_date(candidate_date, self._strategy_config)
            if windows.asia.contains(now):
                return "asia"
            if windows.london.contains(now):
                return "london"
            if windows.ny_trade.contains(now):
                return "ny_trade"
        return "closed"

    def _now_utc(self) -> datetime:
        return self._clock().astimezone(UTC)


def _ordered_level_names(rows: Any) -> tuple[str, ...]:
    names: list[str] = []
    for row in rows:
        level_name = row["level_name"]
        if level_name not in names:
            names.append(level_name)
    return tuple(names)


def _default_notifier_state() -> dict[str, Any]:
    return {"ntfy_enabled": False, "telegram_enabled": False}


def _deployment_facts() -> dict[str, Any]:
    return {
        "access": "LAN",
        "frontend_url": "http://192.168.66.3:30091/",
        "public_route": False,
        "health_path": "/health",
        "readiness_path": "/ready",
        "api_path": "/api",
        "websocket_path": "/ws",
    }


def _sweep_marker(row: dict[str, Any]) -> ChartMarker:
    level_name = row["level_name"]
    return ChartMarker(
        kind="sweep",
        ts=row["ts"],
        instrument=row["instrument"],
        label=f"{level_name} swept",
        price=row["level_price"],
        direction=row["direction"],
        level_name=level_name,
    )


def _fvg_box(row: dict[str, Any]) -> FvgBox:
    return FvgBox(
        id=row["id"],
        ts=row["ts"],
        instrument=row["instrument"],
        type=row["type"],
        top=row["top"],
        bottom=row["bottom"],
        midpoint=row["midpoint"],
        sweep_id=row["sweep_id"],
    )


def _signal_marker(row: dict[str, Any]) -> SignalMarker:
    return SignalMarker(
        id=row["id"],
        ts=row["ts"],
        instrument=row["instrument"],
        direction=row["direction"],
        entry=row["entry"],
        stop=row["stop"],
        target=row["target"],
        status=row["status"],
    )


def _trade_marker(row: dict[str, Any]) -> TradeMarker:
    return TradeMarker(
        id=row["id"],
        signal_id=row["signal_id"],
        side=row["side"],
        units=row["units"],
        entry_price=row["entry_price"],
        entry_ts=row["entry_ts"],
        exit_price=row["exit_price"],
        exit_ts=row["exit_ts"],
        pnl=row["pnl"],
        r_multiple=row["r_multiple"],
        exit_reason=row["exit_reason"],
    )


def _event(row: dict[str, Any]) -> EventLogItem:
    return EventLogItem(
        id=row["id"],
        ts=row["ts"],
        level=row["level"],
        module=row["module"],
        type=row["type"],
        message=row["message"],
        data=row["data_json"],
    )
