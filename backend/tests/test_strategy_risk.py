from datetime import UTC, date, datetime
from decimal import Decimal

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import DayState, LevelName, strategy_config_from_defaults
from harbor_bot.strategy.risk import (
    check_daily_loss,
    check_one_position,
    check_one_trade_per_level,
    check_spread,
    check_trade_count,
    daily_loss_flatten_decision,
    ny_close_flatten_decision,
)


def test_spread_gate_vetoes_wide_spread() -> None:
    result = check_spread(Decimal("1.3"), _config())

    assert result.allowed is False
    assert result.reason == "spread"


def test_daily_loss_gate_vetoes_breach() -> None:
    result = check_daily_loss(
        day_start_nav=Decimal("10000"),
        current_nav=Decimal("9799"),
        config=_config(),
    )

    assert result.allowed is False
    assert result.reason == "daily_loss"


def test_trade_count_and_position_gates() -> None:
    state = DayState(
        trading_date=date(2026, 1, 15),
        trades_taken=2,
        has_open_position=True,
    )

    assert check_trade_count(state, _config()).reason == "max_trades_per_day"
    assert check_one_position(state).reason == "one_position"


def test_one_trade_per_level_gate() -> None:
    state = DayState(
        trading_date=date(2026, 1, 15),
        taken_levels=frozenset({LevelName.ASIA_LOW}),
    )

    result = check_one_trade_per_level(state, LevelName.ASIA_LOW, _config())

    assert result.allowed is False
    assert result.reason == "one_trade_per_level"


def test_ny_close_flatten_decision() -> None:
    decision = ny_close_flatten_decision(
        _candle("2026-01-15T16:30:00+00:00"),
        trading_date=date(2026, 1, 15),
        config=_config(),
        has_open_position=True,
    )
    before_close = ny_close_flatten_decision(
        _candle("2026-01-15T16:29:00+00:00"),
        trading_date=date(2026, 1, 15),
        config=_config(),
        has_open_position=True,
    )

    assert decision is not None
    assert decision.reason == "ny_close"
    assert before_close is None


def test_daily_loss_flatten_decision() -> None:
    decision = daily_loss_flatten_decision(
        ts=datetime(2026, 1, 15, 14, 30, tzinfo=UTC),
        day_start_nav=Decimal("10000"),
        current_nav=Decimal("9799"),
        config=_config(),
    )

    assert decision is not None
    assert decision.reason == "daily_loss"


def _config():
    return strategy_config_from_defaults(load_default_config())


def _candle(ts: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.0900"),
        h=Decimal("1.0910"),
        low=Decimal("1.0890"),
        c=Decimal("1.0905"),
        volume=100,
    )
