from datetime import UTC, datetime
from decimal import Decimal

import pytest

from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.fvgs import detect_fvg
from harbor_bot.strategy.models import Bias, LevelName, SweepState, strategy_config_from_defaults


def test_bullish_fvg_after_bullish_sweep() -> None:
    fvg = detect_fvg(
        _bullish_gap(),
        active_sweep=_sweep(Bias.BULLISH),
        current_index=13,
        trading_date=datetime(2026, 1, 15).date(),
        config=_config(),
    )

    assert fvg is not None
    assert fvg.fvg_type == Bias.BULLISH
    assert fvg.bottom == Decimal("1.0910")
    assert fvg.top == Decimal("1.0920")
    assert fvg.midpoint == Decimal("1.0915")
    assert fvg.sweep.bias == Bias.BULLISH


def test_bearish_fvg_after_bearish_sweep() -> None:
    fvg = detect_fvg(
        _bearish_gap(),
        active_sweep=_sweep(Bias.BEARISH),
        current_index=13,
        trading_date=datetime(2026, 1, 15).date(),
        config=_config(),
    )

    assert fvg is not None
    assert fvg.fvg_type == Bias.BEARISH
    assert fvg.top == Decimal("1.0990")
    assert fvg.bottom == Decimal("1.0980")
    assert fvg.midpoint == Decimal("1.0985")


def test_wrong_direction_fvg_is_rejected() -> None:
    assert (
        detect_fvg(
            _bearish_gap(),
            active_sweep=_sweep(Bias.BULLISH),
            current_index=13,
            trading_date=datetime(2026, 1, 15).date(),
            config=_config(),
        )
        is None
    )


def test_fvg_after_deadline_is_rejected() -> None:
    assert (
        detect_fvg(
            _bullish_gap(),
            active_sweep=_sweep(Bias.BULLISH),
            current_index=19,
            trading_date=datetime(2026, 1, 15).date(),
            config=_config(),
        )
        is None
    )


def test_fvg_outside_ny_window_is_rejected() -> None:
    assert (
        detect_fvg(
            [
                _candle("2026-01-15T17:00:00+00:00", high="1.0910", low="1.0900"),
                _candle("2026-01-15T17:01:00+00:00", high="1.0920", low="1.0915"),
                _candle("2026-01-15T17:02:00+00:00", high="1.0930", low="1.0920"),
            ],
            active_sweep=_sweep(Bias.BULLISH),
            current_index=13,
            trading_date=datetime(2026, 1, 15).date(),
            config=_config(),
        )
        is None
    )


def test_fvg_detection_rejects_incomplete_candles() -> None:
    candles = _bullish_gap()
    candles[-1] = _candle(
        "2026-01-15T14:32:00+00:00",
        high="1.0930",
        low="1.0920",
        complete=False,
    )

    with pytest.raises(ValueError, match="closed candles only"):
        detect_fvg(
            candles,
            active_sweep=_sweep(Bias.BULLISH),
            current_index=13,
            trading_date=datetime(2026, 1, 15).date(),
            config=_config(),
        )


def _config():
    return strategy_config_from_defaults(load_default_config())


def _sweep(bias: Bias) -> SweepState:
    level_name = LevelName.ASIA_LOW if bias == Bias.BULLISH else LevelName.ASIA_HIGH
    return SweepState(
        level_name=level_name,
        level_price=Decimal("1.0900"),
        bias=bias,
        sweep_extreme=Decimal("1.0880") if bias == Bias.BULLISH else Decimal("1.1020"),
        swept_ts=datetime(2026, 1, 15, 14, 29, tzinfo=UTC),
        candle_index=10,
        fvg_deadline_index=18,
    )


def _bullish_gap() -> list[ClosedCandle]:
    return [
        _candle("2026-01-15T14:30:00+00:00", high="1.0910", low="1.0900"),
        _candle("2026-01-15T14:31:00+00:00", high="1.0915", low="1.0905"),
        _candle("2026-01-15T14:32:00+00:00", high="1.0930", low="1.0920"),
    ]


def _bearish_gap() -> list[ClosedCandle]:
    return [
        _candle("2026-01-15T14:30:00+00:00", high="1.1000", low="1.0990"),
        _candle("2026-01-15T14:31:00+00:00", high="1.0995", low="1.0985"),
        _candle("2026-01-15T14:32:00+00:00", high="1.0980", low="1.0970"),
    ]


def _candle(
    ts: str,
    *,
    high: str,
    low: str,
    complete: bool = True,
) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=datetime.fromisoformat(ts),
        o=Decimal("1.0900"),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal("1.0910"),
        volume=100,
        complete=complete,
    )
