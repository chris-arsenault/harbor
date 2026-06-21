from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.historical import ingest_historical_candles
from harbor_bot.instruments import RESEARCH_INSTRUMENTS
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
            "research_instruments": list(_research_instruments(self.settings)),
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
