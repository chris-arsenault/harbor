from datetime import UTC, datetime
from decimal import Decimal

from harbor_bot.backtester.data import candles_from_records
from harbor_bot.backtester.fills import OpenBacktestPosition, simulate_bracket_exit
from harbor_bot.backtester.models import BacktestConfig
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import InstrumentRules, LevelName, MarketEntrySetup

TS = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)


def test_long_stop_counts_on_bid_low_not_midpoint_low() -> None:
    position = _long_position(stop=Decimal("1.09950"), target=Decimal("1.10200"))
    # Midpoint low (1.09960) sits above the stop, but the bid low (1.09940) trades through it.
    midpoint_only = _candle(low=Decimal("1.09960"), high=Decimal("1.10010"))
    with_bid_ask = _candle(
        low=Decimal("1.09960"),
        high=Decimal("1.10010"),
        bid_low=Decimal("1.09940"),
        bid_h=Decimal("1.10005"),
        ask_low=Decimal("1.09980"),
        ask_h=Decimal("1.10030"),
    )

    assert simulate_bracket_exit(position, candle=midpoint_only, **_fill_kwargs()) is None
    honest = simulate_bracket_exit(position, candle=with_bid_ask, **_fill_kwargs())
    assert honest is not None
    assert honest.exit_reason == "stop_loss"


def test_candles_from_records_parses_bid_and_ask_extremes() -> None:
    record = {
        "instrument": "EUR_USD",
        "time": "2026-01-15T14:00:00+00:00",
        "complete": True,
        "volume": 5,
        "mid": {"o": "1.1000", "h": "1.1050", "l": "1.0990", "c": "1.1040"},
        "bid": {"o": "1.0999", "h": "1.1049", "l": "1.0989", "c": "1.1039"},
        "ask": {"o": "1.1001", "h": "1.1051", "l": "1.0991", "c": "1.1041"},
    }

    candle = candles_from_records([record])[0]

    assert candle.low == Decimal("1.0990")
    assert candle.bid_low == Decimal("1.0989")
    assert candle.ask_h == Decimal("1.1051")


def _candle(
    *,
    low: Decimal,
    high: Decimal,
    bid_low: Decimal | None = None,
    bid_h: Decimal | None = None,
    ask_low: Decimal | None = None,
    ask_h: Decimal | None = None,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=TS,
        o=Decimal("1.10000"),
        h=high,
        low=low,
        c=Decimal("1.09990"),
        volume=1,
        bid_h=bid_h,
        bid_low=bid_low,
        ask_h=ask_h,
        ask_low=ask_low,
    )


def _long_position(*, stop: Decimal, target: Decimal) -> OpenBacktestPosition:
    setup = MarketEntrySetup(
        ts=TS,
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.10000"),
        stop=stop,
        target=target,
        risk=abs(Decimal("1.10000") - stop),
        units=Decimal("10000"),
    )
    return OpenBacktestPosition(setup=setup, entry_price=Decimal("1.10000"), entry_ts=TS)


def _fill_kwargs() -> dict[str, object]:
    return {"config": BacktestConfig(), "instrument_rules": _rules()}


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
