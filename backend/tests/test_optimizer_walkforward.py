from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.models import WalkForwardConfig
from harbor_bot.optimizer.search_space import strategy_config_for_params
from harbor_bot.optimizer.walkforward import build_walk_forward_windows
from harbor_bot.strategy.models import strategy_config_from_defaults


def test_walk_forward_windows_are_chronological_and_non_overlapping() -> None:
    windows = build_walk_forward_windows(
        [
            _candle("2026-01-15T01:00:00+00:00"),
            _candle("2026-01-15T14:30:00+00:00"),
            _candle("2026-01-16T01:00:00+00:00"),
            _candle("2026-01-16T14:30:00+00:00"),
            _candle("2026-01-17T01:00:00+00:00"),
            _candle("2026-01-17T14:30:00+00:00"),
        ],
        WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1),
    )

    assert len(windows) == 2
    assert windows[0].train_dates == (datetime(2026, 1, 15).date(),)
    assert windows[0].oos_dates == (datetime(2026, 1, 16).date(),)
    assert windows[1].train_dates == (datetime(2026, 1, 16).date(),)
    assert windows[1].oos_dates == (datetime(2026, 1, 17).date(),)
    assert max(candle.ts for candle in windows[0].train_candles) < min(
        candle.ts for candle in windows[0].oos_candles
    )


def test_walk_forward_rejects_live_forward_style_mixed_instruments() -> None:
    candles = [_candle("2026-01-15T01:00:00+00:00"), _candle("2026-01-16T01:00:00+00:00")]
    candles[1] = _candle("2026-01-16T01:00:00+00:00", instrument="GBP_USD")

    with pytest.raises(ValueError, match="one instrument"):
        build_walk_forward_windows(
            candles,
            WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1),
        )


def test_walk_forward_requires_complete_utc_sorted_candles() -> None:
    config = WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1)

    with pytest.raises(ValueError, match="complete"):
        build_walk_forward_windows(
            [
                _candle("2026-01-15T01:00:00+00:00", complete=False),
                _candle("2026-01-16T01:00:00+00:00"),
            ],
            config,
        )
    with pytest.raises(ValueError, match="UTC"):
        build_walk_forward_windows(
            [
                _candle("2026-01-15T01:00:00+01:00"),
                _candle("2026-01-16T01:00:00+00:00"),
            ],
            config,
        )
    with pytest.raises(ValueError, match="sorted"):
        build_walk_forward_windows(
            [
                _candle("2026-01-16T01:00:00+00:00"),
                _candle("2026-01-15T01:00:00+00:00"),
            ],
            config,
        )


def test_walk_forward_rejects_too_small_dataset() -> None:
    with pytest.raises(ValueError, match="too small"):
        build_walk_forward_windows(
            [_candle("2026-01-15T01:00:00+00:00")],
            WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1),
        )


def test_walk_forward_strategy_mode_discards_partial_session_days() -> None:
    strategy_config = strategy_config_for_params(
        strategy_config_from_defaults(load_default_config()),
        {"asia_start_offset_minutes": 30},
    )

    windows = build_walk_forward_windows(
        [
            _candle("2026-06-18T00:00:00+00:00"),
            _candle("2026-06-18T00:30:00+00:00"),
            _candle("2026-06-18T06:00:00+00:00"),
            _candle("2026-06-18T13:30:00+00:00"),
            _candle("2026-06-18T15:31:00+00:00"),
            _candle("2026-06-19T00:30:00+00:00"),
            _candle("2026-06-19T06:00:00+00:00"),
            _candle("2026-06-19T13:30:00+00:00"),
            _candle("2026-06-19T15:31:00+00:00"),
            _candle("2026-06-20T00:30:00+00:00"),
        ],
        WalkForwardConfig(train_window_days=1, oos_window_days=1, step_days=1),
        strategy_config=strategy_config,
    )

    assert len(windows) == 1
    assert [candle.ts.isoformat() for candle in windows[0].train_candles] == [
        "2026-06-18T00:30:00+00:00",
        "2026-06-18T06:00:00+00:00",
        "2026-06-18T13:30:00+00:00",
        "2026-06-18T15:31:00+00:00",
    ]
    assert [candle.ts.isoformat() for candle in windows[0].oos_candles] == [
        "2026-06-19T00:30:00+00:00",
        "2026-06-19T06:00:00+00:00",
        "2026-06-19T13:30:00+00:00",
        "2026-06-19T15:31:00+00:00",
    ]


def _candle(
    ts: str,
    *,
    instrument: str = "EUR_USD",
    complete: bool = True,
) -> ClosedCandle:
    parsed = datetime.fromisoformat(ts)
    if parsed.tzinfo is not None and parsed.utcoffset() != timedelta(0):
        parsed = parsed.replace(tzinfo=timezone(timedelta(hours=1)))
    return ClosedCandle(
        instrument=instrument,
        ts=parsed,
        o=Decimal("1.1000"),
        h=Decimal("1.1010"),
        low=Decimal("1.0990"),
        c=Decimal("1.1005"),
        volume=100,
        complete=complete,
    )
