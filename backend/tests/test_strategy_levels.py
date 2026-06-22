from datetime import UTC, date, datetime
from decimal import Decimal

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    Bias,
    DayState,
    InstrumentRules,
    LevelName,
    SessionLevels,
    strategy_config_from_defaults,
)
from harbor_bot.strategy.sweeps import detect_sweep

DAY = date(2026, 1, 15)


def test_prev_day_high_is_a_sweepable_level() -> None:
    levels = _levels(prev_day_high=Decimal("1.19500"))
    # High pierces PDH (1.19500) and closes back below it: a bearish sweep.
    candle = _candle(high="1.19600", low="1.19400", close="1.19450")

    sweep = detect_sweep(
        candle,
        levels=levels,
        config=_config(),
        instrument_rules=_rules(),
        day_state=DayState(trading_date=DAY),
        candle_index=20,
    )

    assert sweep is not None
    assert sweep.level_name == LevelName.PREV_DAY_HIGH
    assert sweep.bias == Bias.BEARISH


def test_absent_prev_day_level_is_skipped() -> None:
    levels = _levels(prev_day_high=None, prev_day_low=None)
    candle = _candle(high="1.19600", low="1.19400", close="1.19450")

    sweep = detect_sweep(
        candle,
        levels=levels,
        config=_config(),
        instrument_rules=_rules(),
        day_state=DayState(trading_date=DAY),
        candle_index=20,
    )

    assert sweep is None


def test_price_for_returns_prior_day_levels_and_none_when_absent() -> None:
    present = _levels(prev_day_high=Decimal("1.21000"), prev_day_low=Decimal("1.19000"))
    assert present.price_for(LevelName.PREV_DAY_HIGH) == Decimal("1.21000")
    assert present.price_for(LevelName.PREV_DAY_LOW) == Decimal("1.19000")

    absent = _levels()
    assert absent.price_for(LevelName.PREV_DAY_HIGH) is None
    assert absent.price_for(LevelName.PREV_DAY_LOW) is None


def _levels(
    *, prev_day_high: Decimal | None = None, prev_day_low: Decimal | None = None
) -> SessionLevels:
    return SessionLevels(
        trading_date=DAY,
        instrument="EUR_USD",
        asia_high=Decimal("1.20000"),
        asia_low=Decimal("1.19000"),
        london_high=Decimal("1.20100"),
        london_low=Decimal("1.18900"),
        prev_day_high=prev_day_high,
        prev_day_low=prev_day_low,
    )


def _candle(*, high: str, low: str, close: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 35, tzinfo=UTC),
        o=Decimal(close),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=1,
    )


def _config():
    return strategy_config_from_defaults(load_default_config())


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
