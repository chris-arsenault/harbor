import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from harbor_bot.oanda.client import OandaApiError, OandaClient
from harbor_bot.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures" / "oanda"


@pytest.mark.asyncio
async def test_client_sends_auth_and_parses_account_summary() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_load_json("account_summary.json"))

    async with _client(handler) as client:
        summary = await client.get_account_summary()

    assert summary.nav == Decimal("10002.5678")
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(requests[0].url) == "https://api-fxpractice.oanda.com/v3/accounts/abc/summary"
    assert requests[0].headers["authorization"] == "Bearer token"
    assert requests[0].headers["accept-datetime-format"] == "RFC3339"


@pytest.mark.asyncio
async def test_client_requests_account_instruments() -> None:
    seen_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(200, json=_load_json("account_instruments.json"))

    async with _client(handler) as client:
        instruments = await client.get_account_instruments()

    assert seen_path == "/v3/accounts/abc/instruments"
    assert instruments[0].name == "EUR_USD"


@pytest.mark.asyncio
async def test_client_requests_historical_m1_midpoint_candles() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_load_json("candles.json"))

    async with _client(handler) as client:
        candles = await client.get_historical_candles(
            instrument="EUR_USD",
            from_time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
            count=500,
            include_first=False,
        )

    params = requests[0].url.params
    assert requests[0].url.path == "/v3/instruments/EUR_USD/candles"
    assert params["granularity"] == "M1"
    assert params["price"] == "M"
    assert params["count"] == "500"
    assert params["from"] == "2026-01-15T14:30:00Z"
    assert params["includeFirst"] == "false"
    assert candles[0].instrument == "EUR_USD"
    assert candles[0].complete is True


@pytest.mark.asyncio
async def test_client_omits_include_first_without_from_time() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_load_json("candles.json"))

    async with _client(handler) as client:
        await client.get_historical_candles(
            instrument="EUR_USD",
            count=500,
            include_first=True,
        )

    params = requests[0].url.params
    assert params["granularity"] == "M1"
    assert params["price"] == "M"
    assert params["count"] == "500"
    assert "from" not in params
    assert "includeFirst" not in params


@pytest.mark.asyncio
async def test_client_opens_pricing_and_transaction_stream_lines() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(f"{request.url.path}?{request.url.query.decode()}")
        if request.url.path.endswith("/pricing/stream"):
            return httpx.Response(200, content=b'{"type":"HEARTBEAT"}\n{"type":"PRICE"}\n')
        return httpx.Response(200, content=b'{"type":"HEARTBEAT"}\n')

    async with _client(handler) as client:
        pricing = [line async for line in client.stream_pricing_lines(["EUR_USD", "USD_JPY"])]
        transactions = [line async for line in client.stream_transaction_lines()]

    assert paths == [
        "/v3/accounts/abc/pricing/stream?instruments=EUR_USD%2CUSD_JPY",
        "/v3/accounts/abc/transactions/stream?",
    ]
    assert pricing == ['{"type":"HEARTBEAT"}', '{"type":"PRICE"}']
    assert transactions == ['{"type":"HEARTBEAT"}']


@pytest.mark.asyncio
async def test_client_maps_oanda_error_responses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"errorCode": "UNAUTHORIZED", "errorMessage": "missing token"},
        )

    async with _client(handler) as client:
        with pytest.raises(OandaApiError) as error:
            await client.get_account_summary()

    assert error.value.status_code == 401
    assert error.value.error_code == "UNAUTHORIZED"
    assert str(error.value) == "OANDA API error 401 UNAUTHORIZED: missing token"


def test_client_factory_requires_credentials_when_created() -> None:
    settings = Settings()

    with pytest.raises(ValueError, match="OANDA_API_TOKEN"):
        OandaClient.from_settings(settings)


def _client(handler) -> OandaClient:
    return OandaClient.from_settings(
        Settings(OANDA_API_TOKEN="token", OANDA_ACCOUNT_ID="abc"),
        transport=httpx.MockTransport(handler),
    )


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())
