from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.fvgs import FairValueGap
from harbor_bot.strategy.models import (
    Bias,
    InstrumentRules,
    LevelName,
    SessionLevels,
    SweepState,
    strategy_config_from_defaults,
)
from harbor_bot.strategy.signals import build_market_entry_setup


def test_long_setup_uses_sweep_stop_rr_target_and_sizing() -> None:
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("10000"),
        levels=_levels(),
        recent_candles=[],
        config=_config(),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.side == "long"
    assert setup.stop == Decimal("1.08785")
    assert setup.risk == Decimal("0.00215")
    assert setup.target == Decimal("1.09430")
    assert setup.units == Decimal("23255")


def test_short_setup_uses_high_sweep_stop_and_downside_target() -> None:
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BEARISH),
        entry_price=Decimal("1.1000"),
        nav=Decimal("10000"),
        levels=_levels(),
        recent_candles=[],
        config=_config(),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.side == "short"
    assert setup.stop == Decimal("1.10215")
    assert setup.risk == Decimal("0.00215")
    assert setup.target == Decimal("1.09570")
    assert setup.units == Decimal("23255")


def test_stop_widens_to_recent_swing_low_for_long_setups() -> None:
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("10000"),
        levels=_levels(),
        recent_candles=[_candle(low="1.0870", high="1.0910")],
        config=_config(),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.stop == Decimal("1.08685")


def test_nearer_liquidity_target_must_respect_liquidity_rr_floor() -> None:
    levels = replace(_levels(), asia_high=Decimal("1.0920"), london_high=Decimal("1.0930"))

    assert (
        build_market_entry_setup(
            fvg=_fvg(Bias.BULLISH),
            entry_price=Decimal("1.0900"),
            nav=Decimal("10000"),
            levels=levels,
            recent_candles=[],
            config=_config(),
            instrument_rules=_rules(),
        )
        is None
    )


def test_rr_target_mode_uses_fixed_rr_target_even_when_liquidity_is_nearer() -> None:
    levels = replace(_levels(), asia_high=Decimal("1.0920"), london_high=Decimal("1.0930"))
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("10000"),
        levels=levels,
        recent_candles=[],
        config=replace(_config(), target_mode="rr"),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.target == Decimal("1.09430")


def test_rr_or_liquidity_mode_takes_nearer_liquidity_after_floor() -> None:
    levels = replace(_levels(), asia_high=Decimal("1.0930"), london_high=Decimal("1.1150"))
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("10000"),
        levels=levels,
        recent_candles=[],
        config=_config(),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.target == Decimal("1.0930")


def test_opposite_session_mode_requires_qualified_liquidity_target() -> None:
    levels = replace(_levels(), asia_high=Decimal("1.0920"), london_high=Decimal("1.0930"))
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("10000"),
        levels=levels,
        recent_candles=[],
        config=replace(_config(), target_mode="opposite_session"),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.target == Decimal("1.0930")


def test_units_are_clamped_to_configured_max_units() -> None:
    setup = build_market_entry_setup(
        fvg=_fvg(Bias.BULLISH),
        entry_price=Decimal("1.0900"),
        nav=Decimal("1000000"),
        levels=_levels(),
        recent_candles=[],
        config=_config(),
        instrument_rules=_rules(),
    )

    assert setup is not None
    assert setup.units == Decimal("100000")


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
        asia_high=Decimal("1.1100"),
        asia_low=Decimal("1.0800"),
        london_high=Decimal("1.1150"),
        london_low=Decimal("1.0750"),
    )


def _fvg(bias: Bias) -> FairValueGap:
    sweep = SweepState(
        level_name=LevelName.ASIA_LOW if bias == Bias.BULLISH else LevelName.ASIA_HIGH,
        level_price=Decimal("1.0800") if bias == Bias.BULLISH else Decimal("1.1100"),
        bias=bias,
        sweep_extreme=Decimal("1.0880") if bias == Bias.BULLISH else Decimal("1.1020"),
        swept_ts=datetime(2026, 1, 15, 14, 29, tzinfo=UTC),
        candle_index=10,
        fvg_deadline_index=18,
    )
    return FairValueGap(
        ts=datetime(2026, 1, 15, 14, 32, tzinfo=UTC),
        instrument="EUR_USD",
        fvg_type=bias,
        top=Decimal("1.0910"),
        bottom=Decimal("1.0890"),
        midpoint=Decimal("1.0900"),
        sweep=sweep,
    )


def _candle(*, high: str, low: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.0900"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal("1.0905"),
        volume=100,
    )
