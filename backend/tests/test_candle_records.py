from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from harbor_bot.backtester.data import candles_from_records
from harbor_bot.persistence.market_repository import candle_record_from_row

TS = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "instrument": "EUR_USD",
        "ts": TS,
        "o": Decimal("1.1000"),
        "h": Decimal("1.1050"),
        "l": Decimal("1.0990"),
        "c": Decimal("1.1040"),
        "volume": 5,
        "complete": True,
        "bid_h": Decimal("1.1049"),
        "bid_l": Decimal("1.0989"),
        "ask_h": Decimal("1.1051"),
        "ask_l": Decimal("1.0991"),
    }
    row.update(overrides)
    return row


def test_candle_record_carries_bid_ask_when_present() -> None:
    record = candle_record_from_row(_row())

    assert record["low"] == "1.0990"
    assert record["bid"] == {"h": "1.1049", "l": "1.0989"}
    assert record["ask"] == {"h": "1.1051", "l": "1.0991"}


def test_candle_record_omits_bid_ask_when_absent() -> None:
    record = candle_record_from_row(_row(bid_h=None, bid_l=None, ask_h=None, ask_l=None))

    assert "bid" not in record
    assert "ask" not in record


def test_optimizer_and_backtester_records_feed_bid_ask_into_candles() -> None:
    # Proves the shared path carries honest fill data into ClosedCandle, so the
    # optimizer (which now uses this builder) runs on bid/ask, not midpoint.
    candle = candles_from_records([candle_record_from_row(_row())])[0]

    assert candle.bid_low == Decimal("1.0989")
    assert candle.ask_h == Decimal("1.1051")
