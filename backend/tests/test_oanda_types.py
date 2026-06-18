import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from harbor_bot.oanda.types import (
    PriceFrame,
    PricingHeartbeat,
    TransactionFrame,
    TransactionHeartbeat,
    parse_account_summary,
    parse_historical_candles,
    parse_instruments,
    parse_pricing_frame,
    parse_transaction_frame,
)

FIXTURES = Path(__file__).parent / "fixtures" / "oanda"


def test_account_summary_normalizes_decimal_fields() -> None:
    summary = parse_account_summary(_load_json("account_summary.json"))

    assert summary.account_id == "101-001-1234567-001"
    assert summary.currency == "USD"
    assert summary.balance == Decimal("10000.1234")
    assert summary.nav == Decimal("10002.5678")
    assert summary.unrealized_pl == Decimal("2.4444")
    assert summary.open_trade_count == 1
    assert summary.open_position_count == 1
    assert summary.last_transaction_id == "9001"


def test_instruments_normalize_decimal_and_precision_fields() -> None:
    instruments = parse_instruments(_load_json("account_instruments.json"))

    assert len(instruments) == 1
    assert instruments[0].name == "EUR_USD"
    assert instruments[0].display_name == "EUR/USD"
    assert instruments[0].pip_location == -4
    assert instruments[0].display_precision == 5
    assert instruments[0].trade_units_precision == 0
    assert instruments[0].minimum_trade_size == Decimal("1")


def test_historical_candles_normalize_rfc3339_and_string_prices() -> None:
    candles = parse_historical_candles(_load_json("candles.json"))

    assert [candle.complete for candle in candles] == [True, False]
    assert candles[0].instrument == "EUR_USD"
    assert candles[0].time == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert candles[0].o == Decimal("1.09000")
    assert candles[0].h == Decimal("1.09100")
    assert candles[0].low == Decimal("1.08950")
    assert candles[0].c == Decimal("1.09050")
    assert candles[0].volume == 128


def test_pricing_price_and_heartbeat_frames_are_distinct() -> None:
    price = parse_pricing_frame(_load_json("pricing_price.json"))
    heartbeat = parse_pricing_frame(_load_json("pricing_heartbeat.json"))

    assert isinstance(price, PriceFrame)
    assert price.time == datetime(2026, 1, 15, 14, 30, 12, 345678, tzinfo=UTC)
    assert price.instrument == "EUR_USD"
    assert price.bids[0].price == Decimal("1.09010")
    assert price.asks[0].price == Decimal("1.09020")
    assert price.closeout_bid == Decimal("1.09005")
    assert price.closeout_ask == Decimal("1.09025")
    assert price.tradeable is True

    assert isinstance(heartbeat, PricingHeartbeat)
    assert heartbeat.time == datetime(2026, 1, 15, 14, 30, 15, tzinfo=UTC)


def test_transaction_frames_preserve_raw_payloads() -> None:
    transaction = parse_transaction_frame(_load_json("transaction_order_fill.json"))
    heartbeat = parse_transaction_frame(_load_json("transaction_heartbeat.json"))

    assert isinstance(transaction, TransactionFrame)
    assert transaction.transaction_type == "ORDER_FILL"
    assert transaction.transaction_id == "9010"
    assert transaction.time == datetime(2026, 1, 15, 14, 30, 16, tzinfo=UTC)
    assert transaction.raw["instrument"] == "EUR_USD"
    assert transaction.raw["price"] == "1.09020"

    assert isinstance(heartbeat, TransactionHeartbeat)
    assert heartbeat.time == datetime(2026, 1, 15, 14, 30, 20, tzinfo=UTC)
    assert heartbeat.last_transaction_id == "9011"


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())
