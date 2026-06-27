import asyncio
import copy
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.backfill import (
    HISTORICAL_END_OFFSET_DAYS,
    HISTORICAL_LOOKBACK_DAYS,
    BackfillPlan,
    backfill_status_from_plan,
    build_backfill_plan,
    idle_backfill_status,
    mark_fetch_completed,
    public_backfill_status,
)
from harbor_bot.feed.historical import ingest_historical_candles
from harbor_bot.feed.ingest import SyncReport, sync_universe
from harbor_bot.instruments import RESEARCH_INSTRUMENTS
from harbor_bot.oanda.client import OandaClient
from harbor_bot.persistence.market_repository import (
    get_bid_ask_candle_count,
    get_bulk_candle_coverage,
    get_candle_coverage,
    get_daily_candle_coverage,
)
from harbor_bot.settings import Settings
from harbor_bot.strategy.models import strategy_config_from_defaults

OandaClientFactory = Callable[[Settings], Any]
HistoricalIngestor = Callable[..., Awaitable[int]]
LiveStreamStatusProvider = Callable[[], Mapping[str, Any]]
Clock = Callable[[], datetime]
_UTC_OFFSET = timedelta(0)


@dataclass
class CandleSourceService:
    engine: AsyncEngine
    settings: Settings
    client_factory: OandaClientFactory = OandaClient.from_settings
    historical_ingestor: HistoricalIngestor = ingest_historical_candles
    live_stream_status_provider: LiveStreamStatusProvider | None = None
    clock: Clock = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        self._backfill_task: asyncio.Task[None] | None = None
        self._backfill_status: dict[str, Any] = idle_backfill_status()

    async def get_status(self, *, instrument: str | None = None) -> dict[str, Any]:
        resolved_instrument = instrument or _default_instrument()
        research_instruments = _research_instruments(self.settings)
        async with self.engine.connect() as connection:
            instrument_coverages = await _bulk_coverage(connection, research_instruments)
            coverage = _find_coverage(instrument_coverages, resolved_instrument)
            if coverage is None:
                coverage = await _coverage_with_quality(connection, resolved_instrument)
        return {
            "instrument": resolved_instrument,
            "primary_source": "persisted_candles",
            "granularity": "M1",
            "price_component": "bid_ask_mid",
            "coverage": coverage,
            "instrument_coverages": instrument_coverages,
            "source_methods": ["oanda_historical_import", "oanda_pricing_stream"],
            "research_instruments": list(research_instruments),
            "historical_import": {
                "page_size": self.settings.oanda_historical_candle_page_size,
                "default_count": self.settings.oanda_historical_import_count,
                "request_interval_seconds": (
                    self.settings.oanda_historical_request_interval_seconds
                ),
                "upsert_key": "instrument+timestamp",
                "replaces_existing": False,
            },
            "oanda_historical_import_configured": bool(
                self.settings.oanda_api_token and self.settings.oanda_account_id
            ),
            "live_stream": _live_stream_status(
                settings=self.settings,
                instruments=research_instruments,
                provider=self.live_stream_status_provider,
            ),
        }

    async def import_historical(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        instruments = _payload_instruments(payload, self.settings)
        count = int(payload.get("count") or self.settings.oanda_historical_import_count)
        if count <= 0:
            msg = "count must be positive"
            raise ValueError(msg)
        from_time = _optional_utc_ts(payload.get("from"))
        if from_time is None and count > self.settings.oanda_historical_candle_page_size:
            from_time = datetime.now(UTC) - timedelta(minutes=count)

        results = []
        async with self.client_factory(self.settings) as client:
            for instrument in instruments:
                imported_count = await self.historical_ingestor(
                    client=client,
                    engine=self.engine,
                    instrument=instrument,
                    from_time=from_time,
                    count=count,
                    page_size=self.settings.oanda_historical_candle_page_size,
                    request_interval_seconds=(
                        self.settings.oanda_historical_request_interval_seconds
                    ),
                    include_first=from_time is None,
                )
                status = await self.get_status(instrument=instrument)
                results.append(
                    {
                        "instrument": instrument,
                        "requested_count": count,
                        "imported_count": imported_count,
                        "coverage": status["coverage"],
                    }
                )

        if len(results) == 1:
            return {
                "status": "completed",
                "source": "oanda_historical_import",
                "instrument": results[0]["instrument"],
                "requested_count": count,
                "imported_count": results[0]["imported_count"],
                "from": _iso_or_none(from_time),
                "coverage": results[0]["coverage"],
            }

        return {
            "status": "completed",
            "source": "oanda_historical_import",
            "instrument": "research_universe",
            "instruments": [result["instrument"] for result in results],
            "requested_count": count * len(results),
            "imported_count": sum(int(result["imported_count"]) for result in results),
            "from": _iso_or_none(from_time),
            "coverage": results[0]["coverage"],
            "results": results,
        }

    async def sync(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Gap-aware sourcing: fetch only the candles missing from a trailing
        window for each instrument (see harbor_bot.feed.ingest)."""
        days = int(payload.get("days") or 180)
        if days <= 0:
            msg = "days must be positive"
            raise ValueError(msg)
        repair = bool(payload.get("repair"))
        instruments = _payload_instruments(payload, self.settings)
        reports = await sync_universe(
            settings=self.settings,
            engine=self.engine,
            days=days,
            instruments=instruments,
            repair=repair,
            client_factory=self.client_factory,
        )
        return {
            "status": "completed",
            "days": days,
            "repair": repair,
            "reports": [_report_jsonable(report) for report in reports],
        }

    async def get_backfill_status(self) -> dict[str, Any]:
        return public_backfill_status(copy.deepcopy(self._backfill_status))

    async def start_backfill(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self._backfill_task is not None and not self._backfill_task.done():
            return await self.get_backfill_status()
        if not (self.settings.oanda_api_token and self.settings.oanda_account_id):
            msg = "OANDA_API_TOKEN and OANDA_ACCOUNT_ID are required to source candles"
            raise ValueError(msg)

        instruments = _payload_instruments(payload, self.settings)
        moment = self.clock().astimezone(UTC)
        plan = await self._build_backfill_plan(instruments=instruments, moment=moment)
        self._backfill_status = backfill_status_from_plan(plan, job_id=uuid4().hex)
        self._backfill_task = asyncio.create_task(self._run_backfill_worker(plan))
        return await self.get_backfill_status()

    async def _build_backfill_plan(
        self, *, instruments: tuple[str, ...], moment: datetime
    ) -> BackfillPlan:
        historical_start = (moment - timedelta(days=HISTORICAL_LOOKBACK_DAYS)).date()
        historical_end = (moment - timedelta(days=HISTORICAL_END_OFFSET_DAYS)).date()
        async with self.engine.connect() as connection:
            coverages = {
                row["instrument"]: row
                for row in await get_bulk_candle_coverage(connection, instruments=instruments)
            }
            daily_rows = await get_daily_candle_coverage(
                connection,
                instruments=instruments,
                start=historical_start,
                end=historical_end,
            )
        daily_coverages: dict[str, dict[date, dict[str, Any]]] = {
            instrument: {} for instrument in instruments
        }
        for row in daily_rows:
            daily_coverages.setdefault(row["instrument"], {})[row["day"]] = row
        return build_backfill_plan(
            moment=moment,
            instruments=instruments,
            coverages=coverages,
            daily_coverages=daily_coverages,
        )

    async def _run_backfill_worker(self, plan: BackfillPlan) -> None:
        try:
            async with self.client_factory(self.settings) as client:
                for fetch in plan.fetches:
                    self._backfill_status["status"] = "running"
                    self._backfill_status["current_instrument"] = fetch.instrument
                    imported = await self.historical_ingestor(
                        client=client,
                        engine=self.engine,
                        instrument=fetch.instrument,
                        from_time=fetch.from_time,
                        to_time=fetch.to_time,
                        page_size=self.settings.oanda_historical_candle_page_size,
                        request_interval_seconds=(
                            self.settings.oanda_historical_request_interval_seconds
                        ),
                        include_first=fetch.include_first,
                        replace_existing=False,
                    )
                    mark_fetch_completed(self._backfill_status, fetch, imported=imported)
            self._backfill_status["status"] = "completed"
            self._backfill_status["current_instrument"] = None
            self._backfill_status["finished_at"] = _iso_or_none(self.clock().astimezone(UTC))
        except Exception as exc:  # pragma: no cover - exercised through live worker failures
            self._backfill_status["status"] = "failed"
            self._backfill_status["error"] = str(exc)
            self._backfill_status["finished_at"] = _iso_or_none(self.clock().astimezone(UTC))


def _report_jsonable(report: SyncReport) -> dict[str, Any]:
    return {
        "instrument": report.instrument,
        "imported": report.imported,
        "candle_count": report.candle_count,
        "from": _iso_or_none(report.coverage_from),
        "to": _iso_or_none(report.coverage_to),
    }


async def _coverage_with_quality(connection: AsyncConnection, instrument: str) -> dict[str, Any]:
    coverage = _jsonable_coverage(await get_candle_coverage(connection, instrument=instrument))
    coverage["bid_ask_count"] = await get_bid_ask_candle_count(connection, instrument=instrument)
    return coverage


async def _bulk_coverage(
    connection: AsyncConnection, instruments: tuple[str, ...]
) -> list[dict[str, Any]]:
    rows = await get_bulk_candle_coverage(connection, instruments=instruments)
    return [_jsonable_coverage_with_quality(row) for row in rows]


def _find_coverage(coverages: list[dict[str, Any]], instrument: str) -> dict[str, Any] | None:
    for coverage in coverages:
        if coverage.get("instrument") == instrument:
            return coverage
    return None


def _jsonable_coverage_with_quality(coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        "instrument": coverage["instrument"],
        "candle_count": int(coverage["candle_count"]),
        "from": _iso_or_none(coverage["from"]),
        "to": _iso_or_none(coverage["to"]),
        "bid_ask_count": int(coverage.get("bid_ask_count", 0)),
    }


def _default_instrument() -> str:
    return strategy_config_from_defaults(load_default_config()).instrument


def _payload_instruments(payload: Mapping[str, Any], settings: Settings) -> tuple[str, ...]:
    raw_instruments = payload.get("instruments")
    if isinstance(raw_instruments, list):
        instruments = tuple(str(value).strip().upper() for value in raw_instruments if value)
        if not instruments:
            msg = "instruments cannot be empty"
            raise ValueError(msg)
        return instruments

    raw_instrument = payload.get("instrument")
    if raw_instrument in (None, "", "research_universe"):
        return _research_instruments(settings)
    return (str(raw_instrument).strip().upper(),)


def _research_instruments(settings: Settings) -> tuple[str, ...]:
    return settings.research_instruments or RESEARCH_INSTRUMENTS


def _optional_utc_ts(raw: Any) -> datetime | None:
    if raw in (None, ""):
        return None
    value = str(raw)
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None or ts.utcoffset() != _UTC_OFFSET:
        msg = "from must be a timezone-aware UTC timestamp"
        raise ValueError(msg)
    return ts.astimezone(UTC)


def _jsonable_coverage(coverage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "instrument": coverage["instrument"],
        "candle_count": int(coverage["candle_count"]),
        "from": _iso_or_none(coverage["from"]),
        "to": _iso_or_none(coverage["to"]),
    }


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _live_stream_status(
    *,
    settings: Settings,
    instruments: tuple[str, ...],
    provider: LiveStreamStatusProvider | None,
) -> dict[str, Any]:
    configured = bool(settings.oanda_api_token and settings.oanda_account_id)
    runtime = dict(provider()) if provider is not None else {}
    return {
        "configured": configured,
        "enabled": bool(settings.oanda_pricing_stream_enabled),
        "running": bool(runtime.get("running", False)),
        "state": str(runtime.get("state", "disabled")),
        "starts_on_api_boot": bool(settings.oanda_pricing_stream_enabled and configured),
        "paper_forward_on_closed_candle": True,
        "instruments": list(instruments),
        "heartbeat_timeout_seconds": settings.oanda_stream_heartbeat_timeout_seconds,
        "reconnect_initial_seconds": settings.oanda_reconnect_initial_seconds,
        "reconnect_max_seconds": settings.oanda_reconnect_max_seconds,
        "last_started_at": _iso_or_none(runtime.get("last_started_at")),
        "last_stopped_at": _iso_or_none(runtime.get("last_stopped_at")),
        "last_error": runtime.get("last_error"),
    }
