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
from harbor_bot.strategy.sweeps import detect_sweep, mark_level_taken, with_active_sweep


def test_high_sweep_produces_bearish_bias_and_deadline() -> None:
    sweep = detect_sweep(
        _candle(high="1.10020", close="1.09980"),
        levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        day_state=DayState(trading_date=date(2026, 1, 15)),
        candle_index=10,
    )

    assert sweep is not None
    assert sweep.level_name == LevelName.ASIA_HIGH
    assert sweep.level_price == Decimal("1.1000")
    assert sweep.bias == Bias.BEARISH
    assert sweep.sweep_extreme == Decimal("1.10020")
    assert sweep.fvg_deadline_index == 18


def test_low_sweep_produces_bullish_bias() -> None:
    sweep = detect_sweep(
        _candle(low="1.08980", close="1.09020"),
        levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        day_state=DayState(trading_date=date(2026, 1, 15)),
        candle_index=10,
    )

    assert sweep is not None
    assert sweep.level_name == LevelName.ASIA_LOW
    assert sweep.bias == Bias.BULLISH
    assert sweep.sweep_extreme == Decimal("1.08980")


def test_sweep_requires_rejection_close() -> None:
    assert (
        detect_sweep(
            _candle(high="1.10020", close="1.10005"),
            levels=_levels(),
            config=_config(),
            instrument_rules=_rules(),
            day_state=DayState(trading_date=date(2026, 1, 15)),
            candle_index=10,
        )
        is None
    )


def test_one_trade_per_level_skips_taken_levels() -> None:
    day_state = DayState(
        trading_date=date(2026, 1, 15),
        taken_levels=frozenset({LevelName.ASIA_HIGH}),
    )

    assert (
        detect_sweep(
            _candle(high="1.10020", close="1.09980"),
            levels=_levels(),
            config=_config(),
            instrument_rules=_rules(),
            day_state=day_state,
            candle_index=10,
        )
        is None
    )


def test_day_state_helpers_return_new_instances() -> None:
    day_state = DayState(trading_date=date(2026, 1, 15))
    sweep = detect_sweep(
        _candle(low="1.08980", close="1.09020"),
        levels=_levels(),
        config=_config(),
        instrument_rules=_rules(),
        day_state=day_state,
        candle_index=10,
    )

    with_sweep = with_active_sweep(day_state, sweep)
    marked = mark_level_taken(with_sweep, LevelName.ASIA_LOW)

    assert day_state.active_sweep is None
    assert day_state.taken_levels == frozenset()
    assert with_sweep.active_sweep == sweep
    assert marked.active_sweep is None
    assert marked.taken_levels == frozenset({LevelName.ASIA_LOW})


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


def _levels() -> SessionLevels:
    return SessionLevels(
        trading_date=date(2026, 1, 15),
        instrument="EUR_USD",
        asia_high=Decimal("1.1000"),
        asia_low=Decimal("1.0900"),
        london_high=Decimal("1.1050"),
        london_low=Decimal("1.0950"),
    )


def _candle(
    *,
    high: str = "1.0990",
    low: str = "1.0960",
    close: str = "1.0960",
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.0960"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=100,
    )
