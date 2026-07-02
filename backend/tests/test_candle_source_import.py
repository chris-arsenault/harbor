import asyncio
from typing import Any

from harbor_bot.feed.source_service import CandleSourceService, _import_instruments
from harbor_bot.instruments import (
    IMPORT_INSTRUMENTS,
    RESEARCH_INSTRUMENTS,
    RISK_PROXY_INSTRUMENTS,
)
from harbor_bot.oanda.client import OandaApiError
from harbor_bot.settings import Settings


class _FakeClient:
    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


def test_import_universe_extends_research_instruments_with_risk_proxies() -> None:
    assert (*RESEARCH_INSTRUMENTS, *RISK_PROXY_INSTRUMENTS) == IMPORT_INSTRUMENTS
    assert "BTC_USD" in _import_instruments(Settings())
    # Deduped and stable when settings override the research set.
    resolved = _import_instruments(Settings(HARBOR_RESEARCH_INSTRUMENTS="EUR_USD,BTC_USD"))
    assert resolved.count("BTC_USD") == 1


def test_universe_import_continues_past_unsupported_instrument() -> None:
    ingested: list[str] = []

    async def ingestor(*, instrument: str, **kwargs: Any) -> int:
        ingested.append(instrument)
        if instrument == "BTC_USD":
            raise OandaApiError(
                status_code=400,
                error_code="INSTRUMENT_UNKNOWN",
                message="instrument is not tradeable",
            )
        return 5

    service = CandleSourceService(
        engine=None,  # type: ignore[arg-type] - never touched by the stubbed paths
        settings=Settings(),
        client_factory=lambda settings: _FakeClient(),
        historical_ingestor=ingestor,
    )

    async def fake_status(*, instrument: str | None = None) -> dict[str, Any]:
        return {"coverage": {"instrument": instrument, "candle_count": 5}}

    service.get_status = fake_status  # type: ignore[method-assign]

    result = asyncio.run(
        service.import_historical({"instruments": ["EUR_USD", "BTC_USD", "GBP_USD"], "count": 10})
    )

    assert ingested == ["EUR_USD", "BTC_USD", "GBP_USD"]
    by_instrument = {row["instrument"]: row for row in result["results"]}
    assert by_instrument["EUR_USD"]["imported_count"] == 5
    assert by_instrument["GBP_USD"]["imported_count"] == 5
    assert by_instrument["BTC_USD"]["imported_count"] == 0
    assert "not tradeable" in by_instrument["BTC_USD"]["error"]
    assert result["imported_count"] == 10


def test_single_instrument_import_still_raises_on_api_error() -> None:
    async def ingestor(*, instrument: str, **kwargs: Any) -> int:
        raise OandaApiError(
            status_code=400,
            error_code="INSTRUMENT_UNKNOWN",
            message="instrument is not tradeable",
        )

    service = CandleSourceService(
        engine=None,  # type: ignore[arg-type]
        settings=Settings(),
        client_factory=lambda settings: _FakeClient(),
        historical_ingestor=ingestor,
    )

    try:
        asyncio.run(service.import_historical({"instrument": "BTC_USD", "count": 10}))
    except OandaApiError as exc:
        assert exc.status_code == 400
    else:  # pragma: no cover - failure path
        raise AssertionError("single-instrument import error was swallowed")
