from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import strategy_config_from_defaults
from harbor_bot.strategy.sessions import (
    compute_session_levels,
    is_in_ny_trade_window,
    session_windows_for_date,
)


def test_session_windows_convert_new_york_time_to_utc_without_fixed_offsets() -> None:
    config = strategy_config_from_defaults(load_default_config())

    winter = session_windows_for_date(date(2026, 1, 15), config)
    summer = session_windows_for_date(date(2026, 7, 15), config)

    assert winter.asia.start == datetime(2026, 1, 15, 1, 0, tzinfo=UTC)
    assert winter.asia.end == datetime(2026, 1, 15, 5, 0, tzinfo=UTC)
    assert winter.london.start == datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
    assert winter.london.end == datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    assert winter.ny_trade.start == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert winter.ny_trade.end == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)

    assert summer.asia.start == datetime(2026, 7, 15, 0, 0, tzinfo=UTC)
    assert summer.asia.end == datetime(2026, 7, 15, 4, 0, tzinfo=UTC)
    assert summer.london.start == datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
    assert summer.london.end == datetime(2026, 7, 15, 9, 0, tzinfo=UTC)
    assert summer.ny_trade.start == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
    assert summer.ny_trade.end == datetime(2026, 7, 15, 15, 30, tzinfo=UTC)


def test_ny_trade_window_membership_uses_resolved_session_window() -> None:
    config = strategy_config_from_defaults(load_default_config())
    trading_date = date(2026, 1, 15)

    assert is_in_ny_trade_window(
        _candle("2026-01-15T14:30:00+00:00"),
        trading_date=trading_date,
        config=config,
    )
    assert not is_in_ny_trade_window(
        _candle("2026-01-15T16:30:00+00:00"),
        trading_date=trading_date,
        config=config,
    )


def test_compute_session_levels_from_closed_m1_candles() -> None:
    config = strategy_config_from_defaults(load_default_config())
    levels = compute_session_levels(
        [
            _candle("2026-01-15T00:59:00+00:00", high="1.5000", low="1.4000"),
            _candle("2026-01-15T01:00:00+00:00", high="1.1000", low="1.0900"),
            _candle("2026-01-15T02:00:00+00:00", high="1.1050", low="1.0910"),
            _candle("2026-01-15T04:59:00+00:00", high="1.1010", low="1.0880"),
            _candle("2026-01-15T07:00:00+00:00", high="1.1100", low="1.0980"),
            _candle("2026-01-15T08:00:00+00:00", high="1.1150", low="1.0970"),
            _candle("2026-01-15T09:59:00+00:00", high="1.1120", low="1.0990"),
            _candle("2026-01-15T10:00:00+00:00", high="1.9000", low="1.8000"),
        ],
        trading_date=date(2026, 1, 15),
        instrument="EUR_USD",
        config=config,
    )

    assert levels.asia_high == Decimal("1.1050")
    assert levels.asia_low == Decimal("1.0880")
    assert levels.london_high == Decimal("1.1150")
    assert levels.london_low == Decimal("1.0970")


def test_session_level_calculation_rejects_incomplete_candles() -> None:
    config = strategy_config_from_defaults(load_default_config())

    with pytest.raises(ValueError, match="closed candles only"):
        compute_session_levels(
            [_candle("2026-01-15T01:00:00+00:00", complete=False)],
            trading_date=date(2026, 1, 15),
            instrument="EUR_USD",
            config=config,
        )


def _candle(
    ts: str,
    *,
    high: str = "1.1000",
    low: str = "1.0900",
    complete: bool = True,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.0950"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal("1.0960"),
        volume=100,
        complete=complete,
    )
