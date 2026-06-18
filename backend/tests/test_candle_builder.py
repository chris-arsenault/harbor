from datetime import UTC, datetime
from decimal import Decimal

from harbor_bot.feed.candles import CandleBuilder
from harbor_bot.oanda.types import PriceBucket, PriceFrame, PricingHeartbeat


def test_builder_ignores_heartbeats() -> None:
    builder = CandleBuilder()

    emitted = builder.add(PricingHeartbeat(time=datetime(2026, 1, 15, 14, 30, tzinfo=UTC)))

    assert emitted is None


def test_builder_emits_only_after_later_minute_starts() -> None:
    builder = CandleBuilder()

    assert builder.add(_price("2026-01-15T14:30:05+00:00", "1.09010", "1.09020")) is None
    assert builder.add(_price("2026-01-15T14:30:45+00:00", "1.09050", "1.09070")) is None

    emitted = builder.add(_price("2026-01-15T14:31:00+00:00", "1.09030", "1.09040"))

    assert emitted is not None
    assert emitted.instrument == "EUR_USD"
    assert emitted.ts == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert emitted.o == Decimal("1.09015")
    assert emitted.h == Decimal("1.09060")
    assert emitted.low == Decimal("1.09015")
    assert emitted.c == Decimal("1.09060")
    assert emitted.volume == 2
    assert emitted.complete is True


def test_builder_does_not_synthesize_missing_minutes() -> None:
    builder = CandleBuilder()

    assert builder.add(_price("2026-01-15T14:30:05+00:00", "1.09010", "1.09020")) is None
    first = builder.add(_price("2026-01-15T14:33:00+00:00", "1.09100", "1.09120"))
    second = builder.add(_price("2026-01-15T14:34:00+00:00", "1.09110", "1.09130"))

    assert first is not None
    assert first.ts == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert second is not None
    assert second.ts == datetime(2026, 1, 15, 14, 33, tzinfo=UTC)


def _price(time: str, bid: str, ask: str) -> PriceFrame:
    return PriceFrame(
        time=datetime.fromisoformat(time),
        instrument="EUR_USD",
        bids=(PriceBucket(price=Decimal(bid), liquidity=1_000_000),),
        asks=(PriceBucket(price=Decimal(ask), liquidity=1_000_000),),
        closeout_bid=None,
        closeout_ask=None,
        tradeable=True,
        status="tradeable",
    )
