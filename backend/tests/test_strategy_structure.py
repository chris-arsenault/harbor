from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from harbor_bot.backtester.data import load_candle_fixture
from harbor_bot.backtester.engine import run_backtest
from harbor_bot.backtester.models import BacktestInput
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.optimizer.config import apply_params_to_strategy_config
from harbor_bot.strategy.models import (
    Bias,
    InstrumentRules,
    LevelName,
    SweepState,
    strategy_config_from_defaults,
)
from harbor_bot.strategy.structure import mss_confirmed, volume_spike

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "backtester"
TS = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)


def _bar(index: int, *, high: str, low: str, close: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=TS + timedelta(minutes=index),
        o=Decimal(close),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=1,
    )


# Index 2 is a fractal swing high (1.1020, width 2); index 5 is the bullish low sweep.
_BULLISH_PIVOT = [
    _bar(0, high="1.1005", low="1.0995", close="1.1000"),
    _bar(1, high="1.1010", low="1.1000", close="1.1005"),
    _bar(2, high="1.1020", low="1.1010", close="1.1015"),
    _bar(3, high="1.1012", low="1.1002", close="1.1008"),
    _bar(4, high="1.1008", low="1.0998", close="1.1003"),
    _bar(5, high="1.1000", low="1.0980", close="1.0990"),
    _bar(6, high="1.1015", low="1.1005", close="1.1010"),
    _bar(7, high="1.1025", low="1.1015", close="1.1022"),
]


def test_default_config_does_not_require_mss() -> None:
    assert _config().require_mss is False


def test_apply_params_toggles_require_mss() -> None:
    base = _config()

    assert apply_params_to_strategy_config(base, {"require_mss": True}).require_mss is True
    assert apply_params_to_strategy_config(base, {"require_mss": "false"}).require_mss is False


def test_bullish_mss_requires_break_of_a_real_swing_high() -> None:
    sweep = _sweep(Bias.BULLISH, index=5)

    # Through index 6 the close (1.1010) has not broken the swing-high pivot (1.1020).
    assert (
        mss_confirmed(_BULLISH_PIVOT[:7], sweep=sweep, current_index=6, config=_config()) is False
    )
    # Index 7 closes at 1.1022, breaking the pivot.
    assert mss_confirmed(_BULLISH_PIVOT, sweep=sweep, current_index=7, config=_config()) is True


def test_bearish_mss_requires_break_of_a_real_swing_low() -> None:
    history = [
        _bar(0, high="1.1010", low="1.1000", close="1.1005"),
        _bar(1, high="1.1008", low="1.0998", close="1.1003"),
        _bar(2, high="1.1005", low="1.0985", close="1.0990"),  # swing-low pivot (1.0985)
        _bar(3, high="1.1007", low="1.0995", close="1.1000"),
        _bar(4, high="1.1009", low="1.0998", close="1.1004"),
        _bar(5, high="1.1030", low="1.1010", close="1.1015"),  # bearish high sweep
        _bar(6, high="1.1020", low="1.0990", close="1.0992"),  # not yet below 1.0985
        _bar(7, high="1.1000", low="1.0980", close="1.0982"),  # closes below the pivot
    ]
    sweep = _sweep(Bias.BEARISH, index=5)

    assert mss_confirmed(history[:7], sweep=sweep, current_index=6, config=_config()) is False
    assert mss_confirmed(history, sweep=sweep, current_index=7, config=_config()) is True


def test_mss_unconfirmed_without_a_swing_pivot() -> None:
    # Monotonic rise before the sweep: no fractal swing high exists to break.
    rising = [
        _bar(0, high="1.1000", low="1.0990", close="1.0995"),
        _bar(1, high="1.1010", low="1.1000", close="1.1005"),
        _bar(2, high="1.1020", low="1.1010", close="1.1015"),
        _bar(3, high="1.1030", low="1.1020", close="1.1025"),
        _bar(4, high="1.1040", low="1.1030", close="1.1035"),
        _bar(5, high="1.1005", low="1.0980", close="1.0990"),  # low sweep
        _bar(6, high="1.1060", low="1.1030", close="1.1055"),  # high close, but no prior pivot
    ]
    sweep = _sweep(Bias.BULLISH, index=5)

    assert mss_confirmed(rising, sweep=sweep, current_index=6, config=_config()) is False


def test_default_config_does_not_require_volume_spike() -> None:
    assert _config().require_volume_spike is False


def test_volume_spike_requires_above_average_volume() -> None:
    config = _config()  # swing_lookback 5
    baseline = [_volume_candle(index, 10) for index in range(5)]

    assert volume_spike(baseline + [_volume_candle(5, 25)], current_index=5, config=config) is True
    assert volume_spike(baseline + [_volume_candle(5, 5)], current_index=5, config=config) is False
    assert volume_spike([_volume_candle(0, 25)], current_index=0, config=config) is False


def _volume_candle(index: int, volume: int) -> ClosedCandle:
    price = Decimal("1.10000")
    return ClosedCandle(
        instrument="EUR_USD",
        ts=TS + timedelta(minutes=index),
        o=price,
        h=price,
        low=price,
        c=price,
        volume=volume,
    )


def test_require_mss_never_adds_trades() -> None:
    candles = load_candle_fixture(FIXTURE_DIR / "clean_signal_day.json")
    without = _run(candles, require_mss=False)
    with_gate = _run(candles, require_mss=True)

    assert with_gate.stats.trade_count <= without.stats.trade_count


def _run(candles: tuple[ClosedCandle, ...], *, require_mss: bool):
    config = replace(_config(), require_mss=require_mss)
    return run_backtest(
        BacktestInput(
            instrument="EUR_USD",
            candles=candles,
            strategy_config=config,
            instrument_rules=_rules(),
        )
    )


def _config():
    return strategy_config_from_defaults(load_default_config())


def _sweep(bias: Bias, *, index: int) -> SweepState:
    level = LevelName.ASIA_LOW if bias == Bias.BULLISH else LevelName.ASIA_HIGH
    return SweepState(
        level_name=level,
        level_price=Decimal("1.1000"),
        bias=bias,
        sweep_extreme=Decimal("1.0980"),
        swept_ts=TS + timedelta(minutes=index),
        candle_index=index,
        fvg_deadline_index=index + 8,
    )


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
