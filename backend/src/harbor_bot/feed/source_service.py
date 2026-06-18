from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.historical import ingest_historical_candles
from harbor_bot.oanda.client import OandaClient
from harbor_bot.persistence.market_repository import get_candle_coverage
from harbor_bot.settings import Settings
from harbor_bot.strategy.models import strategy_config_from_defaults

OandaClientFactory = Callable[[Settings], Any]
HistoricalIngestor = Callable[..., Awaitable[int]]
_UTC_OFFSET = timedelta(0)


@dataclass(frozen=True)
class CandleSourceService:
    engine: AsyncEngine
    settings: Settings
    client_factory: OandaClientFactory = OandaClient.from_settings
    historical_ingestor: HistoricalIngestor = ingest_historical_candles

    async def get_status(self, *, instrument: str | None = None) -> dict[str, Any]:
        resolved_instrument = instrument or _default_instrument()
        async with self.engine.connect() as connection:
            coverage = await get_candle_coverage(connection, instrument=resolved_instrument)
        return {
            "instrument": resolved_instrument,
            "primary_source": "persisted_candles",
            "granularity": "M1",
            "price_component": "midpoint",
            "coverage": _jsonable_coverage(coverage),
            "source_methods": ["oanda_historical_import", "oanda_pricing_stream"],
            "oanda_historical_import_configured": bool(
                self.settings.oanda_api_token and self.settings.oanda_account_id
            ),
        }

    async def import_historical(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        instrument = str(payload.get("instrument") or _default_instrument())
        count = int(payload.get("count") or self.settings.oanda_historical_candle_page_size)
        if count <= 0:
            msg = "count must be positive"
            raise ValueError(msg)
        from_time = _optional_utc_ts(payload.get("from"))

        async with self.client_factory(self.settings) as client:
            imported_count = await self.historical_ingestor(
                client=client,
                engine=self.engine,
                instrument=instrument,
                from_time=from_time,
                count=count,
                page_size=self.settings.oanda_historical_candle_page_size,
                include_first=from_time is None,
            )

        status = await self.get_status(instrument=instrument)
        return {
            "status": "completed",
            "source": "oanda_historical_import",
            "instrument": instrument,
            "requested_count": count,
            "imported_count": imported_count,
            "coverage": status["coverage"],
        }


def _default_instrument() -> str:
    return strategy_config_from_defaults(load_default_config()).instrument


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
