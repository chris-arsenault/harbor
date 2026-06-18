from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    Bias,
    DayState,
    FlattenDecision,
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    SessionLevels,
    StrategyConfig,
    StrategyDecision,
    SweepState,
    require_closed_candle,
    strategy_config_from_defaults,
)


def test_strategy_config_loads_from_default_config_mapping() -> None:
    config = strategy_config_from_defaults(load_default_config())

    assert config == StrategyConfig(
        instrument="EUR_USD",
        timezone="America/New_York",
        sessions={
            "asia": {"start": "20:00", "end": "00:00"},
            "london": {"start": "02:00", "end": "05:00"},
            "ny_trade": {"start": "09:30", "end": "11:30"},
        },
        fvg_window=8,
        sweep_buffer_pips=Decimal("1.5"),
        risk_per_trade_pct=Decimal("0.5"),
        max_daily_loss_pct=Decimal("2.0"),
        target_mode="rr_or_liquidity",
        rr_floor=Decimal("2.0"),
        one_trade_per_level=True,
        max_trades_per_day=2,
        max_spread_pips=Decimal("1.2"),
        swing_lookback=5,
        max_units=Decimal("100000"),
    )


def test_instrument_rules_convert_pips_to_price_units() -> None:
    rules = InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )

    assert rules.pip_size == Decimal("0.0001")
    assert rules.pips_to_price(Decimal("1.5")) == Decimal("0.00015")


def test_session_levels_are_addressed_by_level_name() -> None:
    levels = SessionLevels(
        trading_date=date(2026, 1, 15),
        instrument="EUR_USD",
        asia_high=Decimal("1.1000"),
        asia_low=Decimal("1.0900"),
        london_high=Decimal("1.1050"),
        london_low=Decimal("1.0950"),
    )

    assert levels.price_for(LevelName.ASIA_HIGH) == Decimal("1.1000")
    assert levels.price_for(LevelName.ASIA_LOW) == Decimal("1.0900")
    assert levels.price_for(LevelName.LONDON_HIGH) == Decimal("1.1050")
    assert levels.price_for(LevelName.LONDON_LOW) == Decimal("1.0950")
    assert levels.opposite_levels(Bias.BULLISH) == {
        LevelName.ASIA_HIGH: Decimal("1.1000"),
        LevelName.LONDON_HIGH: Decimal("1.1050"),
    }
    assert levels.opposite_levels(Bias.BEARISH) == {
        LevelName.ASIA_LOW: Decimal("1.0900"),
        LevelName.LONDON_LOW: Decimal("1.0950"),
    }


def test_strategy_state_and_decision_models_are_immutable() -> None:
    ts = datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    sweep = SweepState(
        level_name=LevelName.ASIA_LOW,
        level_price=Decimal("1.0900"),
        bias=Bias.BULLISH,
        sweep_extreme=Decimal("1.0880"),
        swept_ts=ts,
        candle_index=10,
        fvg_deadline_index=18,
    )
    day_state = DayState(trading_date=date(2026, 1, 15), active_sweep=sweep)
    setup = MarketEntrySetup(
        ts=ts,
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.0910"),
        stop=Decimal("1.08785"),
        target=Decimal("1.0973"),
        risk=Decimal("0.00315"),
        units=Decimal("10000"),
    )
    flatten = FlattenDecision(ts=ts, reason="ny_close")
    decision = StrategyDecision(kind="market_entry", ts=ts, payload={"side": "long"})

    with pytest.raises(AttributeError):
        day_state.trades_taken = 1
    with pytest.raises(AttributeError):
        setup.units = Decimal("1")
    with pytest.raises(AttributeError):
        flatten.reason = "other"
    with pytest.raises(AttributeError):
        decision.kind = "other"


def test_strategy_boundary_rejects_non_closed_candles() -> None:
    candle = ClosedCandle(
        instrument="EUR_USD",
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        o=Decimal("1.0900"),
        h=Decimal("1.0910"),
        low=Decimal("1.0890"),
        c=Decimal("1.0905"),
        volume=100,
        complete=False,
    )

    with pytest.raises(ValueError, match="closed candles only"):
        require_closed_candle(candle)
