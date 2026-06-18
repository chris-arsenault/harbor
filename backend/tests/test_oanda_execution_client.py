import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from harbor_bot.oanda.client import OandaClient
from harbor_bot.oanda.types import ClientExtensions, MarketOrderRequest
from harbor_bot.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures" / "oanda"


@pytest.mark.asyncio
async def test_client_creates_market_order_with_attached_brackets() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json=_load_json("order_create_market_bracket.json"))

    async with _client(handler) as client:
        result = await client.create_market_order_with_bracket(
            MarketOrderRequest(
                instrument="EUR_USD",
                units=1000,
                stop_loss_price=Decimal("1.08000"),
                take_profit_price=Decimal("1.11000"),
                client_extensions=ClientExtensions(
                    client_id="harbor-signal-20260115T143000",
                    tag="harbor-practice",
                    comment="promoted variant practice execution",
                ),
            )
        )

    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == "https://api-fxpractice.oanda.com/v3/accounts/abc/orders"
    assert json.loads(requests[0].content) == {
        "order": {
            "clientExtensions": {
                "comment": "promoted variant practice execution",
                "id": "harbor-signal-20260115T143000",
                "tag": "harbor-practice",
            },
            "instrument": "EUR_USD",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": "1.08000", "timeInForce": "GTC"},
            "takeProfitOnFill": {"price": "1.11000", "timeInForce": "GTC"},
            "timeInForce": "FOK",
            "type": "MARKET",
            "units": "1000",
        }
    }
    assert result.order_id == "9100"
    assert result.fill_transaction_id == "9101"
    assert result.trade_id == "7001"
    assert result.instrument == "EUR_USD"
    assert result.units == Decimal("1000")
    assert result.price == Decimal("1.09020")
    assert result.last_transaction_id == "9103"
    assert result.related_transaction_ids == ("9100", "9101", "9102", "9103")


@pytest.mark.asyncio
async def test_client_closes_trade() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=_load_json("trade_close.json"))

    async with _client(handler) as client:
        result = await client.close_trade(trade_id="7001")

    assert seen_request is not None
    assert seen_request.method == "PUT"
    assert seen_request.url.path == "/v3/accounts/abc/trades/7001/close"
    assert json.loads(seen_request.content) == {"units": "ALL"}
    assert result.trade_id == "7001"
    assert result.close_transaction_ids == ("9201",)
    assert result.last_transaction_id == "9201"


@pytest.mark.asyncio
async def test_client_closes_open_position() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=_load_json("position_close.json"))

    async with _client(handler) as client:
        result = await client.close_position(instrument="EUR_USD", long_units="ALL")

    assert seen_request is not None
    assert seen_request.method == "PUT"
    assert seen_request.url.path == "/v3/accounts/abc/positions/EUR_USD/close"
    assert json.loads(seen_request.content) == {"longUnits": "ALL"}
    assert result.instrument == "EUR_USD"
    assert result.close_transaction_ids == ("9301",)
    assert result.last_transaction_id == "9301"


@pytest.mark.asyncio
async def test_client_lists_open_trades_and_positions() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/openTrades"):
            return httpx.Response(200, json=_load_json("open_trades.json"))
        return httpx.Response(200, json=_load_json("open_positions.json"))

    async with _client(handler) as client:
        trades = await client.list_open_trades()
        positions = await client.list_open_positions()

    assert paths == [
        "/v3/accounts/abc/openTrades",
        "/v3/accounts/abc/openPositions",
    ]
    assert trades[0].trade_id == "7001"
    assert trades[0].instrument == "EUR_USD"
    assert trades[0].current_units == Decimal("1000")
    assert trades[0].price == Decimal("1.09020")
    assert positions[0].instrument == "EUR_USD"
    assert positions[0].long_units == Decimal("1000")
    assert positions[0].short_units == Decimal("0")


@pytest.mark.asyncio
async def test_client_reads_transactions_since_checkpoint() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json=_load_json("transactions_since.json"))

    async with _client(handler) as client:
        page = await client.get_transactions_since(transaction_id="9099")

    assert seen_request is not None
    assert seen_request.method == "GET"
    assert seen_request.url.path == "/v3/accounts/abc/transactions/sinceid"
    assert seen_request.url.params["id"] == "9099"
    assert page.last_transaction_id == "9201"
    assert [transaction.transaction_id for transaction in page.transactions] == ["9101", "9201"]
    assert page.transactions[0].raw["type"] == "ORDER_FILL"


def _client(handler) -> OandaClient:
    return OandaClient.from_settings(
        Settings(OANDA_API_TOKEN="token", OANDA_ACCOUNT_ID="abc"),
        transport=httpx.MockTransport(handler),
    )


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())
