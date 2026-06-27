from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class AccountSummary:
    account_id: str
    currency: str
    balance: Decimal
    nav: Decimal
    unrealized_pl: Decimal
    open_trade_count: int
    open_position_count: int
    last_transaction_id: str | None


@dataclass(frozen=True)
class Instrument:
    name: str
    display_name: str
    pip_location: int
    display_precision: int
    trade_units_precision: int
    minimum_trade_size: Decimal


@dataclass(frozen=True)
class HistoricalCandle:
    instrument: str
    time: datetime
    o: Decimal
    h: Decimal
    low: Decimal
    c: Decimal
    volume: int
    complete: bool
    bid_h: Decimal | None = None
    bid_low: Decimal | None = None
    bid_c: Decimal | None = None
    ask_h: Decimal | None = None
    ask_low: Decimal | None = None
    ask_c: Decimal | None = None


@dataclass(frozen=True)
class BookBucket:
    price: Decimal
    long_percent: Decimal
    short_percent: Decimal


@dataclass(frozen=True)
class BookSnapshot:
    book_type: str
    instrument: str
    time: datetime
    price: Decimal
    bucket_width: Decimal
    buckets: tuple[BookBucket, ...]


@dataclass(frozen=True)
class PriceBucket:
    price: Decimal
    liquidity: int


@dataclass(frozen=True)
class PriceFrame:
    time: datetime
    instrument: str
    bids: tuple[PriceBucket, ...]
    asks: tuple[PriceBucket, ...]
    closeout_bid: Decimal | None
    closeout_ask: Decimal | None
    tradeable: bool
    status: str | None


@dataclass(frozen=True)
class PricingHeartbeat:
    time: datetime


@dataclass(frozen=True)
class TransactionFrame:
    transaction_type: str
    transaction_id: str | None
    time: datetime
    raw: dict[str, Any]


@dataclass(frozen=True)
class TransactionHeartbeat:
    time: datetime
    last_transaction_id: str | None


@dataclass(frozen=True)
class ClientExtensions:
    client_id: str
    tag: str
    comment: str


@dataclass(frozen=True)
class MarketOrderRequest:
    instrument: str
    units: int
    stop_loss_price: Decimal
    take_profit_price: Decimal
    client_extensions: ClientExtensions


@dataclass(frozen=True)
class OrderCreateResult:
    order_id: str
    fill_transaction_id: str | None
    trade_id: str | None
    instrument: str
    units: Decimal
    price: Decimal | None
    last_transaction_id: str
    related_transaction_ids: tuple[str, ...]
    raw: dict[str, Any]


@dataclass(frozen=True)
class TradeCloseResult:
    trade_id: str
    close_transaction_ids: tuple[str, ...]
    last_transaction_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class PositionCloseResult:
    instrument: str
    close_transaction_ids: tuple[str, ...]
    last_transaction_id: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class OpenTrade:
    trade_id: str
    instrument: str
    price: Decimal
    open_time: datetime
    initial_units: Decimal
    current_units: Decimal
    state: str
    realized_pl: Decimal
    unrealized_pl: Decimal
    raw: dict[str, Any]


@dataclass(frozen=True)
class OpenPosition:
    instrument: str
    long_units: Decimal
    short_units: Decimal
    unrealized_pl: Decimal
    raw: dict[str, Any]


@dataclass(frozen=True)
class TransactionHistoryPage:
    transactions: tuple[TransactionFrame, ...]
    last_transaction_id: str


PricingFrame = PriceFrame | PricingHeartbeat
TransactionStreamFrame = TransactionFrame | TransactionHeartbeat


def parse_account_summary(payload: dict[str, Any]) -> AccountSummary:
    account = _mapping(payload["account"])
    return AccountSummary(
        account_id=str(account["id"]),
        currency=str(account["currency"]),
        balance=_decimal(account["balance"]),
        nav=_decimal(account["NAV"]),
        unrealized_pl=_decimal(account["unrealizedPL"]),
        open_trade_count=int(account["openTradeCount"]),
        open_position_count=int(account["openPositionCount"]),
        last_transaction_id=_optional_str(payload.get("lastTransactionID")),
    )


def parse_instruments(payload: dict[str, Any]) -> list[Instrument]:
    return [
        Instrument(
            name=str(instrument["name"]),
            display_name=str(instrument["displayName"]),
            pip_location=int(instrument["pipLocation"]),
            display_precision=int(instrument["displayPrecision"]),
            trade_units_precision=int(instrument["tradeUnitsPrecision"]),
            minimum_trade_size=_decimal(instrument["minimumTradeSize"]),
        )
        for instrument in payload["instruments"]
    ]


def parse_historical_candles(payload: dict[str, Any]) -> list[HistoricalCandle]:
    instrument = str(payload["instrument"])
    parsed = []
    for candle in payload["candles"]:
        mid = _mapping(candle["mid"])
        bid = candle.get("bid")
        ask = candle.get("ask")
        parsed.append(
            HistoricalCandle(
                instrument=instrument,
                time=parse_rfc3339(str(candle["time"])),
                o=_decimal(mid["o"]),
                h=_decimal(mid["h"]),
                low=_decimal(mid["l"]),
                c=_decimal(mid["c"]),
                volume=int(candle["volume"]),
                complete=bool(candle["complete"]),
                bid_h=_optional_ohlc(bid, "h"),
                bid_low=_optional_ohlc(bid, "l"),
                bid_c=_optional_ohlc(bid, "c"),
                ask_h=_optional_ohlc(ask, "h"),
                ask_low=_optional_ohlc(ask, "l"),
                ask_c=_optional_ohlc(ask, "c"),
            )
        )
    return parsed


def parse_order_book(payload: dict[str, Any]) -> BookSnapshot:
    return _parse_book_snapshot(payload, payload_key="orderBook", book_type="order")


def parse_position_book(payload: dict[str, Any]) -> BookSnapshot:
    return _parse_book_snapshot(payload, payload_key="positionBook", book_type="position")


def _optional_ohlc(group: Any, key: str) -> Decimal | None:
    if not isinstance(group, dict):
        return None
    value = group.get(key)
    return None if value is None else _decimal(value)


def parse_pricing_frame(payload: dict[str, Any]) -> PricingFrame:
    frame_type = str(payload["type"])
    if frame_type == "HEARTBEAT":
        return PricingHeartbeat(time=parse_rfc3339(str(payload["time"])))
    if frame_type != "PRICE":
        msg = f"unsupported pricing frame type: {frame_type}"
        raise ValueError(msg)

    return PriceFrame(
        time=parse_rfc3339(str(payload["time"])),
        instrument=str(payload["instrument"]),
        bids=_parse_price_buckets(payload.get("bids", [])),
        asks=_parse_price_buckets(payload.get("asks", [])),
        closeout_bid=_optional_decimal(payload.get("closeoutBid")),
        closeout_ask=_optional_decimal(payload.get("closeoutAsk")),
        tradeable=bool(payload.get("tradeable", False)),
        status=_optional_str(payload.get("status")),
    )


def parse_transaction_frame(payload: dict[str, Any]) -> TransactionStreamFrame:
    frame_type = str(payload["type"])
    if frame_type == "HEARTBEAT":
        return TransactionHeartbeat(
            time=parse_rfc3339(str(payload["time"])),
            last_transaction_id=_optional_str(payload.get("lastTransactionID")),
        )

    return TransactionFrame(
        transaction_type=frame_type,
        transaction_id=_optional_str(payload.get("id")),
        time=parse_rfc3339(str(payload["time"])),
        raw=dict(payload),
    )


def market_order_request_payload(request: MarketOrderRequest) -> dict[str, Any]:
    return {
        "order": {
            "clientExtensions": {
                "comment": request.client_extensions.comment,
                "id": request.client_extensions.client_id,
                "tag": request.client_extensions.tag,
            },
            "instrument": request.instrument,
            "positionFill": "DEFAULT",
            "stopLossOnFill": {
                "price": _decimal_str(request.stop_loss_price),
                "timeInForce": "GTC",
            },
            "takeProfitOnFill": {
                "price": _decimal_str(request.take_profit_price),
                "timeInForce": "GTC",
            },
            "timeInForce": "FOK",
            "type": "MARKET",
            "units": str(request.units),
        }
    }


def parse_order_create_result(payload: dict[str, Any]) -> OrderCreateResult:
    create_transaction = _mapping(payload["orderCreateTransaction"])
    fill_transaction = payload.get("orderFillTransaction")
    if fill_transaction is not None:
        fill_transaction = _mapping(fill_transaction)
    trade_opened = _mapping(fill_transaction.get("tradeOpened", {})) if fill_transaction else {}
    return OrderCreateResult(
        order_id=str(create_transaction["id"]),
        fill_transaction_id=_optional_str(fill_transaction.get("id")) if fill_transaction else None,
        trade_id=_optional_str(trade_opened.get("tradeID")),
        instrument=str(create_transaction["instrument"]),
        units=_decimal(create_transaction["units"]),
        price=_optional_decimal(fill_transaction.get("price")) if fill_transaction else None,
        last_transaction_id=str(payload["lastTransactionID"]),
        related_transaction_ids=_string_tuple(payload.get("relatedTransactionIDs", [])),
        raw=dict(payload),
    )


def parse_trade_close_result(trade_id: str, payload: dict[str, Any]) -> TradeCloseResult:
    return TradeCloseResult(
        trade_id=trade_id,
        close_transaction_ids=_fill_transaction_ids(payload),
        last_transaction_id=str(payload["lastTransactionID"]),
        raw=dict(payload),
    )


def parse_position_close_result(instrument: str, payload: dict[str, Any]) -> PositionCloseResult:
    return PositionCloseResult(
        instrument=instrument,
        close_transaction_ids=_fill_transaction_ids(payload),
        last_transaction_id=str(payload["lastTransactionID"]),
        raw=dict(payload),
    )


def parse_open_trades(payload: dict[str, Any]) -> list[OpenTrade]:
    return [
        OpenTrade(
            trade_id=str(trade["id"]),
            instrument=str(trade["instrument"]),
            price=_decimal(trade["price"]),
            open_time=parse_rfc3339(str(trade["openTime"])),
            initial_units=_decimal(trade["initialUnits"]),
            current_units=_decimal(trade["currentUnits"]),
            state=str(trade["state"]),
            realized_pl=_decimal(trade.get("realizedPL", "0")),
            unrealized_pl=_decimal(trade.get("unrealizedPL", "0")),
            raw=dict(trade),
        )
        for trade in payload.get("trades", [])
    ]


def parse_open_positions(payload: dict[str, Any]) -> list[OpenPosition]:
    positions = []
    for position in payload.get("positions", []):
        long_side = _mapping(position.get("long", {}))
        short_side = _mapping(position.get("short", {}))
        positions.append(
            OpenPosition(
                instrument=str(position["instrument"]),
                long_units=_decimal(long_side.get("units", "0")),
                short_units=_decimal(short_side.get("units", "0")),
                unrealized_pl=_decimal(position.get("unrealizedPL", "0")),
                raw=dict(position),
            )
        )
    return positions


def parse_transaction_history_page(payload: dict[str, Any]) -> TransactionHistoryPage:
    transactions = tuple(
        transaction
        for transaction in (
            parse_transaction_frame(_mapping(raw_transaction))
            for raw_transaction in payload.get("transactions", [])
        )
        if isinstance(transaction, TransactionFrame)
    )
    return TransactionHistoryPage(
        transactions=transactions,
        last_transaction_id=str(payload["lastTransactionID"]),
    )


def _parse_book_snapshot(
    payload: dict[str, Any], *, payload_key: str, book_type: str
) -> BookSnapshot:
    book = _mapping(payload[payload_key])
    try:
        raw_time = str(book["time"])
        raw_price = book["price"]
        raw_bucket_width = book["bucketWidth"]
    except KeyError as exc:
        msg = f"{payload_key} response missing required field: {exc.args[0]}"
        raise ValueError(msg) from exc

    return BookSnapshot(
        book_type=book_type,
        instrument=str(book["instrument"]),
        time=parse_rfc3339(raw_time),
        price=_decimal(raw_price),
        bucket_width=_decimal(raw_bucket_width),
        buckets=_parse_book_buckets(book.get("buckets", [])),
    )


def parse_rfc3339(value: str) -> datetime:
    normalized = value
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    if "." in normalized:
        date_part, fraction_and_zone = normalized.split(".", 1)
        zone_index = _timezone_index(fraction_and_zone)
        if zone_index == -1:
            fraction = fraction_and_zone
            zone = ""
        else:
            fraction = fraction_and_zone[:zone_index]
            zone = fraction_and_zone[zone_index:]
        normalized = f"{date_part}.{fraction[:6]}{zone}"

    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        msg = "OANDA timestamps must include timezone information"
        raise ValueError(msg)
    return parsed.astimezone(UTC)


def _parse_price_buckets(raw_buckets: list[dict[str, Any]]) -> tuple[PriceBucket, ...]:
    return tuple(
        PriceBucket(price=_decimal(bucket["price"]), liquidity=int(bucket["liquidity"]))
        for bucket in raw_buckets
    )


def _parse_book_buckets(raw_buckets: Any) -> tuple[BookBucket, ...]:
    if not isinstance(raw_buckets, list):
        msg = "book buckets must be a JSON array"
        raise TypeError(msg)
    return tuple(
        BookBucket(
            price=_decimal(bucket["price"]),
            long_percent=_decimal(bucket["longCountPercent"]),
            short_percent=_decimal(bucket["shortCountPercent"]),
        )
        for bucket in (_mapping(raw_bucket) for raw_bucket in raw_buckets)
    )


def _timezone_index(value: str) -> int:
    indexes = [index for index in (value.find("+"), value.find("-")) if index != -1]
    if not indexes:
        return -1
    return min(indexes)


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        msg = "expected JSON object"
        raise TypeError(msg)
    return value


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return _decimal(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _decimal_str(value: Decimal) -> str:
    return format(value, "f")


def _string_tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in value)


def _fill_transaction_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for key, value in payload.items():
        if key.lower().endswith("orderfilltransaction") and isinstance(value, dict):
            transaction_id = _optional_str(value.get("id"))
            if transaction_id is not None:
                ids.append(transaction_id)
    return tuple(ids)
