import json
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx

from harbor_bot.oanda.types import (
    AccountSummary,
    BookSnapshot,
    HistoricalCandle,
    Instrument,
    MarketOrderRequest,
    OpenPosition,
    OpenTrade,
    OrderCreateResult,
    PositionCloseResult,
    TradeCloseResult,
    TransactionHistoryPage,
    market_order_request_payload,
    parse_account_summary,
    parse_historical_candles,
    parse_instruments,
    parse_open_positions,
    parse_open_trades,
    parse_order_book,
    parse_order_create_result,
    parse_position_book,
    parse_position_close_result,
    parse_trade_close_result,
    parse_transaction_history_page,
)
from harbor_bot.settings import Settings


class OandaApiError(RuntimeError):
    def __init__(self, *, status_code: int, error_code: str | None, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        code = f" {error_code}" if error_code else ""
        super().__init__(f"OANDA API error {status_code}{code}: {message}")


class OandaClient:
    def __init__(
        self,
        *,
        account_id: str,
        token: str,
        rest_base_url: str,
        stream_base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> None:
        self.account_id = account_id
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept-Datetime-Format": "RFC3339",
        }
        self._rest_client = httpx.AsyncClient(
            base_url=_base_url(rest_base_url),
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )
        self._stream_client = httpx.AsyncClient(
            base_url=_base_url(stream_base_url),
            headers=headers,
            timeout=timeout_seconds,
            transport=transport,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | httpx.BaseTransport | None = None,
    ) -> "OandaClient":
        if not settings.oanda_api_token:
            msg = "OANDA_API_TOKEN is required to create an OANDA client"
            raise ValueError(msg)
        if not settings.oanda_account_id:
            msg = "OANDA_ACCOUNT_ID is required to create an OANDA client"
            raise ValueError(msg)
        return cls(
            account_id=settings.oanda_account_id,
            token=settings.oanda_api_token,
            rest_base_url=settings.oanda_rest_base_url,
            stream_base_url=settings.oanda_stream_base_url,
            timeout_seconds=settings.oanda_request_timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> "OandaClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._rest_client.aclose()
        await self._stream_client.aclose()

    async def get_account_summary(self) -> AccountSummary:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"accounts/{self.account_id}/summary",
        )
        return parse_account_summary(payload)

    async def get_account_instruments(self) -> list[Instrument]:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"accounts/{self.account_id}/instruments",
        )
        return parse_instruments(payload)

    async def get_historical_candles(
        self,
        *,
        instrument: str,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        count: int | None = None,
        include_first: bool = True,
    ) -> list[HistoricalCandle]:
        params: dict[str, str | int] = {
            "granularity": "M1",
            "price": "MBA",
        }
        if count is not None:
            params["count"] = count
        if from_time is not None:
            params["from"] = _format_rfc3339(from_time)
            params["includeFirst"] = _bool_param(include_first)
        if to_time is not None:
            params["to"] = _format_rfc3339(to_time)

        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"instruments/{instrument}/candles",
            params=params,
        )
        return parse_historical_candles(payload)

    async def get_order_book(
        self, *, instrument: str, time: datetime | None = None
    ) -> BookSnapshot:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"instruments/{instrument}/orderBook",
            params=_time_params(time),
        )
        return parse_order_book(payload)

    async def get_position_book(
        self, *, instrument: str, time: datetime | None = None
    ) -> BookSnapshot:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"instruments/{instrument}/positionBook",
            params=_time_params(time),
        )
        return parse_position_book(payload)

    async def stream_pricing_lines(self, instruments: Sequence[str]) -> AsyncIterator[str]:
        params = {"instruments": ",".join(instruments)}
        async for line in self._stream_lines(
            f"accounts/{self.account_id}/pricing/stream",
            params=params,
        ):
            yield line

    async def stream_transaction_lines(self) -> AsyncIterator[str]:
        async for line in self._stream_lines(f"accounts/{self.account_id}/transactions/stream"):
            yield line

    async def create_market_order_with_bracket(
        self, request: MarketOrderRequest
    ) -> OrderCreateResult:
        payload = await self._request_json(
            self._rest_client,
            "POST",
            f"accounts/{self.account_id}/orders",
            json_body=market_order_request_payload(request),
        )
        return parse_order_create_result(payload)

    async def close_trade(self, *, trade_id: str, units: str = "ALL") -> TradeCloseResult:
        payload = await self._request_json(
            self._rest_client,
            "PUT",
            f"accounts/{self.account_id}/trades/{trade_id}/close",
            json_body={"units": units},
        )
        return parse_trade_close_result(trade_id, payload)

    async def close_position(
        self,
        *,
        instrument: str,
        long_units: str | None = None,
        short_units: str | None = None,
    ) -> PositionCloseResult:
        body: dict[str, str] = {}
        if long_units is not None:
            body["longUnits"] = long_units
        if short_units is not None:
            body["shortUnits"] = short_units
        if not body:
            body = {"longUnits": "ALL", "shortUnits": "ALL"}

        payload = await self._request_json(
            self._rest_client,
            "PUT",
            f"accounts/{self.account_id}/positions/{instrument}/close",
            json_body=body,
        )
        return parse_position_close_result(instrument, payload)

    async def list_open_trades(self) -> list[OpenTrade]:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"accounts/{self.account_id}/openTrades",
        )
        return parse_open_trades(payload)

    async def list_open_positions(self) -> list[OpenPosition]:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"accounts/{self.account_id}/openPositions",
        )
        return parse_open_positions(payload)

    async def get_transactions_since(self, *, transaction_id: str) -> TransactionHistoryPage:
        payload = await self._request_json(
            self._rest_client,
            "GET",
            f"accounts/{self.account_id}/transactions/sinceid",
            params={"id": transaction_id},
        )
        return parse_transaction_history_page(payload)

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await client.request(method, url, params=params, json=json_body)
        await _raise_for_oanda_error(response)
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "expected OANDA response JSON object"
            raise TypeError(msg)
        return payload

    async def _stream_lines(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> AsyncIterator[str]:
        async with self._stream_client.stream("GET", url, params=params) as response:
            await _raise_for_oanda_error(response)
            async for line in response.aiter_lines():
                yield line


async def _raise_for_oanda_error(response: httpx.Response) -> None:
    if response.status_code < 400:
        return

    content = await response.aread()
    try:
        payload = json.loads(content.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}

    error_code = payload.get("errorCode") if isinstance(payload, dict) else None
    message = payload.get("errorMessage") if isinstance(payload, dict) else None
    if not message:
        message = response.reason_phrase

    raise OandaApiError(
        status_code=response.status_code,
        error_code=str(error_code) if error_code else None,
        message=str(message),
    )


def _format_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        msg = "OANDA request timestamps must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _time_params(value: datetime | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {"time": _format_rfc3339(value)}


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _base_url(value: str) -> str:
    return value if value.endswith("/") else f"{value}/"
