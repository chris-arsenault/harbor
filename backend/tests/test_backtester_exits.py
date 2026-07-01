from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from harbor_bot.backtester.fills import (
    OpenBacktestPosition,
    simulate_bracket_exit,
    simulate_exit,
)
from harbor_bot.backtester.models import BacktestConfig
from harbor_bot.config.defaults import load_default_config
from harbor_bot.feed.candles import ClosedCandle
from harbor_bot.strategy.models import (
    InstrumentRules,
    LevelName,
    MarketEntrySetup,
    strategy_config_from_defaults,
)

TS = datetime(2026, 1, 15, 14, 0, tzinfo=UTC)
CONFIG = BacktestConfig()


def _candle(minute: int, *, high: str, low: str, close: str) -> ClosedCandle:
    return ClosedCandle(
        instrument="EUR_USD",
        ts=TS + timedelta(minutes=minute),
        o=Decimal(close),
        h=Decimal(high),
        low=Decimal(low),
        c=Decimal(close),
        volume=1,
    )


def test_time_stop_exits_at_close_after_duration() -> None:
    config = replace(_strategy(), exit_mode="time_stop", time_stop_minutes=120)
    position = _long(stop="1.09800", target="1.10400")
    # 130 minutes later, price has neither hit the stop nor the target.
    candle = _candle(130, high="1.10150", low="1.10050", close="1.10100")

    _, trade = simulate_exit(
        position,
        candle=candle,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[candle],
    )

    assert trade is not None
    assert trade.exit_reason == "time_stop"


def test_time_stop_holds_before_duration() -> None:
    config = replace(_strategy(), exit_mode="time_stop", time_stop_minutes=120)
    position = _long(stop="1.09800", target="1.10400")
    candle = _candle(30, high="1.10150", low="1.10050", close="1.10100")

    _, trade = simulate_exit(
        position,
        candle=candle,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[candle],
    )

    assert trade is None


def test_atr_trailing_stop_locks_in_profit_above_original_stop() -> None:
    config = replace(_strategy(), exit_mode="atr_trail", atr_trail_mult=Decimal("1.5"))
    position = _long(stop="1.09000", target="1.20000")
    rising = [
        _candle(0, high="1.10100", low="1.09950", close="1.10050"),
        _candle(1, high="1.10300", low="1.10100", close="1.10250"),
        _candle(2, high="1.10500", low="1.10300", close="1.10450"),
        _candle(3, high="1.10450", low="1.10000", close="1.10050"),
    ]

    trade = _run_sequence(position, rising, config)

    assert trade is not None
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price > Decimal("1.09000")  # trailed above the original stop
    assert trade.pnl > 0  # locked-in profit


def test_atr_trailing_stop_ignores_current_candle_extreme() -> None:
    # The trail must advance from candles closed before the current one: a
    # spike-and-collapse candle must not raise the trail with its own high and
    # then get stopped against its own low.
    config = replace(_strategy(), exit_mode="atr_trail", atr_trail_mult=Decimal("1.5"))
    position = _long(stop="1.09000", target="1.20000")
    sequence = [
        _candle(0, high="1.10100", low="1.09950", close="1.10050"),
        _candle(1, high="1.10150", low="1.10000", close="1.10100"),
        # Spike to 1.10800 then collapse to 1.10000: the prior-candle trail
        # (1.09925) is untouched, while a same-candle trail (~1.10162) would be.
        _candle(2, high="1.10800", low="1.10000", close="1.10400"),
    ]

    trade = _run_sequence(position, sequence, config)

    assert trade is None


def test_bracket_mode_matches_plain_bracket_exit() -> None:
    config = replace(_strategy(), exit_mode="bracket")
    position = _long(stop="1.09800", target="1.10400")
    target_hit = _candle(5, high="1.10450", low="1.10100", close="1.10420")

    _, dispatched = simulate_exit(
        position,
        candle=target_hit,
        strategy_config=config,
        backtest_config=CONFIG,
        instrument_rules=_rules(),
        recent_candles=[target_hit],
    )
    direct = simulate_bracket_exit(
        position, candle=target_hit, config=CONFIG, instrument_rules=_rules()
    )

    assert dispatched is not None
    assert direct is not None
    assert dispatched.exit_price == direct.exit_price
    assert dispatched.exit_reason == direct.exit_reason == "take_profit"


def _partial_config():
    return replace(
        _strategy(),
        exit_mode="partial_runner",
        partial_fraction=Decimal("0.5"),
        partial_at_r=Decimal("1.0"),
    )


def test_partial_runner_full_loss_when_stopped_before_one_r() -> None:
    # Entry 1.10000, stop 1.09800 (risk 20 pips), target 1.10400, 1R = 1.10200.
    position = _long(stop="1.09800", target="1.10400")
    stopped = [_candle(0, high="1.10100", low="1.09790", close="1.09850")]

    trade = _run_sequence(position, stopped, _partial_config())

    assert trade is not None
    assert trade.exit_reason == "stop_loss"
    assert trade.pnl < 0
    assert trade.pnl < Decimal("-15")  # near the full -1R (~-20)


def test_partial_runner_banks_partial_then_runs_to_breakeven() -> None:
    position = _long(stop="1.09800", target="1.10400")
    sequence = [
        _candle(0, high="1.10210", low="1.10050", close="1.10150"),  # touches 1R → scale out
        _candle(1, high="1.10120", low="1.09990", close="1.10000"),  # runner back to breakeven
    ]

    trade = _run_sequence(position, sequence, _partial_config())

    assert trade is not None
    assert trade.exit_reason == "runner_breakeven"
    assert trade.pnl > 0  # the banked half stays positive even as the runner exits flat


def test_partial_runner_banks_partial_then_runner_hits_target() -> None:
    position = _long(stop="1.09800", target="1.10400")
    breakeven = _run_sequence(
        _long(stop="1.09800", target="1.10400"),
        [
            _candle(0, high="1.10210", low="1.10050", close="1.10150"),
            _candle(1, high="1.10120", low="1.09990", close="1.10000"),
        ],
        _partial_config(),
    )
    sequence = [
        _candle(0, high="1.10210", low="1.10050", close="1.10150"),  # scale out at 1R
        _candle(1, high="1.10410", low="1.10180", close="1.10400"),  # runner to target
    ]

    trade = _run_sequence(position, sequence, _partial_config())

    assert trade is not None
    assert trade.exit_reason == "runner_target"
    assert breakeven is not None
    assert trade.pnl > breakeven.pnl  # letting the runner reach target beats a flat runner


def _run_sequence(position: OpenBacktestPosition, candles: list[ClosedCandle], config):
    history: list[ClosedCandle] = []
    for candle in candles:
        history.append(candle)
        position, trade = simulate_exit(
            position,
            candle=candle,
            strategy_config=config,
            backtest_config=CONFIG,
            instrument_rules=_rules(),
            recent_candles=history,
        )
        if trade is not None:
            return trade
    return None


def _strategy():
    return strategy_config_from_defaults(load_default_config())


def _long(*, stop: str, target: str) -> OpenBacktestPosition:
    setup = MarketEntrySetup(
        ts=TS,
        instrument="EUR_USD",
        side="long",
        level_name=LevelName.ASIA_LOW,
        entry_reference=Decimal("1.10000"),
        stop=Decimal(stop),
        target=Decimal(target),
        risk=Decimal("1.10000") - Decimal(stop),
        units=Decimal("10000"),
    )
    return OpenBacktestPosition(setup=setup, entry_price=Decimal("1.10000"), entry_ts=TS)


def _rules() -> InstrumentRules:
    return InstrumentRules(
        instrument="EUR_USD",
        pip_location=-4,
        display_precision=5,
        trade_units_precision=0,
        minimum_trade_size=Decimal("1"),
        unit_step=Decimal("1"),
    )
